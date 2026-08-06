import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.regression import text_match_rate, image_match_rate, overlap_count, score_run
from tools.blocks import grid_block, Placement


def test_text_match_rate_perfect():
    assert text_match_rate(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_text_match_rate_partial():
    assert text_match_rate(["a", "b", "c", "d"], ["a", "b"]) == 0.5


def test_text_match_rate_ignores_whitespace_diffs():
    assert text_match_rate(["  붉은 거인 의상 세트 "], ["붉은 거인 의상 세트"]) == 1.0


def test_text_match_rate_empty_expected_is_trivially_perfect():
    assert text_match_rate([], ["a"]) == 1.0


def test_image_match_rate_all_resolved():
    expected = [{"name": "a", "image": "a.png"}, {"name": "b", "image": "b.png"}]
    actual = [{"name": "a", "image": "a.png"}, {"name": "b", "image": "b.png"}]
    assert image_match_rate(expected, actual) == 1.0


def test_image_match_rate_partial():
    expected = [{"name": "a", "image": "a.png"}, {"name": "b", "image": "b.png"}]
    actual = [{"name": "a", "image": "a.png"}, {"name": "b", "image": None}]
    assert image_match_rate(expected, actual) == 0.5


def test_image_match_rate_skips_items_without_expected_image():
    expected = [{"name": "a", "image": None}]
    actual = [{"name": "a", "image": None}]
    assert image_match_rate(expected, actual) == 1.0


def test_overlap_count_clean_pages():
    items = [{"name": f"i{i}"} for i in range(6)]
    pages = grid_block(items, columns=3, icon_size=24.0)
    assert overlap_count(pages) == 0


def test_overlap_count_detects_bad_page():
    bad_page = [
        Placement("icon", 100, 100, 50, 50, {"name": "x"}),
        Placement("icon", 110, 110, 50, 50, {"name": "y"}),  # overlaps the first
    ]
    assert overlap_count([bad_page]) == 1


def test_score_run_pass():
    items = [{"name": "a", "image": "a.png"}, {"name": "b", "image": "b.png"}]
    pages = grid_block(items, columns=3, icon_size=24.0)
    result = score_run("202605", items, items, pages)
    assert result.passed
    assert "PASS" in result.summary()


def test_score_run_fail_on_missing_text():
    expected = [{"name": "a", "image": None}, {"name": "b", "image": None}, {"name": "c", "image": None}]
    actual = [{"name": "a", "image": None}]
    pages = grid_block(actual, columns=3, icon_size=24.0)
    result = score_run("202605", expected, actual, pages)
    assert not result.passed
    assert "FAIL" in result.summary()
