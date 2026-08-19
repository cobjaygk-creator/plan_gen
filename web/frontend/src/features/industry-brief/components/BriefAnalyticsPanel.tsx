import type { IndustryBrief } from "../types";

type Analytics = NonNullable<IndustryBrief["analytics"]>;
const COLORS = ["#111111", "#7657c8", "#0d9d9a"];

function InterestChart({ data }: { data: Analytics["interest"] }) {
  const width = 640;
  const height = 190;
  const left = 38;
  const right = 14;
  const top = 15;
  const bottom = 35;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const maximum = Math.max(1, ...data.series.flatMap((series) => series.values));
  const x = (index: number) => left + (data.labels.length <= 1 ? 0 : index * plotWidth / (data.labels.length - 1));
  const y = (value: number) => top + plotHeight - value * plotHeight / maximum;

  return (
    <div className="ib-chart-wrap">
      {data.series.length ? <>
        <div className="ib-chart-legend">{data.series.map((series, index) => <span key={series.name} title={series.originalTitle}><i style={{ background: COLORS[index] }} />{series.name}</span>)}</div>
        <svg className="ib-line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="주요 이슈 기사량 변화">
          {[0, .5, 1].map((ratio) => <line key={ratio} x1={left} x2={width - right} y1={top + plotHeight * ratio} y2={top + plotHeight * ratio} className="ib-chart-grid" />)}
          {data.series.map((series, seriesIndex) => {
            const points = series.values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
            return <g key={series.name}><polyline points={points} fill="none" stroke={COLORS[seriesIndex]} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />{series.values.map((value, index) => <circle key={index} cx={x(index)} cy={y(value)} r="3.5" fill={COLORS[seriesIndex]}><title>{series.originalTitle} · {data.labels[index]} · {value}건</title></circle>)}</g>;
          })}
          {data.labels.map((label, index) => (index === 0 || index === data.labels.length - 1 || index % Math.max(1, Math.ceil(data.labels.length / 5)) === 0) && <text key={label + index} x={x(index)} y={height - 10} textAnchor={index === 0 ? "start" : index === data.labels.length - 1 ? "end" : "middle"}>{label}</text>)}
        </svg>
      </> : <p className="ib-chart-empty">선택 기간에 추세를 구성할 만큼 연결된 기사가 없습니다.</p>}
    </div>
  );
}

function TopicBars({ rows }: { rows: Analytics["topicShare"] }) {
  const maximum = Math.max(1, ...rows.flatMap((row) => [row.game, row.ai]));
  return <div className="ib-topic-bars">
    <div className="ib-topic-legend"><span><i className="game" />GAME</span><span><i className="ai" />AI</span></div>
    {rows.slice(0, 7).map((row) => <div className="ib-topic-row" key={row.topic}>
      <strong>{row.topic}</strong>
      <div className="ib-topic-pair">
        <div><span className="game" style={{ width: `${row.game / maximum * 100}%` }} /><em>{row.game}</em></div>
        <div><span className="ai" style={{ width: `${row.ai / maximum * 100}%` }} /><em>{row.ai}</em></div>
      </div>
    </div>)}
    {!rows.length && <p className="ib-chart-empty">선택 기간에 분류된 관련 기사가 없습니다.</p>}
  </div>;
}

export function BriefAnalyticsPanel({ analytics, periodLabel }: { analytics: Analytics; periodLabel: string }) {
  return <section className="card ib-analytics-panel">
    <div className="ib-analytics-head"><div><span>ISSUE ANALYTICS</span><h2>기사 흐름으로 보는 업계 변화</h2></div><p>{periodLabel} 관련 기사 기준</p></div>
    <div className="ib-analytics-grid">
      <article><div className="ib-chart-title"><h3>이슈 관심도 변화</h3><span>{analytics.interest.bucket} 기사량</span></div><InterestChart data={analytics.interest} /></article>
      <article><div className="ib-chart-title"><h3>GAME·AI 주요 주제 비중</h3><span>기사 1건당 대표 주제 1개</span></div><TopicBars rows={analytics.topicShare} /></article>
    </div>
  </section>;
}
