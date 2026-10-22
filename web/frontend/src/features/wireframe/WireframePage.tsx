import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "../../api/client";
import type { WireframePageInfo, WireframeResult } from "./types";
import "./wireframe.css";

const PREVIEW_WIDTH = 1920;
const POLL_INTERVAL_MS = 2000;
const COST_HINT = "화이트·그레이 테마 · 실제 해상도 · 설명의 인터랙션 구현 · 페이지당 약 150원 (문서 첫 생성은 테마 약 80원 추가)";

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
  const [layout, setLayout] = useState("설계서 기준");
  const [required, setRequired] = useState("");
  const [style, setStyle] = useState("화이트·그레이 업무형");
  const [viewport, setViewport] = useState("데스크톱 1920×1080");
  const [avoid, setAvoid] = useState("");

  function buildInstruction() {
    return [
      `레이아웃: ${layout}`,
      `스타일: ${style}`,
      `기준 해상도: ${viewport}`,
      required.trim() ? `필수 구성 요소: ${required.trim()}` : "",
      avoid.trim() ? `금지 및 제외 사항: ${avoid.trim()}` : "",
      instruction.trim() ? `추가 지시사항: ${instruction.trim()}` : "",
    ].filter(Boolean).join("\n");
  }

  const totalCost = Object.values(results).reduce((sum, r) => sum + r.costUsd, 0);
  const selectedResult = selected ? results[selected] : undefined;
  const anyBusy = Object.values(busy).some(Boolean);

  const hasPreview = Boolean(selectedResult);
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const fit = () => setScale(Math.min(1, stage.clientWidth / PREVIEW_WIDTH));
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [hasPreview]);

  function pickFile(next: File | null) {
    setError(null);
    if (next && !next.name.toLowerCase().endsWith(".pptx")) {
      setError("pptx 파일만 업로드할 수 있습니다.");
      return;
    }
    setFile(next);
    setPages(null);
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
      setPages((await api.analyzeWireframe(file, buildInstruction())).pages);
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
    try {
      const { jobId } = await api.generateWireframe(file, pageId, buildInstruction());
      for (;;) {
        await sleep(POLL_INTERVAL_MS);
        const job = await api.getWireframeJob(jobId);
        if (job.status === "error") throw new ApiError(500, job.error ?? "생성에 실패했습니다.");
        if (job.status === "done" && job.result) {
          setResults((prev) => ({ ...prev, [pageId]: job.result as WireframeResult }));
          setSelected(pageId);
          break;
        }
      }
    } catch (e) {
      setErrors((prev) => ({ ...prev, [pageId]: e instanceof ApiError ? e.message : "생성에 실패했습니다." }));
    } finally {
      setBusy((prev) => ({ ...prev, [pageId]: false }));
    }
  }

  async function generateAll() {
    for (const page of pages ?? []) {
      if (!results[page.pageId]) await generate(page.pageId);
    }
  }

  return (
    <div className="wf-page-root">
      <header className="wf-intro">
        <h1>와이어프레임 생성</h1>
        <p>화면설계서(PPT)를 올리면 화면과 설명을 읽어 페이지 단위 HTML 와이어프레임을 만듭니다.</p>
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

      <div className="wf-settings">
        <div className="wf-settings-title">결과물 품질 설정 <span>선택 입력 · 분석과 생성에 함께 반영</span></div>
        <div className="wf-settings-grid">
          <label>레이아웃
            <select value={layout} onChange={(e) => setLayout(e.target.value)}>
              <option>설계서 기준</option><option>대시보드형</option><option>목록·상세형</option><option>랜딩페이지형</option><option>좌측 사이드바형</option>
            </select>
          </label>
          <label>스타일
            <select value={style} onChange={(e) => setStyle(e.target.value)}>
              <option>화이트·그레이 업무형</option><option>모던 SaaS형</option><option>게임 서비스형</option><option>미니멀 브랜드형</option>
            </select>
          </label>
          <label>기준 해상도
            <select value={viewport} onChange={(e) => setViewport(e.target.value)}>
              <option>데스크톱 1920×1080</option><option>데스크톱 1440×900</option><option>모바일 390×844</option><option>반응형 우선</option>
            </select>
          </label>
          <label>필수 구성 요소
            <input value={required} onChange={(e) => setRequired(e.target.value)} placeholder="예: 검색, 필터, 주요 CTA, 상태 배지" />
          </label>
          <label>금지·제외 사항
            <input value={avoid} onChange={(e) => setAvoid(e.target.value)} placeholder="예: 임의의 메뉴·문구·이미지 추가 금지" />
          </label>
        </div>
      </div>

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
        {totalCost > 0 && <span className="wf-cost">누적 비용 {formatKrw(totalCost)} (${totalCost.toFixed(4)})</span>}
      </div>
      {error && <p className="wf-error">{error}</p>}

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
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={busy[page.pageId] || anyBusy}
                    onClick={() => generate(page.pageId)}
                  >
                    {busy[page.pageId] ? "생성 중… (1~2분)" : result ? "다시 생성" : "생성"}
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
                  <button type="button" className="btn btn-ghost" onClick={() => downloadHtml(selectedResult)}>
                    HTML 다운로드
                  </button>
                </div>
                <div className="wf-stage" ref={stageRef}>
                  <iframe
                    title="와이어프레임 미리보기"
                    sandbox="allow-scripts"
                    srcDoc={selectedResult.html}
                    style={{
                      width: PREVIEW_WIDTH,
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
