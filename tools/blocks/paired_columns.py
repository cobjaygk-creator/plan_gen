"""Block D: 2 compared sets (image+caption side by side) + an optional
sub-item text list + a footnote line (e.g. "아래 패션 세트 중 택 1").
Matches 202503/202509/202512 slide 7 pattern.
"""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM, Placement

PAIR_GAP_X = 20.0
PAIR_HEIGHT = 150.0
PAIR_CAPTION_HEIGHT = 20.0
SUB_ROW_HEIGHT = 18.0
SUB_COLUMNS = 3
SUB_GAP_X = 10.0
FOOTNOTE_HEIGHT = 16.0


def paired_columns_block(pair_items: list[dict], sub_items: list[dict] | None = None,
                          footnote: str | None = None) -> list[list[Placement]]:
    if len(pair_items) != 2:
        raise ValueError(f"paired_columns_block expects exactly 2 pair_items, got {len(pair_items)}")

    placements = []
    cell_w = (CONTENT_WIDTH - PAIR_GAP_X) / 2
    for idx, item in enumerate(pair_items):
        x = CONTENT_LEFT + idx * (cell_w + PAIR_GAP_X)
        placements.append(Placement("image", x, CONTENT_TOP, cell_w, PAIR_HEIGHT, item))
        placements.append(Placement("caption", x, CONTENT_TOP + PAIR_HEIGHT, cell_w, PAIR_CAPTION_HEIGHT, item.get("name")))

    cursor_y = CONTENT_TOP + PAIR_HEIGHT + PAIR_CAPTION_HEIGHT + 10.0

    if sub_items:
        sub_cell_w = (CONTENT_WIDTH - SUB_GAP_X * (SUB_COLUMNS - 1)) / SUB_COLUMNS
        rows_avail = int((CONTENT_BOTTOM - FOOTNOTE_HEIGHT - cursor_y) // SUB_ROW_HEIGHT)
        capacity = max(0, rows_avail * SUB_COLUMNS)
        if len(sub_items) > capacity:
            raise ValueError(
                f"paired_columns_block: {len(sub_items)} sub_items exceed capacity {capacity} "
                "for this page — design doc doesn't define pagination for block D, escalate"
            )
        for idx, item in enumerate(sub_items):
            col = idx % SUB_COLUMNS
            row = idx // SUB_COLUMNS
            x = CONTENT_LEFT + col * (sub_cell_w + SUB_GAP_X)
            y = cursor_y + row * SUB_ROW_HEIGHT
            placements.append(Placement("text", x, y, sub_cell_w, SUB_ROW_HEIGHT, item.get("name")))
        cursor_y += (((len(sub_items) - 1) // SUB_COLUMNS) + 1) * SUB_ROW_HEIGHT if sub_items else 0

    if footnote:
        # right after wherever the actual content ended (pair captions, or
        # sub_items if present) — NOT pinned to CONTENT_BOTTOM, which left
        # a large dead gap and made the footnote look stranded at the very
        # bottom whenever there were no sub_items (the common case)
        y = min(cursor_y + 10.0, CONTENT_BOTTOM - FOOTNOTE_HEIGHT)
        placements.append(Placement("text", CONTENT_LEFT, y, CONTENT_WIDTH, FOOTNOTE_HEIGHT, footnote))

    return [placements]
