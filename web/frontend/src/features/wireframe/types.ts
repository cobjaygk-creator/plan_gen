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

export interface Patch {
  op: "text" | "link" | "style" | "image" | "delete" | "duplicate" | "move" | "insert";
  path: string;
  ref: string;
  node?: number;
  value?: string;
  href?: string;
  target?: string;
  style?: Record<string, string>;
  src?: string;
  dir?: "up" | "down";
  kind?: "text" | "button" | "divider" | "image" | "video";
}

export interface WireframeSibling {
  historyId: number;
  pageId: string;
  title: string | null;
}

export interface WireframeRecord {
  id: number;
  pageId: string;
  title: string | null;
  sourceFilename: string;
  html: string;
  patches: Patch[];
  editedAt: string | null;
  siblings: WireframeSibling[];
  assets: { runtime: string; editor: string };
}

export interface EditSaveResult {
  saved: boolean;
  count: number;
  editedAt: string | null;
}

export interface SelectionInfo {
  path: string;
  ref: string;
  tag: string;
  label: string;
  isBody: boolean;
  textNodes: string[];
  href: string;
  target: string;
  isImg: boolean;
  styles: Record<string, string>;
  rect: { x: number; y: number; w: number; h: number };
  ancestors: { path: string; label: string }[];
  canUp: boolean;
  canDown: boolean;
  canDelete: boolean;
}
