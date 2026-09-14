import type { DetailTimelinePoint } from "../types";

/** 이슈 상세의 일자별 언급 추이 — 날짜별 이산 개수라 선 그래프보다
 * 막대가 더 자연스럽다(dataviz 관례: 불연속 카운트는 막대). */
export function MentionTrendBars({ timeline }: { timeline: DetailTimelinePoint[] }) {
  if (timeline.length === 0) {
    return <p className="sc-empty">추이 데이터가 없습니다.</p>;
  }
  const max = Math.max(1, ...timeline.map((t) => t.count));
  return (
    <div className="sc-mention-bars">
      {timeline.map((t) => (
        <div key={t.date}>
          <b className="tabular">{t.count}</b>
          <i style={{ height: `${Math.max(6, (t.count / max) * 100)}%` }} />
          <span>{t.date.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}
