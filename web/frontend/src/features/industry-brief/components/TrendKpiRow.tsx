import { useEffect, useRef, useState } from "react";
import type { IndustryBrief } from "../types";
import { useInView } from "../hooks/useInView";

// BriefHeader.tsx의 카운트업 애니메이션과 같은 방식 — 트렌드 탭에 들어올
// 때마다 숫자가 0에서 올라오도록 재사용한다. start가 false인 동안은
// 대기만 하고(스크롤로 아직 안 내려온 상태), true가 되는 순간 카운트업을
// 시작한다.
function CountUp({ value, delay, start }: { value: number; delay: number; start: boolean }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    if (!start) return;
    let frame = 0;
    let timeout = 0;
    const duration = 640;
    setDisplay(0);
    timeout = window.setTimeout(() => {
      const started = performance.now();
      const tick = (now: number) => {
        const progress = Math.min((now - started) / duration, 1);
        setDisplay(Math.round(value * (1 - Math.pow(1 - progress, 3))));
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    }, delay);
    return () => { window.clearTimeout(timeout); cancelAnimationFrame(frame); };
  }, [value, delay, start]);
  return <>{display}</>;
}

// 새 숫자를 계산하지 않는다 — analysisStats·topicLandscape·topicFreshness가
// 이미 갖고 있는 값을 요약해서 KPI 4개로만 보여준다.
export function TrendKpiRow({ brief }: { brief: IndustryBrief }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const inView = useInView(containerRef);
  const landscape = brief.analytics?.topicLandscape ?? [];
  const collected = brief.analysisStats?.collected ?? brief.articleCount;
  const activeIssues = brief.analysisStats?.issues ?? landscape.length;
  const ongoingCount = landscape.filter((topic) => topic.days >= 2).length;
  const freshCount = brief.analytics?.topicFreshness.fresh.length ?? 0;

  return (
    <div className="ib-kpi-row" ref={containerRef}>
      <div className={`ib-kpi ib-anim-pop${inView ? " is-visible" : ""}`}><span>수집 기사</span><strong className="tabular"><CountUp value={collected} delay={0} start={inView} /></strong></div>
      <div className={`ib-kpi ib-anim-pop${inView ? " is-visible" : ""}`} style={{ animationDelay: "0.06s" }}><span>활성 이슈</span><strong className="tabular"><CountUp value={activeIssues} delay={60} start={inView} /></strong></div>
      <div className={`ib-kpi ib-anim-pop${inView ? " is-visible" : ""}`} style={{ animationDelay: "0.12s" }}><span>지속형 이슈 (2일+)</span><strong className="tabular"><CountUp value={ongoingCount} delay={120} start={inView} /></strong></div>
      <div className={`ib-kpi ib-anim-pop${inView ? " is-visible" : ""}`} style={{ animationDelay: "0.18s" }}><span>신규 토픽</span><strong className="tabular"><CountUp value={freshCount} delay={180} start={inView} /></strong></div>
    </div>
  );
}
