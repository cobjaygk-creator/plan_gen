import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const u = await api.login(email, password);
    setUser(u);
  }

  async function logout() {
    await api.logout();
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** GitHub Pages 정적 빌드(StaticApp)는 백엔드 로그인이 없어 AuthProvider로
 * 감싸지 않는다 — 그런데도 EventBenchPage/GameSitesPage처럼 동적 앱과
 * 컴포넌트를 공유하는 화면은 관리자 전용 버튼을 숨기려고 로그인 상태를
 * 참조해야 한다. useAuth()는 Provider가 없으면 던지므로, Provider 유무와
 * 무관하게 안전하게 쓸 수 있는 버전이 필요하다 — 정적 빌드에서는 항상
 * null(=비로그인/비관리자)을 반환한다. */
export function useOptionalAuth() {
  return useContext(AuthContext);
}
