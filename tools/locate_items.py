"""Step 7 support: recover each AI-classified item's original (row,
col_letter) by matching its name back against the raw extracted cells.

Why this is needed: step 6's classifier only outputs item names (design
principle 1 — AI never touches coordinates), so the row/col each name
came from isn't in its output. Matching is done by normalized substring
comparison rather than exact equality because the model may strip
markers like "(new)"/"(new!)" out of the name (that's expected — it's
already captured in is_new) or make minor whitespace/roman-numeral
formatting changes.
"""
import re
from dataclasses import dataclass
from typing import Optional

NEW_MARKER_RE = re.compile(r"\s*\(new!?\)\s*$", re.IGNORECASE)


def normalize(text: str) -> str:
    text = NEW_MARKER_RE.sub("", text)
    return re.sub(r"\s+", "", text).lower()


@dataclass
class LocatedItem:
    name: str
    is_new: bool
    row: int
    col_letter: str
    matched_cell_text: str
    pair_group: Optional[int] = None


def locate_items(rows: list[dict], items: list) -> tuple[list[LocatedItem], list]:
    """rows: output of extract_special_reward_rows (has row/cells).
    items: list of Item (has .name, .is_new) from the AI classification.
    Returns (located, unlocated) — unlocated items get flagged rather
    than silently guessing a position."""
    candidates = []
    for row in rows:
        for col_letter, text in row["cells"].items():
            candidates.append((row["row"], col_letter, text, normalize(text)))

    located = []
    unlocated = []
    used = set()  # (row, col_letter) already claimed, avoid double-matching duplicate names

    for item in items:
        target = normalize(item.name)
        best = None
        for row_no, col_letter, raw_text, norm_text in candidates:
            key = (row_no, col_letter)
            if key in used:
                continue
            if target == norm_text or target in norm_text or norm_text in target:
                best = (row_no, col_letter, raw_text)
                break
        if best is None:
            unlocated.append(item)
            continue
        row_no, col_letter, raw_text = best
        used.add((row_no, col_letter))
        located.append(LocatedItem(
            item.name, item.is_new, row_no, col_letter, raw_text,
            pair_group=getattr(item, "pair_group", None),
        ))

    return located, unlocated
