import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Generation, GenerationStatus, User
from ..pipeline_runner import guess_month, run_generation, upload_path_for
from ..schemas import GenerationOut

router = APIRouter(prefix="/generations", tags=["generations"])

TERMINAL_STATUSES = {
    GenerationStatus.DONE.value, GenerationStatus.ERROR.value, GenerationStatus.NEEDS_REVIEW.value,
}


def _get_owned_generation(id: int, user: User, db: Session) -> Generation:
    gen = db.get(Generation, id)
    if gen is None or gen.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "생성 이력을 찾을 수 없습니다.")
    return gen


@router.post("", response_model=GenerationOut, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "xlsx 파일만 업로드할 수 있습니다.")

    gen = Generation(
        user_id=user.id, month=guess_month(file.filename),
        source_filename=file.filename, status=GenerationStatus.PENDING.value,
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)

    dest = upload_path_for(gen.id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)

    background_tasks.add_task(run_generation, gen.id)
    return gen


@router.get("", response_model=list[GenerationOut])
def list_generations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Generation)
        .filter(Generation.user_id == user.id)
        .order_by(Generation.created_at.desc())
        .all()
    )


@router.get("/{id}", response_model=GenerationOut)
def get_generation(id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_owned_generation(id, user, db)


@router.get("/{id}/stream")
async def stream_progress(id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned_generation(id, user, db)  # 404s up front if not found/not owned

    async def event_source():
        last = None
        while True:
            db.expire_all()  # otherwise SQLAlchemy's identity map keeps
                              # returning the same cached row forever
            gen = db.get(Generation, id)
            state = (gen.status, gen.current_step)
            if state != last:
                last = state
                payload = {
                    "status": gen.status, "step": gen.current_step,
                    "error_message": gen.error_message,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if gen.status in TERMINAL_STATUSES:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.get("/{id}/download")
def download_generation(id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    gen = _get_owned_generation(id, user, db)
    if gen.status != GenerationStatus.DONE.value or not gen.output_path:
        raise HTTPException(status.HTTP_409_CONFLICT, "아직 생성이 완료되지 않았습니다.")
    return FileResponse(
        gen.output_path,
        filename=f"gen_{gen.created_at:%Y%m%d_%H%M}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
