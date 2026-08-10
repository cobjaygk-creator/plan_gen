import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.blocks import (
    grid_block, text_list_block,
    few_preview_block, paired_columns_block, icon_only_block, has_any_overlap,
    CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM,
)


def make_items(n, prefix="item"):
    return [{"name": f"{prefix}{i}", "image": f"{prefix}{i}.png"} for i in range(n)]


def assert_within_content_box(placements):
    for p in placements:
        assert p.left >= CONTENT_LEFT - 0.5, f"{p} left of content box"
        assert p.right <= CONTENT_LEFT + CONTENT_WIDTH + 0.5, f"{p} right of content box"
        assert p.top >= CONTENT_TOP - 0.5, f"{p} above content box"
        assert p.bottom <= CONTENT_BOTTOM + 0.5, f"{p} below content box"


class TestGridBlock:
    def test_small_icon_grid_single_page(self):
        pages = grid_block(make_items(6), columns=3, icon_size=24.0)
        assert len(pages) == 1
        assert len(pages[0]) == 12  # icon + caption per item
        assert not has_any_overlap(pages[0])
        assert_within_content_box(pages[0])

    def test_large_icon_grid_paginates(self):
        # icon_size big enough that only a few rows fit per page
        pages = grid_block(make_items(20), columns=3, icon_size=120.0)
        assert len(pages) > 1
        total_items = sum(len(p) // 2 for p in pages)
        assert total_items == 20
        for page in pages:
            assert not has_any_overlap(page)
            assert_within_content_box(page)

    def test_icon_too_big_raises(self):
        with pytest.raises(ValueError):
            grid_block(make_items(3), columns=3, icon_size=1000.0)

    def test_never_drops_items(self):
        items = make_items(37)
        pages = grid_block(items, columns=3, icon_size=24.0)
        seen = sum(len(p) // 2 for p in pages)
        assert seen == 37


class TestTextListBlock:
    def test_fits_one_page(self):
        pages = text_list_block(make_items(9), columns=3)
        assert len(pages) == 1
        assert not has_any_overlap(pages[0])
        assert_within_content_box(pages[0])

    def test_overflow_paginates_without_loss(self):
        items = make_items(100)
        pages = text_list_block(items, columns=3)
        assert len(pages) > 1
        assert sum(len(p) for p in pages) == 100
        for page in pages:
            assert not has_any_overlap(page)

    def test_new_item_gets_suffix_since_there_is_no_icon_to_badge(self):
        items = make_items(3)
        items[1]["is_new"] = True
        pages = text_list_block(items, columns=3)
        texts = [p.ref for p in pages[0]]
        assert "item1 (NEW)" in texts
        assert "item0" in texts and "item0 (NEW)" not in texts


class TestGridBlockNewBadge:
    # "new_highlight" (B') merged into grid_block after 202512 real-data
    # evidence showed NEW items sit in a normal grid cell + small badge,
    # not a separately-sized highlight card (see tools/blocks/grid.py).
    def test_new_item_gets_a_badge(self):
        items = make_items(6)
        items[2]["is_new"] = True
        pages = grid_block(items, columns=3, icon_size=24.0)
        assert sum(1 for p in pages[0] if p.kind == "badge") == 1

    def test_no_badges_when_nothing_is_new(self):
        pages = grid_block(make_items(6), columns=3, icon_size=24.0)
        assert sum(1 for p in pages[0] if p.kind == "badge") == 0

    def test_badge_does_not_count_as_content_overlap(self):
        items = make_items(6)
        items[0]["is_new"] = True
        pages = grid_block(items, columns=3, icon_size=24.0)
        assert not has_any_overlap(pages[0])  # badge intentionally overlays its icon corner


class TestFewPreviewBlock:
    def test_single_item(self):
        pages = few_preview_block(make_items(1))
        assert len(pages) == 1
        assert not has_any_overlap(pages[0])
        assert_within_content_box(pages[0])

    def test_three_items_no_overlap(self):
        pages = few_preview_block(make_items(3))
        assert not has_any_overlap(pages[0])
        assert_within_content_box(pages[0])

    def test_rejects_more_than_three(self):
        with pytest.raises(ValueError):
            few_preview_block(make_items(4))

    def test_rejects_zero(self):
        with pytest.raises(ValueError):
            few_preview_block([])


class TestPairedColumnsBlock:
    def test_basic_pair_with_footnote(self):
        pages = paired_columns_block(
            make_items(2, "set"),
            footnote="아래 패션 세트 중 택 1 (거래불가)",
        )
        assert len(pages) == 1
        assert not has_any_overlap(pages[0])
        assert_within_content_box(pages[0])

    def test_rejects_wrong_pair_count(self):
        with pytest.raises(ValueError):
            paired_columns_block(make_items(1))
        with pytest.raises(ValueError):
            paired_columns_block(make_items(3))

    def test_sub_items_over_capacity_raises(self):
        with pytest.raises(ValueError):
            paired_columns_block(
                make_items(2, "set"),
                sub_items_by_pair=(make_items(200, "sub"), []),
            )

    def test_per_pair_sub_lists_no_overlap(self):
        pages = paired_columns_block(
            make_items(2, "set"),
            sub_items_by_pair=(make_items(6, "sub0"), make_items(4, "sub1")),
            footnote="자켓 세트는 연미복과 자켓/바지로 나뉘어 3종이 전부 지급됩니다.",
        )
        assert len(pages) == 1
        assert not has_any_overlap(pages[0])
        assert_within_content_box(pages[0])

    def test_card_frame_grows_with_sub_item_count(self):
        # real bug: the card around each pair used to be a fixed size that
        # only wrapped the portrait image, leaving the sub-item list to
        # float below it with no border — the frame must stretch to
        # actually contain however much content ends up in that column.
        short_pages = paired_columns_block(
            make_items(2, "set"), sub_items_by_pair=(make_items(2, "sub0"), make_items(2, "sub1")),
        )
        long_pages = paired_columns_block(
            make_items(2, "set"), sub_items_by_pair=(make_items(8, "sub0"), make_items(8, "sub1")),
        )
        short_frame = next(p for p in short_pages[0] if p.kind == "frame")
        long_frame = next(p for p in long_pages[0] if p.kind == "frame")
        assert long_frame.height > short_frame.height

    def test_sub_items_are_always_plain_text_never_icons(self):
        # sub-items never attempt image matching at the pipeline level (see
        # tools/pipeline.py's paired_columns handling) — the single portrait
        # per set represents the whole set, so even a sub_item dict that
        # happens to carry an "image" key must not turn into an icon here.
        pages = paired_columns_block(
            make_items(2, "set"),
            sub_items_by_pair=(make_items(3, "sub0"), make_items(3, "sub1")),
        )
        assert not any(p.kind == "icon" for p in pages[0])
        text_kinds = [p for p in pages[0] if p.kind == "text"]
        assert len(text_kinds) == 6
        assert not has_any_overlap(pages[0])
        assert_within_content_box(pages[0])


class TestIconOnlyBlock:
    BOX = (CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM - CONTENT_TOP)

    def test_single_image_no_caption(self):
        # real case: 202602's 9 cat-hat icons are one combined picture, so
        # a single-image icon_only section is the common real shape
        pages = icon_only_block([{"image": "cat.png"}], box=self.BOX)
        assert len(pages) == 1
        assert len(pages[0]) == 1
        assert pages[0][0].kind == "icon"
        assert not any(p.kind == "caption" for p in pages[0])

    def test_multiple_images_grid_no_overlap(self):
        items = [{"image": f"icon{i}.png"} for i in range(9)]
        pages = icon_only_block(items, box=self.BOX)
        assert not has_any_overlap(pages[0])
        assert len(pages[0]) == 9
        for p in pages[0]:
            assert p.kind == "icon"

    def test_rejects_zero_images(self):
        with pytest.raises(ValueError):
            icon_only_block([], box=self.BOX)

    def test_paginates_when_too_many_for_one_page(self):
        items = [{"image": f"icon{i}.png"} for i in range(60)]
        pages = icon_only_block(items, box=self.BOX)
        assert len(pages) > 1
        assert sum(len(p) for p in pages) == 60
        for page in pages:
            assert not has_any_overlap(page)
