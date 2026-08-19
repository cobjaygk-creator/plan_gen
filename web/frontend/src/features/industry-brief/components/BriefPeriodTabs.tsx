import type { BriefPeriod } from "../api/client";

const TABS: Array<{ value: BriefPeriod; label: string }> = [
  { value: "today", label: "오늘" },
  { value: "3d", label: "3일" },
  { value: "week", label: "이번 주" },
];

export function BriefPeriodTabs({ active, loading, onChange }: {
  active: BriefPeriod; loading: boolean; onChange: (period: BriefPeriod) => void;
}) {
  return <nav className="ib-period-tabs" aria-label="Industry Brief 기간 선택">
    {TABS.map((tab) => <button key={tab.value} type="button" className={active === tab.value ? "is-active" : ""}
      disabled={loading} onClick={() => onChange(tab.value)}>{tab.label}</button>)}
  </nav>;
}
