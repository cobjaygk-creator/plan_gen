import type { CategoryStat, SourceStat } from "../types";

interface SourceCategoryPanelProps {
  sources: SourceStat[];
  categories: CategoryStat[];
}

export function SourceCategoryPanel({ sources, categories }: SourceCategoryPanelProps) {
  const maxCategoryCount = Math.max(1, ...categories.map((c) => c.count));
  return (
    <div className="sc-columns">
      <section className="sc-panel">
        <span className="sc-eyebrow">커뮤니티별 반응</span>
        <h2>출처별 민심 지수</h2>
        <div className="sc-source-grid">
          {sources.map((s) => (
            <article key={s.source}>
              <span>{s.source}</span>
              <strong className="tabular">{s.score}</strong>
              <small className="tabular">{s.count}건</small>
            </article>
          ))}
        </div>
      </section>
      <section className="sc-panel">
        <span className="sc-eyebrow">주제별 언급</span>
        <h2>카테고리 분포</h2>
        <div className="sc-category-list">
          {categories.map((c) => (
            <div key={c.name} className="sc-category-row">
              <span>{c.name}</span>
              <div className="sc-category-track">
                <i style={{ width: `${(c.count / maxCategoryCount) * 100}%` }} />
              </div>
              <b className="tabular">{c.count}</b>
            </div>
          ))}
          {categories.length === 0 && <p className="sc-empty">표시할 데이터가 없습니다.</p>}
        </div>
      </section>
    </div>
  );
}
