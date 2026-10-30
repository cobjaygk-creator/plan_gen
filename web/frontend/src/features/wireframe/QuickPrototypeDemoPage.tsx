import { useEffect, useRef, useState, type DragEvent } from "react";
import { buildDoc } from "./editor/buildDoc";
import { PrototypeEditor } from "./editor/PrototypeEditor";
import runtimeJs from "../../../../backend/app/wireframe/assets/qp_runtime.js?raw";
import editorJs from "../../../../backend/app/wireframe/assets/qp_editor.js?raw";
import type { WireframeRecord } from "./types";
import "./wireframe.css";

const VIEWPORTS = [1920, 1620, 1440, 1280, 1024, 768, 390];
const SAMPLE_URL = `${import.meta.env.BASE_URL}data/quick-prototype-sample.html`;

const EXAMPLE_PAGE = {
  pageId: "DN-SEA-P-0",
  title: "메인페이지 (예시)",
  detail: "슬라이드 1~3 · 요소 24개",
};

// 비용이 드는 실제 생성 대신 미리 만들어 둔 결과를 보여 주는 시연용 메뉴다.
export function QuickPrototypeDemoPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);
  const [html, setHtml] = useState<string | null>(null);
  const [editedHtml, setEditedHtml] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [width, setWidth] = useState(1920);
  const [scale, setScale] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const fit = () => setScale(Math.min(1, stage.clientWidth / width));
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [analyzed, width]);

  function pickFile(next: File | null) {
    setError(null);
    if (next && !next.name.toLowerCase().endsWith(".pptx")) {
      setError("pptx 파일만 올릴 수 있습니다.");
      return;
    }
    setFile(next);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files[0] ?? null);
  }

  async function analyze() {
    setAnalyzing(true);
    setError(null);
    try {
      const res = await fetch(SAMPLE_URL);
      if (!res.ok) throw new Error("sample");
      const text = await res.text();
      await new Promise((resolve) => setTimeout(resolve, 700));
      setHtml(text);
      setEditedHtml(null);
      setAnalyzed(true);
    } catch {
      setError("예시 화면을 불러오지 못했습니다.");
    } finally {
      setAnalyzing(false);
    }
  }

  const record: WireframeRecord | null = html
    ? {
        id: 0,
        pageId: EXAMPLE_PAGE.pageId,
        title: EXAMPLE_PAGE.title,
        sourceFilename: file?.name ?? "예시.pptx",
        html,
        patches: [],
        editedAt: null,
        siblings: [],
        assets: { runtime: runtimeJs, editor: editorJs },
      }
    : null;

  function downloadHtml() {
    if (!html) return;
    const url = URL.createObjectURL(new Blob([editedHtml ?? html], { type: "text/html;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${EXAMPLE_PAGE.pageId}.html`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="wf-page-root">
      {editing && record && (
        <PrototypeEditor
          recordId={0}
          demoRecord={record}
          onClose={(saved) => {
            if (saved) setEditedHtml(buildDoc(saved.html, saved.patches, "view", saved.assets));
            setEditing(false);
          }}
        />
      )}
      <header className="wf-intro">
        <h1>퀵 프로토타입</h1>
        <p>화면설계서(PPT)를 올리면 화면과 설명을 읽어 인터랙션까지 갖춘 페이지 단위 HTML 프로토타입을 만듭니다. 결과 화면은 글자·링크·이미지·동영상을 바로 고칠 수 있습니다.</p>
      </header>

      <p className="wf-settings-missing">
        예시 체험 모드입니다. 실제 생성에는 비용이 발생해, 어떤 파일을 올려도 미리 만들어 둔 예시 화면을 보여 드립니다.
      </p>

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
        <input ref={inputRef} type="file" accept=".pptx" hidden onChange={(e) => pickFile(e.target.files?.[0] ?? null)} />
        {file ? <strong>{file.name}</strong> : <span style={{ color: "var(--danger)", fontWeight: 600 }}>현재 진행중인 기능으로 본 화면은 예시화면 입니다.</span>}
      </div>

      <div className="wf-actions">
        <button type="button" className="btn btn-primary" disabled={analyzing} onClick={analyze}>
          {analyzing ? "분석 중…" : "화면 분석"}
        </button>
      </div>
      {error && <p className="wf-error">{error}</p>}

      {analyzed && record && (
        <div className="wf-workspace">
          <ul className="wf-list">
            <li className="wf-item active">
              <button type="button" className="wf-item-main" disabled>
                <strong>{EXAMPLE_PAGE.title}</strong>
                <span>{EXAMPLE_PAGE.pageId} · {EXAMPLE_PAGE.detail}</span>
                <span className="wf-done">생성됨 · 예시 화면</span>
              </button>
            </li>
          </ul>

          <section className="wf-preview">
            <div className="wf-preview-bar">
              <strong>{EXAMPLE_PAGE.title}</strong>
              <div className="wf-preview-tools">
                <select aria-label="미리보기 해상도" value={width} onChange={(e) => setWidth(Number(e.target.value))}>
                  {VIEWPORTS.map((w) => (
                    <option key={w} value={w}>{w}px</option>
                  ))}
                </select>
                <button type="button" className="btn btn-primary" onClick={() => setEditing(true)}>편집</button>
                <button type="button" className="btn btn-ghost" onClick={downloadHtml}>HTML 다운로드</button>
              </div>
            </div>
            <div className="wf-stage" ref={stageRef}>
              <iframe
                title="퀵 프로토타입 예시 미리보기"
                sandbox="allow-scripts"
                srcDoc={editedHtml ?? html ?? ""}
                style={{ width, height: `calc(78vh / ${scale})`, transform: `scale(${scale})` }}
              />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
