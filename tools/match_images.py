"""Step 7: match each located item to its nearest same-column picture
anchor within request.xlsx — position-based only (design principle 3).

The only image source is what the business team attaches directly in
request.xlsx; there is no separate name/ID-keyed asset repository (design
doc open question 9.1, resolved: confirmed not to exist/not in scope).
Items with no same-column image nearby stay text_only, which is a valid
end state, not an error — organizing a designer-facing asset folder for
those afterward is manual work outside this program's scope.

Matching is a maximum-cardinality bipartite match (Kuhn's algorithm) per
column, not naive per-item-in-order greedy. A greedy "each item grabs its
nearest still-free anchor" approach can leave an item unmatched even when
a valid assignment exists for everyone, because an earlier item can claim
an anchor a later item needed more (ties broken by list order, not need).
Found via a real case (202512 "FX 타이틀 교환권"): 3 items competed for 2
close anchors under tolerance, greedy matched 2/3 and left the item whose
only viable anchor got taken by another item that had an equally-good
alternative — Kuhn's algorithm finds the assignment that matches all 3.
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


def _max_bipartite_match(adjacency: dict[int, list[int]]) -> dict[int, int]:
    """adjacency: item_idx -> candidate anchor_idx list, ordered nearest-first
    (that order is what the algorithm tries first, biasing the result toward
    shorter distances among equally-valid maximum matchings, without
    guaranteeing global minimum total distance — maximizing match count is
    the actual goal here, distance is just a tiebreak preference).
    Returns item_idx -> anchor_idx for one maximum matching."""
    anchor_owner: dict[int, int] = {}  # anchor_idx -> item_idx

    def try_assign(item_idx: int, visited: set[int]) -> bool:
        for anchor_idx in adjacency.get(item_idx, []):
            if anchor_idx in visited:
                continue
            visited.add(anchor_idx)
            if anchor_idx not in anchor_owner or try_assign(anchor_owner[anchor_idx], visited):
                anchor_owner[anchor_idx] = item_idx
                return True
        return False

    for item_idx in adjacency:
        try_assign(item_idx, set())

    return {item_idx: anchor_idx for anchor_idx, item_idx in anchor_owner.items()}


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

    by_col_anchors: dict[str, list[PictureAnchor]] = {}
    for a in anchors:
        by_col_anchors.setdefault(a.col_letter, []).append(a)

    by_col_items: dict[str, list[int]] = {}
    for global_idx, item in enumerate(located_items):
        by_col_items.setdefault(item.col_letter, []).append(global_idx)

    matched_by_global_idx: dict[int, PictureAnchor] = {}

    for col_letter, item_global_indices in by_col_items.items():
        col_anchors = by_col_anchors.get(col_letter, [])
        if not col_anchors:
            continue
        adjacency = {}
        for local_idx, global_idx in enumerate(item_global_indices):
            item = located_items[global_idx]
            candidates = [
                (a_idx, _distance(item, a)) for a_idx, a in enumerate(col_anchors)
                if _distance(item, a) <= row_tolerance
            ]
            candidates.sort(key=lambda x: x[1])
            adjacency[local_idx] = [a_idx for a_idx, _ in candidates]

        matching = _max_bipartite_match(adjacency)
        for local_idx, anchor_idx in matching.items():
            matched_by_global_idx[item_global_indices[local_idx]] = col_anchors[anchor_idx]

    matched = []
    text_only = []
    for global_idx, item in enumerate(located_items):
        anchor = matched_by_global_idx.get(global_idx)
        if anchor is not None:
            matched.append(MatchedItem(
                item.name, item.is_new, item.row, item.col_letter, anchor_to_file[id(anchor)]
            ))
        else:
            text_only.append(item)

    return matched, text_only
