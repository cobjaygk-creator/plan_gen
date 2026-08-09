import type { User, Generation } from "./types";

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

  listGenerations: () => request<Generation[]>("/generations"),
  getGeneration: (id: number) => request<Generation>(`/generations/${id}`),
  createGeneration: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Generation>("/generations", { method: "POST", body: form });
  },
  downloadUrl: (id: number) => `/generations/${id}/download`,
  streamUrl: (id: number) => `/generations/${id}/stream`,
};
