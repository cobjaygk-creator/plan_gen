"""Step 7: match each located item to an image, position-matching first
(design principle 3) — no AI vision here. Two-pass:
  1. Position: nearest same-column picture anchor in request.xlsx within
     row tolerance.
  2. Asset repository: name/ID lookup via tools.asset_repository, whose
     existence is UNCONFIRMED (design doc 9.1). Until confirmed it's a
     stub that always returns None, so this pass is a no-op — wired in
     now so that once the repository is confirmed, only asset_repository.py
     needs an implementation, not this matching logic.

Items resolved by neither pass are returned as text_only, which is a
valid end state (design doc: never fabricate an image), not an error —
the 3.3 AI-vision exception path is a possible future third pass for
the leftover cases, deliberately not built by default since it's meant
to stay a rare exception, not a routine fallback.
"""
from dataclasses import dataclass

from tools.locate_items import LocatedItem
from tools.extract_images import PictureAnchor, get_picture_anchors, extract_and_save_images
from tools.asset_repository import lookup_image_by_name

ROW_TOLERANCE = 3


@dataclass
class MatchedItem:
    name: str
    is_new: bool
    row: int
    col_letter: str
    image_path: str
    source: str  # "position" | "asset_repo"


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
    still_unresolved = []

    for item in located_items:
        candidates = [
            a for a in by_col.get(item.col_letter, [])
            if id(a) not in used_anchor_ids and _distance(item, a) <= row_tolerance
        ]
        if candidates:
            best = min(candidates, key=lambda a: _distance(item, a))
            used_anchor_ids.add(id(best))
            matched.append(MatchedItem(
                item.name, item.is_new, item.row, item.col_letter,
                anchor_to_file[id(best)], source="position",
            ))
        else:
            still_unresolved.append(item)

    text_only = []
    for item in still_unresolved:
        repo_path = lookup_image_by_name(item.name)
        if repo_path:
            matched.append(MatchedItem(
                item.name, item.is_new, item.row, item.col_letter,
                repo_path, source="asset_repo",
            ))
        else:
            text_only.append(item)

    return matched, text_only
