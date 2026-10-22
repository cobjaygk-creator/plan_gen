export interface WireframePageInfo {
  pageId: string;
  title: string;
  slides: number[];
  elementCount: number;
}

export interface WireframeResult {
  pageId: string;
  title: string;
  html: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}

export interface WireframeJob {
  status: "queued" | "running" | "done" | "error";
  result: WireframeResult | null;
  error: string | null;
}
