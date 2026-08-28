import type { IssueCard as IssueCardType } from "../types";
import { IssueCard } from "./IssueCard";

interface Props {
  issues: IssueCardType[];
  /** TODAY page passes a short preview + this to jump to the full 이슈 screen;
   * the dedicated 이슈 screen omits it and shows every issue. */
  limit?: number;
  onViewAll?: () => void;
}

export function ImportantIssuesPanel({ issues, limit, onViewAll }: Props) {
  const visible = limit ? issues.slice(0, limit) : issues;
  return (
    <div className="card ib-issues">
      <div className="ib-issues-head">
        <h2>Important Issues</h2>
        {onViewAll && issues.length > visible.length && (
          <button type="button" className="ib-issues-viewall" onClick={onViewAll}>이슈 전체 보기 ({issues.length})</button>
        )}
      </div>
      {issues.length === 0 ? (
        <div className="ib-empty-panel">오늘 강조할 만큼 근거가 쌓인 이슈가 없습니다.</div>
      ) : (
        <div className="ib-issue-list">
          {visible.map((issue) => (
            <IssueCard issue={issue} key={issue.id} />
          ))}
        </div>
      )}
    </div>
  );
}
