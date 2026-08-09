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
