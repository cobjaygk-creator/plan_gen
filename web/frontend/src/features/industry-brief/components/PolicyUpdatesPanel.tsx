import { useState } from "react";
import type { PolicyUpdate } from "../types";

const FILTERS: Array<{ key: "ALL" | PolicyUpdate["type"]; label: string }> = [
  { key: "ALL", label: "전체" },
  { key: "REGULATION", label: "규제 시행" },
  { key: "ENFORCEMENT", label: "단속·집행" },
  { key: "FUNDING", label: "지원사업" },
  { key: "TALENT", label: "인재" },
  { key: "GLOBAL", label: "해외 진출" },
  { key: "PARTNERSHIP", label: "협력" },
];

export function PolicyUpdatesPanel({ updates, timeline }: { updates: PolicyUpdate[]; timeline: PolicyUpdate[] }) {
  const [filter, setFilter] = useState<"ALL" | PolicyUpdate["type"]>("ALL");
  const [view, setView] = useState<"priority" | "timeline">("priority");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const visible = filter === "ALL" ? updates : updates.filter((item) => item.type === filter);
  const summary = timeline.reduce((counts, item) => {
    counts[item.changeType] = (counts[item.changeType] ?? 0) + 1;
    return counts;
  }, {} as Record<PolicyUpdate["changeType"], number>);
  return <section className="card ib-policy-panel">
    <div className="ib-section-heading">
      <div>정책·제도 업데이트</div>
      <span>공식 발표 원문 기준 · 영향은 시사점으로 구분</span>
    </div>
    <div className="ib-policy-view-tabs">
      <button className={view === "priority" ? "is-active" : ""} onClick={() => setView("priority")} type="button">주요 정책</button>
      <button className={view === "timeline" ? "is-active" : ""} onClick={() => setView("timeline")} type="button">변화 타임라인</button>
    </div>
    {view === "priority" && updates.length > 0 && <div className="ib-policy-filters">{FILTERS.map((item) => (
      <button className={filter === item.key ? "is-active" : ""} key={item.key} onClick={() => setFilter(item.key)} type="button">{item.label}</button>
    ))}</div>}
    {view === "timeline" ? <>
      <div className="ib-policy-summary">
        <div><strong>{timeline.length}</strong><span>전체 변화</span></div>
        <div><strong>{summary.NEW ?? 0}</strong><span>신규</span></div>
        <div><strong>{summary.REVISION ?? 0}</strong><span>개정</span></div>
        <div><strong>{summary.STAGE_CHANGE ?? 0}</strong><span>단계 변화</span></div>
        <div><strong>{summary.FOLLOW_UP ?? 0}</strong><span>후속 발표</span></div>
      </div>
      {timeline.length === 0 ? <p className="ib-policy-empty">선택한 기간에는 정책 변화가 없습니다.</p> : <ol className="ib-policy-timeline">{timeline.map((item) => (
        <li key={`timeline-${item.id}`}>
          <time>{item.publishedDate}</time><span className="ib-policy-timeline-dot" />
          <div><div><strong>{item.changeLabel}</strong><span>{item.typeLabel}</span><em>{item.urgencyLabel}</em></div>
          <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
          <p>{item.policyKey}{item.historyCount > 0 ? ` · 이전 발표 ${item.historyCount}건과 연결` : ""}</p></div>
        </li>
      ))}</ol>}
    </> : visible.length === 0 ? <p className="ib-policy-empty">{updates.length === 0 ? "선택한 기간에는 게임·AI 관련 공식 정책 발표가 없습니다." : "선택한 유형의 공식 정책 발표가 없습니다."}</p> : <div className="ib-policy-grid">{visible.map((item) => (
      <article className={`ib-policy-card${expandedId === item.id ? " is-expanded" : ""}`} key={item.id}>
        <header>
          <div className="ib-policy-badges">
            <span className={`type-${item.type.toLowerCase()}`}>{item.typeLabel}</span>
            <span className={`priority-${item.priorityLabel === "긴급 확인" ? "urgent" : item.priorityLabel === "우선 확인" ? "high" : "watch"}`}>{item.priorityLabel}</span>
          </div>
          <time>{item.publishedDate}</time>
        </header>
        <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
        <div className={`ib-policy-change change-${item.changeType.toLowerCase()}`}>
          {item.changeLabel}<span>{item.policyKey}{item.historyCount > 0 ? ` · 이전 발표 ${item.historyCount}건` : ""}</span>
        </div>
        <div className="ib-policy-reason"><strong>선정 이유</strong>{item.selectionReason}</div>
        {expandedId === item.id && <div className="ib-policy-detail">
          <div className="ib-policy-proof">
            <blockquote><strong>공식 근거 문장</strong>{item.evidenceSentence}</blockquote>
          </div>
          <dl>
            <div><dt>대상</dt><dd>{item.target}</dd></div>
            <div><dt>시행·일정</dt><dd>{item.effectiveDate ?? "원문에서 일정 확인 필요"} <em>{item.urgencyLabel}</em></dd></div>
            <div><dt>핵심 조치</dt><dd>{item.action}</dd></div>
          </dl>
          <p><strong>시사점</strong>{item.implication}</p>
          <div className="ib-policy-response">
            <strong>실무 확인</strong>
            <ul>{item.responseChecklist.map((check) => <li key={check}>{check}</li>)}</ul>
          </div>
          {item.history.length > 0 && <details className="ib-policy-history">
            <summary>변경 이력 보기</summary>
            <ul>{item.history.map((entry) => <li key={`${entry.url}-${entry.publishedDate}`}>
              <span>{entry.publishedDate} · {entry.stageLabel}</span>
              <a href={entry.url} target="_blank" rel="noreferrer">{entry.title}</a>
            </li>)}</ul>
          </details>}
        </div>}
        <footer><span>{item.source} · 공식 원문 ↗</span><button type="button" aria-expanded={expandedId === item.id} onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}>{expandedId === item.id ? "접기 −" : "상세 보기 +"}</button></footer>
      </article>
    ))}</div>}
  </section>;
}
