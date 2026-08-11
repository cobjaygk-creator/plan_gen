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
TEXT_ROW_HEIGHT = 20.0  # matches tools/blocks/text_list.py's ROW_HEIGHT


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


def _text_label(item: dict) -> str:
    name = item.get("name", "")
    return f"{name} (NEW)" if item.get("is_new") else name


def grid_with_text_overflow_block(items: list[dict], columns: int = 3, icon_size: float = 24.0) -> list[list[Placement]]:
    """Like grid_block, but an item with no image (item["image"] is falsy)
    never gets an empty image card — real request data regularly has a few
    items per section with no source image at all (real case: 202508's
    "산뜻한 소망 세트" and 3 others), and a blank card in their place reads
    as broken, not "no image available".

    Image-having items lay out exactly like grid_block, top to bottom on
    each page. Whatever vertical room is left under them (or the entire
    page, if none of this page's items have images) is packed with the
    no-image items as compact text rows instead — same visual result as
    text_list_block for a section where *no* item has an image at all, so
    this also makes the render insensitive to the AI classifier wobbling
    between "grid" and "text_list" for an image-sparse section."""
    if not items:
        return []
    if columns < 1:
        raise ValueError("columns must be >= 1")

    with_image = [i for i in items if i.get("image")]
    without_image = [i for i in items if not i.get("image")]

    cell_w = (CONTENT_WIDTH - GAP_X * (columns - 1)) / columns
    grid_row_h = icon_size + CAPTION_HEIGHT + GAP_Y
    if icon_size > CONTENT_HEIGHT or cell_w < icon_size:
        raise ValueError(
            f"icon_size={icon_size} does not fit content box "
            f"(cell_w={cell_w:.1f}, content_h={CONTENT_HEIGHT:.1f})"
        )

    grid_rows_per_page = max(1, int(CONTENT_HEIGHT // grid_row_h))
    grid_per_page = grid_rows_per_page * columns
    grid_chunks = paginate_by_capacity(with_image, grid_per_page) if with_image else [[]]

    text_queue = list(without_image)
    pages = []
    for chunk in grid_chunks:
        placements = []
        for idx, item in enumerate(chunk):
            col, row = idx % columns, idx // columns
            x = CONTENT_LEFT + col * (cell_w + GAP_X)
            y = CONTENT_TOP + row * grid_row_h
            icon_x = x + (cell_w - icon_size) / 2
            placements.append(Placement("icon", icon_x, y, icon_size, icon_size, item))
            placements.append(Placement("caption", x, y + icon_size + 2, cell_w, CAPTION_HEIGHT, item.get("name")))
            if item.get("is_new"):
                placements.append(Placement("badge", icon_x, y, min(BADGE_SIZE, icon_size), min(BADGE_SIZE, icon_size), "NEW"))
        rows_used = -(-len(chunk) // columns) if chunk else 0  # ceil division
        used_height = rows_used * grid_row_h

        remaining = CONTENT_HEIGHT - used_height
        text_capacity = max(0, int(remaining // TEXT_ROW_HEIGHT)) * columns
        text_chunk, text_queue = text_queue[:text_capacity], text_queue[text_capacity:]
        for idx, item in enumerate(text_chunk):
            col, row = idx % columns, idx // columns
            x = CONTENT_LEFT + col * (cell_w + GAP_X)
            y = CONTENT_TOP + used_height + row * TEXT_ROW_HEIGHT
            placements.append(Placement("text", x, y, cell_w, TEXT_ROW_HEIGHT, _text_label(item)))
        pages.append(placements)

    text_rows_per_page = max(1, int(CONTENT_HEIGHT // TEXT_ROW_HEIGHT))
    text_per_page = text_rows_per_page * columns
    for chunk in paginate_by_capacity(text_queue, text_per_page):
        placements = []
        for idx, item in enumerate(chunk):
            col, row = idx % columns, idx // columns
            x = CONTENT_LEFT + col * (cell_w + GAP_X)
            y = CONTENT_TOP + row * TEXT_ROW_HEIGHT
            placements.append(Placement("text", x, y, cell_w, TEXT_ROW_HEIGHT, _text_label(item)))
        pages.append(placements)

    return pages
