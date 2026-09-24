import os
import tempfile

os.environ["ENVIRONMENT"] = "test"
os.environ["MONGODB_URI"] = "mongodb://127.0.0.1:27017"
os.environ["MONGO_DB"] = "neo_xml_test"
os.environ["JWT_SECRET"] = "test-jwt-secret-value"
os.environ["UPLOAD_ROOT"] = tempfile.mkdtemp(prefix="neo-xml-")
os.environ["ADMIN_EMAIL"] = "admin@neo-xml.local"
os.environ["ADMIN_PASSWORD"] = "ChangeMe123!"
os.environ["CORS_ORIGINS"] = "http://localhost:8017"

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.core.db import set_client
from app.main import app

VALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<dmodule id="dm1">
  <ident><dmc>DMC-00001</dmc></ident>
  <title>Hydraulic pump</title>
  <content>
    <para id="p1">Remove the pump.</para>
  </content>
</dmodule>
"""


@pytest.fixture()
def client():
    mock = mongomock.MongoClient()
    set_client(mock)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    set_client(None)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client, email="admin@neo-xml.local", password="ChangeMe123!") -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def admin_headers(client) -> dict:
    return auth_header(login(client)["access_token"])


def workspace_id(client, headers) -> str:
    response = client.get("/api/v1/workspaces", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"][0]["id"]
