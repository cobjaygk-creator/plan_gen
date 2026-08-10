"""Block F: images with no item names at all — real case: 202602's
"[이벤트] 고양이 모자 선택권", 9 cat-hat icons anchored as one combined
picture under a title + "···중 택1" footnote, with zero item text anywhere
(extract_special_reward_rows() used to drop rows like this entirely, so the
classifier never even knew this content existed — see its docstring).

No AI item-name matching happens for this block type at all — pipeline.py
gathers whichever images are anchored in the section's row range directly
and hands them here as plain {"image": path} dicts, no "name" key needed.
Same box-fitting approach as dynamic_grid.fit_grid_pages, just without a
caption row under each icon.
"""
import math
from .geometry import Placement

GAP = 12.0
MIN_ICON = 50.0
MAX_ICON = 200.0
MAX_COLUMNS_TRIED = 6


def _layout_page(items, box_left, box_top, cols, cell_w, cell_h, icon_size):
    placements = []
    for idx, item in enumerate(items):
        col = idx % cols
        row = idx // cols
        cx = box_left + col * (cell_w + GAP)
        cy = box_top + row * (cell_h + GAP)
        icon_x = cx + (cell_w - icon_size) / 2
        icon_y = cy + (cell_h - icon_size) / 2
        placements.append(Placement("icon", icon_x, icon_y, icon_size, icon_size, item))
    return placements


def icon_only_block(
    items: list[dict], box: tuple[float, float, float, float],
) -> list[list[Placement]]:
    """items: [{"image": path_or_None}, ...] — no "name" key expected or used.
    box is required (left, top, width, height); unlike most other block
    functions here there's no module-level CONTENT_* fallback, since this
    block type only exists to be driven by pipeline.py's row-range image
    scan, which always has a real box to work with."""
    box_left, box_top, box_width, box_height = box
    n = len(items)
    if n == 0:
        raise ValueError("icon_only_block expects at least 1 image, got 0")

    best = None  # (icon_size, cols, cell_w, cell_h)
    for cols in range(1, MAX_COLUMNS_TRIED + 1):
        rows = math.ceil(n / cols)
        cell_w = (box_width - GAP * (cols - 1)) / cols
        cell_h = (box_height - GAP * (rows - 1)) / rows
        icon = min(cell_w, cell_h)
        if icon < MIN_ICON:
            continue
        icon = min(icon, MAX_ICON)
        if best is None or icon > best[0]:
            best = (icon, cols, cell_w, cell_h)

    if best is not None:
        icon_size, cols, cell_w, cell_h = best
        return [_layout_page(items, box_left, box_top, cols, cell_w, cell_h, icon_size)]

    # doesn't fit on one page even at MIN_ICON — paginate, same policy as
    # fit_grid_pages: never shrink below readable, overflow goes to the next page
    cols = 3
    icon_size = MIN_ICON
    cell_h = icon_size
    cell_w = (box_width - GAP * (cols - 1)) / cols
    rows_per_page = max(1, int((box_height + GAP) // (cell_h + GAP)))
    per_page = rows_per_page * cols

    pages = []
    for start in range(0, n, per_page):
        chunk = items[start:start + per_page]
        pages.append(_layout_page(chunk, box_left, box_top, cols, cell_w, cell_h, icon_size))
    return pages
