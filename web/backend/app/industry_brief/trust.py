"""Auditable evidence quality rules for Industry Brief only."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlparse
from .models import Article

ESTABLISHED_MEDIA = {
    "GamesIndustry.biz", "PC Gamer", "TechCrunch", "The Verge", "Ars Technica",
    "인벤", "게임메카", "AI타임스", "전자신문 AI",
}

ESTABLISHED_DOMAINS = {
    "yna.co.kr", "newsis.com", "etnews.com", "zdnet.co.kr", "donga.com",
    "chosun.com", "joongang.co.kr", "hani.co.kr", "khan.co.kr", "mk.co.kr",
    "hankyung.com", "businesspost.co.kr", "bloter.net", "digitaltoday.co.kr",
    # Major general/economic newsrooms present in the Korean news-big-data ecosystem.
    "news1.kr", "edaily.co.kr", "mt.co.kr", "asiae.co.kr", "sedaily.com",
    "heraldcorp.com", "etoday.co.kr", "dt.co.kr", "newspim.com", "ajunews.com",
    "inews24.com", "ytn.co.kr", "sbs.co.kr", "wowtv.co.kr", "kukinews.com",
    "thebell.co.kr", "sportschosun.com",
    # Established specialist publications used by this brief's GAME/AI coverage.
    "inven.co.kr", "gamemeca.com", "thisisgame.com", "aitimes.com",
    "epnc.co.kr", "datanet.co.kr",
}

# First-party corporate newsrooms. Articles discovered through NAVER or another
# media collector still count as primary evidence when their canonical URL is
# hosted on one of these verified company domains.
OFFICIAL_DOMAINS = {
    "openai.com", "nvidia.com", "news.samsung.com", "krafton.com", "nc.com",
}

@dataclass(frozen=True)
class EvidenceQuality:
    verification_status: str
    independent_sources: int
    official_count: int
    established_media_count: int
    discovery_count: int
    confidence: str
    synthesis_eligible: bool
    reason: str


def source_key(article: Article) -> str:
    if article.source.startswith("NAVER "):
        domain=urlparse(article.url).netloc.lower().removeprefix("www.")
        return domain or article.source.casefold()
    return article.source.strip().casefold()


def source_tier(article: Article) -> str:
    if article.source_type == "official":
        return "PRIMARY"
    domain=urlparse(article.url).netloc.lower().removeprefix("www.")
    if any(domain == known or domain.endswith("." + known) for known in OFFICIAL_DOMAINS):
        return "PRIMARY"
    if article.source in ESTABLISHED_MEDIA:
        return "ESTABLISHED_MEDIA"
    if article.source.startswith("NAVER "):
        if any(domain == known or domain.endswith("." + known) for known in ESTABLISHED_DOMAINS):
            return "ESTABLISHED_MEDIA"
        return "DISCOVERY_MEDIA"
    return "OTHER_MEDIA"


def evaluate_evidence(articles: list[Article]) -> EvidenceQuality:
    independent=len({source_key(article) for article in articles})
    tiers=Counter(source_tier(article) for article in articles)
    official=tiers["PRIMARY"]
    established=tiers["ESTABLISHED_MEDIA"]
    discovery=tiers["DISCOVERY_MEDIA"]
    trusted_count=official + established
    if independent >= 3 and trusted_count >= 1:
        status="CORROBORATED"; confidence="STRONG"; eligible=True
    elif independent >= 2 and trusted_count >= 1:
        status="CORROBORATED"; confidence="MODERATE"; eligible=True
    elif official >= 1:
        status="OFFICIAL_ONLY"; confidence="MODERATE"; eligible=True
    elif independent >= 2:
        status="DISCOVERY_ONLY"; confidence="WEAK"; eligible=False
    else:
        status="SINGLE_SOURCE"; confidence="WEAK"; eligible=False
    reasons={
        "CORROBORATED": "Independent reporting and at least one established or primary source corroborate this event.",
        "OFFICIAL_ONLY": "Confirmed by a primary source; independent reporting is still limited.",
        "DISCOVERY_ONLY": "Multiple discovery results exist, but no established or primary source has been confirmed.",
        "SINGLE_SOURCE": "Only one non-primary source is available; additional confirmation is required.",
    }
    return EvidenceQuality(status,independent,official,established,discovery,confidence,eligible,reasons[status])


def trusted_issue_score(importance: float | None, articles: list[Article]) -> float:
    quality=evaluate_evidence(articles)
    score=importance or 0.0
    if quality.verification_status == "SINGLE_SOURCE":
        return min(score, 55.0)
    if quality.verification_status == "OFFICIAL_ONLY":
        return min(score, 78.0)
    return min(100.0, score + min(12.0, (quality.independent_sources - 1) * 4.0))
