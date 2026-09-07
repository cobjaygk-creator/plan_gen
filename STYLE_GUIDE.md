# UX Insight 디자인 스타일 가이드

`event-bench` 페이지(https://cobjaygk-creator.github.io/plan_gen/#/event-bench)와 앱 전역에서 실제로 쓰이는 CSS를 그대로 추출한 가이드입니다. 다른 프로젝트에 이 스타일을 적용할 때, 아래 토큰과 컴포넌트 레시피를 그대로 옮기면 됩니다.

---

## 1. 디자인 톤

- **미니멀 유틸리티 대시보드**. 그림자·그라디언트를 거의 안 쓰고, 1px 얇은 테두리와 라운드 코너로 구획을 나눔
- 컬러는 거의 흑백·회색조이고, **파랑(#2878e8) 하나만 액센트**로 씀. 상태 표시(신규/종료 등)에만 빨강/주황 같은 포인트 컬러를 예외적으로 사용
- 폰트는 굵기 대비(400~900)로 위계를 만들고, 색상 대비는 최소화 — 제목은 진한 검정(#111), 본문은 회색(#777~#888)

---

## 2. 디자인 토큰 (CSS 커스텀 프로퍼티)

전역 `:root`에 이렇게 선언되어 있고, 다크 모드는 `prefers-color-scheme: dark`로 값만 갈아끼웁니다.

```css
:root {
  --bg: #f5f6f8;
  --surface: #ffffff;
  --surface-sunken: #eef0f3;
  --ink: #171b23;
  --ink-muted: #5b6472;
  --ink-faint: #8891a0;
  --accent: #0052cc;
  --accent-ink: #ffffff;
  --accent-soft: #deebff;
  --border: #e2e5ea;
  --border-strong: #ccd1d9;
  --success: #2e8b57;
  --warning: #c98a1b;
  --danger: #c0473f;
  --shadow: 0 1px 2px rgba(23, 27, 35, 0.04), 0 6px 20px rgba(23, 27, 35, 0.06);
  --radius: 8px;
  --font: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont,
    "Apple SD Gothic Neo", "Malgun Gothic", "Segoe UI", sans-serif;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151b;
    --surface: #1b1f27;
    --surface-sunken: #20242d;
    --ink: #edeff3;
    --ink-muted: #97a1b0;
    --ink-faint: #6b7382;
    --accent: #579dff;
    --accent-ink: #08182b;
    --accent-soft: #1c2b41;
    --border: #2a2f3a;
    --border-strong: #3a4150;
    --success: #4caf7d;
    --warning: #e0a940;
    --danger: #e0685f;
    --shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 8px 24px rgba(0, 0, 0, 0.35);
  }
}

* { box-sizing: border-box; }
body { margin: 0; font-family: var(--font); color: var(--ink); background: var(--bg); -webkit-font-smoothing: antialiased; }
button, input { font-family: inherit; }
a { color: inherit; }
```

**주의**: 실제 콘텐츠 영역(카드, 탭, 배지 등)은 위 변수 대신 **하드코딩된 회색 계열 hex**(`#111`, `#555`, `#777`, `#888`, `#ddd`, `#dedede`, `#f1f1f1` 등)를 훨씬 많이 씁니다. 다크 모드 대응이 필요 없는 프로젝트라면 이 방식이 더 간단합니다 — 아래 컴포넌트 레시피는 실제 코드 그대로(하드코딩 값)를 옮겼습니다.

### 자주 쓰이는 하드코딩 그레이 스케일 (콘텐츠 영역)
| 용도 | 값 |
|---|---|
| 제목/강조 텍스트 | `#111` |
| 카드 안 본문 텍스트 | `#222` |
| 보조 텍스트(레이블) | `#555` ~ `#666` |
| 캡션/메타 텍스트 | `#777` ~ `#888` |
| 아주 옅은 배경(뱃지 등) | `#f1f1f1`, `#eef0f3` |
| 기본 테두리 | `#dedede`, `#ddd`, `#e5e5e5`, `#e3e3e3` |
| 활성(active) 배경/테두리 | `#111` (흑백 반전) 또는 `#2878e8` (파랑, 필터류에서만) |

---

## 3. 타이포그래피 규칙

- 폰트는 항상 `var(--font)` 하나만 사용 (Pretendard Variable 우선, 시스템 산세리프 폴백)
- **글자 크기가 커질수록 letter-spacing을 더 촘촘하게(음수로) 줍니다** — 이게 이 스타일의 핵심 습관입니다:

| 크기 | letter-spacing | 용도 |
|---|---|---|
| 34px | `-0.06em` | 페이지 상단 큰 숫자(통계 요약) |
| 28px | `-0.055em` | 페이지 타이틀(h1) |
| 24px | `-0.055em` | 섹션 안 통계 숫자 |
| 22px | `-0.02em` | 브랜드 로고 텍스트 |
| 19px | `-0.01em` | 페이지 서브 타이틀 |
| 17px | `-0.035em` | 카드 제목(h2) |
| 14px 이하 | 보통 `0` (지정 안 함) | 본문/라벨 |

- 폰트 굵기: `700`(굵게, 대부분의 라벨/버튼) / `750`·`800`·`900`(더 굵게, 강조용) / `400`(기본 본문)이 전부 — 500·600은 거의 안 씀
- 숫자가 나열되는 곳(통계, 카운트)엔 `font-variant-numeric: tabular-nums`(`.tabular` 클래스)를 붙여 자릿수 정렬

---

## 4. 레이아웃 / 스페이싱

- 페이지 컨테이너: `max-width: 1320px; margin: 0 auto; padding: 28px 22px 44px;`
- 카드/블록 사이 기본 간격: `12px` ~ `18px` (촘촘한 편)
- 라운드 코너: 카드/큰 블록 `10px`, 버튼/탭/입력 `6px~8px`, 배지/알약형 `999px`(완전한 pill)
- 테두리는 항상 **1px 실선**, 그림자는 거의 안 씀(카드에 그림자 없음 — 테두리만으로 구획)
- 반응형 브레이크포인트: `1100px`(4열→3열), `900px`(3열→2열), `600px`(모바일, 1열 + 패딩 축소)

---

## 5. 컴포넌트 레시피

### 5.1 카드 (기본 블록)
```css
.card {
  background: #fff;
  border: 1px solid #dedede;
  border-radius: 10px;
  overflow: hidden;
}
.card-body { padding: 14px 15px 15px; }
```
이미지가 있는 카드는 `aspect-ratio: 16 / 9; object-fit: cover;`로 썸네일을 통일합니다.

### 5.2 카드 그리드
```css
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
@media (max-width: 1100px) { .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 900px)  { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px)  { .grid { grid-template-columns: 1fr; } }
```

### 5.3 필터 칩(테두리형 버튼) — "전체/게임A/게임B..." 같은 다건 필터
```css
.filter-chip-row { display: flex; flex-wrap: wrap; gap: 7px; margin: 0 0 18px; }
.filter-chip {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 8px 12px; border: 1px solid #ddd; border-radius: 7px;
  background: #fff; color: #555; font-size: 12px; font-weight: 700; cursor: pointer;
}
.filter-chip:hover { border-color: #aaa; color: #111; }
.filter-chip.is-active { border-color: #111; background: #111; color: #fff; }
/* 칩 안에 카운트 숫자를 넣을 때 */
.filter-chip .count {
  min-width: 17px; padding: 1px 5px; border-radius: 99px;
  background: #f1f1f1; color: #777; font-size: 10px; text-align: center;
}
.filter-chip.is-active .count { background: #333; color: #fff; }
```

### 5.4 세그먼트 컨트롤(둥근 알약 안에 탭이 붙어있는 형태) — 2~3개 소수 옵션 전환용
```css
.segment { display: flex; align-items: center; gap: 2px; padding: 3px; border: 1px solid #d9dde5; border-radius: 8px; background: #fff; }
.segment button {
  padding: 7px 12px; border: 0; border-radius: 5px; background: transparent;
  color: #666; font-size: 12px; font-weight: 700; cursor: pointer;
  transition: background .15s, color .15s;
}
.segment button:hover { background: #eef5ff; color: #246dcc; }
.segment button.is-active { background: #2878e8; color: #fff; box-shadow: 0 1px 2px rgb(23 83 160 / 18%); }
```
> 5.3(필터 칩)과 5.4(세그먼트)의 차이: **칩은 각자 독립된 테두리 버튼**(다건 카테고리용), **세그먼트는 하나의 알약 안에 여러 옵션이 붙어있는 형태**(상태 전환 같은 2~3지선다용)입니다. 실제 페이지에서 카테고리 필터는 칩, 상태/형식 필터는 세그먼트로 구분해서 씁니다.

### 5.5 배지 / 뱃지 (상태 표시)
```css
.badge { padding: 3px 6px; border-radius: 99px; font-size: 10px; font-weight: 700; line-height: 1.1; }
.badge-neutral { background: #f1f1f1; color: #555; }      /* 기본 */
.badge-ended   { background: #f0f0f0; color: #777; }      /* 종료됨 */
.badge-accent  { background: #f47a20; color: #fff; }      /* 강조 유형(주황) */
.badge-info    { border: 1px solid #b9d4f5; background: #eaf4ff; color: #2169ad; } /* 정보성(파랑, 테두리 있음) */
.badge-new     { background: #d8432c; color: #fff; font-weight: 800; }            /* NEW(빨강) */
```
썸네일 위에 겹쳐 놓는 "NEW" 배지:
```css
.thumbnail-badge { position: absolute; top: 10px; left: 10px; z-index: 1; box-shadow: 0 1px 4px rgba(0,0,0,.16); }
```

### 5.6 큰 숫자 통계 블록 (헤더 요약, 대시보드 KPI)
```css
.stat strong { display: block; color: #111; font-size: 34px; line-height: 1; letter-spacing: -.06em; }
.stat span { color: #777; font-size: 12px; }
```
여러 개를 가로로 붙일 때(구분선 있는 통계 그룹):
```css
.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid #e5e5e5; border-radius: 6px; overflow: hidden; background: #fff; }
.stat-row > div { min-height: 58px; padding: 10px 12px; }
.stat-row > div + div { border-left: 1px solid #e5e5e5; }
.stat-row strong { display: block; color: #111; font-size: 24px; line-height: 1; letter-spacing: -.055em; }
.stat-row span { display: block; margin-top: 6px; color: #777; font-size: 11px; font-weight: 700; }
```

### 5.7 리스트형 추천/미리보기 아이템 (썸네일 + 텍스트 가로 배치)
```css
.list-item { display: flex; min-width: 0; gap: 9px; color: inherit; text-decoration: none; }
.list-item img { flex: 0 0 74px; width: 74px; height: 52px; border-radius: 5px; object-fit: cover; background: #efefef; }
.list-item .eyebrow { color: #777; font-size: 10px; }
.list-item .title { margin: 2px 0; color: #181818; font-size: 12px; line-height: 1.3;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.list-item .time { color: #888; font-size: 10px; }
.list-item:hover .title { text-decoration: underline; }
```

### 5.8 버튼 (전역)
```css
.btn { font-family: var(--font); font-size: 14px; font-weight: 700; padding: 11px 18px;
  border-radius: 6px; border: 1px solid transparent; cursor: pointer; transition: filter .15s, background .15s; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover:not(:disabled) { filter: brightness(1.06); }
.btn-ghost { background: transparent; border-color: var(--border-strong); color: var(--ink); }
.btn-ghost:hover:not(:disabled) { background: var(--surface-sunken); }
```
콘텐츠 영역에서 자주 쓰는 "흑백 반전" 버튼(활성/선택 표시용, 위 필터 칩과 같은 규칙):
```css
.btn-invert { border: 1px solid #111; background: #111; color: #fff; font-weight: 750; }
.btn-invert:hover { background: #333; }
.btn-invert:disabled { background: #555; }
```

### 5.9 입력 필드
```css
.field label { display: block; font-size: 12.5px; font-weight: 600; color: var(--ink-muted); margin-bottom: 6px; }
.field input { width: 100%; font-size: 14px; padding: 10px 12px; border: 1px solid var(--border-strong);
  border-radius: 6px; background: var(--surface); color: var(--ink); outline: none;
  transition: border-color .15s, box-shadow .15s; }
.field input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
```

### 5.10 상단 내비게이션(GNB) + 좌측 내비게이션(LNB)
```css
.gnb { height: 56px; display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; border-bottom: 1px solid var(--border); background: var(--surface); }
.brand-name { font-size: 22px; font-weight: 900; letter-spacing: -.02em; }
.user-chip { display: flex; align-items: center; gap: 8px; padding: 4px 8px 4px 4px;
  border-radius: 999px; border: 1px solid var(--border); cursor: pointer; }
.avatar { width: 24px; height: 24px; border-radius: 50%; background: var(--accent-soft);
  color: var(--accent); font-size: 11px; font-weight: 800; display: flex; align-items: center; justify-content: center; }

.lnb { width: 220px; background: var(--surface-sunken); border-right: 1px solid var(--border); padding: 16px 12px; }
.lnb-group-label { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: var(--ink-faint); padding: 0 10px; margin-bottom: 6px; }
.lnb-item { display: flex; align-items: center; gap: 10px; padding: 9px 10px; border-radius: 6px;
  font-size: 13.5px; font-weight: 600; color: var(--ink-muted); text-decoration: none; }
.lnb-item:hover { background: var(--surface); color: var(--ink); }
.lnb-item.active { background: var(--accent-soft); color: var(--accent); }

.content { padding: 28px 32px; }
.page-head h1 { font-size: 19px; font-weight: 700; margin: 0 0 4px; letter-spacing: -.01em; }
.page-head p { font-size: 13px; color: var(--ink-muted); margin: 0; }
```

---

## 6. 인터랙션 규칙

- **호버**: 테두리만 있는 버튼/칩은 `border-color`를 진하게(`#aaa`~`#999`) + 텍스트를 `#111`로. 배경 없는 링크는 `text-decoration: underline`
- **활성(선택됨) 상태**: 대부분 "흑백 반전"(`background: #111; color: #fff;`)이 기본. 필터/세그먼트류만 예외적으로 파랑(`#2878e8`) 사용
- **비활성(disabled)**: `opacity: .55~.6` + `cursor: not-allowed` 또는 `default`
- **포커스**: `outline: 2px solid`(액센트 컬러) `+ outline-offset: 2px` — 키보드 접근성 위해 항상 넣음
- 트랜지션은 `.15s` 안팎으로 짧게, `border-color`/`background`/`color`/`filter` 정도만 애니메이션

---

## 7. Cursor에게 전달할 때 요약 프롬프트 (참고)

> 이 프로젝트의 색상은 흑백/회색조 + 파랑(#2878e8) 액센트 하나만 쓰고, 카드/버튼/배지는 그림자 없이 1px 테두리 + 라운드 코너(카드 10px, 버튼 6~8px, 배지 999px)로 구획한다. 폰트는 Pretendard 계열, 큰 글자일수록 letter-spacing을 음수로 좁힌다(예: 28px 제목엔 -0.055em). 활성 상태는 기본적으로 흑백 반전(검정 배경+흰 글자)으로 표시하고, 세그먼트형 필터에만 파란 액센트를 쓴다. 위 CSS 변수와 컴포넌트 레시피를 그대로 이 프로젝트의 전역 스타일에 이식해줘.
