import { useEffect, useRef, useState } from "react";
import type { IndustryBrief } from "../types";

type Analytics = NonNullable<IndustryBrief["analytics"]>;
// 흑색/보라/청록은 옅은 배경 위에서 서로 톤이 가까워 한눈에 구분이 잘 안
// 됐다 — 파랑·주황·초록처럼 색상환 상에서 멀리 떨어진 배색으로 바꿔
// 각 라인이 바로 구분되도록 한다.
const COLORS = ["#2f6feb", "#f2994a", "#1f9d55"];

function InterestChart({ data }: { data: Analytics["interest"] }) {
  // preserveAspectRatio="none"으로 640 고정폭을 넓은 카드에 억지로
  // 늘렸더니, x축 배율만 커지고 y축 배율은 그대로라 점(circle)이 가로로
  // 찌그러진 타원처럼 보였다 — viewBox 폭 자체를 실제 렌더링 폭에 맞추면
  // x/y 배율이 똑같아져서(1:1) 늘어나는 일 없이 점도 항상 원형을 유지한다.
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const measured = entries[0]?.contentRect.width;
      if (measured) setWidth(measured);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const height = 260;
  // y축에 텍스트 라벨이 없는데도 38px를 비워두고 있었다 — 실제로 필요한
  // 만큼(점이 잘리지 않을 정도)만 남기고 왼쪽 여백을 크게 줄인다.
  const left = 10;
  const right = 14;
  const top = 15;
  const bottom = 35;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const maximum = Math.max(1, ...data.series.flatMap((series) => series.values));
  const x = (index: number) => left + (data.labels.length <= 1 ? 0 : index * plotWidth / (data.labels.length - 1));
  const y = (value: number) => top + plotHeight - value * plotHeight / maximum;

  return (
    <div className="ib-chart-wrap" ref={containerRef}>
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

export function BriefAnalyticsPanel({ analytics, periodLabel }: { analytics: Analytics; periodLabel: string }) {
  return <section className="card ib-analytics-panel">
    <div className="ib-analytics-head"><div><span>ISSUE ANALYTICS</span><h2>기사 흐름으로 보는 업계 변화</h2></div><p>{periodLabel} 관련 기사 기준</p></div>
    <div className="ib-analytics-grid">
      <article><div className="ib-chart-title"><h3>이슈 관심도 변화</h3><span>최근 30일 · {analytics.interest.bucket} 기사량</span></div><InterestChart data={analytics.interest} /></article>
    </div>
  </section>;
}
