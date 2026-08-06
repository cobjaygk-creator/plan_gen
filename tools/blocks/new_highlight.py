"""Block B': 1-2 NEW-badged image cards on top + remaining items as a plain
text list below (block B), all within the same content box. Matches
202605 slide 8 ("발레코어 소프트 의상 세트 I/II" + NEW badge + rest list).

Only the first page carries the NEW cards; overflow of rest_items spills
onto plain text-list-only pages (design doesn't specify repeating the
cards on continuation pages, and doing so would just eat capacity).
"""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM, Placement, paginate_by_capacity

CARD_HEIGHT = 145.0
CARD_GAP = 10.0
BADGE_SIZE = 24.0
LIST_ROW_HEIGHT = 20.0
LIST_GAP_X = 10.0
LIST_COLUMNS = 3


def _card_placements(new_items: list[dict]) -> list[Placement]:
    if not (1 <= len(new_items) <= 2):
        raise ValueError("new_highlight_block expects 1-2 NEW items, got %d" % len(new_items))
    n = len(new_items)
    card_w = (CONTENT_WIDTH - CARD_GAP * (n - 1)) / n
    placements = []
    for idx, item in enumerate(new_items):
        x = CONTENT_LEFT + idx * (card_w + CARD_GAP)
        placements.append(Placement("image", x, CONTENT_TOP, card_w, CARD_HEIGHT, item))
        placements.append(Placement("badge", x, CONTENT_TOP, BADGE_SIZE, BADGE_SIZE, "NEW"))
        placements.append(Placement("caption", x, CONTENT_TOP + CARD_HEIGHT, card_w, 17.0, item.get("name")))
    return placements


def _list_page(chunk: list[dict], top: float, bottom: float) -> list[Placement]:
    cell_w = (CONTENT_WIDTH - LIST_GAP_X * (LIST_COLUMNS - 1)) / LIST_COLUMNS
    placements = []
    for idx, item in enumerate(chunk):
        col = idx % LIST_COLUMNS
        row = idx // LIST_COLUMNS
        x = CONTENT_LEFT + col * (cell_w + LIST_GAP_X)
        y = top + row * LIST_ROW_HEIGHT
        if y + LIST_ROW_HEIGHT > bottom:
            raise ValueError("list chunk does not fit page — reduce per_page upstream")
        placements.append(Placement("text", x, y, cell_w, LIST_ROW_HEIGHT, item.get("name")))
    return placements


def new_highlight_block(new_items: list[dict], rest_items: list[dict]) -> list[list[Placement]]:
    pages = []

    first_page = _card_placements(new_items)
    list_top_first = CONTENT_TOP + CARD_HEIGHT + 17.0 + CARD_GAP
    remaining_h_first = CONTENT_BOTTOM - list_top_first
    rows_first = max(0, int(remaining_h_first // LIST_ROW_HEIGHT))
    per_page_first = rows_first * LIST_COLUMNS

    full_rows = max(1, int((CONTENT_BOTTOM - CONTENT_TOP) // LIST_ROW_HEIGHT))
    per_page_full = full_rows * LIST_COLUMNS

    if per_page_first > 0 and rest_items:
        first_chunk, remainder = rest_items[:per_page_first], rest_items[per_page_first:]
        first_page += _list_page(first_chunk, list_top_first, CONTENT_BOTTOM)
        pages.append(first_page)
        for chunk in paginate_by_capacity(remainder, per_page_full):
            pages.append(_list_page(chunk, CONTENT_TOP, CONTENT_BOTTOM))
    else:
        pages.append(first_page)
        for chunk in paginate_by_capacity(rest_items, per_page_full):
            pages.append(_list_page(chunk, CONTENT_TOP, CONTENT_BOTTOM))

    return pages
