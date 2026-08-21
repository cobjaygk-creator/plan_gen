from __future__ import annotations
import hashlib, re, time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import SentimentPost, SentimentReference

DC_LIST = "https://gall.dcinside.com/board/lists/?id=latale&page={page}&list_num=100"
PRIRING_LIST = "https://gall.dcinside.com/mgallery/board/lists/?id=laf&page={page}&list_num=100"
LAT_LIST = "https://www.latale.com/community/forum?page={page}"
UA = "Mozilla/5.0 (compatible; UXTLER-Internal-Research/1.0)"

@dataclass
class Candidate:
    source:str; post_id:str; title:str; url:str; created_at:datetime|None
    author:str|None=None; views:int=0; comments:int=0; upvotes:int=0; content:str|None=None

def _get(url:str)->BeautifulSoup:
    req=Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urlopen(req,timeout=20) as res: raw=res.read(2_000_000)
    if len(raw)<1000: raise RuntimeError("EMPTY_OR_BLOCKED_RESPONSE")
    return BeautifulSoup(raw,"html.parser",from_encoding="utf-8")

def _num(value:str)->int:
    m=re.search(r"[\d,]+",value or "")
    return int(m.group().replace(",", "")) if m else 0

def _date(value:str)->datetime|None:
    value=(value or "").strip(); kst=timezone(timedelta(hours=9)); now=datetime.now(kst)
    for fmt in ("%Y-%m-%d %H:%M:%S","%Y.%m.%d %H:%M","%Y.%m.%d","%Y-%m-%d","%y/%m/%d","%H:%M"):
        try:
            d=datetime.strptime(value,fmt)
            if fmt=="%H:%M": d=d.replace(year=now.year,month=now.month,day=now.day)
            elif fmt in ("%Y.%m.%d","%Y-%m-%d","%y/%m/%d"): d=d.replace(hour=12)
            return d.replace(tzinfo=kst).astimezone(timezone.utc)
        except ValueError: pass
    return None

def _dc_board_candidates(url_template:str,source:str,pages:int=3)->list[Candidate]:
    out=[]
    for page in range(1,pages+1):
        soup=_get(url_template.format(page=page))
        for row in soup.select("tr.ub-content[data-no]"):
            if row.get("data-type") != "icon_txt": continue
            a=row.select_one("td.gall_tit a:not(.reply_numbox)")
            if not a: continue
            no=row.get("data-no") or parse_qs(urlparse(a.get("href","")).query).get("no",[""])[0]
            if not no: continue
            title=a.get_text(" ",strip=True)
            reply=row.select_one(".reply_num, .reply_numbox")
            author_node=row.select_one("td.gall_writer")
            author=(author_node.get("data-nick") if author_node else None) or (author_node.get_text(" ",strip=True) if author_node else None)
            out.append(Candidate(source,no,title,urljoin("https://gall.dcinside.com",a.get("href")),_date(row.select_one("td.gall_date").get("title","") if row.select_one("td.gall_date") and row.select_one("td.gall_date").get("title") else row.select_one("td.gall_date").get_text(strip=True)),author,_num(row.select_one("td.gall_count").get_text() if row.select_one("td.gall_count") else ""),_num(reply.get_text() if reply else ""),_num(row.select_one("td.gall_recommend").get_text() if row.select_one("td.gall_recommend") else "")))
        time.sleep(.5)
    if not out: raise RuntimeError("DC_LIST_EMPTY")
    unique={item.post_id:item for item in out}
    return list(unique.values())

def dc_candidates(pages:int=3)->list[Candidate]:
    return _dc_board_candidates(DC_LIST,"DCINSIDE",pages)

def priring_candidates(pages:int=3)->list[Candidate]:
    return _dc_board_candidates(PRIRING_LIST,"DCINSIDE_PRIRING",pages)

def latale_candidates(pages:int=2)->list[Candidate]:
    out=[]
    for page in range(1,pages+1):
        soup=_get(LAT_LIST.format(page=page))
        for row in soup.select("table tr"):
            a=row.select_one("td.subject a")
            if not a or "/notice/" in (a.get("href") or ""): continue
            href=a.get("href",""); m=re.search(r"/view/(\d+)",href)
            if not m: continue
            author=row.select_one("td.writer")
            out.append(Candidate("LATALE_OFFICIAL",m.group(1),a.get_text(" ",strip=True),urljoin("https://www.latale.com",href),_date(row.select_one("td.write-date").get_text(strip=True) if row.select_one("td.write-date") else ""),author.get_text(" ",strip=True) if author else None,_num(row.select_one("td.read-count").get_text() if row.select_one("td.read-count") else ""),0,_num(row.select_one("td.like-count").get_text() if row.select_one("td.like-count") else "")))
        time.sleep(.25)
    return out

def _content(item:Candidate)->str:
    try:
        soup=_get(item.url)
        node=soup.select_one(".writing_view_box" if item.source=="DCINSIDE" else ".board-content")
        return node.get_text(" ",strip=True)[:10000] if node else ""
    except Exception: return ""

NOTICE_LIST = "https://www.latale.com/news/notice?page={page}"
def collect_references(db:Session,pages:int=2)->dict:
    found=[]; errors=[]
    try:
        for page in range(1,pages+1):
            soup=_get(NOTICE_LIST.format(page=page))
            for row in soup.select("table tr"):
                a=row.select_one("td.subject a")
                if not a: continue
                href=a.get("href",""); m=re.search(r"/view/(\d+)",href)
                if not m: continue
                date_node=row.select_one("td.write-date")
                found.append((m.group(1),a.get_text(" ",strip=True),urljoin("https://www.latale.com",href),_date(date_node.get_text(strip=True) if date_node else "")))
            time.sleep(.2)
    except Exception as exc: errors.append(type(exc).__name__)
    new=0
    for rid,title,url,published in found:
        row=db.execute(select(SentimentReference).where(SentimentReference.reference_id==rid)).scalar_one_or_none()
        if row is None: db.add(SentimentReference(reference_id=rid,title=title,url=url,published_at=published)); new+=1
        else: row.title=title; row.url=url; row.published_at=published
    db.commit(); return {"found":len(found),"new":new,"errors":errors}

def collect(db:Session,pages:int=3,detail_limit:int=30)->dict:
    candidates=[]; errors=[]
    for fn in (dc_candidates,priring_candidates,latale_candidates):
        try: candidates.extend(fn(pages if fn in (dc_candidates,priring_candidates) else min(2,pages)))
        except Exception as exc: errors.append(f"{fn.__name__}: {type(exc).__name__}")
    new=0; updated=0; details=0
    for item in candidates:
        post=db.execute(select(SentimentPost).where(SentimentPost.source==item.source,SentimentPost.post_id==item.post_id)).scalar_one_or_none()
        if post is None:
            if item.source=="LATALE_OFFICIAL" and details<detail_limit: item.content=_content(item); details+=1; time.sleep(.18)
            post=SentimentPost(source=item.source,post_id=item.post_id,title=item.title,content=item.content,author_hash=hashlib.sha256(f"{item.source}:{item.author or ''}".encode()).hexdigest() if item.author else None,url=item.url,created_at=item.created_at,views=item.views,comments=item.comments,upvotes=item.upvotes)
            db.add(post); new+=1
        else:
            post.views=item.views; post.comments=item.comments; post.upvotes=item.upvotes; post.title=item.title
            if item.created_at is not None: post.created_at=item.created_at
            updated+=1
    db.commit()
    references=collect_references(db,pages=2)
    return {"found":len(candidates),"new":new,"updated":updated,"details":details,"errors":errors,"references":references}
