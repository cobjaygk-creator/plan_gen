import { HashRouter, Routes, Route } from "react-router-dom";
import { StaticShell } from "./components/StaticShell";
import { DashboardPage } from "./pages/DashboardPage";
import { EventBenchPage } from "./features/event-bench/EventBenchPage";
import { GameSitesPage } from "./features/game-sites/GameSitesPage";

export function StaticApp() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<StaticShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="event-bench" element={<EventBenchPage />} />
          <Route path="game-sites" element={<GameSitesPage />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
