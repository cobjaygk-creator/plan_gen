import type { Sentiment } from "./types";

export const PERIODS = [
  { label: "24시간", hours: 24 },
  { label: "3일", hours: 72 },
  { label: "7일", hours: 168 },
  { label: "30일", hours: 720 },
];

export const SENTIMENT_LABEL: Record<Sentiment, string> = {
  POSITIVE: "긍정",
  NEUTRAL: "중립",
  NEGATIVE: "부정",
};

export const ANALYSIS_BASIS_LABEL: Record<string, string> = {
  SELECTED_PERIOD: "선택 기간",
  RECENT_7_DAYS: "최근 7일 보조 분석",
  ALL_STORED: "누적 보조 분석",
};

export function dateText(value: string | null): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function shortDateText(value: string | null): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ko-KR", { month: "2-digit", day: "2-digit" }).format(new Date(value));
}
