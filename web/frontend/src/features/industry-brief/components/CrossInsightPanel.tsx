import type { CrossInsight, IndustryPanel, RecommendedArticle } from "../types";

function RecommendationList({ title, articles }: { title: "GAME" | "AI"; articles: RecommendedArticle[] }) {
  return <div className="ib-recommend-column">
    <h3>{title}</h3>
    <ol>
      {articles.map((article) => <li key={`${article.url}-${article.title}`}>
        <a href={article.url} target="_blank" rel="noreferrer" title={article.title}>{article.title}</a>
        <time>{article.publishedDate}</time>
      </li>)}
    </ol>
  </div>;
}

export function CrossInsightPanel({
  insight, game, ai, recommendations = [],
}: { insight: CrossInsight; game: IndustryPanel; ai: IndustryPanel; recommendations?: RecommendedArticle[] }) {
  const mainIssue = insight.hasSignal ? insight.summary[0] : `${game.headline}와 ${ai.headline}`;
  const opinion =
    insight.opinion ||
    "현재는 두 산업을 직접 연결할 만큼 충분한 근거가 없습니다. 각 산업의 개별 변화가 누적되는지 계속 관찰합니다.";
  const gameArticles = recommendations.filter((article) => article.category === "GAME").slice(0, 5);
  const aiArticles = recommendations.filter((article) => article.category === "AI").slice(0, 5);

  return <>
    <section className="card ib-cross ib-cross-brief">
    <div className="ib-cross-brief-head"><span>GAME × AI</span><small>교차 인사이트</small></div>
    <div className="ib-cross-brief-grid"><div><em>주요 이슈</em><strong>{mainIssue}</strong></div><div><em>AI 의견</em><p>{opinion}</p></div></div>
    </section>
    {(gameArticles.length > 0 || aiArticles.length > 0) && <section className="card ib-recommendations-card">
      <div className="ib-recommend-head"><strong>추천 기사</strong><span>제목을 클릭하면 원문으로 이동합니다.</span></div>
      <div className="ib-recommend-grid">
        <RecommendationList title="GAME" articles={gameArticles} />
        <RecommendationList title="AI" articles={aiArticles} />
      </div>
    </section>}
  </>;
}


