"""Downloads and locally caches thumbnail/hero images referenced by
collectors (game sites, event benchmark, pre-registration) so a source site
going down, deleting a page, or rotating an image doesn't break a thumbnail
that's already shown on our own site — a bare hotlinked <img src> would.

Cached files land under web/frontend/public/data/thumbnails/<feature>/ —
the same directory tree already used for the exported *.json data files, so
the existing GitHub Pages workflow (`git add web/frontend/public/data`) and
the local dev server's SPA catch-all (serves any file under frontend/dist,
which is built from frontend/public) both pick them up with no new static
mount or workflow change. A mirror copy is also written under
web/frontend/dist/data/thumbnails/ when that build already exists, so a
locally running dev server serves a freshly cached image immediately
without requiring `npm run build` first.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)
_MAX_BYTES = 5_000_000
_CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
    "image/webp": "webp", "image/gif": "gif", "image/svg+xml": "svg",
}

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PUBLIC_DATA = _REPO_ROOT / "web" / "frontend" / "public" / "data"
_DIST_DATA = _REPO_ROOT / "web" / "frontend" / "dist" / "data"
RELATIVE_ROOT = "data/thumbnails"


def cache_thumbnail(url: str | None, feature: str) -> str | None:
    """Downloads `url` and returns a relative path such as
    "data/thumbnails/game_sites/<hash>.jpg" to store instead of the
    original URL. Returns None — callers should fall back to the original
    URL — on a missing url or any fetch/size failure; a slow or broken
    source must not fail the whole collection run over one image.

    Content is keyed by its own hash rather than by the source URL, so the
    same image referenced from two different pages is only ever stored
    once and a source that reshuffles query params doesn't re-download."""
    if not url:
        return None
    try:
        request = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(request, timeout=20) as response:
            content_type = (response.headers.get_content_type() or "").lower()
            data = response.read(_MAX_BYTES + 1)
    except Exception:
        return None
    if not data or len(data) > _MAX_BYTES:
        return None

    ext = _CONTENT_TYPE_EXT.get(content_type) or Path(urlparse(url).path).suffix.lstrip(".").lower() or "jpg"
    digest = hashlib.sha256(data).hexdigest()[:24]
    relative_path = f"{RELATIVE_ROOT}/{feature}/{digest}.{ext}"

    for root in (_PUBLIC_DATA, _DIST_DATA):
        if root is _DIST_DATA and not _DIST_DATA.is_dir():
            continue
        dest = root.parent / relative_path
        if not dest.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    return relative_path


def as_absolute_path(value: str | None) -> str | None:
    """For live API responses only (the app is always served from the
    origin root locally, unlike the GitHub Pages build which can sit under
    a subpath) — turns a stored relative cache path into a root-absolute
    one so it renders correctly regardless of the current client-side
    route. External fallback URLs (http/https) pass through unchanged."""
    if not value or value.startswith(("http://", "https://", "/")):
        return value
    return f"/{value}"
