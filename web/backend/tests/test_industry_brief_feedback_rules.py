from datetime import datetime, timezone

from app.industry_brief.feedback_rules import _tokens, rule_suggestions
from app.industry_brief.models import Issue, IssueFeedback
from app.industry_brief.routes import _preview_risk


def test_rule_tokenizer_removes_generic_words():
    tokens = _tokens("게임 업계 신작 배우 비하인드 영상 공개")
    assert "게임" not in tokens
    assert "공개" not in tokens
    assert "배우" in tokens
    assert "비하인드" in tokens


def test_rule_is_suggested_only_after_three_distinct_feedback_issues(db_factory):
    db = db_factory()
    now = datetime.now(timezone.utc)
    for index in range(3):
        issue = Issue(category="GAME", title=f"배우 참여 비하인드 영상 {index}", summary="배우 홍보 영상",
                      importance_score=50, confidence="WEAK", lifecycle="EMERGING",
                      first_seen_at=now, last_seen_at=now)
        db.add(issue); db.flush()
        db.add(IssueFeedback(issue_id=issue.id, user_id=1, verdict="NOT_CORE", reason="PROMOTIONAL"))
    db.commit()

    suggestions = rule_suggestions(db)

    actor = next(item for item in suggestions if item["pattern"] == "배우")
    assert actor["reason"] == "PROMOTIONAL"
    assert actor["issueCount"] == 3


def test_rule_preview_warns_for_broad_core_impact():
    level, warnings = _preview_risk(issue_count=4, article_count=12, core_count=3)
    assert level == "CAUTION"
    assert "핵심 후보 3개" in warnings[0]
