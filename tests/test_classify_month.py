import sys
import os
import shutil
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas.classification_schema import ClassificationOutput, Section, Item
from tools.ai_client import ClassificationError, HAIKU_MODEL, SONNET_MODEL
from tools.classify_month import classify_month, NeedsHumanReview, CACHE_DIR


def make_output(confidence=0.9):
    return ClassificationOutput(sections=[
        Section(section_title="테스트 섹션", block_type="grid",
                items=[Item(name="아이템1"), Item(name="아이템2")],
                footnote=None, confidence=confidence)
    ])


def make_paired_columns_output(confidence=0.9, pair_group_none_count=2):
    # real 202503 bug: the model can tag 0 (or 1, or 3+) items with
    # pair_group=None instead of exactly 2 — paired_columns_block hard-
    # requires exactly 2, so anything else guarantees a render-time
    # ValueError that silently drops the whole section from the deck
    items = [Item(name=f"세트{i}", pair_group=None) for i in range(pair_group_none_count)]
    items += [Item(name="구성품1", pair_group=0), Item(name="구성품2", pair_group=1)]
    return ClassificationOutput(sections=[
        Section(section_title="테스트 페어드 섹션", block_type="paired_columns",
                items=items, footnote="아래 중 택 1", confidence=confidence)
    ])


@pytest.fixture(autouse=True)
def clean_cache():
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
    yield
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)


def test_high_confidence_haiku_no_escalation():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.return_value = make_output(confidence=0.9)
        result = classify_month("999901", "raw text here")
        assert result.model_used == HAIKU_MODEL
        assert mock_classify.call_count == 1


def test_low_confidence_escalates_to_sonnet():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.side_effect = [make_output(confidence=0.4), make_output(confidence=0.9)]
        result = classify_month("999902", "raw text here")
        assert result.model_used == SONNET_MODEL
        assert mock_classify.call_count == 2
        first_call_model = mock_classify.call_args_list[0].args[3]
        second_call_model = mock_classify.call_args_list[1].args[3]
        assert first_call_model == HAIKU_MODEL
        assert second_call_model == SONNET_MODEL


def test_both_low_confidence_raises_needs_human_review():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.side_effect = [make_output(confidence=0.3), make_output(confidence=0.3)]
        with pytest.raises(NeedsHumanReview):
            classify_month("999903", "raw text here")


def test_haiku_schema_failure_retries_same_tier_before_escalating():
    # malformed-response retry (MALFORMED_RETRY_ATTEMPTS=2): Haiku fails
    # once, succeeds on retry — should NOT escalate to Sonnet at all
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.side_effect = [ClassificationError("bad json"), make_output(confidence=0.9)]
        result = classify_month("999904", "raw text here")
        assert result.model_used == HAIKU_MODEL
        assert mock_classify.call_count == 2


def test_haiku_fails_both_retries_then_escalates_to_sonnet():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.side_effect = [
            ClassificationError("bad json"), ClassificationError("bad json"),
            make_output(confidence=0.9),
        ]
        result = classify_month("999904b", "raw text here")
        assert result.model_used == SONNET_MODEL
        assert mock_classify.call_count == 3


def test_sonnet_schema_failure_after_haiku_failure_raises():
    with patch("tools.classify_month.classify") as mock_classify:
        # Haiku fails both attempts, Sonnet fails both attempts -> give up
        mock_classify.side_effect = [ClassificationError("bad json")] * 4
        with pytest.raises(NeedsHumanReview):
            classify_month("999905", "raw text here")
        assert mock_classify.call_count == 4


def test_cache_hit_skips_api_call():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.return_value = make_output(confidence=0.9)
        classify_month("999906", "same raw text")
        assert mock_classify.call_count == 1
        result2 = classify_month("999906", "same raw text")
        assert mock_classify.call_count == 1  # not called again
        assert result2.from_cache is True


def test_different_raw_text_is_a_cache_miss():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.return_value = make_output(confidence=0.9)
        classify_month("999907", "text A")
        classify_month("999907", "text B")
        assert mock_classify.call_count == 2


def test_paired_columns_with_exactly_two_pair_items_is_confident():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.return_value = make_paired_columns_output(confidence=0.9, pair_group_none_count=2)
        result = classify_month("999909", "raw text here")
        assert result.model_used == HAIKU_MODEL
        assert mock_classify.call_count == 1


def test_paired_columns_with_zero_pair_items_escalates_despite_high_confidence():
    # the model's own reported confidence (0.9) must not matter here — 0
    # pair_group=None items is structurally guaranteed to fail rendering
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.side_effect = [
            make_paired_columns_output(confidence=0.9, pair_group_none_count=0),
            make_paired_columns_output(confidence=0.9, pair_group_none_count=2),
        ]
        result = classify_month("999910", "raw text here")
        assert result.model_used == SONNET_MODEL
        assert mock_classify.call_count == 2


def test_paired_columns_still_structurally_invalid_after_sonnet_raises_with_clear_reason():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.side_effect = [
            make_paired_columns_output(confidence=0.9, pair_group_none_count=0),
            make_paired_columns_output(confidence=0.9, pair_group_none_count=3),
        ]
        with pytest.raises(NeedsHumanReview, match="exactly 2 top-level items"):
            classify_month("999911", "raw text here")


def test_force_refresh_bypasses_cache():
    with patch("tools.classify_month.classify") as mock_classify:
        mock_classify.return_value = make_output(confidence=0.9)
        classify_month("999908", "same text")
        classify_month("999908", "same text", force_refresh=True)
        assert mock_classify.call_count == 2
