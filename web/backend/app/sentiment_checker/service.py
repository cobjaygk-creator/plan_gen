from __future__ import annotations
import math
from collections import Counter
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import SentimentPost,SentimentReference,SentimentSnapshot,SentimentAIAnalysis,SentimentComment
from .clustering import cluster_posts,representative_name
CATEGORY_LABELS={"OPERATIONS":"\uc6b4\uc601","UPDATE":"\uc5c5\ub370\uc774\ud2b8","EVENT":"\uc774\ubca4\ud2b8","BALANCE":"\ubc38\ub7f0\uc2a4","CLASS":"\uc9c1\uc5c5","CONTENT":"\ucf58\ud150\uce20","ITEM":"\uc544\uc774\ud15c","REWARD":"\ubcf4\uc0c1","MONETIZATION":"\uacfc\uae08","BUG":"\ubc84\uadf8","SERVER":"\uc11c\ubc84","UI_UX":"UI/UX","CONVENIENCE":"\ud3b8\uc758\uc131","NEW_RETURNING":"\uc2e0\uaddc/\ubcf5\uadc0","OTHER":"\uae30\ud0c0"}
SOURCE_LABELS={"DCINSIDE":"DCInside \ub77c\ud14c\uc77c","DCINSIDE_PRIRING":"\ud504\ub9ac\ub9c1(\ub77c\ud14c\uc77c)","LATALE_OFFICIAL":"\ub77c\ud14c\uc77c \uacf5\uc2dd"}
def _aware(d): return None if d is None else d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
def _score(posts):
 eligible=[p for p in posts if p.score_eligible]
 if not eligible:return 50.0
 values=[]
 for p in eligible:
  engagement=1+min(1.5,math.log1p(p.comments+p.upvotes*2)/4); source=1 if p.source.startswith("DCINSIDE") else 1.1
  values.append((p.sentiment_value,engagement*source))
 raw=sum(v*w for v,w in values)/sum(w for _,w in values); confidence=min(1,len(eligible)/20)
 return round(50+50*raw*confidence,1)
def _period_posts(posts,start,end=None): return [p for p in posts if _aware(p.created_at) and _aware(p.created_at)>=start and (end is None or _aware(p.created_at)<end)]
def _issue_terms(title):
 return {x for x in title.lower().replace(":"," ").replace("/"," ").split() if len(x)>=2}
def _display_issue_name(posts,title,category):
 text=" ".join(f"{p.title} {p.issue_key}" for p in posts).lower()
 if category=="OTHER" and len(posts)>=3:
  if "\uae38\ub4dc" in text or "\ub85c\ub9dd" in text: return "\uae38\ub4dc\u00b7\ucee4\ubba4\ub2c8\ud2f0 \uac08\ub4f1"
  if "\ud5ec\ud1b5" in text: return "\ud2b9\uc815 \uc774\uc6a9\uc790 \uad00\ub828 \ubc18\ubcf5 \ub17c\uc7c1"
  if "\ud2b8\uc9f9" in text: return "\ucee4\ubba4\ub2c8\ud2f0 \uc774\uc6a9\uc790 \uac04 \uac08\ub4f1"
  if any(x in text for x in ("\uc7a1\ub2f4","\uac1c\uc778 \uacf5\uaca9","\ube44\ubc29","\uc695\uc124")): return "\uac1c\uc778 \uac04 \ub17c\uc7c1\u00b7\ube44\ubc29 \uc99d\uac00"
 return title
def _issue_rows(current,previous):
 current_groups=cluster_posts(current); previous_groups=cluster_posts(previous)
 previous_issues=[(representative_name(group),len(group)) for group in previous_groups if group]
 rows=[]
 for posts in current_groups:
  posts.sort(key=lambda p:_aware(p.created_at) or datetime.min.replace(tzinfo=timezone.utc),reverse=True)
  cats=Counter(p.category for p in posts); sentiments=Counter(p.sentiment for p in posts); category=cats.most_common(1)[0][0]
  raw_title=representative_name(posts); title=_display_issue_name(posts,raw_title,category); terms=_issue_terms(raw_title); previous_mentions=0
  for previous_title,count in previous_issues:
   previous_terms=_issue_terms(previous_title)
   similarity=len(terms & previous_terms)/max(1,len(terms | previous_terms))
   if similarity>=.34: previous_mentions=max(previous_mentions,count)
  growth=len(posts)-previous_mentions
  rows.append({"key":f"{category}:{raw_title}","title":title,"category":CATEGORY_LABELS.get(category,"\uae30\ud0c0"),"mentions":len(posts),"growth":growth,"positive":round(sentiments["POSITIVE"]*100/len(posts)),"neutral":round(sentiments["NEUTRAL"]*100/len(posts)),"negative":round(sentiments["NEGATIVE"]*100/len(posts)),"representative":[{"title":p.title,"url":p.url,"source":SOURCE_LABELS.get(p.source,p.source),"created_at":p.created_at.isoformat() if p.created_at else None} for p in posts[:3]]})
 rows.sort(key=lambda x:(x["mentions"]*2+max(0,x["growth"]),x["negative"]),reverse=True); return rows
def dashboard(db:Session,hours:int=24):
 now=datetime.now(timezone.utc); start=now-timedelta(hours=hours); prev_start=start-timedelta(hours=hours)
 all_posts=db.execute(select(SentimentPost)).scalars().all(); current=_period_posts(all_posts,start); previous=_period_posts(all_posts,prev_start,start)
 current_ids={p.id for p in current}; comments=[c for c in db.execute(select(SentimentComment)).scalars().all() if c.post_db_id in current_ids]
 comment_sentiments=Counter(c.sentiment for c in comments); comment_stances=Counter(c.stance for c in comments)
 issues=_issue_rows(current,previous); analysis_posts=current; analysis_basis="SELECTED_PERIOD"
 if len(current)<10 or len(issues)<3:
  analysis_posts=_period_posts(all_posts,now-timedelta(days=7)); analysis_basis="RECENT_7_DAYS"
  issues=_issue_rows(analysis_posts,[])
 if len(issues)<1 and all_posts:
  analysis_posts=all_posts; analysis_basis="ALL_STORED"
  issues=_issue_rows(analysis_posts,[])
 score=_score(current); prev_score=_score(previous)
 source_stats=[{"source":label,"count":len(ps),"score":_score(ps)} for source,label in SOURCE_LABELS.items() for ps in [[p for p in current if p.source==source]]]
 categories=Counter(CATEGORY_LABELS.get(p.category,"\uae30\ud0c0") for p in analysis_posts if p.score_eligible)
 exclusions=Counter(p.exclusion_reason or ("AI_EXCLUDED" if not p.score_eligible else "") for p in current if not p.score_eligible)
 exclusion_labels={"TOO_SHORT":"\uc9e7\uc740 \uae00\u00b7\ub2e8\uc21c \ubc18\uc751","QUESTION":"\ub2e8\uc21c \uc9c8\ubb38","ADVERTISEMENT":"\uad11\uace0\uc131 \uae00","TRADE":"\uac70\ub798 \uae00","OFFTOPIC":"\uad00\ub828 \uc5c6\ub294 \uae00","AI_EXCLUDED":"\uc7a1\ub2f4\u00b7\uac1c\uc778 \ub17c\uc7c1"}
 observations=[{"name":exclusion_labels.get(k,k),"count":v,"reason":k} for k,v in exclusions.most_common(5)]
 refs=db.execute(select(SentimentReference).order_by(SentimentReference.published_at.desc())).scalars().all(); related=[{"title":r.title,"url":r.url,"published_at":r.published_at.isoformat() if r.published_at else None,"relation":"TIME_ASSOCIATION"} for r in refs if _aware(r.published_at) and _aware(r.published_at)>=start-timedelta(days=3)][:6]
 top=issues[:8]
 brief=(f"\ubd84\uc11d \ub300\uc0c1 \uac8c\uc2dc\uae00 {len(analysis_posts)}\uac74\uc744 \ubb36\uc740 \uacb0\uacfc, {', '.join(i['title'][:24] for i in top[:3])}\uc774(\uac00) \uac00\uc7a5 \ub9ce\uc774 \ubc18\ubcf5\ub41c \uc774\uc288\uc785\ub2c8\ub2e4. \uac01 \uc774\uc288\ub97c \ub204\ub974\uba74 \uadfc\uac70 \uac8c\uc2dc\uae00\uacfc \ub300\ud45c \uc758\uacac\uc744 \ud655\uc778\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4." if top else "\uc120\ud0dd\ud55c \uae30\uac04\uc5d0 \uc774\uc288\ub85c \ubb36\uc744 \uac8c\uc2dc\uae00\uc774 \ucda9\ubd84\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.")
 if comments:
  brief += f" 공식 커뮤니티 댓글 {len(comments)}건 중 동의 {comment_stances['AGREE']}건, 반론 {comment_stances['DISAGREE']}건이 확인됩니다."
 snapshots=db.execute(select(SentimentSnapshot).where(SentimentSnapshot.period_hours==hours).order_by(SentimentSnapshot.observed_at.desc()).limit(48)).scalars().all()
 timeline=[{"observed_at":x.observed_at.isoformat(),"score":x.sentiment_score,"count":x.post_count} for x in reversed(snapshots)]
 ai_ids={x.post_db_id for x in db.execute(select(SentimentAIAnalysis)).scalars().all()}; ai_analyzed=sum(p.id in ai_ids for p in current)
 return {"generated_at":now.isoformat(),"period_hours":hours,"analysis_basis":analysis_basis,"analysis_count":len(analysis_posts),"metrics":{"stored_total":len(all_posts),"collected":len(current),"eligible":sum(p.score_eligible for p in current),"issue_count":len(issues),"ai_analyzed":ai_analyzed,"ai_pending":max(0,len(current)-ai_analyzed),"analysis_coverage":round(ai_analyzed*100/max(1,len(current))),"score":score,"change":round(score-prev_score,1),"positive":sum(p.sentiment=="POSITIVE" for p in current),"neutral":sum(p.sentiment=="NEUTRAL" for p in current),"negative":sum(p.sentiment=="NEGATIVE" for p in current)},"brief":brief,"comment_metrics":{"count":len(comments),"positive":comment_sentiments["POSITIVE"],"neutral":comment_sentiments["NEUTRAL"],"negative":comment_sentiments["NEGATIVE"],"agree":comment_stances["AGREE"],"disagree":comment_stances["DISAGREE"],"stance_neutral":comment_stances["NEUTRAL"]},"issues":top,"spikes":[i for i in issues if i["growth"]>=2][:5],"sources":source_stats,"categories":[{"name":k,"count":v} for k,v in categories.most_common(8)],"observations":observations,"references":related,"timeline":timeline,"recent":[{"title":p.title,"url":p.url,"source":SOURCE_LABELS.get(p.source,p.source),"created_at":p.created_at.isoformat() if p.created_at else None,"sentiment":p.sentiment,"category":CATEGORY_LABELS.get(p.category,"\uae30\ud0c0")} for p in sorted(current,key=lambda p:_aware(p.created_at) or datetime.min.replace(tzinfo=timezone.utc),reverse=True)[:12]]}
def save_snapshot(db:Session,hours:int=24):
 data=dashboard(db,hours); m=data["metrics"]
 row=SentimentSnapshot(period_hours=hours,post_count=m["collected"],eligible_count=m["eligible"],sentiment_score=m["score"],positive_count=m["positive"],neutral_count=m["neutral"],negative_count=m["negative"])
 db.add(row);db.commit();return row


def issue_detail(db:Session,key:str,hours:int=168):
 now=datetime.now(timezone.utc); start=now-timedelta(hours=hours)
 posts=_period_posts(db.execute(select(SentimentPost)).scalars().all(),start)
 target=None; title=""; category="OTHER"
 for group in cluster_posts(posts):
  if not group: continue
  name=representative_name(group); candidate=f"{group[0].category}:{name}"
  if candidate==key: target=group;title=name;category=group[0].category;break
 if target is None:
  posts=db.execute(select(SentimentPost)).scalars().all()
  for group in cluster_posts(posts):
   if not group: continue
   name=representative_name(group); candidate=f"{group[0].category}:{name}"
   if candidate==key: target=group;title=name;category=group[0].category;break
 if target is None:return None
 target.sort(key=lambda p:_aware(p.created_at) or datetime.min.replace(tzinfo=timezone.utc),reverse=True)
 sentiments=Counter(p.sentiment for p in target); buckets=Counter((_aware(p.created_at).date().isoformat()) for p in target if _aware(p.created_at))
 target_ids=[p.id for p in target]
 comments=db.execute(select(SentimentComment).where(SentimentComment.post_db_id.in_(target_ids)).order_by(SentimentComment.created_at.desc())).scalars().all()
 comment_sentiments=Counter(c.sentiment for c in comments);stances=Counter(c.stance for c in comments)
 ai_rows=db.execute(select(SentimentAIAnalysis).where(SentimentAIAnalysis.post_db_id.in_(target_ids))).scalars().all()
 rationales=[x.rationale for x in ai_rows if x.rationale]
 refs=db.execute(select(SentimentReference).order_by(SentimentReference.published_at.desc())).scalars().all()
 issue_terms={x for x in title.lower().split() if len(x)>=2}
 related=[]
 for r in refs:
  overlap=len(issue_terms & {x for x in r.title.lower().split() if len(x)>=2})
  temporal=any(_aware(p.created_at) and _aware(r.published_at) and abs((_aware(p.created_at)-_aware(r.published_at)).total_seconds())<=3*86400 for p in target)
  if overlap or temporal: related.append({"title":r.title,"url":r.url,"published_at":r.published_at.isoformat() if r.published_at else None,"overlap":overlap,"relation":"KEYWORD_AND_TIME" if overlap and temporal else "KEYWORD" if overlap else "TIME"})
 related.sort(key=lambda x:(x["overlap"],x["published_at"] or ""),reverse=True)
 negative=round(sentiments["NEGATIVE"]*100/len(target));positive=round(sentiments["POSITIVE"]*100/len(target));neutral=100-negative-positive
 interpretation=(rationales[0] if rationales else f"{len(target)}\uac74\uc758 \uadfc\uac70\uc5d0\uc11c {CATEGORY_LABELS.get(category,'\uae30\ud0c0')} \uc774\uc288\uac00 \uad00\ucc30\ub429\ub2c8\ub2e4. \ubd80\uc815 {negative}%, \uae0d\uc815 {positive}%\ub85c \ud45c\ubcf8\uc774 \uc801\uc744 \uacbd\uc6b0 \ub2e8\uc815\ud558\uc9c0 \uc54a\ub294 \uac83\uc774 \uc88b\uc2b5\ub2c8\ub2e4.")
 return {"key":key,"title":title,"category":CATEGORY_LABELS.get(category,"\uae30\ud0c0"),"mentions":len(target),"sentiment":{"positive":positive,"neutral":neutral,"negative":negative},"timeline":[{"date":k,"count":v} for k,v in sorted(buckets.items())],"interpretation":interpretation,"ai_rationales":rationales[:3],"comment_reaction":{"count":len(comments),"agree":stances["AGREE"],"disagree":stances["DISAGREE"],"neutral":stances["NEUTRAL"],"positive":comment_sentiments["POSITIVE"],"negative":comment_sentiments["NEGATIVE"]},"comments":[{"content":c.content,"created_at":c.created_at.isoformat() if c.created_at else None,"sentiment":c.sentiment,"stance":c.stance,"upvotes":c.upvotes} for c in comments[:30]],"references":related[:5],"posts":[{"title":p.title,"url":p.url,"source":SOURCE_LABELS.get(p.source,p.source),"created_at":p.created_at.isoformat() if p.created_at else None,"views":p.views,"comments":p.comments,"upvotes":p.upvotes,"sentiment":p.sentiment,"excerpt":(p.content or "")[:240]} for p in target[:20]]}
