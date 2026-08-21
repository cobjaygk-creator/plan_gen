"""Event sources whose real content only exists after client-side JS runs
(confirmed live: the plain urllib fetch in nexon_sample.py sees an empty
app shell). These use Playwright to actually render the page in a real
browser and read the DOM afterward, so they require the `playwright`
package plus its Chromium build (`playwright install chromium`) to be
present wherever this runs.

Kept in a separate module from nexon_sample.py so importing the existing
static-HTML collectors never requires Playwright to be installed.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.sync_api import Browser, sync_playwright

from .nexon_sample import EventCandidate

EPIC_SEVEN_EVENTS_URL = "https://page.onstove.com/epicseven/kr/list/1000"


def _collect_epic_seven(browser: Browser) -> list[EventCandidate]:
    """Epic Seven's official event board lives on Smilegate's shared STOVE
    community platform (page.onstove.com) — unlike Lost Ark's onstove
    board (server-rendered, see nexon_sample.py), this one ships an empty
    shell and fills the list in client-side JS (confirmed live: a plain
    fetch returns ~5KB with none of the event titles present)."""
    page = browser.new_page()
    try:
        page.goto(EPIC_SEVEN_EVENTS_URL, wait_until="networkidle", timeout=30000)
        # The board re-sorts/re-mounts its list shortly after first paint —
        # wait_for_selector() proved unreliable here (confirmed live: it
        # resolves on a transient render that then gets replaced, so an
        # eval_on_selector_all() right after it intermittently reads 0 rows
        # even across retries with short waits). A flat pause long enough to
        # clear that resort window was reliable across repeated live runs.
        page.wait_for_timeout(3000)
        rows = page.eval_on_selector_all(
            "section.s-board-item",
            """els => els.map(el => {
                const link = el.querySelector('a.s-board-link');
                const img = el.querySelector('.s-board-thumb-image');
                const date = el.querySelector('.s-board-info-date .s-board-info-text');
                return {
                    href: link ? link.getAttribute('href') : null,
                    title: link ? link.getAttribute('title') : null,
                    image: img ? img.getAttribute('src') : null,
                    date: date ? date.textContent.trim() : null,
                };
            })""",
        )
    finally:
        page.close()
    collected_at = datetime.now(timezone.utc).isoformat()
    candidates: list[EventCandidate] = []
    seen: set[str] = set()
    for row in rows:
        href, title = (row.get("href") or "").strip(), row.get("title")
        if not href or not title:
            continue
        event_url = urljoin(EPIC_SEVEN_EVENTS_URL, href)
        if event_url in seen:
            continue
        seen.add(event_url)
        image = row.get("image")
        if image:
            image = urljoin(EPIC_SEVEN_EVENTS_URL, image)
        published = None
        match = re.match(r"(\d{4})-(\d{2})-(\d{2})", row.get("date") or "")
        if match:
            published = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        candidates.append(EventCandidate(
            publisher="Smilegate", game="에픽세븐", title=title, event_url=event_url,
            hero_image_url=image, starts_on=None, ends_on=None,
            published_on=published, status="ongoing", event_format="board", collected_at=collected_at,
        ))
    return candidates


def collect_epic_seven_events() -> list[EventCandidate]:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            return _collect_epic_seven(browser)
        finally:
            browser.close()
