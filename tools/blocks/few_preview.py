"""Block C: 1-3 items, single row, large image + caption. No pagination —
by definition this type only ever holds a handful of items (202509 slide 8:
1 item at 227x244.8pt). More than 3 items is a classification error upstream,
not something this block should silently paginate around.
"""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_HEIGHT, Placement

GAP_X = 20.0
CAPTION_HEIGHT = 20.0


def few_preview_block(items: list[dict]) -> list[list[Placement]]:
    if not (1 <= len(items) <= 3):
        raise ValueError(f"few_preview_block expects 1-3 items, got {len(items)}")

    n = len(items)
    cell_w = (CONTENT_WIDTH - GAP_X * (n - 1)) / n
    image_h = CONTENT_HEIGHT - CAPTION_HEIGHT

    placements = []
    for idx, item in enumerate(items):
        x = CONTENT_LEFT + idx * (cell_w + GAP_X)
        placements.append(Placement("image", x, CONTENT_TOP, cell_w, image_h, item))
        placements.append(Placement("caption", x, CONTENT_TOP + image_h, cell_w, CAPTION_HEIGHT, item.get("name")))
    return [placements]
