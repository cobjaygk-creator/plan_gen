export interface WireframePageInfo {
  pageId: string;
  title: string;
  slides: number[];
  elementCount: number;
}

export interface WireframeSettings {
  slide: number;
  text: string;
}

export interface WireframeAnalysis {
  settings: WireframeSettings | null;
  pages: WireframePageInfo[];
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

export type JobStage = "queued" | "theme" | "page" | "saving";

export interface JobProgress {
  stage: JobStage;
  progress: number;
  elapsedSec: number;
}

export interface WireframeJob extends JobProgress {
  status: "queued" | "running" | "done" | "error";
  result: WireframeResult | null;
  error: string | null;
}
