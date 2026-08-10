"""Manual trigger for Phase 5 trend computation (see
app/industry_brief/trends.py). No API calls — pure local computation.
Prints today's per-category signals + updates each Issue's lifecycle.

Usage:
    .venv\\Scripts\\python.exe web/backend/industry_brief_trends.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.industry_brief.trends import compute_daily_trends, new_today, refresh_issue_lifecycles


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for category in ("GAME", "AI"):
            trends = compute_daily_trends(db, category, now)
            print(f"=== {category} signals ===")
            for t in trends[:10]:
                print(f"  {t.direction:>4} {t.topic:<24} today={t.today_count} baseline_avg={t.baseline_avg:.1f} lifecycle={t.lifecycle}")
            fresh = new_today(trends)
            if fresh:
                print(f"  new today: {[t.topic for t in fresh]}")

        updated = refresh_issue_lifecycles(db, now)
        print(f"이슈 라이프사이클 갱신: {updated}건")
    finally:
        db.close()


if __name__ == "__main__":
    main()
