import { useEffect } from "react";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { StaticShell } from "./components/StaticShell";

// GitHub Pages 정적 빌드는 CI가 시간마다 스냅샷을 커밋해야만 최신 데이터가
// 반영되고, 그 배포 자체도 GitHub Actions 트리거 지연을 여러 번 겪었다.
// 반면 오라클 서버는 이미 로그인 없이 공개 접속 가능하고 항상 실데이터를
// 보여준다 — 그래서 이 두 경로는 정적 페이지를 직접 렌더링하는 대신 오라클
// 서버의 동일 경로로 즉시 넘겨버린다.
const OCI_ORIGIN = "http://150.230.101.248:8000";

function RedirectToOci({ path }: { path: string }) {
  useEffect(() => {
    window.location.replace(`${OCI_ORIGIN}${path}`);
  }, [path]);
  return null;
}

export function StaticApp() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<StaticShell />}>
          <Route index element={<Navigate to="event-bench" replace />} />
          <Route path="event-bench" element={<RedirectToOci path="/event-bench" />} />
          <Route path="game-sites" element={<RedirectToOci path="/game-sites" />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
