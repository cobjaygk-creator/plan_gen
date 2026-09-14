from threading import Lock
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from .analyzer import analyze_pending
from .collector import collect
from .service import save_snapshot,issue_detail,load_dashboard_cache,save_dashboard_cache
from .ai_analyzer import analyze_with_ai
from .comment_collector import collect_comments,collect_dc_comments
router=APIRouter(prefix="/sentiment-checker",tags=["sentiment-checker"])
lock=Lock()
_CACHED_PERIODS=(24,72,168,720)
@router.get("/dashboard")
def get_dashboard(hours:int=24,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    # "수동 갱신"을 눌러 실제로 새 데이터를 모았을 때만 다시 계산한다 —
    # 이 GET은 그 결과를 캐시에서 그대로 읽어 즉시 돌려준다. 화면이 쓰는
    # 4개 기간 밖의 값이 들어오면(직접 API를 호출하는 경우 등) 캐시가
    # 없으니 그때만 즉석에서 계산한다.
    return load_dashboard_cache(db,max(6,min(hours,24*30)))
@router.get("/issues/detail")
def get_issue_detail(key:str,hours:int=168,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    result=issue_detail(db,key,max(24,min(hours,24*30)))
    if result is None: raise HTTPException(404,"Issue not found")
    return result

@router.post("/refresh")
def refresh(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if not lock.acquire(False): raise HTTPException(409,"Collection already running")
    try:
        collected=collect(db); comment_result=collect_comments(db,post_limit=30); dc_comment_result=collect_dc_comments(db,post_limit=40); analyzed=analyze_pending(db); ai=analyze_with_ai(db,limit=60)
        dashboard_24=None
        for period in _CACHED_PERIODS:
            computed=save_dashboard_cache(db,period)
            save_snapshot(db,period,data=computed)
            if period==24: dashboard_24=computed
        return {"collection":collected,"comments":comment_result,"dc_comments":dc_comment_result,"analyzed":analyzed,"ai":ai,"dashboard":dashboard_24}
    finally: lock.release()
