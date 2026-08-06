import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas.classification_schema import ClassificationOutput, Section, Item
from tools.classify_month import ClassifyResult
from tools.locate_items import LocatedItem
from tools import pipeline

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def _fake_classify(month, raw_text, **kwargs):
    output = ClassificationOutput(sections=[
        Section(section_title="기간제 패키지", block_type="grid",
                items=[Item(name="[이벤트] 고대의 서 30일 상자"), Item(name="[이벤트] 세레스의 가호 습득서"),
                       Item(name="그림자 스킨(30일) 교환권"), Item(name="길드의 가호 습득서(기간제)"),
                       Item(name="[이벤트] 피크닉 타이틀 습득서 (30일)"), Item(name="헌터의 힘 스킬 습득서 (30일)")],
                footnote="(구성품)", confidence=0.95),
    ])
    return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)


def test_process_month_renders_grid_section_end_to_end():
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path)

    assert result.needs_human_review is None
    assert result.fatal_error is None
    assert len(result.sections) == 1
    section = result.sections[0]
    assert section.render_error is None
    assert section.item_count == 6
    assert len(section.pages) >= 1
    summary = pipeline.summarize(result)
    assert "[OK]" in summary or "[OVERLAP]" in summary


def test_process_month_records_render_error_without_crashing():
    def fake_classify_bad_paired(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="이상한 섹션", block_type="paired_columns",
                    items=[Item(name="아이템 하나뿐")], footnote=None, confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_bad_paired):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path)

    assert len(result.sections) == 1
    assert result.sections[0].render_error is not None  # paired_columns needs exactly 2
    summary = pipeline.summarize(result)
    assert "[ERROR]" in summary


def test_process_month_propagates_needs_human_review():
    from tools.classify_month import NeedsHumanReview

    def fake_classify_raises(month, raw_text, **kwargs):
        raise NeedsHumanReview(month, "confidence too low", raw_text)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_raises):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path)

    assert result.needs_human_review is not None
    assert "202605" in pipeline.summarize(result)
