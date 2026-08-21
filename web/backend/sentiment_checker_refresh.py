from app.database import Base,SessionLocal,engine
from app.sentiment_checker import models
from app.sentiment_checker.collector import collect
from app.sentiment_checker.analyzer import analyze_pending
from app.sentiment_checker.ai_analyzer import analyze_with_ai
from app.sentiment_checker.comment_collector import collect_comments
from app.sentiment_checker.service import save_snapshot
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
 result={"collection":collect(db),"comments":collect_comments(db,30),"analyzed":analyze_pending(db),"ai":analyze_with_ai(db,25)}
 for period in (24,72,168,720): save_snapshot(db,period)
 print(result)
