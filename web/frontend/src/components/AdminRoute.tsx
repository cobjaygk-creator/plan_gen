import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ADMIN_EMAIL } from "../auth/adminEmail";

/** 기획서 생성/생성 이력/민심 체크기 — 관리자 계정으로 로그인했을 때만
 * 들어갈 수 있다. 비로그인은 물론, 다른 계정으로 로그인한 경우도 막는다
 * (실제 접근 제어는 각 API가 로그인 자체는 그대로 요구하므로 여기서는
 * 화면 진입만 막는다 — AppShell도 같은 기준으로 메뉴 자체를 숨긴다). */
export function AdminRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user || user.email !== ADMIN_EMAIL) return <Navigate to="/" replace />;
  return <Outlet />;
}
