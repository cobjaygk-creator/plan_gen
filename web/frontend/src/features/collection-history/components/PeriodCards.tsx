import type { CollectionTotals } from "../types";

interface Props {
  totals: CollectionTotals;
}

export function PeriodCards({ totals }: Props) {
  const cards = [
    { label: "1일 이내", value: totals.d1 },
    { label: "7일 이내", value: totals.d7 },
    { label: "30일 이내", value: totals.d30 },
    { label: "올해", value: totals.ytd },
  ];
  return (
    <section className="ch-cards" aria-label="기간별 신규 수집 건수">
      {cards.map((card) => (
        <div key={card.label} className="ch-card">
          <span className="ch-card-label">{card.label}</span>
          <strong className="ch-card-value">{card.value.toLocaleString()}</strong>
          <span className="ch-card-sub">신규 수집 이벤트</span>
        </div>
      ))}
      <div className="ch-card ch-card-total">
        <span className="ch-card-label">전체 보관</span>
        <strong className="ch-card-value">{totals.total.toLocaleString()}</strong>
        <span className="ch-card-sub">진행 중 {totals.active.toLocaleString()}건</span>
      </div>
    </section>
  );
}
