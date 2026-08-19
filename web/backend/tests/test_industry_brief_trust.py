from app.industry_brief.models import Article
from app.industry_brief.trust import evaluate_evidence, source_tier


def article(source, url, source_type="media"):
    return Article(source=source, source_type=source_type, category="AI", title="t", url=url)


def test_established_naver_origin_is_trusted_media():
    row=article("NAVER · zdnet.co.kr", "https://zdnet.co.kr/view/?no=1")
    assert source_tier(row) == "ESTABLISHED_MEDIA"


def test_verified_game_and_ai_specialist_domains_are_trusted_media():
    for domain in ("inven.co.kr", "gamemeca.com", "thisisgame.com", "aitimes.com"):
        row = article(f"NAVER · {domain}", f"https://www.{domain}/news/1")
        assert source_tier(row) == "ESTABLISHED_MEDIA"


def test_subdomain_of_verified_newsroom_is_trusted_media():
    row = article("NAVER · view.asiae.co.kr", "https://view.asiae.co.kr/article/1")
    assert source_tier(row) == "ESTABLISHED_MEDIA"


def test_unverified_small_outlets_remain_discovery_media():
    for domain in ("cbci.co.kr", "wsobi.com", "newsdream.kr"):
        row = article(f"NAVER · {domain}", f"https://{domain}/news/1")
        assert source_tier(row) == "DISCOVERY_MEDIA"


def test_corporate_newsroom_discovered_via_naver_is_primary_evidence():
    for url in (
        "https://www.krafton.com/news/press/example/",
        "https://www.nc.com/newsroom/news/articles/?articleId=1",
        "https://news.samsung.com/kr/example",
    ):
        row = article("NAVER · discovered", url)
        assert source_tier(row) == "PRIMARY"


def test_discovered_corporate_newsroom_is_official_only_and_eligible():
    row = article("NAVER · krafton.com", "https://www.krafton.com/news/press/example/")
    quality = evaluate_evidence([row])
    assert quality.verification_status == "OFFICIAL_ONLY"
    assert quality.synthesis_eligible is True


def test_unknown_discovery_results_are_not_synthesis_evidence():
    rows=[
        article("NAVER · a.example", "https://a.example/1"),
        article("NAVER · b.example", "https://b.example/1"),
    ]
    quality=evaluate_evidence(rows)
    assert quality.verification_status == "DISCOVERY_ONLY"
    assert quality.synthesis_eligible is False


def test_official_source_is_synthesis_evidence():
    quality=evaluate_evidence([article("OpenAI", "https://openai.com/news/x", "official")])
    assert quality.verification_status == "OFFICIAL_ONLY"
    assert quality.synthesis_eligible is True
