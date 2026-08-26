import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { StaticShell } from "./components/StaticShell";
import { EventBenchPage } from "./features/event-bench/EventBenchPage";
import { GameSitesPage } from "./features/game-sites/GameSitesPage";

export function StaticApp() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<StaticShell />}>
          <Route index element={<Navigate to="event-bench" replace />} />
          <Route path="event-bench" element={<EventBenchPage />} />
          <Route path="game-sites" element={<GameSitesPage />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
