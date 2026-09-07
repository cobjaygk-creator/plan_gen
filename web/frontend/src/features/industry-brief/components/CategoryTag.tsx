import type { CSSProperties } from "react";

const CATEGORY_COLORS: Record<string, string> = {
  GAME: "var(--cat-game)",
  AI: "var(--cat-ai)",
  // 게임/AI 두 산업에 걸치거나 어느 한쪽으로 딱 잘라 말하기 애매한 경우
  // (예: IndustryLandscapePanel의 "게임 × AI" 도메인) — 기존 success
  // 토큰(초록)을 그대로 재사용한다.
  GAME_AI: "var(--success)",
};

const CATEGORY_LABELS: Record<string, string> = { GAME: "GAME", AI: "AI", GAME_AI: "GAME × AI" };

/** IndustryPanelCard의 "막대 + 굵은 대문자 라벨" 헤더 스타일을 트렌드·정책
 * 화면의 카테고리 표시에도 그대로 재사용한다 — 게임=주황, AI=파랑, 애매·
 * 혼합=초록(GAME_AI). */
export function CategoryTag({ category }: { category: string }) {
  const color = CATEGORY_COLORS[category] ?? "var(--ink-faint)";
  const label = CATEGORY_LABELS[category] ?? category;
  return (
    <span className="ib-category-tag" style={{ "--cat-color": color } as CSSProperties}>
      <span className="ib-panel-color-bar" aria-hidden="true" />
      {label}
    </span>
  );
}

/** 섹션 제목 앞에 붙이는 색 막대만 필요할 때(카테고리 라벨 텍스트 없이) —
 * 트렌드/정책/레이더 화면의 일반 섹션 헤딩에 쓴다. 탭마다 그 탭의 LeadCard
 * dotColor와 같은 색을 써서 "이 화면 전체의 색"이라는 느낌을 준다. */
export function SectionBar({ color }: { color: string }) {
  return <span className="ib-panel-color-bar" aria-hidden="true" style={{ "--cat-color": color } as CSSProperties} />;
}
