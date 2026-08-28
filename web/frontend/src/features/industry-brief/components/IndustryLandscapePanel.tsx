import { useState } from "react";
import { fetchLandscapeIssueDetail } from "../api/client";
import type { IndustryLandscape, LandscapeEvidenceArticle, LandscapeIssueDetail } from "../types";

interface Props { landscape: IndustryLandscape; limit?: number; }

const DOMAIN_TITLES: Record<string, string> = { GAME: "게임 산업", AI: "AI 산업", GAME_AI: "게임 × AI" };

function EvidenceList({ articles, emptyText }: { articles: LandscapeEvidenceArticle[]; emptyText: string }) {
  if (articles.length === 0) return <p className="ib-landscape-empty">{emptyText}</p>;
  return <ul className="ib-landscape-evidence-list">{articles.map((article) => (
    <li key={`${article.url}-${article.title}`}>
      {article.url ? <a href={article.url} target="_blank" rel="noreferrer">{article.title}</a> : <strong>{article.title}</strong>}
      <div className="ib-landscape-evidence-meta"><span>{article.source ?? "출처 미상"}</span>{article.publishedAt && <time>{article.publishedAt}</time>}</div>
    </li>
  ))}</ul>;
}

export function IndustryLandscapePanel({ landscape, limit = 3 }: Props) {
  const [detail, setDetail] = useState<LandscapeIssueDetail | null>(null);
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const maxTimelineCount = Math.max(1, ...(detail?.timeline.map((point) => point.count) ?? [1]));
  const close = () => { setDetail(null); setError(false); };
  async function openDetail(issueKey: string) {
    setLoadingKey(issueKey); setError(false);
    try { setDetail(await fetchLandscapeIssueDetail(issueKey)); } catch { setError(true); } finally { setLoadingKey(null); }
  }
  return <section className="ib-landscape" aria-label="연간 업계 이슈 지도">
    <div className="ib-section-heading ib-landscape-heading"><div><span>업계 이슈 지도</span><small>올해 기획팀이 축적한 {landscape.referenceArticleCount}건의 스크랩을 기준으로, 최근 흐름을 함께 봅니다.</small></div><span>장기 흐름 · 최근 신호</span></div>
    <div className="ib-landscape-grid">{landscape.domains.map((domain) => <article className="ib-landscape-domain" key={domain.key}>
      <header><h3>{DOMAIN_TITLES[domain.key] ?? domain.label}</h3><span>TOP {Math.min(limit, domain.issues.length) || domain.issues.length}</span></header>
      <div className="ib-landscape-list">{domain.issues.length === 0 && <p className="ib-landscape-empty">축적된 이슈가 아직 없습니다.</p>}
        {domain.issues.slice(0, limit).map((issue) => <button className="ib-landscape-issue" type="button" key={issue.key} onClick={() => void openDetail(issue.key)}>
          <strong>{issue.title}</strong><div className="ib-landscape-meta"><span>올해 {issue.referenceCount}건</span><span>최근 분석 {issue.recentArticleCount}건</span></div>
          {issue.priorityReasons.length > 0 && <p className="ib-landscape-priority">{issue.priorityReasons.join(" · ")}</p>}<em>{loadingKey === issue.key ? "불러오는 중" : "근거 기사 보기"}</em>
        </button>)}</div>
    </article>)}</div>
    {(detail || error) && <div className="ib-landscape-modal-backdrop" role="presentation" onClick={close}><section className="ib-landscape-modal" role="dialog" aria-modal="true" aria-label="이슈 근거 기사" onClick={(event) => event.stopPropagation()}>
      <button type="button" className="ib-landscape-close" onClick={close} aria-label="닫기">×</button>
      {error ? <p className="ib-landscape-empty">근거 기사를 불러오지 못했습니다.</p> : detail && <><p className="ib-landscape-modal-eyebrow">이슈 근거</p><h3>{detail.title}</h3><p className="ib-landscape-modal-summary">{detail.historicalStart ? `${detail.historicalStart}부터` : "올해"} 축적된 기사 {detail.historicalCount}건과 최근 분석 기사 {detail.recentCount}건입니다.</p><div className="ib-landscape-change"><strong>관찰의 변화</strong><p>{detail.changeSummary}</p><div className="ib-landscape-timeline" aria-label="월별 기준선 기사 수">{detail.timeline.map((point) => <div key={point.month}><span style={{ height: `${Math.max(12, Math.round((point.count / maxTimelineCount) * 100))}%` }} /><small>{point.month.slice(5)}월</small></div>)}</div></div><div className="ib-landscape-evidence-columns"><div><h4>올해 스크랩</h4><EvidenceList articles={detail.historicalArticles} emptyText="기준선 기사가 없습니다." /></div><div><h4>최근 분석 기사</h4><EvidenceList articles={detail.recentArticles} emptyText="최근 30일 내 연결된 기사가 없습니다." /></div></div></>}
    </section></div>}
  </section>;
}