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

export interface ProgressEvent {
  status: GenerationStatus;
  step: number;
  error_message: string | null;
}
