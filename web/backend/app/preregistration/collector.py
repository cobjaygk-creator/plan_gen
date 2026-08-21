from __future__ import annotations

import html, json, os, re, sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from tools.ai_client import ClassificationError, classify
from .models import GamePreRegistration, PreRegistrationType

NAVER_WEBKR_URL = "https://naverapihub.apigw.ntruss.com/search/v1/webkr"
DISCOVERY_QUERIES = ("\uac8c\uc784 \uc0ac\uc804\uc608\uc57d", "\uac8c\uc784 \uc0ac\uc804\ub4f1\ub85d", "\uac8c\uc784 \uc5c5\ub370\uc774\ud2b8 \uc0ac\uc804\uc608\uc57d", "\uc2e0\uaddc \ud074\ub798\uc2a4 \uc0ac\uc804\uc608\uc57d", "\ub300\uaddc\ubaa8 \uc5c5\ub370\uc774\ud2b8 \uc0ac\uc804\uc608\uc57d", "\uc2dc\uc98c \uc5c5\ub370\uc774\ud2b8 \uc0ac\uc804\uc608\uc57d", "\uac8c\uc784 \uc8fc\ub144 \uc0ac\uc804\uc608\uc57d", "\uac8c\uc784 \ubcf5\uadc0 \uc0ac\uc804\uc608\uc57d")
MAX_CANDIDATES_PER_RUN = 60
OFFICIAL_SEED_URLS = (
    ("https://zeus.com2us.com/", "\uc81c\uc6b0\uc2a4: \uc624\ub9cc\uc758 \uc2e0 \uc0ac\uc804\uc608\uc57d", "\ucef4\ud22c\uc2a4 \uacf5\uc2dd \uc2e0\uaddc MMORPG \uc0ac\uc804\uc608\uc57d"),
    ("https://mlb9innings26.com2us.com/ko?r=p1", "MLB 9\uc774\ub2dd\uc2a4 26 \uc2dc\uc98c \uc5c5\ub370\uc774\ud2b8 \uc0ac\uc804\uc608\uc57d", "\ucef4\ud22c\uc2a4 \uacf5\uc2dd \uc2dc\uc98c \uc5c5\ub370\uc774\ud2b8 \uc0ac\uc804\uc608\uc57d"),
)
RECENT_DAYS = 62
_TAGS = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_IMAGE = re.compile(r"<meta[^>]+(?:property|name)=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)", re.I)
_PREREG_WORDS = ("\uc0ac\uc804\uc608\uc57d", "\uc0ac\uc804 \ub4f1\ub85d", "\uc0ac\uc804\ub4f1\ub85d", "pre-register", "pre registration", "preregistration")
_REJECTED_HOSTS = ("naver.com", "daum.net", "tistory.com", "brunch.co.kr", "youtube.com", "instagram.com", "facebook.com", "x.com", "twitter.com", "inven.co.kr", "ruliweb.com", "gamemeca.com", "thisisgame.com", "game.donga.com", "newsis.com", "yna.co.kr", "zdnet.co.kr", "sedaily.com", "gamechosun.co.kr", "onestore.co.kr", "support.google.com", "vgamelifev.com")
_TRUSTED_OFFICIAL_HOSTS = (
    "nexon.com", "plaync.com", "com2us.com", "netmarble.com", "netmarble.net", "onstove.com",
    "kakaogames.com", "webzen.co.kr", "wemade.com", "gravity.co.kr", "neowiz.com", "hanbiton.com",
    "playwith.co.kr", "pearabyss.com", "xlgames.com", "valofe.com", "bandainamcoent.co.kr",
)
_EXCLUDED_URL_PARTS = ("g123.jp/games/pre-registration",)
_LEGACY_EXCLUDED_GAMES = ("veiled experts",)
_GENERIC_GAME_NAMES = ("\uc6d0\uc2a4\ud1a0\uc5b4", "\ubaa8\ube44", "\uc2e0\uc791 \ubaa8\ubc14\uc77c", "unknown", "\ubcf4\ub4dc\uac8c\uc784\ucf58")
_GENERIC_CAMPAIGN_TERMS = ("\ubaa9\ub85d", "\ubaa8\uc74c", "\ubc29\ubc95", "\uc778\uc9c0\ub3c4", "\ucfe0\ud3f0")
_REJECTED_TERMS = ("\uad7f\uc988", "\ud53c\uaddc\uc5b4", "\ucf58\uc11c\ud2b8", "\ud31d\uc5c5\uc2a4\ud1a0\uc5b4", "\uc88c\uc11d \uc608\uc57d", "\uc608\uc57d\uad6c\ub9e4", "\uc608\uc57d \ud310\ub9e4", "\uc0c1\ud488 \uc608\uc57d")

@dataclass(frozen=True)
class DiscoveryCandidate:
    url: str
    title: str
    description: str

class CampaignAnalysis(BaseModel):
    is_game_preregistration: bool
    is_official_landing: bool
    preregistration_type: PreRegistrationType = PreRegistrationType.OTHER
    game_name: str | None = None
    normalized_game_name: str | None = None
    campaign_name: str | None = None
    developer: str | None = None
    publisher: str | None = None
    genre: str | None = None
    platform: list[str] = Field(default_factory=list)
    preregistration_start_date: date | None = None
    preregistration_end_date: date | None = None
    release_date: date | None = None
    update_date: date | None = None
    status: str = "unknown"
    confidence_score: float = 0

SYSTEM_PROMPT = """?? ?? ??? ?? ???? ?????? ???? ??? ??????. URL, ?? ??, ??? ??? ??? ????. is_game_preregistration? ???? ?? ??? ? ?? ?? ????/???? ???? ?? true?. is_official_landing? ??? ?? ????? ?? ???? ?? true?. ????????????????? ??????? ?? ??? ? ? false?. ?? ??? ??? ?? ?? ????, ?? ???/???/??, ???/?? ????, ??, ??, ?? ???? ????. ? ? ?? ?? null? ?? ???? ??. ?? ??? ???? status? ended? ??."""

def _clean(value: str) -> str:
    return html.unescape(_TAGS.sub("", value or "")).strip()

def _fetch_webkr(query: str, client_id: str, client_secret: str) -> list[dict]:
    url=f"{NAVER_WEBKR_URL}?{urlencode({'query': query, 'display': 20, 'start': 1, 'format': 'json'})}"
    request=Request(url, headers={"X-NCP-APIGW-API-KEY-ID":client_id,"X-NCP-APIGW-API-KEY":client_secret})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8")).get("items", [])

def _looks_like_candidate(url: str, title: str, description: str) -> bool:
    host=urlparse(url).netloc.casefold().removeprefix("www.")
    content=f"{title} {description}".casefold()
    return bool(host) and not any(host.endswith(x) for x in _REJECTED_HOSTS) and not any(part in url.casefold() for part in _EXCLUDED_URL_PARTS) and any(x in content for x in _PREREG_WORDS) and not any(x in content for x in _REJECTED_TERMS)

def discover_candidates(queries: Iterable[str]=DISCOVERY_QUERIES) -> list[DiscoveryCandidate]:
    client_id=os.environ.get("NAVER_CLIENT_ID", "").strip(); client_secret=os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret: raise RuntimeError("NAVER_CLIENT_ID/SECRET not configured")
    seen:set[str]=set(); candidates:list[DiscoveryCandidate]=[]
    for query in queries:
        for item in _fetch_webkr(query,client_id,client_secret):
            url=(item.get("link") or "").strip(); title=_clean(item.get("title", "")); description=_clean(item.get("description", ""))
            if not url or not title or url in seen or not _looks_like_candidate(url,title,description): continue
            seen.add(url); candidates.append(DiscoveryCandidate(url,title,description))
            if len(candidates)>=MAX_CANDIDATES_PER_RUN: return candidates
    return candidates

def _official_seed_candidates() -> list[DiscoveryCandidate]:
    return [DiscoveryCandidate(url, title, description) for url, title, description in OFFICIAL_SEED_URLS]

def _fetch_page(url: str) -> tuple[str, str | None]:
    request=Request(url, headers={"User-Agent":"Mozilla/5.0 (compatible; PlanGenPrereRegistrationCollector/1.0)"})
    with urlopen(request,timeout=20) as response:
        raw=response.read(600_000).decode(response.headers.get_content_charset() or "utf-8",errors="replace")
    image=_IMAGE.search(raw)
    return _clean(raw)[:12000], html.unescape(image.group(1)) if image else None

def _analyze(candidate: DiscoveryCandidate, body: str) -> CampaignAnalysis | None:
    prompt=f"URL: {candidate.url}\n?? ??: {candidate.title}\n?? ??: {candidate.description}\n\n??? ??:\n{body[:9000]}"
    try:
        analysis = classify(SYSTEM_PROMPT,prompt,CampaignAnalysis,os.environ.get("PREREGISTRATION_CLASSIFIER_MODEL","gpt-4o-mini"),provider="openai")
    except ClassificationError:
        return None
    # Dates are compliance-sensitive: do not retain an AI-inferred date unless
    # the exact ISO date appears in the fetched page text.
    for field in ("preregistration_start_date", "preregistration_end_date", "release_date", "update_date"):
        value = getattr(analysis, field)
        if value and value.isoformat() not in body:
            setattr(analysis, field, None)
    return analysis

def _title_type_hint(candidate: DiscoveryCandidate, analysis: CampaignAnalysis) -> PreRegistrationType:
    title = f"{candidate.title} {analysis.campaign_name or ''}".casefold()
    if "\uc2dc\uc98c" in title:
        return PreRegistrationType.SEASON_UPDATE
    if "\uc5c5\ub370\uc774\ud2b8" in title or "reboot" in title or "re:update" in title:
        return PreRegistrationType.MAJOR_UPDATE
    if "\ud074\ub798\uc2a4" in title or "\uc804\uc9c1" in title:
        return PreRegistrationType.NEW_CLASS
    if "\uce90\ub9ad\ud130" in title:
        return PreRegistrationType.NEW_CHARACTER
    if "\uc11c\ubc84" in title:
        return PreRegistrationType.NEW_SERVER
    if "\uc8fc\ub144" in title:
        return PreRegistrationType.ANNIVERSARY
    if "\ubcf5\uadc0" in title:
        return PreRegistrationType.RETURN_CAMPAIGN
    return analysis.preregistration_type

def _has_historical_year(candidate: DiscoveryCandidate, analysis: CampaignAnalysis) -> bool:
    """Reject pages whose URL/title explicitly identifies a completed old campaign."""
    values = f"{candidate.url} {candidate.title} {analysis.campaign_name or ''}"
    years = [int(value) for value in re.findall(r"(?<!\d)(20\d{2})(?!\d)", values)]
    return any(year < date.today().year for year in years)

def _is_recent(analysis: CampaignAnalysis) -> bool:
    boundary=date.today()-timedelta(days=RECENT_DAYS)
    values=(analysis.preregistration_start_date,analysis.preregistration_end_date,analysis.release_date,analysis.update_date)
    return not any(values) or any(x is not None and x>=boundary for x in values)

def collect_and_store(db: Session, queries: Iterable[str]=DISCOVERY_QUERIES) -> dict[str,int]:
    stats={"discovered":0,"verified":0,"added":0,"updated":0,"failed":0}
    try:
        candidates = discover_candidates(queries)
    except Exception:
        candidates = _official_seed_candidates()
    stats["discovered"]=len(candidates); now=datetime.now(timezone.utc)
    for candidate in candidates:
        try:
            body,image_url=_fetch_page(candidate.url)
            if not any(x in body.casefold() for x in _PREREG_WORDS): continue
            analysis=_analyze(candidate,body)
            if not analysis or not analysis.is_game_preregistration or not analysis.is_official_landing or not analysis.game_name or not analysis.campaign_name or not _is_recent(analysis) or _has_historical_year(candidate, analysis): continue
            if any(term in analysis.game_name.casefold() for term in (*_GENERIC_GAME_NAMES, *_LEGACY_EXCLUDED_GAMES)) or any(term in analysis.campaign_name.casefold() for term in _GENERIC_CAMPAIGN_TERMS): continue
            analysis.preregistration_type = _title_type_hint(candidate, analysis)
            stats["verified"]+=1
            existing=db.scalar(select(GamePreRegistration).where(GamePreRegistration.preregistration_url==candidate.url))
            values={"game_name":analysis.game_name,"normalized_game_name":analysis.normalized_game_name or analysis.game_name,"campaign_name":analysis.campaign_name,"preregistration_type":analysis.preregistration_type.value,"developer":analysis.developer,"publisher":analysis.publisher,"genre":analysis.genre,"platform":",".join(analysis.platform),"preregistration_start_date":analysis.preregistration_start_date,"preregistration_end_date":analysis.preregistration_end_date,"release_date":analysis.release_date,"update_date":analysis.update_date,"official_url":candidate.url,"preregistration_url":candidate.url,"thumbnail_url":image_url,"main_visual_url":image_url,"status":analysis.status if analysis.status in {"ongoing","upcoming","ended"} else "ongoing","is_game_preregistration":True,"confidence_score":analysis.confidence_score,"verified_at":now}
            if existing:
                for field,value in values.items(): setattr(existing,field,value)
                stats["updated"]+=1
            else:
                db.add(GamePreRegistration(discovered_at=now,**values)); stats["added"]+=1
            db.commit()
        except Exception:
            db.rollback(); stats["failed"]+=1
    return stats
