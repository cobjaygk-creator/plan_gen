"""Downloads and locally caches thumbnail/hero images referenced by
collectors (game sites, event benchmark, pre-registration) so a source site
going down, deleting a page, or rotating an image doesn't break a thumbnail
that's already shown on our own site — a bare hotlinked <img src> would.

Cached files used to land under web/frontend/public|dist/data/thumbnails/ —
that made sense back when a GitHub Pages static export read from the same
tree. Now that Pages is retired, that location is actively harmful: every
deploy rebuilds web/frontend/dist/ from scratch on a GitHub Actions runner
and rsyncs the whole thing over, which silently deletes any thumbnail the
production server had cached since the last deploy (confirmed live —
이터널 리턴/어둠의전설 thumbnails cached right after launch were wiped by
the next code push, and the stored `/data/thumbnails/...` path started
resolving to the SPA's index.html fallback instead of the image).

Cached files now land under web/backend/data/thumbnails/<feature>/ instead
— a directory excluded from the deploy rsync (like data/live/) so it
survives every deploy — and are served via a dedicated static mount
(see app/main.py) instead of the frontend build's catch-all route.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import DATA_DIR

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)
_MAX_BYTES = 5_000_000
_CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
    "image/webp": "webp", "image/gif": "gif", "image/svg+xml": "svg",
}

THUMBNAIL_DIR = DATA_DIR / "thumbnails"
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

    dest = THUMBNAIL_DIR / feature / f"{digest}.{ext}"
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return relative_path


def is_cached_thumbnail_missing(value: str | None) -> bool:
    """True only for a stored relative cache path (e.g. "data/thumbnails/
    event_bench/<hash>.jpg") whose file no longer exists under THUMBNAIL_DIR
    — used to clean up records left over from before the cache location
    moved off web/frontend/dist (see the module docstring): those records'
    thumbnail_url/hero_image_url still point at a path that's gone forever
    since the original source URL was already overwritten and can't be
    re-downloaded. An external http(s) URL or an already-empty value isn't
    "missing" in this sense — only a broken *local* reference is."""
    if not value or value.startswith(("http://", "https://")):
        return False
    return not (THUMBNAIL_DIR / value.removeprefix(f"{RELATIVE_ROOT}/")).is_file()


def as_absolute_path(value: str | None) -> str | None:
    """For live API responses only (the app is always served from the
    origin root locally, unlike the GitHub Pages build which can sit under
    a subpath) — turns a stored relative cache path into a root-absolute
    one so it renders correctly regardless of the current client-side
    route. External fallback URLs (http/https) pass through unchanged."""
    if not value or value.startswith(("http://", "https://", "/")):
        return value
    return f"/{value}"
