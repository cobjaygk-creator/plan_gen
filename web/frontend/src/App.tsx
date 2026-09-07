import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { AdminRoute } from "./components/AdminRoute";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { GeneratePage } from "./pages/GeneratePage";
import { HistoryPage } from "./pages/HistoryPage";
import { EventBenchPage } from "./features/event-bench/EventBenchPage";
import { PreRegistrationPage } from "./features/preregistration/PreRegistrationPage";
import { GameSitesPage } from "./features/game-sites/GameSitesPage";
import { SentimentCheckerPage } from "./features/sentiment-checker/SentimentCheckerPage";

// 업계동향/타사 이벤트/타사 사이트는 로그인 없이 누구나 볼 수 있다 —
// 기획서 생성/생성 이력/민심 체크기, 사전예약 조사만 관리자 계정
// 전용(AdminRoute)으로 남긴다.
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="event-bench" element={<EventBenchPage />} />
            <Route path="game-sites" element={<GameSitesPage />} />
            <Route element={<AdminRoute />}>
              <Route path="preregistrations" element={<PreRegistrationPage />} />
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
