"""Step 4: regression scoring.

Scores a generated block layout against the answer key (expected item
names + expected images) for a month. Three numeric signals only —
no "느낌" judgment (design doc principle 4):
  - text_match_rate: expected item names vs actual, set-based
  - image_match_rate: of expected items that should have an image,
    how many actually got one resolved
  - overlap_count: shape collisions in the actual generated pages
    (uses blocks.geometry.has_any_overlap, which already excludes
    badge-over-image by design — see step 3)

score_run() combines these into one short PASS/FAIL summary. Output is
deliberately terse (design doc principle 8.5: "PASS/FAIL + 점수 요약
몇 줄", not a wall of per-item diagnostics) — callers that need the
detail can read the returned dict fields directly.

NOTE: this module scores layout/content already produced by the block
engine (step 3). It does not yet run against a real generated PPT for a
real month, because the extraction/AI/rendering steps (5-7) that would
produce one don't exist yet — that wiring happens in step 8 per the
design doc's own ordering. Until then this is exercised by tests/test_regression.py
using synthetic expected/actual pairs.
"""
from dataclasses import dataclass

from tools.blocks.geometry import Placement, has_any_overlap

TEXT_MATCH_THRESHOLD = 0.95
IMAGE_MATCH_THRESHOLD = 0.90


def _normalize(name: str) -> str:
    return " ".join(name.split()).strip()


def text_match_rate(expected_names: list[str], actual_names: list[str]) -> float:
    if not expected_names:
        return 1.0
    expected = {_normalize(n) for n in expected_names}
    actual = {_normalize(n) for n in actual_names}
    return len(expected & actual) / len(expected)


def image_match_rate(expected_items: list[dict], actual_items: list[dict]) -> float:
    """expected_items: items that are supposed to have an image (image key truthy).
    actual_items: same-shape list, matched by 'name', to check if image got resolved."""
    needing_image = [i for i in expected_items if i.get("image")]
    if not needing_image:
        return 1.0
    actual_by_name = {_normalize(i.get("name", "")): i for i in actual_items}
    hits = 0
    for exp in needing_image:
        act = actual_by_name.get(_normalize(exp.get("name", "")))
        if act and act.get("image"):
            hits += 1
    return hits / len(needing_image)


def overlap_count(pages: list[list[Placement]]) -> int:
    return sum(1 for page in pages if has_any_overlap(page))


@dataclass
class RegressionResult:
    month: str
    text_match: float
    image_match: float
    overlapping_pages: int
    total_pages: int
    passed: bool

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.month}: text={self.text_match:.0%} "
            f"image={self.image_match:.0%} overlap_pages={self.overlapping_pages}/{self.total_pages}"
        )


def score_run(month: str, expected_items: list[dict], actual_items: list[dict],
              pages: list[list[Placement]]) -> RegressionResult:
    tm = text_match_rate([i["name"] for i in expected_items], [i["name"] for i in actual_items])
    im = image_match_rate(expected_items, actual_items)
    oc = overlap_count(pages)
    passed = tm >= TEXT_MATCH_THRESHOLD and im >= IMAGE_MATCH_THRESHOLD and oc == 0
    return RegressionResult(month, tm, im, oc, len(pages), passed)
