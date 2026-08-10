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
