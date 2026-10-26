import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.deps as deps_module
from app.models import SiteVisit


def test_reloaded_datetimes_are_utc_aware(db_factory):
    db = db_factory()
    db.add(SiteVisit(ip_address="1.2.3.4", path="/", occurred_at=datetime(2026, 10, 26, 23, 2, tzinfo=timezone.utc)))
    db.commit()
    db.close()

    loaded = db_factory().query(SiteVisit).one().occurred_at
    assert loaded.tzinfo is not None and loaded.utcoffset().total_seconds() == 0
    assert loaded.hour == 23


def test_api_serializes_utc_offset_so_browsers_show_local_time(client, make_user, db_factory, monkeypatch):
    # 저장값 23:02(UTC)가 offset 없이 내려가면 한국 브라우저에 23:02로 보이지만 실제는 08:02(KST)다.
    monkeypatch.setattr(deps_module, "ADMIN_EMAIL", "admin@team.com")
    make_user(email="admin@team.com", password="correcthorse", name="관리자")
    db = db_factory()
    db.add(SiteVisit(ip_address="1.2.3.4", path="/", occurred_at=datetime(2026, 10, 26, 23, 2, tzinfo=timezone.utc)))
    db.commit()
    db.close()

    client.post("/auth/login", json={"email": "admin@team.com", "password": "correcthorse"})
    stamp = client.get("/auth/site-visits").json()[0]["occurred_at"]
    assert stamp.endswith("+00:00") or stamp.endswith("Z")
    assert datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc).hour == 23
