"""Block B: image-less name list, N columns (design doc default 3)."""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_HEIGHT, Placement, paginate_by_capacity

ROW_HEIGHT = 20.0
GAP_X = 10.0


def text_list_block(items: list[dict], columns: int = 3) -> list[list[Placement]]:
    if columns < 1:
        raise ValueError("columns must be >= 1")

    cell_w = (CONTENT_WIDTH - GAP_X * (columns - 1)) / columns
    rows_per_page = max(1, int(CONTENT_HEIGHT // ROW_HEIGHT))
    per_page = rows_per_page * columns

    pages = []
    for chunk in paginate_by_capacity(items, per_page):
        placements = []
        for idx, item in enumerate(chunk):
            col = idx % columns
            row = idx // columns
            x = CONTENT_LEFT + col * (cell_w + GAP_X)
            y = CONTENT_TOP + row * ROW_HEIGHT
            placements.append(Placement("text", x, y, cell_w, ROW_HEIGHT, item.get("name")))
        pages.append(placements)
    return pages
