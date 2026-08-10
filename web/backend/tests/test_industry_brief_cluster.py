import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.cluster import cluster_pending
from app.industry_brief.models import Article, Issue, IssueArticle


def _classified_article(
    db, title, url, category="GAME", source="Outlet A", source_type="media",
    keywords=None, entities=None, importance=60.0, published=None,
):
    a = Article(
        source=source, source_type=source_type, category=category, title=title, url=url,
        summary=f"{title} 관련 요약", is_relevant=True, importance_score=importance,
        keywords=json.dumps(keywords or [], ensure_ascii=False),
        entities=json.dumps(entities or [], ensure_ascii=False),
        classified_at=datetime.now(timezone.utc),
        published_at=published or datetime.now(timezone.utc),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_similar_articles_about_the_same_event_merge_into_one_issue(db_factory):
    db = db_factory()
    _classified_article(
        db, "OpenAI releases new coding agent", "https://a.example.com/1",
        source="Outlet A", keywords=["AI Coding Agent"], entities=["OpenAI"],
    )
    _classified_article(
        db, "OpenAI unveils new coding agent for developers", "https://b.example.com/1",
        source="Outlet B", keywords=["AI Coding Agent", "Developer Tools"], entities=["OpenAI"],
    )

    result = cluster_pending(db)

    assert result.new_issues == 1
    assert result.appended == 1
    issues = db.query(Issue).all()
    assert len(issues) == 1
    assert db.query(IssueArticle).filter(IssueArticle.issue_id == issues[0].id).count() == 2


def test_unrelated_articles_stay_as_separate_issues(db_factory):
    db = db_factory()
    _classified_article(
        db, "Take-Two reports Q1 earnings", "https://a.example.com/1",
        keywords=["Earnings"], entities=["Take-Two"],
    )
    _classified_article(
        db, "Roblox investors unhappy with new direction", "https://a.example.com/2",
        keywords=["Metaverse"], entities=["Roblox"],
    )

    result = cluster_pending(db)

    assert result.new_issues == 2
    assert result.appended == 0
    assert db.query(Issue).count() == 2


def test_same_topic_different_category_never_merges(db_factory):
    db = db_factory()
    _classified_article(
        db, "AI model update announced", "https://a.example.com/1", category="AI",
        keywords=["AI Agent"], entities=["OpenAI"],
    )
    _classified_article(
        db, "AI model update announced", "https://a.example.com/2", category="GAME",
        keywords=["AI Agent"], entities=["OpenAI"],
    )

    result = cluster_pending(db)

    assert result.new_issues == 2
    issues = db.query(Issue).all()
    assert {i.category for i in issues} == {"AI", "GAME"}


def test_confidence_reflects_distinct_sources_and_official_presence(db_factory):
    db = db_factory()
    _classified_article(
        db, "Anthropic ships new safety framework", "https://a.example.com/1",
        source="Anthropic", source_type="official", keywords=["AI Safety"], entities=["Anthropic"],
    )
    cluster_pending(db)
    issue = db.query(Issue).first()
    assert issue.confidence == "WEAK"  # 1 source, even if official

    _classified_article(
        db, "Anthropic unveils new AI safety framework", "https://b.example.com/1",
        source="Outlet B", source_type="media", keywords=["AI Safety"], entities=["Anthropic"],
    )
    _classified_article(
        db, "Anthropic's new safety framework explained", "https://c.example.com/1",
        source="Outlet C", source_type="media", keywords=["AI Safety"], entities=["Anthropic"],
    )
    cluster_pending(db)
    db.refresh(issue)
    assert issue.confidence == "STRONG"  # 3 sources incl. 1 official


def test_already_clustered_articles_are_not_reprocessed(db_factory):
    db = db_factory()
    _classified_article(db, "Game news", "https://a.example.com/1", keywords=["Live Service"])
    first = cluster_pending(db)
    second = cluster_pending(db)

    assert first.new_issues == 1
    assert second.new_issues == 0
    assert second.appended == 0
    assert db.query(Issue).count() == 1


def test_unclassified_or_irrelevant_articles_are_ignored(db_factory):
    db = db_factory()
    db.add(Article(source="A", source_type="media", category="GAME", title="아직 미분류", url="https://a.example.com/1"))
    db.add(Article(
        source="A", source_type="media", category="GAME", title="관련없음", url="https://a.example.com/2",
        is_relevant=False, classified_at=datetime.now(timezone.utc),
    ))
    db.commit()

    result = cluster_pending(db)

    assert result.new_issues == 0
    assert db.query(Issue).count() == 0
