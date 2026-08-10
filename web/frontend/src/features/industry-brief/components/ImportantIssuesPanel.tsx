import type { IssueCard as IssueCardType } from "../types";
import { IssueCard } from "./IssueCard";

export function ImportantIssuesPanel({ issues }: { issues: IssueCardType[] }) {
  return (
    <div className="card ib-issues">
      <h2>Important Issues</h2>
      {issues.length === 0 ? (
        <div className="ib-empty-panel">오늘 강조할 만큼 근거가 쌓인 이슈가 없습니다.</div>
      ) : (
        <div className="ib-issue-list">
          {issues.map((issue) => (
            <IssueCard issue={issue} key={issue.id} />
          ))}
        </div>
      )}
    </div>
  );
}
