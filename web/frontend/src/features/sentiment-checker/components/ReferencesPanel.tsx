import type { ReferenceLink } from "../types";
import { dateText } from "../utils";

export function ReferencesPanel({ references }: { references: ReferenceLink[] }) {
  return (
    <section className="sc-panel">
      <span className="sc-eyebrow">공식 컨텍스트</span>
      <h2>관련 공지·패치</h2>
      <p className="sc-panel-note">게시물과 공지의 시점이 가까운 경우를 연관 가능성으로 표시합니다. 인과관계를 의미하지는 않습니다.</p>
      <div className="sc-reference-list">
        {references.map((r) => (
          <a key={r.url} href={r.url} target="_blank" rel="noreferrer">
            <strong>{r.title}</strong>
            <time>{dateText(r.published_at)}</time>
          </a>
        ))}
        {references.length === 0 && <p className="sc-empty">연관 가능한 공지가 없습니다.</p>}
      </div>
    </section>
  );
}
