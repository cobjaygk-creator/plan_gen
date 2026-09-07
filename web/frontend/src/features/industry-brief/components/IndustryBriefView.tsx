import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { IndustryBrief } from "../types";
import {
  fetchBriefForDate, fetchHighlightsForDate,
  refreshDailyHighlights, refreshIndustryBrief, type DailyHighlightsResponse,
} from "../api/client";
import { formatDateLabel, formatKoreanDateTime, todayKstDateString } from "../utils/format";
import { DateNavigator } from "./DateNavigator";
import { IndustrySubmenu, type IndustryScreen } from "./IndustrySubmenu";
import { IndustryPanelCard } from "./IndustryPanelCard";
import { IndustryLandscapePanel } from "./IndustryLandscapePanel";
import { TechRadarPanel } from "./TechRadarPanel";
import { PolicyUpdatesPanel } from "./PolicyUpdatesPanel";
import { BriefAnalyticsPanel } from "./BriefAnalyticsPanel";
import { TopicLandscapePanel } from "./TopicLandscapePanel";
import { PolicyImpactPanel } from "./PolicyImpactPanel";
import { TrendKpiRow } from "./TrendKpiRow";
import { LeadCard } from "./LeadCard";
import { TodayLeadCard } from "./TodayLeadCard";
import { ReadingListPanel } from "./ReadingListPanel";
import { BriefSkeleton } from "./BriefSkeleton";
import "../industry-brief.css";

const REFRESH_STEP_LABELS = ["최신 뉴스 수집", "신규 기사 분석", "이슈와 근거 기사 정리", "브리핑 작성"];
// 백엔드가 /refresh 하나로 끝까지 블로킹 호출이라 실제 진행률 API가 없다
// — "지금 몇 %"는 여전히 경과 시간 기준 근사치일 수밖에 없지만, 적어도
// 4개의 구체적인 단계 중 "지금 여기"는 보여줄 수 있다(예전처럼 의미 없는
// 숫자만 올라가는 것보다는 낫다). 완료한 단계에 실제 결과 수치를 붙이지
// 못하는 건 진행 상황을 실시간으로 알려주는 백엔드 API가 없어서다.
const REFRESH_STEP_BOUNDARIES = [15, 50, 90, 140]; // 각 단계가 끝난다고 보는 누적 초(추정치)

function RefreshProgress({ open }: { open: boolean }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!open) return;
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [open]);
  if (!open) return null;
  const firstUnmet = REFRESH_STEP_BOUNDARIES.findIndex((boundary) => elapsed < boundary);
  const stepIndex = firstUnmet === -1 ? REFRESH_STEP_BOUNDARIES.length - 1 : firstUnmet;
  const stepStart = stepIndex === 0 ? 0 : REFRESH_STEP_BOUNDARIES[stepIndex - 1];
  const stepEnd = REFRESH_STEP_BOUNDARIES[stepIndex];
  const withinStep = Math.min(1, (elapsed - stepStart) / (stepEnd - stepStart));
  const percent = Math.min(96, Math.round(((stepIndex + withinStep) / REFRESH_STEP_BOUNDARIES.length) * 100));
  return (
    <div className="ib-refresh-progress-backdrop" role="presentation">
      <section className="ib-refresh-progress" role="status" aria-live="polite">
        <span className="ib-refresh-progress-label">INDUSTRY BRIEF UPDATE</span>
        <h2>{REFRESH_STEP_LABELS[stepIndex]}</h2>
        <p className="ib-refresh-progress-sub">보통 2~3분 걸립니다. 이 화면을 떠나도 계속 진행됩니다.</p>
        <div className="ib-refresh-progress-track"><span style={{ width: `${percent}%` }} /></div>
        <div className="ib-refresh-progress-meta">
          <span className="tabular">{stepIndex + 1} / {REFRESH_STEP_LABELS.length}단계</span>
          <strong className="tabular">{percent}%</strong>
        </div>
        <ol className="ib-refresh-steps">
          {REFRESH_STEP_LABELS.map((label, index) => (
            <li key={label} className={index < stepIndex ? "is-done" : index === stepIndex ? "is-active" : "is-pending"}>
              <span className="ib-refresh-step-dot" aria-hidden="true">{index < stepIndex ? "✓" : ""}</span>
              <span>{label}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

const VALID_SCREENS: readonly IndustryScreen[] = ["today", "trend", "policy", "tech"];

export function IndustryBriefView() {
  // 탭 선택 상태를 URL 쿼리(?tab=)에 담아둔다 — 로컬 state로만 두면
  // 브라우저 새로고침(F5)마다 "today"로 초기화돼서, 다른 탭을 보다가
  // 새로고침하면 매번 업계동향으로 튕겨나가는 게 불편하다는 피드백이 있었다.
  const [searchParams, setSearchParams] = useSearchParams();
  const activeScreen = useMemo<IndustryScreen>(() => {
    const raw = searchParams.get("tab");
    return (VALID_SCREENS as readonly string[]).includes(raw ?? "") ? (raw as IndustryScreen) : "today";
  }, [searchParams]);
  const setActiveScreen = useCallback((screen: IndustryScreen) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (screen === "today") next.delete("tab"); else next.set("tab", screen);
      return next;
    }, { replace: true });
  }, [setSearchParams]);
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

  if (loading) return <BriefSkeleton />;
  if (error && !brief) return (
    <div className="ib-page-status">
      아직 생성된 Industry Brief가 없습니다.<br />
      {/* 새로 배포한 서버처럼 DB가 완전히 비어있을 때, 여기서 막다른 길이었다 —
          평소 새로고침 버튼은 브리핑이 이미 있어야 나오는 헤더 안에만 있어서,
          최초 수집을 시작할 방법 자체가 화면에 없었다. */}
      첫 수집을 시작해주세요.
      <div className="ib-page-status-action">
        <button type="button" className={`ib-refresh${refreshing ? " is-refreshing" : ""}`} onClick={() => void refreshToday()} disabled={refreshing}>
          <span aria-hidden="true">↻</span> {refreshing ? "수집 중" : "첫 수집 시작"}
        </button>
      </div>
      <RefreshProgress open={refreshing} />
    </div>
  );
  if (!brief) return null;

  const trendFreshCount = brief.analytics?.topicFreshness.fresh.length ?? 0;
  const trendOngoingCount = (brief.analytics?.topicLandscape ?? []).filter((topic) => topic.days >= 2).length;
  const currentMonthPrefix = `${selectedDate.slice(0, 7).replace("-", ".")}.`;
  const policyThisMonthCount = (brief.policyTimeline ?? []).filter((item) => item.publishedDate.startsWith(currentMonthPrefix)).length;
  const topPolicy = brief.policyUpdates?.[0];

  return (
    <div className="ib-page-bg">
    <div className="ib-stack">
      <header className="ib-page-header">
        <h1>게임 · AI 업계 동향</h1>
        <div className="ib-header-actions">
          <div className="ib-header-period"><span>{isToday ? "오늘" : formatDateLabel(selectedDate)}</span><strong className="tabular">{formatKoreanDateTime(brief.generatedAt)}</strong></div>
          {isToday && (
            <button type="button" className={`ib-refresh${refreshing ? " is-refreshing" : ""}`} onClick={() => void refreshToday()} disabled={refreshing}><span aria-hidden="true">↻</span> {refreshing ? "업데이트 중" : "새로고침"}</button>
          )}
        </div>
      </header>
      <div className="ib-period-row">
        <IndustrySubmenu active={activeScreen} onChange={setActiveScreen} />
        {/* 정책/제도 탭(변화 타임라인, 항상 올해 기준)과 트렌드 탭(대부분
            30일 롤링 윈도우)은 날짜 이동이 내용에 거의 영향을 못 준다 —
            예전엔 이 두 탭에서 DOM에서 통째로 뺐는데, 그러면 탭을 옮길
            때마다 헤더 높이가 흔들렸다(6단계에서 지적된 문제). 자리는
            유지하고 비활성화 + 반투명 처리만 한다. */}
        <DateNavigator
          date={selectedDate}
          loading={dateLoading || refreshing}
          onChange={changeDate}
          disabled={activeScreen === "policy" || activeScreen === "trend"}
          label={activeScreen === "trend" ? "최근 30일" : activeScreen === "policy" ? `${selectedDate.slice(0, 4)}년` : undefined}
        />
      </div>
      {error && <div className="card ib-notice">최신 결과를 불러오지 못해 이전 분석을 표시합니다.</div>}<RefreshProgress open={refreshing} />

      {activeScreen === "today" && (
        <>
          <TodayLeadCard brief={brief} />
          <div className="ib-two-col">
            <IndustryPanelCard title="GAME" panel={brief.game} category="game" periodLabel={formatDateLabel(selectedDate)} highlights={highlights?.game} onViewLatest={isToday ? undefined : () => changeDate(todayKstDateString())} />
            <IndustryPanelCard title="AI" panel={brief.ai} category="ai" periodLabel={formatDateLabel(selectedDate)} highlights={highlights?.ai} onViewLatest={isToday ? undefined : () => changeDate(todayKstDateString())} />
          </div>
          <ReadingListPanel game={highlights?.game.recommended ?? []} ai={highlights?.ai.recommended ?? []} />
        </>
      )}

      {activeScreen === "policy" && brief.policyTimeline && (
        <>
          <LeadCard
            dotColor="var(--warning)"
            eyebrow="이번 달 판단"
            clamped
            headline={
              // 원문 제목을 그대로 인용하면 기사 헤드라인 특유의 겹따옴표·
              // 말줄임표가 뒤섞여 문장이 지저분해진다("관세청 "내년
              // 예산안...");  evidenceSentence(본문에서 뽑은 완결된 한 문장)를
              // 대신 써서 "OOO에서 ~했습니다" 식의 짧고 자연스러운 문장으로
              // 보여준다.
              topPolicy
                ? `이번 달 정책·제도 발표 ${policyThisMonthCount}건 중 가장 주목할 것은 ${topPolicy.source}의 발표입니다 — ${topPolicy.evidenceSentence}`
                : "이번 달은 특별히 주목할 정책·제도 발표가 없습니다."
            }
          />
          <PolicyUpdatesPanel timeline={brief.policyTimeline} />
        </>
      )}

      {activeScreen === "tech" && (
        <>
          <LeadCard
            dotColor="var(--cat-ai)"
            eyebrow="오늘의 태그 분포"
            compact
            headline={
              brief.techRadar && brief.techRadar.length > 0
                ? `오늘 AI 업계에서 가장 활발한 태그는 "${brief.techRadar[0].label}"입니다.`
                : "오늘은 두드러진 AI 기술 태그가 없습니다."
            }
          >
            {brief.techRadar && brief.techRadar.length > 0 && (
              <div className="ib-lead-tag-chips">
                {brief.techRadar.map((tag, index) => (
                  <span key={tag.key} className={`ib-lead-tag-chip${index < 2 ? " is-top" : ""}`}>{tag.label} {tag.articleCount}</span>
                ))}
              </div>
            )}
          </LeadCard>
          <TechRadarPanel items={brief.techRadar ?? []} />
        </>
      )}

      {activeScreen === "trend" && (
        <>
          <LeadCard
            dotColor="var(--success)"
            eyebrow="최근 30일 판단"
            clamped
            clampLines={1}
            headline={
              trendFreshCount > 0
                ? `이번 달 새로 등장한 토픽 ${trendFreshCount}개, 2일 이상 이어지는 지속형 이슈는 ${trendOngoingCount}개입니다.`
                : `이번 달은 새로 등장한 토픽 없이, 지속형 이슈 ${trendOngoingCount}개가 흐름을 이어가고 있습니다.`
            }
          >
            <TrendKpiRow brief={brief} />
          </LeadCard>
          {brief.analytics && <BriefAnalyticsPanel analytics={brief.analytics} />}
          {brief.analytics && <TopicLandscapePanel analytics={brief.analytics} />}
          <PolicyImpactPanel impacts={brief.policyImpact} />
          {brief.landscape && <IndustryLandscapePanel landscape={brief.landscape} limit={8} />}
        </>
      )}
    </div>
    </div>
  );
}
