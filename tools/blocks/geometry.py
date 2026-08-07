"""Shared layout constants and primitives for all block engine functions.

Coordinates are in points (pt), matching master_template.md. Content box
values come from templates/master_template_summary.json slides 7-8 (the
"모서리가 둥근 직사각형 89" background varies slightly per slide depending
on whether a sub-header sits above it; we use a slightly conservative
shared box so every block type fits the same working area).
"""
from dataclasses import dataclass, field
from typing import Any, Optional

CONTENT_LEFT = 163.3
CONTENT_TOP = 99.0          # below the fixed "기간제 패키지" sub-header row
CONTENT_WIDTH = 391.7
CONTENT_BOTTOM = 526.0      # above the fixed footer bar at 528.7
CONTENT_HEIGHT = CONTENT_BOTTOM - CONTENT_TOP


@dataclass
class Placement:
    kind: str                    # 'icon' | 'caption' | 'badge' | 'image' | 'text' | 'frame'
    left: float
    top: float
    width: float
    height: float
    ref: Any = None              # source item dict, or literal text
    meta: dict = field(default_factory=dict)

    @property
    def right(self):
        return self.left + self.width

    @property
    def bottom(self):
        return self.top + self.height


def overlaps(a: Placement, b: Placement) -> bool:
    if a.right <= b.left or b.right <= a.left:
        return False
    if a.bottom <= b.top or b.bottom <= a.top:
        return False
    return True


def has_any_overlap(placements: list[Placement], ignore_kinds: tuple[str, ...] = ("badge", "frame")) -> bool:
    """Badges intentionally overlay their parent image/icon corner by design
    (see the NEW-badge reference sample) — excluded by default. 'frame' is a
    background card drawn behind a group of other placements (see
    paired_columns_block) and is expected to overlap everything inside it.
    Pass ignore_kinds=() to check literally everything."""
    checked = [p for p in placements if p.kind not in ignore_kinds]
    for i in range(len(checked)):
        for j in range(i + 1, len(checked)):
            if overlaps(checked[i], checked[j]):
                return True
    return False


def paginate_by_capacity(items: list, per_page: int) -> list[list]:
    """Split items into pages of at most per_page each. per_page must be >= 1."""
    if per_page < 1:
        raise ValueError("per_page must be >= 1 (item does not fit content box)")
    return [items[i:i + per_page] for i in range(0, len(items), per_page)]
