import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.blocks.dynamic_grid import fit_grid_pages, MIN_ICON, MAX_ICON
from tools.blocks.geometry import has_any_overlap


def make_items(n, prefix="item"):
    return [{"name": f"{prefix}{i}", "image": None} for i in range(n)]


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
