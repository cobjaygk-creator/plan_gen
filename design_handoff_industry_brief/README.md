# Handoff: 업계동향 (Industry Brief) 페이지 재설계

## Overview

`plan_gen/web/frontend` 의 **업계 동향** 화면(라우트 `/`, `IndustryBriefView`) 전체 재설계 패키지입니다.
탭 4개(업계동향 · 트렌드 · 정책/제도 · 기술 레이더)와 로딩/빈 상태를 포함합니다.

목표는 기능 추가가 아니라 **정보 위계 정리와 스타일 시스템 복구**입니다. 실사용자는 팀 내 기획자
몇 명 + 임원 보고이며, 화면을 그대로 캡처해 보고에 쓰는 사용 패턴이 전제입니다.

핵심 변경 5가지:

1. 모든 탭이 **리드 카드**(한 줄 판단 + 근거 3칸)로 시작하는 동일 골격
2. 핵심이슈 **자동 로테이션(6.5초) 완전 제거** — 읽는 도중 내용이 바뀌던 문제
3. `industry-brief.css` 1,960줄의 **중복 정의 지층 정리** + 토큰화 (다크모드 복구)
4. 그래프에 **y축 눈금·값·해석 문장** 복원, 버블 차트 → **순위 표**로 교체
5. **스켈레톤 로딩 / 전용 빈 상태 / 4단계 진행 표시** 신설

---

## About the Design Files

`designs/` 안의 파일은 **HTML로 만든 디자인 레퍼런스**입니다. 의도한 모양과 동작을 보여주는
프로토타입이며, 그대로 복사해 쓰는 프로덕션 코드가 아닙니다.

이 저장소의 실제 환경은 **React 18 + TypeScript + Vite + react-router-dom, 플레인 CSS**
(CSS-in-JS·유틸리티 프레임워크 없음)입니다. 디자인 레퍼런스의 인라인 스타일을 그대로 옮기지 말고,
**기존 패턴대로 `.css` 파일 + BEM 유사 클래스(`ib-*` 접두사)** 로 재현하세요.

- `designs/industry-brief-redesign.dc.html` — 4개 탭 + 상태 처리 시안 (캔버스, 좌우 스크롤)
- `designs/refactoring-guide.dc.html` — CSS 리팩터링 실행 지시서 (인쇄용 문서)
- `designs/doc-page.js` — 위 문서가 쓰는 런타임. 구현과 무관, 문서 열람용

> 두 HTML은 브라우저로 바로 열립니다. `.dc.html` 확장자지만 표준 HTML 문서입니다.

## Fidelity

**High-fidelity.** 색상·타이포·여백·상태가 모두 확정값입니다. 아래 Design Tokens 섹션의 값을
그대로 사용하세요. 다만 아이콘·레이아웃 프리미티브는 이미 저장소에 있는 것(`AppShell.tsx`의 인라인
SVG, `index.css`의 `.btn` / `.card` / `.field`)을 재사용합니다.

---

## 대상 파일

| 파일 | 역할 |
| --- | --- |
| `src/index.css` | 전역 토큰. **여기에 새 토큰 추가** |
| `src/features/industry-brief/industry-brief.css` | 1,960줄. **최대 정리 대상** |
| `src/features/industry-brief/components/IndustryBriefView.tsx` | 페이지 셸 · 탭 · 날짜 · 새로고침 |
| `.../components/IndustryPanelCard.tsx` | GAME/AI 패널, `DailyHighlightsBlock` |
| `.../components/IndustrySubmenu.tsx` | 탭 UI |
| `.../components/DateNavigator.tsx` | 날짜 이동 |
| `.../components/BriefAnalyticsPanel.tsx` | 관심도 라인 차트 |
| `.../components/TopicLandscapePanel.tsx` | 버블 차트 + 신선도 컬럼 |
| `.../components/PolicyUpdatesPanel.tsx` | 정책 타임라인 |
| `.../components/PolicyImpactPanel.tsx` | 정책 전후 막대 차트 |
| `.../components/SignalsPanel.tsx` | 주요 시그널 |
| `.../components/TechRadarPanel.tsx` | 기술 레이더 |
| `.../components/TrendKpiRow.tsx` | KPI 4종 |
| `.../components/IndustryLandscapePanel.tsx` | 업계 이슈 지도 |

**백엔드 변경 없음.** 모든 변경은 기존 응답 필드의 재배치·재렌더링입니다.

---

## Design Tokens

`src/index.css` 의 `:root` 에 추가. 다크 블록(`@media (prefers-color-scheme: dark)`)에도 대응값 추가.

```css
:root {
  /* ── 타이포: 기존 27종 → 6종 ───────────────── */
  --fs-page:  26px;   /* 페이지 제목 "게임 · AI 업계 동향" */
  --fs-lead:  40px;   /* 리드 헤드라인 (오늘의 판단) */
  --fs-title: 19px;   /* 섹션 제목 */
  --fs-card:  16px;   /* 카드/이슈 제목 (칼럼 안에서는 17px 허용) */
  --fs-body:  14.5px; /* 본문 */
  --fs-meta:  12.5px; /* 메타·라벨 */
  /* 배지 전용 11px 만 예외로 허용 */

  /* ── 여백: 4px 그리드 ───────────────────────── */
  --sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px;
  --sp-4: 16px; --sp-5: 24px; --sp-6: 32px;
  --card-pad: 24px;

  /* ── 카테고리색 (차트와 공유, 유일한 예외색) ── */
  --cat-game: #f2994a;
  --cat-ai:   #2f6feb;
}
```

기존 토큰은 그대로 사용합니다 (변경 없음):

| 토큰 | 라이트 | 다크 | 용도 |
| --- | --- | --- | --- |
| `--bg` | `#f5f6f8` | `#12151b` | 콘텐츠 영역 배경 |
| `--surface` | `#ffffff` | `#1b1f27` | 카드 |
| `--surface-sunken` | `#eef0f3` | `#20242d` | 배지·트랙 |
| `--ink` | `#171b23` | `#edeff3` | 제목·본문 |
| `--ink-muted` | `#5b6472` | `#97a1b0` | 보조 본문 |
| `--ink-faint` | `#8891a0` | `#6b7382` | 메타·라벨 |
| `--border` | `#e2e5ea` | `#2a2f3a` | 카드 테두리·구분선 |
| `--accent` | `#0052cc` | `#579dff` | **유일한 강조색** |
| `--accent-soft` | `#deebff` | `#1c2b41` | 활성 배경 |
| `--success` | `#2e8b57` | `#4caf7d` | 상승·교차확인 |
| `--warning` | `#c98a1b` | `#e0a940` | 마감·단일관점 |
| `--danger` | `#c0473f` | `#e0685f` | 하락 |

**반경**: 카드 `14px`, 내부 블록 `9px`, 컨트롤 `8px`, 배지 `5px`, 알약 `999px`
**그림자**: 카드는 그림자 없음. 테두리 `1px solid var(--border)` 만.
**폰트**: `--font` (Pretendard) 하나. **`OneStoreMobileGothicTitleFont` @font-face 는 삭제.**

### 없애야 할 하드코딩 색

`industry-brief.css` 에서 아래를 전부 토큰으로 치환합니다. 치환만으로 다크모드가 복구됩니다.

| 현재 | 교체 |
| --- | --- |
| `#2878e8` (서브메뉴 활성), `#285f9e` (링크), `#2f6feb` (차트 외 용도) | `var(--accent)` |
| `#111`, `#151515`, `#1f1f1f`, `#222` | `var(--ink)` |
| `#333`, `#444`, `#555`, `#666` | `var(--ink-muted)` |
| `#777`, `#888`, `#999`, `#a0a0a0` | `var(--ink-faint)` |
| `#dedede`, `#d8d8d8`, `#e1e1e1`, `#e5e5e5`, `#ececec`, `#eee` | `var(--border)` |
| `#fff` | `var(--surface)` |
| `#fafafa`, `#fcfcfc`, `#f9fbfe`, `#f3f3f3`, `#f0f0f0` | `var(--surface-sunken)` 또는 제거 |
| `#141a2b`, `#232b42`, `#7c8db8`, `#eef1fa`, `#8892ab` | **삭제** (다크 블록 제거) |

`--cat-game` / `--cat-ai` 만 리터럴 색을 유지합니다.

---

## Screens / Views

전체 4개 탭 모두 아래 **공통 셸**을 공유합니다.

### 공통 셸

- **GNB** — 높이 `56px`, `padding: 0 20px`, `border-bottom: 1px solid var(--border)`, 배경 `var(--surface)`
  - 브랜드 "UX Insight" — `font-weight: 800`, `20px`, `letter-spacing: -.03em` (기존 900/22px에서 조정)
  - 우측 사용자 칩 — 기존 `.user-chip` 그대로
- **LNB** — 폭 `212px` (기존 220px), 배경 **`var(--surface)`** (기존 `--surface-sunken` 에서 변경),
  `border-right: 1px solid var(--border)`, `padding: 16px 12px`
  - 항목: `padding: 9px 10px`, `border-radius: 7px`, `font-size: 13.5px`
  - 비활성 `font-weight: 500` / `color: var(--ink-muted)` (기존 600에서 완화)
  - 활성 `background: var(--accent-soft)` / `color: var(--accent)` / `font-weight: 600`
  - 아이콘은 `AppShell.tsx` 의 기존 인라인 SVG 6종 재사용 — **새로 그리지 말 것**
- **페이지 헤더** — `padding: 24px 40px 0`, `border-bottom: 1px solid var(--border)`
  - eyebrow `DAILY INDUSTRY BRIEF` — `11px / 700 / letter-spacing .14em / var(--ink-faint)`
  - h1 — `var(--fs-page)` / `700` / `letter-spacing -.03em`
  - 우측: 날짜 네비게이터 + 새로고침 버튼 (`background: var(--ink)`, `color: #fff`, `radius 8px`, `padding 9px 14px`)
  - **탭은 알약 세그먼트가 아니라 밑줄 탭**: `padding: 10px 2px`, 항목 간 `margin-right: 16px`,
    활성 `border-bottom: 2px solid var(--ink)` + `font-weight 600`, 비활성 `transparent` + `var(--ink-faint)`
  - 탭 행 우측 끝에 메타 한 줄 (`12.5px`, `var(--ink-faint)`) — 탭마다 문구 다름
- **콘텐츠** — `padding: 32px 40px 48px`, 세로 `flex`, `gap: 24px`, 배경 `var(--bg)`

> **날짜 네비게이터**: 현재 트렌드·정책 탭에서 조건부로 DOM에서 제거되어 탭 전환 시 헤더 높이가
> 흔들립니다. **자리는 유지하고 `disabled` + `opacity: .45`** 로 바꾸세요. 라벨도 탭에 맞게
> ("최근 30일", "2026년") 바꿉니다.

### 공통 컴포넌트: 리드 카드 (신설)

4개 탭 모두 최상단에 옵니다.

```
<section class="ib-lead">
  <div class="ib-lead-eyebrow">● 오늘의 판단</div>
  <p class="ib-lead-headline">…</p>
  <div class="ib-lead-grounds">  ← 3칸 또는 4칸
    <div><span>근거 1</span><p>…</p></div> ×3
  </div>
</section>
```

- 카드: `border: 1px solid var(--border)`, `radius 14px`, `background var(--surface)`, `padding: 36px 40px`
- eyebrow: 앞에 `6px` 원형 dot (`--success` / `--warning` / `--cat-ai`, 탭별) + `11px/700/.14em/var(--ink-muted)`
- 헤드라인: `var(--fs-lead)` / `700` / `line-height 1.32` / `letter-spacing -.04em` / `max-width: 38ch`
  — **`text-wrap` 을 건드리지 말고 `word-break: keep-all`** 로 한글 어절 보존
- 근거 구획: `grid`, 등폭, 칸 사이 `border-left: 1px solid var(--border)` + `padding: 0 28px`,
  상단 `border-top: 1px solid var(--border)` + `padding-top: 20px`
  - 라벨 `11px/700/.1em/var(--ink-faint)`, 본문 `var(--fs-body)/1.65/var(--ink-muted)`
  - 강조어만 `font-weight 600` + `var(--ink)`

---

### 1. 업계동향 탭 (`?tab` 없음, 기본)

**목적**: 오늘 무슨 일이 있었는지 5분 안에 파악하고, 리드 카드만 캡처해 보고에 붙인다.

레이아웃 (위→아래):

1. **리드 카드** — dot `--success`, eyebrow "오늘의 판단", 근거 3칸(근거 1 / 근거 2 / 지켜볼 것)
2. **GAME · AI 2칼럼** — `grid-template-columns: 1fr 1fr`, `gap: 20px`, `align-items: start`
3. **하단 2칼럼** — 오늘 새로 뜬 키워드 / 읽어볼 기사

#### GAME · AI 패널

- 카드 `padding: var(--card-pad)`, `radius 14px`
- 헤더: `3px × 18px` 세로 컬러 바(`--cat-game` / `--cat-ai`) + h2 `17px/700` + 건수 `12.5px/var(--ink-faint)`,
  아래 `border-bottom: 1px solid var(--border)`, `padding-bottom: 16px`
  — **기존 25px/800/letter-spacing -.065em 의 큰 "GAME" 로고 타입은 폐기**
- 이슈 3건, 각 `padding: 20px 0`, 사이 `border-bottom: 1px solid` (연한 구분선 — `--border` 보다 옅게)
  - `display: flex; gap: 14px`
  - 번호 `01/02/03` — `width: 22px`, `700 15px`, 색은 카테고리색, `tabular-nums`
  - 제목 `h3` — `17px/600/1.45/letter-spacing -.015em`, **줄바꿈 허용, 말줄임 없음**
  - 요약 `p` — `var(--fs-body)/1.7/var(--ink-muted)`, **clamp 없음**
  - 푸터 배지 행: `기사 N건` · `독립 매체 N곳` (`--surface-sunken` 배경, `--ink-muted`)
    \+ 신뢰도 배지 1종 + 우측 끝 `근거 기사 →` 링크(`13px/600/var(--accent)`)

**신뢰도 배지 3종** (기존 `confidence.level` / `verification` 필드 매핑):

| 라벨 | 배경 | 글자 | 조건 |
| --- | --- | --- | --- |
| 교차 확인 | `#e9f3ed` | `var(--success)` | `corroborated` / `STRONG` |
| 단일 관점 | `#fdf3e6` | `#a8721a` | `single_source` / `WEAK` |
| 신규 등장 | `#eef2f7` | `#43576b` | `state === "NEW"` / `EMERGING` |

> **`DailyHighlightsBlock` 삭제 대상**: `issuePage` state, 6.5초 `setInterval`,
> `animationDelay` 인라인 계산, `.ib-change-flap` 키프레임, `grid-template-rows: repeat(2, 150px)`,
> `.ib-highlight-core` 다크 배색, `OneStoreMobileGothicTitleFont`,
> `VISIBLE_CORE_ISSUES` 순환 인덱싱. `coreIssues.slice(0, 3)` 을 그냥 전부 렌더합니다.

#### 오늘 새로 뜬 키워드

`SignalsPanel` 데이터 사용. 행 5개, `grid-template-columns: minmax(0,1fr) 88px 64px`, `gap: 12px`,
`padding: 12px 0`, 행 사이 연한 구분선.

- 키워드 `15px/600/var(--ink)`
- 막대 `height: 6px`, `radius 999px`, 트랙 `--surface-sunken`, 채움색은 방향별
  (`up`→`--success`, `flat`→`#c9cfd8`, `down`→`--danger`), 폭 = `todayCount / max × 100%`
- 값 `13.5px/600`, 우측 정렬, 방향색. 신규는 `신규 N건`, 나머지는 `N건 ▲/—/▼`

#### 읽어볼 기사

`highlights.recommended` 사용. 항목 `padding: 12px 0`, 사이 연한 구분선.
매체명 `12.5px/600/var(--accent)` + 경과시간 `12px/var(--ink-faint)` → 제목 `15px/500/1.5/var(--ink)`.
**제목 `-webkit-line-clamp: 1` 과 `nowrap` 제거 — 줄바꿈 허용.**

---

### 2. 트렌드 탭 (`?tab=trend`)

**목적**: 최근 30일 흐름에서 무엇이 자리 잡고 무엇이 사라졌는지 판단.

1. **리드 카드** — dot `--success`, eyebrow "최근 30일 판단". 근거 구획 대신 **KPI 4칸**
   (수집 기사 / 활성 이슈 / 지속형 이슈(2일+) / 신규 토픽)
   - 값 `30px/700/letter-spacing -.035em/tabular-nums` + 옆에 델타 `13px/600` (`▲14%` 등)
   - `TrendKpiRow` 의 CountUp 애니메이션은 유지해도 되고 제거해도 됩니다 (진입 1회이므로 무해)
2. **이슈 관심도 변화** (`BriefAnalyticsPanel`)
3. **토픽 지형도** (`TopicLandscapePanel`) — **버블 → 표로 교체**
4. **정책 발표 → 업계 반응** (`PolicyImpactPanel`)

#### 관심도 라인 차트 — 수정 사항

현재 `left = 10` 이라 y축 라벨 공간이 없습니다.

- `left: 10 → 40`, `bottom: 35 → 44`
- 눈금선 3개 → **5개**, 각 선 좌측에 값 라벨 (`text-anchor: end`, `x = left - 10`, `12px/500/var(--ink-faint)`)
- 눈금 값은 `maximum` 을 4등분해 올림한 정수
- **범례의 `max-width: 31%` 삭제** — 잘리지 않게
- 범례 항목: `9px` 사각 색상칩 + `13.5px/600/var(--ink-muted)`
- 마지막 데이터 포인트에만 `r=4.5` 원 표시 (모든 점에 원 → 과밀)
- 차트 아래 **해석 문장 슬롯** 추가: `border-top: 1px solid`, `padding-top: 18px`,
  `var(--fs-body)/1.7/var(--ink-muted)`, 숫자만 `600/var(--ink)`
  예) "코딩 에이전트는 한 달 내내 완만하게 올라온 지속형이고, AI 브라우저는 마지막 사흘에 튀어오른 돌발형입니다."

> 색상은 기존 `COLORS = ["#2f6feb", "#f2994a", "#1f9d55"]` 유지 — 단 앞의 둘은
> `var(--cat-ai)` / `var(--cat-game)` 로 바꿉니다.

#### 토픽 지형도 — 버블 차트를 표로 교체

`TopicBubbleChart` 를 통째로 제거합니다 (`fanOffset`, 클러스터 배지, `ib-bubble-popover`,
`openGroup` state 포함). 겹친 원을 클릭해야 이름이 보이는 구조 자체가 문제였습니다.

새 표 — `grid-template-columns: 32px minmax(0,1fr) 96px 96px 110px 92px`, `gap: 16px`,
행 `padding: 14px 8px`:

| 열 | 정렬 | 스타일 |
| --- | --- | --- |
| 순위 | 좌 | `13px/600/var(--ink-faint)/tabular-nums` |
| 토픽 | 좌 | `9px` 색상칩(카테고리색) + `15.5px/600/var(--ink)` |
| 기사 | 우 | `15px/600/var(--ink)/tabular-nums` |
| 독립 출처 | 우 | `14px/500/var(--ink-muted)/tabular-nums` |
| 지속 | 우 | `14px/500/var(--ink-muted)` + "일" |
| 성격 | 우 | 배지 |

- 헤더 행: `11.5px/600/.06em/var(--ink-faint)`, 아래 `border-bottom: 1px solid var(--border)`
- 성격 배지: `신규`(`#eef2f7`/`#43576b`) · `지속`(`#e9f3ed`/`--success`) ·
  `관찰`(`#fdf3e6`/`#a8721a`) · `마케팅성`(`--surface-sunken`/`--ink-faint`)
- `isMarketing === true` 인 행은 **행 전체 `opacity: .5`**
- 7행까지 노출 후 전체폭 `나머지 N개 토픽 보기` 버튼
- 정렬 기준: `articleCount` 내림차순 (기존과 동일)
- 기존 `TopicFreshnessColumns`(신규 진입 vs 지속)는 이 표에 흡수되므로 **제거**

#### 정책 발표 → 업계 반응

기존 막대 차트 유지. 수정만:

- `left: 10 → 40`, y축 눈금 3개에 값 라벨 추가
- 제목 `16px → 17px/600`, 말줄임 제거
- 시사점 블록: `border-left: 3px solid var(--accent)`, `radius 0 8px 8px 0`,
  `background #f4f7fd`, `padding 12px 16px`, `14px/1.65/#33507a`, 앞에 `시사점 · ` (`700/var(--accent)`)

---

### 3. 정책 · 제도 탭 (`?tab=policy`)

**목적**: 지금 대응해야 하는 규제가 무엇이고 마감이 언제인지.

1. **상단 2칼럼** (`grid-template-columns: 1.4fr 1fr`, `gap: 20px`, `align-items: stretch`)
   - 좌: 리드 카드 (dot `--warning`, eyebrow "이번 달 판단", 헤드라인 `34px`, 근거 구획 없이 본문 한 단락)
   - 우: **D-day 카드 2장** (세로 스택, `gap: 12px`, 각 카드 `flex: 1`)
     - `border: 1px solid #f0e0c4`, `background #fffaf1`, `radius 14px`, `padding: 20px 24px`
     - `D-9` 배지 (`background var(--warning)`, `color #fff`, `11px/700`, `radius 5px`) +
       구분 라벨(`12.5px/600/#8b6a26`) + 제목 `16px/600/1.45/var(--ink)`
     - **신규 로직**: `PolicyUpdate` 중 마감/시행 예정일이 있는 항목을 D-day 계산해 상위 2건 승격
2. **정책 타임라인** 카드

#### 타임라인

- 필터: 카테고리 세그먼트(전체/게임/AI) + 유형 알약 7종 — 기존과 동일, 스타일만 토큰화
  - 세그먼트 활성 `background var(--ink)` / `color #fff` / `radius 5px`
  - 알약 활성 `background var(--ink)` / 비활성 `border 1px solid var(--border)` / `var(--ink-muted)`
- 항목: `grid-template-columns: 104px 20px minmax(0,1fr)`, `gap: 20px`, `padding-bottom: 28px`
  - **`min-height: 101px` 고정 제거** — 내용에 따라 자라게
  - 날짜: 우측 정렬, `13.5px/500/var(--ink-faint)/tabular-nums`. 오늘이면 아래 `오늘` (`12px/600/var(--warning)`)
  - dot: `11px` 원. 기본 `2px solid var(--ink)`. 48시간 이내면 `3px solid var(--warning)` +
    `box-shadow: 0 0 0 4px rgba(201,138,27,.14)`
    — **깜빡이는 `ib-policy-dot-pulse` 애니메이션은 제거** (계속 움직이는 요소 금지)
  - 세로 연결선: `position: absolute; top: 18px; bottom: -28px; width: 1px; background: var(--border)`.
    `::after` 고정 높이 `83px` 대신 이 방식으로 — 항목 높이가 가변이므로
  - 배지 행: 카테고리(게임 `#fdf0e3`/`#a8721a`, AI `#e7effc`/`#1d4fa8`) + 유형(`--surface-sunken`) +
    긴급도(`대응 필요` → `#fdecea`/`--danger`, `의견 제출 D-9` → `#fdf3e6`/`#a8721a`)
  - 제목 `a`: **`19px/600/1.45/letter-spacing -.02em`, 줄바꿈 허용** (기존 `18px` + `nowrap + ellipsis` 였음)
  - 설명 `p`: `var(--fs-body)/1.7/var(--ink-muted)`, `max-width: 82ch`
  - 시사점: 위 인용 블록 스타일 (있는 항목만)

---

### 4. 기술 레이더 탭 (`?tab=tech`)

**목적**: AI 카테고리 내부에서 어떤 세부 태그가 움직이는지.

1. **리드 카드** — dot `--cat-ai`, eyebrow "오늘의 태그 분포", 헤드라인 `34px`.
   근거 구획 대신 **태그 칩 행**: `padding: 7px 13px`, `radius 999px`, `14px/600`.
   상위 2개는 `background var(--accent-soft)` / `color var(--accent)`, 나머지는 `--surface-sunken` / `--ink-muted`.
   칩 텍스트는 `{label} {articleCount}`
2. **태그 카드 그리드** — **`repeat(2, 1fr)` → `repeat(3, minmax(0,1fr))`**, `gap: 16px`
   - 카드 `padding: var(--card-pad)`, `radius 14px`, `background var(--surface)` (기존 `#fafafa` 아님)
   - 헤더: 태그명 `17px/700/letter-spacing -.02em` + 건수 `13px/600/var(--ink-faint)/tabular-nums`,
     `padding-bottom: 14px`, `border-bottom: 1px solid var(--border)`
   - 기사 항목: `padding: 14px 0`, 사이 연한 구분선.
     매체명 `12px/600/var(--accent)` (블록, `margin-bottom: 5px`) → 제목 `15px/500/1.5/var(--ink)`
   - **`-webkit-line-clamp: 2` 와 음수 마진 hover 배경 제거** — 제목 전체 노출
   - 정렬: `articleCount` 내림차순

---

## 상태 처리 (신설 — 4개 탭 공통)

현재 로딩은 `"Industry Brief를 불러오는 중입니다."` 텍스트 한 줄이고, 완료 시 레이아웃이
통째로 나타나며 점프합니다.

### 로딩 스켈레톤 (`BriefSkeleton.tsx` 신설)

최종 레이아웃과 **같은 골격**의 회색 블록. `IndustryBriefView` 의 `if (loading)` 분기를 교체.

- 블록 색 `#e8ebef` (큰 것) / `#eef0f3` (작은 것), `radius 4~6px`
- 컨테이너에 `animation: skel 1.4s ease-in-out infinite`
  (`@keyframes skel { 0%,100% { opacity:.5 } 50% { opacity:.9 } }`)
- 구성: eyebrow 바 → 헤드라인 2줄 → 구분선 → 근거 3칸 (각 라벨 + 2줄)
- `@media (prefers-reduced-motion: reduce)` 에서 `animation: none`

### 빈 상태

`hasSignal === false` 이거나 `coreIssues.length === 0` 일 때. 탭별 문구를 다르게.

- 좌측 정렬, `padding: 28px 0`, `gap: 12px`
- `44px` 아이콘 박스 (`radius 12px`, `background var(--surface-sunken)`, 안에 `22px` stroke 아이콘)
- 제목 `18px/600/1.4/var(--ink)` — **날짜와 이유를 명시**
  예) "9월 3일에는 핵심 이슈로 뽑을 만큼 기사가 모이지 않았습니다"
- 설명 `14px/1.7/var(--ink-muted)` — 수집 건수와 흔한 원인
  예) "수집은 41건 됐지만 교차 확인된 이슈가 없습니다. 주말·공휴일에는 흔한 상태입니다."
- 액션 2개: `가장 최근 브리핑 보기` (primary, `background var(--ink)`) /
  `수집 기사 N건 보기` (ghost)

### 새로고침 진행 (`RefreshProgress` 교체)

현재는 `setInterval` 로 8%→92% 를 가짜로 올립니다. 4단계 체크리스트로 교체:

- 제목 `17px/600` — 현재 단계명
- 부제 `13.5px/var(--ink-faint)` — "보통 2~3분 걸립니다. 이 화면을 떠나도 계속 진행됩니다."
- 진행 바 `height: 6px`, `radius 999px`, 트랙 `--surface-sunken`, 채움 `var(--ink)`, `transition: width .55s ease`
- 하단 라벨 `2 / 4단계` ↔ `48%` (`12.5px/600/var(--ink-faint)`, `tabular-nums`)
- 단계 리스트 4줄, `border-top: 1px solid` 위:
  - 완료 → `✓` (`--success`) + `500/var(--ink-faint)` + 우측 결과값
  - 진행 중 → `6px` 원(`var(--accent)`) + `600/var(--ink)` + 우측 `104 / 218`
  - 대기 → `6px` 원(`var(--border)`) + `500/#c9cfd8`
- 단계명: `최신 뉴스 수집` → `신규 기사 분석` → `이슈와 근거 기사 정리` → `브리핑 작성`

> 백엔드가 진행 상황을 노출하지 않으면 최소한 단계 라벨과 `analysisStats.collected` 만이라도
> 실제 값으로 채우세요. 가짜 퍼센트만 올라가는 것보다 낫습니다.

---

## Interactions & Behavior

| 대상 | 동작 |
| --- | --- |
| 탭 | `?tab=` 쿼리 유지 (기존 로직 그대로). 전환 시 헤더 높이 불변 |
| 날짜 화살표 | 하루 이동. 오늘이면 `›` disabled. 트렌드/정책 탭에서는 전체 disabled + `opacity .45` |
| 새로고침 | 기존 순차 호출 유지 (`/refresh` → `/highlights/refresh`, 동시 호출 시 409) |
| 이슈 `근거 기사 →` | 기존 팝오버 또는 모달 유지 |
| 신뢰도 배지 | 정적. 클릭 없음 |
| 토픽 표 행 | hover 시 `background var(--surface-sunken)`. 클릭 시 기존 근거 모달 |
| 시그널 행 | 클릭 시 기존 `ib-signal-modal` 유지 |
| 정책 제목 | `target="_blank"` 원문 링크 (기존과 동일) |

**애니메이션 정책** — 이게 이번 변경의 핵심입니다:

- ✅ 허용: 진입 시 **1회** 페이드/카운트업, hover 트랜지션(`.15s`), 진행 바 `width` 트랜지션
- ❌ 금지: 자동 로테이션, 무한 반복(`infinite`), flap/flip, 깜빡이는 dot
- 모든 애니메이션은 `@media (prefers-reduced-motion: reduce)` 에서 `animation: none`

---

## State Management

기존 `IndustryBriefView` 의 state 를 그대로 씁니다. 변경은 두 가지뿐:

**제거**: `IndustryPanelCard` / `DailyHighlightsBlock` 의 `issuePage` + 6.5초 `setInterval`
**제거**: `TopicLandscapePanel` 의 `openGroup` (버블 클러스터 팝오버)

신규 데이터 요구 없음. D-day 카드는 기존 `PolicyUpdate` 의 날짜 필드에서 클라이언트 계산합니다.

---

## 적용 순서

각 단계가 독립적으로 배포 가능합니다. 한 번에 다 하지 마세요.

1. **토큰 추가 + 색상 치환** — 화면 변화 거의 없음. 다크모드가 이 단계에서 복구됨
2. **중복·죽은 셀렉터 삭제** — 순수 정리. **렌더 결과가 달라지면 삭제가 잘못된 것**
3. **로테이션 · 다크블록 · 전용폰트 제거** — 체감 변화 최대. 여기서 팀 확인 1회
4. **리드 카드 신설 + 이슈 목록 재구성** — 백엔드 변경 없음
5. **차트 y축 · 버블→표 · 시그널 표**
6. **스켈레톤 · 빈 상태 · 진행 표시**

### 2단계 상세: 삭제 목록

**중복 정의** — 각 셀렉터의 마지막(최종 승자) 정의만 남기고 앞의 것 제거:

| 셀렉터 | 횟수 | 남길 것 |
| --- | --- | --- |
| `.ib-panel .headline` | 5 | `clamp(16px,1.5vw,19px)` + 2줄 clamp |
| `.ib-signal-tile.is-keyword` | 4 | `min-height: 82px`, topic `15.5px` |
| `.ib-change-tile` | 3 | `border-top: 1px solid` (컬러 라인은 이미 무효화됨) |
| `.ib-landscape-issue` | 3 | `border: 0` 편집형 리스트 |
| `.ib-stack` / `.ib-signal-grid` / `.ib-panel` | 각 3 | 마지막 정의 |

**죽은 셀렉터** — CSS 와 JSX 를 **함께** 제거 (숨기지 말고 마크업에서 삭제):

`.ib-panel-accent` · `.ib-live-dot` · `.ib-signal-open` · `.ib-signal-detail` ·
`.ib-flip-in` (이미 `animation: none`) · `.ib-lnb-spacer`

**동작 제거**: `.ib-change-flap` 키프레임 + `animationDelay` 계산,
`.ib-policy-dot-pulse` 키프레임, `.ib-highlight-core` 다크 배색,
`@font-face OneStoreMobileGothicTitleFont` 와 이를 쓰는 두 규칙

---

## 검증 체크리스트

- [ ] `industry-brief.css` 에 `#` 색상 리터럴이 카테고리 색 2종 외에 남아 있지 않다
- [ ] 같은 셀렉터가 파일 안에서 2번 이상 등장하지 않는다
- [ ] `font-size` 값이 토큰 6종 + 배지용 11px 외에 없다
- [ ] 모든 카드 `padding` 이 `var(--card-pad)` 이다
- [ ] 다크모드에서 흰 배경 카드가 하나도 남지 않는다
- [ ] 탭 4개를 모두 전환해도 헤더 높이가 변하지 않는다
- [ ] 60초 동안 화면을 그냥 두었을 때 어떤 텍스트도 자동으로 교체되지 않는다
- [ ] 빈 날짜(주말 등)로 이동했을 때 각 탭이 전용 빈 상태를 보여준다
- [ ] 페이지 전체를 캡처했을 때 호버 없이도 모든 그래프 수치를 읽을 수 있다
- [ ] `prefers-reduced-motion: reduce` 에서 움직이는 요소가 없다
- [ ] `npx oxlint` 통과 (`.oxlintrc.json` 설정 기준)

---

## Assets

새 에셋 없음.

- 아이콘 — `AppShell.tsx` 의 기존 인라인 SVG 6종 재사용. 새로 그리지 말 것
- 폰트 — Pretendard(`--font`) 하나. `OneStoreMobileGothicTitleFont` 는 **삭제**
- 차트 — 전부 인라인 SVG 수작업. 차트 라이브러리 도입 불필요
  (도입한다면 정책 막대 차트만 후보이며, 라인/스파크라인은 현재 SVG 로 충분합니다)

## Files

| 파일 | 내용 |
| --- | --- |
| `designs/industry-brief-redesign.dc.html` | 4개 탭 시안(1a, 2a, 2b, 2c) + 상태 처리(1c). 캔버스 형식, 브라우저로 열면 좌우 패닝 |
| `designs/refactoring-guide.dc.html` | CSS 정리 지시서. 인쇄/PDF 가능 |
| `designs/doc-page.js` | 위 문서의 페이지 런타임. 구현과 무관 |
