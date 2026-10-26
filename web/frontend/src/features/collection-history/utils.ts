const HOUR_MS = 3_600_000;
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

export type Freshness = "ok" | "warn" | "late" | "none";

export function freshnessOf(iso: string | null, now: number): { level: Freshness; label: string } {
  if (!iso) return { level: "none", label: "기록 없음" };
  const hours = Math.max(0, (now - new Date(iso).getTime()) / HOUR_MS);
  const label =
    hours < 1 ? "방금 전" : hours < 24 ? `${Math.floor(hours)}시간 전` : `${Math.floor(hours / 24)}일 전`;
  if (hours > 48) return { level: "late", label };
  if (hours > 24) return { level: "warn", label };
  return { level: "ok", label };
}

export function recentDates(today: string, count: number): string[] {
  const base = new Date(`${today}T00:00:00Z`);
  return Array.from({ length: count }, (_, i) => {
    const day = new Date(base.getTime() - (count - 1 - i) * 24 * HOUR_MS);
    return day.toISOString().slice(0, 10);
  });
}

export function dayLabel(date: string): string {
  const day = new Date(`${date}T00:00:00Z`);
  return `${date.slice(5, 7)}/${date.slice(8, 10)} (${WEEKDAYS[day.getUTCDay()]})`;
}

export function shortDay(date: string): string {
  return `${Number(date.slice(5, 7))}/${Number(date.slice(8, 10))}`;
}

export function dateTimeText(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  });
}
