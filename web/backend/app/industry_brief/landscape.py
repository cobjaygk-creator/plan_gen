"""Long-horizon industry map derived from the planning team reference scrape."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article, ArticleAnalysis, ReferenceArticle

ISSUE_LABELS = {
    "game_ai_distribution": "게임 AI의 유통 단계 진입",
    "game_ai_talent": "AI 시대 게임 인력·역량 변화",
    "game_ai_trust": "게임 AI의 신뢰·수용성 과제",
    "game_ai_gameplay": "AI 게임플레이·이용자 경험",
    "game_ai_production": "게임 제작·운영 AI 확산",
    "game_global_expansion": "K게임의 글로벌·중국 전략",
    "game_policy": "게임 정책·규제 환경",
    "game_platform": "게임 플랫폼·유통 구조",
    "game_market": "게임 시장·투자·조직 변화",
    "game_liveops": "신작·라이브 서비스 흐름",
    "game_ip_fandom": "IP·팬덤 확장",
    "game_content": "신작·IP·라이브서비스 변화",
    "ai_global_competition": "AI 글로벌 경쟁과 주권",
    "ai_policy": "AI 규제·안전 환경",
    "ai_platform": "AI 제품·플랫폼 경쟁",
    "ai_market": "AI 투자·인프라·수익성",
    "ai_infrastructure": "AI 인프라·컴퓨팅",
    "ai_work_agents": "AI 에이전트·업무 자동화",
    "ai_adoption": "AI 업무 도입·자동화 확산",
}

DOMAIN_LABELS = {"GAME": "GAME", "AI": "AI", "GAME_AI": "GAME × AI"}


def build_landscape(db: Session, days: int = 30) -> dict:
    """Rank long-horizon issues using auditable current-signal evidence."""
    references = db.execute(select(ReferenceArticle)).scalars().all()
    groups: dict[str, list[ReferenceArticle]] = defaultdict(list)
    for reference in references:
        groups[reference.primary_domain].append(reference)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    seven_day_cutoff = now - timedelta(days=7)
    live_rows = db.execute(
        select(Article, ArticleAnalysis)
        .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
        .where(Article.classified_at.is_not(None), Article.classified_at >= cutoff)
    ).all()
    live_stats: dict[str, dict] = defaultdict(lambda: {
        "recent30": 0, "recent7": 0, "sources": set(), "official": 0,
    })
    for article, analysis in live_rows:
        classified_at = article.classified_at
        if classified_at and classified_at.tzinfo is None:
            classified_at = classified_at.replace(tzinfo=timezone.utc)
        for key in json.loads(analysis.reference_issue_keys or "[]"):
            stat = live_stats[key]
            stat["recent30"] += 1
            if classified_at and classified_at >= seven_day_cutoff:
                stat["recent7"] += 1
            stat["sources"].add(article.source)
            if article.source_type == "official":
                stat["official"] += 1

    domains = []
    for domain in ("GAME", "AI", "GAME_AI"):
        issue_groups: dict[str, list[ReferenceArticle]] = defaultdict(list)
        for reference in groups[domain]:
            issue_groups[reference.issue_key or "unknown"].append(reference)
        issues = []
        for key, items in issue_groups.items():
            axes = Counter(axis for item in items for axis in json.loads(item.axes or "[]"))
            dates = [item.observed_at for item in items if item.observed_at]
            months = {date.strftime("%Y-%m") for date in dates}
            stat = live_stats[key]
            source_count = len(stat["sources"])
            score = min(len(items), 30) / 30 * 20
            score += min(len(months), 6) / 6 * 15
            score += min(stat["recent30"], 10) / 10 * 30
            score += min(stat["recent7"], 5) / 5 * 15
            score += min(source_count, 4) / 4 * 10
            score += min(stat["official"], 2) / 2 * 5
            if domain == "GAME_AI":
                score += 5
            reasons = []
            if stat["recent7"]:
                reasons.append(f"최근 7일 {stat['recent7']}건")
            if source_count >= 2:
                reasons.append(f"{source_count}개 매체")
            if len(months) >= 2:
                reasons.append(f"올해 {len(months)}개월 관찰")
            if stat["official"]:
                reasons.append(f"공식 발표 {stat['official']}건")
            if domain == "GAME_AI":
                reasons.append("게임·AI 교차 이슈")
            issues.append({
                "key": key,
                "title": ISSUE_LABELS.get(key, key),
                "referenceCount": len(items),
                "recentArticleCount": stat["recent30"],
                "firstObservedAt": min(dates).date().isoformat() if dates else None,
                "axes": [axis for axis, _ in axes.most_common(3)],
                "priorityScore": round(score),
                "priorityReasons": reasons[:3],
            })
        issues.sort(key=lambda item: (item["priorityScore"], item["recentArticleCount"], item["referenceCount"]), reverse=True)
        domains.append({"key": domain, "label": DOMAIN_LABELS[domain], "issues": issues[:5]})
    return {"referenceArticleCount": len(references), "domains": domains}

def build_issue_detail(db: Session, issue_key: str, days: int = 30) -> dict:
    """Return the auditable evidence behind one long-horizon issue map item."""
    references = list(
        db.execute(
            select(ReferenceArticle)
            .where(ReferenceArticle.issue_key == issue_key)
            .order_by(ReferenceArticle.observed_at.desc().nulls_last())
        ).scalars().all()
    )
    if not references:
        raise HTTPException(status_code=404, detail="Unknown industry-map issue.")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    live_rows = db.execute(
        select(Article, ArticleAnalysis)
        .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
        .where(Article.classified_at.is_not(None), Article.classified_at >= cutoff)
        .order_by(Article.published_at.desc().nulls_last(), Article.collected_at.desc())
    ).all()
    live = []
    for article, analysis in live_rows:
        if issue_key not in json.loads(analysis.reference_issue_keys or "[]"):
            continue
        live.append({
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "publishedAt": (article.published_at or article.collected_at).date().isoformat(),
        })

    dates = [reference.observed_at for reference in references if reference.observed_at]
    timeline_counts = Counter(date.strftime("%Y-%m") for date in dates)
    timeline = [{"month": month, "count": count} for month, count in sorted(timeline_counts.items())]
    first_date = min(dates).date().isoformat() if dates else None
    last_date = max(dates).date().isoformat() if dates else None
    if first_date and last_date:
        change_summary = f"{first_date}부터 {last_date}까지 기준선 기사 {len(references)}건이 축적됐고, 최근 {days}일 분석에서 {len(live)}건이 다시 연결됐습니다."
    else:
        change_summary = f"기준선 기사 {len(references)}건 중 최근 {days}일 분석에서 {len(live)}건이 연결됐습니다."
    return {
        "key": issue_key,
        "title": ISSUE_LABELS.get(issue_key, issue_key),
        "historicalStart": min(dates).date().isoformat() if dates else None,
        "historicalCount": len(references),
        "recentCount": len(live),
        "historicalEnd": last_date,
        "changeSummary": change_summary,
        "timeline": timeline,
        "historicalArticles": [
            {
                "title": reference.title,
                "url": reference.url,
                "source": reference.source,
                "publishedAt": reference.observed_at.date().isoformat() if reference.observed_at else None,
            }
            for reference in references[:20]
        ],
        "recentArticles": live[:20],
    }