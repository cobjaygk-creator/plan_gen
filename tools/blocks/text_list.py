"""Block B: image-less name list, N columns (design doc default 3).

is_new items get a "(NEW)" suffix on their text — there's no icon here to
put a badge on, so this is the only way to keep that signal visible
instead of silently dropping it (see 202605, whose real ground truth
renders this section as a table/list with no images at all, including
for its 2 NEW items).
"""
from .geometry import CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_HEIGHT, Placement, paginate_by_capacity

ROW_HEIGHT = 20.0
GAP_X = 10.0


def _label(item: dict) -> str:
    name = item.get("name", "")
    return f"{name} (NEW)" if item.get("is_new") else name


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
            placements.append(Placement("text", x, y, cell_w, ROW_HEIGHT, _label(item)))
        pages.append(placements)
    return pages
