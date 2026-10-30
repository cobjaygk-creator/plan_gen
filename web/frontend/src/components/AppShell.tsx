import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ADMIN_EMAIL } from "../auth/adminEmail";
import "./AppShell.css";

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
function HistoryIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </svg>
  );
}
function TrendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 17 9 11 13 15 21 6" />
      <polyline points="15 6 21 6 21 12" />
    </svg>
  );
}
function CalendarIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  );
}
function GlobeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.5 4 5.7 4 9s-1.5 6.5-4 9c-2.5-2.5-4-5.7-4-9s1.5-6.5 4-9Z" />
    </svg>
  );
}
function LayoutIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M9 9v12" />
    </svg>
  );
}
function DatabaseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </svg>
  );
}
function ChevronDown() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function navClass({ isActive }: { isActive: boolean }) {
  return "lnb-item" + (isActive ? " active" : "");
}

export function AppShell() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const isAdmin = user?.email === ADMIN_EMAIL;

  return (
    <div className="app-shell">
      <div className="gnb">
        <div className="gnb-left">
          <div className="brand-mark">
            <div className="brand-name">UX Insight</div>
          </div>
        </div>
        <div className="gnb-right">
          {/* 로그인 없이 보는 게 기본 화면이라 로그인 버튼은 두지 않지만,
              어떤 계정으로든 로그인된 상태라면 로그아웃할 수 있어야 한다. */}
          {user && (
            <div className="user-menu">
              <button
                type="button"
                className="user-chip"
                onClick={() => setMenuOpen((v) => !v)}
                aria-expanded={menuOpen}
              >
                <span className="avatar">{user?.name?.[0] ?? "?"}</span>
                <span className="name">{user?.name}</span>
                <ChevronDown />
              </button>
              {menuOpen && (
                <div className="user-menu-popover">
                  <button type="button" onClick={() => logout()}>
                    로그아웃
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="app-body">
        <div className="lnb">
          <div className="lnb-group-label">메뉴</div>
          <NavLink to="/" end className={navClass}>
            <span className="ic">
              <TrendIcon />
            </span>
            업계 동향
          </NavLink>
          <NavLink to="/event-bench" className={navClass}>
            <span className="ic">
              <CalendarIcon />
            </span>
            타사 이벤트
          </NavLink>
          <NavLink to="/game-sites" className={navClass}>
            <span className="ic">
              <GlobeIcon />
            </span>
            {"타사 사이트"}
          </NavLink>
          <NavLink to="/quick-prototype" className={navClass}>
            <span className="ic">
              <LayoutIcon />
            </span>
            퀵 프로토타입
          </NavLink>
          {isAdmin && (
            <>
              <NavLink to="/generate" className={navClass}>
                <span className="ic">
                  <PlusIcon />
                </span>
                기획서 생성
              </NavLink>
              <NavLink to="/history" className={navClass}>
                <span className="ic">
                  <HistoryIcon />
                </span>
                생성 이력
              </NavLink>
              <NavLink to="/wireframe" className={navClass}>
                <span className="ic">
                  <LayoutIcon />
                </span>
                퀵 프로토타입(J)
              </NavLink>
              <NavLink to="/collection-history" className={navClass}>
                <span className="ic">
                  <DatabaseIcon />
                </span>
                수집 이력
              </NavLink>
            </>
          )}
        </div>
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
