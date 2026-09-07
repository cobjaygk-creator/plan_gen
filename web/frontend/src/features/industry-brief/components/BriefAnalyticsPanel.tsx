import { useEffect, useRef, useState } from "react";
import type { IndustryBrief } from "../types";
import { useInView } from "../hooks/useInView";
import { SectionBar } from "./CategoryTag";

type Analytics = NonNullable<IndustryBrief["analytics"]>;
// 흑색/보라/청록은 옅은 배경 위에서 서로 톤이 가까워 한눈에 구분이 잘 안
// 됐다 — 파랑·주황·초록처럼 색상환 상에서 멀리 떨어진 배색으로 바꿔
// 각 라인이 바로 구분되도록 한다. 앞의 둘은 5단계에서 카테고리 토큰으로
// 교체 — 다른 카테고리 차트(토픽 지형도 등)와 같은 배색 언어를 쓴다.
const COLORS = ["var(--cat-ai)", "var(--cat-game)", "#1f9d55"];

/** 급격히 튀어오른 "돌발형"과 기간 내내 완만히 오른 "지속형"을 구분한다 —
 * 마지막 20%(최소 1개) 구간 평균이 그 이전 평균보다 1.8배 이상 뛰면
 * 돌발형, 시작보다 끝이 높고 최근 구간도 평균 이상이면 지속형으로 본다. */
function classifySeries(values: number[]): "spike" | "steady" | "flat" {
  if (values.length < 4) return "flat";
  const window = Math.max(1, Math.floor(values.length * 0.2));
  const recent = values.slice(-window);
  const earlier = values.slice(0, values.length - window);
  const recentAvg = recent.reduce((sum, value) => sum + value, 0) / recent.length;
  const earlierAvg = earlier.length ? earlier.reduce((sum, value) => sum + value, 0) / earlier.length : 0;
  if (recentAvg >= 2 && recentAvg > earlierAvg * 1.8) return "spike";
  if (values[values.length - 1] > values[0] && recentAvg >= earlierAvg) return "steady";
  return "flat";
}

/** 캡처해서 보고하는 페이지라 그래프만 보여주고 끝내면 "그래서 뭐가
 * 중요한데?"가 남는다 — 지속형/돌발형 중 눈에 띄는 흐름을 한 문장으로
 * 짚어준다. 이름에 조사를 직접 붙이면 받침 유무에 따라 어색해질 수 있어
 * "쪽" 같은 조사 비의존 표현으로 우회한다. */
function buildInsightSentence(series: Analytics["interest"]["series"]): string {
  const classified = series.map((item) => ({ name: item.name, kind: classifySeries(item.values) }));
  const spike = classified.find((item) => item.kind === "spike");
  const steady = classified.find((item) => item.kind === "steady" && item.name !== spike?.name);
  if (steady && spike) return `완만하게 지속되는 흐름은 «${steady.name}» 쪽, 최근 급격히 튀어오른 흐름은 «${spike.name}» 쪽입니다.`;
  if (spike) return `«${spike.name}» 쪽에서 최근 급격한 증가세가 눈에 띕니다.`;
  if (steady) return `«${steady.name}» 쪽이 기간 내내 완만하게 이어지는 지속형 흐름입니다.`;
  return "뚜렷한 돌발 신호 없이 대체로 평이한 흐름입니다.";
}

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
  const inView = useInView(containerRef);

  const height = 260;
  // 5단계: y축에 값 라벨을 실제로 그리게 되면서, 라벨이 들어갈 공간을
  // 다시 확보해야 했다(1단계 이전에는 라벨이 아예 없어서 10px로 줄였던
  // 여백이었다).
  const left = 40;
  const right = 14;
  const top = 15;
  const bottom = 44;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  // 눈금은 실제 최대값이 아니라, 그걸 4등분해 올림한 "보기 좋은" 값
  // 기준으로 그린다 — 그래야 맨 위 눈금이 딱 떨어지는 정수로 보인다.
  const rawMax = Math.max(1, ...data.series.flatMap((series) => series.values));
  const tickStep = Math.max(1, Math.ceil(rawMax / 4));
  const axisMax = tickStep * 4;
  const x = (index: number) => left + (data.labels.length <= 1 ? 0 : index * plotWidth / (data.labels.length - 1));
  const y = (value: number) => top + plotHeight - (value / axisMax) * plotHeight;
  const insightSentence = data.series.length > 0 ? buildInsightSentence(data.series) : null;

  return (
    <div className="ib-chart-wrap" ref={containerRef}>
      {data.series.length ? <>
        <div className="ib-chart-legend">{data.series.map((series, index) => <span key={series.name} title={series.originalTitle}><i style={{ background: COLORS[index] }} />{series.name}</span>)}</div>
        <svg className="ib-line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="주요 이슈 기사량 변화">
          {[0, 1, 2, 3, 4].map((tick) => {
            const tickY = top + plotHeight - (tick / 4) * plotHeight;
            return (
              <g key={tick}>
                <line x1={left} x2={width - right} y1={tickY} y2={tickY} className="ib-chart-grid" />
                <text x={left - 10} y={tickY} textAnchor="end" dominantBaseline="middle" className="ib-chart-axis-label">{tickStep * tick}</text>
              </g>
            );
          })}
          {data.series.map((series, seriesIndex) => {
            const points = series.values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
            const lastIndex = series.values.length - 1;
            return (
              <g key={series.name}>
                <polyline
                  points={points} fill="none" stroke={COLORS[seriesIndex]} strokeWidth="3"
                  strokeLinejoin="round" strokeLinecap="round" className={`ib-anim-line${inView ? " is-visible" : ""}`}
                  style={{ animationDelay: `${seriesIndex * 0.15}s` }}
                />
                {/* 점마다 원을 찍으면 지점이 많을 때 과밀해 보인다 — 마지막
                    (가장 최근) 값 하나에만 원을 찍어 "지금 여기"를 짚어준다. */}
                <circle
                  cx={x(lastIndex)} cy={y(series.values[lastIndex])} r="4.5" fill={COLORS[seriesIndex]}
                  className={`ib-anim-pop${inView ? " is-visible" : ""}`} style={{ animationDelay: `${0.5 + seriesIndex * 0.15}s` }}
                >
                  <title>{series.originalTitle} · {data.labels[lastIndex]} · {series.values[lastIndex]}건</title>
                </circle>
              </g>
            );
          })}
          {data.labels.map((label, index) => (index === 0 || index === data.labels.length - 1 || index % Math.max(1, Math.ceil(data.labels.length / 5)) === 0) && <text key={label + index} x={x(index)} y={height - 10} textAnchor={index === 0 ? "start" : index === data.labels.length - 1 ? "end" : "middle"}>{label}</text>)}
        </svg>
        {insightSentence && <p className="ib-chart-insight">{insightSentence}</p>}
      </> : <p className="ib-chart-empty">선택 기간에 추세를 구성할 만큼 연결된 기사가 없습니다.</p>}
    </div>
  );
}

export function BriefAnalyticsPanel({ analytics }: { analytics: Analytics }) {
  return <section className="card ib-analytics-panel">
    <div className="ib-analytics-head"><div><span>ISSUE ANALYTICS</span><h2><SectionBar color="var(--success)" />기사 흐름으로 보는 업계 변화</h2></div></div>
    <div className="ib-analytics-grid">
      <article><div className="ib-chart-title"><h3>이슈 관심도 변화</h3><span>최근 30일 · {analytics.interest.bucket} 기사량</span></div><InterestChart data={analytics.interest} /></article>
    </div>
  </section>;
}
