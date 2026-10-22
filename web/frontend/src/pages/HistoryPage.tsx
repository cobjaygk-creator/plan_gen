import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Generation, GenerationStatus, WireframeGeneration } from "../api/types";
import "./HistoryPage.css";

const STATUS_LABEL: Record<GenerationStatus, string> = {
  pending: "대기 중",
  running: "생성 중",
  done: "완료",
  error: "오류",
  needs_review: "검토 필요",
};

const STATUS_CLASS: Record<GenerationStatus, string> = {
  pending: "neutral",
  running: "neutral",
  done: "ok",
  error: "err",
  needs_review: "warn",
};

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatMonth(month: string): string {
  const m = /^(\d{4})(\d{2})$/.exec(month);
  return m ? `${m[1]}년 ${m[2]}월` : month;
}

export function HistoryPage() {
  const [items, setItems] = useState<Generation[] | null>(null);
  const [wireframes, setWireframes] = useState<WireframeGeneration[] | null>(null);
  const [activeTab, setActiveTab] = useState<"documents" | "wireframes">("documents");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.listGenerations().then(setItems);
    api.listWireframeHistory().then(setWireframes);
  }, []);

  const filtered = (items ?? []).filter((g) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return g.source_filename.toLowerCase().includes(q) || formatMonth(g.month).includes(q);
  });

  return (
    <>
      <div className="page-head">
        <h1>생성 이력</h1>
        <p>과거에 생성한 SB 문서를 확인하고 다시 내려받을 수 있습니다.</p>
      </div>
      <div className="history-tabs" role="tablist" aria-label="생성 이력 종류">
        <button type="button" role="tab" aria-selected={activeTab === "documents"} className={activeTab === "documents" ? "active" : ""} onClick={() => setActiveTab("documents")}>기획서 생성 이력 <span>{items?.length ?? 0}</span></button>
        <button type="button" role="tab" aria-selected={activeTab === "wireframes"} className={activeTab === "wireframes" ? "active" : ""} onClick={() => setActiveTab("wireframes")}>와이어프레임 생성 이력 <span>{wireframes?.length ?? 0}</span></button>
      </div>
      {activeTab === "documents" && <div className="card table-card">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: "1px solid var(--border)", gap: 12, flexWrap: "wrap" }}>
          <input
            className="field-search"
            placeholder="파일명 또는 월 검색"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ fontFamily: "inherit", fontSize: 13, padding: "8px 12px", border: "1px solid var(--border-strong)", borderRadius: 6, background: "var(--surface)", color: "var(--ink)", width: 220, outline: "none" }}
          />
          <span className="eyebrow">전체 {items?.length ?? 0}건</span>
        </div>

        {items === null ? (
          <div className="empty-history">불러오는 중...</div>
        ) : filtered.length === 0 ? (
          <div className="empty-history">
            {items.length === 0 ? (
              <>
                아직 생성한 문서가 없습니다. <Link to="/generate">기획서 생성</Link>에서 시작해보세요.
              </>
            ) : (
              "검색 결과가 없습니다."
            )}
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>파일</th>
                <th>월</th>
                <th>생성 일시</th>
                <th>상태</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((g) => (
                <tr key={g.id}>
                  <td>
                    <div className="fname-cell">
                      <span className="ic">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <path d="M14 2v6h6" />
                        </svg>
                      </span>
                      <div>
                        <div className="txt">{g.source_filename}</div>
                        {g.error_message && <div className="sub">{g.error_message}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="tabular">{formatMonth(g.month)}</td>
                  <td className="tabular">{formatDateTime(g.created_at)}</td>
                  <td>
                    <span className={`pill ${STATUS_CLASS[g.status]}`}>
                      <span className="dot" />
                      {STATUS_LABEL[g.status]}
                    </span>
                  </td>
                  <td className="row-actions">
                    {g.status === "done" ? (
                      <a href={api.downloadUrl(g.id)}>다운로드</a>
                    ) : (
                      <span style={{ color: "var(--ink-faint)", cursor: "default" }}>다운로드</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>}
      {activeTab === "wireframes" && <div className="card table-card">
        {wireframes === null ? <div className="empty-history">불러오는 중...</div> : wireframes.length === 0 ? <div className="empty-history">아직 생성한 와이어프레임이 없습니다. <Link to="/wireframe">와이어프레임 생성</Link>에서 시작해보세요.</div> : (
          <table><thead><tr><th>원본 파일</th><th>화면</th><th>생성 일시</th><th>상태</th><th>모델</th><th>비용</th><th></th></tr></thead><tbody>
            {wireframes.map((item) => <tr key={item.id}><td>{item.source_filename}</td><td>{item.page_title || item.page_id}</td><td className="tabular">{formatDateTime(item.created_at)}</td><td><span className={`pill ${item.status === "done" ? "ok" : item.status === "error" ? "err" : "neutral"}`}><span className="dot" />{item.status === "done" ? "완료" : item.status === "error" ? "오류" : item.status === "running" ? "생성 중" : "대기 중"}</span></td><td>{item.model || "-"}</td><td>{item.cost_usd == null ? "-" : `$${item.cost_usd.toFixed(4)}`}</td><td>{item.status === "done" ? <a href={api.wireframeDownloadUrl(item.id)}>HTML 다운로드</a> : <span style={{color:"var(--ink-faint)"}}>다운로드</span>}</td></tr>)}
          </tbody></table>
        )}
      </div>}
    </>
  );
}
