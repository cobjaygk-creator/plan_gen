"""Best-effort scheduled refresh used by the GitHub Pages workflow."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent


def run(script: str, *args: str) -> None:
    command = [sys.executable, str(BACKEND / script), *args]
    result = subprocess.run(command, cwd=BACKEND, env=os.environ.copy(), text=True)
    if result.returncode:
        # A missing optional API key must not destroy the previous published snapshot.
        print(f"[static refresh] {script} skipped (exit {result.returncode})")


def main() -> None:
    run("event_bench_refresh.py")
    run("industry_brief_collect.py")
    run("industry_brief_classify.py", os.environ.get("STATIC_CLASSIFY_LIMIT", "80"))
    run("industry_brief_cluster.py")
    run("industry_brief_trends.py")
    run("industry_brief_synthesize.py")
    run("preregistration_refresh.py")
    run("game_sites_refresh.py")
    run("static_export.py")


if __name__ == "__main__":
    main()
