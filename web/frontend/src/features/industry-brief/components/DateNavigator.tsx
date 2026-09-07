import { formatDateLabel, shiftDateString, todayKstDateString } from "../utils/format";

export function DateNavigator({ date, loading, onChange, disabled, label }: {
  date: string; loading: boolean; onChange: (date: string) => void;
  /** 트렌드/정책 탭처럼 날짜 이동이 그 탭 내용에 영향을 못 줄 때 — DOM에서
   * 통째로 빼면 탭 전환마다 헤더 높이가 흔들린다. 자리는 그대로 두고
   * 비활성화 + 반투명 처리만 한다. */
  disabled?: boolean;
  /** 트렌드="최근 30일", 정책="2026년"처럼 탭 맥락에 맞는 라벨로 교체. */
  label?: string;
}) {
  const isToday = date === todayKstDateString();
  return (
    <div className={`ib-date-nav${disabled ? " is-disabled" : ""}`}>
      <button
        type="button"
        className="ib-date-nav-arrow"
        aria-label="이전 날짜"
        disabled={disabled || loading}
        onClick={() => onChange(shiftDateString(date, -1))}
      >
        ‹
      </button>
      <span className="ib-date-nav-label tabular">{label ?? formatDateLabel(date)}</span>
      <button
        type="button"
        className="ib-date-nav-arrow"
        aria-label="다음 날짜"
        disabled={disabled || loading || isToday}
        onClick={() => onChange(shiftDateString(date, 1))}
      >
        ›
      </button>
      {!disabled && !isToday && (
        <button type="button" className="ib-date-nav-today" disabled={loading} onClick={() => onChange(todayKstDateString())}>
          오늘로
        </button>
      )}
    </div>
  );
}
