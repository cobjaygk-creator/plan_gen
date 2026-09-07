import { useState } from "react";
import type { IndustryPanel, SourceItem } from "../types";
import { clearIssueFeedback, submitIssueFeedback, type CategoryHighlights, type CoreFeedbackReason, type HighlightIssue } from "../api/client";
import { EmptyState } from "./EmptyState";

interface Props {

  title: string;
  panel: IndustryPanel;
  category: "game" | "ai";
  periodLabel: string;
  /** When set (오늘 tab only), replaces the old cross-verification-gated
   * key-summary block with the AI-judged 핵심 이슈 + 추천 기사 list. */
  highlights?: CategoryHighlights;
  /** 빈 상태에서 "가장 최근 브리핑 보기"를 눌렀을 때 오늘 날짜로 이동. */
  onViewLatest?: () => void;
}

const MAX_CORE_ISSUES = 3;

function DailyHighlightsBlock({ highlights, periodLabel, onViewLatest }: { highlights: CategoryHighlights; periodLabel: string; onViewLatest?: () => void }) {
  const [openIssue, setOpenIssue] = useState<HighlightIssue | null>(null);
  // 자동 로테이션 제거(디자인 핸드오프 3단계) — 예전엔 5개를 뽑아 2개씩
  // 6.5초마다 돌려 보여줬는데, 읽는 도중 내용이 바뀌는 문제가 있었다.
  // 이제 최대 3개를 그냥 다 렌더한다.
  const coreIssues = highlights.coreIssues.slice(0, MAX_CORE_ISSUES);

  if (!highlights.hasSignal) {
    return (
      <div className="ib-daily-highlights ib-highlight-section">
        <div className="eyebrow">핵심이슈</div>
        <EmptyState
          title={`${periodLabel}에는 핵심 이슈로 뽑을 만큼 기사가 모이지 않았습니다`}
          description={`수집은 ${highlights.articleCount}건 됐지만 교차 확인된 이슈가 없습니다. 주말·공휴일에는 흔한 상태입니다.`}
          actions={onViewLatest ? [{ label: "가장 최근 브리핑 보기", onClick: onViewLatest, variant: "primary" }] : undefined}
        />
      </div>
    );
  }
  return (
    <div className="ib-daily-highlights">
      <div className="ib-highlight-section ib-highlight-core">
        <div className="eyebrow">핵심이슈</div>
        <div className="ib-highlight-issue-list">
          {coreIssues.map((issue, index) => {
            // AI가 판단한 핵심이슈는 별도 신뢰도 점수가 없어서(교차검증
            // 스코어링을 거치는 옛 keySummaryDetails 경로와 다름), 근거
            // 기사의 매체 다양성으로 대신 근사한다 — 서로 다른 매체 2곳
            // 이상이면 "교차 확인", 아니면 "단일 관점".
            const sourceCount = new Set(issue.articles.map((article) => article.source)).size;
            const isCorroborated = sourceCount >= 2;
            return (
              <button
                type="button"
                className="ib-highlight-issue"
                key={issue.title}
                onClick={() => setOpenIssue(issue)}
              >
                <span className="ib-highlight-issue-rank tabular">{String(index + 1).padStart(2, "0")}</span>
                <div className="ib-highlight-issue-body">
                  <p className="ib-highlight-summary ib-highlight-briefing">{issue.summary}</p>
                  <div className="ib-highlight-issue-foot">
                    <span className="ib-highlight-issue-foot-label">기사 {issue.articles.length}건 · 독립 매체 {sourceCount}곳</span>
                    <span className={`ib-confidence-badge ${isCorroborated ? "is-corroborated" : "is-single"}`}>
                      {isCorroborated ? "교차 확인" : "단일 관점"}
                    </span>
                    <span className="ib-highlight-issue-foot-more">근거 기사 →</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
      {openIssue && <HighlightIssueModal issue={openIssue} onClose={() => setOpenIssue(null)} />}
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

function HighlightIssueModal({ issue, onClose }: { issue: HighlightIssue; onClose: () => void }) {
  return (
    <div className="ib-highlight-modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="ib-highlight-modal"
        role="dialog"
        aria-modal="true"
        aria-label="핵심이슈 상세"
        onClick={(event) => event.stopPropagation()}
      >
        <button type="button" className="ib-highlight-modal-close" onClick={onClose} aria-label="닫기">×</button>
        <p className="ib-highlight-modal-eyebrow">핵심이슈</p>
        <p className="ib-highlight-modal-body">{issue.summary}</p>
        {issue.detail && <p className="ib-highlight-modal-detail">{issue.detail}</p>}
        <div className="ib-highlight-modal-articles">
          <div className="ib-source-pop-title">관련 기사 {issue.articles.length}건</div>
          {issue.articles.map((article) => (
            <a key={article.url} className="ib-item-source" href={article.url} target="_blank" rel="noreferrer">
              <span className="outlet">{article.source.replace(/^NAVER · /, "")}</span>
              <span className="title">{article.title}</span>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}

export function IndustryPanelCard({ title, panel, category, periodLabel, highlights, onViewLatest }: Props) {
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
        <div className="ib-panel-title">
          <span className="ib-panel-color-bar" aria-hidden="true" />
          <h2>{title}</h2>
          {highlights && <span className="ib-panel-count">기사 {highlights.articleCount}건</span>}
        </div>
        <span className="ib-panel-status">{periodLabel}</span>
      </div>

      {highlights ? (
        <DailyHighlightsBlock highlights={highlights} periodLabel={periodLabel} onViewLatest={onViewLatest} />
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
