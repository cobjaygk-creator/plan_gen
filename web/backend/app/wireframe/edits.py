from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent / "assets"

MAX_PATCHES = 1500
MAX_JSON_BYTES = 6_000_000
MAX_DATA_URI_CHARS = 1_600_000

_PATH_RE = re.compile(r"^body(?:>[a-z][a-z0-9-]*:nth-child\(\d{1,4}\)){0,40}$")
_HREF_RE = re.compile(
    r"^(?:https?://[^\s\"'<>()\\]{1,1000}|mailto:[^\s\"'<>()\\]{1,200}|tel:[0-9+\-() ]{3,30}"
    r"|#[\w\-]{0,100}|\./[\w\-./]{1,200}|/[\w\-./]{1,200}|page:[A-Za-z0-9._\-]{1,80})$"
)
_IMAGE_RE = re.compile(r"^(?:data:image/(?:png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+|https?://[^\s\"'<>()\\]{1,1000})$")
_STYLE_VALUE_RE = re.compile(r"^[#%.,()\sa-zA-Z0-9-]{0,60}$")
_FORBIDDEN_STYLE = re.compile(r"url\(|expression|javascript|@import", re.IGNORECASE)

STYLE_PROPS = {
    "color", "backgroundColor", "fontSize", "fontWeight", "textAlign", "borderRadius",
    "padding", "margin", "opacity", "lineHeight", "letterSpacing",
}
INSERT_KINDS = {"text", "button", "divider", "image", "video"}
_VIDEO_RE = re.compile(
    r"^https://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]{11}[\w&=%-]{0,100}|youtu\.be/[\w-]{11}[\w?&=%-]{0,100}"
    r"|youtube\.com/embed/[\w-]{11}|vimeo\.com/\d{1,15})$"
    r"|^https://[^\s\"'<>()\\]{1,900}\.(?:mp4|webm|ogg)(?:\?[^\s\"'<>()\\]{0,100})?$"
)


class PatchError(ValueError):
    pass


def _clean_text(value, limit: int, field: str) -> str:
    if not isinstance(value, str):
        raise PatchError(f"{field}는 문자열이어야 합니다.")
    if len(value) > limit:
        raise PatchError(f"{field}가 너무 깁니다. (최대 {limit}자)")
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in value):
        raise PatchError(f"{field}에 사용할 수 없는 문자가 있습니다.")
    return value


def validate_patch(raw) -> dict:
    if not isinstance(raw, dict):
        raise PatchError("수정 항목 형식이 올바르지 않습니다.")
    op = raw.get("op")
    path = raw.get("path")
    if not isinstance(path, str) or not _PATH_RE.match(path):
        raise PatchError("수정 대상 위치가 올바르지 않습니다.")
    patch: dict = {"op": op, "path": path}
    ref = raw.get("ref", "")
    patch["ref"] = _clean_text(ref, 60, "ref") if ref else ""

    if op == "text":
        node = raw.get("node", 0)
        if not isinstance(node, int) or isinstance(node, bool) or not 0 <= node <= 50:
            raise PatchError("글자 위치가 올바르지 않습니다.")
        patch["node"] = node
        patch["value"] = _clean_text(raw.get("value", ""), 3000, "글자")
    elif op == "link":
        href = raw.get("href", "")
        if not isinstance(href, str) or (href and not _HREF_RE.match(href)):
            raise PatchError("허용되지 않는 링크 주소입니다. (http, https, mailto, tel, #, 상대 경로, 페이지 연결만 가능)")
        target = raw.get("target", "")
        if target not in ("", "_blank"):
            raise PatchError("링크 열기 방식이 올바르지 않습니다.")
        patch["href"] = href
        patch["target"] = target
    elif op == "style":
        style = raw.get("style")
        if not isinstance(style, dict) or not style:
            raise PatchError("스타일 값이 없습니다.")
        clean = {}
        for key, value in style.items():
            if key not in STYLE_PROPS:
                raise PatchError(f"지원하지 않는 스타일입니다: {key}")
            if not isinstance(value, str) or not _STYLE_VALUE_RE.match(value) or _FORBIDDEN_STYLE.search(value):
                raise PatchError(f"허용되지 않는 스타일 값입니다: {key}")
            clean[key] = value
        patch["style"] = clean
    elif op == "image":
        src = raw.get("src", "")
        if not isinstance(src, str) or len(src) > MAX_DATA_URI_CHARS or (src and not _IMAGE_RE.match(src)):
            raise PatchError("허용되지 않는 이미지입니다. (png, jpeg, webp, gif 또는 https 주소, 1.2MB 이하)")
        patch["src"] = src
    elif op == "move":
        if raw.get("dir") not in ("up", "down"):
            raise PatchError("이동 방향이 올바르지 않습니다.")
        patch["dir"] = raw["dir"]
    elif op == "insert":
        if raw.get("kind") not in INSERT_KINDS:
            raise PatchError("추가할 수 없는 요소입니다.")
        patch["kind"] = raw["kind"]
        if raw["kind"] == "video":
            src = raw.get("src", "")
            if not isinstance(src, str) or not _VIDEO_RE.match(src):
                raise PatchError("지원하지 않는 영상 주소입니다. (https 의 mp4·webm·ogg 파일, 유튜브, 비메오만 가능)")
            patch["src"] = src
    elif op in ("delete", "duplicate"):
        pass
    else:
        raise PatchError("지원하지 않는 수정 종류입니다.")
    return patch


def validate_patches(raw) -> list[dict]:
    if not isinstance(raw, list):
        raise PatchError("수정 목록 형식이 올바르지 않습니다.")
    if len(raw) > MAX_PATCHES:
        raise PatchError(f"수정 항목이 너무 많습니다. (최대 {MAX_PATCHES}개)")
    patches = [validate_patch(item) for item in raw]
    if len(json.dumps(patches, ensure_ascii=False).encode("utf-8")) > MAX_JSON_BYTES:
        raise PatchError("수정 내용이 너무 큽니다. 이미지 크기를 줄여 주세요.")
    return patches


def load_asset(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8")


def _json_for_script(patches: list[dict]) -> str:
    text = json.dumps(patches, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build_document(html: str, patches: list[dict], mode: str = "view") -> str:
    """원본 HTML에 수정 목록과 적용 스크립트를 붙인다. 수정이 없는 보기 모드는 원본 그대로 돌려준다."""
    if mode == "view" and not patches:
        return html
    scripts = [f"<script>window.__QP_MODE={json.dumps(mode)};</script>"]
    scripts.append(f'<script id="qp-patches" type="application/json">{_json_for_script(patches)}</script>')
    scripts.append(f"<script>{load_asset('qp_runtime.js')}</script>")
    if mode == "edit":
        scripts.append(f"<script>{load_asset('qp_editor.js')}</script>")
    block = "\n".join(scripts)
    index = html.lower().rfind("</body>")
    if index == -1:
        return html + block
    return html[:index] + block + html[index:]


_FILE_SAFE_RE = re.compile(r"[^A-Za-z0-9._\-]")


def safe_page_filename(page_id: str) -> str:
    return _FILE_SAFE_RE.sub("_", page_id)


def export_zip(pages: list[tuple[str, str, str]]) -> bytes:
    """(page_id, title, html) 목록을 zip으로 묶는다. 페이지 연결 링크는 ./<page_id>.html로 열린다."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        items = []
        for page_id, title, html in pages:
            name = safe_page_filename(page_id)
            archive.writestr(f"{name}.html", html)
            safe_title = (title or page_id).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            items.append(f'<li><a href="./{name}.html">{safe_title}</a> <small>{name}</small></li>')
        index = (
            '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>퀵 프로토타입</title>'
            "<style>body{font:15px/1.7 'Malgun Gothic',sans-serif;max-width:640px;margin:48px auto;padding:0 16px}"
            "small{color:#8a949e;margin-left:8px}</style></head><body><h1>퀵 프로토타입</h1><ul>"
            + "".join(items)
            + "</ul></body></html>"
        )
        archive.writestr("index.html", index)
    return buffer.getvalue()
