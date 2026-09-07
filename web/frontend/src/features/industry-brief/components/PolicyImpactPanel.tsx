import { useEffect, useRef, useState } from "react";
import type { IndustryBrief } from "../types";
import { useInView } from "../hooks/useInView";
import { CategoryTag, SectionBar } from "./CategoryTag";

type PolicyImpact = NonNullable<IndustryBrief["policyImpact"]>[number];

const CATEGORY_COLORS = { GAME: "var(--cat-game)", AI: "var(--cat-ai)" } as const;

function PolicyImpactChart({ impact }: { impact: PolicyImpact }) {
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

  const height = 200;
  const left = 40, right = 14, top = 34, bottom = 26;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const n = impact.labels.length;
  const maximum = Math.max(1, ...impact.values);
  // index*plotWidth/(n-1)로 막대 "중심"을 양 끝(left, width-right)에 정확히
  // 맞췄더니, 그 중심에서 barWidth/2만큼 좌우로 그리는 막대 자체는 도표
  // 바깥으로 튀어나갔다(첫/마지막 막대가 잘려 보이던 원인) — 막대 그래프는
  // 각자의 "칸(slot)" 한가운데 그려야 양 끝에도 여백이 남는다.
  const slotWidth = n > 0 ? plotWidth / n : 0;
  const barWidth = slotWidth * 0.6;
  const x = (index: number) => left + slotWidth * (index + 0.5);
  const y = (value: number) => top + plotHeight - (value / maximum) * plotHeight;
  const ratioText = impact.beforeAvg > 0 ? `×${(impact.afterAvg / impact.beforeAvg).toFixed(1)}` : "신규";
  const color = CATEGORY_COLORS[impact.category];
  const eventX = x(impact.eventIndex);

  return (
    <div className="ib-chart-wrap" ref={containerRef}>
      <svg className="ib-policy-impact-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${impact.policyTitle} 발표 전후 기사량`}>
        {[0, .5, 1].map((ratio) => {
          const tickY = top + plotHeight * ratio;
          return (
            <g key={ratio}>
              <line x1={left} x2={width - right} y1={tickY} y2={tickY} className="ib-chart-grid" />
              <text x={left - 10} y={tickY} textAnchor="end" dominantBaseline="middle" className="ib-chart-axis-label">{Math.round(maximum * (1 - ratio))}</text>
            </g>
          );
        })}
        {impact.values.map((value, index) => {
          const barTop = y(value);
          return (
            <rect
              key={index}
              x={x(index) - barWidth / 2}
              y={barTop}
              width={barWidth}
              height={top + plotHeight - barTop}
              rx={3}
              fill={color}
              opacity={index === impact.eventIndex ? 1 : 0.55}
              className={`ib-anim-bar${inView ? " is-visible" : ""}`}
              style={{ animationDelay: `${index * 0.03}s` }}
            >
              <title>{impact.labels[index]} · {value}건</title>
            </rect>
          );
        })}
        <line x1={eventX} x2={eventX} y1={16} y2={top + plotHeight} className="ib-policy-impact-marker" />
        <circle cx={eventX} cy={10} r={4} className={`ib-policy-impact-flag ib-anim-pop${inView ? " is-visible" : ""}`} style={{ animationDelay: "0.6s" }} />
        <text x={eventX} y={4} textAnchor={eventX > width - 100 ? "end" : "middle"} className="ib-policy-impact-ratio">발표 후 {ratioText}</text>
        {impact.labels.map((label, index) => (index === 0 || index === n - 1 || index === impact.eventIndex) && (
          <text key={label + index} x={x(index)} y={height - 8} textAnchor="middle">{label}</text>
        ))}
      </svg>
    </div>
  );
}

export function PolicyImpactPanel({ impacts }: { impacts?: IndustryBrief["policyImpact"] }) {
  if (!impacts || impacts.length === 0) return null;
  return (
    <section className="card ib-policy-impact-panel">
      <div className="ib-section-heading"><div><SectionBar color="var(--success)" />정책 발표 → 업계 반응</div></div>
      {impacts.map((impact) => (
        <div className="ib-policy-impact-item" key={impact.policyTitle}>
          <div className="ib-policy-impact-title">
            {impact.policyUrl ? (
              <a href={impact.policyUrl} target="_blank" rel="noreferrer"><strong>{impact.policyTitle}</strong></a>
            ) : (
              <strong>{impact.policyTitle}</strong>
            )}
            <span className="ib-policy-impact-meta">{impact.publishedDate} · <CategoryTag category={impact.category} /></span>
          </div>
          <PolicyImpactChart impact={impact} />
          <p className="ib-policy-impact-stat">발표 전 3일 평균 <b>{impact.beforeAvg}건</b> → 발표 후 3일 평균 <b>{impact.afterAvg}건</b></p>
          {impact.implication && <p className="ib-policy-impact-implication">{impact.implication}</p>}
        </div>
      ))}
    </section>
  );
}
