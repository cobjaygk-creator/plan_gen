"""Suggest plain-text editorial rules from repeated, explicit feedback."""
from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EditorialRule, Issue, IssueFeedback

MIN_DISTINCT_ISSUES = 3
_STOP_WORDS = {
    "게임", "업계", "신작", "관련", "공개", "출시", "대한", "통해", "위한", "주목",
    "있습니다", "한다", "했다", "이번", "오늘", "news", "game",
}


def _tokens(text: str) -> set[str]:
    return {
        token.casefold() for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", text)
        if token.casefold() not in _STOP_WORDS and not token.isdigit()
    }


def rule_suggestions(db: Session) -> list[dict]:
    rows = db.execute(
        select(IssueFeedback, Issue).join(Issue, Issue.id == IssueFeedback.issue_id)
        .where(IssueFeedback.verdict == "NOT_CORE")
    ).all()
    occurrences: dict[tuple[str, str], set[int]] = defaultdict(set)
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    for feedback, issue in rows:
        reason = feedback.reason or "OTHER"
        for token in _tokens(f"{issue.title} {issue.summary or ''}"):
            key = (reason, token)
            occurrences[key].add(issue.id)
            if issue.title not in examples[key] and len(examples[key]) < 3:
                examples[key].append(issue.title)
    active = {(rule.reason, rule.pattern.casefold()) for rule in db.execute(
        select(EditorialRule).where(EditorialRule.status == "ACTIVE")
    ).scalars().all()}
    suggestions = [{
        "reason": reason,
        "pattern": token,
        "issueCount": len(issue_ids),
        "examples": examples[(reason, token)],
    } for (reason, token), issue_ids in occurrences.items()
      if len(issue_ids) >= MIN_DISTINCT_ISSUES and (reason, token) not in active]
    return sorted(suggestions, key=lambda item: (-item["issueCount"], item["pattern"]))[:12]


def active_rule_match(db: Session, issue: Issue, member_titles: list[str]) -> EditorialRule | None:
    text = " ".join([issue.title, issue.summary or "", *member_titles]).casefold()
    return next((rule for rule in db.execute(
        select(EditorialRule).where(EditorialRule.status == "ACTIVE")
    ).scalars().all() if rule.pattern.casefold() in text), None)
