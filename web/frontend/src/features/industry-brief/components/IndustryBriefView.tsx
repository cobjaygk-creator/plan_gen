import { useCallback, useEffect, useState } from "react";
import type { IndustryBrief } from "../types";
import { fetchPeriodBrief, refreshIndustryBrief, type BriefPeriod } from "../api/client";
import { formatKoreanDateTime } from "../utils/format";
import { BriefHeader } from "./BriefHeader";
import { BriefPeriodTabs } from "./BriefPeriodTabs";
import { IndustryPanelCard } from "./IndustryPanelCard";
import { CrossInsightPanel } from "./CrossInsightPanel";
import { SignalsPanel } from "./SignalsPanel";
import { ImportantIssuesPanel } from "./ImportantIssuesPanel";
import { IndustryLandscapePanel } from "./IndustryLandscapePanel";
import { MarketComparisonPanel } from "./MarketComparisonPanel";
import { PolicyUpdatesPanel } from "./PolicyUpdatesPanel";
import { BriefAnalyticsPanel } from "./BriefAnalyticsPanel";
import { EditorialFeedbackManager } from "./EditorialFeedbackManager";
import "../industry-brief.css";

function RefreshProgress({ open }: { open: boolean }) {
  const [progress, setProgress] = useState(8);
  useEffect(() => {
    if (!open) return;
    setProgress(8);
    const timer = window.setInterval(() => setProgress((value) => Math.min(92, value + (value < 45 ? 8 : value < 75 ? 4 : 1))), 700);
    return () => window.clearInterval(timer);
  }, [open]);
  if (!open) return null;
  const label = progress < 35 ? "최신 뉴스 수집 중" : progress < 62 ? "신규 기사 분석 중" : progress < 84 ? "이슈와 근거 기사 정리 중" : "브리핑을 작성하고 있습니다";
  return <div className="ib-refresh-progress-backdrop" role="presentation"><section className="ib-refresh-progress" role="status" aria-live="polite"><span className="ib-refresh-progress-label">INDUSTRY BRIEF UPDATE</span><h2>{label}</h2><p>새로운 업계 동향을 반영하고 있습니다.</p><div className="ib-refresh-progress-track"><span style={{ width: `${progress}%` }} /></div><strong>{progress}%</strong></section></div>;
}
export function IndustryBriefView() {
  const [brief, setBrief] = useState<IndustryBrief | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [periodLoading, setPeriodLoading] = useState(false);
  const [activePeriod, setActivePeriod] = useState<BriefPeriod>("today");

  const loadBrief = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    setError(false);
    try {
      setBrief(manual ? await refreshIndustryBrief() : await fetchPeriodBrief("today"));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadPeriod = useCallback(async (period: BriefPeriod) => {
    if (period === activePeriod) return;
    setPeriodLoading(true);
    setError(false);
    try {
      setBrief(await fetchPeriodBrief(period));
      setActivePeriod(period);
    } catch {
      setError(true);
    } finally {
      setPeriodLoading(false);
    }
  }, [activePeriod]);
  const reloadActivePeriod = useCallback(async () => {
    try { setBrief(await fetchPeriodBrief(activePeriod)); } catch { setError(true); }
  }, [activePeriod]);
  useEffect(() => { void loadBrief(); }, [loadBrief]);

  if (loading) return <div className="ib-page-status">Industry Brief를 불러오는 중입니다.</div>;
  if (error && !brief) return <div className="ib-page-status">아직 생성된 Industry Brief가 없습니다.<br />첫 분석이 완료되면 표시됩니다.</div>;
  if (!brief) return null;

  return (
    <div className="ib-stack">
      <header className="ib-page-header">
        <h1>{brief.periodLabel}{" 게임 · AI 업계 동향"}</h1>
        <div className="ib-header-actions">
          <div className="ib-header-period"><span>{brief.periodLabel}</span><strong className="tabular">{formatKoreanDateTime(brief.generatedAt)}</strong></div>
          <button type="button" className={`ib-refresh${refreshing ? " is-refreshing" : ""}`} onClick={() => { setActivePeriod("today"); void loadBrief(true); }} disabled={refreshing}><span aria-hidden="true">↻</span> {refreshing ? "업데이트 중" : "새로고침"}</button>
        </div>
      </header>
      {error && <div className="card ib-notice">최신 결과를 불러오지 못해 이전 분석을 표시합니다.</div>}<RefreshProgress open={refreshing} />
      <div className="ib-period-row">
        <BriefPeriodTabs active={activePeriod} loading={periodLoading} onChange={(period) => void loadPeriod(period)} />
        <EditorialFeedbackManager onRestore={() => void reloadActivePeriod()} />
      </div>
      <div className="ib-two-col">
        <IndustryPanelCard title="GAME" panel={brief.game} category="game" signals={brief.signals} periodLabel={brief.periodLabel} />
        <IndustryPanelCard title="AI" panel={brief.ai} category="ai" signals={brief.signals} periodLabel={brief.periodLabel} />
      </div>
      {brief.analytics && <BriefAnalyticsPanel analytics={brief.analytics} periodLabel={brief.periodLabel} />}
      {brief.policyUpdates && <PolicyUpdatesPanel updates={brief.policyUpdates} timeline={brief.policyTimeline ?? brief.policyUpdates} />}
      <CrossInsightPanel insight={brief.crossInsight} game={brief.game} ai={brief.ai} recommendations={brief.recommendedArticles} />
      {brief.landscape && <IndustryLandscapePanel landscape={brief.landscape} />}
      <SignalsPanel signals={brief.signals} />
      {brief.marketComparison && <MarketComparisonPanel panels={brief.marketComparison} />}
      <ImportantIssuesPanel issues={brief.issues} />
      <BriefHeader brief={brief} />
    </div>
  );
}

