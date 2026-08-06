import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.parse_fixed_fields import parse_fixed_fields
from tools.extract_special_reward import extract_special_reward_rows, to_compact_text

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def _rows_for(month):
    path = os.path.join(SAMPLES_DIR, f"{month}_request.xlsx")
    fixed = parse_fixed_fields(path)
    return extract_special_reward_rows(path, fixed["special_reward_start_row"])


def test_cell_based_captions_202605():
    rows = _rows_for("202605")
    text = to_compact_text(rows)
    assert "발레코어 소프트 의상 세트 I (new)" in text
    assert "기간제 패키지" in text
    # must stop before the fixed-field boundary, not leak into it
    assert "유의사항" not in text
    assert "보상 리스트 보러 가기" not in text


def test_drawing_textbox_captions_202509():
    # 202509's item names live in floating drawing textboxes, not cell
    # values — this is the case that broke the first extractor version.
    rows = _rows_for("202509")
    text = to_compact_text(rows)
    assert "할로윈 뱀파이어 슈트 세트" in text
    assert "할로윈 뱀파이어 원피스 세트" in text
    assert "할로윈 펌킨 버킷 등록권" in text


def test_stays_within_declared_row_range():
    rows = _rows_for("202605")
    for row in rows:
        assert row["row"] >= 16  # special_reward_start_row for this sample
