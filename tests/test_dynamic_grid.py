import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.blocks.dynamic_grid import fit_grid_pages, fit_grid_pages_with_text_overflow, MIN_ICON, MAX_ICON
from tools.blocks.geometry import has_any_overlap, CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM


def make_items(n, prefix="item"):
    return [{"name": f"{prefix}{i}", "image": None} for i in range(n)]


def make_items_with_images(n, prefix="item"):
    return [{"name": f"{prefix}{i}", "image": f"{prefix}{i}.png"} for i in range(n)]


def assert_within_box(placements, left, top, width, height):
    for p in placements:
        assert p.left >= left - 0.5, f"{p} left of box"
        assert p.right <= left + width + 0.5, f"{p} right of box"
        assert p.top >= top - 0.5, f"{p} above box"
        assert p.bottom <= top + height + 0.5, f"{p} below box"


def test_few_items_get_large_icons():
    pages = fit_grid_pages(make_items(2), box_left=0, box_top=0, box_width=460, box_height=460)
    assert len(pages) == 1
    icon_sizes = {round(p.width) for p in pages[0] if p.kind == "icon"}
    assert all(s > 100 for s in icon_sizes), icon_sizes  # 2 items in a big box -> big cards


def test_many_items_get_smaller_icons_same_box():
    pages_few = fit_grid_pages(make_items(2), 0, 0, 460, 460)
    pages_many = fit_grid_pages(make_items(8), 0, 0, 460, 460)
    icon_few = next(p.width for p in pages_few[0] if p.kind == "icon")
    icon_many = next(p.width for p in pages_many[0] if p.kind == "icon")
    assert icon_many < icon_few


def test_icon_size_stays_within_bounds():
    for n in (1, 2, 3, 5, 8, 12, 20):
        pages = fit_grid_pages(make_items(n), 0, 0, 460, 460)
        for page in pages:
            for p in page:
                if p.kind == "icon":
                    assert MIN_ICON - 0.5 <= p.width <= MAX_ICON + 0.5, (n, p.width)


def test_never_drops_items_across_pagination():
    items = make_items(40)
    pages = fit_grid_pages(items, 0, 0, 460, 460)
    total_icons = sum(1 for page in pages for p in page if p.kind == "icon")
    assert total_icons == 40


def test_no_overlap_at_any_item_count():
    for n in (1, 4, 9, 17, 30):
        pages = fit_grid_pages(make_items(n), 0, 0, 460, 460)
        for page in pages:
            assert not has_any_overlap(page), n


def test_empty_items_returns_no_pages():
    assert fit_grid_pages([], 0, 0, 460, 460) == []


def test_new_item_gets_a_badge():
    items = make_items(4)
    items[1]["is_new"] = True
    pages = fit_grid_pages(items, 0, 0, 460, 460)
    badges = [p for p in pages[0] if p.kind == "badge"]
    assert len(badges) == 1


def test_layout_respects_box_offset():
    pages = fit_grid_pages(make_items(2), box_left=100, box_top=50, box_width=460, box_height=460)
    for p in pages[0]:
        assert p.left >= 100 - 0.5
        assert p.top >= 50 - 0.5


# Small box (forces the hard-pagination branch reliably regardless of exact
# item count, so these tests aren't sensitive to the "maximize icon size"
# search's exact thresholds) — mirrors the real template's reward box.
BOX = (0, 0, 300, 200)


class TestFitGridPagesWithTextOverflow:
    # Real bug (202508): several items in "배틀패스 의상 교환권" legitimately
    # have no source image — fit_grid_pages still gave them an empty image
    # card, which the real render showed as a blank white box. This variant
    # packs them as compact text rows in whatever room is left instead.
    def test_no_image_items_become_text_not_empty_cards(self):
        items = make_items_with_images(4)
        items[1]["image"] = None
        items[3]["image"] = None
        pages = fit_grid_pages_with_text_overflow(items, *BOX)
        all_placements = [p for page in pages for p in page]

        icon_names = {p.ref.get("name") for p in all_placements if p.kind == "icon"}
        text_labels = {p.ref for p in all_placements if p.kind == "text"}
        assert icon_names == {"item0", "item2"}
        assert text_labels == {"item1", "item3"}

    def test_never_drops_items_mixed(self):
        items = make_items_with_images(30)
        for i in range(0, 30, 3):
            items[i]["image"] = None
        pages = fit_grid_pages_with_text_overflow(items, *BOX)
        icon_count = sum(1 for page in pages for p in page if p.kind == "icon")
        text_count = sum(1 for page in pages for p in page if p.kind == "text")
        assert icon_count == sum(1 for i in items if i["image"])
        assert text_count == sum(1 for i in items if not i["image"])

    def test_no_overlap_and_within_box_mixed(self):
        items = make_items_with_images(25)
        for i in range(0, 25, 2):
            items[i]["image"] = None
        pages = fit_grid_pages_with_text_overflow(items, *BOX)
        for page in pages:
            assert not has_any_overlap(page)
            assert_within_box(page, *BOX)

    def test_all_items_have_images_matches_plain_fit_grid_pages(self):
        items = make_items_with_images(12)
        assert fit_grid_pages_with_text_overflow(items, *BOX) == fit_grid_pages(items, *BOX)

    def test_no_items_have_images_reads_like_a_text_list(self):
        # AI classifier wobbling between grid/text_list for an all-text
        # section must not change the visible result.
        items = make_items_with_images(6)
        for i in items:
            i["image"] = None
        pages = fit_grid_pages_with_text_overflow(items, *BOX)
        assert all(p.kind == "text" for page in pages for p in page)
        assert sum(len(p) for p in pages) == 6

    def test_empty_items_returns_no_pages(self):
        assert fit_grid_pages_with_text_overflow([], *BOX) == []

    def test_new_no_image_item_gets_suffix_not_a_badge(self):
        items = make_items_with_images(2)
        items[1]["image"] = None
        items[1]["is_new"] = True
        pages = fit_grid_pages_with_text_overflow(items, *BOX)
        all_placements = [p for page in pages for p in page]
        assert "item1 (NEW)" in [p.ref for p in all_placements if p.kind == "text"]
        assert sum(1 for p in all_placements if p.kind == "badge") == 0
