import { NavLink, Outlet } from "react-router-dom";
import "./AppShell.css";

export function StaticShell() {
  return (
    <div className="app-shell">
      <div className="gnb">
        <div className="gnb-left"><div className="brand-mark"><div className="brand-name">UX Insight</div></div></div>
      </div>
      <div className="app-body">
        <div className="lnb">
          <div className="lnb-group-label">벤치마크</div>
          <NavLink to="/event-bench" end className={({ isActive }) => `lnb-item${isActive ? " active" : ""}`}><span className="ic">□</span>타사 이벤트</NavLink>
          <NavLink to="/game-sites" className={({ isActive }) => `lnb-item${isActive ? " active" : ""}`}><span className="ic">◎</span>타사 사이트</NavLink>
        </div>
        <div className="content"><Outlet /></div>
      </div>
    </div>
  );
}
