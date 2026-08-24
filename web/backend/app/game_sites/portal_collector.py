"""Discover official game websites from publisher-owned portals only."""
from __future__ import annotations

import html
import json
import re
import ssl
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener

from bs4 import BeautifulSoup

from ..config import BENCHMARK_DATA_DIR

# Smilegate's crossfire.do 301-loops on a cookie-less first request but
# succeeds once a cookie from an earlier smilegate.com request is attached
# (confirmed live) — a shared jar lets that earlier request's cookie carry
# over without any portal-specific special-casing.
_OPENER = build_opener(HTTPCookieProcessor(CookieJar()))
# asia.battlegrounds.pubg.com serves a cert that doesn't cover its own
# hostname (confirmed live: SSLCertVerificationError, hostname mismatch —
# a misconfiguration on PUBG's side, not ours). Only used as a fallback in
# _page_metadata, which fetches a public marketing title/thumbnail for
# display — no credentials or user data ever go through this opener.
_INSECURE_OPENER = build_opener(HTTPSHandler(context=ssl._create_unverified_context()))

DATA_DIR = BENCHMARK_DATA_DIR / "game_sites"
SNAPSHOT_PATH = DATA_DIR / "portal_snapshot.json"
OFFICIAL_PATH = DATA_DIR / "official_sites.json"
LAST_REFRESH_PATH = DATA_DIR / "last_refresh.json"
RECENT_DAYS = 730
PORTALS = {
    "NEXON": "https://oasisapi.nexon.com/game/mainlist",
    "NETMARBLE": "https://www.netmarble.net/",
    "KAKAO_GAMES": "https://web-contents-api.pcpf.kakaogames.com/contents/gametop?menu=main",
    "WEBZEN": "https://www.webzen.co.kr/",
    "GAMEMECA_SCHEDULE": "https://www.gamemeca.com/game.php?rts=schedule",
    "SMILEGATE": "https://www.smilegate.com/ko",
    "KRAFTON": "https://www.krafton.com/en/games/",
    "PEARL_ABYSS": "https://www.pearlabyss.com/Company/About/Games",
    "WEMADE": "https://www.wemade.com/games",
}
# NCSOFT, Com2uS: their game-list sections are client-rendered after page
# load (the games never appear in the raw HTML this module fetches with
# urlopen — confirmed by diffing a plain fetch against a real browser's
# DOM), so a static-HTML collector can't see them without a headless
# browser dependency this project doesn't otherwise need. ThisIsGame
# (디스이즈게임) 403s a plain fetch even with full browser-like headers —
# bot-protected past what a User-Agent tweak fixes. All three are
# deliberately left out rather than shipped broken.
_REJECT_HOST = ("help.", "forum.", "company.", "career.", "member.", "payment.", "privacy.", "pcbang.", "blog.", "ch.netmarble.com")
_REJECT_PATH = ("/event/", "/events/", "/promotion/", "/pg/", "/board/", "/news/", "/notice/", "/community/", "/support/", "/recruit/")
_REJECT_SCHEDULE_HOSTS = ("steampowered.com", "steamcommunity.com", "g123.jp")
# Publisher portals do not consistently expose release dates. These URLs were
# separately verified as titles introduced or actively prepared within the
# two-year window; no fabricated date is assigned to them.
RECENT_VERIFIED_URLS = {
    "https://7origin.netmarble.com/ko",
    "https://slvariseoverdrive.netmarble.com/ko",
    "https://chronoodyssey.kakaogames.com/ko",
    "https://poe2.kakaogames.com/",
    "https://sminiz.kakaogames.com/",
    "https://brand-mupocketknights.webzen.com/",
    "https://brand-r2origin.webzen.co.kr/",
    "https://brand-dragonsword.webzen.co.kr/",
    "https://brand-terbis.webzen.com/",
    "https://mumonarch2.webzen.co.kr/",
}


def _fetch(url: str, *, insecure: bool = False) -> tuple[bytes, str]:
    # Krafton's WordPress front returns 403 to the old bare identifying
    # UA (confirmed: same request succeeds with a full Chrome UA string +
    # Accept-Language, nothing else changed) — a real bot-detection
    # threshold, not a fluke, so this is the default for every portal now.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if "oasisapi.nexon.com" in url:
        headers.update({"Origin": "https://www.nexon.com", "Referer": "https://www.nexon.com/"})
    elif "kakaogames.com" in url:
        headers.update({"Origin": "https://kakaogames.com", "Referer": "https://kakaogames.com/"})
    req = Request(url, headers=headers)
    opener = _INSECURE_OPENER if insecure else _OPENER
    with opener.open(req, timeout=25) as response:
        return response.read(2_000_000), response.headers.get_content_charset() or "utf-8"


def _normalize_url(value: str) -> str | None:
    value = html.unescape(value or "").replace("\\/", "/").strip()
    if not value.startswith(("http://", "https://")):
        return None
    parsed = urlparse(value)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path or "/"
    if not host or any(host.startswith(x) for x in _REJECT_HOST) or any(x in path.lower() for x in _REJECT_PATH):
        return None
    return urlunparse(("https", parsed.netloc.lower(), path.rstrip("/") or "/", "", "", ""))


def _image(game: dict[str, Any]) -> str | None:
    images = game.get("extendGameInfo", {}).get("gameImageList", [])
    for kind in ("fileRecommendImg", "fileDelegate", "fileGnbDirect"):
        for item in images:
            if item.get("gameImageType") == kind and item.get("imageUrl"):
                return item["imageUrl"]
    return None


def _collect_nexon() -> list[dict]:
    raw, _ = _fetch(PORTALS["NEXON"])
    rows = []
    for game in json.loads(raw).get("gameList", []):
        basic = game.get("basicGameInfo", {})
        extended = game.get("extendGameInfo", {})
        url = _normalize_url(extended.get("gameWebUrl", {}).get("pcSiteUrl", ""))
        if not url:
            continue
        rows.append({"url": url, "game_name": basic.get("gameName") or "NEXON GAME", "publisher": "NEXON", "published_on": (basic.get("deployDate") or "").replace(".", "-"), "thumbnail_url": _image(game), "portal": "NEXON"})
    return rows


def _collect_netmarble() -> list[dict]:
    raw, charset = _fetch(PORTALS["NETMARBLE"])
    soup = BeautifulSoup(raw.decode(charset, "replace"), "html.parser")
    rows = []
    for anchor in soup.select('a[data-trcode="pc_pcgame_link"][href]'):
        url = _normalize_url(anchor.get("href", ""))
        if not url or not urlparse(url).netloc.lower().endswith(("netmarble.com", "netmarble.net")):
            continue
        title = anchor.select_one(".title")
        image = anchor.select_one("img")
        rows.append({"url": url, "game_name": title.get_text(" ", strip=True) if title else urlparse(url).netloc.split(".")[0], "publisher": "NETMARBLE", "published_on": None, "thumbnail_url": image.get("src") if image else None, "portal": "NETMARBLE"})
    return rows


def _collect_anchor_portal(name: str, url: str, allowed: tuple[str, ...]) -> list[dict]:
    raw, charset = _fetch(url)
    soup = BeautifulSoup(raw.decode(charset, "replace"), "html.parser")
    rows = []
    for anchor in soup.select("a[href]"):
        candidate = _normalize_url(anchor.get("href", ""))
        if not candidate or not any(urlparse(candidate).netloc.lower().endswith(x) for x in allowed):
            continue
        label = anchor.get_text(" ", strip=True) or urlparse(candidate).netloc.split(".")[0]
        image = anchor.select_one("img")
        rows.append({"url": candidate, "game_name": label[:100], "publisher": name, "published_on": None, "thumbnail_url": image.get("src") if image else None, "portal": name})
    return rows


def _walk_links(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"linkurl", "homepageurl", "url"} and isinstance(child, str):
                yield child, value
            yield from _walk_links(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_links(child)


def _collect_kakao() -> list[dict]:
    raw, _ = _fetch(PORTALS["KAKAO_GAMES"])
    data = json.loads(raw)
    rows = []
    for value, parent in _walk_links(data):
        url = _normalize_url(value)
        if not url or not urlparse(url).netloc.lower().endswith(("kakaogames.com", "onstove.com")):
            continue
        label = next((str(parent.get(k)) for k in ("title", "gameName", "name") if parent.get(k)), urlparse(url).netloc.split(".")[0])
        thumb = next((parent.get(k) for k in ("bannerImagePC", "imageUrl", "thumbnailUrl") if parent.get(k)), None)
        rows.append({"url": url, "game_name": label[:100], "publisher": "KAKAO GAMES", "published_on": None, "thumbnail_url": thumb, "portal": "KAKAO_GAMES"})
    return rows


def _collect_gamemeca_schedule() -> list[dict]:
    endpoint = "https://www.gamemeca.com/json.php?rts=json/index/gmdb_schedule"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; UXTLERGamePortalCollector/1.0)", "Referer": PORTALS["GAMEMECA_SCHEDULE"]}
    schedule: dict[str, dict] = {}
    year = date.today().year
    for month in range(1, 13):
        url = f"{endpoint}&type=list&ym={year}{month:02d}"
        with _OPENER.open(Request(url, headers=headers), timeout=25) as response:
            for item in json.loads(response.read()):
                schedule[item["gmid"]] = item
    rows = []
    for item in schedule.values():
        url = f"{endpoint}&type=today&ymd={item['symd']}&seq={item['seq']}"
        try:
            with _OPENER.open(Request(url, headers=headers), timeout=25) as response:
                details = json.loads(response.read())
        except Exception:
            continue
        if not details:
            continue
        detail = details[0]
        official = _normalize_url(detail.get("gm_url", ""))
        host = urlparse(official or "").netloc.lower()
        if not official or any(host == rejected or host.endswith("." + rejected) for rejected in _REJECT_SCHEDULE_HOSTS):
            continue
        released = item.get("symd", "")
        published = f"{released[:4]}-{released[4:6]}-{released[6:8]}" if len(released) == 8 else None
        rows.append({"url": official, "game_name": detail.get("gm_name") or re.sub(r"\s*\([^)]*\)\s*$", "", item.get("title", "")).strip(), "publisher": None, "published_on": published, "thumbnail_url": detail.get("thumbnail"), "portal": "GAMEMECA_SCHEDULE"})
    return rows


def _collect_path_portal(name: str, url: str, host_suffix: str, path_prefixes: tuple[str, ...]) -> list[dict]:
    """Like _collect_anchor_portal, but for sites whose nav (About/Careers/
    Studios/...) shares the same domain as the actual per-game pages —
    domain-only filtering pulled in the whole top nav on Smilegate and
    Krafton (confirmed against their real pages), so this also requires
    the path to start with one of path_prefixes (e.g. "/ko/game/")."""
    raw, charset = _fetch(url)
    soup = BeautifulSoup(raw.decode(charset, "replace"), "html.parser")
    rows = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        # Smilegate's per-game links are site-relative ("/ko/game/crossfire.do"),
        # unlike every other collector's source site — _normalize_url silently
        # drops anything that isn't already an absolute http(s) URL, so resolve
        # against the fetched page's own URL first.
        candidate = _normalize_url(urljoin(url, href) if href else href)
        if not candidate:
            continue
        parsed = urlparse(candidate)
        if not parsed.netloc.lower().endswith(host_suffix) or not any(parsed.path.startswith(p) for p in path_prefixes):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        label = anchor.get_text(" ", strip=True) or urlparse(candidate).path.rsplit("/", 2)[-2]
        image = anchor.select_one("img")
        rows.append({"url": candidate, "game_name": label[:100], "publisher": name, "published_on": None, "thumbnail_url": image.get("src") if image else None, "portal": name})
    return rows


def _resolve_outbound_links(rows: list[dict], anchor_selector: str) -> list[dict]:
    """For portals whose per-game page is the publisher's own intro page
    about the title rather than the game's actual site, follow the page's
    outbound "official website" anchor and collect that URL instead. Rows
    whose page has no such anchor (e.g. a nav/list page, not a real
    per-game page) are dropped rather than kept pointing at the wrong
    page. A target that 404s or 410s (e.g. Krafton's own "Official
    Website" link for Undusted points at a retired /undusted_en page —
    confirmed live, the site now only serves /undusted_kr) is dropped too
    rather than stored as a dead site; other failures (timeout, DNS) don't
    prove the target is gone, so those rows are kept without a title."""
    resolved = []
    for row in rows:
        try:
            raw, charset = _fetch(row["url"])
            soup = BeautifulSoup(raw.decode(charset, "replace"), "html.parser")
            anchor = soup.select_one(anchor_selector)
            target = _normalize_url(anchor.get("href", "")) if anchor else None
        except Exception:
            target = None
        if not target:
            continue
        title = None
        try:
            try:
                target_raw, target_charset = _fetch(target)
            except URLError as exc:
                if not isinstance(exc.reason, ssl.SSLCertVerificationError):
                    raise
                target_raw, target_charset = _fetch(target, insecure=True)
            title, _ = _extract_metadata(target_raw, target_charset)
        except HTTPError as exc:
            if exc.code in (404, 410):
                continue
        except Exception:
            pass
        row["url"] = target
        row["game_name"] = title or row["game_name"]
        resolved.append(row)
    return resolved


def _collect_smilegate() -> list[dict]:
    """Smilegate's /ko/game/*.do pages are Smilegate's own intro pages about
    each title, not the game's actual site — each one links out via a
    "GO TO WEBSITE" anchor (class="website_anchor") to the real external
    site (e.g. lostark.game.onstove.com). Follow that link so the collected
    URL is the game's own site, not a Smilegate-hosted page about it."""
    intro_pages = _collect_path_portal("SMILEGATE", PORTALS["SMILEGATE"], "smilegate.com", ("/ko/game/", "/en/game/"))
    return _resolve_outbound_links(intro_pages, "a.website_anchor[href]")


def _collect_krafton() -> list[dict]:
    """KRAFTON's /en|ko/games/<slug> pages are Krafton's own intro pages
    about each title (confirmed against inZOI, PUBG, TERA, Subnautica 2,
    [REDACTED]) — each real per-game page links out via an "Official
    Website" anchor (class="GameIconLink") to the game's actual site.
    Pages without that anchor (e.g. the "games-list" nav link, not a real
    per-game page) are dropped by _resolve_outbound_links."""
    intro_pages = _collect_path_portal("KRAFTON", PORTALS["KRAFTON"], "krafton.com", ("/en/games/", "/ko/games/"))
    return _resolve_outbound_links(intro_pages, "a.GameIconLink[href]")


_PEARL_ABYSS_REJECT_HOST = ("adjust.com", "google.com", "gstatic.com", "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "linkedin.com", "apple.com", "itunes.apple.com", "play.google.com", "onesto.re")


def _collect_pearlabyss() -> list[dict]:
    """Pearl Abyss lists each title's own official domain (e.g. playblackdesert.com)
    directly on its games page — unlike Smilegate/Krafton, these are real
    external sites, not self-hosted intro pages, so this can't reuse
    _collect_anchor_portal's single-domain allowlist. Filters out the ad-
    tracking/store/social links mixed into the same page instead."""
    raw, charset = _fetch(PORTALS["PEARL_ABYSS"])
    soup = BeautifulSoup(raw.decode(charset, "replace"), "html.parser")
    rows = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        url = _normalize_url(anchor.get("href", ""))
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        if host.endswith("pearlabyss.com") or host.endswith("pearlcdn.com") or any(host == r or host.endswith("." + r) for r in _PEARL_ABYSS_REJECT_HOST):
            continue
        if url in seen:
            continue
        seen.add(url)
        title, image = _page_metadata(url)
        rows.append({"url": url, "game_name": title or host.split(".")[0], "publisher": "Pearl Abyss", "published_on": None, "thumbnail_url": image, "portal": "PEARL_ABYSS"})
    return rows


_WEMADE_OFFICIAL_URL_RE = re.compile(r'\\"(\w+)_Official_Url\\":\\"([^\\]+)\\"')


def _collect_wemade() -> list[dict]:
    """WEMADE's games page is a Next.js app whose per-title official/store
    URLs aren't in plain <a href> links — they're embedded as an escaped
    JSON blob inside a React Server Components script payload (confirmed
    live: '\\"Night_Crows_Official_Url\\":\\"https://www.nightcrows.com/\\"'),
    so this extracts that key/value pattern directly rather than parsing DOM."""
    raw, charset = _fetch(PORTALS["WEMADE"])
    text = raw.decode(charset, "replace")
    rows = []
    seen: set[str] = set()
    for key, href in _WEMADE_OFFICIAL_URL_RE.findall(text):
        url = _normalize_url(href)
        if not url or url in seen:
            continue
        seen.add(url)
        label = key.replace("_", " ").strip()
        rows.append({"url": url, "game_name": label[:100], "publisher": "WEMADE", "published_on": None, "thumbnail_url": None, "portal": "WEMADE"})
    return rows


def discover_portal_sites() -> tuple[list[dict], dict[str, str]]:
    rows: list[dict] = []
    errors: dict[str, str] = {}
    collectors = {
        "NEXON": _collect_nexon,
        "NETMARBLE": _collect_netmarble,
        "KAKAO_GAMES": _collect_kakao,
        "WEBZEN": lambda: _collect_anchor_portal("WEBZEN", PORTALS["WEBZEN"], ("webzen.co.kr", "webzen.com")),
        "GAMEMECA_SCHEDULE": _collect_gamemeca_schedule,
        "SMILEGATE": _collect_smilegate,
        "KRAFTON": _collect_krafton,
        "PEARL_ABYSS": _collect_pearlabyss,
        "WEMADE": _collect_wemade,
    }
    for name, collector in collectors.items():
        try:
            rows.extend(collector())
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
    by_url = {item["url"]: item for item in rows}
    return list(by_url.values()), errors


def _extract_metadata(raw: bytes, charset: str) -> tuple[str | None, str | None]:
    # BeautifulSoup rather than a regex — a regex needs quoted attribute
    # values and og:image before content in source order, which real
    # sites don't reliably follow (tera-console.com's og:image is
    # unquoted; confirmed live).
    soup = BeautifulSoup(raw.decode(charset, "replace"), "html.parser")
    title_tag = soup.select_one("title")
    clean_title = title_tag.get_text(" ", strip=True) if title_tag else None
    image_tag = soup.select_one('meta[property="og:image"], meta[name="og:image"], meta[name="twitter:image"]')
    image = image_tag.get("content") if image_tag else None
    return clean_title or None, image or None


def _rendered_page_metadata(url: str) -> tuple[str | None, str | None]:
    """Fallback for pages whose real content only exists after client-side
    JS runs (confirmed live: lastepoch.com serves a Nuxt loading shell with
    no meta tags at all in the raw HTML). Renders the page with Playwright
    and reads the title/og:image from the live DOM; when there's still no
    og:image after rendering, falls back to the largest real (non-icon)
    <img> visible on the page rather than leaving the thumbnail empty."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None
    script = """() => {
        const meta = document.querySelector('meta[property="og:image"], meta[name="og:image"], meta[name="twitter:image"]');
        let image = meta ? meta.getAttribute('content') : null;
        if (!image) {
            let best = null, bestArea = 0;
            for (const el of document.querySelectorAll('img')) {
                const r = el.getBoundingClientRect();
                const area = r.width * r.height;
                if (area > bestArea && el.naturalWidth > 150 && el.naturalHeight > 100) {
                    bestArea = area;
                    best = el.currentSrc || el.src;
                }
            }
            image = best;
        }
        return { title: document.title || null, image };
    }"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                # onewayticketstudio.com serves a cert its own hostname
                # doesn't validate against (confirmed live) — this context
                # only renders a page to read its public title/thumbnail,
                # never handles credentials, so ignoring cert errors here
                # is the same low-risk tradeoff as _INSECURE_OPENER above.
                page = browser.new_page(ignore_https_errors=True)
                # "networkidle" hangs to a timeout on sites that keep a
                # background connection open (confirmed live: lastepoch.com
                # never goes idle) — "load" plus a flat pause for late
                # client-side rendering is reliable across more sites.
                page.goto(url, wait_until="load", timeout=20000)
                page.wait_for_timeout(2000)
                result = page.evaluate(script)
            finally:
                browser.close()
        return result.get("title") or None, result.get("image") or None
    except Exception:
        return None, None


def _page_metadata(url: str) -> tuple[str | None, str | None]:
    try:
        try:
            raw, charset = _fetch(url)
        except URLError as exc:
            if not isinstance(exc.reason, ssl.SSLCertVerificationError):
                raise
            raw, charset = _fetch(url, insecure=True)
        title, image = _extract_metadata(raw, charset)
    except Exception:
        title, image = None, None
    if not image:
        rendered_title, rendered_image = _rendered_page_metadata(url)
        title = title or rendered_title
        image = image or rendered_image
    return title, image


def refresh_portal_sites() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    previous = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")) if SNAPSHOT_PATH.is_file() else []
    previous_urls = {item["url"] for item in previous}
    discovered, errors = discover_portal_sites()
    now = datetime.now(timezone.utc)
    boundary = date.today() - timedelta(days=RECENT_DAYS)
    existing = json.loads(OFFICIAL_PATH.read_text(encoding="utf-8")) if OFFICIAL_PATH.is_file() else []
    official_urls = {item["url"] for item in existing}
    added = 0
    for item in discovered:
        published = item.get("published_on")
        recent_dated = False
        if published:
            try:
                recent_dated = date.fromisoformat(published) >= boundary
            except ValueError:
                pass
        is_new = bool(previous_urls) and item["url"] not in previous_urls
        verified_recent = item["url"] in RECENT_VERIFIED_URLS
        if item["url"] in official_urls or not (recent_dated or verified_recent or is_new):
            continue
        title, image = _page_metadata(item["url"])
        existing.append({"id": f"portal:{item['portal']}:{len(existing)+1}", "game_name": item["game_name"], "site_name": title or item["game_name"], "site_type": "OFFICIAL", "url": item["url"], "thumbnail_url": image or item.get("thumbnail_url"), "publisher": item["publisher"], "platform": [], "discovered_at": now.isoformat(), "published_on": published, "source": f"OFFICIAL_PORTAL:{item['portal']}", "evidence_url": PORTALS[item["portal"]], "status": "ACTIVE", "verified_at": now.isoformat()})
        official_urls.add(item["url"])
        added += 1
    OFFICIAL_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    SNAPSHOT_PATH.write_text(json.dumps(discovered, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"portals": len(PORTALS), "discovered": len(discovered), "new_sites": added, "errors": errors, "refreshed_at": now.isoformat()}
    LAST_REFRESH_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
