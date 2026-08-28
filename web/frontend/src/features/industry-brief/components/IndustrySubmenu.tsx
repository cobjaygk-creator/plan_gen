export type IndustryScreen = "today" | "issue" | "trend" | "tech";

const ITEMS: Array<{ key: IndustryScreen; label: string } | { key: null; label: string }> = [
  { key: "today", label: "오늘" },
  { key: null, label: "뉴스" },
  { key: "issue", label: "이슈" },
  { key: "tech", label: "기술 레이더" },
  { key: "trend", label: "트렌드" },
];

/** Top-level IA for 업계동향, scoped inside this feature's own header — the
 * app's left rail belongs to other systems and stays untouched (기획 문서
 * "02 메뉴 구조" 결정). 오늘/이슈/기술 레이더/트렌드 are wired
 * (Phase 1+2+3); 뉴스 renders disabled as a placeholder for where that IA
 * attaches later, rather than hiding it entirely. */
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
