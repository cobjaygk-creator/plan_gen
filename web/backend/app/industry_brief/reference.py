"""Historical planning-team scrape baseline for Industry Brief.

The baseline is deliberately parsed with deterministic rules first. It gives
new daily articles a stable industry-map vocabulary without requiring an AI
call for every historical item.
"""
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article, ArticleAnalysis, ReferenceArticle

_URL = re.compile(r"^https?://")
_AUTHOR_DATE = re.compile(r"(김행렬|김주영|김성태).*?(\d{2})-(\d{2})")

_AXIS_RULES = {
    "MARKET": ("실적", "매출", "투자", "인수", "합병", "펀드", "주가", "감원", "상장"),
    "CONTENT": ("신작", "출시", "업데이트", "ip", "리메이크", "클래식", "mmorpg"),
    "PLATFORM": ("스팀", "앱스토어", "원스토어", "콘솔", "xbox", "닌텐도", "플랫폼", "클라우드"),
    "GLOBAL": ("중국", "판호", "글로벌", "해외", "북미", "유럽", "사우디"),
    "USER": ("이용자", "유저", "팬덤", "쇼츠", "고령", "방치형", "팝업", "콜라보"),
    "POLICY": ("규제", "법", "정부", "문체부", "공정위", "게임위", "세제", "저작권"),
    "TECH": ("ai", "인공지능", "llm", "에이전트", "생성형", "오픈소스"),
    "OPERATIONS": ("qa", "운영", "부정행위", "보안", "해킹", "디도스", "안전"),
    "INFRA": ("gpu", "반도체", "메모리", "d램", "데이터센터", "전력"),
    "TALENT": ("채용", "인재", "개발자", "조직", "노조", "인력"),
}

_EVENT_RULES = {
    "REGULATION": ("규제", "법", "정부", "공정위", "게임위", "판호", "세제"),
    "INVESTMENT": ("투자", "인수", "합병", "펀드", "주가", "실적", "매출"),
    "PRODUCT": ("신작", "출시", "공개", "업데이트", "출시"),
    "PLATFORM": ("스팀", "앱스토어", "원스토어", "플랫폼", "콘솔"),
    "ORGANIZATION": ("채용", "감원", "조직", "스튜디오", "노조"),
}


def _labels(text: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
    text = text.casefold()
    return [label for label, terms in rules.items() if any(term.casefold() in text for term in terms)]


def _domain(text: str) -> tuple[str, list[str]]:
    value = text.casefold()
    ai = any(term in value for term in ("ai", "인공지능", "llm", "에이전트", "생성형"))
    game = any(term in value for term in ("게임", "넥슨", "크래프톤", "엔씨", "스팀", "콘솔", "판호", "mmorpg"))
    if ai and game:
        return "GAME_AI", ["GAME", "AI"]
    if ai:
        return "AI", []
    return "GAME", []


def _issue_key(domain: str, axes: list[str], text: str = "") -> str:
    """Map evidence to planning-relevant, mutually useful issue lanes."""
    value = text.casefold()
    if domain == "GAME_AI":
        if any(term in value for term in ("npc", "플레이", "이용자", "유저", "대화", "채팅")):
            return "game_ai_gameplay"
        if any(term in value for term in ("저작권", "법률", "안전", "신뢰", "표시", "규정", "규제")):
            return "game_ai_trust"
        if "TALENT" in axes:
            return "game_ai_talent"
        if "PLATFORM" in axes:
            return "game_ai_distribution"
        return "game_ai_production"
    if domain == "GAME":
        if "GLOBAL" in axes:
            return "game_global_expansion"
        if "POLICY" in axes:
            return "game_policy"
        if "PLATFORM" in axes:
            return "game_platform"
        if "MARKET" in axes:
            return "game_market"
        if any(term in value for term in ("ip", "캐릭터", "콜라보", "팬", "굿즈")):
            return "game_ip_fandom"
        if any(term in value for term in ("신작", "출시", "업데이트", "라이브", "mmorpg")):
            return "game_liveops"
        return "game_content"
    if "GLOBAL" in axes:
        return "ai_global_competition"
    if "POLICY" in axes:
        return "ai_policy"
    if "PLATFORM" in axes:
        return "ai_platform"
    if "MARKET" in axes:
        return "ai_market"
    if "INFRA" in axes or any(term in value for term in ("gpu", "데이터센터", "반도체", "전력")):
        return "ai_infrastructure"
    if any(term in value for term in ("에이전트", "업무 자동화", "자동화", "copilot")):
        return "ai_work_agents"
    return "ai_adoption"


def reclassify_reference_articles(db: Session) -> tuple[int, int]:
    """Apply the current issue taxonomy to imported baseline records in-place."""
    changed = total = 0
    for article in db.execute(select(ReferenceArticle)).scalars():
        total += 1
        combined = f"{article.title}\n{article.raw_note or ''}"
        domain, secondary = _domain(combined)
        axes = _labels(combined, _AXIS_RULES)
        event_types = _labels(combined, _EVENT_RULES)
        issue_key = _issue_key(domain, axes, combined)
        if (article.primary_domain, article.secondary_domains, article.axes, article.event_type, article.issue_key) != (
            domain, json.dumps(secondary, ensure_ascii=False), json.dumps(axes, ensure_ascii=False),
            event_types[0] if event_types else None, issue_key,
        ):
            article.primary_domain = domain
            article.secondary_domains = json.dumps(secondary, ensure_ascii=False)
            article.axes = json.dumps(axes, ensure_ascii=False)
            article.event_type = event_types[0] if event_types else None
            article.issue_key = issue_key
            changed += 1
    db.commit()
    return changed, total

@dataclass(frozen=True)
class ReferenceRecord:
    title: str
    url: str | None
    source: str | None
    observed_at: datetime | None
    curator: str | None
    raw_note: str | None
    primary_domain: str
    secondary_domains: list[str]
    axes: list[str]
    event_type: str | None
    issue_key: str


def parse_reference_scrape(path: Path) -> list[ReferenceRecord]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    records: list[ReferenceRecord] = []
    for index, line in enumerate(lines):
        if not _URL.match(line):
            continue
        title = next((lines[i].lstrip("* ") for i in range(index - 1, max(index - 5, -1), -1)
                      if lines[i] and not _URL.match(lines[i]) and not lines[i].isdigit()), "")
        if not title:
            continue
        metadata = next((lines[i] for i in range(index + 1, min(index + 6, len(lines))) if _AUTHOR_DATE.search(lines[i])), "")
        match = _AUTHOR_DATE.search(metadata)
        curator, observed_at = None, None
        if match:
            curator = match.group(1)
            observed_at = datetime(2026, int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc)
        source = urlparse(line).netloc.removeprefix("www.") or None
        note = None
        if index >= 2 and lines[index - 2] and not lines[index - 2].isdigit():
            note = lines[index - 2][:2000]
        combined = f"{title}\n{note or ''}"
        domain, secondary = _domain(combined)
        axes = _labels(combined, _AXIS_RULES)
        event_types = _labels(combined, _EVENT_RULES)
        records.append(ReferenceRecord(title, line, source, observed_at, curator, note, domain, secondary, axes,
                                       event_types[0] if event_types else None, _issue_key(domain, axes, combined)))
    return records


def import_reference_scrape(db: Session, path: Path) -> tuple[int, int]:
    created = existing = 0
    seen_fingerprints: set[str] = set()
    for record in parse_reference_scrape(path):
        fingerprint = hashlib.sha256(f"{record.title}|{record.url or ''}".encode("utf-8")).hexdigest()
        if fingerprint in seen_fingerprints or db.execute(
            select(ReferenceArticle.id).where(ReferenceArticle.fingerprint == fingerprint)
        ).first():
            existing += 1
            continue
        seen_fingerprints.add(fingerprint)
        db.add(ReferenceArticle(
            fingerprint=fingerprint, title=record.title, url=record.url, source=record.source,
            observed_at=record.observed_at, curator=record.curator, raw_note=record.raw_note,
            primary_domain=record.primary_domain, secondary_domains=json.dumps(record.secondary_domains, ensure_ascii=False),
            axes=json.dumps(record.axes, ensure_ascii=False), event_type=record.event_type, issue_key=record.issue_key,
        ))
        created += 1
    db.commit()
    return created, existing

def analyze_live_article(db: Session, article: Article) -> ArticleAnalysis:
    """Attach the live article to the team’s historical observation map.

    Deterministic by design: it is a cheap post-classification enrichment and
    never changes the original relevance/category decision.
    """
    combined = f"{article.title}\n{article.summary or ''}"
    domain, secondary = _domain(combined)
    axes = _labels(combined, _AXIS_RULES)
    event_types = _labels(combined, _EVENT_RULES)
    references = db.execute(select(ReferenceArticle)).scalars().all()
    primary_issue_key = _issue_key(domain, axes, combined)
    known_issue_keys = {reference.issue_key for reference in references if reference.primary_domain == domain}
    # One article maps to its best-fitting lane.  Broad shared axes (for example
    # TECH) must not make the same article inflate several unrelated issues.
    issue_keys = [primary_issue_key] if primary_issue_key in known_issue_keys else []
    existing = db.execute(select(ArticleAnalysis).where(ArticleAnalysis.article_id == article.id)).scalar_one_or_none()
    analysis = existing or ArticleAnalysis(article_id=article.id, primary_domain=domain)
    analysis.primary_domain = domain
    analysis.secondary_domains = json.dumps(secondary, ensure_ascii=False)
    analysis.axes = json.dumps(axes, ensure_ascii=False)
    analysis.event_type = event_types[0] if event_types else None
    analysis.change_type = "NEW" if not issue_keys else "GROWING"
    analysis.impact_scope = "BROAD" if len(axes) >= 2 else "FOCUSED"
    analysis.impact_horizon = "LONG" if any(axis in axes for axis in ("POLICY", "MARKET", "INFRA", "GLOBAL")) else "MEDIUM"
    analysis.structural_impact_score = min(100.0, 20.0 + len(axes) * 15.0 + (20.0 if domain == "GAME_AI" else 0.0))
    analysis.novelty_score = 30.0 if not issue_keys else 10.0
    analysis.reference_issue_keys = json.dumps(issue_keys, ensure_ascii=False)
    if existing is None:
        db.add(analysis)
    return analysis