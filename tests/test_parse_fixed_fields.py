import sys
import os
import glob
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.parse_fixed_fields import parse_fixed_fields

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def sample_months():
    paths = sorted(glob.glob(os.path.join(SAMPLES_DIR, "*_request.xlsx")))
    return [p for p in paths if "~$" not in os.path.basename(p)]


@pytest.mark.parametrize("path", sample_months())
def test_parses_every_sample_without_error(path):
    result = parse_fixed_fields(path)
    assert len(result["title_lines"]) >= 1
    assert result["period"]
    assert len(result["grade_table"]["tiers"]) == 3
    assert len(result["grade_table"]["prices"]) == 3
    assert result["special_reward_start_row"] is not None


def test_202605_exact_values():
    result = parse_fixed_fields(os.path.join(SAMPLES_DIR, "202605_request.xlsx"))
    assert result["title_lines"] == ["매 순간이 반짝이는", "Rocking 배틀패스"]
    assert "2026년 5월 13일" in result["period"]
    assert result["grade_table"]["tiers"] == ["일반 배틀패스", "프리미엄 배틀패스", "로얄 배틀패스"]
    assert result["grade_table"]["prices"] == ["FREE", "24900캐쉬", "29900캐쉬"]
    assert any("해당 시즌" in n for n in result["notices"])


def test_handles_period_label_prefix_variant():
    # 202502 has "기간 : ..." prefix, 202605 has none — both must parse.
    result = parse_fixed_fields(os.path.join(SAMPLES_DIR, "202502_request.xlsx"))
    assert "점검" in result["period"]
    assert "~" in result["period"]


def test_grade_table_content_is_stable_across_months():
    # All 10 months use the identical tier/price scheme — a real change here
    # would be a signal worth flagging, not silently accepting.
    tiers_seen = set()
    prices_seen = set()
    for path in sample_months():
        result = parse_fixed_fields(path)
        tiers_seen.add(tuple(result["grade_table"]["tiers"]))
        prices_seen.add(tuple(result["grade_table"]["prices"]))
    assert len(tiers_seen) == 1
    assert len(prices_seen) == 1
