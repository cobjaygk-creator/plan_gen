import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.keyword_taxonomy import classify_signal_keyword
from app.industry_brief.models import Article


def _article(entities):
    return Article(source="NAVER · example.com", source_type="media", category="GAME", title="test", url=f"https://example.com/{len(entities)}", entities=json.dumps(entities))


def test_classifies_industry_company_and_project_keywords():
    assert classify_signal_keyword("MMORPG", []) == ("INDUSTRY", "산업 주제")
    assert classify_signal_keyword("PROJECT D1", []) == ("PROJECT", "프로젝트")
    assert classify_signal_keyword("붉은사막", []) == ("PRODUCT", "제품")
    articles = [_article(["웹젠"]), _article(["웹젠"]), _article(["웹젠"])]
    assert classify_signal_keyword("웹젠", articles) == ("COMPANY", "기업")