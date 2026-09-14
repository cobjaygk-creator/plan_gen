def test_login_with_correct_credentials_succeeds(client, make_user):
    make_user(email="kim@team.com", password="correcthorse", name="김기획")
    res = client.post("/auth/login", json={"email": "kim@team.com", "password": "correcthorse"})
    assert res.status_code == 200
    assert res.json()["email"] == "kim@team.com"
    assert res.json()["name"] == "김기획"
    assert "password" not in res.json()
    assert "password_hash" not in res.json()


def test_login_with_wrong_password_rejected(client, make_user):
    make_user(email="kim@team.com", password="correcthorse")
    res = client.post("/auth/login", json={"email": "kim@team.com", "password": "wrongpass"})
    assert res.status_code == 401


def test_login_with_unknown_email_rejected(client):
    res = client.post("/auth/login", json={"email": "nobody@team.com", "password": "whatever"})
    assert res.status_code == 401


def test_login_error_message_does_not_reveal_which_field_was_wrong(client, make_user):
    make_user(email="kim@team.com", password="correcthorse")
    wrong_password = client.post("/auth/login", json={"email": "kim@team.com", "password": "nope"})
    unknown_email = client.post("/auth/login", json={"email": "nobody@team.com", "password": "nope"})
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_me_requires_login(client):
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_returns_current_user_after_login(client, make_user):
    make_user(email="kim@team.com", password="correcthorse", name="김기획")
    client.post("/auth/login", json={"email": "kim@team.com", "password": "correcthorse"})
    res = client.get("/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == "kim@team.com"


def test_logout_clears_session(client, make_user):
    make_user(email="kim@team.com", password="correcthorse")
    client.post("/auth/login", json={"email": "kim@team.com", "password": "correcthorse"})
    assert client.get("/auth/me").status_code == 200

    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401


def test_health_check_does_not_require_login(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_access_logs_require_admin_login(client, make_user):
    res = client.get("/auth/access-logs")
    assert res.status_code == 401  # 아예 로그인하지 않은 경우

    make_user(email="kim@team.com", password="correcthorse")
    client.post("/auth/login", json={"email": "kim@team.com", "password": "correcthorse"})
    res = client.get("/auth/access-logs")
    assert res.status_code == 403  # 로그인은 했지만 관리자 계정이 아닌 경우


def test_login_records_access_log_visible_only_to_admin(client, make_user, monkeypatch):
    import app.deps as deps_module
    monkeypatch.setattr(deps_module, "ADMIN_EMAIL", "admin@team.com")

    make_user(email="admin@team.com", password="correcthorse", name="관리자")
    make_user(email="kim@team.com", password="correcthorse", name="김기획")

    client.post("/auth/login", json={"email": "kim@team.com", "password": "correcthorse"})
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "admin@team.com", "password": "correcthorse"})

    res = client.get("/auth/access-logs")
    assert res.status_code == 200
    emails = [row["email"] for row in res.json()]
    assert emails == ["admin@team.com", "kim@team.com"]  # 최신순
    assert all(row["ip_address"] for row in res.json())


def test_site_visits_require_admin(client, make_user):
    res = client.get("/auth/site-visits")
    assert res.status_code == 401

    make_user(email="kim@team.com", password="correcthorse")
    client.post("/auth/login", json={"email": "kim@team.com", "password": "correcthorse"})
    res = client.get("/auth/site-visits")
    assert res.status_code == 403


def test_site_visits_are_visible_to_admin(client, make_user, db_factory, monkeypatch):
    # 로그인 없이 쓰는 시스템이라(가입 자체가 없음) 실제 접속 통계는
    # main.py의 SPA 캐치올이 남긴 SiteVisit이 유일한 출처다 — 여기서는
    # 그 라우트를 직접 거치지 않고 DB에 미리 적재해, "관리자만 조회
    # 가능한지"와 "최신순 정렬"만 이 엔드포인트 자체의 책임으로 검증한다.
    from datetime import datetime, timedelta, timezone
    import app.deps as deps_module
    from app.models import SiteVisit
    monkeypatch.setattr(deps_module, "ADMIN_EMAIL", "admin@team.com")
    make_user(email="admin@team.com", password="correcthorse", name="관리자")

    now = datetime.now(timezone.utc)
    db = db_factory()
    db.add(SiteVisit(ip_address="1.2.3.4", path="/event-bench", occurred_at=now - timedelta(minutes=1)))
    db.add(SiteVisit(ip_address="5.6.7.8", path="/", occurred_at=now))
    db.commit()

    client.post("/auth/login", json={"email": "admin@team.com", "password": "correcthorse"})
    res = client.get("/auth/site-visits")
    assert res.status_code == 200
    paths = [row["path"] for row in res.json()]
    assert paths == ["/", "/event-bench"]  # insertion(=시간)순의 역순 — 최신순
