"""Block A/E (통합): N-column grid of icon/image + caption.

Icon size is a parameter, not a hardcoded type distinction — this is what
lets a single function cover both the 24x24pt small-icon grid (formerly
"A") and the 60-160pt image grid (formerly "E"). Position-based image
matching (design principle 3) happens upstream; this function only lays
out already-resolved items.
"""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_HEIGHT, Placement, paginate_by_capacity

CAPTION_HEIGHT = 17.0
GAP_X = 10.0
GAP_Y = 10.0


def grid_block(items: list[dict], columns: int = 3, icon_size: float = 24.0) -> list[list[Placement]]:
    """items: [{"name": str, "image": path|None, ...}, ...]
    Returns pages; each page is a list of Placement (icon + caption per item).
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
        pages.append(placements)
    return pages
