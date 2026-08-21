from __future__ import annotations
import json,os,sys
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
REPO_ROOT=Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from tools.ai_client import classify,ClassificationError
from .models import SentimentPost,SentimentAIAnalysis
MODEL=os.environ.get("SENTIMENT_CLASSIFIER_MODEL","gpt-4o-mini")
PROVIDER=os.environ.get("SENTIMENT_AI_PROVIDER","openai")
CATEGORIES=Literal["OPERATIONS","UPDATE","EVENT","BALANCE","CLASS","CONTENT","ITEM","REWARD","MONETIZATION","BUG","SERVER","UI_UX","CONVENIENCE","NEW_RETURNING","OTHER"]
class Result(BaseModel):
 category:CATEGORIES
 sentiment:Literal["POSITIVE","NEUTRAL","NEGATIVE"]
 sentiment_value:float=Field(ge=-1,le=1)
 score_eligible:bool
 issue_name:str=Field(description="10~24\uc790\uc758 \uad6c\uccb4\uc801 \uc774\uc288\uba85")
 keywords:list[str]=Field(default_factory=list,max_length=6)
 rationale:str
SYSTEM="""\ub108\ub294 \ub77c\ud14c\uc77c \uac8c\uc784 \ucee4\ubba4\ub2c8\ud2f0 \ubd84\uc11d\uae30\ub2e4. \uac8c\uc2dc\ubb3c\uc758 \uc2e4\uc81c \ud45c\ud604\ub9cc \uadfc\uac70\ub85c \ubd84\ub958\ud574\ub77c. \uc791\uc131\uc790\ub098 \uac1c\uc778\uc744 \ud3c9\uac00\ud558\uc9c0 \ub9d0\uace0 \uac8c\uc784 \uc774\uc288\ub9cc \ubd84\uc11d\ud55c\ub2e4. \uac1c\uc778 \uacf5\uaca9, \uc7a1\ub2f4, \ub2e8\uc21c \uac70\ub798, \uad11\uace0, \uc758\ubbf8 \uc5c6\ub294 \uc9e7\uc740 \uae00, \ub2e8\uc21c \uc9c8\ubb38\uc740 score_eligible=false\ub85c \ud558\ub418 \uce74\ud14c\uace0\ub9ac\uc640 \uc774\uc288\uba85\uc740 \uc791\uc131\ud55c\ub2e4. \uc774\uc288\uba85\uc740 '\uc6b4\uc601 \ubb38\uc81c'\ucc98\ub7fc \ud3ec\uad04\uc801\uc73c\ub85c \uc4f0\uc9c0 \ub9d0\uace0 '\uc810\ud551\ud018 \ubcf4\uc0c1 \uc644\ub8cc \uc870\uac74'\ucc98\ub7fc \uad6c\uccb4\uc801\uc73c\ub85c \uc4f4\ub2e4. \ub77c\ud14c\uc77c \uc740\uc5b4\uc640 \ucd95\uc57d\uc5b4\ub97c \ubb38\ub9e5\uc5d0 \ub9de\uac8c \ud574\uc11d\ud558\ub418 \ubd88\ud655\uc2e4\ud558\uba74 \ucd94\uce21\ud558\uc9c0 \ub9c8\ub77c."""
def analyze_with_ai(db:Session,limit:int=25)->dict:
 done_ids=set(db.execute(select(SentimentAIAnalysis.post_db_id)).scalars().all())
 pool=[p for p in db.execute(select(SentimentPost).order_by(SentimentPost.created_at.desc())).scalars().all() if p.id not in done_ids and len((p.title or '')+(p.content or ''))>=12]
 pool.sort(key=lambda p:(p.score_eligible,p.category!="OTHER",len(p.content or ""),p.created_at or p.collected_at),reverse=True)
 candidates=pool[:max(0,min(limit,25))]
 done=failed=0
 for post in candidates:
  prompt=f"\uc81c\ubaa9: {post.title}\n\ubcf8\ubb38: {(post.content or '')[:1800]}\n\ucd9c\ucc98: {post.source}"
  try: result=classify(SYSTEM,prompt,Result,MODEL,provider=PROVIDER)
  except ClassificationError: failed+=1; continue
  row=SentimentAIAnalysis(post_db_id=post.id,model=MODEL,category=result.category,sentiment=result.sentiment,sentiment_value=result.sentiment_value,score_eligible=result.score_eligible,issue_name=result.issue_name[:160],keywords=json.dumps(result.keywords,ensure_ascii=False),rationale=result.rationale[:500])
  db.add(row); post.category=result.category; post.sentiment=result.sentiment; post.sentiment_value=result.sentiment_value; post.score_eligible=result.score_eligible; post.issue_key=f"AI:{result.issue_name[:115]}"; post.keywords=json.dumps(result.keywords,ensure_ascii=False); done+=1
 db.commit(); return {"selected":len(candidates),"analyzed":done,"failed":failed,"model":MODEL}
