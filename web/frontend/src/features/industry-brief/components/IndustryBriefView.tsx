import { useEffect, useState } from "react";
import type { IndustryBrief } from "../types";
import { fetchLatestBrief } from "../api/client";
import { BriefHeader } from "./BriefHeader";
import { IndustryPanelCard } from "./IndustryPanelCard";
import { CrossInsightPanel } from "./CrossInsightPanel";
import { SignalsPanel } from "./SignalsPanel";
import { NewTodayPanel } from "./NewTodayPanel";
import { ImportantIssuesPanel } from "./ImportantIssuesPanel";
import "../industry-brief.css";

export function IndustryBriefView() {
  const [brief, setBrief] = useState<IndustryBrief | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchLatestBrief()
      .then((b) => {
        if (!cancelled) setBrief(b);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div className="ib-page-status">Industry Brief를 불러오는 중입니다.</div>;
  }
  if (error && !brief) {
    return <div className="ib-page-status">아직 생성된 Industry Brief가 없습니다.<br />첫 분석이 완료되면 표시됩니다.</div>;
  }
  if (!brief) {
    return null;
  }

  return (
    <div className="ib-stack">
      {error && (
        <div className="card ib-header" style={{ borderColor: "var(--warning)" }}>
          최신 분석 생성에 실패하여 이전 분석 결과를 표시하고 있습니다.
        </div>
      )}
      <BriefHeader brief={brief} />
      <div className="ib-two-col">
        <IndustryPanelCard icon="🎮" title="Game Industry" panel={brief.game} />
        <IndustryPanelCard icon="🤖" title="AI Industry" panel={brief.ai} />
      </div>
      <CrossInsightPanel insight={brief.crossInsight} />
      <SignalsPanel signals={brief.signals} />
      <NewTodayPanel items={brief.newToday} />
      <ImportantIssuesPanel issues={brief.issues} />
    </div>
  );
}
