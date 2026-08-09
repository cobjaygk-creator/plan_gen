import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
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
function GridIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
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

  return (
    <div className="app-shell">
      <div className="gnb">
        <div className="gnb-left">
          <div className="brand-mark">
            <div className="brand-glyph">PG</div>
            <div className="brand-name">plan gen</div>
          </div>
        </div>
        <div className="gnb-right">
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
        </div>
      </div>
      <div className="app-body">
        <div className="lnb">
          <div className="lnb-group-label">메뉴</div>
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
          <div className="lnb-spacer" />
          <div className="lnb-group-label">보기</div>
          <NavLink to="/" end className={navClass}>
            <span className="ic">
              <GridIcon />
            </span>
            대시보드
          </NavLink>
        </div>
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
