"""Vision-assisted fallback for the minority of items plain position
matching (match_images.py) can't resolve — only called when there's
something worth looking at, so the common case (position matching just
works) costs nothing extra.

Two real failure modes motivated this (see STATUS.md rounds 8-11):
  1. Fewer real images than named items in a row-group (e.g. 4 names,
     3 images) — one item goes unmatched even though a human looking at
     the images would pair 2 similar items under one shared photo.
  2. Two real images collide on the same column letter (e.g. "블랙 하이틴
     캐쥬얼 세트 I/II") — position math can only give one of them to
     whichever item wins the tiebreak, leaving the other unmatched, even
     though both images plainly exist and belong to different items.

Neither is solvable by more positional rules alone — round 9 already
proved that "always disambiguate collisions" breaks a *different* real
case (a decorative badge colliding with real content) that structurally
needs the opposite behavior. So instead of guessing, this only fires for
items match_images() already gave up on (text_only), looks at whatever
real images are anchored near those specific rows, and asks a vision
model to look and decide — same judgment call a human (or the reference
Claude session STATUS.md round 11 was built to match) makes instantly.
"""
import os
from dataclasses import dataclass

from pydantic import BaseModel, Field

from tools.ai_client import classify_with_images, ClassificationError, SONNET_MODEL
from tools.extract_images import extract_and_save_images
from tools.locate_items import LocatedItem
from tools.match_images import MatchedItem, ROW_TOLERANCE

VISION_MODEL = os.environ.get("VISION_MATCH_MODEL", SONNET_MODEL)

SYSTEM_PROMPT = """\
너는 게임 보상 항목 이름과 실제 캐릭터/아이템 이미지를 짝짓는 작업을 한다.
아래 항목 이름 목록과 번호가 매겨진 이미지들을 보고, 각 항목이 어떤 이미지에
해당하는지 판단해라.

- 이미지 내용(캐릭터 의상, 색상, 테마, 소품)과 항목 이름을 실제로 비교해서
  판단해라. 이름만 보고 대충 순서대로 배정하지 마라.
- 이미지 하나가 실제로 항목 2개 모두를 보여주는 경우(예: 캐릭터 2명이 함께
  나온 사진), 그 이미지 번호를 두 항목 모두에 배정해도 된다.
- 리본, 티켓, 뱃지, 로고 같은 장식용 아이콘은 어떤 항목에도 배정하지 마라 —
  실제 캐릭터/아이템을 보여주는 사진만 배정해라.
- 확신이 없으면 억지로 배정하지 말고 image_index를 null로 남겨라. 틀리게
  배정하는 것보다 비워두는 게 낫다.
- 주어진 이미지 번호(0부터 시작) 범위 밖의 번호를 만들어내지 마라."""


class ImageAssignment(BaseModel):
    item_name: str = Field(description="주어진 항목 이름 중 하나, 원문 그대로")
    image_index: int | None = Field(description="이 항목에 해당하는 이미지 번호(0부터). 해당 없으면 null")


class VisionMatchResult(BaseModel):
    assignments: list[ImageAssignment] = Field(default_factory=list)


@dataclass
class VisionResolvedItem:
    name: str
    image_path: str


def _rid_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _media_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower()
    return "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"


def resolve_unmatched_with_vision(
    request_path: str, text_only: list[LocatedItem], matched: list[MatchedItem],
    image_out_dir: str, row_tolerance: int = ROW_TOLERANCE,
) -> tuple[list[VisionResolvedItem], list[LocatedItem]]:
    """Returns (resolved, still_unresolved). Two resolved items can share
    the same image_path — the caller is responsible for merging those
    into one combined-caption card (see pipeline.py's _merge_shared_images),
    not duplicating the image into two separate cells (that reintroduces
    the cross-section duplicate-photo bug from STATUS.md round 10).

    Does nothing (returns ([], text_only), no API call) if none of the
    text_only items has an unclaimed image anchored anywhere near its
    row — a genuinely image-less item (real case: 202508's damage skins)
    costs zero extra cost or latency."""
    if not text_only:
        return [], []

    anchor_files = extract_and_save_images(request_path, image_out_dir)
    used_rids = {_rid_from_path(m.image_path) for m in matched}

    def _near_any_unmatched(anchor) -> bool:
        return any(
            anchor.row_start - row_tolerance <= item.row <= anchor.row_end + row_tolerance
            for item in text_only
        )

    candidates = [
        (a, path) for a, path in anchor_files
        if _rid_from_path(path) not in used_rids and _near_any_unmatched(a)
    ]
    if not candidates:
        return [], text_only

    images = []
    for _, path in candidates:
        with open(path, "rb") as f:
            images.append((_media_type(path), f.read()))

    user_prompt = "항목 이름:\n" + "\n".join(f"- {item.name}" for item in text_only)

    try:
        result = classify_with_images(SYSTEM_PROMPT, user_prompt, images, VisionMatchResult, VISION_MODEL)
    except ClassificationError:
        return [], text_only

    by_name = {a.item_name: a.image_index for a in result.assignments}
    resolved, still_unresolved = [], []
    for item in text_only:
        idx = by_name.get(item.name)
        if idx is None or not isinstance(idx, int) or not (0 <= idx < len(candidates)):
            still_unresolved.append(item)
            continue
        resolved.append(VisionResolvedItem(item.name, candidates[idx][1]))
    return resolved, still_unresolved
