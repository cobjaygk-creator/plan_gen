"""On-demand refresh pipeline for the isolated Industry Brief feature.

The pipeline is deliberately explicit: collection, limited AI classification,
heuristic clustering, then grounded synthesis.  It is only invoked through
Industry Brief's authenticated refresh endpoint; no existing plan-generation
flow or database tables are involved.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .classifier import classify_pending
from .cluster import cluster_pending
from .collector import collect_all
from .synthesis import generate_daily_brief

# A refresh is a "what changed since the last view" action, not a backlog
# cleanup.  The classifier already prioritizes fresh Korean and high-value
# articles, so this keeps latency and API cost bounded while surfacing new news.
REFRESH_CLASSIFY_LIMIT = 80


@dataclass(frozen=True)
class RefreshResult:
    collected: int
    classified: int
    new_issues: int
    appended_to_issues: int
    brief_id: int


def refresh_industry_brief(db: Session, classify_limit: int = REFRESH_CLASSIFY_LIMIT) -> RefreshResult:
    collected = collect_all(db)
    classified = classify_pending(db, limit=classify_limit)
    clustered = cluster_pending(db)
    brief = generate_daily_brief(db)
    return RefreshResult(
        collected=collected.total_new,
        classified=classified,
        new_issues=clustered.new_issues,
        appended_to_issues=clustered.appended,
        brief_id=brief.id,
    )