"""202512 as a formal regression case — added after a real bug (image
matching leaving 서핑푸리링 unmatched, NEW badge misattributed to the wrong
item) was found via manual comparison against the actual reference sample.

Ground truth below was hand-verified against samples/202512_request.xlsx's
raw cell/drawing data during that investigation (see git log for
tools/match_images.py and tools/classify_month.py around this test's
commit) — not from re-running the AI, so this test doesn't call the API
and stays free/fast/deterministic. It exercises the real xlsx file
through locate_items -> match_images -> block engine, i.e. everything
downstream of classification, which is where both bugs actually were.

check_live_classification_matches_ground_truth() at the bottom is
deliberately NOT prefixed test_ (pytest won't collect it) — it calls the
real API and is meant to be run manually/occasionally to catch the AI
classifier drifting from this ground truth, not on every `pytest` run.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas.classification_schema import ClassificationOutput, Section, Item
from tools.locate_items import locate_items
from tools.match_images import match_images
from tools.extract_special_reward import extract_special_reward_rows
from tools.parse_fixed_fields import parse_fixed_fields
from tools.pipeline import _items_with_images, _render_section
from tools.blocks import has_any_overlap

REQUEST_PATH = os.path.join(os.path.dirname(__file__), "..", "samples", "202512_request.xlsx")

# Ground truth, hand-verified against the raw source (see module docstring).
GROUND_TRUTH = ClassificationOutput(sections=[
    Section(
        section_title="시계태엽 의상 선택권", block_type="paired_columns",
        items=[Item(name="시계태엽 바지 세트"), Item(name="시계태엽 치마 세트")],
        footnote="아래 패션 세트 중 택 1 (거래 불가)", confidence=1.0,
    ),
    Section(
        section_title="배틀패스 FX 타이틀 교환권", block_type="grid",
        items=[
            Item(name="RETRO FX 타이틀 습득서 (영구제)"),
            Item(name="수묵화 FX 타이틀 습득서(영구제)"),
            Item(name="아에루라 FX 타이틀 습득서(영구제)"),
            Item(name="LEFICA 타이틀 습득서 (영구제)"),
            Item(name="DEVIL FX 타이틀 습득서 (영구제)"),
            Item(name="멍멍 멍멍멍 FX 타이틀 습득서(영구제)"),
            Item(name="서핑 푸리링 타이틀 습득서(영구제)"),
            Item(name="따끈따근 프리링 타이틀 습득서(영구제)", is_new=True),  # only this one
        ],
        footnote="아래 FX 타이틀 중 택 1 (거래 불가)", confidence=1.0,
    ),
    Section(
        section_title="신규 배틀패스 헤어 출시", block_type="few_preview",
        items=[Item(name="[이벤트] 배틀패스 머리모양 영구 변경권"), Item(name="베이비펌 사과머리")],
        footnote="배틀패스 쿠폰을 통해 '[이벤트] 배틀패스 머리모양 영구 변경권' 획득 가능", confidence=1.0,
    ),
])

# expected (matched_count, total_count) per section, in the same order
EXPECTED_IMAGE_COVERAGE = [(2, 2), (7, 8), (1, 2)]
EXPECTED_NEW_ITEMS = [[], ["따끈따근 프리링 타이틀 습득서(영구제)"], []]


def _rows():
    fixed = parse_fixed_fields(REQUEST_PATH)
    return extract_special_reward_rows(REQUEST_PATH, fixed["special_reward_start_row"])


def test_image_coverage_matches_ground_truth():
    rows = _rows()
    for section, (expected_matched, expected_total) in zip(GROUND_TRUTH.sections, EXPECTED_IMAGE_COVERAGE):
        located, unlocated = locate_items(rows, section.items)
        matched, text_only = match_images(REQUEST_PATH, located)
        assert len(section.items) == expected_total, section.section_title
        assert len(matched) == expected_matched, (
            f"{section.section_title}: expected {expected_matched}/{expected_total} matched, "
            f"got {len(matched)} (regressed image matching?)"
        )


def test_new_badge_on_correct_item_only():
    for section, expected_new in zip(GROUND_TRUTH.sections, EXPECTED_NEW_ITEMS):
        actual_new = [i.name for i in section.items if i.is_new]
        assert actual_new == expected_new, section.section_title


def test_full_render_no_overlap_and_matches_coverage():
    rows = _rows()
    for section, (expected_matched, _) in zip(GROUND_TRUTH.sections, EXPECTED_IMAGE_COVERAGE):
        located, unlocated = locate_items(rows, section.items)
        matched, text_only = match_images(REQUEST_PATH, located)
        items = _items_with_images(section, matched, text_only)
        pages = _render_section(section, items)
        for page in pages:
            assert not has_any_overlap(page), section.section_title
        assert sum(1 for i in items if i["image"]) == expected_matched, section.section_title


def check_live_classification_matches_ground_truth():
    """Not collected by pytest — run manually: calls the real API."""
    from tools.classify_month import classify_month
    from tools.extract_special_reward import to_compact_text

    rows = _rows()
    raw_text = to_compact_text(rows)
    result = classify_month("202512", raw_text, force_refresh=True)

    mismatches = []
    for expected, actual in zip(GROUND_TRUTH.sections, result.output.sections):
        if expected.block_type != actual.block_type:
            mismatches.append(f"{expected.section_title}: block_type {actual.block_type} != {expected.block_type}")
        expected_new = {i.name for i in expected.items if i.is_new}
        actual_new = {i.name for i in actual.items if i.is_new}
        if expected_new != actual_new:
            mismatches.append(f"{expected.section_title}: is_new items {actual_new} != {expected_new}")

    if mismatches:
        print("DRIFT DETECTED:\n" + "\n".join(mismatches))
    else:
        print("Live classification matches ground truth.")
    return mismatches


if __name__ == "__main__":
    check_live_classification_matches_ground_truth()
