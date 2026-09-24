import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import RateLimiter
from app.storage.disk import DiskStorage
from app.validation.engine import default_brex_bytes, default_schema_bytes, run_validation
from tests.conftest import VALID_XML, admin_headers, auth_header, login, workspace_id


def test_settings_reject_blank_secret():
    with pytest.raises(ValidationError):
        Settings(mongodb_uri="mongodb://localhost:27017", jwt_secret="short")


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200


def test_login_me_refresh_logout_and_viewer_forbidden(client):
    tokens = login(client)
    headers = auth_header(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert "Super Admin" in me.json()["roles"]
    assert "dm.create" in me.json()["permissions"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    old = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert old.status_code == 401

    assert client.get("/api/v1/data-modules").status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "nope"}).status_code == 422

    headers = admin_headers(client)
    ws = workspace_id(client, headers)
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "viewer@neo-xml.local",
            "name": "Viewer",
            "password": "ViewerPass1",
            "roles": ["Viewer"],
            "workspace_ids": [ws],
        },
    )
    assert created.status_code == 201, created.text
    viewer = auth_header(login(client, "viewer@neo-xml.local", "ViewerPass1")["access_token"])
    denied = client.post(
        "/api/v1/data-modules",
        headers=viewer,
        json={"workspace_id": ws, "title": "Nope", "xml_content": VALID_XML},
    )
    assert denied.status_code == 403

    logout = client.post(
        "/api/v1/auth/logout",
        headers=auth_header(new_tokens["access_token"]),
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout.status_code == 204


def test_upload_download_and_path_rules(client, tmp_path):
    headers = admin_headers(client)
    ws = workspace_id(client, headers)
    bad = client.post(
        "/api/v1/files/upload",
        headers=headers,
        data={"category": "data_modules", "workspace_id": ws},
        files={"file": ("../../etc/passwd", b"<dmodule/>", "application/xml")},
    )
    assert bad.status_code == 422

    good = client.post(
        "/api/v1/files/upload",
        headers=headers,
        data={"category": "data_modules", "workspace_id": ws},
        files={"file": ("pump.xml", VALID_XML.encode(), "application/xml")},
    )
    assert good.status_code == 201, good.text
    file_id = good.json()["id"]
    assert ".." not in good.json()["relative_path"]
    downloaded = client.get(f"/api/v1/files/{file_id}/download", headers=headers)
    assert downloaded.status_code == 200
    assert b"Hydraulic pump" in downloaded.content
    assert client.get(f"/api/v1/files/{file_id}/download").status_code == 401

    storage = DiskStorage(tmp_path)
    try:
        storage.resolve("../../etc/passwd")
        raise AssertionError("path should be rejected")
    except AppError as exc:
        assert exc.status_code == 422


def test_data_module_revision_is_immutable_after_approval(client):
    headers = admin_headers(client)
    ws = workspace_id(client, headers)
    created = client.post(
        "/api/v1/data-modules",
        headers=headers,
        json={"workspace_id": ws, "title": "Pump", "dmc": "DMC-00001", "xml_content": VALID_XML},
    )
    assert created.status_code == 201, created.text
    module_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    duplicate = client.post(
        "/api/v1/data-modules",
        headers=headers,
        json={"workspace_id": ws, "title": "Pump 2", "dmc": "DMC-00001", "xml_content": VALID_XML},
    )
    assert duplicate.status_code == 409

    history = client.get(f"/api/v1/data-modules/{module_id}/history", headers=headers).json()
    first = history[0]
    result = client.post(f"/api/v1/data-modules/{module_id}/validate", headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "passed"
    fetched = client.get(f"/api/v1/validation-results/{result.json()['id']}", headers=headers)
    assert fetched.status_code == 200

    users = client.get("/api/v1/users", headers=headers).json()["items"]
    admin_id = users[0]["id"]
    review = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={"object_id": module_id, "assigned_to": admin_id},
    )
    assert review.status_code == 201, review.text
    review_id = review.json()["id"]
    comment = client.post(
        f"/api/v1/reviews/{review_id}/comments",
        headers=headers,
        json={"text": "Looks good", "location": "title"},
    )
    assert comment.status_code == 201
    decision = client.post(
        f"/api/v1/reviews/{review_id}/decision",
        headers=headers,
        json={"decision": "approve"},
    )
    assert decision.status_code == 200, decision.text
    module = client.get(f"/api/v1/data-modules/{module_id}", headers=headers).json()
    assert module["status"] == "approved"

    blocked = client.patch(
        f"/api/v1/data-modules/{module_id}",
        headers=headers,
        json={"title": "Changed", "xml_content": VALID_XML.replace("Hydraulic", "Electric")},
    )
    assert blocked.status_code == 409

    revised = client.post(
        f"/api/v1/data-modules/{module_id}/revisions",
        headers=headers,
        json={"xml_content": VALID_XML.replace("Hydraulic", "Electric"), "comment": "new issue"},
    )
    assert revised.status_code == 201, revised.text
    assert revised.json()["revision"] == 2
    history = client.get(f"/api/v1/data-modules/{module_id}/history", headers=headers).json()
    assert history[0]["checksum"] == first["checksum"]
    assert history[0]["file_path"] == first["file_path"]
    module = client.get(f"/api/v1/data-modules/{module_id}", headers=headers).json()
    assert module["status"] == "draft"
    assert module["current_revision"] == 2

    audit = client.get("/api/v1/audit", headers=headers, params={"resource_type": "data_module"})
    actions = {item["action"] for item in audit.json()["items"]}
    assert "review.approve" in actions


def test_wrong_workspace_is_hidden(client):
    headers = admin_headers(client)
    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other Shop"})
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    author = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "author@neo-xml.local",
            "name": "Author",
            "password": "AuthorPass1",
            "roles": ["Author"],
            "workspace_ids": [workspace_id(client, headers)],
        },
    )
    assert author.status_code == 201, author.text
    created = client.post(
        "/api/v1/data-modules",
        headers=headers,
        json={"workspace_id": other_id, "title": "Secret", "xml_content": VALID_XML},
    )
    assert created.status_code == 201, created.text
    author_headers = auth_header(login(client, "author@neo-xml.local", "AuthorPass1")["access_token"])
    hidden = client.get(f"/api/v1/data-modules/{created.json()['id']}", headers=author_headers)
    assert hidden.status_code == 404


def test_graphics_validation_review_csdb_and_publish(client):
    headers = admin_headers(client)
    ws = workspace_id(client, headers)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    graphic = client.post(
        "/api/v1/graphics",
        headers=headers,
        data={"workspace_id": ws, "title": "Pump", "icn": "ICN-00001"},
        files={"file": ("pump.png", png, "image/png")},
    )
    assert graphic.status_code == 201, graphic.text
    graphic_id = graphic.json()["id"]
    old_checksum = graphic.json()["checksum"]
    revised = client.post(
        f"/api/v1/graphics/{graphic_id}/revisions",
        headers=headers,
        files={"file": ("pump2.png", png + b"1", "image/png")},
    )
    assert revised.status_code == 201, revised.text
    assert revised.json()["checksum"] != old_checksum
    assert revised.json()["revision"] == 2

    xml = VALID_XML.replace(
        "</content>",
        '<graphic icn="ICN-00001"/></content>',
    )
    created = client.post(
        "/api/v1/data-modules",
        headers=headers,
        json={
            "workspace_id": ws,
            "title": "Pump procedure",
            "xml_content": xml,
            "graphic_ids": [graphic_id],
        },
    )
    assert created.status_code == 201, created.text
    module_id = created.json()["id"]
    broken = client.post(
        "/api/v1/data-modules",
        headers=headers,
        json={"workspace_id": ws, "title": "Broken", "xml_content": "<dmodule><title>Only</title></dmodule>"},
    )
    bad = client.post(f"/api/v1/data-modules/{broken.json()['id']}/validate", headers=headers)
    assert bad.status_code == 200
    assert bad.json()["status"] == "failed"
    assert any(item["rule_id"] == "BREX-DMC" for item in bad.json()["errors"])
    denied = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={"object_id": broken.json()["id"], "assigned_to": client.get("/api/v1/auth/me", headers=headers).json()["id"]},
    )
    assert denied.status_code == 409

    passed = client.post(f"/api/v1/data-modules/{module_id}/validate", headers=headers)
    assert passed.json()["status"] == "passed", passed.text
    me = client.get("/api/v1/auth/me", headers=headers).json()
    review = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={"object_id": module_id, "assigned_to": me["id"]},
    )
    review_id = review.json()["id"]
    edited = client.post(
        f"/api/v1/data-modules/{module_id}/revisions",
        headers=headers,
        json={"xml_content": xml.replace("Remove", "Inspect")},
    )
    assert edited.status_code == 409 or edited.status_code == 201
    compared = client.get(
        f"/api/v1/data-modules/{module_id}/compare",
        headers=headers,
        params={"left": 1, "right": 1},
    )
    assert compared.status_code == 200
    history = client.get(f"/api/v1/data-modules/{module_id}/history", headers=headers).json()
    change = client.post(
        f"/api/v1/reviews/{review_id}/changes",
        headers=headers,
        json={
            "revision_id": history[0]["id"],
            "change_type": "modify",
            "location": "line 5",
            "original_text": "Remove",
            "new_text": "Inspect",
        },
    )
    assert change.status_code == 201, change.text
    accepted = client.post(
        f"/api/v1/reviews/{review_id}/changes/{change.json()['id']}/accept",
        headers=headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    client.post(f"/api/v1/reviews/{review_id}/decision", headers=headers, json={"decision": "approve"})

    summary = client.get("/api/v1/csdb", headers=headers, params={"workspace_id": ws})
    assert summary.status_code == 200
    assert summary.json()["counts"]["data_modules"] >= 1
    assert summary.json()["counts"]["graphics"] == 1

    publication = client.post(
        "/api/v1/publication-modules",
        headers=headers,
        json={"workspace_id": ws, "title": "Pump package", "data_module_ids": [module_id]},
    )
    assert publication.status_code == 201, publication.text
    job = client.post(
        "/api/v1/transformations/run",
        headers=headers,
        json={"publication_id": publication.json()["id"], "scenario": "web"},
    )
    assert job.status_code == 201, job.text
    assert job.json()["status"] == "completed"
    downloaded = client.get(f"/api/v1/files/{job.json()['output_file_id']}/download", headers=headers)
    assert b"Pump package" in downloaded.content
    pdf = client.post(
        "/api/v1/transformations/run",
        headers=headers,
        json={"publication_id": publication.json()["id"], "scenario": "pdf"},
    )
    assert pdf.status_code == 201, pdf.text
    pdf_bytes = client.get(f"/api/v1/files/{pdf.json()['output_file_id']}/download", headers=headers).content
    assert pdf_bytes.startswith(b"%PDF")

    dmrl = client.post(
        "/api/v1/dmrl",
        headers=headers,
        json={
            "workspace_id": ws,
            "title": "Pump list",
            "entries": [{"dmc": created.json()["dmc"], "title": "Pump procedure"}],
        },
    )
    assert dmrl.status_code == 201, dmrl.text
    ddn = client.post(
        "/api/v1/ddn",
        headers=headers,
        json={
            "workspace_id": ws,
            "title": "Dispatch",
            "dmrl_id": dmrl.json()["id"],
            "recipient": "Partner",
        },
    )
    assert ddn.status_code == 201, ddn.text
    csdb_modules = client.get("/api/v1/csdb/data-modules", headers=headers, params={"workspace_id": ws})
    assert csdb_modules.status_code == 200
    csdb_pubs = client.get("/api/v1/csdb/publication-modules", headers=headers)
    assert csdb_pubs.json()["total"] >= 1


def test_validation_engine_rules():
    bad_table = b"""<dmodule id="dm1"><ident><dmc>X</dmc></ident><title>T</title><content><table><row/></table></content></dmodule>"""
    outcome = run_validation(bad_table, default_schema_bytes(), default_brex_bytes(), None, set())
    assert any(item["rule_id"] == "CALS-TABLE" for item in outcome["errors"])
    assert any(item["name"] == "STE" and item["status"] == "not_configured" for item in outcome["checks"])


def test_stack_trace_is_hidden(client):
    response = client.get("/__boom")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert "secret" not in response.text
    assert "Traceback" not in response.text


def test_rate_limiter_blocks():
    limiter = RateLimiter()
    limiter.hit("login:1", 2, 60)
    limiter.hit("login:1", 2, 60)
    try:
        limiter.hit("login:1", 2, 60)
        raise AssertionError("expected limit")
    except AppError as exc:
        assert exc.status_code == 429
