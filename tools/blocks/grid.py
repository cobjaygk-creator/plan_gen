"""Block A/E (통합): N-column grid of icon/image + caption.

Icon size is a parameter, not a hardcoded type distinction — this is what
lets a single function cover both the 24x24pt small-icon grid (formerly
"A") and the 60-160pt image grid (formerly "E"). Position-based image
matching (design principle 3) happens upstream; this function only lays
out already-resolved items.

Also covers what was originally a separate "new_highlight" (B') block:
real data (202512's "FX 타이틀 교환권") showed NEW-flagged items sitting in
the *same* grid cell size as everything else with just a small badge, not
a separately-sized oversized card — the old new_highlight_block's "2 big
cards + plain-text-only rest" layout was overfit to a single 202605
example and produced a badly wrong result on other months. items may
carry an "is_new" key (bool); those get a badge, and an item with no
image gets an "이미지 추후 전달 예정" placeholder if is_new else just an
empty card (matches source data: a genuinely new item explains its own
missing art, an ordinary item with no image is just missing one).
"""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_HEIGHT, Placement, paginate_by_capacity

CAPTION_HEIGHT = 17.0
GAP_X = 10.0
GAP_Y = 10.0
BADGE_SIZE = 16.0


def grid_block(items: list[dict], columns: int = 3, icon_size: float = 24.0) -> list[list[Placement]]:
    """items: [{"name": str, "image": path|None, "is_new": bool}, ...]
    Returns pages; each page is a list of Placement (icon + caption, plus
    badge/placeholder-text as applicable, per item).
    Raises ValueError if a single cell doesn't fit the content box at all.
    """
    if columns < 1:
        raise ValueError("columns must be >= 1")

    cell_w = (CONTENT_WIDTH - GAP_X * (columns - 1)) / columns
    row_h = icon_size + CAPTION_HEIGHT + GAP_Y
    if icon_size > CONTENT_HEIGHT or cell_w < icon_size:
        raise ValueError(
            f"icon_size={icon_size} does not fit content box "
            f"(cell_w={cell_w:.1f}, content_h={CONTENT_HEIGHT:.1f})"
        )

    rows_per_page = max(1, int(CONTENT_HEIGHT // row_h))
    per_page = rows_per_page * columns

    pages = []
    for chunk in paginate_by_capacity(items, per_page):
        placements = []
        for idx, item in enumerate(chunk):
            col = idx % columns
            row = idx // columns
            x = CONTENT_LEFT + col * (cell_w + GAP_X)
            y = CONTENT_TOP + row * row_h
            icon_x = x + (cell_w - icon_size) / 2
            placements.append(Placement("icon", icon_x, y, icon_size, icon_size, item))
            placements.append(Placement("caption", x, y + icon_size + 2, cell_w, CAPTION_HEIGHT, item.get("name")))
            if item.get("is_new"):
                placements.append(Placement("badge", icon_x, y, min(BADGE_SIZE, icon_size), min(BADGE_SIZE, icon_size), "NEW"))
        pages.append(placements)
    return pages
