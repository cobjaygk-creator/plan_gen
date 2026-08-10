import type { IndustryBrief } from "../types";

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
