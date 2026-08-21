import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { GeneratePage } from "./pages/GeneratePage";
import { HistoryPage } from "./pages/HistoryPage";
import { EventBenchPage } from "./features/event-bench/EventBenchPage";
import { PreRegistrationPage } from "./features/preregistration/PreRegistrationPage";
import { GameSitesPage } from "./features/game-sites/GameSitesPage";
import { SentimentCheckerPage } from "./features/sentiment-checker/SentimentCheckerPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<DashboardPage />} />
              <Route path="event-bench" element={<EventBenchPage />} />
              <Route path="preregistrations" element={<PreRegistrationPage />} />
              <Route path="game-sites" element={<GameSitesPage />} />
              <Route path="generate" element={<GeneratePage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="sentiment-checker" element={<SentimentCheckerPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
