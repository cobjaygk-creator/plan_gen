import type { Issue } from "../types";
import { SentimentBar } from "./SentimentBar";

interface IssuesPanelProps {
  issues: Issue[];
  onSelect: (key: string) => void;
}

export function IssuesPanel({ issues, onSelect }: IssuesPanelProps) {
  return (
    <section className="sc-panel">
      <span className="sc-eyebrow">주요 이슈</span>
      <h2>지금 가장 많이 언급되는 이슈</h2>
      <div className="sc-issue-list">
        {issues.map((issue, index) => (
          <article
            key={issue.key}
            onClick={() => onSelect(issue.key)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter") onSelect(issue.key);
            }}
          >
            <b className="tabular">{String(index + 1).padStart(2, "0")}</b>
            <div>
              <h3>
                {issue.title}
                <small>{issue.category}</small>
              </h3>
              <p>
                언급 {issue.mentions}건 · 이전 대비 {issue.growth > 0 ? "+" : ""}
                {issue.growth}
              </p>
              {issue.representative[0] && <p className="sc-issue-example">{issue.representative[0].title}</p>}
              <SentimentBar positive={issue.positive} neutral={issue.neutral} negative={issue.negative} />
            </div>
          </article>
        ))}
        {issues.length === 0 && <p className="sc-empty">이 기간에는 두드러진 이슈가 없습니다.</p>}
      </div>
    </section>
  );
}
