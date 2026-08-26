import { useEffect, useState } from "react";
import type { IndustryPanel, SourceItem } from "../types";
import { clearIssueFeedback, submitIssueFeedback, type CategoryHighlights, type CoreFeedbackReason } from "../api/client";

interface Props {

  title: string;
  panel: IndustryPanel;
  category: "game" | "ai";
  periodLabel: string;
  /** When set (오늘 tab only), replaces the old cross-verification-gated
   * key-summary block with the AI-judged 핵심 이슈 + 추천 기사 list. */
  highlights?: CategoryHighlights;
}

const MAX_CORE_ISSUES = 5;
const VISIBLE_CORE_ISSUES = 3;
const RECOMMENDED_PAGE_SIZE = 6;

function articleToSource(article: { title: string; url: string; source: string }): SourceItem {
  return { outlet: article.source.replace(/^NAVER · /, ""), title: article.title, url: article.url, publishedAgo: "" };
}

function DailyHighlightsBlock({ highlights, category }: { highlights: CategoryHighlights; category: "game" | "ai" }) {
  const [issuePage, setIssuePage] = useState(0);
  const [recommendedPage, setRecommendedPage] = useState(0);
  const recommendedPageCount = Math.max(1, Math.ceil(highlights.recommended.length / RECOMMENDED_PAGE_SIZE));
  const visibleRecommended = highlights.recommended.slice(
    recommendedPage * RECOMMENDED_PAGE_SIZE, recommendedPage * RECOMMENDED_PAGE_SIZE + RECOMMENDED_PAGE_SIZE,
  );
  const recommendedLabel = `${category === "game" ? "게임" : "AI"}추천기사`;
  const coreIssues = highlights.coreIssues.slice(0, MAX_CORE_ISSUES);
  const issuePageCount = Math.max(1, Math.ceil(coreIssues.length / VISIBLE_CORE_ISSUES));
  useEffect(() => {
    if (issuePageCount <= 1) return;
    const timer = window.setInterval(() => setIssuePage((page) => (page + 1) % issuePageCount), 6500);
    return () => window.clearInterval(timer);
  }, [issuePageCount]);

  if (!highlights.hasSignal) {
    return (
      <div className="ib-daily-highlights ib-highlight-section">
        <div className="eyebrow">핵심이슈</div>
        <div className="ib-key-summary"><p className="headline">지난 24시간 동안 분석할 만큼 충분한 기사가 수집되지 않았습니다.</p></div>
      </div>
    );
  }
  const visibleIssueCount = Math.min(VISIBLE_CORE_ISSUES, coreIssues.length);
  const visibleIssues = Array.from(
    { length: visibleIssueCount },
    (_, offset) => coreIssues[(issuePage * VISIBLE_CORE_ISSUES + offset) % coreIssues.length],
  );
  return (
    <div className="ib-daily-highlights">
      <div className="ib-highlight-section">
        <div className="eyebrow">핵심이슈</div>
        <div className="ib-highlight-issue-list">
          {visibleIssues.map((issue, index) => (
            <div className="ib-highlight-issue ib-change-flap" key={issue.title} style={{ animationDelay: `${(index * 0.11).toFixed(2)}s` }}>
              <p className="headline">{issue.title}</p>
              <p className="ib-highlight-summary">{issue.summary}</p>
              <div className="ib-highlight-issue-foot">
                <span className="ib-highlight-issue-foot-label">관련 기사</span>
                <EvidenceSources sources={issue.articles.map(articleToSource)} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {highlights.recommended.length > 0 && (
        <div className="ib-highlight-section">
          <div className="ib-recommended-head">
            <span className="section-label">{recommendedLabel}</span>
            {recommendedPageCount > 1 && (
              <button
                type="button"
                className="ib-recommended-next"
                onClick={() => setRecommendedPage((page) => (page + 1) % recommendedPageCount)}
              >
                다음
              </button>
            )}
          </div>
          <div className="ib-recommended-list">
            {visibleRecommended.map((article) => (
              <a key={article.url} href={article.url} target="_blank" rel="noreferrer" className="ib-recommended-item">
                <div className="ib-recommended-top"><span className="outlet">{article.source.replace(/^NAVER · /, "")}</span></div>
                <div className="title">{article.title}</div>
                <div className="reason">{article.reason}</div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EvidenceSources({ sources }: { sources: SourceItem[] }) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;

  return (
    <div className="ib-item-evidence">
      <button type="button" className="ib-evidence-count tabular" aria-expanded={open} title="근거 기사 보기" onClick={() => setOpen((value) => !value)}>
        {open ? "−" : "+"}{sources.length}
      </button>
      {open && (
        <div className="ib-item-source-list">
          <div className="ib-source-pop-title">근거 기사 {sources.length}건</div>
          {sources.map((source) => (
            <a key={source.url + source.title} className="ib-item-source" href={source.url} target="_blank" rel="noreferrer">
              <span className="outlet">{source.outlet}</span>
              <span className="title">{source.title}</span>
              <span className="ago">{source.publishedAgo}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

export function IndustryPanelCard({ title, panel, category, periodLabel, highlights }: Props) {
  const keySummaries = panel.keySummaries?.length ? panel.keySummaries.slice(0, 2) : [panel.headline];
  const [dismissedIssues, setDismissedIssues] = useState<Set<number>>(new Set());
  const [feedbackError, setFeedbackError] = useState<number | null>(null);
  const [reasonIssue, setReasonIssue] = useState<number | null>(null);
  const markNotCore = async (issueId: number, reason: CoreFeedbackReason) => {
    try {
      await submitIssueFeedback(issueId, "NOT_CORE", reason);
      setDismissedIssues((current) => new Set(current).add(issueId));
      setReasonIssue(null);
      window.dispatchEvent(new Event("industry-feedback-changed"));
      setFeedbackError(null);
    } catch {
      setFeedbackError(issueId);
    }
  };
  const undoNotCore = async (issueId: number) => {
    try {
      await clearIssueFeedback(issueId);
      setDismissedIssues((current) => { const next = new Set(current); next.delete(issueId); return next; });
      window.dispatchEvent(new Event("industry-feedback-changed"));
      setFeedbackError(null);
    } catch { setFeedbackError(issueId); }
  };
  return (
    <section className={`card ib-panel ib-panel-${category}`}>

      <div className="ib-panel-head">
        <div className="ib-panel-title"><h2>{title}</h2></div>
        <span className="ib-panel-status">{periodLabel}</span>
      </div>

      {highlights ? (
        <DailyHighlightsBlock highlights={highlights} category={category} />
      ) : (
        <>
          <div className="ib-highlight-section">
          <div className="eyebrow">핵심 요약</div>
          <div className="ib-key-summary-list">
            {keySummaries.map((summary, index) => {
              const detail = panel.keySummaryDetails?.[index];
              if (detail?.issueId && dismissedIssues.has(detail.issueId)) return <div className="ib-feedback-applied" key={`${index}-${summary}`}>핵심 아님 의견이 반영됐습니다.<button type="button" onClick={() => void undoNotCore(detail.issueId!)}>취소</button></div>;
              return <div className="ib-key-summary" key={`${index}-${summary}`}><p className="headline">{summary}</p>{detail && <><div className="ib-key-summary-meta"><p className="ib-key-summary-reason">{detail.selectionReason}</p>{detail.issueId && <button type="button" onClick={() => setReasonIssue((current) => current === detail.issueId ? null : detail.issueId!)}>{feedbackError === detail.issueId ? "저장 실패" : "핵심 아님"}</button>}</div>{detail.issueId && reasonIssue === detail.issueId && <div className="ib-feedback-reasons"><span>제외 사유</span>{([['PROMOTIONAL','홍보성'],['LOW_IMPORTANCE','중요도 낮음'],['DUPLICATE','중복'],['LOW_IMPACT','업계 영향 부족'],['OTHER','기타']] as Array<[CoreFeedbackReason,string]>).map(([value,label]) => <button type="button" key={value} onClick={() => void markNotCore(detail.issueId!, value)}>{label}</button>)}</div>}</>}{detail?.scoreBreakdown && <details className="ib-score-breakdown"><summary>선정 점수 <strong>{detail.scoreBreakdown.total}</strong>점</summary><div className="ib-score-grid"><span>근거 신뢰도 <b>{detail.scoreBreakdown.evidence}</b></span><span>기사 확산 <b>{detail.scoreBreakdown.coverage}</b></span><span>중요도 <b>{detail.scoreBreakdown.importance}</b></span><span>지속성 <b>{detail.scoreBreakdown.persistence}</b></span><span>증가세 <b>{detail.scoreBreakdown.momentum}</b></span>{detail.scoreBreakdown.editorialAdjustment !== 0 && <span className="adjustment">편집 기준 <b>{detail.scoreBreakdown.editorialAdjustment}</b></span>}{detail.scoreBreakdown.userFeedback !== 0 && <span className="adjustment">사용자 판단 <b>{detail.scoreBreakdown.userFeedback}</b></span>}{detail.scoreBreakdown.approvedRule !== 0 && <span className="adjustment">승인 규칙 <b>{detail.scoreBreakdown.approvedRule}</b></span>}</div></details>}</div>;
            })}
          </div>
          </div>

          {(panel.observations?.length ?? 0) > 0 && <div className="ib-observation-block">
            <div className="ib-observation-heading"><span>공식·주요 매체 관찰</span><small>추가 보도 확인 중</small></div>
            <div className="ib-observation-list">{panel.observations!.map((observation) => (
              <div className="ib-observation-item" key={observation.title}>
                <span className="ib-observation-status">{observation.statusLabel}</span>
                <div className="ib-observation-copy"><strong>{observation.title}</strong><p>{observation.description}</p><small>{observation.selectionReason}</small></div>
                <EvidenceSources sources={observation.sources} />
              </div>
            ))}</div>
          </div>}

          {(panel.promotions?.length ?? 0) > 0 && <div className="ib-promotion-block">
            <div className="ib-promotion-heading">관찰에서 핵심으로 승격</div>
            {panel.promotions!.map((promotion) => <div className="ib-promotion-item" key={`${promotion.title}-${promotion.promotedAt}`}>
              <span>승격</span><div><strong>{promotion.title}</strong><p>{promotion.reason}</p></div>
            </div>)}
          </div>}

          {(panel.closedObservations?.length ?? 0) > 0 && <details className="ib-closed-observations">
            <summary>관찰 종료 {panel.closedObservations!.length}건</summary>
            {panel.closedObservations!.map((item) => <div key={`${item.title}-${item.closedAt}`}><strong>{item.title}</strong><p>{item.reason}</p></div>)}
          </details>}

          <div className="ib-highlight-section">
          <div className="section-label">앞으로 볼 것</div>
          <div className="ib-watch-list">
            {panel.watchList.slice(0, 3).map((watch) => (
              <div className="ib-watch-item" key={watch.rank}>
                <span className="rank tabular">{String(watch.rank).padStart(2, "0")}</span>
                <div className="body">
                  <div className="ib-item-topic-row">
                    <div className="topic">{watch.topic}</div>
                    <EvidenceSources sources={watch.sources ?? []} />
                  </div>
                  <div className="desc">{watch.description}</div>
                </div>
              </div>
            ))}
          </div>
          </div>
        </>
      )}
    </section>
  );
}
