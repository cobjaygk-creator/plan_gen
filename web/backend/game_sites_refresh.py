from __future__ import annotations
import json, sys
from pathlib import Path
BACKEND=Path(__file__).resolve().parent
if str(BACKEND) not in sys.path: sys.path.insert(0,str(BACKEND))
from app.game_sites.portal_collector import refresh_portal_sites
if __name__ == "__main__": print(json.dumps(refresh_portal_sites(), ensure_ascii=False))
