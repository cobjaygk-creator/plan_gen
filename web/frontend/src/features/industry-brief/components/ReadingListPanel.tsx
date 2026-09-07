import { useState } from "react";
import { fetchCollectedArticles, type CollectedArticlesResponse, type RecommendedArticle } from "../api/client";

const LIMIT = 9;

function ReadingListColumn({
  label, color, category, articles,
}: { label: string; color: string; category: "GAME" | "AI"; articles: RecommendedArticle[] }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [collected, setCollected] = useState<CollectedArticlesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  // 더보기를 처음 누를 때만 불러오고, 이후엔 다시 여는 동안 캐시해둔 걸 쓴다.
  const openModal = async () => {
    setModalOpen(true);
    if (collected) return;
    setLoading(true);
    setError(false);
    try {
      setCollected(await fetchCollectedArticles(category));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ib-reading-list-column">
      <div className="ib-reading-list-column-head">
        <span className="ib-panel-color-bar" aria-hidden="true" style={{ background: color }} />
        <h3>{label}</h3>
      </div>
      {articles.length === 0 ? (
        <p className="ib-chart-empty">오늘은 추천할 기사가 없습니다.</p>
      ) : (
        <>
          <div className="ib-reading-list-items">
            {articles.map((article) => (
              <a key={article.url} href={article.url} target="_blank" rel="noreferrer" className="ib-reading-list-item">
                <span className="outlet">{article.source.replace(/^NAVER · /, "")}</span>
                <span className="title">{article.title}</span>
              </a>
            ))}
          </div>
          <button type="button" className="ib-reading-list-more" onClick={() => void openModal()}>더보기</button>
        </>
      )}
      {modalOpen && (
        <div className="ib-highlight-modal-backdrop" role="presentation" onClick={() => setModalOpen(false)}>
          <section
            className="ib-highlight-modal" role="dialog" aria-modal="true" aria-label={`${label} 수집 기사 전체`}
            onClick={(event) => event.stopPropagation()}
          >
            <button type="button" className="ib-highlight-modal-close" onClick={() => setModalOpen(false)} aria-label="닫기">×</button>
            <p className="ib-highlight-modal-eyebrow">{label}</p>
            <p className="ib-highlight-modal-body">
              {loading ? "불러오는 중…" : error ? "불러오지 못했습니다." : `최근 24시간 수집 기사 ${collected?.articleCount ?? 0}건`}
            </p>
            {!loading && !error && (
              <div className="ib-highlight-modal-articles">
                {(collected?.articles ?? []).map((article) => (
                  <a key={article.url} className="ib-item-source" href={article.url} target="_blank" rel="noreferrer">
                    <span className="outlet">{article.source.replace(/^NAVER · /, "")}</span>
                    <span className="title">{article.title}</span>
                  </a>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

/** "읽어볼 기사" — 업계동향 탭 하단. 게임/AI 각각 9건 고정 추천, 더보기를
 * 누르면 그 9건으로 추려지기 전 최근 24시간 수집분 전체를 팝업으로 본다. */
export function ReadingListPanel({ game, ai }: { game: RecommendedArticle[]; ai: RecommendedArticle[] }) {
  if (game.length === 0 && ai.length === 0) return null;
  return (
    <section className="card ib-reading-list">
      <div className="ib-reading-list-grid">
        <ReadingListColumn label="게임추천기사" color="var(--cat-game)" category="GAME" articles={game.slice(0, LIMIT)} />
        <ReadingListColumn label="AI추천기사" color="var(--cat-ai)" category="AI" articles={ai.slice(0, LIMIT)} />
      </div>
    </section>
  );
}
