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


def test_image_only_rows_are_not_dropped_202602():
    # real bug: rows 42-50 anchor a single combined image (202602's
    # "[이벤트] 고양이 모자 선택권", 9 cat-hat icons, no item names anywhere)
    # but carry zero cell text — used to be silently excluded entirely, so
    # the classifier never even knew the section had content past its
    # title/footnote (see extract_special_reward_rows' docstring note)
    rows = _rows_for("202602")
    by_row = {r["row"]: r for r in rows}
    assert 42 in by_row
    assert by_row[42]["cells"] == {}
    assert by_row[42]["has_image"] is True

    text = to_compact_text(rows)
    assert "42: [이미지있음]" in text
    assert "[이벤트] 고양이 모자 선택권" in text


def test_colliding_textbox_captions_are_not_dropped_202508():
    # real bug (user-reported, screenshots): "배틀패스 의상 교환권" rendered
    # as a broken 4-image icon_only block instead of its real 21-item grid.
    # Root cause: several rows pack 2 textboxes into the same nominal
    # spreadsheet column (col_idx0 identical, colOff very different — e.g.
    # "화이트 니트 세트" and "브라운 니트 세트" both anchor at col_idx0=2)
    # — the old merge used dict.setdefault(col_letter, text), so the
    # second caption in each colliding pair was silently dropped. With
    # only 5 of the real 21 names visible, the classifier had no way to
    # tell this apart from a real icon_only section.
    rows = _rows_for("202508")
    text = to_compact_text(rows)
    for name in ["브라운 니트 세트", "레트로 팬츠 세트", "도플갱어 거인 의상 세트", "바다의 향기 의상 세트"]:
        assert name in text, f"{name!r} missing — collision fix regressed"


def test_drawing_textbox_entities_are_unescaped_202508():
    # real bug found alongside the collision one: XML text runs keep
    # entities literal ("&amp;"), so "빌브라트 수트 & 펀치 mini" rendered
    # with the escape still in it.
    rows = _rows_for("202508")
    text = to_compact_text(rows)
    assert "빌브라트 수트 & 펀치 mini" in text
    assert "&amp;" not in text
