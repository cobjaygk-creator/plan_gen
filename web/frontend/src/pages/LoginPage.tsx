import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import "./LoginPage.css";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "로그인에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="card login-card">
        <div className="brand-mark">
          <div className="brand-glyph">PG</div>
          <div>
            <div className="brand-name">plan gen</div>
            <div className="brand-sub">배틀패스 SB 생성기</div>
          </div>
        </div>
        <h1>로그인</h1>
        <p className="lede">
          요청서를 업로드하고 SB 문서를 생성하려면
          <br />팀 계정으로 로그인하세요.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="li-email">이메일</label>
            <input
              id="li-email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="li-pw">비밀번호</label>
            <input
              id="li-pw"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <div className="error-text">{error}</div>}
          <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={submitting}>
            {submitting ? "로그인 중..." : "로그인"}
          </button>
        </form>
        <div className="login-foot">계정이 없으신가요? 관리자에게 초대를 요청하세요.</div>
      </div>
    </div>
  );
}
