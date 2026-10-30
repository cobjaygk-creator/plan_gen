export interface User {
  id: number;
  email: string;
  name: string;
  created_at: string;
}

export type GenerationStatus = "pending" | "running" | "done" | "error" | "needs_review";

export interface Generation {
  id: number;
  month: string;
  source_filename: string;
  status: GenerationStatus;
  current_step: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface WireframeGeneration {
  id: number;
  source_filename: string;
  page_id: string;
  page_title: string | null;
  status: "queued" | "running" | "done" | "error";
  model: string | null;
  cost_usd: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  has_edits: boolean;
  edited_at: string | null;
}

export interface ProgressEvent {
  status: GenerationStatus;
  step: number;
  error_message: string | null;
}

export interface AccessLog {
  id: number;
  email: string;
  ip_address: string;
  occurred_at: string;
}

export interface SiteVisit {
  id: number;
  ip_address: string;
  path: string;
  occurred_at: string;
}
