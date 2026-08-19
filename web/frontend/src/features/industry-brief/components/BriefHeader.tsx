import { useEffect, useState } from "react";
import type { IndustryBrief } from "../types";

interface Props { brief: IndustryBrief; }

function CountUp({ value, delay }: { value: number; delay: number }) {
  const [display, setDisplay] = useState(0);
  const [settled, setSettled] = useState(false);
  useEffect(() => {
    let frame = 0; let timeout = 0; const duration = 640;
    setDisplay(0); setSettled(false);
    timeout = window.setTimeout(() => {
      const started = performance.now();
      const tick = (now: number) => {
        const progress = Math.min((now - started) / duration, 1);
        setDisplay(Math.round(value * (1 - Math.pow(1 - progress, 3))));
        if (progress < 1) frame = requestAnimationFrame(tick); else setSettled(true);
      };
      frame = requestAnimationFrame(tick);
    }, delay);
    return () => { window.clearTimeout(timeout); cancelAnimationFrame(frame); };
  }, [value, delay]);
  return <span className={`value tabular${settled ? " ib-count-settled" : ""}`}>{display}</span>;
}

export function BriefHeader({ brief }: Props) {
  const stats = brief.analysisStats ?? { collected: brief.articleCount, analyzed: brief.articleCount, relevant: brief.articleCount, issues: brief.issues.length };
  const pending = stats.pending ?? Math.max(0, stats.collected - stats.analyzed);
  const completion = stats.completionRate ?? Math.round(stats.analyzed * 100 / Math.max(1, stats.collected));
  const state = stats.analysisStatus ?? (completion >= 80 ? "COMPLETE" : completion >= 40 ? "PARTIAL" : "INSUFFICIENT");
  const stateLabel = state === "COMPLETE" ? "분석 완료" : state === "PARTIAL" ? "분석 진행 중" : "분석 불충분";
  const cards = [[stats.collected, "수집 기사"], [stats.analyzed, "분석 완료"], [pending, "분석 대기"], [stats.verifiedIssues ?? 0, "교차검증 이슈"]] as const;
  return <div className="card ib-header ib-live-board">
    <div className="ib-live-label">INDUSTRY BRIEF</div>
    <div className="ib-board-grid">{cards.map(([value, label], index) => <div className="ib-board-stat" key={label}><CountUp value={value} delay={index * 140} /><span className="label">{label}</span></div>)}</div>
    <div className={`ib-analysis-health is-${state.toLowerCase()}`}><div><strong>{stateLabel}</strong><span>{completion}%{" · "}{stats.analyzed}/{stats.collected}{"건 분석 · 관련 기사 "}{stats.relevant}{"건"}</span></div><div className="ib-health-track"><i style={{ width: `${completion}%` }} /></div>{state !== "COMPLETE" && <p>{"현재 브리핑은 잠정 결과입니다. 분석률 80% 이상에서 완료 상태로 전환됩니다."}</p>}</div>
  </div>;
}
