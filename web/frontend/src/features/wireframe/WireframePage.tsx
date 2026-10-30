import { useEffect, useRef, useState, type DragEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { ProgressBar } from "./components/ProgressBar";
import { buildDoc } from "./editor/buildDoc";
import { PrototypeEditor } from "./editor/PrototypeEditor";
import type { JobProgress, JobStage, WireframePageInfo, WireframeResult, WireframeSettings } from "./types";
import "./wireframe.css";

const VIEWPORTS = [1920, 1620, 1440, 1280, 1024, 768, 390];
const POLL_INTERVAL_MS = 2000;
const COST_HINT = "화이트·그레이 테마 · 실제 해상도 · 설명의 인터랙션 구현 · 페이지당 약 150원 (문서 첫 생성은 테마 약 80원 추가)";

const STAGE_LABEL: Record<JobStage, string> = {
  queued: "생성 준비 중",
  theme: "디자인 테마 만드는 중",
  page: "화면 HTML 만드는 중",
  saving: "결과 저장 중",
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatKrw(usd: number): string {
  return `약 ${Math.max(1, Math.round(usd * 1400))}원`;
}

function downloadHtml(result: WireframeResult) {
  const url = URL.createObjectURL(new Blob([result.html], { type: "text/html;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${result.pageId}.html`;
  link.click();
  URL.revokeObjectURL(url);
}

export function WireframePage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [pages, setPages] = useState<WireframePageInfo[] | null>(null);
  const [results, setResults] = useState<Record<string, WireframeResult>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [instruction, setInstruction] = useState("");
  const [settings, setSettings] = useState<WireframeSettings | null>(null);
  const [progress, setProgress] = useState<Record<string, JobProgress>>({});
  const [batch, setBatch] = useState<{ done: number; total: number } | null>(null);
  const [previewWidth, setPreviewWidth] = useState(1920);
  const [historyIds, setHistoryIds] = useState<Record<string, number>>({});
  const [editedHtml, setEditedHtml] = useState<Record<string, string>>({});
  const [searchParams, setSearchParams] = useSearchParams();
  const [editingId, setEditingId] = useState<number | null>(null);
  const editParam = Number(searchParams.get("edit"));
  const openEditId = editingId ?? (Number.isInteger(editParam) && editParam > 0 ? editParam : null);

  const totalCost = Object.values(results).reduce((sum, r) => sum + r.costUsd, 0);
  const selectedResult = selected ? results[selected] : undefined;
  const anyBusy = Object.values(busy).some(Boolean);

  const hasPreview = Boolean(selectedResult);
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const fit = () => setScale(Math.min(1, stage.clientWidth / previewWidth));
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [hasPreview, previewWidth]);

  function pickFile(next: File | null) {
    setError(null);
    if (next && !next.name.toLowerCase().endsWith(".pptx")) {
      setError("pptx 파일만 업로드할 수 있습니다.");
      return;
    }
    setFile(next);
    setPages(null);
    setSettings(null);
    setResults({});
    setErrors({});
    setSelected(null);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files[0] ?? null);
  }

  async function analyze() {
    if (!file) return;
    setAnalyzing(true);
    setError(null);
    try {
      const analysis = await api.analyzeWireframe(file, instruction.trim());
      setPages(analysis.pages);
      setSettings(analysis.settings);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "분석에 실패했습니다.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function generate(pageId: string) {
    if (!file) return;
    setBusy((prev) => ({ ...prev, [pageId]: true }));
    setErrors((prev) => ({ ...prev, [pageId]: "" }));
    setProgress((prev) => ({ ...prev, [pageId]: { stage: "queued", progress: 1, elapsedSec: 0 } }));
    try {
      const { jobId, historyId } = await api.generateWireframe(file, pageId, instruction.trim());
      for (;;) {
        await sleep(POLL_INTERVAL_MS);
        const job = await api.getWireframeJob(jobId);
        if (job.status === "error") throw new ApiError(500, job.error ?? "생성에 실패했습니다.");
        setProgress((prev) => ({ ...prev, [pageId]: { stage: job.stage, progress: job.progress, elapsedSec: job.elapsedSec } }));
        if (job.status === "done" && job.result) {
          setResults((prev) => ({ ...prev, [pageId]: job.result as WireframeResult }));
          setHistoryIds((prev) => ({ ...prev, [pageId]: historyId }));
          setEditedHtml((prev) => {
            const { [pageId]: _stale, ...rest } = prev;
            return rest;
          });
          setSelected(pageId);
          break;
        }
      }
    } catch (e) {
      setErrors((prev) => ({ ...prev, [pageId]: e instanceof ApiError ? e.message : "생성에 실패했습니다." }));
    } finally {
      setBusy((prev) => ({ ...prev, [pageId]: false }));
      setProgress((prev) => {
        const { [pageId]: _finished, ...rest } = prev;
        return rest;
      });
    }
  }

  async function generateAll() {
    const pending = (pages ?? []).filter((page) => !results[page.pageId]);
    setBatch({ done: 0, total: pending.length });
    for (const [index, page] of pending.entries()) {
      await generate(page.pageId);
      setBatch({ done: index + 1, total: pending.length });
    }
    setBatch(null);
  }

  function closeEditor(saved: import("./types").WireframeRecord | null) {
    if (saved) {
      const doc = buildDoc(saved.html, saved.patches, "view", saved.assets);
      setEditedHtml((prev) => ({ ...prev, [saved.pageId]: doc }));
    }
    setEditingId(null);
    if (searchParams.has("edit")) setSearchParams({}, { replace: true });
  }

  const selectedHistoryId = selected ? historyIds[selected] : undefined;
  const zipIds = Object.values(historyIds);

  return (
    <div className="wf-page-root">
      {openEditId !== null && <PrototypeEditor recordId={openEditId} onClose={closeEditor} />}
      <header className="wf-intro">
        <h1>퀵 프로토타입</h1>
        <p>화면설계서(PPT)를 올리면 화면과 설명을 읽어 인터랙션까지 갖춘 페이지 단위 HTML 프로토타입을 만듭니다. SB 앞쪽에 설정 장표(화면 범위·레이아웃·시각 기준·생성 지시사항)를 넣으면 함께 읽어 반영합니다.</p>
      </header>

      <div
        className={"wf-drop" + (dragging ? " dragging" : "")}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pptx"
          hidden
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        />
        {file ? <strong>{file.name}</strong> : <span>PPTX 파일을 끌어놓거나 클릭해서 선택</span>}
      </div>

      <p className="wf-hint">{COST_HINT}</p>

      <label className="wf-instruction-label" htmlFor="wf-instruction">자연어 지시사항 <span>선택</span></label>
      <textarea id="wf-instruction" className="wf-instruction" value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="예: 상단 메뉴는 고정하고, 3열 카드 영역은 한 화면에 모두 보이게 구성해 주세요. 설계서에서 누락된 버튼은 넣지 마세요." rows={3} />
      <p className="wf-instruction-help">인식이 부족한 부분, 우선순위, 화면 구성 의도를 자연어로 적어 주세요. 아래에서 생성할 화면을 선택하면 이 지시사항이 함께 전달됩니다.</p>

      <div className="wf-actions">
        <button type="button" className="btn btn-primary" disabled={!file || analyzing} onClick={analyze}>
          {analyzing ? "분석 중…" : "화면 분석"}
        </button>
        {pages && pages.length > 1 && (
          <button type="button" className="btn btn-ghost" disabled={anyBusy} onClick={generateAll}>
            남은 페이지 모두 생성
          </button>
        )}
        {batch && (
          <div className="wf-batch">
            <ProgressBar
              value={(batch.done / batch.total) * 100}
              label="전체 생성 진행률"
              caption={`전체 ${batch.done}/${batch.total}개 완료`}
            />
          </div>
        )}
        {totalCost > 0 && <span className="wf-cost">누적 비용 {formatKrw(totalCost)} (${totalCost.toFixed(4)})</span>}
      </div>
      {error && <p className="wf-error">{error}</p>}

      {pages &&
        (settings ? (
          <details className="wf-settings-found">
            <summary>설정 장표 인식됨 · 슬라이드 {settings.slide} — 모든 페이지 생성에 최우선으로 반영됩니다</summary>
            <pre>{settings.text}</pre>
          </details>
        ) : (
          <p className="wf-settings-missing">
            설정 장표를 찾지 못했습니다. SB 앞쪽 6장 이내에 화면 범위·레이아웃·시각 기준·생성 지시사항 장표를 넣으면 반영됩니다.
            없으면 설계서 내용만으로 생성합니다.
          </p>
        ))}

      {pages && (
        <div className="wf-workspace">
          <ul className="wf-list">
            {pages.map((page) => {
              const result = results[page.pageId];
              return (
                <li key={page.pageId} className={"wf-item" + (selected === page.pageId ? " active" : "")}>
                  <button type="button" className="wf-item-main" disabled={!result} onClick={() => setSelected(page.pageId)}>
                    <strong>{page.title || page.pageId}</strong>
                    <span>
                      {page.pageId} · 슬라이드 {page.slides.join(", ")} · 요소 {page.elementCount}개
                    </span>
                    {result && <span className="wf-done">생성됨 · {formatKrw(result.costUsd)}</span>}
                    {errors[page.pageId] && <span className="wf-error">{errors[page.pageId]}</span>}
                  </button>
                  {busy[page.pageId] && progress[page.pageId] && (
                    <ProgressBar
                      value={progress[page.pageId].progress}
                      label={`${page.title || page.pageId} 생성 진행률`}
                      caption={`${STAGE_LABEL[progress[page.pageId].stage]} · ${progress[page.pageId].elapsedSec}초 경과`}
                    />
                  )}
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={busy[page.pageId] || anyBusy}
                    onClick={() => generate(page.pageId)}
                  >
                    {busy[page.pageId] ? "생성 중…" : result ? "다시 생성" : "생성"}
                  </button>
                </li>
              );
            })}
          </ul>

          <section className="wf-preview">
            {selectedResult ? (
              <>
                <div className="wf-preview-bar">
                  <strong>{selectedResult.title || selectedResult.pageId}</strong>
                  <div className="wf-preview-tools">
                    <select aria-label="미리보기 해상도" value={previewWidth} onChange={(e) => setPreviewWidth(Number(e.target.value))}>
                      {VIEWPORTS.map((w) => (
                        <option key={w} value={w}>{w}px</option>
                      ))}
                    </select>
                    {selectedHistoryId !== undefined && (
                      <button type="button" className="btn btn-primary" onClick={() => setEditingId(selectedHistoryId)}>
                        편집
                      </button>
                    )}
                    <button type="button" className="btn btn-ghost" onClick={() => downloadHtml({ ...selectedResult, html: editedHtml[selectedResult.pageId] ?? selectedResult.html })}>
                      HTML 다운로드
                    </button>
                    {zipIds.length > 1 && (
                      <a className="btn btn-ghost" href={api.wireframeZipUrl(zipIds)}>전체 ZIP</a>
                    )}
                  </div>
                </div>
                <div className="wf-stage" ref={stageRef}>
                  <iframe
                    title="퀵 프로토타입 미리보기"
                    sandbox="allow-scripts"
                    srcDoc={editedHtml[selectedResult.pageId] ?? selectedResult.html}
                    style={{
                      width: previewWidth,
                      height: `calc(78vh / ${scale})`,
                      transform: `scale(${scale})`,
                    }}
                  />
                </div>
              </>
            ) : (
              <p className="wf-empty">왼쪽에서 페이지를 생성하면 여기에 미리보기가 표시됩니다.</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
