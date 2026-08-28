"""Verified sample collectors for official NEXON event lists.

Each source is explicitly registered only after its official list URL and
markup have been checked.  The collectors discover candidates; they do not
make a subjective design-quality judgment.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


FC_ONLINE_EVENTS_URL = "https://fconline.nexon.com/news/events"
MAPLESTORY_EVENTS_URL = "https://maplestory.nexon.com/news/event"
MABINOGI_EVENTS_URL = "https://mabinogi.nexon.com/page/news/event_list.asp"
TALESWEAVER_EVENTS_URL = "https://tales.nexon.com/News/Event"
ELSWORD_EVENTS_URL = "https://elsword.nexon.com/News/Events/List"
BARAM_EVENTS_URL = "https://baram.nexon.com/Event/List"
LOSTARK_EVENTS_URL = "https://lostark.game.onstove.com/News/Event/Now"
LINEAGE_EVENTON_API_URL = "https://promotion.plaync.com/eventon/on"
BLACK_DESERT_EVENTS_URL = "https://www.kr.playblackdesert.com/ko-KR/News/Notice?boardType=3&progressType=1"
GERSANG_EVENTS_URL = "https://www.gersang.co.kr/news/event.gs"
DNF_EVENTS_URL = "https://df.nexon.com/community/news/event/list"
TALESRUNNER_EVENT_API_URL = "https://tr.rhaon.co.kr/eventb/event/SNB"
CSO_EVENTS_URL = "https://csonline.nexon.com/News/Event/List"
HEROES_EVENTS_URL = "https://heroes.nexon.com/news/event/ing"
RAGNAROK_EVENTS_URL = "https://ro.gnjoy.com/news/event/list.asp"
_DATE_RANGE = re.compile(r"(20\d{2}\s*[.-]\s*\d{2}\s*[.-]\s*\d{2})\s*[^~]{0,20}~\s*(20\d{2}\s*[.-]\s*\d{2}\s*[.-]\s*\d{2})")


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


def _fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; EventBenchSample/0.1)"}
    if "mabinogi.nexon.com" in url:
        # mabinogi.nexon.com's WAF has been returning a blanket 403 to every
        # GitHub Actions run since 2026-08-25 01:47 (confirmed via
        # data/ci/event_bench/refresh.log — every other Nexon-family source
        # in the same run succeeds, so this is specific to this one host's
        # bot check, not an IP-range ban on all of nexon.com). The generic
        # self-identifying UA above is exactly what a WAF keys on; a real
        # browser UA + the headers a browser actually sends is the same fix
        # already used for 삼성전자 뉴스룸 in collector.py.
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://mabinogi.nexon.com/",
        }
    request = Request(url, headers=headers)
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
        if not title or event_url in seen:
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


def collect_lineage_events() -> list[EventCandidate]:
    """Collect official Lineage EventON cards when the public feed has entries."""
    payload = json.loads(_fetch_html(LINEAGE_EVENTON_API_URL))
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for group in payload.values() if isinstance(payload, dict) else []:
        for raw_item in group if isinstance(group, list) else []:
            item = json.loads(raw_item) if isinstance(raw_item, str) else raw_item
            if not isinstance(item, dict):
                continue
            event_url = (item.get("link") or item.get("url") or "").strip()
            title = re.sub(r"<[^>]+>", "", str(item.get("title") or "")).strip()
            if not event_url or not title or event_url in seen:
                continue
            seen.add(event_url)
            date_text = " ".join(str(item.get(key) or "") for key in ("period", "startDate", "endDate"))
            starts_on, ends_on = _date_parts(date_text)
            if not _is_current_or_scheduled(starts_on, ends_on, str(item.get("status") or "??")):
                continue
            candidates.append(EventCandidate(
                publisher="NCSOFT", game="\ub9ac\ub2c8\uc9c0", title=title, event_url=event_url,
                hero_image_url=item.get("img") or item.get("image"), starts_on=starts_on, ends_on=ends_on,
                published_on=None, status="??", event_format="full_page", collected_at=collected_at,
            ))
    return candidates


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
        *collect_black_desert_events(),
        *collect_gersang_events(),
        *collect_cso_events(),
        *collect_heroes_events(),
        *collect_talesrunner_events(),
        *collect_dnf_events(),
    ]
def main() -> None:
    parser = argparse.ArgumentParser(description="Collect verified NEXON official event candidates.")
    parser.add_argument("--source", choices=("fc-online", "maplestory", "mabinogi", "talesweaver", "elsword", "baram", "lostark", "lineage", "black-desert", "gersang", "cso", "heroes", "talesrunner", "dnf", "ragnarok", "all"), default="all")
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
    else:
        candidates = collect_nexon_events()
    rendered = json.dumps([asdict(item) for item in candidates], ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

