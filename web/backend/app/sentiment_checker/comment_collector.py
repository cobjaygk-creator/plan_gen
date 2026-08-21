from __future__ import annotations
import hashlib,http.cookiejar,re,time
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPCookieProcessor
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import SentimentPost,SentimentComment
UA="Mozilla/5.0 (compatible; UXTLER-Internal-Research/1.0)"
POS=["\uc88b","\uace0\ub9c8","\uac10\uc0ac","\ub9de\uc544","\ub3d9\uc758","\u3147\u3148","\ud61c\uc790","\uafc0"]
NEG=["\uc2eb","\uc9dc\uc99d","\ubb38\uc81c","\uc624\ub958","\ubc84\uadf8","\ubcc4\ub85c","\ucd5c\uc545","\uc548\ub428","\uc548\ub3fc"]
AGREE=["\ub9de\uc544","\ub3d9\uc758","\uadf8\ub7ec\uac8c","\u3147\u3148","\uc778\uc815","\ub9de\ub294"]
DISAGREE=["\uc544\ub2c8","\uc544\ub2d8","\ud2c0\ub9bc","\uadfc\ub370","\uadf8\uac74","\ubc18\ub300"]
def _headers(referer):return {"User-Agent":UA,"Accept-Language":"ko-KR","Referer":referer}
def _date(value):
 value=(value or "").strip().replace("AM","AM").replace("PM","PM")
 for fmt in ("%Y.%m.%d %I:%M %p","%Y.%m.%d %H:%M"):
  try:return datetime.strptime(value,fmt).replace(tzinfo=timezone.utc)
  except ValueError:pass
 return None
def _analyze(text):
 low=text.lower();pos=sum(low.count(x) for x in POS);neg=sum(low.count(x) for x in NEG);value=max(-1,min(1,(pos-neg)/max(1,pos+neg)))
 sentiment="POSITIVE" if value>.15 else "NEGATIVE" if value<-.15 else "NEUTRAL"
 agree=sum(low.count(x) for x in AGREE);disagree=sum(low.count(x) for x in DISAGREE);stance="AGREE" if agree>disagree else "DISAGREE" if disagree>agree else "NEUTRAL"
 return sentiment,float(value),stance
def _fetch_pages(post):
 jar=http.cookiejar.CookieJar();opener=build_opener(HTTPCookieProcessor(jar));headers=_headers(post.url)
 raw=opener.open(Request(post.url,headers=headers),timeout=20).read();soup=BeautifulSoup(raw,"html.parser",from_encoding="utf-8")
 token_node=soup.select_one('input[name="ViewToken"]')
 if not token_node:return []
 token=token_node.get("value","");pages=[];page_no=1;max_pages=5
 while page_no<=max_pages:
  data=urlencode({"token":token,"PageNo":str(page_no)}).encode()
  req=Request("https://www.latale.com/community/comment",data=data,headers={**headers,"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8","X-Requested-With":"XMLHttpRequest","Accept":"text/html, */*; q=0.01"})
  body=opener.open(req,timeout=20).read();fragment=BeautifulSoup(body,"html.parser",from_encoding="utf-8");pages.append(fragment)
  nums=[int(x) for x in re.findall(r"PageMove\((\d+)\)",body.decode("utf-8","replace"))]
  actual_max=max(nums or [1]);max_pages=min(5,actual_max)
  page_no+=1;time.sleep(.15)
 return pages
def collect_comments(db:Session,post_limit:int=30)->dict:
 posts=db.execute(select(SentimentPost).where(SentimentPost.source=="LATALE_OFFICIAL").order_by(SentimentPost.created_at.desc()).limit(post_limit)).scalars().all()
 found=new=updated=0;errors=[]
 for post in posts:
  try:pages=_fetch_pages(post)
  except Exception as exc:errors.append(f"{post.post_id}:{type(exc).__name__}");continue
  count=0
  for page in pages:
   for node in page.select("section.comment:not(.write)"):
    content_node=node.select_one(".content-wrap");author_node=node.select_one(".user-nickname");date_node=node.select_one("time")
    if not content_node:continue
    content=content_node.get_text(" ",strip=True);author=author_node.get_text(" ",strip=True) if author_node else "";created=_date(date_node.get_text(strip=True) if date_node else "")
    cid=hashlib.sha256(f"{post.id}|{author}|{created}|{content}".encode()).hexdigest();sentiment,value,stance=_analyze(content)
    row=db.execute(select(SentimentComment).where(SentimentComment.post_db_id==post.id,SentimentComment.comment_id==cid)).scalar_one_or_none()
    like_node=node.select_one(".like button");upvotes=int(re.sub(r"\D","",like_node.get_text()) or 0) if like_node else 0
    if row is None:
     db.add(SentimentComment(post_db_id=post.id,comment_id=cid,source=post.source,content=content[:5000],author_hash=hashlib.sha256(f"{post.source}:{author}".encode()).hexdigest() if author else None,created_at=created,upvotes=upvotes,sentiment=sentiment,sentiment_value=value,stance=stance));new+=1
    else:row.upvotes=upvotes;row.sentiment=sentiment;row.sentiment_value=value;row.stance=stance;updated+=1
    found+=1;count+=1
  post.comments=max(post.comments,count)
  db.commit();time.sleep(.2)
 return {"posts_checked":len(posts),"found":found,"new":new,"updated":updated,"errors":errors}
