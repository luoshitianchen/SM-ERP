import os
from pathlib import Path

os.environ["ERP_DATABASE_PATH"] = str(Path(__file__).parent / "test.db")
os.environ["ERP_SM4_KEY_HEX"] = "00112233445566778899aabbccddeeff"
os.environ["ERP_BOOTSTRAP_PASSWORD"] = "admin"

from fastapi.testclient import TestClient
from app.main import app


def test_admin_can_manage_organization_and_people():
    Path(os.environ["ERP_DATABASE_PATH"]).unlink(missing_ok=True)
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert login.status_code == 200
        csrf = {"X-CSRF-Token": login.json()["csrf_token"]}
        client.cookies.clear()
        assert client.get("/api/employees", headers={"X-User-Id": "admin"}).status_code == 401
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        csrf = {"X-CSRF-Token": login.json()["csrf_token"]}
        assert client.post("/api/departments", json={"id": "blocked", "name": "禁止部门"}).status_code == 403
        assert client.post("/api/departments", headers=csrf, json={"id": "operations", "name": "运营部"}).status_code == 201
        employee = client.post("/api/employees", headers=csrf, json={"username": "operator", "password": "secure123", "name": "运营同事", "department": "operations", "role": "manager"})
        assert employee.status_code == 201
        assert client.patch(f"/api/employees/{employee.json()['id']}/status?active=false", headers=csrf).status_code == 200
        assert client.get("/api/audit-logs").status_code == 200
        assert client.post("/api/auth/logout", headers=csrf).status_code == 200
        assert client.get("/api/employees").status_code == 401


def test_login_lockout_after_failed_attempts(monkeypatch):
    Path(os.environ["ERP_DATABASE_PATH"]).unlink(missing_ok=True)
    from app import main
    monkeypatch.setattr(main, "LOGIN_MAX_FAILURES", 2)
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
        assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
        assert client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).status_code == 429


def test_sm4_key_is_required(monkeypatch):
    from app.main import master_key
    monkeypatch.delenv("ERP_SM4_KEY_HEX")
    try:
        master_key()
    except RuntimeError as exc:
        assert "ERP_SM4_KEY_HEX" in str(exc)
    else:
        raise AssertionError("missing SM4 key must fail")


def test_security_headers_and_request_id():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-Id": "audit-trace-1"})
        assert response.status_code == 200
        assert response.headers["X-Request-Id"] == "audit-trace-1"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert float(response.headers["X-Process-Time-Ms"]) >= 0
        assert response.headers["Server-Timing"].startswith("app;dur=")


def test_rejects_oversized_request_body(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "MAX_REQUEST_BYTES", 8)
    with TestClient(app) as client:
        response = client.post("/api/auth/login", content="x" * 9, headers={"content-type": "application/json"})
        assert response.status_code == 413
        assert response.headers["X-Request-Id"]


def test_rejects_malformed_content_length():
    with TestClient(app) as client:
        response = client.get("/health", headers={"Content-Length": "not-a-number"})
        assert response.status_code == 400


def test_replaces_unsafe_request_id():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-Id": "x" * 65})
        assert response.status_code == 200
        assert response.headers["X-Request-Id"] != "x" * 65


def test_integration_key_rotation_accepts_current_and_previous(monkeypatch):
    from app.main import integration_keys
    monkeypatch.setenv("ERP_KNOWLEDGE_BOT_INTEGRATION_KEYS", "current-key, previous-key")
    assert integration_keys() == ("current-key", "previous-key")


def test_admin_audit_logs_support_pagination_and_action_filter():
    Path(os.environ["ERP_DATABASE_PATH"]).unlink(missing_ok=True)
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert login.status_code == 200
        response = client.get("/api/audit-logs?action=auth.login&limit=1&offset=0")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] >= 1
        assert len(payload["items"]) == 1
        assert payload["items"][0]["action"] == "auth.login"


def test_session_pruning_keeps_latest_sessions(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "MAX_SESSIONS_PER_USER", 2)
    with main.db() as conn:
        for index in range(4):
            conn.execute("INSERT OR REPLACE INTO sessions (token_hash,employee_id,expires_at,created_at,csrf_hash) VALUES (?,?,?,?,?)", (f"session-{index}", "admin", main.timestamp() + 3600, f"2026-01-01T00:00:0{index}+00:00", "csrf"))
        main.prune_employee_sessions(conn, "admin")
        assert conn.execute("SELECT COUNT(*) FROM sessions WHERE employee_id='admin'").fetchone()[0] == 2
