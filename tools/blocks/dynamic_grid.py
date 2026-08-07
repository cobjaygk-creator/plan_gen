"""Box-fitting grid layout: given a target bounding box (usually a
template.pptx blue marker's bbox) and a list of items, pick the column
count and icon size that best fill the box — fewer items get bigger
cards, more items get more columns/smaller cards — instead of a single
fixed icon_size like the original grid_block. Built after real user
feedback comparing against a reference render: fixed 24pt icons looked
cramped regardless of how much room was actually available.

Still returns tools.blocks.geometry.Placement lists, so it's a drop-in
for anything that already consumes grid_block's output (has_any_overlap,
the renderer, etc).
"""
import math
from .geometry import Placement

CAPTION_HEIGHT = 34.0
GAP = 12.0
MIN_ICON = 50.0
MAX_ICON = 200.0
BADGE_SIZE = 20.0
MAX_COLUMNS_TRIED = 6


def _layout_page(items, box_left, box_top, cols, cell_w, cell_h, icon_size):
    placements = []
    for idx, item in enumerate(items):
        col = idx % cols
        row = idx // cols
        cx = box_left + col * (cell_w + GAP)
        cy = box_top + row * (cell_h + GAP)
        icon_x = cx + (cell_w - icon_size) / 2
        placements.append(Placement("icon", icon_x, cy, icon_size, icon_size, item))
        placements.append(Placement(
            "caption", cx, cy + icon_size + 4, cell_w, CAPTION_HEIGHT - 4, item.get("name")
        ))
        if item.get("is_new"):
            placements.append(Placement("badge", icon_x, cy, BADGE_SIZE, BADGE_SIZE, "NEW"))
    return placements


def fit_grid_pages(
    items: list[dict], box_left: float, box_top: float, box_width: float, box_height: float,
) -> list[list[Placement]]:
    n = len(items)
    if n == 0:
        return []

    best = None  # (icon_size, cols, cell_w, cell_h)
    for cols in range(1, MAX_COLUMNS_TRIED + 1):
        rows = math.ceil(n / cols)
        cell_w = (box_width - GAP * (cols - 1)) / cols
        cell_h = (box_height - GAP * (rows - 1)) / rows
        icon = min(cell_w, cell_h - CAPTION_HEIGHT)
        if icon < MIN_ICON:
            continue
        icon = min(icon, MAX_ICON)
        if best is None or icon > best[0]:
            best = (icon, cols, cell_w, cell_h)

    if best is not None:
        icon_size, cols, cell_w, cell_h = best
        return [_layout_page(items, box_left, box_top, cols, cell_w, cell_h, icon_size)]

    # Doesn't fit on one page even at MIN_ICON — paginate (design principle:
    # never shrink below readable, never overlap; overflow goes to the next
    # page instead).
    cols = 3
    icon_size = MIN_ICON
    cell_h = icon_size + CAPTION_HEIGHT
    cell_w = (box_width - GAP * (cols - 1)) / cols
    rows_per_page = max(1, int((box_height + GAP) // (cell_h + GAP)))
    per_page = rows_per_page * cols

    pages = []
    for start in range(0, n, per_page):
        chunk = items[start:start + per_page]
        pages.append(_layout_page(chunk, box_left, box_top, cols, cell_w, cell_h, icon_size))
    return pages
