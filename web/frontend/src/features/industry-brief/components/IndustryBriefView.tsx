import { useCallback, useEffect, useState } from "react";
import type { IndustryBrief } from "../types";
import {
  fetchBriefForDate, fetchHighlightsForDate,
  refreshDailyHighlights, refreshIndustryBrief, type DailyHighlightsResponse,
} from "../api/client";
import { formatDateLabel, formatKoreanDateTime, todayKstDateString } from "../utils/format";
import { DateNavigator } from "./DateNavigator";
import { IndustrySubmenu, type IndustryScreen } from "./IndustrySubmenu";
import { IndustryPanelCard } from "./IndustryPanelCard";
import { SignalsPanel } from "./SignalsPanel";
import { IndustryLandscapePanel } from "./IndustryLandscapePanel";
import { TechRadarPanel } from "./TechRadarPanel";
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
  const [activeScreen, setActiveScreen] = useState<IndustryScreen>("today");
  const [selectedDate, setSelectedDate] = useState(todayKstDateString());
  const [brief, setBrief] = useState<IndustryBrief | null>(null);
  const [highlights, setHighlights] = useState<DailyHighlightsResponse | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dateLoading, setDateLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const isToday = selectedDate === todayKstDateString();

  const loadDate = useCallback(async (date: string, isInitial = false) => {
    if (isInitial) setLoading(true); else setDateLoading(true);
    setError(false);
    try {
      const [nextBrief, nextHighlights] = await Promise.all([fetchBriefForDate(date), fetchHighlightsForDate(date)]);
      setBrief(nextBrief);
      setHighlights(nextHighlights);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
      setDateLoading(false);
    }
  }, []);

  useEffect(() => { void loadDate(selectedDate, true); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const changeDate = useCallback((date: string) => {
    setSelectedDate(date);
    void loadDate(date);
  }, [loadDate]);

  const refreshToday = useCallback(async () => {
    setRefreshing(true);
    setError(false);
    try {
      // Sequential, not Promise.all: /refresh and /highlights/refresh share
      // one process-local lock on the backend, so firing them concurrently
      // guarantees one instantly 409s and the whole refresh reports failure
      // no matter how fast either endpoint is.
      const nextBrief = await refreshIndustryBrief();
      const nextHighlights = await refreshDailyHighlights();
      setSelectedDate(todayKstDateString());
      setBrief(nextBrief);
      setHighlights(nextHighlights);
    } catch {
      setError(true);
    } finally {
      setRefreshing(false);
    }
  }, []);

  const reloadSelectedDate = useCallback(async () => {
    try { setBrief(await fetchBriefForDate(selectedDate)); } catch { setError(true); }
  }, [selectedDate]);

  if (loading) return <div className="ib-page-status">Industry Brief를 불러오는 중입니다.</div>;
  if (error && !brief) return <div className="ib-page-status">아직 생성된 Industry Brief가 없습니다.<br />첫 분석이 완료되면 표시됩니다.</div>;
  if (!brief) return null;

  return (
    <div className="ib-page-bg">
    <div className="ib-stack">
      <header className="ib-page-header">
        <h1>게임 · AI 업계 동향</h1>
        <div className="ib-header-actions">
          <div className="ib-header-period"><span>{isToday ? "오늘" : formatDateLabel(selectedDate)}</span><strong className="tabular">{formatKoreanDateTime(brief.generatedAt)}</strong></div>
          {isToday && activeScreen === "today" && (
            <button type="button" className={`ib-refresh${refreshing ? " is-refreshing" : ""}`} onClick={() => void refreshToday()} disabled={refreshing}><span aria-hidden="true">↻</span> {refreshing ? "업데이트 중" : "새로고침"}</button>
          )}
        </div>
      </header>
      <IndustrySubmenu active={activeScreen} onChange={setActiveScreen} />
      {error && <div className="card ib-notice">최신 결과를 불러오지 못해 이전 분석을 표시합니다.</div>}<RefreshProgress open={refreshing} />
      <div className="ib-period-row">
        <DateNavigator date={selectedDate} loading={dateLoading || refreshing} onChange={changeDate} />
        <EditorialFeedbackManager onRestore={() => void reloadSelectedDate()} />
      </div>

      {activeScreen === "today" && (
        <div className="ib-two-col">
          <IndustryPanelCard title="GAME" panel={brief.game} category="game" periodLabel={formatDateLabel(selectedDate)} highlights={highlights?.game} />
          <IndustryPanelCard title="AI" panel={brief.ai} category="ai" periodLabel={formatDateLabel(selectedDate)} highlights={highlights?.ai} />
        </div>
      )}

      {activeScreen === "policy" && brief.policyUpdates && (
        <PolicyUpdatesPanel updates={brief.policyUpdates} timeline={brief.policyTimeline ?? brief.policyUpdates} />
      )}

      {activeScreen === "tech" && <TechRadarPanel items={brief.techRadar ?? []} />}

      {activeScreen === "trend" && (
        <>
          {brief.landscape && <IndustryLandscapePanel landscape={brief.landscape} limit={8} />}
          {brief.analytics && <BriefAnalyticsPanel analytics={brief.analytics} periodLabel={formatDateLabel(selectedDate)} />}
          <SignalsPanel signals={brief.signals} limit={30} />
        </>
      )}
    </div>
    </div>
  );
}
