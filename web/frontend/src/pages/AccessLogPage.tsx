import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { SiteVisit } from "../api/types";
import "./HistoryPage.css";

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// 이 시스템은 가입/로그인 없이 이용된다(업계동향/타사 이벤트/타사 사이트는
// 공개 열람) — 그래서 실제 접속 통계는 로그인 기록이 아니라, 새 탭/
// 새로고침/직접 URL 접근마다 서버가 남기는 SiteVisit(IP·시간·경로)이다.
export function AccessLogPage() {
  const [items, setItems] = useState<SiteVisit[] | null>(null);

  useEffect(() => {
    api.listSiteVisits().then(setItems);
  }, []);

  return (
    <>
      <div className="page-head">
        <h1>접속 통계</h1>
        <p>최근 접속 시간과 IP를 확인합니다.</p>
      </div>
      <div className="card table-card">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: "1px solid var(--border)" }}>
          <span className="eyebrow">최근 {items?.length ?? 0}건</span>
        </div>

        {items === null ? (
          <div className="empty-history">불러오는 중...</div>
        ) : items.length === 0 ? (
          <div className="empty-history">아직 기록된 접속이 없습니다.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>접속 시간</th>
                <th>IP</th>
                <th>경로</th>
              </tr>
            </thead>
            <tbody>
              {items.map((visit) => (
                <tr key={visit.id}>
                  <td className="tabular">{formatDateTime(visit.occurred_at)}</td>
                  <td className="tabular">{visit.ip_address}</td>
                  <td>{visit.path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
