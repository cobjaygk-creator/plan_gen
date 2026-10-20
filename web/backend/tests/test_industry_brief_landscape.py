import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.landscape import build_issue_detail, build_landscape
from app.industry_brief.reference import import_reference_scrape
from app.industry_brief.models import ReferenceArticle
from sqlalchemy import select


def test_landscape_groups_reference_articles_by_three_domains(db_factory, tmp_path):
    path = tmp_path / "reference.txt"
    path.write_text(
        "게임 AI 플랫폼 오픈\nhttps://example.com/1\n김주영\t08-10 07:52\n\n"
        "AI 에이전트 기업 도입\nhttps://example.com/2\n김성태\t08-09 07:52\n\n"
        "중국 판호 확대\nhttps://example.com/3\n김행렬\t08-08 07:52\n",
        encoding="utf-8",
    )
    db = db_factory()
    import_reference_scrape(db, path)

    landscape = build_landscape(db)

    assert landscape["referenceArticleCount"] == 3
    assert [domain["key"] for domain in landscape["domains"]] == ["GAME", "AI", "GAME_AI"]
    assert landscape["domains"][0]["issues"]
    assert landscape["domains"][1]["issues"]
    assert landscape["domains"][2]["issues"]

def test_issue_detail_returns_historical_and_recent_evidence(db_factory, tmp_path):
    from datetime import datetime, timezone
    from app.industry_brief.models import Article
    from app.industry_brief.reference import analyze_live_article

    path = tmp_path / "reference.txt"
    path.write_text(
        "AI platform expansion\nhttps://example.com/reference\nKim 08-10 07:52\n",
        encoding="utf-8",
    )
    db = db_factory()
    import_reference_scrape(db, path)
    reference = db.execute(select(ReferenceArticle)).scalar_one()
    article = Article(
        source="Outlet", source_type="media", category="AI", title="AI platform expansion",
        url="https://example.com/live", summary="", classified_at=datetime.now(timezone.utc),
    )
    db.add(article)
    db.flush()
    analyze_live_article(db, article)
    db.commit()

    detail = build_issue_detail(db, reference.issue_key)

    assert detail["historicalCount"] == 1
    assert detail["historicalArticles"][0]["url"] == "https://example.com/reference"
    assert detail["recentCount"] == 1
    assert detail["recentArticles"][0]["url"] == "https://example.com/live"


def test_observation_timeline_includes_automated_articles_and_empty_current_month(db_factory, tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from app.industry_brief import landscape
    from app.industry_brief.models import Article
    from app.industry_brief.reference import analyze_live_article

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 21, tzinfo=timezone.utc)

    monkeypatch.setattr(landscape, "datetime", Clock)
    path = tmp_path / "reference.txt"
    path.write_text("AI platform expansion\nhttps://example.com/reference\nKim 08-10 07:52\n", encoding="utf-8")
    db = db_factory()
    import_reference_scrape(db, path)
    reference = db.execute(select(ReferenceArticle)).scalar_one()
    reference.observed_at = datetime(2026, 8, 10, tzinfo=timezone.utc)
    db.add(article := Article(
        source="Outlet", source_type="media", category="AI", title="AI platform expansion",
        url="https://example.com/september", summary="",
        published_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        classified_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    ))
    db.flush()
    analyze_live_article(db, article)
    db.commit()
    detail = build_issue_detail(db, reference.issue_key)
    months = {point["month"]: point for point in detail["timeline"]}
    assert months["2026-08"]["referenceCount"] == 1
    assert months["2026-09"]["analyzedCount"] == 1
    assert months["2026-10"]["count"] == 0
    assert detail["recentCount"] == 0
    assert detail["historicalEnd"] == "2026-08-10"
    assert "2026-09-02" in detail["changeSummary"]
    assert "최신 동향을 판단할 수 없습니다" in detail["changeSummary"]


def test_unknown_map_issue_returns_404(db_factory):
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        build_issue_detail(db_factory(), "missing")
    assert exc.value.status_code == 404
