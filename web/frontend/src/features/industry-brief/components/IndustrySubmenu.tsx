export type IndustryScreen = "today" | "policy" | "trend" | "tech";

const ITEMS: Array<{ key: IndustryScreen; label: string } | { key: null; label: string }> = [
  { key: "today", label: "업계동향" },
  { key: "policy", label: "정책/제도" },
  { key: "tech", label: "기술 레이더" },
  { key: "trend", label: "트렌드" },
];

/** Top-level IA for 업계동향, scoped inside this feature's own header — the
 * app's left rail belongs to other systems and stays untouched (기획 문서
 * "02 메뉴 구조" 결정). 업계동향=GAME/AI 핵심이슈·추천기사, 정책/제도=정책·
 * 제도 업데이트, 기술 레이더=AI 키워드 태그, 트렌드=업계 이슈 지도·기사
 * 흐름 분석·주요 시그널. */
export function IndustrySubmenu({ active, onChange }: { active: IndustryScreen; onChange: (screen: IndustryScreen) => void }) {
  return (
    <nav className="ib-submenu" aria-label="업계동향 메뉴">
      {ITEMS.map((item) =>
        item.key ? (
          <button
            key={item.label}
            type="button"
            className={`ib-submenu-item${active === item.key ? " is-active" : ""}`}
            onClick={() => onChange(item.key)}
          >
            {item.label}
          </button>
        ) : (
          <span key={item.label} className="ib-submenu-item is-disabled" title="준비 중" aria-disabled="true">
            {item.label}
          </span>
        ),
      )}
    </nav>
  );
}
