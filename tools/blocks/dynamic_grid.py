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
# Real user comparison (2026-08-11): a from-scratch reference render sized
# its cards ~65-83pt even on a 9-items-per-page layout, vs. this fitter's
# old MIN_ICON=50 floor (which the "always use the smallest reward slot as
# the shared reference box" pagination policy in render_from_template.py
# hits often — see that module's docstring — so 50 wasn't a rare fallback,
# it was the common case). Raised the floor so cards stay reference-sized;
# a page that no longer fits just paginates into more slides instead of
# shrinking, same as before.
MIN_ICON = 65.0
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


TEXT_ROW_HEIGHT = 24.0  # compact row for no-image items sharing a page with the image grid


def _text_rows(items, box_left, top, box_width, cols, row_height=TEXT_ROW_HEIGHT):
    cell_w = (box_width - GAP * (cols - 1)) / cols
    placements = []
    for idx, item in enumerate(items):
        col, row = idx % cols, idx // cols
        x = box_left + col * (cell_w + GAP)
        y = top + row * (row_height + GAP)
        label = item.get("name", "")
        if item.get("is_new"):
            label += " (NEW)"
        placements.append(Placement("text", x, y, cell_w, row_height, label))
    return placements


TEXT_COLUMNS = 3  # independent of however many columns the image grid above
                   # used — real case: a page with just 1 image picks 1
                   # wide column to maximize icon size (see fit_grid_pages),
                   # but text rows are narrow single lines and packing them
                   # into that same lone column wasted 2/3 of the box width,
                   # fitting far fewer text items per page than the room
                   # actually allowed.


def fit_grid_pages_with_text_overflow(
    items: list[dict], box_left: float, box_top: float, box_width: float, box_height: float,
) -> list[list[Placement]]:
    """Like fit_grid_pages, but an item with no image (item["image"] is
    falsy) never gets an empty image card — real request data regularly
    has a few items per section with no source image at all (real case:
    202508's "산뜻한 소망 세트" and 3 others), and a blank card in their
    place reads as broken rather than "no image available".

    Image-having items are laid out exactly as fit_grid_pages would (that
    function is reused unchanged — this only reads its output, never
    modifies its behavior). Whatever vertical room is left under the
    lowest placement on each resulting page is packed with the no-image
    items as compact text rows instead; leftovers spill onto their own
    text-only page(s), same layout a pure text_list would use."""
    with_image = [i for i in items if i.get("image")]
    without_image = [i for i in items if not i.get("image")]
    if not with_image and not without_image:
        return []

    image_pages = fit_grid_pages(with_image, box_left, box_top, box_width, box_height) if with_image else []

    text_queue = list(without_image)
    pages = []
    box_bottom = box_top + box_height
    for page in image_pages:
        used_bottom = max((p.bottom for p in page), default=box_top)
        available = box_bottom - used_bottom - GAP
        capacity = (max(0, int(available // (TEXT_ROW_HEIGHT + GAP))) * TEXT_COLUMNS) if available > 0 else 0
        chunk, text_queue = text_queue[:capacity], text_queue[capacity:]
        pages.append(page + _text_rows(chunk, box_left, used_bottom + GAP, box_width, TEXT_COLUMNS))

    rows_per_page = max(1, int((box_height + GAP) // (TEXT_ROW_HEIGHT + GAP)))
    per_page = rows_per_page * TEXT_COLUMNS
    for start in range(0, len(text_queue), per_page):
        chunk = text_queue[start:start + per_page]
        pages.append(_text_rows(chunk, box_left, box_top, box_width, TEXT_COLUMNS))

    return pages
