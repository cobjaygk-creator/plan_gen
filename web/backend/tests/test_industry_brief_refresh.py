from types import SimpleNamespace

from app.industry_brief.refresh import refresh_industry_brief


def test_refresh_runs_every_stage_and_returns_counts(db_factory, monkeypatch):
    db = db_factory()
    calls = []

    def fake_collect(_db):
        calls.append("collect")
        return SimpleNamespace(total_new=9)

    def fake_classify(_db, limit):
        calls.append(("classify", limit))
        return 5

    def fake_cluster(_db):
        calls.append("cluster")
        return SimpleNamespace(new_issues=2, appended=3)

    def fake_synthesize(_db):
        calls.append("synthesize")
        return SimpleNamespace(id=42)

    monkeypatch.setattr("app.industry_brief.refresh.collect_all", fake_collect)
    monkeypatch.setattr("app.industry_brief.refresh.classify_pending", fake_classify)
    monkeypatch.setattr("app.industry_brief.refresh.cluster_pending", fake_cluster)
    monkeypatch.setattr("app.industry_brief.refresh.generate_daily_brief", fake_synthesize)

    result = refresh_industry_brief(db, classify_limit=12)

    assert calls == ["collect", ("classify", 12), "cluster", "synthesize"]
    assert result.collected == 9
    assert result.classified == 5
    assert result.new_issues == 2
    assert result.appended_to_issues == 3
    assert result.brief_id == 42