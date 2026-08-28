import type { ConfidenceLevel, Direction, Lifecycle } from "../types";

export const DIRECTION_SYMBOL: Record<Direction, string> = { up: "↑", flat: "→", down: "↓" };
export const DIRECTION_CLASS: Record<Direction, string> = { up: "dir-up", flat: "dir-flat", down: "dir-down" };

export const LIFECYCLE_LABEL: Record<Lifecycle, string> = {
  EMERGING: "EMERGING",
  GROWING: "GROWING ↑",
  PEAK: "PEAK",
  STABLE: "STABLE",
  DECLINING: "DECLINING ↓",
};

export const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  STRONG: "근거 강함",
  MODERATE: "근거 보통",
  WEAK: "근거 약함",
};

export function formatKoreanDateTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())} 기준`;
}

/** "YYYY-MM-DD" for today in KST, independent of the viewer's own timezone —
 * the whole Industry Brief page's day boundaries are KST, so "today" here
 * must match the backend's day_window(), not the browser's local date. */
export function todayKstDateString(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** Shifts a "YYYY-MM-DD" string by whole days (calendar arithmetic done in
 * UTC to sidestep DST — none of the dates involved are DST-affected). */
export function shiftDateString(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

export function formatDateLabel(date: string): string {
  return date.replaceAll("-", ".");
}
