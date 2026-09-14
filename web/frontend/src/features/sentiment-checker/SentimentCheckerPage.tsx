import { useEffect, useState } from "react";
import type { DashboardData, IssueDetail } from "./types";
import { PERIODS } from "./utils";
import { ScoreBand } from "./components/ScoreBand";
import { BriefCard } from "./components/BriefCard";
import { IssuesPanel } from "./components/IssuesPanel";
import { RisingPanel } from "./components/RisingPanel";
import { TrendPanel } from "./components/TrendPanel";
import { SourceCategoryPanel } from "./components/SourceCategoryPanel";
import { ReferencesPanel } from "./components/ReferencesPanel";
import { RecentPanel } from "./components/RecentPanel";
import { IssueDetailModal } from "./components/IssueDetailModal";
import "./sentiment-checker.css";

export function SentimentCheckerPage() {
  const [hours, setHours] = useState(24);
  const [data, setData] = useState<DashboardData | null>(null);
  // loading: 그냥 저장된 데이터를 읽어오는 초기/기간 전환 로딩.
  // refreshing: "수동 갱신"이 실제로 외부 사이트를 크롤링하고 AI 분석까지
  // 돌리는 무거운 작업이 진행 중이라는 뜻 — 이 둘을 하나로 합쳐 쓰면
  // 페이지를 열기만 해도 버튼이 "분석 중"으로 보이는 문제가 생긴다
  // (실제로 갱신 버튼을 누른 적이 없는데도 그렇게 보인다는 피드백으로
  // 확인).
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);
  const [detail, setDetail] = useState<IssueDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = (h = hours) => {
    setLoading(true);
    setError(false);
    fetch(`/sentiment-checker/dashboard?hours=${h}`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => load(hours), [hours]);

  const openDetail = (key: string) => {
    setDetailLoading(true);
    fetch(`/sentiment-checker/issues/detail?key=${encodeURIComponent(key)}&hours=${hours}`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(setDetail)
      .finally(() => setDetailLoading(false));
  };

  const refresh = () => {
    setRefreshing(true);
    fetch("/sentiment-checker/refresh", { method: "POST", credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((x) => setData(x.dashboard))
      .catch(() => setError(true))
      .finally(() => setRefreshing(false));
  };

  return (
    <main className="sc-page">
      <header className="sc-hero">
        <div>
          <span className="sc-eyebrow">COMMUNITY PULSE</span>
          <h1>라테일 민심 체크기</h1>
          <p>커뮤니티 반응을 이슈 단위로 묶어 변화를 추적합니다.</p>
        </div>
        <div className="sc-hero-actions">
          <nav className="sc-periods">
            {PERIODS.map((p) => (
              <button key={p.hours} className={hours === p.hours ? "is-active" : ""} onClick={() => setHours(p.hours)}>
                {p.label}
              </button>
            ))}
          </nav>
          <button className="sc-refresh-btn" onClick={refresh} disabled={loading || refreshing}>
            {refreshing ? "분석 중" : "수동 갱신"}
          </button>
        </div>
      </header>

      {error && <p className="sc-error">데이터를 불러오지 못했습니다.</p>}
      {!data && !error && <p className="sc-loading">민심 데이터를 불러오는 중입니다.</p>}

      {data && (
        <>
          <ScoreBand metrics={data.metrics} timeline={data.timeline} />
          <BriefCard brief={data.brief} analysisBasis={data.analysis_basis} analysisCount={data.analysis_count} />

          <div className="sc-columns">
            <IssuesPanel issues={data.issues} onSelect={openDetail} />
            <RisingPanel spikes={data.spikes} observations={data.observations} onSelect={openDetail} />
          </div>

          <TrendPanel timeline={data.timeline} />
          <ReferencesPanel references={data.references} />
          <SourceCategoryPanel sources={data.sources} categories={data.categories} />
          <RecentPanel recent={data.recent} />
        </>
      )}

      {detailLoading && (
        <div className="sc-modal-backdrop">
          <div className="sc-modal-loading">이슈 근거를 불러오는 중입니다.</div>
        </div>
      )}
      {detail && !detailLoading && <IssueDetailModal detail={detail} onClose={() => setDetail(null)} />}
    </main>
  );
}
