"""Collectors for verified official HTML news lists without usable RSS."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from .collector import SourceResult
from .models import Article


KST = timezone(timedelta(hours=9))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
RELEVANCE_TERMS = (
    "게임", "게이밍", "이스포츠", "e스포츠", "인디게임", "콘솔",
    "인공지능", "생성형 ai", " ai ", "ai·", "ai ", "ai기술", "ai 기술",
    "게임산업", "게임 산업", "게임물", "확률형 아이템",
)


@dataclass(frozen=True)
class OfficialHtmlSource:
    name: str
    list_url: str
    category: str
    parser: str
    page_param: str
    max_pages: int = 6
    first_page: int = 1


OFFICIAL_HTML_SOURCES = (
    OfficialHtmlSource(
        "한국콘텐츠진흥원",
        "https://www.kocca.kr/kocca/koccanews/reportlist.do?menuNo=204767",
        "GAME",
        "kocca",
        "pageIndex",
    ),
    OfficialHtmlSource(
        "문화체육관광부",
        "https://www.mcst.go.kr/site/s_notice/press/pressList.jsp?pCurrentPage=1",
        "GAME",
        "mcst",
        "pCurrentPage",
    ),
    OfficialHtmlSource(
        "대한민국 정책브리핑",
        "https://www.korea.kr/briefing/pressReleaseList.do?pageIndex=1",
        "AUTO",
        "korea_policy",
        "pageIndex",
    ),
    OfficialHtmlSource(
        "게임물관리위원회",
        "https://www.grac.or.kr/Board/NewsData.aspx?pageindex=0",
        "GAME",
        "grac",
        "pageindex",
        first_page=0,
    ),
    OfficialHtmlSource(
        "크래프톤",
        "https://www.krafton.com/news/press/?var_page=1",
        "GAME",
        "krafton",
        "var_page",
        max_pages=3,
    ),
    OfficialHtmlSource(
        "넥슨게임즈",
        "https://www.nexongames.co.kr/bbs/board.php?bo_table=media_event&page=1",
        "GAME",
        "nexon_games",
        "page",
        max_pages=3,
    ),
    OfficialHtmlSource(
        "넷마블",
        "https://ch.netmarble.com/Newsroom/PressRelease/List",
        "GAME",
        "netmarble",
        "page",
        max_pages=1,
    ),
)


def _fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def _fetch_bytes(url: str, max_bytes: int = 10_000_000) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError("official attachment exceeds size limit")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("official attachment exceeds size limit")
        return data


def _is_relevant(title: str, summary: str = "") -> bool:
    text = f" {title} {summary} ".lower()
    return any(term in text for term in RELEVANCE_TERMS)


def _date(value: str) -> datetime | None:
    match = re.search(
        r"(20\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})",
        value,
    )
    if not match:
        return None
    return datetime(*(int(part) for part in match.groups()), tzinfo=KST)


def _parse_kocca(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for item in soup.select(".board_list03 > ul > li"):
        link = item.find("a", href=True)
        title_node = item.select_one(".title")
        if not link or not title_node:
            continue
        title = title_node.get_text(" ", strip=True)
        summary_node = item.select_one(".txt span")
        summary = summary_node.get_text(" ", strip=True) if summary_node else ""
        if not _is_relevant(title, summary):
            continue
        info = item.select_one(".info")
        entries.append({
            "title": title,
            "url": urljoin(base_url, link["href"]),
            "summary": summary,
            "published_at": _date(info.get_text(" ", strip=True) if info else ""),
        })
    return entries


def _parse_mcst(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for row in soup.select("tr"):
        link = row.select_one('a[href*="pressView.jsp"]')
        if not link:
            continue
        title = (link.get("title") or link.get_text(" ", strip=True)).strip()
        if not title or not _is_relevant(title):
            continue
        date_node = row.select_one('[aria-label="게시일"]')
        entries.append({
            "title": title,
            "url": urljoin(base_url, link["href"]),
            "summary": "",
            "published_at": _date(date_node.get_text(" ", strip=True) if date_node else ""),
        })
    return entries


def _parse_korea_policy(html: str, base_url: str) -> list[dict]:
    """Parse verified Korea Policy Briefing press-release list entries.

    MCST releases are intentionally skipped because the original ministry
    collector already provides them (including attachment text).
    """
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for link in soup.select('a[href*="pressReleaseView.do"]'):
        title_node = link.select_one(".text > strong")
        source_nodes = link.select(".source > span")
        if not title_node or len(source_nodes) < 2:
            continue
        title = title_node.get_text(" ", strip=True)
        summary_node = link.select_one(".lead")
        summary = summary_node.get_text(" ", strip=True) if summary_node else ""
        publisher = source_nodes[-1].get_text(" ", strip=True)
        # This portal republishes every ministry's full body. Body matching is
        # too noisy (incidental AI mentions), so only an explicit title match
        # is accepted for this broad cross-government source.
        if publisher == "문화체육관광부" or not _is_relevant(title):
            continue
        entries.append({
            "title": title,
            "url": urljoin(base_url, link["href"]),
            "summary": summary,
            "published_at": _date(source_nodes[0].get_text(" ", strip=True)),
            "publisher": publisher,
        })
    return entries


GRAC_POLICY_TERMS = (
    "확률형", "표시의무", "피해구제", "불법게임", "불법 게임",
    "사설서버", "등급분류", "사행성", "게임산업법", "게임법",
    "행정지도", "이용자보호", "이용자 보호", "자체등급분류",
)


def _parse_grac(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for row in soup.select("tr"):
        link = row.select_one('a[href*="type=view"][href*="bno="]')
        cells = row.find_all("td", recursive=False)
        if not link or len(cells) < 3:
            continue
        title = link.get_text(" ", strip=True)
        if not any(term in title.replace(" ", "") for term in GRAC_POLICY_TERMS):
            continue
        entries.append({
            "title": title,
            "url": urljoin(base_url, link["href"]),
            "summary": "",
            "published_at": _date(cells[2].get_text(" ", strip=True)),
        })
    return entries


def _parse_krafton(html: str, base_url: str) -> list[dict]:
    """Parse KRAFTON's verified first-party press-release cards."""
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for item in soup.select(".NewsListItem"):
        link = item.select_one("a.NewsListItem-link[href]")
        title_node = item.select_one(".title")
        if not link or not title_node:
            continue
        title = title_node.get_text(" ", strip=True)
        summary_node = item.select_one(".NewsListItem-text")
        date_node = item.select_one(".date")
        entries.append({
            "title": title,
            "url": urljoin(base_url, link["href"]),
            "summary": summary_node.get_text(" ", strip=True) if summary_node else "",
            "published_at": _date(date_node.get_text(" ", strip=True) if date_node else ""),
        })
    return entries


def _parse_nexon_games(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for item in soup.select(".gall_li"):
        link = item.select_one("a.bo_tit[href]")
        date_node = item.select_one(".wr_date")
        if not link:
            continue
        entries.append({
            "title": link.get_text(" ", strip=True),
            "url": urljoin(base_url, link["href"]),
            "summary": "",
            "published_at": _date(date_node.get_text(" ", strip=True) if date_node else ""),
        })
    return entries


def _parse_netmarble(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for item in soup.select(".list_item"):
        title_node = item.select_one(".cont_b .title")
        date_node = item.select_one(".cont_b .date")
        action = item.select_one('a[onclick*="ContentsClickEvent"]')
        if not title_node or not action:
            continue
        match = re.search(
            r"ContentsClickEvent\('user',\s*'(\d+)',\s*'(\d+)'",
            action.get("onclick", ""),
        )
        if not match:
            continue
        board_code, post_seq = match.groups()
        detail_path = (
            f"/Newsroom/PressRelease/Detail?bbs_code={board_code}"
            f"&post_seq={post_seq}"
        )
        entries.append({
            "title": title_node.get_text(" ", strip=True),
            "url": urljoin(base_url, detail_path),
            "summary": "",
            "published_at": _date(date_node.get_text(" ", strip=True) if date_node else ""),
        })
    return entries


def _fetch_grac_summary(page_url: str) -> str:
    soup = BeautifulSoup(_fetch_html(page_url), "html.parser")
    panel = soup.find(id="ctl00_ContentHolder_BoardHolder_ctl00_pnlBoardContentView")
    if not panel:
        return ""
    candidates = [
        cell.get_text(" ", strip=True)
        for cell in panel.find_all("td")
        if len(cell.get_text(" ", strip=True)) >= 100
    ]
    return max(candidates, key=len) if candidates else ""


def _mcst_pdf_url(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for attachment in soup.select(".add_file"):
        label = attachment.select_one(".pdf_down")
        link = attachment.select_one('a[onclick*="file_download"]')
        if not label or not link:
            continue
        match = re.search(
            r"file_download\('([^']+)',\s*'([^']+)',\s*'([^']+)'",
            link.get("onclick", ""),
        )
        if not match:
            continue
        original_name, saved_name, path = match.groups()
        base = urljoin(page_url, "/servlets/eduport/front/upload/UplDownloadFile")
        return (
            f"{base}?pFileName={original_name}&pRealName={saved_name}"
            f"&pPath={path}&pFlag="
        )
    return None


def _pdf_text(data: bytes, max_pages: int = 12, max_chars: int = 12_000) -> str:
    reader = PdfReader(BytesIO(data))
    parts = []
    length = 0
    for page in reader.pages[:max_pages]:
        text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        if not text:
            continue
        remaining = max_chars - length
        if remaining <= 0:
            break
        parts.append(text[:remaining])
        length += len(parts[-1])
    return " ".join(parts).strip()


def _fetch_mcst_summary(page_url: str) -> str:
    html = _fetch_html(page_url)
    pdf_url = _mcst_pdf_url(html, page_url)
    if pdf_url:
        try:
            text = _pdf_text(_fetch_bytes(pdf_url))
            if text:
                return text
        except Exception:
            # The official HTML body still provides a safe fallback when an
            # attachment is temporarily unavailable or image-only.
            pass
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".view_con")
    return body.get_text(" ", strip=True) if body else ""


PARSERS = {
    "kocca": _parse_kocca,
    "mcst": _parse_mcst,
    "korea_policy": _parse_korea_policy,
    "grac": _parse_grac,
    "krafton": _parse_krafton,
    "nexon_games": _parse_nexon_games,
    "netmarble": _parse_netmarble,
}


def _entry_category(source: OfficialHtmlSource, entry: dict) -> str:
    if source.category != "AUTO":
        return source.category
    text = f" {entry['title']} {entry.get('summary', '')} ".lower()
    ai_terms = ("인공지능", "생성형 ai", "ai·", "ai기술", "ai 기술")
    return "AI" if any(term in text for term in ai_terms) or re.search(r"(?<![a-z])ai(?![a-z])", text) else "GAME"


def _page_url(source: OfficialHtmlSource, page: int) -> str:
    parts = urlsplit(source.list_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[source.page_param] = str(page)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def collect_official_html(db: Session, source: OfficialHtmlSource) -> SourceResult:
    try:
        entries_by_url = {}
        for page in range(source.first_page, source.first_page + source.max_pages):
            page_url = _page_url(source, page)
            for entry in PARSERS[source.parser](_fetch_html(page_url), page_url):
                entries_by_url.setdefault(entry["url"], entry)
        entries = list(entries_by_url.values())
    except Exception as exc:
        return SourceResult(source.name, 0, 0, 0, error=f"{type(exc).__name__}: {exc}")

    new_count = 0
    duplicates = 0
    for entry in entries:
        stored = db.scalar(select(Article).where(Article.url == entry["url"]))
        if not stored and entry.get("published_at"):
            # Policy Briefing republishes ministry releases with a new URL.
            # Title + publication date keeps the original source canonical.
            stored = db.scalar(select(Article).where(
                Article.title == entry["title"],
                Article.published_at == entry["published_at"],
            ))
        if stored:
            if source.parser == "mcst" and len((stored.summary or "").strip()) < 500:
                detail = _fetch_mcst_summary(entry["url"])
                if detail:
                    stored.summary = detail[:6000]
            duplicates += 1
            continue
        if source.parser == "mcst" and not entry["summary"]:
            entry["summary"] = _fetch_mcst_summary(entry["url"])
        if source.parser == "grac" and not entry["summary"]:
            entry["summary"] = _fetch_grac_summary(entry["url"])
        db.add(Article(
            source=source.name,
            source_type="official",
            category=_entry_category(source, entry),
            title=entry["title"][:500],
            url=entry["url"],
            published_at=entry["published_at"],
            summary=(entry["summary"][:6000] or None),
        ))
        new_count += 1
    db.commit()
    return SourceResult(source.name, len(entries), new_count, duplicates)


def collect_all_official_html(db: Session) -> list[SourceResult]:
    return [collect_official_html(db, source) for source in OFFICIAL_HTML_SOURCES]


# Naver's own editorial category listing (e.g. IT/과학 > 게임/리뷰) aggregates
# every partner press outlet Naver tagged under that category — including
# business dailies like 한국경제 that aren't in SOURCES. Comprehensive by
# category instead of by how well a hand-picked search-keyword list happens
# to match, at the cost of only ever seeing roughly the latest ~30 articles
# per section (the page doesn't paginate server-side), so this needs to be
# collected reasonably often to not miss anything.
@dataclass(frozen=True)
class NaverSectionSource:
    label: str
    url: str
    category: str
    # Naver has no dedicated AI section, so the AI lane uses the whole
    # IT/과학 category and needs a relevance check before storing —
    # otherwise every telecom-plan and phone-review story in IT/과학 floods
    # the classification queue too. None = no filter (게임/리뷰 is already
    # narrow enough on its own).
    relevance_terms: tuple[str, ...] | None = None


NAVER_SECTION_SOURCES: tuple[NaverSectionSource, ...] = (
    NaverSectionSource("게임/리뷰", "https://news.naver.com/breakingnews/section/105/229", "GAME"),
    NaverSectionSource(
        "IT/과학", "https://news.naver.com/section/105", "AI",
        relevance_terms=("인공지능", "생성형", "머신러닝", "딥러닝", "챗gpt", "llm", "에이전트"),
    ),
)

_RELATIVE_TIME_RE = re.compile(r"(\d+)\s*(분|시간|일)\s*전")
_AI_TOKEN_RE = re.compile(r"(?<![a-z0-9])ai(?![a-z0-9])")


def _relative_datetime(text: str) -> datetime | None:
    match = _RELATIVE_TIME_RE.search(text)
    if not match:
        return _date(text)
    amount, unit = int(match.group(1)), match.group(2)
    delta = {"분": timedelta(minutes=amount), "시간": timedelta(hours=amount), "일": timedelta(days=amount)}[unit]
    return datetime.now(timezone.utc) - delta


def _parse_naver_section(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for item in soup.select("li.sa_item"):
        link = item.select_one("a.sa_text_title[href]")
        title_node = item.select_one(".sa_text_strong")
        if not link or not title_node:
            continue
        lede_node = item.select_one(".sa_text_lede")
        press_node = item.select_one(".sa_text_press")
        time_node = item.select_one(".sa_text_datetime")
        entries.append({
            "title": title_node.get_text(" ", strip=True),
            "url": link["href"].strip(),
            "summary": lede_node.get_text(" ", strip=True) if lede_node else "",
            "published_at": _relative_datetime(time_node.get_text(" ", strip=True) if time_node else ""),
            "press": press_node.get_text(" ", strip=True) if press_node else "네이버뉴스",
        })
    return entries


def _passes_relevance(entry: dict, relevance_terms: tuple[str, ...] | None) -> bool:
    if relevance_terms is None:
        return True
    text = f" {entry['title']} {entry.get('summary', '')} ".casefold()
    return bool(_AI_TOKEN_RE.search(text)) or any(term in text for term in relevance_terms)


def collect_naver_section(db: Session, source: NaverSectionSource) -> SourceResult:
    try:
        entries = _parse_naver_section(_fetch_html(source.url))
    except Exception as exc:
        return SourceResult(f"NAVER 섹션 · {source.label}", 0, 0, 0, error=f"{type(exc).__name__}: {exc}")

    new_count = duplicates = 0
    seen_this_batch: set[str] = set()
    for entry in entries:
        if not _passes_relevance(entry, source.relevance_terms):
            continue
        # Naver's own listing repeats an entry (e.g. a "Hot" pick also shown
        # in the regular list) within a single fetch — the DB check alone
        # only catches rows already committed from a *previous* run, so a
        # same-batch repeat still hits the url column's unique constraint.
        if entry["url"] in seen_this_batch:
            duplicates += 1
            continue
        seen_this_batch.add(entry["url"])
        if db.scalar(select(Article.id).where(Article.url == entry["url"])):
            duplicates += 1
            continue
        db.add(Article(
            source=f"NAVER · {entry['press']}",
            source_type="media",
            category=source.category,
            title=entry["title"][:500],
            url=entry["url"],
            published_at=entry["published_at"],
            summary=(entry["summary"][:2000] or None),
        ))
        new_count += 1
    db.commit()
    return SourceResult(f"NAVER 섹션 · {source.label}", len(entries), new_count, duplicates)


def collect_all_naver_sections(db: Session) -> list[SourceResult]:
    return [collect_naver_section(db, source) for source in NAVER_SECTION_SOURCES]
