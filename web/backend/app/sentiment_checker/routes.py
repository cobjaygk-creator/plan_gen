from threading import Lock
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from .analyzer import analyze_pending
from .collector import collect
from .service import dashboard,save_snapshot,issue_detail
from .ai_analyzer import analyze_with_ai
from .comment_collector import collect_comments
router=APIRouter(prefix="/sentiment-checker",tags=["sentiment-checker"])
lock=Lock()
@router.get("/dashboard")
def get_dashboard(hours:int=24,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return dashboard(db,max(6,min(hours,24*30)))
@router.get("/issues/detail")
def get_issue_detail(key:str,hours:int=168,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    result=issue_detail(db,key,max(24,min(hours,24*30)))
    if result is None: raise HTTPException(404,"Issue not found")
    return result

@router.post("/refresh")
def refresh(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if not lock.acquire(False): raise HTTPException(409,"Collection already running")
    try:
        collected=collect(db); comment_result=collect_comments(db,post_limit=30); analyzed=analyze_pending(db); ai=analyze_with_ai(db,limit=25)
        for period in (24,72,168,720): save_snapshot(db,period)
        return {"collection":collected,"comments":comment_result,"analyzed":analyzed,"ai":ai,"dashboard":dashboard(db,24)}
    finally: lock.release()
