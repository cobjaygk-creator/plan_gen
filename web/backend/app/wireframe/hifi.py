from __future__ import annotations

import re

from .converter import SlideDoc
from .generator import Page, outline_text

HIFI_MODEL = "claude-sonnet-5-5"
THEME_MAX_TOKENS = 8000
PAGE_MAX_TOKENS = 32000

THEME_SYSTEM = """너는 게임/서비스 공식 사이트를 설계하는 시니어 웹 UI 디자이너다. 화면설계서(SB)의 문서 정보와 공통 레이아웃 규칙을 읽고, 그 서비스에 어울리는 디자인 테마(CSS)를 만든다. 이 테마는 문서의 모든 페이지 시안이 공유한다.

규칙:
- 문서 정보에 [와이어프레임 설정 장표 — 최우선 반영]이 있으면 그 내용(스타일, 색상, 해상도, 레이아웃, 시각 기준, 필수·금지 조건)을 최우선 기준으로 따른다. 장표에서 "예)"로 시작하는 문구와 안내 문장은 입력값이 아니라 작성 예시이므로 값으로 쓰지 않는다.
- 설정 장표가 스타일·색상을 지정하지 않았다면 기본 테마는 화이트·그레이 무채색 와이어프레임 톤이다. 브랜드 컬러와 다크 배경은 쓰지 않는다.
  · 배경 #ffffff와 연회색 #f3f4f5, 구분선 #d9dcdf, 본문 #1f2328, 보조 텍스트 #6b7178, 비활성 #a3a9af.
  · 포인트 컬러 없이, 강조는 진한 회색/검정(#2b2f33)과 글자 굵기, 면 대비로만 표현한다. 기본 버튼은 진회색 면에 흰 글자, 보조 버튼은 흰 면에 회색 테두리.
  · 이미지/영상 자리는 연회색 면에 은은한 대각선 패턴을 둔다.
  · 타이포 위계와 여백은 완성도 있게 잡아 시안 수준으로 만든다.
- 출력은 순수 CSS 하나뿐이다. 코드펜스, 설명, <style> 태그를 쓰지 않는다.
- 포함할 것: :root 디자인 토큰(--bg --surface --ink --ink-muted --accent --line --radius 등), 리셋, Noto Sans KR 기반 타이포 위계(.display .h1 .h2 .body .eyebrow), 컨테이너(.wrap: 레이아웃 규칙의 콘텐츠 최대 폭, 좌우 중앙), 버튼(.btn .btn-primary .btn-ghost 의 hover/focus 상태), 카드(.card hover), 태그/배지(.tag), GNB(.gnb 와 스크롤 후 .gnb.solid 상태), 섹션(.section), 이미지/영상 자리(.ph: 그라디언트와 은은한 패턴, 라벨용 .ph-label), 목록 행(.row hover), 페이지네이션/탭(.tabs .tab.active, .pager), 포커스 링, 반응형 유틸.
- 외부 이미지 URL, 외부 라이브러리를 쓰지 않는다. 폰트는 @import 없이 font-family 선언만 하고(페이지 쪽에서 링크로 불러온다) fallback을 둔다.
- 400줄 이내로 간결하게."""

PAGE_SYSTEM = """너는 시니어 웹 UI 디자이너 겸 프런트엔드 개발자다. 화면설계서(SB)의 요소 목록과 번호별 설명을 분석해, 실제 사이트 해상도로 동작하는 시안 HTML 한 장을 만든다.

입력: 문서 정보, 공통 레이아웃 규칙, 이 페이지의 요소 목록(962px 프레임 기준 좌표), 번호별 설명.

규칙:
- 출력은 <!doctype html>부터 </html>까지 단일 HTML 문서 하나뿐이다. 설명과 코드펜스는 쓰지 않는다.
- 문서 정보에 [와이어프레임 설정 장표 — 최우선 반영]이 있으면 화면 범위·목적, 사용자와 핵심 흐름, 레이아웃과 정보 구조, 컴포넌트와 상태, 시각 기준과 제약, 생성 지시사항을 모두 반영한다. 설계서 내용과 충돌하면 설정 장표가 우선이다. 장표에서 "예)"로 시작하는 문구와 안내 문장은 작성 예시이므로 값으로 쓰지 않는다. 컴포넌트·상태에 적힌 상태(로딩, 빈 화면, 오류, 완료 등)는 화면 안에서 직접 확인할 수 있게(우측 하단 상태 전환 버튼 등) 구현한다.
- <head>에 Noto Sans KR 구글 폰트 <link>를 넣고, 아래 [테마 CSS]를 <style id="theme">에 그대로 넣은 뒤 페이지 전용 <style>을 추가한다. 테마 클래스를 우선 재사용한다.
- 실제 사이트 해상도로 만든다. 디자인 기준 해상도와 콘텐츠 최대 폭은 레이아웃 규칙을 따른다(없으면 1920/1600). 요소 좌표는 962px 프레임 기준의 상대 배치이므로 비율과 순서, 열 수, 개수를 그대로 따른다.
- 번호별 설명을 하나도 빠뜨리지 말고 분석해 반영한다.
  · 노출 조건, 개수, 정렬, 최대 줄 수는 그대로 구현한다.
  · 브라우저 폭에 따른 숨김/변형(예: 1620px 이하 숨김)은 @media로 구현한다.
  · 동작(스크롤 시 GNB 배경 전환, 섹션 인디케이터 클릭 시 해당 섹션으로 이동, 슬라이드/탭/아코디언/모달/호버, 플로팅 배너 닫기, 새 창 이동 등)은 바닐라 JS로 실제로 동작하게 만든다.
  · 데이터(CMS 값, 게시글, 날짜, 수치)는 설계서의 문구를 우선 쓰고 없으면 그럴듯한 자리표시 데이터를 쓴다.
- 이미지/영상 영역은 외부 URL 없이 테마의 연회색 .ph 면과 라벨로 표현한다(예: 라벨 "메인 배너 영상 2560×1440"). 색은 아래 [테마 CSS]의 팔레트만 쓴다(설정 장표가 없으면 화이트/그레이이며, 이 경우 브랜드 컬러, 다크 배경, 컬러 그라디언트는 쓰지 않는다).
- 번호 표식(#1 등)과 설계서 용어(SB, 슬라이드)를 화면에 드러내지 않는다. 개발 참고 메모가 필요하면 <span class="dev-note">로 쓰고 기본은 숨긴다(우측 하단 작은 토글 버튼으로 켜고 끈다).
- [다른 페이지 참고]는 실제 문구와 공통 요소(SNS 아이콘, 플로팅 배너, 푸터 등)를 재사용하기 위한 자료다. 이 페이지의 요소 목록과 번호별 설명에 없는 섹션이나 기능을 새로 만들어 넣지 않는다. 다만 이 페이지의 설명이 다른 페이지의 구간을 가리키는 경우(예: 섹션 인디케이터가 이동할 대상)에는 참고 페이지의 해당 구간을 축약해서 보여준다.
- 자리표시("TITLE AREA", "Title")가 이 페이지에 그대로 있으면 [다른 페이지 참고]의 실제 문구로 바꿔 쓴다.
- 외부 라이브러리 금지. 시맨틱 마크업과 키보드 포커스를 지킨다.

[테마 CSS]
{theme}"""

RELATED_PAGE_MAX_CHARS = 6000


SETTINGS_MAX_SLIDE_INDEX = 6
SETTINGS_HEADINGS = (
    "화면 범위와 목적", "사용자와 핵심 흐름", "레이아웃과 정보 구조",
    "컴포넌트와 상태", "시각 기준과 제약", "생성 지시사항",
)
SETTINGS_KEYWORDS = (
    "화면 범위", "화면 목적", "대상 화면", "핵심 흐름", "레이아웃", "정보 구조",
    "컴포넌트", "시각 기준", "스타일", "해상도", "생성 지시", "필수", "금지",
)


def slide_text(doc: SlideDoc) -> str:
    return "\n".join(item[5] for item in doc.items if item[5])


def find_settings_slide(docs: list[SlideDoc]) -> SlideDoc | None:
    """SB 앞쪽에 둔 '와이어프레임 설정 장표'를 찾는다 — 가이드 양식의 6개 소제목이
    2개 이상 있거나, '와이어프레임'·'프로토타입'이라는 말과 설정 키워드 3개 이상이 있는 비화면 슬라이드."""
    for doc in docs:
        if doc.index > SETTINGS_MAX_SLIDE_INDEX or doc.page_id or doc.annotations:
            continue
        text = slide_text(doc)
        if sum(heading in text for heading in SETTINGS_HEADINGS) >= 2:
            return doc
        if ("와이어프레임" in text or "프로토타입" in text) and sum(keyword in text for keyword in SETTINGS_KEYWORDS) >= 3:
            return doc
    return None


def deck_context(docs: list[SlideDoc]) -> str:
    chunks: list[str] = []
    settings = find_settings_slide(docs)
    if settings is not None:
        chunks.append(f"[와이어프레임 설정 장표 — 최우선 반영]\n{slide_text(settings)}")
    for doc in docs:
        if doc is settings:
            continue
        is_screen = bool(doc.page_id and doc.annotations)
        if is_screen and "-L-" not in doc.page_id:
            continue
        lines = [f"[{doc.title or '슬라이드 ' + str(doc.index)}]"]
        lines += [item[5] for item in doc.items if item[5]]
        lines += [f"#{a.number} {a.text.replace(chr(10), ' ')}" for a in doc.annotations]
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def _strip_fence(text: str) -> str:
    return re.sub(r"^```[a-zA-Z]*\n|\n```\s*$", "", text.strip())


def _extract_document(text: str) -> str:
    match = re.search(r"<!doctype html.*</html>", text, re.DOTALL | re.IGNORECASE)
    return match.group(0) if match else _strip_fence(text)


def _usage(final) -> dict:
    usage = final.usage
    return {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cacheRead": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cacheWrite": getattr(usage, "cache_creation_input_tokens", 0) or 0,
    }


def _call(client, model: str, system, user: str, max_tokens: int, on_text=None) -> tuple[str, dict]:
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        if on_text is not None:
            for chunk in stream.text_stream:
                on_text(len(chunk))
        final = stream.get_final_message()
    text = "".join(block.text for block in final.content if block.type == "text")
    return text, _usage(final)


def generate_theme(context: str, client=None, model: str = HIFI_MODEL, on_text=None) -> tuple[str, dict]:
    client = client or _client()
    text, usage = _call(client, model, THEME_SYSTEM, f"문서 정보와 공통 레이아웃 규칙:\n{context}", THEME_MAX_TOKENS, on_text)
    return _strip_fence(text), usage


def related_pages_text(pages: list[Page], current: Page) -> str:
    chunks = []
    for other in pages:
        if other.page_id == current.page_id or "-L-" in other.page_id:
            continue
        chunks.append(outline_text(other)[:RELATED_PAGE_MAX_CHARS])
    return "\n\n".join(chunks)


def generate_page_hifi(
    page: Page, context: str, theme_css: str, related: str = "", instruction: str = "", client=None,
    model: str = HIFI_MODEL, on_text=None,
) -> tuple[str, dict]:
    client = client or _client()
    system = [
        {"type": "text", "text": PAGE_SYSTEM.replace("{theme}", theme_css), "cache_control": {"type": "ephemeral"}}
    ]
    user = f"문서 정보와 공통 레이아웃 규칙:\n{context}\n\n[이 페이지]\n{outline_text(page)}"
    if related:
        user += f"\n\n[다른 페이지 참고]\n{related}"
    if instruction.strip():
        user += f"\n\n[사용자 추가 지시사항]\n{instruction.strip()}\n위 지시사항은 설계서의 모호한 부분을 보완하는 우선 요구사항으로 반영해라."
    text, usage = _call(client, model, system, user, PAGE_MAX_TOKENS, on_text)
    return _extract_document(text), usage


def _client():
    import anthropic

    return anthropic.Anthropic(timeout=900.0)
