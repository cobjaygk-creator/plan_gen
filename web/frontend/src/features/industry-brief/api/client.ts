import type { IndustryBrief, LandscapeIssueDetail } from "../types";

/** Backed by the real `GET /industry-brief/latest` endpoint now. A 404
 * (no brief synthesized yet) is surfaced as a thrown error, same as any
 * other failure — IndustryBriefView already renders a dedicated "아직
 * 생성된 Industry Brief가 없습니다" state for that case, so there's no
 * need to silently fall back to Phase 1's mock data here. */
export async function fetchLatestBrief(): Promise<IndustryBrief> {
  const res = await fetch("/industry-brief/latest", { credentials: "include" });
  if (!res.ok) {
    let detail = `요청이 실패했습니다 (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON — keep the generic message
    }
    throw new Error(detail);
  }
  return res.json() as Promise<IndustryBrief>;
}

export async function fetchLandscapeIssueDetail(issueKey: string): Promise<LandscapeIssueDetail> {
  const res = await fetch(`/industry-brief/landscape/${encodeURIComponent(issueKey)}/articles`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("이슈 근거 기사를 불러오지 못했습니다.");
  return res.json() as Promise<LandscapeIssueDetail>;
}
export async function refreshIndustryBrief(): Promise<IndustryBrief> {
  const res = await fetch("/industry-brief/refresh", { method: "POST", credentials: "include" });
  if (!res.ok) {
    let detail = `업데이트에 실패했습니다 (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON — keep the generic message
    }
    throw new Error(detail);
  }
  const body = await res.json() as { brief: IndustryBrief };
  return body.brief;
}
export interface HighlightArticle {
  title: string;
  url: string;
  source: string;
}

export interface HighlightIssue {
  title: string;
  summary: string;
  articles: HighlightArticle[];
}

export interface RecommendedArticle {
  title: string;
  url: string;
  source: string;
  reason: string;
}

export interface CategoryHighlights {
  category: "GAME" | "AI";
  hasSignal: boolean;
  articleCount: number;
  generatedAt: string;
  coreIssues: HighlightIssue[];
  recommended: RecommendedArticle[];
}

export interface DailyHighlightsResponse {
  game: CategoryHighlights;
  ai: CategoryHighlights;
}

export async function fetchDailyHighlights(): Promise<DailyHighlightsResponse> {
  const res = await fetch("/industry-brief/highlights", { credentials: "include" });
  if (!res.ok) throw new Error("오늘의 핵심 이슈를 불러오지 못했습니다.");
  return res.json() as Promise<DailyHighlightsResponse>;
}

export async function refreshDailyHighlights(): Promise<DailyHighlightsResponse> {
  const res = await fetch("/industry-brief/highlights/refresh", { method: "POST", credentials: "include" });
  if (!res.ok) {
    let detail = `업데이트에 실패했습니다 (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON — keep the generic message
    }
    throw new Error(detail);
  }
  return res.json() as Promise<DailyHighlightsResponse>;
}

export type BriefPeriod = "today" | "3d" | "week";

export async function fetchPeriodBrief(period: BriefPeriod): Promise<IndustryBrief> {
  // Period tabs read already stored articles; collection and AI run only through refresh.
  const res = await fetch(`/industry-brief/period/${period}`, { method: "POST", credentials: "include" });
  if (!res.ok) throw new Error("기간별 동향을 생성하지 못했습니다.");
  return res.json() as Promise<IndustryBrief>;
}

export type CoreFeedbackReason = "PROMOTIONAL" | "LOW_IMPORTANCE" | "DUPLICATE" | "LOW_IMPACT" | "OTHER";

export async function submitIssueFeedback(issueId: number, verdict: "NOT_CORE", reason: CoreFeedbackReason): Promise<void> {
  const res = await fetch(`/industry-brief/issues/${issueId}/feedback`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ verdict, reason }),
  });
  if (!res.ok) throw new Error("피드백을 저장하지 못했습니다.");
}

export interface CoreFeedbackItem {
  issueId: number;
  title: string;
  category: "GAME" | "AI";
  feedbackCount: number;
  createdAt: string;
  reasonCounts: Partial<Record<CoreFeedbackReason, number>>;
}

export async function fetchCoreFeedbacks(): Promise<CoreFeedbackItem[]> {
  const res = await fetch("/industry-brief/feedback", { credentials: "include" });
  if (!res.ok) throw new Error("편집 기준을 불러오지 못했습니다.");
  return res.json() as Promise<CoreFeedbackItem[]>;
}

export async function clearIssueFeedback(issueId: number): Promise<void> {
  const res = await fetch(`/industry-brief/issues/${issueId}/feedback`, {
    method: "DELETE", credentials: "include",
  });
  if (!res.ok) throw new Error("피드백을 취소하지 못했습니다.");
}

export interface EditorialRuleSuggestion {
  reason: CoreFeedbackReason;
  pattern: string;
  issueCount: number;
  examples: string[];
}
export interface ActiveEditorialRule {
  id: number;
  pattern: string;
  reason: CoreFeedbackReason;
  createdAt: string;
  impact: EditorialRulePreview;
}
export interface EditorialRuleHistory {
  id: number;
  ruleId: number;
  action: "APPROVED" | "REACTIVATED" | "DEACTIVATED";
  actorName: string;
  actorEmail: string;
  pattern: string;
  reason: CoreFeedbackReason;
  issueCount: number;
  articleCount: number;
  coreCandidateCount: number;
  riskLevel: "SAFE" | "CAUTION";
  createdAt: string;
}
export interface EditorialRulePreview {
  pattern: string;
  reason: CoreFeedbackReason;
  issueCount: number;
  articleCount: number;
  coreCandidateCount: number;
  riskLevel: "SAFE" | "CAUTION";
  warnings: string[];
  issues: Array<{ issueId: number; category: "GAME" | "AI"; title: string; articleCount: number; coreCandidate: boolean; sources: string[] }>;
}
export async function fetchEditorialRules(): Promise<{ suggestions: EditorialRuleSuggestion[]; activeRules: ActiveEditorialRule[]; history: EditorialRuleHistory[] }> {
  const res = await fetch("/industry-brief/feedback/rules", { credentials: "include" });
  if (!res.ok) throw new Error("편집 규칙을 불러오지 못했습니다.");
  return res.json();
}
export async function approveEditorialRule(pattern: string, reason: CoreFeedbackReason, confirmBroadImpact = false): Promise<void> {
  const res = await fetch("/industry-brief/feedback/rules", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pattern, reason, confirmBroadImpact }) });
  if (!res.ok) throw new Error("편집 규칙을 승인하지 못했습니다.");
}
export async function deactivateEditorialRule(ruleId: number): Promise<void> {
  const res = await fetch(`/industry-brief/feedback/rules/${ruleId}`, { method: "DELETE", credentials: "include" });
  if (!res.ok) throw new Error("편집 규칙을 해제하지 못했습니다.");
}
export async function previewEditorialRule(pattern: string, reason: CoreFeedbackReason): Promise<EditorialRulePreview> {
  const res = await fetch("/industry-brief/feedback/rules/preview", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pattern, reason }) });
  if (!res.ok) throw new Error("규칙 영향을 확인하지 못했습니다.");
  return res.json();
}
