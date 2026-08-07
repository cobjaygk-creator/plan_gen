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


def test_process_month_renders_grid_section_end_to_end(tmp_path):
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path, image_out_dir=str(tmp_path))

    assert result.needs_human_review is None
    assert result.fatal_error is None
    assert len(result.sections) == 1
    section = result.sections[0]
    assert section.render_error is None
    assert section.item_count == 6
    assert len(section.pages) >= 1
    summary = pipeline.summarize(result)
    assert "[OK]" in summary or "[OVERLAP]" in summary


def test_process_month_records_render_error_without_crashing(tmp_path):
    def fake_classify_bad_paired(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="이상한 섹션", block_type="paired_columns",
                    items=[Item(name="아이템 하나뿐")], footnote=None, confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_bad_paired):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path, image_out_dir=str(tmp_path))

    assert len(result.sections) == 1
    assert result.sections[0].render_error is not None  # paired_columns needs exactly 2
    summary = pipeline.summarize(result)
    assert "[ERROR]" in summary


def test_process_month_propagates_needs_human_review(tmp_path):
    from tools.classify_month import NeedsHumanReview

    def fake_classify_raises(month, raw_text, **kwargs):
        raise NeedsHumanReview(month, "confidence too low", raw_text)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_raises):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path, image_out_dir=str(tmp_path))

    assert result.needs_human_review is not None
    assert "202605" in pipeline.summarize(result)


def test_process_month_paired_columns_matches_set_names_not_sub_items(tmp_path):
    # Real 202606 bug: "자켓 세트"/"치마 세트" portraits are anchored at
    # column C/D while their own text sits in column B/D — outside
    # match_images' default col_tolerance=0. Widening tolerance blindly
    # would let a sub-item (whose row sits exactly inside the portrait
    # anchor's row span, distance 0) win the anchor away from the actual
    # set name (row 18, distance >0) via the nearest-first tiebreak.
    # process_month must exclude sub-items from paired_columns matching
    # entirely so only the 2 set-name items ever compete for portraits.
    def fake_classify_202606(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="배틀패스 신규 의상", block_type="paired_columns", items=[
                Item(name="20th 파티 자켓 세트", pair_group=None),
                Item(name="20th 파티 치마 세트", pair_group=None),
                Item(name="20th 파티 연미복", pair_group=0),
                Item(name="20th 파티 흰꽃 머리띠", pair_group=1),
            ], footnote="* 각주", confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_202606):
        path = os.path.join(SAMPLES_DIR, "202606_request.xlsx")
        result = pipeline.process_month("202606", path, image_out_dir=str(tmp_path))

    section = result.sections[0]
    assert section.render_error is None
    items_by_name = {i["name"]: i for i in section.items}
    assert items_by_name["20th 파티 자켓 세트"]["image"] is not None
    assert items_by_name["20th 파티 치마 세트"]["image"] is not None
    # sub-items must never receive an image even though match_images would
    # gladly hand one to them if they were left in the matching pool
    assert items_by_name["20th 파티 연미복"]["image"] is None
    assert items_by_name["20th 파티 흰꽃 머리띠"]["image"] is None


def test_process_month_defaults_to_real_local_image_paths():
    # Regression: omitting image_out_dir used to leave in-archive paths
    # (e.g. "xl/media/image8.PNG") on matched items, which render_pptx.py's
    # os.path.exists() check silently treats as "no image" — a fully-
    # matched section could render with zero pictures and no error at all.
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path)  # no image_out_dir

    section = result.sections[0]
    for page in section.pages:
        for placement in page:
            if placement.kind == "icon" and isinstance(placement.ref, dict):
                image_path = placement.ref.get("image")
                if image_path:
                    assert os.path.exists(image_path), f"matched image path is not a real file: {image_path}"
