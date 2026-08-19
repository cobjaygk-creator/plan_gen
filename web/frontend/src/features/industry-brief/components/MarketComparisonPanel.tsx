import type { ComparisonTopic, MarketComparisonPanel as MarketPanel } from "../types";

function Topics({ topics, mode }: { topics: ComparisonTopic[]; mode: "single" | "shared" }) {
  if (topics.length === 0) return <span className="ib-market-empty">뚜렷한 차이가 없습니다.</span>;
  return <div className="ib-market-topics">{topics.map((topic) => (
    <span key={topic.topic}>{topic.topic}{mode === "shared" && <small>한국 {topic.koreaCount} · 글로벌 {topic.globalCount}</small>}</span>
  ))}</div>;
}

export function MarketComparisonPanel({ panels }: { panels: MarketPanel[] }) {
  if (panels.length === 0) return null;
  return <section className="card ib-market-comparison">
    <div className="ib-section-heading"><div>한국 vs 글로벌</div><span>같은 기간의 실제 기사 키워드 비교</span></div>
    <div className="ib-market-list">{panels.map((panel) => (
      <article className="ib-market-row" key={panel.category}>
        <header><strong>{panel.label} 산업</strong><span>한국 {panel.koreaArticleCount}건 · 글로벌 {panel.globalArticleCount}건</span></header>
        <div className="ib-market-grid">
          <div><h4>한국 집중</h4><Topics topics={panel.koreaFocus} mode="single" /></div>
          <div className="shared"><h4>공통 흐름</h4><Topics topics={panel.sharedTopics} mode="shared" /></div>
          <div><h4>글로벌 집중</h4><Topics topics={panel.globalFocus} mode="single" /></div>
        </div>
      </article>
    ))}</div>
  </section>;
}