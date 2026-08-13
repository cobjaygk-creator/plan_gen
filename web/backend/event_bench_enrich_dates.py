"""Backfill official registration dates for active Event Benchmark cards."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from app.event_bench.nexon_sample import _published_date_from_page

PATH = Path(__file__).resolve().parent / "data" / "event_bench" / "nexon_events_sample.json"

if __name__ == "__main__":
    rows = json.loads(PATH.read_text(encoding="utf-8"))
    targets = [row for row in rows if row.get("is_active", True) and not row.get("published_on")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_published_date_from_page, row["event_url"]): row for row in targets}
        for future in as_completed(futures):
            row = futures[future]
            try:
                row["published_on"] = future.result()
            except Exception:
                row["published_on"] = None
    rows.sort(key=lambda row: (bool(row.get("is_active", False)), row.get("published_on") or row.get("first_collected_at") or row.get("collected_at") or ""), reverse=True)
    PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"resolved={sum(1 for row in targets if row.get('published_on'))}/{len(targets)}")
