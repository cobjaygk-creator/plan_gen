"""Step 6 support (still no AI): pull the raw "특별 보상 미리보기" section out
of request.xlsx as a compact grid-preserving text block, ready to hand to
the AI classifier. Everything above this section (title/period/grade
table) was already consumed by step 5's parse_fixed_fields(); everything
from special_reward_start_row down to (but not including) the
"배틀패스 보상 리스트 보러 가기" / "유의사항" boundary belongs here.

Important finding: item captions are NOT always plain cell values. Some
months (confirmed: 202509) put the caption as a floating drawing textbox
anchored near the image instead of a cell value — openpyxl's cell API
sees nothing there. So this module reads text from both sources (cell
values + drawing textbox runs) and merges them by anchor row, the same
way images will need to be position-matched in step 7.
"""
import re
import zipfile
import openpyxl

END_MARKERS_RE = re.compile(r"(배틀패스\s*보상\s*리스트\s*보러\s*가기|^유의사항$)")
COLS = ["B", "C", "D", "E", "F"]

ANCHOR_SPLIT_RE = re.compile(r"(?=<xdr:(?:twoCellAnchor|oneCellAnchor)[ >])")
FROM_RE = re.compile(r"<xdr:from><xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>", re.S)
TEXT_RUN_RE = re.compile(r"<a:t>(.*?)</a:t>")


def _find_drawing_path(path: str) -> str | None:
    with zipfile.ZipFile(path) as z:
        rels_path = "xl/worksheets/_rels/sheet1.xml.rels"
        if rels_path in z.namelist():
            rels = z.read(rels_path).decode("utf-8")
            m = re.search(r'Target="\.\./(drawings/drawing\d+\.xml)"', rels)
            if m:
                return f"xl/{m.group(1)}"
        candidates = [n for n in z.namelist() if re.match(r"xl/drawings/drawing\d+\.xml$", n)]
        return candidates[0] if candidates else None


def extract_drawing_text_anchors(path: str) -> list[dict]:
    """Returns [{"row": excel_row_1indexed, "col_letter": "B", "text": str}, ...]
    for every floating textbox (not picture) in the sheet's drawing, ignoring
    shapes that have no text runs at all."""
    drawing_path = _find_drawing_path(path)
    if drawing_path is None:
        return []
    with zipfile.ZipFile(path) as z:
        data = z.read(drawing_path).decode("utf-8", errors="replace")

    anchors = []
    for chunk in ANCHOR_SPLIT_RE.split(data)[1:]:
        if "<xdr:pic>" in chunk:
            continue  # picture anchor, handled separately in step 7
        texts = TEXT_RUN_RE.findall(chunk)
        if not texts:
            continue
        m = FROM_RE.search(chunk)
        if not m:
            continue
        col_idx0, row_idx0 = int(m.group(1)), int(m.group(2))
        if col_idx0 >= len(COLS):
            continue
        joined = "".join(texts).strip()
        if joined:
            anchors.append({"row": row_idx0 + 1, "col_letter": COLS[col_idx0], "text": joined})
    return anchors


def extract_special_reward_rows(path: str, start_row: int) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]

    end_row = ws.max_row + 1
    for r in range(start_row + 1, ws.max_row + 1):
        for c in range(2, 7):
            v = ws.cell(row=r, column=c).value
            if v and END_MARKERS_RE.search(str(v).strip()):
                end_row = r
                break
        if end_row == r:
            break

    row_map: dict[int, dict] = {}

    for r in range(start_row, end_row):
        cells = {}
        for col_idx, col_letter in zip(range(2, 7), COLS):
            v = ws.cell(row=r, column=col_idx).value
            if v not in (None, ""):
                cells[col_letter] = str(v).strip()
        if cells:
            row_map[r] = {"row": r, "cells": cells}

    for anchor in extract_drawing_text_anchors(path):
        r = anchor["row"]
        if not (start_row <= r < end_row):
            continue
        entry = row_map.setdefault(r, {"row": r, "cells": {}})
        # don't clobber a real cell value with a textbox guess at the same slot
        entry["cells"].setdefault(anchor["col_letter"], anchor["text"])

    return [row_map[r] for r in sorted(row_map)]


def to_compact_text(rows: list[dict]) -> str:
    """Grid-preserving compact text — cheap on tokens, keeps enough
    structure (which columns are populated together) for the model to
    infer N-column grid vs single-column list vs paired layout."""
    lines = []
    for row in rows:
        cells = row["cells"]
        cols = "".join(cells.keys())
        values = " | ".join(cells.values())
        lines.append(f"{cols}{row['row']}: {values}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    from tools.parse_fixed_fields import parse_fixed_fields

    path = sys.argv[1] if len(sys.argv) > 1 else "samples/202605_request.xlsx"
    fixed = parse_fixed_fields(path)
    rows = extract_special_reward_rows(path, fixed["special_reward_start_row"])
    text = to_compact_text(rows)
    with open("templates/_extract_debug.txt", "w", encoding="utf-8") as f:
        f.write(text + f"\n\n--- {len(rows)} rows, {sum(len(r['cells']) for r in rows)} cells ---")
