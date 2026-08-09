"""Backend settings, loaded from environment (.env at repo root, same file
the CLI pipeline already uses for ANTHROPIC_API_KEY)."""
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'plan_gen.db'}"

# Signs the session cookie (itsdangerous) — a real deployment must set this
# in .env; the fallback is only for local dev and is not a secret anyone
# should rely on.
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "dev-only-insecure-secret-change-me")
SESSION_COOKIE_NAME = "plan_gen_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days
