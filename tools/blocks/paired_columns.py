"""Block D: 2 compared sets (image+caption side by side) + an optional
sub-item text list + a footnote line (e.g. "아래 패션 세트 중 택 1").
Matches 202503/202509/202512 slide 7 pattern.
"""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM, Placement

PAIR_GAP_X = 20.0
PAIR_HEIGHT_RATIO = 0.55  # of box height, so a bigger box (e.g. a template
                          # blue marker) gives bigger pair images too, not
                          # just a fixed 150pt regardless of available room
PAIR_HEIGHT_MIN = 100.0
PAIR_HEIGHT_MAX = 260.0
PAIR_CAPTION_HEIGHT = 20.0
SUB_ROW_HEIGHT = 18.0
SUB_COLUMNS = 3
SUB_GAP_X = 10.0
FOOTNOTE_HEIGHT = 16.0


def paired_columns_block(
    pair_items: list[dict], sub_items: list[dict] | None = None, footnote: str | None = None,
    box: tuple[float, float, float, float] | None = None,
) -> list[list[Placement]]:
    """box: optional (left, top, width, height) override, e.g. a
    template.pptx blue marker's bbox — defaults to the module-level
    CONTENT_* box for callers that don't have one."""
    if len(pair_items) != 2:
        raise ValueError(f"paired_columns_block expects exactly 2 pair_items, got {len(pair_items)}")

    left, top, width, height = box if box else (CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM - CONTENT_TOP)
    bottom = top + height
    pair_height = min(PAIR_HEIGHT_MAX, max(PAIR_HEIGHT_MIN, height * PAIR_HEIGHT_RATIO))

    placements = []
    cell_w = (width - PAIR_GAP_X) / 2
    for idx, item in enumerate(pair_items):
        x = left + idx * (cell_w + PAIR_GAP_X)
        placements.append(Placement("image", x, top, cell_w, pair_height, item))
        placements.append(Placement("caption", x, top + pair_height, cell_w, PAIR_CAPTION_HEIGHT, item.get("name")))

    cursor_y = top + pair_height + PAIR_CAPTION_HEIGHT + 10.0

    if sub_items:
        sub_cell_w = (width - SUB_GAP_X * (SUB_COLUMNS - 1)) / SUB_COLUMNS
        rows_avail = int((bottom - FOOTNOTE_HEIGHT - cursor_y) // SUB_ROW_HEIGHT)
        capacity = max(0, rows_avail * SUB_COLUMNS)
        if len(sub_items) > capacity:
            raise ValueError(
                f"paired_columns_block: {len(sub_items)} sub_items exceed capacity {capacity} "
                "for this page — design doc doesn't define pagination for block D, escalate"
            )
        for idx, item in enumerate(sub_items):
            col = idx % SUB_COLUMNS
            row = idx // SUB_COLUMNS
            x = left + col * (sub_cell_w + SUB_GAP_X)
            y = cursor_y + row * SUB_ROW_HEIGHT
            placements.append(Placement("text", x, y, sub_cell_w, SUB_ROW_HEIGHT, item.get("name")))
        cursor_y += (((len(sub_items) - 1) // SUB_COLUMNS) + 1) * SUB_ROW_HEIGHT if sub_items else 0

    if footnote:
        # right after wherever the actual content ended (pair captions, or
        # sub_items if present) — NOT pinned to the box bottom, which left
        # a large dead gap and made the footnote look stranded at the very
        # bottom whenever there were no sub_items (the common case)
        y = min(cursor_y + 10.0, bottom - FOOTNOTE_HEIGHT)
        placements.append(Placement("text", left, y, width, FOOTNOTE_HEIGHT, footnote))

    return [placements]
