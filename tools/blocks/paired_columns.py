"""Block D: 2 compared sets (image+caption side by side), each with its
own sub-item list stacked directly underneath its own image — not one
shared list spanning both columns. Matches the real reference sample
(202606 "배틀패스 신규 의상": 자켓 세트/치마 세트 portraits, each with its
own ~6-item component list below it) and the simpler 202503/202509/202512
case (2 sets + a shared footnote, no sub-items at all).
"""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM, Placement

PAIR_GAP_X = 20.0
PAIR_HEIGHT_RATIO = 0.55  # of box height, used only when there are no
                          # sub-items (the simple 2-set-compare case) — a
                          # bigger box then gives bigger pair images too
PAIR_HEIGHT_WITH_SUBLIST_RATIO = 0.35  # smaller portrait when a per-set
                                        # sub-item list also has to fit
                                        # in the same column underneath
PAIR_HEIGHT_MIN = 90.0
PAIR_HEIGHT_MAX = 260.0
PAIR_CAPTION_HEIGHT = 20.0
SUB_ROW_HEIGHT = 18.0
CARD_BOTTOM_PAD = 8.0  # card frame grows this much past the last row it wraps
FOOTNOTE_LINE_HEIGHT = 14.0


def paired_columns_block(
    pair_items: list[dict],
    sub_items_by_pair: tuple[list[dict], list[dict]] | None = None,
    footnote: str | None = None,
    box: tuple[float, float, float, float] | None = None,
) -> list[list[Placement]]:
    """box: optional (left, top, width, height) override, e.g. a
    template.pptx blue marker's bbox — defaults to the module-level
    CONTENT_* box for callers that don't have one.
    sub_items_by_pair: optional (sub_items_for_pair_items[0], sub_items_for_pair_items[1]) —
    each pair item's own component list, rendered in a single column
    directly under that pair's image. None/empty tuple = no sub-lists
    (the simpler "just compare 2 sets + footnote" case)."""
    if len(pair_items) != 2:
        raise ValueError(f"paired_columns_block expects exactly 2 pair_items, got {len(pair_items)}")

    left, top, width, height = box if box else (CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM - CONTENT_TOP)
    bottom = top + height
    has_sublists = bool(sub_items_by_pair) and any(sub_items_by_pair)
    ratio = PAIR_HEIGHT_WITH_SUBLIST_RATIO if has_sublists else PAIR_HEIGHT_RATIO
    pair_height = min(PAIR_HEIGHT_MAX, max(PAIR_HEIGHT_MIN, height * ratio))

    footnote_lines = footnote.count("\n") + 1 if footnote else 0
    footnote_height = footnote_lines * FOOTNOTE_LINE_HEIGHT

    placements = []
    cell_w = (width - PAIR_GAP_X) / 2
    cursor_ys = []
    for idx, item in enumerate(pair_items):
        x = left + idx * (cell_w + PAIR_GAP_X)
        pair_placements = [
            # no_frame: the wrapping card (added below, once its height is
            # known) already gives this column a border — a second border
            # just around the portrait would double up against it
            Placement("image", x, top, cell_w, pair_height, item, meta={"no_frame": True}),
            Placement("caption", x, top + pair_height, cell_w, PAIR_CAPTION_HEIGHT, item.get("name")),
        ]
        cursor_y = top + pair_height + PAIR_CAPTION_HEIGHT + 8.0

        sub_items = sub_items_by_pair[idx] if sub_items_by_pair and idx < len(sub_items_by_pair) else None
        if sub_items:
            rows_avail = int((bottom - footnote_height - cursor_y) // SUB_ROW_HEIGHT)
            if len(sub_items) > max(0, rows_avail):
                raise ValueError(
                    f"paired_columns_block: pair {idx} has {len(sub_items)} sub_items, "
                    f"only {max(0, rows_avail)} rows available — design doc doesn't define "
                    "pagination for block D, escalate"
                )
            # always plain centered text, never a per-item icon — sub-items
            # never attempt image matching at the pipeline level (see
            # tools/pipeline.py's paired_columns handling), and both the
            # human-made reference sample and the user's own edited version
            # of a generated file show the sub-list as text only, with the
            # single portrait image being what represents the whole set
            for row, sub_item in enumerate(sub_items):
                y = cursor_y + row * SUB_ROW_HEIGHT
                pair_placements.append(Placement("text", x, y, cell_w, SUB_ROW_HEIGHT, sub_item.get("name")))
            cursor_y += len(sub_items) * SUB_ROW_HEIGHT
        cursor_ys.append(cursor_y)

        # background card sized to wrap exactly what this column ended up
        # containing (image + caption + its own sub-item list) instead of a
        # box that stops short of / overshoots the actual content — must be
        # inserted before this pair's other placements so it renders behind
        # them (python-pptx stacks later-added shapes on top of earlier ones)
        card_bottom = min(cursor_y + CARD_BOTTOM_PAD, bottom)
        placements.append(Placement("frame", x, top, cell_w, card_bottom - top))
        placements.extend(pair_placements)

    if footnote:
        # right after wherever the taller of the two columns' content
        # ended — NOT pinned to the box bottom, which left a dead gap
        # whenever a column was short (see git history for that bug)
        y = min(max(cursor_ys) + 10.0, bottom - footnote_height)
        placements.append(Placement("text", left, y, width, footnote_height, footnote))

    return [placements]
