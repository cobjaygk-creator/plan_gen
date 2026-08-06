"""Step 7: match each located item to its nearest same-column picture
anchor within request.xlsx — position-based only (design principle 3).

The only image source is what the business team attaches directly in
request.xlsx; there is no separate name/ID-keyed asset repository (design
doc open question 9.1, resolved: confirmed not to exist/not in scope).
Items with no same-column image nearby stay text_only, which is a valid
end state, not an error — organizing a designer-facing asset folder for
those afterward is manual work outside this program's scope.
"""
from dataclasses import dataclass

from tools.locate_items import LocatedItem
from tools.extract_images import PictureAnchor, get_picture_anchors, extract_and_save_images

ROW_TOLERANCE = 3


@dataclass
class MatchedItem:
    name: str
    is_new: bool
    row: int
    col_letter: str
    image_path: str


def _distance(item: LocatedItem, anchor: PictureAnchor) -> int:
    if anchor.row_start <= item.row <= anchor.row_end:
        return 0
    return min(abs(item.row - anchor.row_start), abs(item.row - anchor.row_end))


def match_images(
    path: str, located_items: list[LocatedItem], out_dir: str | None = None,
    row_tolerance: int = ROW_TOLERANCE,
) -> tuple[list[MatchedItem], list[LocatedItem]]:
    if out_dir:
        anchor_files = extract_and_save_images(path, out_dir)
        anchor_to_file = {id(a): f for a, f in anchor_files}
        anchors = [a for a, _ in anchor_files]
    else:
        anchors = get_picture_anchors(path)
        anchor_to_file = {id(a): a.media_path for a in anchors}

    by_col: dict[str, list[PictureAnchor]] = {}
    for a in anchors:
        by_col.setdefault(a.col_letter, []).append(a)

    used_anchor_ids = set()
    matched = []
    text_only = []

    for item in located_items:
        candidates = [
            a for a in by_col.get(item.col_letter, [])
            if id(a) not in used_anchor_ids and _distance(item, a) <= row_tolerance
        ]
        if candidates:
            best = min(candidates, key=lambda a: _distance(item, a))
            used_anchor_ids.add(id(best))
            matched.append(MatchedItem(
                item.name, item.is_new, item.row, item.col_letter, anchor_to_file[id(best)]
            ))
        else:
            text_only.append(item)

    return matched, text_only
