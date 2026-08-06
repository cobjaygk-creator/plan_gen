import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.blocks import (
    grid_block, text_list_block, new_highlight_block,
    few_preview_block, paired_columns_block, has_any_overlap,
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


class TestNewHighlightBlock:
    def test_two_new_cards_plus_rest(self):
        new_items = make_items(2, "new")
        rest = make_items(10, "rest")
        pages = new_highlight_block(new_items, rest)
        assert len(pages) >= 1
        assert not has_any_overlap(pages[0])  # badges vs image ignored by default
        assert_within_content_box(pages[0])
        # 2 new items x 3 placements (image+badge+caption) present on first page
        assert sum(1 for p in pages[0] if p.kind == "badge") == 2

    def test_rejects_too_many_new_items(self):
        with pytest.raises(ValueError):
            new_highlight_block(make_items(3, "new"), [])

    def test_rest_overflow_spills_to_plain_pages(self):
        pages = new_highlight_block(make_items(1, "new"), make_items(80, "rest"))
        assert len(pages) > 1
        for page in pages[1:]:
            assert all(p.kind != "badge" for p in page)
            assert not has_any_overlap(page)


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
            sub_items=make_items(4, "sub"),
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
            paired_columns_block(make_items(2, "set"), sub_items=make_items(200, "sub"))
