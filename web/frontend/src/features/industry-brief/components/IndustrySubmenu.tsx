const ITEMS = [
  { label: "오늘", ready: true },
  { label: "뉴스", ready: false },
  { label: "이슈", ready: false },
  { label: "기술 레이더", ready: false },
  { label: "트렌드", ready: false },
];

/** Top-level IA for 업계동향, scoped inside this feature's own header — the
 * app's left rail belongs to other systems and stays untouched (기획 문서
 * "02 메뉴 구조" 결정). Only 오늘 is wired in Phase 1; the rest render as
 * disabled previews of where 이슈/기술 레이더/트렌드 will attach later,
 * rather than hiding the eventual IA entirely. */
export function IndustrySubmenu() {
  return (
    <nav className="ib-submenu" aria-label="업계동향 메뉴">
      {ITEMS.map((item) => (
        <span
          key={item.label}
          className={`ib-submenu-item${item.ready ? " is-active" : " is-disabled"}`}
          title={item.ready ? undefined : "준비 중"}
          aria-disabled={!item.ready}
        >
          {item.label}
        </span>
      ))}
    </nav>
  );
}
