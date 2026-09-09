"""Verified sample collectors for official NEXON event lists.

Each source is explicitly registered only after its official list URL and
markup have been checked.  The collectors discover candidates; they do not
make a subjective design-quality judgment.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


FC_ONLINE_EVENTS_URL = "https://fconline.nexon.com/news/events"
MAPLESTORY_EVENTS_URL = "https://maplestory.nexon.com/news/event"
MABINOGI_EVENTS_URL = "https://mabinogi.nexon.com/page/news/event_list.asp"
TALESWEAVER_EVENTS_URL = "https://tales.nexon.com/News/Event"
ELSWORD_EVENTS_URL = "https://elsword.nexon.com/News/Events/List"
BARAM_EVENTS_URL = "https://baram.nexon.com/Event/List"
BARAM_CASHSHOP_URL = "https://baram.nexon.com/CashshopUpdate/List/1"
# 명시적 요청: 2026-08-27("풍요의보물함 판매")보다 오래된 캐시샵 업데이트
# 게시물은 소급 수집하지 않는다 — 그 날짜 이후(포함) 올라온 것만.
_BARAM_CASHSHOP_CUTOFF = date(2026, 8, 27)
LOSTARK_EVENTS_URL = "https://lostark.game.onstove.com/News/Event/Now"
NC_EVENTON_API_URL = "https://promotion.plaync.com/eventon/item"
BLACK_DESERT_EVENTS_URL = "https://www.kr.playblackdesert.com/ko-KR/News/Notice?boardType=3&progressType=1"
GERSANG_EVENTS_URL = "https://www.gersang.co.kr/news/event.gs"
DNF_EVENTS_URL = "https://df.nexon.com/community/news/event/list"
TALESRUNNER_EVENT_API_URL = "https://tr.rhaon.co.kr/eventb/event/SNB"
CSO_EVENTS_URL = "https://csonline.nexon.com/News/Event/List"
HEROES_EVENTS_URL = "https://heroes.nexon.com/news/event/ing"
RAGNAROK_EVENTS_URL = "https://ro.gnjoy.com/news/event/list.asp"
AUDITION_EVENTS_URL = "https://audition.hangame.com/Desk/EventList"
CYPHERS_EVENTS_URL = "https://cyphers.nexon.com/article/event/running"
THEFINALS_EVENTS_URL = "https://thefinals.nexon.com/news?headlineId=3069"
# 요약(summary)에 실질적인 설명 텍스트가 있으면 "텍스트 많이 포함된"
# 공지성 게시물로 보고 제외한다 — 배너 이미지 한 장(+있어도 캡션 수준의
# 짧은 문구)뿐인 "통이미지" 게시물만 수집해달라는 명시적 요청. 실측: 통
# 이미지형은 요약이 0~15자, 텍스트가 많은 공지는 490~500자(서버가 500자
# 에서 자름)로 뚜렷이 갈린다.
_THEFINALS_SUMMARY_MAX_LEN = 30
LOD_EVENTS_URL = "https://lod.nexon.com/news/event"
# ?hl=ko-KR 없이 요청하면 서버가 영문판을 내려준다(직접 확인).
ETERNALRETURN_EVENTS_URL = "https://event.playeternalreturn.com/S12_Sailing?hl=ko-KR"
_DATE_RANGE = re.compile(r"(20\d{2}\s*[.-]\s*\d{2}\s*[.-]\s*\d{2})\s*[^~]{0,20}~\s*(20\d{2}\s*[.-]\s*\d{2}\s*[.-]\s*\d{2})")
# Cyphers prints dates without a year ("9/3 점검 후 ~ 9/22 점검 전") — _DATE_RANGE
# expects a 4-digit year and never matches this format.
_MD_RANGE = re.compile(r"(\d{1,2})/(\d{1,2}).*?~.*?(\d{1,2})/(\d{1,2})")


@dataclass(frozen=True)
class EventCandidate:
    publisher: str
    game: str
    title: str
    event_url: str
    hero_image_url: str | None
    starts_on: str | None
    ends_on: str | None
    published_on: str | None
    status: str | None
    event_format: str
    collected_at: str


def _headers_for(url: str) -> dict[str, str]:
    """대부분의 공식 목록은 이 범용 UA로 충분하지만, mabinogi.nexon.com과
    tr.rhaon.co.kr은 운영 서버(오라클 클라우드 IP)에서만 계속 봇 취급으로
    막혀서(mabinogi: GitHub Actions 러너에서 2026-08-25 01:47부터 전량
    403 확인; tr.rhaon.co.kr: 오라클 서버에서 2026-08-24 이후 계속 수집
    실패, 집·사무실 IP에서는 그대로 성공하는 것 직접 확인) 실브라우저
    UA+헤더로 우회한다 — 삼성전자 뉴스룸(collector.py)에 쓴 것과 같은
    처방."""
    if "mabinogi.nexon.com" in url or "tr.rhaon.co.kr" in url:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://mabinogi.nexon.com/" if "mabinogi.nexon.com" in url else "https://tr.rhaon.co.kr/",
        }
    return {"User-Agent": "Mozilla/5.0 (compatible; EventBenchSample/0.1)"}


def _fetch_html(url: str) -> str:
    request = Request(url, headers=_headers_for(url))
    with urlopen(request, timeout=20) as response:  # noqa: S310 - explicit verified official URLs
        # Mabinogi is EUC-KR; the other verified official lists deliver UTF-8
        # despite inconsistent legacy headers.
        charset = "euc-kr" if "mabinogi.nexon.com" in url else "utf-8"
        return response.read().decode(charset, errors="replace")


def _published_date_from_page(event_url: str) -> str | None:
    """Extract an explicitly displayed board-post date; never infer one."""
    try:
        page = _fetch_html(event_url)
    except Exception:
        return None
    soup = BeautifulSoup(page, "html.parser")
    for selector in (".title_area .date", ".th.date", ".board_view .date", "time[datetime]"):
        node = soup.select_one(selector)
        value = (node.get("datetime") or node.get_text(" ", strip=True)) if node else ""
        match = re.search(r"(20\d{2})[.-](\d{1,2})[.-](\d{1,2})", value)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    meta = soup.select_one('meta[property="article:published_time"]')
    if meta and meta.get("content"):
        match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", meta["content"])
        if match:
            return match.group(0)
    return None


def _event_format(event_url: str) -> str:
    """Distinguish a dedicated event landing page from a site board post."""
    host = urlparse(event_url).netloc.lower()
    path = urlparse(event_url).path.lower()
    if host == "elsword.nexon.com":
        # Board posts use /News/Events/View; campaign landing pages use /EventsYYYY/.
        return "full_page" if path.startswith("/events20") else "board"
    if host == "heroes.nexon.com" and path.startswith("/promotion/"):
        return "full_page"
    if host == "df.nexon.com" and path.startswith("/pg/"):
        return "full_page"
    if host == "baram.essential.nexon.com":
        return "full_page"
    if host == "baram.nexon.com" and path == "/pccafebenefit":
        return "full_page"
    if "/eventfull/" in path or "/page/event/" in path or host.startswith("events.") or host.startswith("shop.") or host == "lostark.game.onstove.com" and path.startswith("/event/"):
        return "full_page"
    if host == "tales.nexon.com" and re.match(r"/\d{6}/", path):
        return "full_page"
    if host == "cyphers.nexon.com" and path.startswith("/pages/events/"):
        return "full_page"
    if host == "lod.nexon.com" and path.startswith("/event/"):
        return "full_page"
    return "board"


def _fetch_talesweaver_html(url: str = TALESWEAVER_EVENTS_URL) -> str:
    """Fetch the verified official TalesWeaver list via curl.

    The site blocks urllib with HTTP 403 while accepting its public browser
    response path. This is used only for the explicitly verified list URL.
    The binary is named "curl.exe" on Windows and "curl" on Linux (e.g. the
    GitHub Actions runner); resolve whichever is actually on PATH.
    """
    curl_bin = shutil.which("curl.exe") or shutil.which("curl") or "curl"
    result = subprocess.run(
        [
            curl_bin, "-L", "--fail", "--silent", "--show-error", "--max-time", "20",
            "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/139 Safari/537.36",
            "-H", "Accept-Language: ko-KR,ko;q=0.9",
            "-H", "Referer: https://tales.nexon.com/",
            url,
        ],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def _date_parts(value: str) -> tuple[str | None, str | None]:
    match = _DATE_RANGE.search(value)
    if not match:
        return None, None
    normalize = lambda value: re.sub(r"\s*[.-]\s*", "-", value)
    return normalize(match.group(1)), normalize(match.group(2))


def _date_parts_md(value: str, reference: date | None = None) -> tuple[str | None, str | None]:
    """Cyphers' event list only ever shows month/day ("9/3 점검 후 ~ 9/22
    점검 전"), never a year. The list is always ongoing/upcoming campaigns
    only, so if a parsed date lands more than ~2 months in the past relative
    to today it must actually be next year's (the range wrapped past
    new year's)."""
    match = _MD_RANGE.search(value)
    if not match:
        return None, None
    reference = reference or date.today()

    def to_iso(month: str, day: str) -> str | None:
        try:
            candidate = date(reference.year, int(month), int(day))
        except ValueError:
            return None
        if (reference - candidate).days > 60:
            candidate = candidate.replace(year=candidate.year + 1)
        return candidate.isoformat()

    return to_iso(match.group(1), match.group(2)), to_iso(match.group(3), match.group(4))


_LOD_DATE_RANGE = re.compile(
    r"(\d{4})\.(\d{2})\.(\d{2})\.\s*\d{2}:\d{2}\s*~\s*(?:(\d{4})\.(\d{2})\.(\d{2})\.\s*\d{2}:\d{2}|상시)"
)


def _parse_lod_date_range(text: str) -> tuple[str | None, str | None]:
    """어둠의전설: "2026.08.20. 08:00 ~ 2026.09.17. 08:00" 또는 종료일 없이
    "2024.05.30. 12:30 ~ 상시"."""
    match = _LOD_DATE_RANGE.search(text)
    if not match:
        return None, None
    start = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    end = f"{match.group(4)}-{match.group(5)}-{match.group(6)}" if match.group(4) else None
    return start, end


_ER_KOREAN_DATE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
_ER_DOT_DATE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")


def _parse_eternalreturn_dates(text: str) -> tuple[str | None, str | None]:
    """이터널 리턴 좌측 메뉴의 설명 문구는 형식이 제각각이다 — "2026년 9월
    3일(목) 점검 종료 후 ~ 2026년 9월 17일(목) 점검 전까지"처럼 날짜가
    있을 수도, "나만의 캐릭터를 만들어보세요!"처럼 아예 없을 수도 있다.
    날짜가 하나뿐이면(예: "2026.08.06 OPEN") 시작일로만 쓴다."""
    korean_dates = _ER_KOREAN_DATE.findall(text)
    if korean_dates:
        def fmt(parts: tuple[str, str, str]) -> str:
            return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        start = fmt(korean_dates[0])
        end = fmt(korean_dates[1]) if len(korean_dates) > 1 else None
        return start, end
    dot_match = _ER_DOT_DATE.search(text)
    if dot_match:
        return f"{dot_match.group(1)}-{dot_match.group(2)}-{dot_match.group(3)}", None
    return None, None


def _is_current_or_scheduled(starts_on: str | None, ends_on: str | None, status_text: str = "") -> bool:
    """Keep only official entries that are ongoing or announced for the future."""
    normalized = status_text.replace(" ", "")
    if "??" in normalized:
        return False
    today = date.today()
    try:
        if starts_on and date.fromisoformat(starts_on) > today:
            return True
        if ends_on and date.fromisoformat(ends_on) >= today:
            return True
    except ValueError:
        pass
    return any(token in normalized for token in ("??", "??", "??"))


def _last_page_number(soup: BeautifulSoup, pattern: str, default: int = 1) -> int:
    numbers = [int(value) for value in re.findall(pattern, str(soup))]
    return max(numbers, default=default)


def collect_fc_online_events() -> list[EventCandidate]:
    """Collect every official FC ONLINE event marked ongoing or upcoming."""
    first_soup = BeautifulSoup(_fetch_html(FC_ONLINE_EVENTS_URL), "html.parser")
    last_page = _last_page_number(first_soup, r"ArticleList\(this,(\d+),")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for page in range(1, last_page + 1):
        list_url = f"{FC_ONLINE_EVENTS_URL}/ListPart?n4PageNo={page}&strSearch=&emSearchType=&n4ArticleCategorySN=0&n4ArticleCategory2SN=1"
        soup = first_soup if page == 1 else BeautifulSoup(_fetch_html(list_url), "html.parser")
        for anchor in soup.select("div.content.event a[href]"):
            event_url = anchor.get("href", "").strip()
            item_text = " ".join(anchor.stripped_strings)
            status_node = anchor.select_one(".state")
            status_text = status_node.get_text(" ", strip=True) if status_node else item_text
            if not event_url or not item_text or event_url in seen:
                continue
            starts_on, ends_on = _date_parts(item_text)
            if not _is_current_or_scheduled(starts_on, ends_on, status_text):
                continue
            seen.add(event_url)
            title = _DATE_RANGE.sub("", item_text).replace("??", "").replace("?? ?", "").strip()
            image = anchor.find("img")
            candidates.append(EventCandidate(
                publisher="NEXON Korea", game="FC ONLINE", title=title, event_url=event_url,
                hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
                published_on=_published_date_from_page(event_url), status=status_text or None,
                event_format=_event_format(event_url), collected_at=collected_at,
            ))
    return candidates
def collect_maplestory_events() -> list[EventCandidate]:
    """Collect candidates from the verified MapleStory official event list."""
    soup = BeautifulSoup(_fetch_html(MAPLESTORY_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()

    for card in soup.select("li"):
        title_link = card.select_one("dt a[href]")
        period_link = card.select_one("dd a[href]")
        if title_link is None or period_link is None:
            continue
        event_url = urljoin(MAPLESTORY_EVENTS_URL, title_link.get("href", "").strip())
        title = " ".join(title_link.stripped_strings)
        period = " ".join(period_link.stripped_strings)
        if not title or event_url in seen:
            continue
        seen.add(event_url)
        starts_on, ends_on = _date_parts(period)
        image = card.find("img")
        candidates.append(EventCandidate(
            publisher="NEXON Korea", game="\uba54\uc774\ud50c\uc2a4\ud1a0\ub9ac", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=None, status="진행", event_format=_event_format(event_url), collected_at=collected_at,
        ))
    return candidates


def collect_mabinogi_events() -> list[EventCandidate]:
    """Collect every official Mabinogi event that is ongoing or upcoming."""
    first_soup = BeautifulSoup(_fetch_html(MABINOGI_EVENTS_URL), "html.parser")
    last_page = _last_page_number(first_soup, r"page_max\s*=\s*(\d+)")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for page in range(1, last_page + 1):
        list_url = MABINOGI_EVENTS_URL if page == 1 else f"{MABINOGI_EVENTS_URL}?page={page}"
        soup = first_soup if page == 1 else BeautifulSoup(_fetch_html(list_url), "html.parser")
        for card in soup.select("li"):
            title_link = card.select_one("dt a[href]")
            if title_link is None:
                continue
            event_url = urljoin(MABINOGI_EVENTS_URL, title_link.get("href", "").strip())
            title = " ".join(title_link.stripped_strings)
            date_node = card.select_one("p.date")
            date_text = date_node.get_text(" ", strip=True) if date_node else ""
            starts_on, ends_on = _date_parts(date_text)
            if not title or event_url in seen or not _is_current_or_scheduled(starts_on, ends_on, date_text):
                continue
            seen.add(event_url)
            image = card.select_one("p.thum img")
            candidates.append(EventCandidate(
                publisher="NEXON Korea", game="\ub9c8\ube44\ub178\uae30", title=title, event_url=event_url,
                hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
                published_on=None, status="??", event_format=_event_format(event_url), collected_at=collected_at,
            ))
    return candidates
def collect_talesweaver_events() -> list[EventCandidate]:
    """Collect every official TalesWeaver event marked ongoing or upcoming."""
    first_soup = BeautifulSoup(_fetch_talesweaver_html(), "html.parser")
    last_page = _last_page_number(first_soup, r"[?&]page=(\d+)")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for page in range(1, last_page + 1):
        list_url = TALESWEAVER_EVENTS_URL if page == 1 else f"{TALESWEAVER_EVENTS_URL}?page={page}&pageSize=9"
        soup = first_soup if page == 1 else BeautifulSoup(_fetch_talesweaver_html(list_url), "html.parser")
        for anchor in soup.select("li.ing > a[href], li.ready > a[href], li.before > a[href]"):
            title_node = anchor.select_one("div.title .text")
            if title_node is None:
                continue
            event_url = urljoin(TALESWEAVER_EVENTS_URL, anchor.get("href", "").strip())
            title = title_node.get_text(" ", strip=True)
            period_node = anchor.select_one(".icon.time")
            period_text = period_node.get_text(" ", strip=True) if period_node else ""
            starts_on, ends_on = _date_parts(period_text)
            if not title or event_url in seen or not _is_current_or_scheduled(starts_on, ends_on, anchor.get_text(" ", strip=True)):
                continue
            seen.add(event_url)
            image = anchor.select_one(".thumbnail img")
            candidates.append(EventCandidate(
                publisher="NEXON Korea", game="\ud14c\uc77c\uc988\uc704\ubc84", title=title, event_url=event_url,
                hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
                published_on=None, status="??", event_format=_event_format(event_url), collected_at=collected_at,
            ))
    return candidates
def collect_elsword_events() -> list[EventCandidate]:
    """Collect every official Elsword event marked ongoing or upcoming."""
    first_soup = BeautifulSoup(_fetch_html(ELSWORD_EVENTS_URL), "html.parser")
    last_page = _last_page_number(first_soup, r"n4PageNo=(\d+)")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for page in range(1, last_page + 1):
        list_url = ELSWORD_EVENTS_URL if page == 1 else f"{ELSWORD_EVENTS_URL}?n4PageNo={page}"
        soup = first_soup if page == 1 else BeautifulSoup(_fetch_html(list_url), "html.parser")
        for card in soup.select("dl"):
            schedule = card.select_one(".e_schedule")
            title_link = card.select_one(".e_subject .subject a[href]")
            if schedule is None or title_link is None:
                continue
            date_node = schedule.select_one(".data")
            date_text = date_node.get_text(" ", strip=True) if date_node else ""
            starts_on, ends_on = _date_parts(date_text)
            status_text = schedule.get_text(" ", strip=True)
            if not schedule.select_one(".ing, .before, .ready") or not _is_current_or_scheduled(starts_on, ends_on, status_text):
                continue
            event_url = urljoin(ELSWORD_EVENTS_URL, title_link.get("href", "").strip())
            title = title_link.get_text(" ", strip=True)
            if not title or event_url in seen:
                continue
            seen.add(event_url)
            image = card.select_one("dt img")
            candidates.append(EventCandidate(
                publisher="NEXON Korea", game="\uc5d8\uc18c\ub4dc", title=title, event_url=event_url,
                hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
                published_on=None, status="??", event_format=_event_format(event_url), collected_at=collected_at,
            ))
    return candidates
def collect_baram_events() -> list[EventCandidate]:
    """Collect current events from the verified Baram official event list."""
    soup = BeautifulSoup(_fetch_html(BARAM_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    for card in soup.select("li dl"):
        title_link = card.select_one("dd.title a[href]")
        date_node = card.select_one("dd.date")
        if title_link is None or date_node is None:
            continue
        event_url = urljoin(BARAM_EVENTS_URL, title_link.get("href", "").strip())
        title = title_link.get_text(" ", strip=True)
        if not title or any(item.event_url == event_url for item in candidates):
            continue
        starts_on, ends_on = _date_parts(date_node.get_text(" ", strip=True))
        image = card.select_one("dt img")
        candidates.append(EventCandidate(
            publisher="NEXON Korea", game="\ubc14\ub78c\uc758\ub098\ub77c", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=None, status="ongoing", event_format=_event_format(event_url), collected_at=collected_at,
        ))
    candidates.extend(collect_baram_cashshop_events())
    return candidates


def _parse_cashshop_date(date_node) -> date | None:
    """dd.date p \uc548\uc758 '<span>2026</span>08-27' \uc870\uac01\uc744 date\ub85c \ud569\uce5c\ub2e4."""
    if date_node is None:
        return None
    year_node = date_node.select_one("span")
    year_text = year_node.get_text(strip=True) if year_node else ""
    month_day = date_node.get_text(" ", strip=True).replace(year_text, "", 1).strip()
    match = re.match(r"(\d{1,2})-(\d{1,2})", month_day)
    if not year_text or not match:
        return None
    try:
        return date(int(year_text), int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None


def collect_baram_cashshop_events() -> list[EventCandidate]:
    """Collect \ubc14\ub78c\uc758\ub098\ub77c's official \uce90\uc2dc\uc0f5 \uc5c5\ub370\uc774\ud2b8 board posts (\ubcc4\ub3c4 \uac8c\uc2dc\ud310,
    Event/List\uc640\ub294 \ub2e4\ub978 URL) \u2014 2026-08-27("\ud48d\uc694\uc758\ubcf4\ubb3c\ud568 \ud310\ub9e4") \uc774\ud6c4(\ud3ec\ud568)
    \uc62c\ub77c\uc628 \uac8c\uc2dc\ubb3c\ub9cc \uc218\uc9d1\ud55c\ub2e4(\uba85\uc2dc\uc801 \uc694\uccad)."""
    soup = BeautifulSoup(_fetch_html(BARAM_CASHSHOP_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for item in soup.select("div.con_aside li"):
        title_link = item.select_one("dd p a[href]")
        published = _parse_cashshop_date(item.select_one("dd.date p"))
        if title_link is None or published is None or published < _BARAM_CASHSHOP_CUTOFF:
            continue
        event_url = urljoin(BARAM_CASHSHOP_URL, title_link.get("href", "").strip())
        title = title_link.get_text(" ", strip=True)
        if not title or event_url in seen:
            continue
        seen.add(event_url)
        candidates.append(EventCandidate(
            publisher="NEXON Korea", game="\ubc14\ub78c\uc758\ub098\ub77c", title=title, event_url=event_url,
            hero_image_url=None, starts_on=published.isoformat(), ends_on=None,
            published_on=published.isoformat(), status="ongoing", event_format="board", collected_at=collected_at,
        ))
    return candidates


def collect_lostark_events() -> list[EventCandidate]:
    """Collect every page of the verified Lost Ark official event board."""
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    for page in range(1, 50):
        list_url = f"{LOSTARK_EVENTS_URL}?page={page}&searchtype=0&searchtext="
        soup = BeautifulSoup(_fetch_html(list_url), "html.parser")
        page_candidates = 0
        for anchor in soup.select("a[href]"):
            # The official "Now" board also contains announced upcoming events.
            if anchor.select_one(".list__status--ongoing, .list__status--before") is None:
                continue
            title_node = anchor.select_one(".list__title")
            if title_node is None:
                continue
            event_url = urljoin(LOSTARK_EVENTS_URL, anchor.get("href", "").strip())
            title = title_node.get_text(" ", strip=True)
            if not title or any(item.event_url == event_url for item in candidates):
                continue
            dates = [node.get("data-utc", "")[:10] for node in anchor.select(".list__term [data-utc]")]
            starts_on = dates[0] if dates else None
            ends_on = dates[1] if len(dates) > 1 else None
            image = anchor.select_one(".list__thumb img")
            candidates.append(EventCandidate(
                publisher="Smilegate RPG", game="\ub85c\uc2a4\ud2b8\uc544\ud06c", title=title, event_url=event_url,
                hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
                published_on=None, status="ongoing", event_format=_event_format(event_url), collected_at=collected_at,
            ))
            page_candidates += 1
        if page_candidates == 0:
            break
    return candidates
def _is_gersang_excluded(title: str) -> bool:
    """"당첨자 배송지" 안내글은 이벤트 참여글이 아니라 이미 끝난 이벤트의
    당첨자에게 배송지를 입력해달라는 사무 공지라 수집 대상에서 뺀다
    (명시적 요청)."""
    return "당첨자 배송지" in title


def collect_gersang_events() -> list[EventCandidate]:
    """Collect every ongoing campaign from the verified official Gersang event board."""
    soup = BeautifulSoup(_fetch_html(GERSANG_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for card in soup.select(".event-main .list-box"):
        label = card.select_one(".label")
        if label is None or "\uc9c4\ud589\uc911" not in label.get_text(" ", strip=True):
            continue
        title_link = card.select_one(".subject a[href]")
        if title_link is None:
            continue
        event_url = urljoin(GERSANG_EVENTS_URL, title_link.get("href", "").strip())
        title = title_link.get_text(" ", strip=True)
        date_node = card.select_one(".date")
        starts_on, ends_on = _date_parts(date_node.get_text(" ", strip=True) if date_node else "")
        if not title or event_url in seen or _is_gersang_excluded(title):
            continue
        seen.add(event_url)
        image = card.select_one(".thumnail img, .thumbnail img")
        candidates.append(EventCandidate(
            publisher="AtoZ Games", game="\uac70\uc0c1", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=starts_on, status="ongoing", event_format="full_page", collected_at=collected_at,
        ))
    return candidates


def collect_black_desert_events() -> list[EventCandidate]:
    """Collect every card from Black Desert's verified official ongoing-event board."""
    soup = BeautifulSoup(_fetch_html(BLACK_DESERT_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for card in soup.select(".event_area .event_list > ul > li"):
        anchor = card.select_one("a[href]")
        if anchor is None:
            continue
        event_url = urljoin(BLACK_DESERT_EVENTS_URL, anchor.get("href", "").strip())
        text = anchor.get_text(" ", strip=True)
        # The official selected board is ongoing only; remove visual badges and remaining-day text.
        title = re.sub(r"^(?:New\s*)+", "", text).strip()
        title = re.sub(r"\s+\d+\s*\uc77c\s*\ub0a8\uc74c$", "", title).strip()
        if not title or event_url in seen:
            continue
        seen.add(event_url)
        image = anchor.select_one(".img_area img")
        candidates.append(EventCandidate(
            publisher="Pearl Abyss", game="\uac80\uc740\uc0ac\ub9c9", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=None, ends_on=None,
            published_on=_published_date_from_page(event_url), status="ongoing", event_format="board", collected_at=collected_at,
        ))
    return candidates


def collect_cso_events() -> list[EventCandidate]:
    """Collect current or announced CS Online events from its official list."""
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for page in range(1, 102):
        list_url = CSO_EVENTS_URL if page == 1 else f"{CSO_EVENTS_URL}/{page}"
        soup = BeautifulSoup(_fetch_html(list_url), "html.parser")
        ongoing_on_page = 0
        for card in soup.select(".wrap_board ul.list > li"):
            state = card.select_one(".gr_state")
            status_text = state.get_text(" ", strip=True) if state else ""
            if "\uc9c4\ud589\uc911" not in status_text and "\uc608\uc815" not in status_text:
                continue
            title_link = card.select_one(".gr_tit .tit a[href]")
            if title_link is None:
                continue
            event_url = urljoin(CSO_EVENTS_URL, title_link.get("href", "").strip())
            title = title_link.get_text(" ", strip=True)
            period = card.select_one(".gr_tit .time")
            starts_on, ends_on = _date_parts(period.get_text(" ", strip=True) if period else "")
            if not title or not event_url or event_url in seen:
                continue
            seen.add(event_url)
            ongoing_on_page += 1
            image = card.select_one(".gr_img img")
            candidates.append(EventCandidate(
                publisher="NEXON Korea", game="\uce74\uc6b4\ud130\uc2a4\ud2b8\ub77c\uc774\ud06c \uc628\ub77c\uc778", title=title, event_url=event_url,
                hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
                published_on=starts_on, status=status_text, event_format=_event_format(event_url), collected_at=collected_at,
            ))
        # The official list is newest-first. Once a complete page has no
        # current/announced entry, later pages are historical only.
        if ongoing_on_page == 0:
            break
    return candidates


def collect_heroes_events() -> list[EventCandidate]:
    """Collect the official Mabinogi Heroes 'in progress' event board."""
    soup = BeautifulSoup(_fetch_html(HEROES_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for row in soup.select("table.tbl_list02 tbody tr"):
        title_link = row.select_one("td.tit a[href]") or row.select_one("td .img a[href]")
        if title_link is None:
            continue
        event_url = urljoin(HEROES_EVENTS_URL, title_link.get("href", "").strip())
        title_node = row.select_one("td.tit h3")
        title = title_node.get_text(" ", strip=True) if title_node else ""
        date_node = row.select_one("td.tit .date")
        starts_on, ends_on = _date_parts(date_node.get_text(" ", strip=True) if date_node else "")
        if not title or not event_url or event_url in seen:
            continue
        seen.add(event_url)
        image = row.select_one("td .img img")
        candidates.append(EventCandidate(
            publisher="NEXON Korea", game="\ub9c8\ube44\ub178\uae30 \uc601\uc6c5\uc804", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=starts_on, status="ongoing", event_format=_event_format(event_url), collected_at=collected_at,
        ))
    return candidates


def collect_ragnarok_events() -> list[EventCandidate]:
    """Collect every card from Ragnarok Online's official 'ongoing' event board."""
    soup = BeautifulSoup(_fetch_html(RAGNAROK_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for card in soup.select("section.eventList li"):
        title_link = card.select_one("p a[href]")
        if title_link is None:
            continue
        event_url = urljoin(RAGNAROK_EVENTS_URL, title_link.get("href", "").strip())
        title_node = title_link.select_one("strong")
        title = title_node.get_text(" ", strip=True) if title_node else title_link.get_text(" ", strip=True)
        date_node = title_link.select_one(".date em")
        starts_on, ends_on = _date_parts(date_node.get_text(" ", strip=True) if date_node else "")
        if not title or event_url in seen:
            continue
        seen.add(event_url)
        image = card.select_one("a.eventImg img")
        candidates.append(EventCandidate(
            publisher="Gravity", game="라그나로크", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=starts_on, status="ongoing", event_format="board", collected_at=collected_at,
        ))
    return candidates


def collect_audition_events() -> list[EventCandidate]:
    """Collect Audition(오디션)'s official event cards.

    The "진행중인 이벤트"(id="progress") list actually keeps stale entries
    around past their listed end date (confirmed live: an event that ended
    2025-07-31 was still showing today) — like the other sources here, trust
    each card's own printed date range rather than which tab it sits under."""
    soup = BeautifulSoup(_fetch_html(AUDITION_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for item in soup.select("ul#progress > li"):
        title_link = item.select_one("dt.title a[href]")
        if title_link is None:
            continue
        title = title_link.get_text(" ", strip=True)
        event_url = urljoin(AUDITION_EVENTS_URL, title_link.get("href", "").strip())
        if not title or not event_url or event_url in seen:
            continue
        starts_on, ends_on = _date_parts(" ".join(item.stripped_strings))
        if not _is_current_or_scheduled(starts_on, ends_on):
            continue
        seen.add(event_url)
        image = item.select_one(".thumb img")
        candidates.append(EventCandidate(
            publisher="한빛소프트", game="오디션", title=title, event_url=event_url,
            hero_image_url=urljoin(AUDITION_EVENTS_URL, image.get("src", "").strip()) if image and image.get("src") else None,
            starts_on=starts_on, ends_on=ends_on,
            published_on=starts_on, status="ongoing", event_format=_event_format(event_url), collected_at=collected_at,
        ))
    return candidates


def collect_talesrunner_events() -> list[EventCandidate]:
    """Collect dated, active campaigns from TalesRunner's official event API."""
    payload = json.loads(_fetch_html(TALESRUNNER_EVENT_API_URL))
    items = ((payload.get("result") or {}).get("list") or []) if isinstance(payload, dict) else []
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("isSnb"):
            continue
        title = str(item.get("subject") or item.get("subtitle") or "").strip()
        link = str(item.get("link") or "").strip()
        starts_on = str(item.get("snbStartAt") or "")[:10] or None
        ends_on = str(item.get("snbEndAt") or "")[:10] or None
        if not title or not link or not _is_current_or_scheduled(starts_on, ends_on, "ongoing"):
            continue
        candidates.append(EventCandidate(
            publisher="RHAON Entertainment", game="\ud14c\uc77c\uc988\ub7f0\ub108", title=title,
            event_url=urljoin("https://tr.rhaon.co.kr", link), hero_image_url=item.get("eventImageUrl"),
            starts_on=starts_on, ends_on=ends_on, published_on=starts_on, status="ongoing",
            event_format="full_page", collected_at=collected_at,
        ))
    return candidates


def collect_dnf_events() -> list[EventCandidate]:
    """Collect every current event from Dungeon Fighter's official event list."""
    soup = BeautifulSoup(_fetch_html(DNF_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for card in soup.select("article.board_eventlist li.title"):
        title_node = card.select_one("b")
        if title_node is None:
            continue
        title = title_node.get_text(" ", strip=True)
        period = card.select_one("span")
        starts_on, ends_on = _date_parts(period.get_text(" ", strip=True) if period else "")
        if not title or not _is_current_or_scheduled(starts_on, ends_on, "ongoing"):
            continue
        onclick = card.get("onclick", "")
        match = re.search(r"window\.location\.href=['\"]([^'\"]+)", onclick)
        if match:
            event_url = urljoin(DNF_EVENTS_URL, match.group(1))
        elif card.get("data-no"):
            # Verified official board detail route for the list item's data-no.
            event_url = f"https://df.nexon.com/community/news/event/{card['data-no']}"
        else:
            continue
        if event_url in seen:
            continue
        seen.add(event_url)
        image = card.select_one("img")
        candidates.append(EventCandidate(
            publisher="NEOPLE", game="\ub358\uc804\uc564\ud30c\uc774\ud130", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=starts_on, status="ongoing", event_format=_event_format(event_url), collected_at=collected_at,
        ))
    return candidates


def collect_cyphers_events() -> list[EventCandidate]:
    """Collect Cyphers(사이퍼즈) events — 풀페이지(dedicated "/pages/events/..."
    landing pages)만 수집한다. 게시판형("/article/event/topic/...") 공지는
    명시적 요청에 따라 제외한다."""
    soup = BeautifulSoup(_fetch_html(CYPHERS_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for card in soup.select("div.event_list > ul"):
        title_link = card.select_one("li.tbox p a[href]")
        if title_link is None:
            continue
        event_url = urljoin(CYPHERS_EVENTS_URL, title_link.get("href", "").strip())
        if _event_format(event_url) != "full_page":
            continue
        title = title_link.get_text(" ", strip=True)
        if not title or event_url in seen:
            continue
        seen.add(event_url)
        date_node = card.select_one("li.tbox p.date")
        starts_on, ends_on = _date_parts_md(date_node.get_text(" ", strip=True) if date_node else "")
        image = card.select_one("li.thum img")
        candidates.append(EventCandidate(
            publisher="NEXON Korea", game="사이퍼즈", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=starts_on, status="ongoing", event_format="full_page", collected_at=collected_at,
        ))
    return candidates


def _extract_balanced_array(text: str, start: int) -> str | None:
    """text[start]가 '['라고 가정하고, 문자열 리터럴 안의 대괄호(예:
    summary 값 "[사전 참가 신청 바로가기]")는 무시하면서 짝이 맞는 ']'
    까지를 잘라 반환한다."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _thefinals_slug(title: str) -> str:
    """실제 사이트의 URL 슬러그 규칙을 흉내낸다(threadId만 실제로 라우팅에
    쓰이고 슬러그 값 자체는 검증되지 않는 걸 직접 확인했지만, 그래도 진짜
    URL과 같은 모양으로 만든다)."""
    cleaned = re.sub(r"[^\w가-힣\s-]", "", title).strip()
    return re.sub(r"\s+", "-", cleaned).lower()


def _parse_thefinals_threads(page_html: str) -> list[dict]:
    marker = '"threads":['
    idx = page_html.find(marker)
    if idx == -1:
        return []
    raw = _extract_balanced_array(page_html, idx + len(marker) - 1)
    if raw is None:
        return []
    try:
        threads = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return threads if isinstance(threads, list) else []


def collect_thefinals_events() -> list[EventCandidate]:
    """Collect THE FINALS' 이벤트 게시판 중 "통이미지"(설명 텍스트가 거의
    없는 배너형) 게시물만 — 목록 페이지가 React Query 하이드레이션 데이터를
    <script> 안에 그대로 심어두므로(threadId/title/summary/thumbnailImageUrl
    포함), HTML 마크업을 스크레이핑하는 대신 그 JSON을 직접 파싱한다."""
    page_html = _fetch_html(THEFINALS_EVENTS_URL)
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    for thread in _parse_thefinals_threads(page_html):
        summary = (thread.get("summary") or "").strip()
        if len(summary) > _THEFINALS_SUMMARY_MAX_LEN:
            continue
        thread_id = thread.get("threadId")
        title = html_lib.unescape(str(thread.get("title") or "")).strip()
        if not thread_id or not title:
            continue
        published = None
        create_date = thread.get("createDate")
        if isinstance(create_date, (int, float)):
            published = datetime.fromtimestamp(create_date, tz=timezone.utc).date().isoformat()
        event_url = f"https://thefinals.nexon.com/news/{thread_id}/{_thefinals_slug(title)}"
        candidates.append(EventCandidate(
            publisher="NEXON Korea", game="더 파이널스", title=title, event_url=event_url,
            hero_image_url=thread.get("thumbnailImageUrl"), starts_on=published, ends_on=None,
            published_on=published, status="ongoing", event_format="board", collected_at=collected_at,
        ))
    return candidates


def collect_lod_events() -> list[EventCandidate]:
    """Collect 어둠의전설 풀페이지(dedicated "/event/..." landing pages)만 —
    게시판형("/News/event/{id}") 공지는 명시적 요청에 따라 제외한다."""
    soup = BeautifulSoup(_fetch_html(LOD_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for item in soup.select(".media_list.ml_ev li"):
        title_link = item.select_one("a[href]")
        if title_link is None:
            continue
        event_url = urljoin(LOD_EVENTS_URL, title_link.get("href", "").strip())
        if _event_format(event_url) != "full_page":
            continue
        title_node = title_link.select_one(".tit")
        title = title_node.get_text(" ", strip=True) if title_node else title_link.get_text(" ", strip=True)
        if not title or event_url in seen:
            continue
        seen.add(event_url)
        date_node = item.select_one(".info .timeline .date")
        starts_on, ends_on = _parse_lod_date_range(date_node.get_text(" ", strip=True) if date_node else "")
        image = title_link.select_one("img")
        candidates.append(EventCandidate(
            publisher="NEXON Korea", game="어둠의전설", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=starts_on, status="ongoing", event_format="full_page", collected_at=collected_at,
        ))
    return candidates


def collect_eternalreturn_events() -> list[EventCandidate]:
    """Collect 이터널 리턴의 좌측(side) 이벤트 메뉴에 나열된 캠페인들 — 이
    사이트는 이벤트마다 독립된 랜딩 페이지(event.playeternalreturn.com/...)
    뿐이라 전부 풀페이지로 취급한다."""
    soup = BeautifulSoup(_fetch_html(ETERNALRETURN_EVENTS_URL), "html.parser")
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for item in soup.select(".mode_side ul li"):
        title_node = item.select_one(".tit")
        link = item.select_one("a[href]")
        if title_node is None or link is None:
            continue
        title = title_node.get_text(" ", strip=True)
        event_url = urljoin(ETERNALRETURN_EVENTS_URL, link.get("href", "").strip())
        if not title or event_url in seen:
            continue
        seen.add(event_url)
        text_node = item.select_one(".txt")
        starts_on, ends_on = _parse_eternalreturn_dates(text_node.get_text(" ", strip=True) if text_node else "")
        image = item.select_one("img")
        candidates.append(EventCandidate(
            publisher="Nimble Neuron", game="이터널 리턴", title=title, event_url=event_url,
            hero_image_url=image.get("src") if image else None, starts_on=starts_on, ends_on=ends_on,
            published_on=starts_on, status="ongoing", event_format="full_page", collected_at=collected_at,
        ))
    return candidates


def _eventon_full_page_entry(item: dict) -> dict | None:
    """NC\uc758 \uacf5\uc6a9 '\uc774\ubca4\ud2b8ON' \ud50c\ub7ab\ud3fc\uc740 \ub85c\uc2a4\ud2b8\uc544\ud06c\uc640 \ub2ec\ub9ac \uac01 \ud56d\ubaa9\uc774 \uc2e4\uc81c\ub85c
    \uc5b4\ub514\ub85c \uc5f0\uacb0\ub418\ub294\uc9c0\ub97c URL \ud328\ud134 \ucd94\uce21 \uc5c6\uc774 marketingEntrySet[].entryType\ub85c
    \uc9c1\uc811 \uc54c\ub824\uc900\ub2e4 \u2014 "promo"\ub294 \uc804\uc6a9 \ub79c\ub529 \ud398\uc774\uc9c0(\ud480\ud398\uc774\uc9c0), "link_board"\ub294
    \uac8c\uc2dc\ud310 \uae00, "link"\ub294 \uc678\ubd80 \ub9c1\ud06c. \uac8c\uc2dc\ud310/\uc678\ubd80 \ub9c1\ud06c\ub9cc \uc788\ub294 \ud56d\ubaa9\uc740 \uc81c\uc678\ud558\uace0,
    \ud480\ud398\uc774\uc9c0 entry\uac00 \uc788\uc73c\uba74(\ubcf4\ud1b5 \uae30\uae30\ubcc4\ub85c \uc911\ubcf5) PC(NORMAL)\uc6a9\uc744 \uc6b0\uc120
    \ub3cc\ub824\uc900\ub2e4 \u2014 \uc2e4\uce21 \ud655\uc778: lineagem.plaync.com/eventon 13\uac74 \uc911 2\uac74\ub9cc promo,
    \ub098\uba38\uc9c0 11\uac74\uc740 board \uae00\uc774\uc5c8\ub2e4."""
    entries = [e for e in (item.get("marketingEntrySet") or []) if e.get("entryType") == "promo" and e.get("entryUrl")]
    if not entries:
        return None
    return next((e for e in entries if e.get("entryDevice") == "NORMAL"), entries[0])


def _eventon_hero_image(item: dict) -> str | None:
    additions = {a.get("additionType"): a.get("additionData") for a in (item.get("marketingItemAdditionSet") or [])}
    return additions.get("eventListImgUrl") or additions.get("eventListSmallImgUrl") or additions.get("snsImgUrl")


def _collect_nc_eventon_game(game: str, domain_tag: str) -> list[EventCandidate]:
    """NC \ud55c \uac8c\uc784\uc758 \uc9c4\ud589 \uc911 \uc774\ubca4\ud2b8 \uc911, \uac8c\uc2dc\ud310 \uae00\uc774 \uc544\ub2c8\ub77c \uc804\uc6a9 \ud480\ud398\uc774\uc9c0\ub85c
    \uc5f0\uacb0\ub418\ub294 \uac83\ub9cc \ubaa8\uc740\ub2e4. \uc774\uc804\uc5d0\ub294 LINEAGE_EVENTON_API_URL(promotion.plaync.
    com/eventon/on)\uc744 \ud638\ucd9c\ud588\ub294\ub370, \uc774 \uc5d4\ub4dc\ud3ec\uc778\ud2b8\ub294 \uad00\ub9ac\uc790\uc6a9 \ube48 \uc54c\ub9bc
    \ubc84\ud0b7({"ON_ISSUE":[],...})\ub9cc \ub3cc\ub824\uc918\uc11c \uc2e4\uc81c\ub85c\ub294 \ud56d\uc0c1 0\uac74\uc774\uc5c8\ub2e4(\uc9c1\uc811
    \uc2e4\ud589\ud574\uc11c \ud655\uc778) \u2014 \ud654\uba74\uc774 \uc2e4\uc81c\ub85c \ud638\ucd9c\ud558\ub294 \ubaa9\ub85d API(/eventon/item)\ub85c
    \ubc14\uafe8\ub2e4."""
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    page = 1
    while True:
        tag = quote(f"MKT_PROMOTION,{domain_tag},,", safe="")
        list_url = f"{NC_EVENTON_API_URL}?tag={tag}&status=RUNNING&pageSize=50&page={page}"
        payload = json.loads(_fetch_html(list_url))
        for item in payload.get("content", []):
            entry = _eventon_full_page_entry(item)
            if entry is None:
                continue
            event_url = (entry.get("entryUrl") or "").strip()
            title = (item.get("itemTitle") or "").strip()
            if not event_url or not title or event_url in seen:
                continue
            seen.add(event_url)
            candidates.append(EventCandidate(
                publisher="NCSOFT", game=game, title=title, event_url=event_url,
                hero_image_url=_eventon_hero_image(item),
                starts_on=(item.get("itemStart") or "")[:10] or None,
                ends_on=(item.get("itemEnd") or "")[:10] or None,
                published_on=None, status="ongoing", event_format="full_page", collected_at=collected_at,
            ))
        if payload.get("last", True):
            break
        page += 1
    return candidates


def collect_lineage_events() -> list[EventCandidate]:
    """Collect official Lineage(1) EventON full-page cards (board posts excluded)."""
    return _collect_nc_eventon_game("\ub9ac\ub2c8\uc9c0", "DOMAIN_LINEAGE")


def collect_lineagem_events() -> list[EventCandidate]:
    """Collect official Lineage M EventON full-page cards (board posts excluded)."""
    return _collect_nc_eventon_game("\ub9ac\ub2c8\uc9c0M", "DOMAIN_LINEAGEM")


def collect_blade_and_soul_events() -> list[EventCandidate]:
    """Collect official Blade & Soul EventON full-page cards (board posts excluded)."""
    return _collect_nc_eventon_game("\ube14\ub808\uc774\ub4dc\uc564\uc18c\uc6b8", "DOMAIN_BNS")

# \ub9ac\ub2c8\uc9c02/\ub9ac\ub2c8\uc9c02M/\uc544\uc774\uc628/\uc544\uc774\uc6282\ub3c4 \uac19\uc740 \ud50c\ub7ab\ud3fc(EventON)\uc744 \uc4f0\uc9c0\ub9cc,
# \uc9c1\uc811 \uc870\ud68c\ud574 \ud655\uc778\ud574\ubcf4\ub2c8 \ud604\uc7ac \uc9c4\ud589 \uc911\uc778 \uc774\ubca4\ud2b8\uac00 \ubaa8\ub450 "promo"(\ud480\ud398\uc774\uc9c0)\uac00
# \uc544\ub2cc "link_board"(\uac8c\uc2dc\ud310) \ud0c0\uc785\uc774\uc5b4\uc11c, \ud480\ud398\uc774\uc9c0\ub9cc \uac70\ub974\ub294 \uc218\uc9d1\uae30\ub97c \ub192\uc774\uba74
# \ud56d\uc0c1 0\uac74\uc774\ub2e4 \u2014 event_bench_refresh.py\uac00 \ube48 \uacb0\uacfc\ub97c "\uc218\uc9d1 \uc2e4\ud328"\ub85c \ucde8\uae09\ud574 \ub9e4\ubc88
# \ub85c\uadf8\uc5d0 \uc624\ub958\ub85c \ucc0d\ud790 \uac83\uc774\ub77c, \ud574\ub2f9 \uac8c\uc784\ub4e4\uc774 \uc2e4\uc81c\ub85c \ud480\ud398\uc774\uc9c0 \uc774\ubca4\ud2b8\ub97c \uc4f0\uae30
# \uc2dc\uc791\ud558\uba74 \uadf8\ub54c \ucd94\uac00\ud55c\ub2e4.


def collect_nexon_events() -> list[EventCandidate]:
    return [
        *collect_fc_online_events(),
        *collect_maplestory_events(),
        *collect_mabinogi_events(),
        *collect_talesweaver_events(),
        *collect_elsword_events(),
        *collect_baram_events(),
        *collect_lostark_events(),
        *collect_lineage_events(),
        *collect_lineagem_events(),
        *collect_blade_and_soul_events(),
        *collect_black_desert_events(),
        *collect_gersang_events(),
        *collect_cso_events(),
        *collect_heroes_events(),
        *collect_talesrunner_events(),
        *collect_dnf_events(),
        *collect_audition_events(),
        *collect_cyphers_events(),
        *collect_thefinals_events(),
        *collect_lod_events(),
        *collect_eternalreturn_events(),
    ]
def main() -> None:
    parser = argparse.ArgumentParser(description="Collect verified NEXON official event candidates.")
    parser.add_argument("--source", choices=("fc-online", "maplestory", "mabinogi", "talesweaver", "elsword", "baram", "lostark", "lineage", "lineagem", "blade-and-soul", "black-desert", "gersang", "cso", "heroes", "talesrunner", "dnf", "ragnarok", "audition", "cyphers", "thefinals", "lod", "eternalreturn", "all"), default="all")
    parser.add_argument("--output", type=Path, help="Optional UTF-8 JSON output path.")
    args = parser.parse_args()
    if args.source == "fc-online":
        candidates = collect_fc_online_events()
    elif args.source == "maplestory":
        candidates = collect_maplestory_events()
    elif args.source == "mabinogi":
        candidates = collect_mabinogi_events()
    elif args.source == "talesweaver":
        candidates = collect_talesweaver_events()
    elif args.source == "elsword":
        candidates = collect_elsword_events()
    elif args.source == "baram":
        candidates = collect_baram_events()
    elif args.source == "lostark":
        candidates = collect_lostark_events()
    elif args.source == "lineage":
        candidates = collect_lineage_events()
    elif args.source == "lineagem":
        candidates = collect_lineagem_events()
    elif args.source == "blade-and-soul":
        candidates = collect_blade_and_soul_events()
    elif args.source == "black-desert":
        candidates = collect_black_desert_events()
    elif args.source == "gersang":
        candidates = collect_gersang_events()
    elif args.source == "cso":
        candidates = collect_cso_events()
    elif args.source == "heroes":
        candidates = collect_heroes_events()
    elif args.source == "talesrunner":
        candidates = collect_talesrunner_events()
    elif args.source == "dnf":
        candidates = collect_dnf_events()
    elif args.source == "ragnarok":
        candidates = collect_ragnarok_events()
    elif args.source == "audition":
        candidates = collect_audition_events()
    elif args.source == "cyphers":
        candidates = collect_cyphers_events()
    elif args.source == "thefinals":
        candidates = collect_thefinals_events()
    elif args.source == "lod":
        candidates = collect_lod_events()
    elif args.source == "eternalreturn":
        candidates = collect_eternalreturn_events()
    else:
        candidates = collect_nexon_events()
    rendered = json.dumps([asdict(item) for item in candidates], ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

