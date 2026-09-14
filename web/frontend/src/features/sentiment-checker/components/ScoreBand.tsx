import type { Metrics, TimelinePoint } from "../types";
import { LineChart } from "./LineChart";
import { shortDateText } from "../utils";

interface ScoreBandProps {
  metrics: Metrics;
  timeline: TimelinePoint[];
}

function StatTile({ value, label, sub }: { value: number | string; label: string; sub?: string }) {
  return (
    <div className="sc-stat-tile">
      <strong className="tabular">{value}</strong>
      <span>{label}</span>
      {sub && <em>{sub}</em>}
    </div>
  );
}

/** 헤드라인 지표(민심 지수 + 추이 스파크라인)와 부가 지표 타일을 한 밴드로
 * 묶는다 — 예전엔 지수·게시글 수·이슈 수·AI 분석 현황이 전부 같은 크기
 * 타일 6개로 나열돼서 뭐가 중요한 숫자인지 한눈에 안 들어왔다. */
export function ScoreBand({ metrics, timeline }: ScoreBandProps) {
  const changeUp = metrics.change > 0;
  const changeDown = metrics.change < 0;
  const points = timeline.map((t) => ({ label: shortDateText(t.observed_at), value: t.score }));

  return (
    <section className="sc-score-band">
      <div className="sc-score-main">
        <span className="sc-eyebrow">보조 민심 지수</span>
        <div className="sc-score-value">
          <strong className="tabular">{metrics.score}</strong>
          <span className={`sc-score-change ${changeUp ? "is-up" : changeDown ? "is-down" : "is-flat"}`}>
            {changeUp ? "▲" : changeDown ? "▼" : "―"} {Math.abs(metrics.change)}
          </span>
        </div>
        <p className="sc-score-caption">이전 기간 대비 변화 · 0에 가까울수록 부정, 100에 가까울수록 긍정입니다.</p>
        <div className="sc-score-sparkline">
          <LineChart points={points} height={110} yMin={0} yMax={100} emptyText="자동 갱신 후 시간대별 추이가 누적됩니다." />
        </div>
      </div>
      <div className="sc-stat-grid">
        <StatTile value={metrics.collected} label="기간 내 게시글" />
        <StatTile value={metrics.issue_count} label="발견된 이슈" />
        <StatTile value={`${metrics.analysis_coverage}%`} label="AI 분석 커버리지" sub={`${metrics.ai_analyzed}건 완료 · ${metrics.ai_pending}건 대기`} />
        <StatTile value={metrics.stored_total} label="누적 수집 게시글" />
      </div>
    </section>
  );
}
