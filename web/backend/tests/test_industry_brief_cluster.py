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


def test_cluster_pending_does_not_starve_new_articles_behind_linked_rows(db_factory):
    db = db_factory()
    now = datetime.now(timezone.utc)
    linked = Article(
        source="Existing", source_type="media", category="GAME", title="기존 연결 기사",
        url="https://example.com/linked", is_relevant=True, importance_score=60,
        keywords="[]", entities="[]", classified_at=now, published_at=now,
    )
    fresh = Article(
        source="Fresh", source_type="media", category="GAME", title="새로 분류된 기사",
        url="https://example.com/fresh", is_relevant=True, importance_score=60,
        keywords="[]", entities="[]", classified_at=now, published_at=now,
    )
    db.add_all([linked, fresh])
    db.commit()
    db.refresh(linked)
    issue = Issue(
        category="GAME", title="기존 이슈", summary="", importance_score=60,
        lifecycle="EMERGING", first_seen_at=now, last_seen_at=now,
    )
    db.add(issue)
    db.commit()
    db.add(IssueArticle(issue_id=issue.id, article_id=linked.id))
    db.commit()

    result = cluster_pending(db, limit=1)

    assert result.new_issues == 1

def test_same_company_but_different_event_types_do_not_merge(db_factory):
    db = db_factory()
    _classified_article(
        db, "Acme launches a new AI model", "https://a.example.com/release",
        category="AI", source="Outlet A", keywords=["AI model"], entities=["Acme"],
    )
    _classified_article(
        db, "Acme reports quarterly earnings", "https://b.example.com/earnings",
        category="AI", source="Outlet B", keywords=["earnings"], entities=["Acme"],
    )
    result = cluster_pending(db)
    assert result.new_issues == 2
    assert db.query(Issue).count() == 2


def test_same_company_and_event_type_but_different_subjects_do_not_merge(db_factory):
    db = db_factory()
    _classified_article(
        db, "OpenAI partners with Disney to bring characters to Sora",
        "https://openai.com/disney", category="AI", source="OpenAI",
        source_type="official", keywords=["Sora", "Disney partnership"],
        entities=["OpenAI", "Disney", "Sora"],
    )
    _classified_article(
        db, "OpenAI partners with Cerebras for inference capacity",
        "https://openai.com/cerebras", category="AI", source="OpenAI",
        source_type="official", keywords=["Inference", "Cerebras partnership"],
        entities=["OpenAI", "Cerebras"],
    )

    result = cluster_pending(db)

    assert result.new_issues == 2
    assert result.appended == 0


def test_same_game_franchise_but_different_events_do_not_merge(db_factory):
    db = db_factory()
    _classified_article(
        db, "PUBG Mobile opens 2026 international esports tournament",
        "https://krafton.com/tournament", source="KRAFTON",
        source_type="official", keywords=["PMWC", "esports tournament"],
        entities=["KRAFTON", "PUBG Mobile", "PMWC"],
    )
    _classified_article(
        db, "PUBG Mobile launches Ferrari collaboration",
        "https://krafton.com/ferrari", source="KRAFTON",
        source_type="official", keywords=["Ferrari collaboration"],
        entities=["KRAFTON", "PUBG Mobile", "Ferrari"],
    )

    result = cluster_pending(db)

    assert result.new_issues == 2
    assert result.appended == 0


def test_same_official_source_separate_updates_do_not_merge(db_factory):
    db = db_factory()
    _classified_article(
        db, "Nexon updates Sudden Attack with a new battlefield",
        "https://nexon.example/battlefield", source="Nexon", source_type="official",
        keywords=["Sudden Attack", "Update"], entities=["Nexon", "Sudden Attack"],
    )
    _classified_article(
        db, "Nexon updates Sudden Attack with a new character",
        "https://nexon.example/character", source="Nexon", source_type="official",
        keywords=["Sudden Attack", "Update"], entities=["Nexon", "Sudden Attack"],
    )

    result = cluster_pending(db)

    assert result.new_issues == 2
    assert result.appended == 0


def test_intermediate_media_article_does_not_chain_distinct_same_source_events(db_factory):
    db = db_factory()
    shared_keywords = ["Crimson Desert", "Pearl Abyss", "Release"]
    shared_entities = ["Pearl Abyss", "Crimson Desert"]
    _classified_article(
        db, "Pearl Abyss presents Crimson Desert technology at Gamescom Dev",
        "https://inven.example/gamescom", source="Inven",
        keywords=shared_keywords, entities=shared_entities,
    )
    _classified_article(
        db, "Crimson Desert developer presents technology at Gamescom Dev 2026",
        "https://media.example/gamescom", source="Media Daily",
        keywords=shared_keywords, entities=shared_entities,
    )
    _classified_article(
        db, "Pearl Abyss publishes Crimson Desert post-launch update infographic",
        "https://inven.example/infographic", source="Inven",
        keywords=shared_keywords, entities=shared_entities,
    )

    result = cluster_pending(db)

    assert result.new_issues == 2
    assert result.appended == 1


def test_roundup_body_tags_do_not_merge_unrelated_headline(db_factory):
    db = db_factory()
    shared_keywords = ["AI semiconductor", "Intel", "investment", "rights offering"]
    shared_entities = ["Intel", "NVIDIA"]
    _classified_article(
        db, "Intel raises capital to fund AI semiconductor investment",
        "https://wire.example/intel", source="Wire One",
        keywords=shared_keywords, entities=shared_entities,
    )
    _classified_article(
        db, "US stocks close lower as oil prices rise",
        "https://market.example/closing", source="Market Daily",
        keywords=shared_keywords, entities=shared_entities,
    )

    result = cluster_pending(db)

    assert result.new_issues == 2
    assert result.appended == 0


def test_korean_company_name_alone_does_not_define_same_event(db_factory):
    db = db_factory()
    _classified_article(
        db, "구글, 국내 모바일 이용자 수에서 네이버 첫 추월",
        "https://usage.example/google", source="Usage News",
        keywords=["구글", "생성형 AI"], entities=["구글", "네이버"],
    )
    _classified_article(
        db, "KT, 구글과 AI 요금제 출시",
        "https://telecom.example/plan", source="Telecom News",
        keywords=["구글", "생성형 AI", "요금제"], entities=["KT", "구글"],
    )

    result = cluster_pending(db)

    assert result.new_issues == 2
    assert result.appended == 0
