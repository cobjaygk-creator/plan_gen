import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.ai_client import ClassificationError
from tools.extract_images import PictureAnchor
from tools.locate_items import LocatedItem
from tools.match_images import MatchedItem
from tools.vision_match import (
    ImageAssignment, VisionMatchResult, resolve_unmatched_with_vision,
    IconFilterResult, filter_decorative_icons,
)


def _item(name: str, row: int) -> LocatedItem:
    return LocatedItem(name=name, is_new=False, row=row, col_letter="C", matched_cell_text=name)


def test_no_text_only_items_makes_no_calls():
    with patch("tools.vision_match.extract_and_save_images") as extract, \
         patch("tools.vision_match.classify_with_images") as classify:
        resolved, unresolved = resolve_unmatched_with_vision("req.xlsx", [], [], "out")

    assert resolved == []
    assert unresolved == []
    extract.assert_not_called()
    classify.assert_not_called()


def test_no_nearby_unclaimed_anchor_short_circuits():
    text_only = [_item("수묵화 대미지 스킨", row=10)]
    # anchor exists but far from row 10, well outside ROW_TOLERANCE
    anchor = PictureAnchor("C", 100, 100, "rId1", "xl/media/image1.png")
    with patch("tools.vision_match.extract_and_save_images", return_value=[(anchor, "out/rId1.png")]), \
         patch("tools.vision_match.classify_with_images") as classify:
        resolved, unresolved = resolve_unmatched_with_vision("req.xlsx", text_only, [], "out")

    assert resolved == []
    assert unresolved == text_only
    classify.assert_not_called()


def test_already_used_anchor_is_excluded_from_candidates():
    text_only = [_item("수묵화 대미지 스킨", row=10)]
    anchor = PictureAnchor("C", 9, 11, "rId1", "xl/media/image1.png")
    matched = [MatchedItem(name="다른항목", is_new=False, row=9, col_letter="C", image_path="out/rId1.png")]
    with patch("tools.vision_match.extract_and_save_images", return_value=[(anchor, "out/rId1.png")]), \
         patch("tools.vision_match.classify_with_images") as classify:
        resolved, unresolved = resolve_unmatched_with_vision("req.xlsx", text_only, matched, "out")

    assert resolved == []
    assert unresolved == text_only
    classify.assert_not_called()


def test_successful_resolution_assigns_image_path(tmp_path):
    text_only = [_item("수묵화 대미지 스킨", row=10)]
    anchor = PictureAnchor("C", 9, 11, "rId1", "xl/media/image1.png")
    image_path = str(tmp_path / "rId1.png")
    with open(image_path, "wb") as f:
        f.write(b"fake-png-bytes")

    result = VisionMatchResult(assignments=[ImageAssignment(item_name="수묵화 대미지 스킨", image_index=0)])
    with patch("tools.vision_match.extract_and_save_images", return_value=[(anchor, image_path)]), \
         patch("tools.vision_match.classify_with_images", return_value=result) as classify:
        resolved, unresolved = resolve_unmatched_with_vision("req.xlsx", text_only, [], "out")

    assert unresolved == []
    assert len(resolved) == 1
    assert resolved[0].name == "수묵화 대미지 스킨"
    assert resolved[0].image_path == image_path
    classify.assert_called_once()


def test_two_items_sharing_one_image_index_both_resolve_to_same_path(tmp_path):
    text_only = [_item("레트로 원피스 세트", row=10), _item("레트로 팬츠 세트", row=11)]
    anchor = PictureAnchor("C", 9, 12, "rId1", "xl/media/image1.png")
    image_path = str(tmp_path / "rId1.png")
    with open(image_path, "wb") as f:
        f.write(b"fake-png-bytes")

    result = VisionMatchResult(assignments=[
        ImageAssignment(item_name="레트로 원피스 세트", image_index=0),
        ImageAssignment(item_name="레트로 팬츠 세트", image_index=0),
    ])
    with patch("tools.vision_match.extract_and_save_images", return_value=[(anchor, image_path)]), \
         patch("tools.vision_match.classify_with_images", return_value=result):
        resolved, unresolved = resolve_unmatched_with_vision("req.xlsx", text_only, [], "out")

    assert unresolved == []
    assert len(resolved) == 2
    assert resolved[0].image_path == resolved[1].image_path == image_path


def test_null_index_leaves_item_unresolved(tmp_path):
    text_only = [_item("장식 리본", row=10)]
    anchor = PictureAnchor("C", 9, 11, "rId1", "xl/media/image1.png")
    image_path = str(tmp_path / "rId1.png")
    with open(image_path, "wb") as f:
        f.write(b"fake-png-bytes")

    result = VisionMatchResult(assignments=[ImageAssignment(item_name="장식 리본", image_index=None)])
    with patch("tools.vision_match.extract_and_save_images", return_value=[(anchor, image_path)]), \
         patch("tools.vision_match.classify_with_images", return_value=result):
        resolved, unresolved = resolve_unmatched_with_vision("req.xlsx", text_only, [], "out")

    assert resolved == []
    assert unresolved == text_only


def test_out_of_range_index_leaves_item_unresolved(tmp_path):
    text_only = [_item("수묵화 대미지 스킨", row=10)]
    anchor = PictureAnchor("C", 9, 11, "rId1", "xl/media/image1.png")
    image_path = str(tmp_path / "rId1.png")
    with open(image_path, "wb") as f:
        f.write(b"fake-png-bytes")

    # model hallucinated an index beyond the single candidate given (0)
    result = VisionMatchResult(assignments=[ImageAssignment(item_name="수묵화 대미지 스킨", image_index=5)])
    with patch("tools.vision_match.extract_and_save_images", return_value=[(anchor, image_path)]), \
         patch("tools.vision_match.classify_with_images", return_value=result):
        resolved, unresolved = resolve_unmatched_with_vision("req.xlsx", text_only, [], "out")

    assert resolved == []
    assert unresolved == text_only


def test_classification_error_leaves_everything_unresolved(tmp_path):
    text_only = [_item("수묵화 대미지 스킨", row=10)]
    anchor = PictureAnchor("C", 9, 11, "rId1", "xl/media/image1.png")
    image_path = str(tmp_path / "rId1.png")
    with open(image_path, "wb") as f:
        f.write(b"fake-png-bytes")

    with patch("tools.vision_match.extract_and_save_images", return_value=[(anchor, image_path)]), \
         patch("tools.vision_match.classify_with_images", side_effect=ClassificationError("boom")):
        resolved, unresolved = resolve_unmatched_with_vision("req.xlsx", text_only, [], "out")

    assert resolved == []
    assert unresolved == text_only


def test_filter_decorative_icons_single_image_makes_no_call():
    with patch("tools.vision_match.classify_with_images") as classify:
        kept = filter_decorative_icons([("image/png", b"only-one")])

    assert kept == [0]
    classify.assert_not_called()


def test_filter_decorative_icons_empty_list_makes_no_call():
    with patch("tools.vision_match.classify_with_images") as classify:
        kept = filter_decorative_icons([])

    assert kept == []
    classify.assert_not_called()


def test_filter_decorative_icons_drops_the_badge():
    # real case: 202512's "신규 배틀패스 헤어 출시" icon_only section
    # anchors both the real two-pose character photo and a decorative
    # PASS-ribbon badge in the same image-only row range
    images = [("image/png", b"real-content-photo"), ("image/png", b"decorative-pass-ribbon")]
    result = IconFilterResult(real_content_indices=[0])
    with patch("tools.vision_match.classify_with_images", return_value=result) as classify:
        kept = filter_decorative_icons(images)

    assert kept == [0]
    classify.assert_called_once()


def test_filter_decorative_icons_keeps_all_when_all_are_real():
    # real case: 202602's 9 real cat-hat icons, no decoration to exclude
    images = [("image/png", f"icon-{i}".encode()) for i in range(9)]
    result = IconFilterResult(real_content_indices=list(range(9)))
    with patch("tools.vision_match.classify_with_images", return_value=result):
        kept = filter_decorative_icons(images)

    assert kept == list(range(9))


def test_filter_decorative_icons_fails_open_on_classification_error():
    images = [("image/png", b"a"), ("image/png", b"b")]
    with patch("tools.vision_match.classify_with_images", side_effect=ClassificationError("boom")):
        kept = filter_decorative_icons(images)

    assert kept == [0, 1]


def test_filter_decorative_icons_fails_open_on_empty_response():
    # model returned no indices at all (e.g. misjudged everything as
    # decorative) — fail open rather than silently dropping every image
    images = [("image/png", b"a"), ("image/png", b"b")]
    result = IconFilterResult(real_content_indices=[])
    with patch("tools.vision_match.classify_with_images", return_value=result):
        kept = filter_decorative_icons(images)

    assert kept == [0, 1]


def test_filter_decorative_icons_ignores_out_of_range_index():
    images = [("image/png", b"a"), ("image/png", b"b")]
    result = IconFilterResult(real_content_indices=[0, 99])
    with patch("tools.vision_match.classify_with_images", return_value=result):
        kept = filter_decorative_icons(images)

    assert kept == [0]
