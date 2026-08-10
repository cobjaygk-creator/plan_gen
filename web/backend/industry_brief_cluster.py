"""Manual trigger for Phase 4 issue clustering (see
app/industry_brief/cluster.py). No API calls — pure local computation.

Usage:
    .venv\\Scripts\\python.exe web/backend/industry_brief_cluster.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.industry_brief.cluster import cluster_pending


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = cluster_pending(db)
        print(f"신규 이슈 {result.new_issues}건, 기존 이슈에 합류 {result.appended}건")
    finally:
        db.close()


if __name__ == "__main__":
    main()
