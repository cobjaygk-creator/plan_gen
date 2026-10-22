from __future__ import annotations

import re
from dataclasses import dataclass

from .converter import SlideDoc

_PAGE_SUFFIX_RE = re.compile(r"\s*\(\d+/\d+\)\s*$")


@dataclass
class Page:
    page_id: str
    title: str
    slides: list[SlideDoc]


def group_pages(docs: list[SlideDoc]) -> list[Page]:
    pages: list[Page] = []
    for doc in docs:
        if not doc.page_id or not doc.annotations:
            continue
        if pages and pages[-1].page_id == doc.page_id:
            pages[-1].slides.append(doc)
        else:
            pages.append(Page(doc.page_id, _PAGE_SUFFIX_RE.sub("", doc.title), [doc]))
    return pages


def _item_line(item: tuple) -> str:
    kind, x, y, w, h, text = item
    label = f' "{text}"' if text else ""
    return f"{kind} {x:.0f},{y:.0f} {w:.0f}x{h:.0f}{label}"


def _contains(outer: tuple, inner: tuple) -> bool:
    return (
        outer is not inner
        and outer[1] <= inner[1] + 2 and outer[2] <= inner[2] + 2
        and outer[1] + outer[3] >= inner[1] + inner[3] - 2
        and outer[2] + outer[4] >= inner[2] + inner[4] - 2
    )


def layout_hints(slide: SlideDoc) -> list[str]:
    big = [i for i in slide.items if i[0] in ("box", "image") and i[3] >= 120 and i[4] >= 100]
    top_level = [i for i in big if not any(_contains(o, i) for o in big)]
    columns: list[list[tuple]] = []
    for item in sorted(top_level, key=lambda i: i[1]):
        for column in columns:
            if abs(column[0][1] - item[1]) <= 10:
                column.append(item)
                break
        else:
            columns.append([item])
    if len(columns) < 2:
        return []
    widths = ", ".join(f"{max(i[3] for i in c):.0f}" for c in columns)
    counts = ", ".join(str(len(c)) for c in columns)
    return [f"큰 영역이 가로 {len(columns)}열 (왼쪽부터 너비 {widths}), 열별 영역 개수 {counts}"]


def outline_text(page: Page) -> str:
    chunks = [f"페이지: {page.title} ({page.page_id})"]
    for slide in page.slides:
        chunks.append(f"\n[구간: {slide.title}]")
        chunks.extend(_item_line(item) for item in slide.items if item[5] or item[0] != "text")
        hints = layout_hints(slide)
        if hints:
            chunks.append("배치 힌트(코드가 계산한 사실, 반드시 지킬 것):")
            chunks.extend(hints)
        if slide.annotations:
            chunks.append("번호별 설명:")
            chunks.extend(f"#{a.number} {a.text.replace(chr(10), ' ')}" for a in slide.annotations)
    return "\n".join(chunks)
