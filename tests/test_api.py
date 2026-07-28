import os
from pathlib import Path

os.environ["ERP_DATABASE_PATH"] = str(Path(__file__).parent / "test.db")

from fastapi.testclient import TestClient
from app.main import app


def test_admin_can_manage_organization_and_people():
    Path(os.environ["ERP_DATABASE_PATH"]).unlink(missing_ok=True)
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert login.status_code == 200
        headers = {"X-User-Id": "admin"}
        assert client.post("/api/departments", headers=headers, json={"id": "operations", "name": "运营部"}).status_code == 201
        employee = client.post("/api/employees", headers=headers, json={"username": "operator", "password": "secure123", "name": "运营同事", "department": "operations", "role": "manager"})
        assert employee.status_code == 201
        assert client.patch(f"/api/employees/{employee.json()['id']}/status?active=false", headers=headers).status_code == 200
        assert client.get("/api/audit-logs", headers=headers).status_code == 200
