import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root, for schemas/tools

from schemas.classification_schema import ClassificationOutput, Section, Item
from tools.classify_month import ClassifyResult, NeedsHumanReview

SAMPLE_XLSX = Path(__file__).resolve().parents[3] / "samples" / "202605_request.xlsx"


def _fake_classify(month, raw_text, **kwargs):
    output = ClassificationOutput(sections=[
        Section(section_title="기간제 패키지", block_type="grid",
                items=[Item(name="[이벤트] 고대의 서 30일 상자"), Item(name="[이벤트] 세레스의 가호 습득서")],
                footnote=None, confidence=0.95),
    ])
    return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)


def _login(client, make_user, email="user@example.com", password="hunter2"):
    make_user(email=email, password=password)
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200


def _upload(client):
    with open(SAMPLE_XLSX, "rb") as f:
        return client.post(
            "/generations",
            files={"file": ("202605_request.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )


def test_create_generation_requires_login(client):
    with open(SAMPLE_XLSX, "rb") as f:
        res = client.post("/generations", files={"file": ("202605_request.xlsx", f)})
    assert res.status_code == 401


def test_create_generation_rejects_non_xlsx(client, make_user):
    _login(client, make_user)
    res = client.post("/generations", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert res.status_code == 400


def test_create_generation_runs_pipeline_to_completion(client, make_user):
    _login(client, make_user)
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        res = _upload(client)
    assert res.status_code == 202
    body = res.json()
    assert body["month"] == "202605"
    assert body["source_filename"] == "202605_request.xlsx"

    # TestClient runs BackgroundTasks to completion before returning, so by
    # now the pipeline has already finished (real 202605 sample, mocked AI)
    detail = client.get(f"/generations/{body['id']}").json()
    assert detail["status"] == "done"
    assert detail["current_step"] == 4


def test_generation_not_visible_to_a_different_user(client, make_user):
    _login(client, make_user, email="a@team.com")
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        created = _upload(client).json()

    client.post("/auth/logout")
    _login(client, make_user, email="b@team.com", password="otherpass")
    res = client.get(f"/generations/{created['id']}")
    assert res.status_code == 404


def test_list_generations_only_shows_own(client, make_user):
    _login(client, make_user, email="a@team.com")
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        _upload(client)

    client.post("/auth/logout")
    _login(client, make_user, email="b@team.com", password="otherpass")
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        _upload(client)

    res = client.get("/generations")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_download_available_after_done(client, make_user):
    _login(client, make_user)
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        created = _upload(client).json()

    res = client.get(f"/generations/{created['id']}/download")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert len(res.content) > 0


def test_download_before_done_returns_409(client, make_user):
    _login(client, make_user)
    # never runs the background task, so it stays "pending"
    with open(SAMPLE_XLSX, "rb") as f:
        with patch("app.routers.generations.run_generation"):
            created = client.post("/generations", files={"file": ("202605_request.xlsx", f)}).json()
    res = client.get(f"/generations/{created['id']}/download")
    assert res.status_code == 409


def test_needs_human_review_maps_to_needs_review_status(client, make_user):
    _login(client, make_user)

    def raise_review(month, raw_text, **kwargs):
        raise NeedsHumanReview(month, "테스트용 낮은 신뢰도", raw_text)

    with patch("tools.pipeline.classify_month", side_effect=raise_review):
        created = _upload(client).json()

    detail = client.get(f"/generations/{created['id']}").json()
    assert detail["status"] == "needs_review"
    assert detail["error_message"] is not None


def test_stream_returns_final_state_as_sse(client, make_user):
    _login(client, make_user)
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        created = _upload(client).json()

    res = client.get(f"/generations/{created['id']}/stream")
    assert res.status_code == 200
    assert "data:" in res.text
    assert '"status": "done"' in res.text or '"status":"done"' in res.text
