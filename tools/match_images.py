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
from tools.extract_special_reward import COLS

ROW_TOLERANCE = 3
COL_INDEX = {c: i for i, c in enumerate(COLS)}


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


def _col_distance(a_col: str, b_col: str) -> int:
    ia, ib = COL_INDEX.get(a_col), COL_INDEX.get(b_col)
    if ia is None or ib is None:
        return 0 if a_col == b_col else 999
    return abs(ia - ib)


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
    row_tolerance: int = ROW_TOLERANCE, col_tolerance: int = 0,
) -> tuple[list[MatchedItem], list[LocatedItem]]:
    """col_tolerance=0 (default) requires an exact same-column anchor,
    matching every existing caller's behavior unchanged. A caller can widen
    it (see paired_columns handling in tools/pipeline.py) for layouts where
    the image is anchored 1-2 columns off from its item's own text column —
    e.g. a tall portrait anchored near the center column between two
    side-by-side item lists. Not on by default because a wider tolerance
    lets a *closer-row* item in a neighboring column outcompete the item an
    anchor actually belongs to (see git history: paired_columns sub-items
    sitting inside a set-portrait's row span would otherwise win it away
    from the set name itself)."""
    if out_dir:
        anchor_files = extract_and_save_images(path, out_dir)
        anchor_to_file = {id(a): f for a, f in anchor_files}
        anchors = [a for a, _ in anchor_files]
    else:
        anchors = get_picture_anchors(path)
        anchor_to_file = {id(a): a.media_path for a in anchors}

    adjacency: dict[int, list[int]] = {}
    for item_idx, item in enumerate(located_items):
        candidates = [
            (a_idx, _distance(item, a), _col_distance(item.col_letter, a.col_letter))
            for a_idx, a in enumerate(anchors)
        ]
        candidates = [
            (a_idx, rd, cd) for a_idx, rd, cd in candidates
            if rd <= row_tolerance and cd <= col_tolerance
        ]
        candidates.sort(key=lambda x: (x[1], x[2]))  # nearest row first, then nearest column
        adjacency[item_idx] = [a_idx for a_idx, _, _ in candidates]

    matching = _max_bipartite_match(adjacency)
    matched_by_global_idx: dict[int, PictureAnchor] = {
        item_idx: anchors[a_idx] for item_idx, a_idx in matching.items()
    }

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
