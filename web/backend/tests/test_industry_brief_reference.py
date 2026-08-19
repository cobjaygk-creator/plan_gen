import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.models import Article, ArticleAnalysis, ReferenceArticle
from app.industry_brief.reference import analyze_live_article, import_reference_scrape, parse_reference_scrape


def _scrape(tmp_path):
    path = tmp_path / "scrape.txt"
    path.write_text(
        "원스토어, AI 창작 게임 전문관 오픈\n"
        "https://www.inven.co.kr/webzine/news/?news=1\n"
        "김주영\t08-10 07:52\n\n"
        "중국 판호 확대, K게임 글로벌 진출 기대\n"
        "https://www.gamemeca.com/view.php?gid=2\n"
        "김행렬\t07-10 10:14\n",
        encoding="utf-8",
    )
    return path


def test_parse_reference_scrape_classifies_game_ai_and_global(tmp_path):
    records = parse_reference_scrape(_scrape(tmp_path))

    assert len(records) == 2
    assert records[0].primary_domain == "GAME_AI"
    assert "PLATFORM" in records[0].axes
    assert records[0].issue_key == "game_ai_distribution"
    assert records[1].primary_domain == "GAME"
    assert "GLOBAL" in records[1].axes


def test_import_reference_scrape_is_idempotent(db_factory, tmp_path):
    db = db_factory()
    path = _scrape(tmp_path)

    assert import_reference_scrape(db, path) == (2, 0)
    assert import_reference_scrape(db, path) == (0, 2)
    assert db.query(ReferenceArticle).count() == 2


def test_live_article_connects_to_matching_reference_issue(db_factory, tmp_path):
    db = db_factory()
    import_reference_scrape(db, _scrape(tmp_path))
    article = Article(
        source="게임메카", source_type="media", category="GAME",
        title="게임 AI 플랫폼과 유통 전략 확대", url="https://example.com/live",
        summary="AI 창작 게임을 플랫폼에서 유통하는 움직임", is_relevant=True,
        classified_at=datetime.now(timezone.utc),
    )
    db.add(article)
    db.commit()
    db.refresh(article)

    analysis = analyze_live_article(db, article)
    db.commit()

    assert analysis.primary_domain == "GAME_AI"
    assert "PLATFORM" in json.loads(analysis.axes)
    assert "game_ai_distribution" in json.loads(analysis.reference_issue_keys)
    assert db.query(ArticleAnalysis).count() == 1