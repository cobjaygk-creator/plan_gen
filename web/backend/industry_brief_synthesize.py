"""Manual trigger for Phase 6 AI brief synthesis (see
app/industry_brief/synthesis.py). Makes real OpenAI calls (up to 3: GAME
panel, AI panel, cross-insight) unless a category has no issues yet, in
which case that call is skipped and a fixed fallback is used instead.

Usage:
    .venv\\Scripts\\python.exe web/backend/industry_brief_synthesize.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.industry_brief.synthesis import generate_daily_brief


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        brief = generate_daily_brief(db)
        print(f"brief id={brief.id} date={brief.brief_date} article_count={brief.article_count} issue_count={brief.issue_count}")
        print(f"GAME headline: {brief.game_headline}")
        print(f"AI headline: {brief.ai_headline}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
