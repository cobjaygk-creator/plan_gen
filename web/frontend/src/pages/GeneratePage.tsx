import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "../api/client";
import type { Generation, ProgressEvent } from "../api/types";
import "./GeneratePage.css";

const STEP_DEFS = [
  { step: 1, title: "고정 필드 파싱", detail: "제목 · 기간 · 등급표 · 유의사항 추출" },
  { step: 2, title: "AI 분류 + 이미지 매칭", detail: "특별 보상 구간 분류 (Haiku → Sonnet 에스컬레이션)" },
  { step: 3, title: "레이아웃 계산", detail: "항목 수 기준 카드 크기 · 페이지 배치 계산" },
  { step: 4, title: ".pptx 렌더링", detail: "template.pptx 마커에 콘텐츠 삽입" },
];

function guessMonth(filename: string): string | null {
  const m = /^(\d{4})(\d{2})/.exec(filename);
  return m ? `${m[1]}년 ${m[2]}월` : null;
}

function formatBytes(n: number): string {
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))}KB` : `${(n / 1024 / 1024).toFixed(1)}MB`;
}

function stepBadgeState(step: number, gen: Generation): "done" | "active" | "pending" | "error" {
  if (step <= gen.current_step) return "done";
  const isNext = step === gen.current_step + 1;
  if (isNext && (gen.status === "running" || gen.status === "pending")) return "active";
  if (isNext && gen.status === "error") return "error";
  return "pending";
}

export function GeneratePage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [generation, setGeneration] = useState<Generation | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => eventSourceRef.current?.close();
  }, []);

  function pickFile(f: File | null) {
    setSubmitError(null);
    if (f && !f.name.toLowerCase().endsWith(".xlsx")) {
      setSubmitError("xlsx 파일만 업로드할 수 있습니다.");
      return;
    }
    setFile(f);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files[0] ?? null);
  }

  function subscribeToProgress(id: number) {
    const es = new EventSource(api.streamUrl(id), { withCredentials: true });
    eventSourceRef.current = es;
    es.onmessage = (event) => {
      const payload = JSON.parse(event.data) as ProgressEvent;
      setGeneration((prev) =>
        prev ? { ...prev, status: payload.status, current_step: payload.step, error_message: payload.error_message } : prev,
      );
      if (payload.status === "done" || payload.status === "error" || payload.status === "needs_review") {
        es.close();
      }
    };
    es.onerror = () => es.close();
  }

  async function startGeneration() {
    if (!file) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createGeneration(file);
      setGeneration(created);
      subscribeToProgress(created.id);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "생성을 시작하지 못했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    eventSourceRef.current?.close();
    setGeneration(null);
    setFile(null);
    setSubmitError(null);
  }

  if (generation) {
    const pct = Math.round((generation.current_step / 4) * 100);
    const isTerminal = ["done", "error", "needs_review"].includes(generation.status);
    return (
      <>
        <div className="page-head">
          <h1>기획서 생성 {isTerminal ? "결과" : "중"}</h1>
          <p>
            {generation.source_filename} · {guessMonth(generation.source_filename) ?? generation.month}
          </p>
        </div>
        <div className="card progress-card">
          <div className="progress-head">
            <h2>생성 진행 상태</h2>
            <span className="progress-pct tabular">{generation.current_step} / 4 단계</span>
          </div>
          <p className="progress-sub">
            {isTerminal ? "생성이 종료되었습니다." : "완료까지 잠시만 기다려주세요. 창을 닫지 마세요."}
          </p>
          <div className="bar-track">
            <div
              className={"bar-fill" + (isTerminal ? "" : " animated")}
              style={{ width: `${pct}%`, background: generation.status === "error" ? "var(--danger)" : undefined }}
            />
          </div>
          <div className="steps">
            {STEP_DEFS.map((def) => {
              const state = stepBadgeState(def.step, generation);
              return (
                <div className={`step ${state}`} key={def.step}>
                  <div className="step-badge">
                    {state === "done" ? "✓" : state === "active" ? <span className="spin" /> : state === "error" ? "!" : def.step}
                  </div>
                  <div className="step-label">
                    <div className="step-title">{def.title}</div>
                    <div className="step-detail">{def.detail}</div>
                  </div>
                  <div className="step-time tabular">
                    {state === "done" ? "완료" : state === "active" ? "진행 중" : state === "error" ? "실패" : "대기 중"}
                  </div>
                </div>
              );
            })}
          </div>

          {generation.status === "done" && (
            <div className="result-banner ok">
              <span className="msg">SB 문서 생성이 완료되었습니다.</span>
              <a className="btn btn-primary" href={api.downloadUrl(generation.id)}>
                다운로드
              </a>
            </div>
          )}
          {(generation.status === "error" || generation.status === "needs_review") && (
            <div className="result-banner err">
              <span className="msg">
                {generation.status === "needs_review" ? "AI가 확신 있게 분류하지 못해 사람의 검토가 필요합니다." : "생성 중 오류가 발생했습니다."}
                {generation.error_message ? ` — ${generation.error_message}` : ""}
              </span>
            </div>
          )}
          {isTerminal && (
            <div className="actions-row">
              <button type="button" className="btn btn-ghost" onClick={reset}>
                새로 생성
              </button>
            </div>
          )}
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <h1>기획서 생성</h1>
        <p>배틀패스 요청서(request.xlsx)를 업로드하면 SB 문서를 자동으로 생성합니다.</p>
      </div>
      <div className="card upload-card">
        <div
          className={"dropzone" + (dragging ? " dragging" : "")}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          role="button"
          tabIndex={0}
        >
          <div className="ic">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" style={{ margin: "0 auto", display: "block" }}>
              <path d="M12 3v12" />
              <path d="m7 8 5-5 5 5" />
              <path d="M5 21h14a2 2 0 0 0 2-2v-4" />
              <path d="M5 15v4a2 2 0 0 0 2 2" />
            </svg>
          </div>
          <div className="primary">요청서 파일을 여기로 끌어다 놓으세요</div>
          <div className="secondary">또는 파일 선택 · .xlsx만 지원</div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          />
        </div>

        {file && (
          <div className="file-chip">
            <div className="ic">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
              </svg>
            </div>
            <div className="meta">
              <div className="fname">{file.name}</div>
              <div className="fsub tabular">{formatBytes(file.size)}</div>
            </div>
            <button type="button" className="remove-btn" onClick={() => setFile(null)} aria-label="파일 제거">
              ✕
            </button>
          </div>
        )}

        {submitError && <div className="error-text" style={{ marginTop: 16 }}>{submitError}</div>}

        {file && guessMonth(file.name) && (
          <div className="form-row">
            <label>인식된 월</label>
            <span className="month-pill">{guessMonth(file.name)}</span>
          </div>
        )}

        <div className="actions-row">
          <button type="button" className="btn btn-ghost" onClick={reset} disabled={!file}>
            취소
          </button>
          <button type="button" className="btn btn-primary" onClick={startGeneration} disabled={!file || submitting}>
            {submitting ? "시작하는 중..." : "생성 시작"}
          </button>
        </div>
      </div>
    </>
  );
}
