import { formatDateLabel, shiftDateString, todayKstDateString } from "../utils/format";

export function DateNavigator({ date, loading, onChange }: {
  date: string; loading: boolean; onChange: (date: string) => void;
}) {
  const isToday = date === todayKstDateString();
  return (
    <div className="ib-date-nav">
      <button
        type="button"
        className="ib-date-nav-arrow"
        aria-label="이전 날짜"
        disabled={loading}
        onClick={() => onChange(shiftDateString(date, -1))}
      >
        ‹
      </button>
      <span className="ib-date-nav-label tabular">{formatDateLabel(date)}</span>
      <button
        type="button"
        className="ib-date-nav-arrow"
        aria-label="다음 날짜"
        disabled={loading || isToday}
        onClick={() => onChange(shiftDateString(date, 1))}
      >
        ›
      </button>
      {!isToday && (
        <button type="button" className="ib-date-nav-today" disabled={loading} onClick={() => onChange(todayKstDateString())}>
          오늘로
        </button>
      )}
    </div>
  );
}
