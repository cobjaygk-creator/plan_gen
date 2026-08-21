from __future__ import annotations
import json,re
from collections import Counter
from datetime import datetime,timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import SentimentPost

CATEGORY_RULES={
 "OPERATIONS":["\uc6b4\uc601","\uc6b4\uc601\uc9c4","gm","\uacf5\uc9c0"],
 "UPDATE":["\uc5c5\ub370\uc774\ud2b8","\ud328\uce58","\ud14c\uc2a4\ud2b8"],
 "EVENT":["\uc774\ubca4\ud2b8","\ucd9c\uc11d","\ucfe0\ud3f0"],
 "BALANCE":["\ubc38\ub7f0\uc2a4","\ub108\ud504","\uc0c1\ud5a5","\ud558\ud5a5"],
 "CLASS":["\uc9c1\uc5c5","\uc804\uc9c1","\uc2a4\ud0ac","\ub525"],
 "CONTENT":["\ub358\uc804","\ub808\uc774\ub4dc","\ubcf4\uc2a4","\ucf58\ud150\uce20","\uc810\ud551\ud018"],
 "ITEM":["\uc544\uc774\ud15c","\uc7a5\ube44","\uc778\ucc08\ud2b8","\uc7ac\ub8cc"],
 "REWARD":["\ubcf4\uc0c1","\uc9c0\uae09","\ud61c\ud0dd"],
 "MONETIZATION":["\ud604\uc9c8","\uce90\uc2dc","\ud328\ud0a4\uc9c0","\ud655\ub960","\uacfc\uae08"],
 "BUG":["\ubc84\uadf8","\uc624\ub958","\ud29c\uae40","\ud050\ub77c\uc774\uc5b8\ud2b8"],
 "SERVER":["\uc11c\ubc84","\ub809","\uc811\uc18d","\uc810\uac80"],
 "UI_UX":["ui","ux","\uc778\ud130\ud398\uc774\uc2a4","\uac00\ub3c5\uc131"],
 "CONVENIENCE":["\ud3b8\uc758","\uc790\ub3d9","\uc778\ubca4\ud1a0\ub9ac","\ucc3d\uace0"],
 "NEW_RETURNING":["\ub274\ube44","\ubcf5\uadc0","\uc2e0\uaddc","\uc720\uc785"],
}
POS=["\uc88b","\uafc0","\uc7ac\ubc0c","\uac10\uc0ac","\ud61c\uc790","\uc88b\ub2e4","\uc88b\ub124","\uad1c\ucc2e","\uc7ac\ubc0c","\uc7ac\ubbf8","\ub9cc\uc871","\uac10\uc0ac","\ud61c\uc790","\ucd94\ucc9c","\uc774\uc058"]
NEG=["\uc2eb","\uc9dc\uc99d","\ubcd1\uc2e0","\uc4f0\ub808\uae30","\uc2eb\ub2e4","\ubcc4\ub85c","\ub178\uc7bc","\ucd5c\uc545","\ubd88\ub9cc","\ubb38\uc81c","\ub9dd","\uc5ed\uacb9","\ud30c\ub780","\ub809","\ubc84\uadf8","\uc624\ub958","\uc548\ub428","\uc548\ub3fc","\uc81c\ubc1c"]
EXCLUDE={"ADVERTISEMENT":["\uad11\uace0","\ud64d\ubcf4","\ucf54\ub4dc \ucd94\ucc9c"],"TRADE":["\ud310\ub9e4","\uad6c\ub9e4","\uc0bd\ub2c8\ub2e4","\ud314\uc544\uc694"],"OFFTOPIC":["\ud0c0\uac8c\uc784"]}
STOP={"\ub77c\ud14c\uc77c","\uc774\uac70","\uc800\uac70","\uc9c4\uc9dc","\uadf8\ub0e5","\uc624\ub298","\uc544\ub2c8","\ud558\ub294","\uc788\ub294","\uc5c6\ub294","\ud574\uc8fc\uc138\uc694","\uc9c8\ubb38"}

def _terms(text): return re.findall(r"[A-Za-z][A-Za-z0-9_+-]{1,}|[\uac00-\ud7a3]{2,}",text.lower())
def classify(post:SentimentPost):
 text=f"{post.title} {post.content or ''}".lower()
 reason=None
 for key,words in EXCLUDE.items():
  if any(w in text for w in words): reason=key; break
 if not reason and len(text.strip())<8: reason="TOO_SHORT"
 category="OTHER"; best=0; matched=None
 for key,words in CATEGORY_RULES.items():
  ranked=sorted(((text.count(w),w) for w in words),reverse=True)
  count=sum(x[0] for x in ranked)
  if count>best: category,best,matched=key,count,ranked[0][1]
 pos=sum(text.count(w) for w in POS); neg=sum(text.count(w) for w in NEG)
 value=max(-1.0,min(1.0,(pos-neg)/max(1,pos+neg)))
 sentiment="POSITIVE" if value>.15 else "NEGATIVE" if value<-.15 else "NEUTRAL"
 tokens=[t for t in _terms(f"{post.title} {post.content or ''}") if t not in STOP and len(t)<25]
 common=[w for w,_ in Counter(tokens).most_common(6)]
 issue=(common[0] if common else category)
 if category!="OTHER": issue=f"{category}:{matched or category}"
 post.category=category; post.sentiment=sentiment; post.sentiment_value=value
 post.score_eligible=reason is None; post.exclusion_reason=reason; post.issue_key=issue
 post.keywords=json.dumps(common,ensure_ascii=False); post.analyzed_at=datetime.now(timezone.utc)

def analyze_pending(db:Session)->int:
 posts=db.execute(select(SentimentPost).where(SentimentPost.analyzed_at.is_(None))).scalars().all()
 for post in posts: classify(post)
 db.commit(); return len(posts)
