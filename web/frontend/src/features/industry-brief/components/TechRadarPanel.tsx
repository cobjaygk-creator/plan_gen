import type { TechRadarItem } from "../types";

/** AI 카테고리 내부의 세부 태그 뷰 — 별도 최상위 카테고리가 아니다. 활동이
 * 있는 태그만 서버에서 이미 걸러져 오므로, 여기서는 그대로 그리드로 나열
 * 하기만 한다 (12칸 고정 그리드로 채우지 않는다는 기획 결정). */
export function TechRadarPanel({ items, limit }: { items: TechRadarItem[]; limit?: number }) {
  const visible = limit ? items.slice(0, limit) : items;
  return (
    <div className="card ib-tech-radar">
      <h2>기술 레이더 <span className="ib-tech-radar-sub">AI 카테고리 내 세부 태그 · 최근 활동 있는 것만</span></h2>
      {visible.length === 0 ? (
        <div className="ib-empty-panel">이 기간에는 눈에 띄는 기술 태그가 없습니다.</div>
      ) : (
        <div className="ib-tech-radar-grid">
          {visible.map((item) => (
            <div className="ib-tech-radar-card" key={item.key}>
              <div className="ib-tech-radar-top">
                <span className="ib-tech-radar-label">{item.label}</span>
                <span className="ib-tech-radar-count tabular">{item.articleCount}건</span>
              </div>
              <div className="ib-tech-radar-articles">
                {item.articles.map((article) => (
                  <a key={article.url} href={article.url} target="_blank" rel="noreferrer">
                    <span className="outlet">{article.source.replace(/^NAVER · /, "")}</span>
                    {article.title}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
