import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.locate_items import locate_items, normalize, LocatedItem
from tools.match_images import match_images, _distance
from tools.extract_images import PictureAnchor


class FakeItem:
    def __init__(self, name, is_new=False):
        self.name = name
        self.is_new = is_new


def test_normalize_strips_new_marker_and_whitespace():
    assert normalize("발레코어 소프트 의상 세트 I (new)") == normalize("발레코어 소프트 의상 세트 I")
    assert normalize("  코스튬   A ") == normalize("코스튬A")
    assert normalize("세트 (new!)") == normalize("세트")


def test_locate_items_finds_exact_and_new_marker_stripped():
    rows = [
        {"row": 19, "cells": {"B": "아이템A", "C": "아이템B (new)"}},
        {"row": 20, "cells": {"B": "아이템C"}},
    ]
    items = [FakeItem("아이템A"), FakeItem("아이템B", is_new=True), FakeItem("아이템C")]
    located, unlocated = locate_items(rows, items)
    assert len(unlocated) == 0
    assert len(located) == 3
    by_name = {i.name: i for i in located}
    assert by_name["아이템A"].row == 19 and by_name["아이템A"].col_letter == "B"
    assert by_name["아이템B"].row == 19 and by_name["아이템B"].col_letter == "C"


def test_locate_items_flags_missing_names_instead_of_guessing():
    rows = [{"row": 19, "cells": {"B": "아이템A"}}]
    items = [FakeItem("아이템A"), FakeItem("존재하지않는아이템")]
    located, unlocated = locate_items(rows, items)
    assert len(located) == 1
    assert len(unlocated) == 1
    assert unlocated[0].name == "존재하지않는아이템"


def test_locate_items_does_not_double_assign_same_cell():
    # two items with the same normalized name shouldn't both claim one cell
    rows = [{"row": 19, "cells": {"B": "같은이름"}}]
    items = [FakeItem("같은이름"), FakeItem("같은이름")]
    located, unlocated = locate_items(rows, items)
    assert len(located) == 1
    assert len(unlocated) == 1


def test_distance_zero_when_row_within_anchor_span():
    item = LocatedItem("x", False, row=20, col_letter="B", matched_cell_text="x")
    anchor = PictureAnchor("B", row_start=19, row_end=22, rid="rId1", media_path="xl/media/image1.png")
    assert _distance(item, anchor) == 0


def test_distance_positive_outside_span():
    item = LocatedItem("x", False, row=30, col_letter="B", matched_cell_text="x")
    anchor = PictureAnchor("B", row_start=19, row_end=22, rid="rId1", media_path="xl/media/image1.png")
    assert _distance(item, anchor) == 8


def test_match_images_reports_unmatched_when_no_column_images(monkeypatch, tmp_path):
    # simulates the real 202605 case: images exist but in a column with no items
    from tools import match_images as mi_module

    def fake_get_anchors(path):
        return [PictureAnchor("E", 31, 38, "rId1", "xl/media/image1.png")]

    monkeypatch.setattr(mi_module, "get_picture_anchors", fake_get_anchors)

    located = [LocatedItem("아이템A", False, row=19, col_letter="B", matched_cell_text="아이템A")]
    matched, unmatched = match_images("fake_path.xlsx", located)
    assert len(matched) == 0
    assert len(unmatched) == 1
    assert unmatched[0].name == "아이템A"


def test_match_images_matches_same_column_within_tolerance(monkeypatch):
    from tools import match_images as mi_module

    def fake_get_anchors(path):
        return [PictureAnchor("B", 18, 21, "rId1", "xl/media/image1.png")]

    monkeypatch.setattr(mi_module, "get_picture_anchors", fake_get_anchors)

    located = [LocatedItem("아이템A", False, row=19, col_letter="B", matched_cell_text="아이템A")]
    matched, unmatched = match_images("fake_path.xlsx", located)
    assert len(matched) == 1
    assert len(unmatched) == 0
    assert matched[0].image_path == "xl/media/image1.png"


def test_match_images_does_not_reuse_same_anchor_twice(monkeypatch):
    from tools import match_images as mi_module

    def fake_get_anchors(path):
        return [PictureAnchor("B", 18, 21, "rId1", "xl/media/image1.png")]

    monkeypatch.setattr(mi_module, "get_picture_anchors", fake_get_anchors)

    located = [
        LocatedItem("아이템A", False, row=19, col_letter="B", matched_cell_text="아이템A"),
        LocatedItem("아이템B", False, row=20, col_letter="B", matched_cell_text="아이템B"),
    ]
    matched, unmatched = match_images("fake_path.xlsx", located)
    assert len(matched) == 1
    assert len(unmatched) == 1


def test_match_images_no_column_images_stays_text_only(monkeypatch):
    # only image source is request.xlsx itself — nothing else to fall
    # back to, so a miss must land as text_only, not error out
    from tools import match_images as mi_module

    monkeypatch.setattr(mi_module, "get_picture_anchors", lambda path: [])
    located = [LocatedItem("아이템A", False, row=19, col_letter="B", matched_cell_text="아이템A")]
    matched, text_only = match_images("fake_path.xlsx", located)
    assert len(matched) == 0
    assert len(text_only) == 1


def test_match_images_finds_optimal_assignment_not_just_greedy(monkeypatch):
    # Real bug reproduction (202512 "FX 타이틀 교환권"): 3 items competing
    # for anchors under tolerance where a naive per-item-in-order greedy
    # match leaves one item unmatched (an earlier item takes the anchor a
    # later item needed more, even though it had an equally-good backup)
    # despite a valid 3-of-3 assignment existing. Exact real row numbers.
    from tools import match_images as mi_module

    def fake_get_anchors(path):
        return [
            PictureAnchor("C", 42, 45, "rId1", "img8.png"),   # anchor1
            PictureAnchor("C", 37, 40, "rId2", "img10.png"),  # anchor2
            PictureAnchor("C", 49, 51, "rId3", "img11.png"),  # anchor3
        ]

    monkeypatch.setattr(mi_module, "get_picture_anchors", fake_get_anchors)

    located = [
        LocatedItem("아에루라", False, row=41, col_letter="C", matched_cell_text="아에루라"),
        LocatedItem("멍멍멍멍", False, row=46, col_letter="C", matched_cell_text="멍멍멍멍"),
        LocatedItem("서핑푸리링", False, row=52, col_letter="C", matched_cell_text="서핑푸리링"),
    ]
    matched, text_only = match_images("fake_path.xlsx", located)
    assert len(text_only) == 0
    assert len(matched) == 3
