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

# 업계동향/타사 이벤트/타사 사이트는 로그인 없이 공개 열람할 수 있게 열었다
# (get_current_user_optional 참고). 새로고침 등 실제 비용(LLM 호출)이 드는
# 작업은 여전히 로그인을 요구하지만 이 계정으로 제한하지는 않는다 — 팀
# 계정 전체가 함께 쓰는 기존 방식 그대로다. 이 값은 프런트엔드가 "기획서
# 생성/생성 이력/민심 체크기 메뉴를 보여줄지"를 판단하는 데만 쓰인다
# (web/frontend/src/auth/adminEmail.ts에 같은 값을 따로 둔다 — 백엔드
# 설정을 프런트가 직접 import할 수 없어서 부득이하게 두 곳에 둔다).
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "stkim@actoz.com")
