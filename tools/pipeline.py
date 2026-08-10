"""Step 8: connect steps 5-7-6-3 into one pipeline per month.

request.xlsx
  -> parse_fixed_fields (step 5, no AI)
  -> extract_special_reward_rows (step 6 prep, no AI)
  -> classify_month (step 6, AI: Haiku->Sonnet)
  -> locate_items + match_images (step 7, no AI)
  -> dispatch to the matching tools.blocks function (step 3) per section

Each section's items become {"name": ..., "image": path_or_None}, fed to
whichever block engine function its block_type maps to. Block engine
functions raise ValueError on malformed input (design: never silently
misrender) — this module catches that per-section and records it as a
RenderError rather than crashing the whole month, since one bad section
in a 4-page request shouldn't block the other three.
"""
from dataclasses import dataclass, field
from typing import Callable

from tools.parse_fixed_fields import parse_fixed_fields
from tools.extract_special_reward import extract_special_reward_rows, to_compact_text
from tools.classify_month import classify_month, NeedsHumanReview
from tools.locate_items import locate_items, normalize
from tools.match_images import match_images
from tools.extract_images import get_picture_anchors, extract_and_save_images
from tools.blocks import (
    grid_block, text_list_block, few_preview_block, paired_columns_block, icon_only_block,
    has_any_overlap, CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM,
)


PAIRED_COLUMNS_COL_TOLERANCE = 2  # bridges the gap between a set's own text
                                   # column (B or D) and where its portrait
                                   # image is actually anchored (often nearer
                                   # the center column, C) — see real 202606
                                   # case in tools/match_images.py's docstring


@dataclass
class SectionResult:
    title: str
    block_type: str
    item_count: int
    matched_image_count: int
    text_only_count: int
    pages: list = field(default_factory=list)
    render_error: str | None = None
    footnote: str | None = None
    items: list = field(default_factory=list)


@dataclass
class MonthResult:
    month: str
    sections: list[SectionResult] = field(default_factory=list)
    needs_human_review: str | None = None
    fatal_error: str | None = None


def _items_with_images(section, matched, text_only) -> list[dict]:
    image_by_name = {m.name: m.image_path for m in matched}
    out = []
    for item in section.items:
        out.append({
            "name": item.name, "image": image_by_name.get(item.name), "is_new": item.is_new,
            "pair_group": item.pair_group,
        })
    return out


def split_pair_items(items: list[dict]) -> tuple[list[dict], tuple[list[dict], list[dict]]]:
    """Splits a flat item list into (pair_items, (sub_items_for_pair0,
    sub_items_for_pair1)) using each item's pair_group tag (real case:
    202606 "배틀패스 신규 의상" — 2 sets, each with its own ~6-item component
    list, see tools/blocks/paired_columns.py). Falls back to plain
    positional slicing with no sub-lists when nothing carries a
    pair_group tag at all — the simpler "2 sets + shared footnote" case
    that predates this field, and any pre-existing ai_results/ cache
    entries from before it existed."""
    if not any(i.get("pair_group") is not None for i in items):
        return items[:2], ([], [])
    pair_items = [i for i in items if i.get("pair_group") is None]
    sub0 = [i for i in items if i.get("pair_group") == 0]
    sub1 = [i for i in items if i.get("pair_group") == 1]
    return pair_items, (sub0, sub1)


def _find_title_row(rows: list[dict], title: str) -> int | None:
    target = normalize(title)
    for row in rows:
        for text in row["cells"].values():
            norm = normalize(text)
            if target == norm or target in norm or norm in target:
                return row["row"]
    return None


def _icon_only_row_range(rows: list[dict], title_row: int, footnote: str | None) -> tuple[int | None, int | None]:
    """Scans rows after title_row for a contiguous run of image-only rows
    (no cell text at all — see extract_special_reward_rows), skipping the
    section's own footnote row along the way. Stops at the first row that
    has real text unrelated to the footnote, since that's the next
    section's title. Returns (start, end) row numbers, or (None, None) if
    no image-only rows were found."""
    footnote_norm = normalize(footnote) if footnote else None
    start = end = None
    for row in sorted(rows, key=lambda r: r["row"]):
        r = row["row"]
        if r <= title_row:
            continue
        if row["cells"]:
            combined = normalize(" ".join(row["cells"].values()))
            if footnote_norm and (footnote_norm == combined or footnote_norm in combined):
                continue  # this is the section's own footnote line, keep going
            break  # real content unrelated to our footnote -> next section
        if row.get("has_image"):
            if start is None:
                start = r
            end = r
    return start, end


def _icon_only_items(request_path: str, rows: list[dict], section, image_out_dir: str) -> list[dict]:
    """No item names exist for this block type (see tools/blocks/icon_only.py)
    — instead of the usual AI-name -> locate -> match flow, grab whatever
    images are anchored within the section's own row range directly."""
    title_row = _find_title_row(rows, section.section_title)
    if title_row is None:
        return []
    start, end = _icon_only_row_range(rows, title_row, section.footnote)
    if start is None:
        return []

    anchor_files = extract_and_save_images(request_path, image_out_dir)
    selected = [
        (a, f) for a, f in anchor_files
        if not (a.row_end < start or a.row_start > end)
    ]
    return [{"name": "", "image": f, "is_new": False, "pair_group": None} for _, f in selected]


def _render_section(section, items: list[dict]) -> list:
    bt = section.block_type
    if bt in ("grid", "new_highlight"):
        # new_highlight merged into grid: real data (202512) showed NEW
        # items sit in a normal-sized grid cell with just a badge, not a
        # separately-sized "highlight card" — see tools/blocks/grid.py
        return grid_block(items, columns=3, icon_size=24.0)
    if bt == "text_list":
        return text_list_block(items, columns=3)
    if bt == "few_preview":
        return few_preview_block(items)
    if bt == "paired_columns":
        pair_items, sub_items_by_pair = split_pair_items(items)
        return paired_columns_block(pair_items, sub_items_by_pair=sub_items_by_pair, footnote=section.footnote)
    if bt == "icon_only":
        box = (CONTENT_LEFT, CONTENT_TOP, CONTENT_WIDTH, CONTENT_BOTTOM - CONTENT_TOP)
        return icon_only_block(items, box=box)
    raise ValueError(f"unknown block_type: {bt!r}")


def process_month(
    month: str, request_path: str, image_out_dir: str | None = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> MonthResult:
    """image_out_dir=None extracts to out/<month>/images by default — NOT
    "no images": omitting it used to silently leave match_images.py's
    in-archive paths (e.g. "xl/media/image8.PNG") on each item, which
    render_pptx.py's os.path.exists() check then quietly treats as "no
    image" (empty card, no error). That's how a fully-matched section
    could render with zero pictures. Pass an explicit dir (or the same
    default) if you want the images anywhere else.

    on_progress(step, message): optional callback fired after each of this
    function's 3 stages (1=고정 필드 파싱, 2=AI 분류+이미지 매칭,
    3=레이아웃 계산) — step 4 (.pptx 렌더링) happens outside this function,
    in whatever calls render_from_template(), and isn't reported here.
    Added for the web backend's SSE progress stream (web/backend/app/
    pipeline_runner.py); run.py and existing callers just don't pass it."""
    def _progress(step: int, message: str) -> None:
        if on_progress:
            on_progress(step, message)

    if image_out_dir is None:
        image_out_dir = f"out/{month}/images"

    fixed = parse_fixed_fields(request_path)
    rows = extract_special_reward_rows(request_path, fixed["special_reward_start_row"])
    raw_text = to_compact_text(rows)
    _progress(1, "고정 필드 파싱 완료")

    try:
        classify_result = classify_month(month, raw_text)
    except NeedsHumanReview as e:
        return MonthResult(month, needs_human_review=str(e))

    # phase 1: classify (done above) + per-section locate/match — the only
    # network-bound work left after this point is none, so this is where
    # "AI 분류 + 이미지 매칭" (step 2) actually finishes.
    prepared = []  # (section, items, matched, text_only, unlocated)
    for section in classify_result.output.sections:
        if section.block_type == "icon_only":
            # no item names to locate/match at all — see tools/blocks/icon_only.py
            items = _icon_only_items(request_path, rows, section, image_out_dir)
            prepared.append((section, items, items, [], []))
            continue
        located, unlocated = locate_items(rows, section.items)
        if section.block_type == "paired_columns":
            # only the 2 set-name items (pair_group is None) ever attempt
            # image matching — sub-items are always rendered as plain text
            # (see tools/blocks/paired_columns.py) and, worse, a sub-item's
            # row often sits exactly inside a set-portrait anchor's row span
            # (distance 0), so if left in the competition it would win that
            # anchor away from the actual set name via the nearest-first
            # tiebreak — confirmed on the real 202606 data.
            matchable = [l for l in located if l.pair_group is None]
            never_matched = [l for l in located if l.pair_group is not None]
            matched, unmatched = match_images(
                request_path, matchable, out_dir=image_out_dir,
                col_tolerance=PAIRED_COLUMNS_COL_TOLERANCE,
            )
            text_only = unmatched + never_matched
        else:
            matched, text_only = match_images(request_path, located, out_dir=image_out_dir)
        items = _items_with_images(section, matched, text_only)
        prepared.append((section, items, matched, text_only, unlocated))
    _progress(2, "AI 분류 + 이미지 매칭 완료")

    # phase 2: per-section layout (block engine -> Placement pages)
    result = MonthResult(month)
    for section, items, matched, text_only, unlocated in prepared:
        # icon_only sections never have AI-named items (see tools/blocks/
        # icon_only.py) — section.items is always [] for that type, so the
        # image count found by row-range scanning is the real item count.
        item_count = len(items) if section.block_type == "icon_only" else len(section.items)
        try:
            pages = _render_section(section, items)
            result.sections.append(SectionResult(
                title=section.section_title, block_type=section.block_type,
                item_count=item_count, matched_image_count=len(matched),
                text_only_count=len(text_only) + len(unlocated), pages=pages,
                footnote=section.footnote, items=items,
            ))
        except ValueError as e:
            result.sections.append(SectionResult(
                title=section.section_title, block_type=section.block_type,
                item_count=item_count, matched_image_count=len(matched),
                text_only_count=len(text_only) + len(unlocated), render_error=str(e),
                footnote=section.footnote, items=items,
            ))
    _progress(3, "레이아웃 계산 완료")

    return result


def summarize(result: MonthResult) -> str:
    if result.fatal_error:
        return f"[ERROR] {result.month}: {result.fatal_error}"
    if result.needs_human_review:
        return f"[NEEDS_REVIEW] {result.month}: {result.needs_human_review}"
    lines = [f"{result.month}:"]
    for s in result.sections:
        overlap_pages = sum(1 for p in s.pages if has_any_overlap(p)) if s.pages else 0
        status = "ERROR" if s.render_error else ("OVERLAP" if overlap_pages else "OK")
        img_pct = (s.matched_image_count / s.item_count * 100) if s.item_count else 0
        detail = s.render_error or f"img={img_pct:.0f}% overlap_pages={overlap_pages}/{len(s.pages)}"
        lines.append(f"  [{status}] {s.title} ({s.block_type}, {s.item_count} items): {detail}")
    return "\n".join(lines)
