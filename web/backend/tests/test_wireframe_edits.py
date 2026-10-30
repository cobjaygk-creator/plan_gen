import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import app.deps as deps_module
from app.models import WireframeEdit, WireframeGeneration
from app.wireframe.edits import (
    MAX_PATCHES, PatchError, build_document, export_zip, safe_page_filename, validate_patch, validate_patches,
)

HTML = '<!doctype html><html><head><title>t</title></head><body><h1>제목</h1><a href="#">버튼</a></body></html>'
PATH = "body>h1:nth-child(1)"


def good(**fields):
    return {"op": "text", "path": PATH, "ref": "제목", "node": 0, "value": "새 제목", **fields}


# ---------- 검증 ----------
def test_valid_patches_of_every_kind_are_normalized():
    raw = [
        good(),
        {"op": "link", "path": PATH, "href": "https://example.com/a?b=1", "target": "_blank"},
        {"op": "link", "path": PATH, "href": "page:DN-SEA-P-0", "target": ""},
        {"op": "link", "path": PATH, "href": ""},
        {"op": "style", "path": PATH, "style": {"color": "#112233", "fontSize": "18px", "padding": "8px 12px"}},
        {"op": "image", "path": PATH, "src": "data:image/png;base64,iVBORw0KGgo="},
        {"op": "image", "path": PATH, "src": "https://example.com/a.png"},
        {"op": "move", "path": PATH, "dir": "up"},
        {"op": "insert", "path": PATH, "kind": "button"},
        {"op": "delete", "path": PATH},
        {"op": "duplicate", "path": PATH},
    ]
    clean = validate_patches(raw)
    assert [p["op"] for p in clean] == [p["op"] for p in raw]
    assert all(set(p) >= {"op", "path", "ref"} for p in clean)


@pytest.mark.parametrize(
    "patch",
    [
        {"op": "text", "path": "body>div", "value": "x"},
        {"op": "text", "path": "body>div:nth-child(1);alert(1)", "value": "x"},
        {"op": "text", "path": "html>body", "value": "x"},
        {"op": "teleport", "path": PATH},
        {"op": "text", "path": PATH, "node": -1, "value": "x"},
        {"op": "text", "path": PATH, "node": True, "value": "x"},
        {"op": "text", "path": PATH, "value": "x" * 3001},
        {"op": "text", "path": PATH, "value": "bad\x00char"},
        {"op": "link", "path": PATH, "href": "javascript:alert(1)"},
        {"op": "link", "path": PATH, "href": "data:text/html,<script>1</script>"},
        {"op": "link", "path": PATH, "href": "https://a.com/x y"},
        {"op": "link", "path": PATH, "href": "https://a.com/\"onclick=1"},
        {"op": "link", "path": PATH, "href": "https://a.com", "target": "_top"},
        {"op": "style", "path": PATH, "style": {"position": "fixed"}},
        {"op": "style", "path": PATH, "style": {"color": "url(http://x)"}},
        {"op": "style", "path": PATH, "style": {"color": "red;background:red"}},
        {"op": "style", "path": PATH, "style": {}},
        {"op": "image", "path": PATH, "src": "data:text/html;base64,AAAA"},
        {"op": "image", "path": PATH, "src": "javascript:alert(1)"},
        {"op": "move", "path": PATH, "dir": "left"},
        {"op": "insert", "path": PATH, "kind": "script"},
        "not-a-dict",
    ],
)
def test_unsafe_or_malformed_patches_are_rejected(patch):
    with pytest.raises(PatchError):
        validate_patch(patch)


def test_oversized_lists_and_images_are_rejected():
    with pytest.raises(PatchError):
        validate_patches([{"op": "delete", "path": PATH}] * (MAX_PATCHES + 1))
    huge = "data:image/png;base64," + "A" * 1_700_000
    with pytest.raises(PatchError):
        validate_patch({"op": "image", "path": PATH, "src": huge})
    with pytest.raises(PatchError):
        validate_patches("nope")


def test_unknown_fields_are_dropped():
    clean = validate_patch({"op": "delete", "path": PATH, "onclick": "alert(1)", "html": "<b>"})
    assert set(clean) == {"op", "path", "ref"}


# ---------- 문서 조립 ----------
def test_view_without_patches_returns_the_original_untouched():
    assert build_document(HTML, [], "view") == HTML


def test_view_with_patches_embeds_runtime_before_body_end_without_editor():
    doc = build_document(HTML, [good()], "view")
    assert 'id="qp-patches"' in doc and "__qpRuntime" in doc and "__qpEditor" not in doc
    assert doc.index('id="qp-patches"') < doc.rindex("</body>")
    assert 'window.__QP_MODE="view"' in doc


def test_edit_mode_adds_the_editor_script_even_without_patches():
    doc = build_document(HTML, [], "edit")
    assert "__qpEditor" in doc and 'window.__QP_MODE="edit"' in doc


def test_patch_text_cannot_break_out_of_the_script_tag():
    evil = good(value="</script><script>alert(1)</script>")
    doc = build_document(HTML, [evil], "view")
    assert "</script><script>alert(1)" not in doc
    assert "\\u003c/script\\u003e" in doc
    embedded = doc.split('id="qp-patches" type="application/json">')[1].split("</script>")[0]
    assert json.loads(embedded)[0]["value"] == "</script><script>alert(1)</script>"


def test_documents_without_body_tag_get_scripts_appended_and_last_body_is_used():
    assert build_document("<p>x</p>", [good()], "view").startswith("<p>x</p><script>")
    two = "<body>a</body> text <body>b</body>"
    doc = build_document(two, [good()], "view")
    assert doc.startswith("<body>a</body> text <body>b<script>") and doc.endswith("</body>")


# ---------- 묶음 ----------
def test_zip_has_one_file_per_page_plus_an_index_with_safe_names():
    data = export_zip([("DN-SEA-P-0", "메인 <1>", "<html>a</html>"), ("a/b c", "서브", "<html>b</html>")])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert sorted(archive.namelist()) == ["DN-SEA-P-0.html", "a_b_c.html", "index.html"]
        index = archive.read("index.html").decode("utf-8")
    assert "./a_b_c.html" in index and "&lt;1&gt;" in index and "<1>" not in index
    assert safe_page_filename("a/b c") == "a_b_c"


# ---------- API ----------
@pytest.fixture()
def admin(client, make_user, monkeypatch):
    monkeypatch.setattr(deps_module, "ADMIN_EMAIL", "admin@team.com")
    user = make_user(email="admin@team.com", password="correcthorse", name="관리자")
    client.post("/auth/login", json={"email": "admin@team.com", "password": "correcthorse"})
    return user


@pytest.fixture()
def make_record(db_factory, tmp_path):
    def _make(user, page_id="P-1", title="메인", source="sb.pptx", status="done", html=HTML):
        path = tmp_path / f"{user.id}_{safe_page_filename(page_id)}_{status}_{len(list(tmp_path.iterdir()))}.html"
        path.write_text(html, encoding="utf-8")
        db = db_factory()
        record = WireframeGeneration(
            user_id=user.id, source_filename=source, page_id=page_id, page_title=title,
            status=status, output_path=str(path),
        )
        db.add(record)
        db.commit()
        record_id = record.id
        db.close()
        return record_id

    return _make


def test_record_endpoints_require_login(client):
    assert client.get("/wireframe/history/1").status_code == 401
    assert client.put("/wireframe/history/1/edits", json={"patches": []}).status_code == 401
    assert client.get("/wireframe/export?ids=1").status_code == 401


def test_other_users_records_are_not_visible(client, admin, make_user, make_record):
    other = make_user(email="other@team.com", password="hunter2", name="다른사람")
    record_id = make_record(other)
    assert client.get(f"/wireframe/history/{record_id}").status_code == 404
    assert client.put(f"/wireframe/history/{record_id}/edits", json={"patches": []}).status_code == 404
    assert client.get(f"/wireframe/history/{record_id}/download").status_code == 404
    assert client.get(f"/wireframe/export?ids={record_id}").status_code == 404


def test_detail_returns_original_assets_and_latest_sibling_per_page(client, admin, make_record):
    first = make_record(admin, "P-1", "메인")
    make_record(admin, "P-2", "서브")
    latest = make_record(admin, "P-1", "메인 다시 생성")
    make_record(admin, "P-3", "다른 문서", source="other.pptx")
    make_record(admin, "P-4", "생성 중", status="running")

    body = client.get(f"/wireframe/history/{first}").json()
    assert body["html"] == HTML and body["patches"] == [] and body["editedAt"] is None
    assert "__qpRuntime" in body["assets"]["runtime"] and "__qpEditor" in body["assets"]["editor"]
    assert [(s["pageId"], s["historyId"]) for s in body["siblings"]] == [("P-2", first + 1), ("P-1", latest)]


def test_save_reload_and_clear_edits(client, admin, make_record, db_factory):
    record_id = make_record(admin)
    saved = client.put(f"/wireframe/history/{record_id}/edits", json={"patches": [good()]})
    assert saved.status_code == 200 and saved.json()["count"] == 1 and saved.json()["editedAt"]

    detail = client.get(f"/wireframe/history/{record_id}").json()
    assert detail["patches"][0]["value"] == "새 제목" and detail["editedAt"]
    listing = client.get("/wireframe/history").json()
    assert listing[0]["id"] == record_id and listing[0]["has_edits"] is True and listing[0]["edited_at"]

    again = client.put(f"/wireframe/history/{record_id}/edits", json={"patches": [good(value="두 번째")]})
    assert again.json()["count"] == 1
    assert client.get(f"/wireframe/history/{record_id}").json()["patches"][0]["value"] == "두 번째"

    cleared = client.put(f"/wireframe/history/{record_id}/edits", json={"patches": []})
    assert cleared.json() == {"saved": True, "count": 0, "editedAt": None}
    assert client.get("/wireframe/history").json()[0]["has_edits"] is False
    assert db_factory().get(WireframeEdit, record_id) is None


def test_unsafe_edits_are_rejected_and_nothing_is_stored(client, admin, make_record, db_factory):
    record_id = make_record(admin)
    res = client.put(
        f"/wireframe/history/{record_id}/edits",
        json={"patches": [{"op": "link", "path": PATH, "href": "javascript:alert(1)"}]},
    )
    assert res.status_code == 422 and "링크" in res.json()["detail"]
    assert db_factory().get(WireframeEdit, record_id) is None


def test_only_finished_records_can_be_edited(client, admin, make_record):
    record_id = make_record(admin, status="running")
    assert client.put(f"/wireframe/history/{record_id}/edits", json={"patches": [good()]}).status_code == 409
    assert client.get(f"/wireframe/history/{record_id}").status_code == 409


def test_download_serves_original_or_edited(client, admin, make_record):
    record_id = make_record(admin, "DN/P 1")
    client.put(f"/wireframe/history/{record_id}/edits", json={"patches": [good()]})

    original = client.get(f"/wireframe/history/{record_id}/download")
    assert original.text == HTML and "qp-patches" not in original.text
    edited = client.get(f"/wireframe/history/{record_id}/download?version=edited")
    assert "qp-patches" in edited.text and "새 제목" in edited.text
    assert 'filename="DN_P_1.html"' in edited.headers["content-disposition"]

    plain_id = make_record(admin, "P-9")
    assert client.get(f"/wireframe/history/{plain_id}/download?version=edited").text == HTML


def test_export_zip_bundles_latest_edited_pages(client, admin, make_record):
    a = make_record(admin, "P-1", "메인")
    b = make_record(admin, "P-2", "서브")
    dup = make_record(admin, "P-1", "중복")
    client.put(f"/wireframe/history/{a}/edits", json={"patches": [good()]})

    res = client.get(f"/wireframe/export?ids={a},{b},{dup}")
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        assert sorted(archive.namelist()) == ["P-1.html", "P-2.html", "index.html"]
        assert "qp-patches" in archive.read("P-1.html").decode("utf-8")
        assert archive.read("P-2.html").decode("utf-8") == HTML

    original = client.get(f"/wireframe/export?ids={a}&version=original")
    with zipfile.ZipFile(io.BytesIO(original.content)) as archive:
        assert archive.read("P-1.html").decode("utf-8") == HTML


def test_export_validates_ids(client, admin, make_record):
    assert client.get("/wireframe/export?ids=abc").status_code == 400
    assert client.get("/wireframe/export?ids=999").status_code == 404
    running = make_record(admin, status="running")
    assert client.get(f"/wireframe/export?ids={running}").status_code == 404
