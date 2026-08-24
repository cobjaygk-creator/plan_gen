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

# Deployment jobs can point the isolated benchmark collector at a separate
# SQLite file. Local use keeps the original database path unchanged.
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'plan_gen.db'}")

# event_bench/game_sites write their archives under this root. A CI job that
# commits its own collection results back to git (the GitHub Pages workflow)
# must point this at a directory the job owns — otherwise its commit tracks
# the same path local dev writes to, and a later `git pull` silently
# overwrites a developer's locally-accumulated archive with the CI's leaner
# one (confirmed: this actually happened — a local 231-event event_bench
# archive was overwritten down to 166 after pulling the workflow's first
# commit). Local use keeps the original shared "data" directory unchanged.
BENCHMARK_DATA_DIR = Path(os.environ.get("BENCHMARK_DATA_DIR", str(DATA_DIR)))
BENCHMARK_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Signs the session cookie (itsdangerous) — a real deployment must set this
# in .env; the fallback is only for local dev and is not a secret anyone
# should rely on.
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "dev-only-insecure-secret-change-me")
SESSION_COOKIE_NAME = "plan_gen_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days
