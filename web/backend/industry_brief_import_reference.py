"""Import the planning team’s historical article scrape as Industry Brief baseline.

Usage:
    .venv\\Scripts\\python.exe web/backend/industry_brief_import_reference.py <scrape.txt>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.industry_brief.reference import import_reference_scrape, reclassify_reference_articles


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Usage: industry_brief_import_reference.py <scrape.txt> [--reclassify]")
    source = Path(sys.argv[1]).resolve()
    if not source.is_file():
        raise SystemExit(f"Scrape file not found: {source}")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        created, existing = import_reference_scrape(db, source)
        if "--reclassify" in sys.argv:
            changed, total = reclassify_reference_articles(db)
            print(f"Reclassified baseline: {changed}/{total}")
        print(f"기준선 스크랩 import: 신규 {created}건, 기존 {existing}건")
    finally:
        db.close()


if __name__ == "__main__":
    main()