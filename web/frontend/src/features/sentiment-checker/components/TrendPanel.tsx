import type { TimelinePoint } from "../types";
import { LineChart } from "./LineChart";
import { shortDateText } from "../utils";

export function TrendPanel({ timeline }: { timeline: TimelinePoint[] }) {
  const points = timeline.map((t) => ({ label: shortDateText(t.observed_at), value: t.score }));
  return (
    <section className="sc-panel">
      <span className="sc-eyebrow">추이</span>
      <h2>민심 점수 추이</h2>
      <LineChart points={points} height={160} yMin={0} yMax={100} emptyText="자동 갱신 후 시간대별 추이가 누적됩니다." />
    </section>
  );
}
