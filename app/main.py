from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

DATABASE = Path(os.getenv("ERP_DATABASE_PATH", "data/erp.db"))
DATABASE.parent.mkdir(parents=True, exist_ok=True)
Role = Literal["employee", "manager", "admin"]

app = FastAPI(title="SM ERP", version="0.1.0", description="企业资源与身份管理系统")


@contextmanager
def db():
    conn = sqlite3.connect(DATABASE, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now() -> str:
    return datetime.now(UTC).isoformat()


def initialize() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS departments (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, manager_id TEXT);
        CREATE TABLE IF NOT EXISTS employees (
          id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL, name TEXT NOT NULL,
          department TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, action TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
        """)
        conn.execute("INSERT OR IGNORE INTO departments VALUES ('engineering','研发部',NULL)")
        conn.execute("INSERT OR IGNORE INTO departments VALUES ('finance','财务部',NULL)")
        conn.execute("INSERT OR IGNORE INTO employees VALUES ('admin','admin','admin','系统管理员','engineering','admin',1,?)", (now(),))


@app.on_event("startup")
def startup() -> None:
    initialize()


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class EmployeeInput(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=256)
    name: str = Field(min_length=1, max_length=80)
    department: str = Field(min_length=1, max_length=80)
    role: Role = "employee"


def actor(x_user_id: str | None) -> sqlite3.Row:
    if not x_user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请提供 X-User-Id")
    with db() as conn:
        row = conn.execute("SELECT * FROM employees WHERE id=? AND active=1", (x_user_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return row


def audit(conn: sqlite3.Connection, actor_id: str, action: str, detail: str = "") -> None:
    conn.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?)", (str(uuid4()), actor_id, action, detail, now()))


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.post("/api/auth/login")
def login(payload: LoginInput) -> dict[str, str]:
    with db() as conn:
        row = conn.execute("SELECT * FROM employees WHERE username=? AND password=? AND active=1", (payload.username, payload.password)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码错误")
        audit(conn, row["id"], "auth.login")
    return {"id": row["id"], "name": row["name"], "department": row["department"], "role": row["role"]}


@app.get("/api/employees")
def employees(x_user_id: str | None = Header(default=None)) -> list[dict[str, object]]:
    current = actor(x_user_id)
    if current["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    with db() as conn:
        rows = conn.execute("SELECT id,username,name,department,role,active,created_at FROM employees ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/employees", status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeInput, x_user_id: str | None = Header(default=None)) -> dict[str, str]:
    current = actor(x_user_id)
    if current["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    employee_id = str(uuid4())
    with db() as conn:
        try:
            conn.execute("INSERT INTO employees VALUES (?,?,?,?,?,?,1,?)", (employee_id, payload.username, payload.password, payload.name, payload.department, payload.role, now()))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "ERP 账号已存在") from exc
        audit(conn, current["id"], "employee.created", payload.username)
    return {"id": employee_id, "message": "员工已创建"}


@app.get("/api/dashboard")
def dashboard_data(x_user_id: str | None = Header(default=None)) -> dict[str, object]:
    current = actor(x_user_id)
    with db() as conn:
        employee_count = conn.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
        department_count = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
        logs = conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 8").fetchall()
    return {"user": {"id": current["id"], "name": current["name"], "role": current["role"], "department": current["department"]}, "employees": employee_count, "departments": department_count, "activities": [dict(row) for row in logs]}
