"""Manual trigger for Phase 3 article classification (see
app/industry_brief/classifier.py). Makes real Anthropic API calls — keep
the limit small unless you mean to spend more.

Usage:
    .venv\\Scripts\\python.exe web/backend/industry_brief_classify.py [limit]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.industry_brief.classifier import classify_pending


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        done = classify_pending(db, limit=limit)
        print(f"분류 완료: {done}건 (최대 {limit}건 처리 시도)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
