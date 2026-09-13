import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AccessLog } from "../api/types";
import "./HistoryPage.css";

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function AccessLogPage() {
  const [items, setItems] = useState<AccessLog[] | null>(null);

  useEffect(() => {
    api.listAccessLogs().then(setItems);
  }, []);

  return (
    <>
      <div className="page-head">
        <h1>접속 통계</h1>
        <p>최근 로그인 접속 시간과 IP를 확인합니다.</p>
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
                <th>이메일</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {items.map((log) => (
                <tr key={log.id}>
                  <td className="tabular">{formatDateTime(log.occurred_at)}</td>
                  <td>{log.email}</td>
                  <td className="tabular">{log.ip_address}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
