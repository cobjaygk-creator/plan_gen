import type { User, Generation, AccessLog, SiteVisit, WireframeGeneration } from "./types";
import type { EditSaveResult, Patch, WireframeAnalysis, WireframeJob, WireframeRecord } from "../features/wireframe/types";
import type { CollectionHistory } from "../features/collection-history/types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const res = await fetch(path, {
    credentials: "include",
    ...options,
    headers: isFormData
      ? options.headers
      : { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });

  if (!res.ok) {
    let detail = `요청이 실패했습니다 (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON — keep the generic message
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),
  getCollectionHistory: () => request<CollectionHistory>("/event-bench/collection-history"),
  listAccessLogs: () => request<AccessLog[]>("/auth/access-logs"),
  listSiteVisits: () => request<SiteVisit[]>("/auth/site-visits"),

  listGenerations: () => request<Generation[]>("/generations"),
  listWireframeHistory: () => request<WireframeGeneration[]>("/wireframe/history"),
  wireframeDownloadUrl: (id: number, version: "original" | "edited" = "original") =>
    `/wireframe/history/${id}/download?version=${version}`,
  wireframeZipUrl: (ids: number[], version: "original" | "edited" = "edited") =>
    `/wireframe/export?ids=${ids.join(",")}&version=${version}`,
  getWireframeRecord: (id: number) => request<WireframeRecord>(`/wireframe/history/${id}`),
  saveWireframeEdits: (id: number, patches: Patch[]) =>
    request<EditSaveResult>(`/wireframe/history/${id}/edits`, { method: "PUT", body: JSON.stringify({ patches }) }),
  getGeneration: (id: number) => request<Generation>(`/generations/${id}`),
  createGeneration: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Generation>("/generations", { method: "POST", body: form });
  },
  analyzeWireframe: (file: File, instruction = "") => {
    const form = new FormData();
    form.append("file", file);
    form.append("instruction", instruction);
    return request<WireframeAnalysis>("/wireframe/analyze", { method: "POST", body: form });
  },
  generateWireframe: (file: File, pageId: string, instruction = "") => {
    const form = new FormData();
    form.append("file", file);
    form.append("page_id", pageId);
    form.append("instruction", instruction);
    return request<{ jobId: string; historyId: number }>("/wireframe/generate", { method: "POST", body: form });
  },
  getWireframeJob: (jobId: string) => request<WireframeJob>(`/wireframe/jobs/${jobId}`),
  downloadUrl: (id: number) => `/generations/${id}/download`,
  streamUrl: (id: number) => `/generations/${id}/stream`,
};
