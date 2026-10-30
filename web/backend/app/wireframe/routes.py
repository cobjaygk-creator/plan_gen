from __future__ import annotations

import hashlib
import io
import json
import math
import re
import threading
import time
import uuid
from pathlib import Path
from collections import OrderedDict

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..deps import require_admin
from ..models import User, WireframeEdit, WireframeGeneration
from ..database import SessionLocal, get_db
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .converter import SlideDoc, convert
from .edits import PatchError, build_document, export_zip, load_asset, safe_page_filename, validate_patches
from .generator import Page, group_pages
from .hifi import (
    HIFI_MODEL, deck_context, find_settings_slide, generate_page_hifi, generate_theme,
    related_pages_text, slide_text,
)

router = APIRouter(prefix="/wireframe", tags=["wireframe"])

MAX_PPTX_BYTES = 20 * 1024 * 1024
MAX_JOBS_KEPT = 50
# (입력, 출력) USD / 100만 토큰
INPUT_USD_PER_MTOK, OUTPUT_USD_PER_MTOK = 2.0, 10.0

_jobs: "OrderedDict[str, dict]" = OrderedDict()
_jobs_lock = threading.Lock()
_themes: dict[str, tuple[str, dict]] = {}
_theme_lock = threading.Lock()
_WIRE_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "wireframe_outputs"
_WIRE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# 단계별 진행률 구간(시작%, 끝%), 예상 글자 수, 예상 소요 초 — 실제 생성 로그에서 잡은 대략값
_STAGES = {
    "queued": (0, 5, 1, 2),
    "theme": (5, 30, 10_000, 35),
    "page": (30, 96, 22_000, 85),
    "saving": (96, 99, 1, 2),
}
_PAGE_START_WITHOUT_THEME = 8


def _enter_stage(job: dict, stage: str) -> None:
    job["stage"] = stage
    job["stageStartedAt"] = time.time()
    job["chars"] = 0


def _progress(job: dict) -> int:
    if job["status"] == "done":
        return 100
    stage = job.get("stage", "queued")
    start, end, expected_chars, expected_secs = _STAGES[stage]
    if stage == "page" and not job.get("themeGenerated"):
        start = _PAGE_START_WITHOUT_THEME
    elapsed = time.time() - job.get("stageStartedAt", time.time())
    fraction = min(0.95, max(job.get("chars", 0) / expected_chars, 1 - math.exp(-elapsed / expected_secs)))
    value = max(job.get("progress", 0), round(start + (end - start) * fraction))
    job["progress"] = value
    return value


def _cost(usage: dict) -> float:
    billed_in = usage["input"] + 1.25 * usage.get("cacheWrite", 0) + 0.1 * usage.get("cacheRead", 0)
    return (billed_in * INPUT_USD_PER_MTOK + usage["output"] * OUTPUT_USD_PER_MTOK) / 1e6


def _pages_from_slide_range(docs: list[SlideDoc], sources: list[str]) -> list[Page]:
    """화면ID가 없는 SB용 — 지시문이나 설정 장표의 '슬라이드 7~11' 같은 화면 범위를 쓴다."""
    for source in sources:
        match = re.search(r"(?:슬라이드|slide)\s*(\d+)\s*(?:~|-|–|부터)\s*(\d+)", source, re.IGNORECASE)
        if not match:
            continue
        start, end = sorted((int(match.group(1)), int(match.group(2))))
        selected = [doc for doc in docs if start <= doc.index <= end]
        if selected:
            return [Page(f"SLIDE-RANGE-{start}-{end}", f"슬라이드 {start}~{end}", selected)]
    return []


def _load_deck(file: UploadFile, instruction: str = "") -> tuple[str, list[SlideDoc], list[Page]]:
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "pptx 파일만 업로드할 수 있습니다.")
    data = file.file.read(MAX_PPTX_BYTES + 1)
    if len(data) > MAX_PPTX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "20MB 이하 파일만 업로드할 수 있습니다.")
    try:
        docs = convert(io.BytesIO(data))
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PPT 파일을 읽을 수 없습니다.")
    pages = group_pages(docs)
    if not pages:
        settings = find_settings_slide(docs)
        pages = _pages_from_slide_range(docs, [instruction, slide_text(settings) if settings else ""])
    if not pages:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "화면 설계 슬라이드를 찾지 못했습니다. 화면ID가 있는 슬라이드 또는 ‘슬라이드 7~11’처럼 범위를 입력해 주세요.",
        )
    return hashlib.sha256(data).hexdigest(), docs, pages


def _theme_for(deck_hash: str, context: str, job: dict) -> tuple[str, dict, bool]:
    with _theme_lock:
        cached = _themes.get(deck_hash)
        if cached is not None:
            return cached[0], cached[1], False
        job["themeGenerated"] = True
        _enter_stage(job, "theme")
        css, usage = generate_theme(context, on_text=lambda n: job.update(chars=job.get("chars", 0) + n))
        _themes[deck_hash] = (css, usage)
        return css, usage, True


def _run_job(job_id: str, record_id: int, deck_hash: str, docs: list[SlideDoc], pages: list[Page], page: Page, instruction: str) -> None:
    job = _jobs[job_id]
    job["status"] = "running"
    db = SessionLocal()
    try:
        record = db.get(WireframeGeneration, record_id)
        if record: record.status = "running"; db.commit()
        context = deck_context(docs)
        theme_css, theme_usage, theme_fresh = _theme_for(deck_hash, context, job)
        _enter_stage(job, "page")
        document, usage = generate_page_hifi(
            page, context, theme_css, related_pages_text(pages, page), instruction=instruction,
            on_text=lambda n: job.update(chars=job.get("chars", 0) + n),
        )
        _enter_stage(job, "saving")
        cost = _cost(usage) + (_cost(theme_usage) if theme_fresh else 0.0)
        job["result"] = {
            "pageId": page.page_id,
            "title": page.title,
            "html": document,
            "model": HIFI_MODEL,
            "inputTokens": usage["input"],
            "outputTokens": usage["output"],
            "costUsd": round(cost, 5),
        }
        output_path = _WIRE_OUTPUT_DIR / f"{record_id}_{page.page_id}.html"
        output_path.write_text(document, encoding="utf-8")
        job["status"] = "done"
        if record:
            record.status = "done"; record.model = HIFI_MODEL; record.cost_usd = round(cost, 5); record.output_path = str(output_path); record.completed_at = datetime.now(timezone.utc); db.commit()
    except Exception as error:
        job["error"] = f"AI 생성에 실패했습니다: {error}"
        job["status"] = "error"
        record = db.get(WireframeGeneration, record_id)
        if record: record.status = "error"; record.error_message = str(error)[:2000]; record.completed_at = datetime.now(timezone.utc); db.commit()
    finally:
        db.close()


@router.post("/analyze")
def analyze(file: UploadFile, instruction: str = Form(""), _: User = Depends(require_admin)):
    _, docs, pages = _load_deck(file, instruction)
    settings = find_settings_slide(docs)
    return {
        "settings": {"slide": settings.index, "text": slide_text(settings)} if settings else None,
        "pages": [
            {
                "pageId": page.page_id,
                "title": page.title,
                "slides": [slide.index for slide in page.slides],
                "elementCount": sum(len(slide.items) for slide in page.slides),
            }
            for page in pages
        ]
    }


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
def generate(file: UploadFile, page_id: str = Form(...), instruction: str = Form(""), user: User = Depends(require_admin), db: Session = Depends(get_db)):
    deck_hash, docs, pages = _load_deck(file, instruction)
    page = next((p for p in pages if p.page_id == page_id), None)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "해당 화면ID를 찾을 수 없습니다.")
    job_id = uuid.uuid4().hex
    record = WireframeGeneration(user_id=user.id, source_filename=file.filename or "uploaded.pptx", page_id=page.page_id, page_title=page.title, status="queued")
    db.add(record); db.commit(); db.refresh(record)
    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "stage": "queued", "stageStartedAt": time.time(), "startedAt": time.time(), "chars": 0, "progress": 0}
        while len(_jobs) > MAX_JOBS_KEPT:
            _jobs.popitem(last=False)
    threading.Thread(target=_run_job, args=(job_id, record.id, deck_hash, docs, pages, page, instruction), daemon=True).start()
    return {"jobId": job_id, "historyId": record.id}


def _owned_record(db: Session, history_id: int, user: User) -> WireframeGeneration:
    record = db.get(WireframeGeneration, history_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "퀵 프로토타입 이력을 찾을 수 없습니다.")
    return record


def _read_original(record: WireframeGeneration) -> str:
    if record.status != "done" or not record.output_path or not Path(record.output_path).is_file():
        raise HTTPException(status.HTTP_409_CONFLICT, "완료된 결과 파일이 없습니다.")
    return Path(record.output_path).read_text(encoding="utf-8")


def _load_patches(db: Session, record_id: int) -> tuple[list[dict], datetime | None]:
    edit = db.get(WireframeEdit, record_id)
    if edit is None:
        return [], None
    try:
        return json.loads(edit.patches), edit.updated_at
    except json.JSONDecodeError:
        return [], None


def _attachment(filename: str) -> dict:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/history")
def list_wireframe_history(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(WireframeGeneration, WireframeEdit.updated_at)
        .outerjoin(WireframeEdit, WireframeEdit.record_id == WireframeGeneration.id)
        .where(WireframeGeneration.user_id == user.id)
        .order_by(WireframeGeneration.created_at.desc())
    ).all()
    return [
        {
            "id": record.id, "source_filename": record.source_filename, "page_id": record.page_id,
            "page_title": record.page_title, "status": record.status, "model": record.model,
            "cost_usd": record.cost_usd, "error_message": record.error_message,
            "created_at": record.created_at, "completed_at": record.completed_at,
            "has_edits": edited_at is not None, "edited_at": edited_at,
        }
        for record, edited_at in rows
    ]


@router.get("/history/{history_id}")
def get_wireframe_record(history_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    record = _owned_record(db, history_id, user)
    html = _read_original(record)
    patches, edited_at = _load_patches(db, record.id)
    latest_by_page: dict[str, WireframeGeneration] = {}
    for sibling in db.execute(
        select(WireframeGeneration)
        .where(
            WireframeGeneration.user_id == user.id,
            WireframeGeneration.source_filename == record.source_filename,
            WireframeGeneration.status == "done",
        )
        .order_by(WireframeGeneration.id.desc())
    ).scalars():
        latest_by_page.setdefault(sibling.page_id, sibling)
    return {
        "id": record.id, "pageId": record.page_id, "title": record.page_title, "sourceFilename": record.source_filename,
        "html": html, "patches": patches, "editedAt": edited_at,
        "siblings": [
            {"historyId": item.id, "pageId": item.page_id, "title": item.page_title}
            for item in sorted(latest_by_page.values(), key=lambda item: item.id)
        ],
        "assets": {"runtime": load_asset("qp_runtime.js"), "editor": load_asset("qp_editor.js")},
    }


class EditsIn(BaseModel):
    patches: list[dict]


@router.put("/history/{history_id}/edits")
def save_wireframe_edits(history_id: int, body: EditsIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    record = _owned_record(db, history_id, user)
    if record.status != "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "생성이 끝난 결과만 수정할 수 있습니다.")
    try:
        clean = validate_patches(body.patches)
    except PatchError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))
    edit = db.get(WireframeEdit, record.id)
    if not clean:
        if edit is not None:
            db.delete(edit)
            db.commit()
        return {"saved": True, "count": 0, "editedAt": None}
    payload = json.dumps(clean, ensure_ascii=False)
    if edit is None:
        db.add(WireframeEdit(record_id=record.id, patches=payload))
    else:
        edit.patches = payload
        edit.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"saved": True, "count": len(clean), "editedAt": db.get(WireframeEdit, record.id).updated_at}


@router.get("/history/{history_id}/download")
def download_wireframe(history_id: int, version: str = "original", user: User = Depends(require_admin), db: Session = Depends(get_db)):
    record = _owned_record(db, history_id, user)
    html = _read_original(record)
    filename = f"{safe_page_filename(record.page_id)}.html"
    patches = _load_patches(db, record.id)[0] if version == "edited" else []
    if not patches:
        return FileResponse(record.output_path, media_type="text/html", filename=filename)
    return Response(build_document(html, patches, "view"), media_type="text/html; charset=utf-8", headers=_attachment(filename))


@router.get("/export")
def export_wireframes(ids: str, version: str = "edited", user: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        wanted = [int(part) for part in ids.split(",") if part.strip()][:50]
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ids 형식이 올바르지 않습니다.")
    pages: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for history_id in wanted:
        record = db.get(WireframeGeneration, history_id)
        if record is None or record.user_id != user.id or record.status != "done" or record.page_id in seen:
            continue
        if not record.output_path or not Path(record.output_path).is_file():
            continue
        html = Path(record.output_path).read_text(encoding="utf-8")
        patches = _load_patches(db, record.id)[0] if version == "edited" else []
        pages.append((record.page_id, record.page_title or record.page_id, build_document(html, patches, "view")))
        seen.add(record.page_id)
    if not pages:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "내려받을 완료된 결과가 없습니다.")
    return Response(export_zip(pages), media_type="application/zip", headers=_attachment("quick-prototype.zip"))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, _: User = Depends(require_admin)):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "작업을 찾을 수 없습니다. 다시 생성해 주세요.")
    return {
        "status": job["status"], "stage": job.get("stage", "queued"), "progress": _progress(job),
        "elapsedSec": round(time.time() - job.get("startedAt", time.time())),
        "result": job.get("result"), "error": job.get("error"),
    }
