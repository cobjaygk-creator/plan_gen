"""Manual trigger for the Industry Brief RSS collector. No scheduler yet
(Phase 7) — run this by hand until then.

Usage:
    .venv\\Scripts\\python.exe web/backend/industry_brief_collect.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.industry_brief.collector import collect_all


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = collect_all(db)
        for s in result.sources:
            status = f"오류: {s.error}" if s.error else f"신규 {s.new}건, 중복 {s.duplicates}건 (전체 {s.fetched}건 조회)"
            print(f"[{s.source}] {status}")
        print(f"총 신규 기사: {result.total_new}건")
    finally:
        db.close()


if __name__ == "__main__":
    main()
