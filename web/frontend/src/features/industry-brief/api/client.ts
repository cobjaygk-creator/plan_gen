import type { IndustryBrief } from "../types";
import { SAMPLE_BRIEF } from "../mock/sample-brief";

/** Phase 1: static mock data, no network call. Phase 2+ swaps this body
 * for `GET /industry-brief/latest` without changing the call site — every
 * component below only depends on this function's return shape. */
export async function fetchLatestBrief(): Promise<IndustryBrief> {
  return SAMPLE_BRIEF;
}
