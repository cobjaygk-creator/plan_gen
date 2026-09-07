import { useState } from "react";
import type { RecommendedArticle } from "../api/client";

const PAGE_SIZE = 10;

function ReadingListColumn({ label, color, articles }: { label: string; color: string; articles: RecommendedArticle[] }) {
  // 백엔드가 최대 20건까지 추천해주므로, 10건씩 두 페이지로 나눠 보여주고
  // "기사 N건" 자리의 새로고침 아이콘으로 다음 10건을 불러온다 — 페이지가
  // 하나뿐이면(추천 후보가 10건 이하) 굳이 누를 게 없으므로 숨긴다.
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(articles.length / PAGE_SIZE));
  const shown = articles.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  return (
    <div className="ib-reading-list-column">
      <div className="ib-reading-list-column-head">
        <span className="ib-panel-color-bar" aria-hidden="true" style={{ background: color }} />
        <h3>{label}</h3>
        {pageCount > 1 && (
          <button
            type="button"
            className="ib-reading-list-refresh"
            aria-label="다른 추천 기사 보기"
            title="다른 추천 기사 보기"
            onClick={() => setPage((current) => (current + 1) % pageCount)}
          >
            ↻
          </button>
        )}
      </div>
      {shown.length === 0 ? (
        <p className="ib-chart-empty">오늘은 추천할 기사가 없습니다.</p>
      ) : (
        <div className="ib-reading-list-items">
          {shown.map((article) => (
            <a key={article.url} href={article.url} target="_blank" rel="noreferrer" className="ib-reading-list-item">
              <span className="outlet">{article.source.replace(/^NAVER · /, "")}</span>
              <span className="title">{article.title}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

/** "읽어볼 기사" — 업계동향 탭 하단(design_handoff 4단계, 이후 사용자
 * 피드백으로 GAME/AI 패널과 같은 카드 헤더 디자인을 쓰는 2열 레이아웃으로
 * 재구성). 게임/AI 각각 최대 20건을 추천받아 10건씩 페이지로 나눠 보여준다. */
export function ReadingListPanel({ game, ai }: { game: RecommendedArticle[]; ai: RecommendedArticle[] }) {
  if (game.length === 0 && ai.length === 0) return null;
  return (
    <section className="card ib-reading-list">
      <div className="ib-reading-list-grid">
        <ReadingListColumn label="게임추천기사" color="var(--cat-game)" articles={game} />
        <ReadingListColumn label="AI추천기사" color="var(--cat-ai)" articles={ai} />
      </div>
    </section>
  );
}
