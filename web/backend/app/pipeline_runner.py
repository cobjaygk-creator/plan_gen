"""Runs the existing CLI pipeline (tools/pipeline.py, tools/render_from_template.py)
for one Generation row, reporting progress into the DB as it goes so
routers/generations.py's SSE endpoint can stream it out. This is the one
place the web backend calls into the untouched pipeline code — everything
else here is new.

Meant to run in a background thread (see routers/generations.py's
BackgroundTasks.add_task) — it opens its own DB session since the
request-scoped one from FastAPI's dependency injection is gone by the
time this executes.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.parse_fixed_fields import parse_fixed_fields
from tools.pipeline import process_month
from tools.render_from_template import render_from_template

from .database import SessionLocal
from .models import Generation, GenerationStatus

TEMPLATE_PATH = REPO_ROOT / "samples" / "template.pptx"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
IMAGE_DIR = DATA_DIR / "images"

MONTH_RE = re.compile(r"^(\d{6})")


def guess_month(filename: str) -> str:
    m = MONTH_RE.match(filename)
    return m.group(1) if m else "output"


def upload_path_for(generation_id: int) -> Path:
    return UPLOAD_DIR / f"{generation_id}.xlsx"


def run_generation(generation_id: int) -> None:
    db = SessionLocal()
    try:
        gen = db.get(Generation, generation_id)
        if gen is None:
            return

        gen.status = GenerationStatus.RUNNING.value
        gen.current_step = 0
        db.commit()

        def on_progress(step: int, _message: str) -> None:
            gen.current_step = step
            db.commit()

        request_path = str(upload_path_for(generation_id))
        image_out_dir = str(IMAGE_DIR / str(generation_id))

        try:
            fixed = parse_fixed_fields(request_path)
            result = process_month(
                gen.month, request_path, image_out_dir=image_out_dir, on_progress=on_progress,
            )

            if result.needs_human_review:
                gen.status = GenerationStatus.NEEDS_REVIEW.value
                gen.error_message = result.needs_human_review
                db.commit()
                return

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            out_path = str(OUTPUT_DIR / f"{generation_id}.pptx")
            render_from_template(fixed, result, str(TEMPLATE_PATH), out_path)
            on_progress(4, ".pptx 렌더링 완료")

            gen.status = GenerationStatus.DONE.value
            gen.output_path = out_path
            gen.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            # never let a pipeline bug leave a generation stuck at
            # "running" forever with no explanation
            gen.status = GenerationStatus.ERROR.value
            gen.error_message = f"{type(e).__name__}: {e}"
            db.commit()
    finally:
        db.close()
