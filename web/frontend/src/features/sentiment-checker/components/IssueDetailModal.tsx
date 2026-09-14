import type { IssueDetail } from "../types";
import { SENTIMENT_LABEL, dateText } from "../utils";
import { MentionTrendBars } from "./MentionTrendBars";

const STANCE_LABEL: Record<string, string> = { AGREE: "동의", DISAGREE: "반론", NEUTRAL: "중립" };

interface IssueDetailModalProps {
  detail: IssueDetail;
  onClose: () => void;
}

export function IssueDetailModal({ detail, onClose }: IssueDetailModalProps) {
  return (
    <div className="sc-modal-backdrop" onMouseDown={onClose}>
      <section className="sc-modal" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <header>
          <div>
            <span className="sc-eyebrow">
              {detail.category} · {detail.mentions}건 언급
            </span>
            <h2>{detail.title}</h2>
          </div>
          <button onClick={onClose} aria-label="닫기">
            ×
          </button>
        </header>

        <div className="sc-modal-score-row">
          <article className="is-positive">
            <strong className="tabular">{detail.sentiment.positive}%</strong>
            <span>긍정</span>
          </article>
          <article className="is-neutral">
            <strong className="tabular">{detail.sentiment.neutral}%</strong>
            <span>중립</span>
          </article>
          <article className="is-negative">
            <strong className="tabular">{detail.sentiment.negative}%</strong>
            <span>부정</span>
          </article>
        </div>

        {detail.comment_reaction.count > 0 && (
          <section className="sc-comment-reaction">
            <div>
              <span>댓글 반응</span>
              <strong className="tabular">{detail.comment_reaction.count}건</strong>
            </div>
            <div>
              <span>공감·동의</span>
              <strong className="tabular">{detail.comment_reaction.agree}</strong>
            </div>
            <div>
              <span>반론</span>
              <strong className="tabular">{detail.comment_reaction.disagree}</strong>
            </div>
            <div>
              <span>중립</span>
              <strong className="tabular">{detail.comment_reaction.neutral}</strong>
            </div>
          </section>
        )}

        <div className="sc-modal-grid">
          <section>
            <span className="sc-eyebrow">AI 분석 의견</span>
            <h3>분석 의견</h3>
            <p className="sc-modal-opinion">{detail.interpretation}</p>
          </section>
          <section>
            <span className="sc-eyebrow">언급 추이</span>
            <h3>일자별 언급</h3>
            <MentionTrendBars timeline={detail.timeline} />
          </section>
        </div>

        <section className="sc-modal-section">
          <span className="sc-eyebrow">공식 컨텍스트</span>
          <h3>관련 공지·패치</h3>
          {detail.references.length ? (
            <div className="sc-reference-list">
              {detail.references.map((r) => (
                <a href={r.url} target="_blank" rel="noreferrer" key={r.url}>
                  <strong>{r.title}</strong>
                  <time>{dateText(r.published_at)}</time>
                </a>
              ))}
            </div>
          ) : (
            <p className="sc-empty">시간·키워드가 겹치는 공지가 없습니다.</p>
          )}
        </section>

        {detail.comments.length > 0 && (
          <section className="sc-modal-section">
            <span className="sc-eyebrow">댓글 반응</span>
            <h3>실제 댓글 반응</h3>
            <div className="sc-detail-comments">
              {detail.comments.map((c, i) => (
                <article key={`${c.created_at}-${i}`}>
                  <p>{c.content}</p>
                  <span>
                    {dateText(c.created_at)} · {STANCE_LABEL[c.stance]}
                  </span>
                  <em className={`is-${c.sentiment.toLowerCase()}`}>{SENTIMENT_LABEL[c.sentiment]}</em>
                </article>
              ))}
            </div>
          </section>
        )}

        <section className="sc-modal-section">
          <span className="sc-eyebrow">근거</span>
          <h3>근거 게시물</h3>
          <div className="sc-detail-posts">
            {detail.posts.map((p) => (
              <a href={p.url} target="_blank" rel="noreferrer" key={p.url}>
                <div>
                  <strong>{p.title}</strong>
                  <p>{p.excerpt || "본문 요약 없음"}</p>
                  <span>
                    {p.source} · {dateText(p.created_at)}
                  </span>
                </div>
                <em className={`is-${p.sentiment.toLowerCase()}`}>{SENTIMENT_LABEL[p.sentiment]}</em>
              </a>
            ))}
          </div>
        </section>
      </section>
    </div>
  );
}
