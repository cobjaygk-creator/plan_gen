import type { NewTodayItem } from "../types";

export function NewTodayPanel({ items }: { items: NewTodayItem[] }) {
  return (
    <div className="card ib-new-today">
      <h2>New Today</h2>
      {items.length === 0 ? (
        <div className="ib-empty-panel">오늘 새롭게 의미 있는 수준으로 등장한 주제가 없습니다.</div>
      ) : (
        <div className="ib-stack">
          {items.map((item) => (
            <div className="ib-new-today-item" key={item.topic}>
              <div className="topic">{item.topic}</div>
              <div className="desc">{item.description}</div>
              <div className="ib-new-today-stats">
                <span>
                  관련 자료 <span className="tabular">{item.articleCount}</span>건
                </span>
                <span>
                  독립 출처 <span className="tabular">{item.independentSources}</span>개
                </span>
                <span>
                  공식 발표 <span className="tabular">{item.officialCount}</span>건
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
