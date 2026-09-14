from __future__ import annotations
import hashlib,http.cookiejar,json,re,time
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPCookieProcessor,urlopen
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

# DCInside 댓글: 라테일 갤러리(DCINSIDE)/프리링(DCINSIDE_PRIRING)에는 공식
# 커뮤니티용 collect_comments()가 전혀 닿지 않아서, "댓글 반응" 지표가
# 실제로는 공식 공지 댓글만 보고 있었다 — 정작 민심이 제일 많이 드러나는
# 곳은 DCInside인데 거기 댓글은 전혀 안 봤다는 뜻. DCInside 댓글은 게시글
# 페이지에 박힌 hidden input #e_s_n_o 토큰과 /board/comment/ POST
# 엔드포인트로 가져온다(직접 확인 — 쿠키 없이도, 이 토큰과 Referer만
# 맞으면 동작한다).
_DC_GALL_ID={"DCINSIDE":"latale","DCINSIDE_PRIRING":"laf"}
_DC_COMMENT_URL="https://gall.dcinside.com/board/comment/"

def _dc_comment_date(value):
 value=(value or "").strip();kst=timezone(timedelta(hours=9));now=datetime.now(kst)
 for fmt in ("%Y-%m-%d %H:%M:%S","%m.%d %H:%M:%S"):
  try:
   d=datetime.strptime(value,fmt)
   if fmt=="%m.%d %H:%M:%S":d=d.replace(year=now.year)
   return d.replace(tzinfo=kst).astimezone(timezone.utc)
  except ValueError:pass
 return None

def _fetch_dc_comments(post):
 gall_id=_DC_GALL_ID.get(post.source)
 if not gall_id:return []
 req=Request(post.url,headers={"User-Agent":UA,"Accept-Language":"ko-KR"})
 with urlopen(req,timeout=20) as res:raw=res.read()
 soup=BeautifulSoup(raw,"html.parser",from_encoding="utf-8")
 token_node=soup.select_one("#e_s_n_o")
 token=token_node.get("value","") if token_node else ""
 if not token:return []
 headers={"User-Agent":UA,"Accept-Language":"ko-KR","Referer":post.url,"X-Requested-With":"XMLHttpRequest","Content-Type":"application/x-www-form-urlencoded; charset=UTF-8"}
 collected=[];page=1
 while page<=10:
  data=urlencode({"id":gall_id,"no":post.post_id,"cmt_id":gall_id,"cmt_no":post.post_id,"e_s_n_o":token,"comment_page":str(page),"sort":"","prevCnt":"","board_type":"","_GALLTYPE_":"","clean":"","nptest":""}).encode()
  req=Request(_DC_COMMENT_URL,data=data,headers=headers)
  with urlopen(req,timeout=20) as res:payload=json.loads(res.read().decode("utf-8"))
  items=payload.get("comments") or [];collected.extend(items)
  if len(collected)>=payload.get("total_cnt",len(collected)) or not items:break
  page+=1;time.sleep(.15)
 return collected

def collect_dc_comments(db:Session,post_limit:int=40)->dict:
 posts=db.execute(select(SentimentPost).where(SentimentPost.source.in_(("DCINSIDE","DCINSIDE_PRIRING"))).order_by(SentimentPost.created_at.desc()).limit(post_limit)).scalars().all()
 found=new=updated=0;errors=[]
 for post in posts:
  try:items=_fetch_dc_comments(post)
  except Exception as exc:errors.append(f"{post.post_id}:{type(exc).__name__}");continue
  count=0
  for item in items:
   if item.get("is_delete")=="1" or item.get("del_yn")=="Y":continue
   content=BeautifulSoup(item.get("memo") or "","html.parser").get_text(" ",strip=True)
   if not content:continue
   author=item.get("user_id") or item.get("name") or "";created=_dc_comment_date(item.get("reg_date"))
   cid=hashlib.sha256(f"{post.id}|{item.get('no')}".encode()).hexdigest();sentiment,value,stance=_analyze(content)
   row=db.execute(select(SentimentComment).where(SentimentComment.post_db_id==post.id,SentimentComment.comment_id==cid)).scalar_one_or_none()
   if row is None:
    db.add(SentimentComment(post_db_id=post.id,comment_id=cid,source=post.source,content=content[:5000],author_hash=hashlib.sha256(f"{post.source}:{author}".encode()).hexdigest() if author else None,created_at=created,upvotes=0,sentiment=sentiment,sentiment_value=value,stance=stance));new+=1
   else:row.sentiment=sentiment;row.sentiment_value=value;row.stance=stance;updated+=1
   found+=1;count+=1
  post.comments=max(post.comments,count)
  db.commit();time.sleep(.2)
 return {"posts_checked":len(posts),"found":found,"new":new,"updated":updated,"errors":errors}
