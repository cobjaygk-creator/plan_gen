from __future__ import annotations

import hashlib
import io
import re
import threading
import uuid
from pathlib import Path
from collections import OrderedDict

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ..deps import require_admin
from ..models import User, WireframeGeneration
from ..database import SessionLocal, get_db
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .converter import SlideDoc, convert
from .generator import Page, group_pages
from .hifi import HIFI_MODEL, deck_context, generate_page_hifi, generate_theme, related_pages_text

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


def _cost(usage: dict) -> float:
    billed_in = usage["input"] + 1.25 * usage.get("cacheWrite", 0) + 0.1 * usage.get("cacheRead", 0)
    return (billed_in * INPUT_USD_PER_MTOK + usage["output"] * OUTPUT_USD_PER_MTOK) / 1e6


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
    if not pages and instruction:
        match = re.search(r"(?:슬라이드|slide)\s*(\d+)\s*(?:~|-|–|부터)\s*(\d+)", instruction, re.IGNORECASE)
        if match:
            start, end = sorted((int(match.group(1)), int(match.group(2))))
            selected = [doc for doc in docs if start <= doc.index <= end]
            if selected:
                pages = [Page(f"SLIDE-RANGE-{start}-{end}", f"슬라이드 {start}~{end}", selected)]
    if not pages:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "화면 설계 슬라이드를 찾지 못했습니다. 화면ID가 있는 슬라이드 또는 ‘슬라이드 7~11’처럼 범위를 입력해 주세요.",
        )
    return hashlib.sha256(data).hexdigest(), docs, pages


def _theme_for(deck_hash: str, context: str) -> tuple[str, dict, bool]:
    with _theme_lock:
        cached = _themes.get(deck_hash)
        if cached is not None:
            return cached[0], cached[1], False
        css, usage = generate_theme(context)
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
        theme_css, theme_usage, theme_fresh = _theme_for(deck_hash, context)
        document, usage = generate_page_hifi(page, context, theme_css, related_pages_text(pages, page), instruction=instruction)
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
    _, _, pages = _load_deck(file, instruction)
    return {
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
        _jobs[job_id] = {"status": "queued"}
        while len(_jobs) > MAX_JOBS_KEPT:
            _jobs.popitem(last=False)
    threading.Thread(target=_run_job, args=(job_id, record.id, deck_hash, docs, pages, page, instruction), daemon=True).start()
    return {"jobId": job_id, "historyId": record.id}


@router.get("/history")
def list_wireframe_history(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.execute(select(WireframeGeneration).where(WireframeGeneration.user_id == user.id).order_by(WireframeGeneration.created_at.desc())).scalars().all()


@router.get("/history/{history_id}/download")
def download_wireframe(history_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    record = db.get(WireframeGeneration, history_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "와이어프레임 이력을 찾을 수 없습니다.")
    if record.status != "done" or not record.output_path or not Path(record.output_path).is_file():
        raise HTTPException(status.HTTP_409_CONFLICT, "완료된 결과 파일이 없습니다.")
    safe_name = f"{record.page_id}.html"
    return FileResponse(record.output_path, media_type="text/html", filename=safe_name)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, _: User = Depends(require_admin)):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "작업을 찾을 수 없습니다. 다시 생성해 주세요.")
    return {"status": job["status"], "result": job.get("result"), "error": job.get("error")}
