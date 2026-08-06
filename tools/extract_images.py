"""Step 7 support: extract picture anchors (position + resolved media file)
from request.xlsx's drawing XML, and save the underlying image bytes to
disk so the block engine/renderer can reference a real file path later.
"""
import os
import re
import zipfile
from dataclasses import dataclass

from tools.extract_special_reward import _find_drawing_path, ANCHOR_SPLIT_RE, COLS

EMBED_RE = re.compile(r'<a:blip[^>]*r:embed="(rId\d+)"')
FROM_RE = re.compile(r"<xdr:from><xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>", re.S)
TO_ROW_RE = re.compile(r"<xdr:to>.*?<xdr:row>(\d+)</xdr:row>", re.S)


@dataclass
class PictureAnchor:
    col_letter: str
    row_start: int
    row_end: int
    rid: str
    media_path: str  # e.g. "xl/media/image3.png"


def _drawing_rels_path(drawing_path: str) -> str:
    parts = drawing_path.rsplit("/", 1)
    return f"{parts[0]}/_rels/{parts[1]}.rels"


def _resolve_media_map(zf: zipfile.ZipFile, drawing_path: str) -> dict[str, str]:
    rels_path = _drawing_rels_path(drawing_path)
    if rels_path not in zf.namelist():
        return {}
    data = zf.read(rels_path).decode("utf-8")
    mapping = {}
    for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="\.\./(media/[^"]+)"', data):
        mapping[m.group(1)] = f"xl/{m.group(2)}"
    return mapping


def get_picture_anchors(path: str) -> list[PictureAnchor]:
    drawing_path = _find_drawing_path(path)
    if drawing_path is None:
        return []
    with zipfile.ZipFile(path) as z:
        data = z.read(drawing_path).decode("utf-8", errors="replace")
        media_map = _resolve_media_map(z, drawing_path)

    anchors = []
    for chunk in ANCHOR_SPLIT_RE.split(data)[1:]:
        if "<xdr:pic>" not in chunk:
            continue
        from_m = FROM_RE.search(chunk)
        embed_m = EMBED_RE.search(chunk)
        if not from_m or not embed_m:
            continue
        col_idx0 = int(from_m.group(1))
        if col_idx0 >= len(COLS):
            continue
        row_start = int(from_m.group(2)) + 1
        to_m = TO_ROW_RE.search(chunk)
        row_end = int(to_m.group(1)) + 1 if to_m else row_start
        rid = embed_m.group(1)
        media_path = media_map.get(rid)
        if media_path is None:
            continue
        anchors.append(PictureAnchor(COLS[col_idx0], row_start, row_end, rid, media_path))
    return anchors


def extract_and_save_images(path: str, out_dir: str) -> list[tuple[PictureAnchor, str]]:
    """Saves each anchored image to out_dir, named by rId, and returns
    [(anchor, local_file_path), ...]."""
    os.makedirs(out_dir, exist_ok=True)
    anchors = get_picture_anchors(path)
    results = []
    with zipfile.ZipFile(path) as z:
        for anchor in anchors:
            ext = anchor.media_path.rsplit(".", 1)[-1].lower()
            local_path = os.path.join(out_dir, f"{anchor.rid}.{ext}")
            if not os.path.exists(local_path):
                with open(local_path, "wb") as f:
                    f.write(z.read(anchor.media_path))
            results.append((anchor, local_path))
    return results
