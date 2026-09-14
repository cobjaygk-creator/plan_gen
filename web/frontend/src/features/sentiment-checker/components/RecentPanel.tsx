import type { RecentPost } from "../types";
import { SENTIMENT_LABEL, dateText } from "../utils";

export function RecentPanel({ recent }: { recent: RecentPost[] }) {
  return (
    <section className="sc-panel">
      <span className="sc-eyebrow">근거</span>
      <h2>최근 근거 게시물</h2>
      <div className="sc-recent-list">
        {recent.map((post) => (
          <a href={post.url} target="_blank" rel="noreferrer" key={post.url}>
            <strong>{post.title}</strong>
            <span>
              {post.source} · {post.category}
            </span>
            <em className={`is-${post.sentiment.toLowerCase()}`}>{SENTIMENT_LABEL[post.sentiment]}</em>
            <time>{dateText(post.created_at)}</time>
          </a>
        ))}
        {recent.length === 0 && <p className="sc-empty">표시할 게시물이 없습니다.</p>}
      </div>
    </section>
  );
}
