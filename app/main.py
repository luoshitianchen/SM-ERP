from __future__ import annotations

import os
import sqlite3
import hashlib
import secrets
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from gmssl import func, sm3
from gmssl.sm4 import CryptSM4, SM4_DECRYPT, SM4_ENCRYPT

DATABASE = Path(os.getenv("ERP_DATABASE_PATH", "data/erp.db"))
DATABASE.parent.mkdir(parents=True, exist_ok=True)
Role = Literal["employee", "manager", "admin"]

app = FastAPI(title="SM ERP", version="1.1.0", description="企业资源与身份管理系统")


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


def sm3_hex(data: bytes) -> str:
    return sm3.sm3_hash(func.bytes_to_list(data))


def password_hash(password: str, salt: str | None = None, rounds: int | None = None) -> str:
    """SM3 迭代盐化口令派生，避免存储明文或可逆口令。"""
    rounds = rounds or int(os.getenv("ERP_SM3_PASSWORD_ROUNDS", "10000"))
    salt = salt or secrets.token_hex(16)
    digest = sm3_hex((salt + password).encode())
    for _ in range(rounds - 1):
        digest = sm3_hex((salt + digest).encode())
    return f"sm3${rounds}${salt}${digest}"


def password_matches(password: str, stored: str) -> bool:
    if stored.startswith("sm3$"):
        _, rounds, salt, digest = stored.split("$", 3)
        return secrets.compare_digest(password_hash(password, salt, int(rounds)).split("$", 3)[3], digest)
    if not stored.startswith("scrypt$"):
        return secrets.compare_digest(password, stored)
    _, salt, digest = stored.split("$", 2)
    legacy = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return secrets.compare_digest(legacy, digest)


def sm4_key() -> bytes:
    key = bytes.fromhex(os.getenv("ERP_SM4_KEY_HEX", "00112233445566778899aabbccddeeff"))
    if len(key) != 16:
        raise RuntimeError("ERP_SM4_KEY_HEX 必须是 16 字节的十六进制密钥")
    return key


def encrypt_sensitive(value: str) -> str:
    """SM4-CBC 加密并追加 SM3 MAC，供审计详情等敏感字段使用。"""
    key, iv = sm4_key(), secrets.token_bytes(16)
    cipher = CryptSM4()
    cipher.set_key(key, SM4_ENCRYPT)
    ciphertext = cipher.crypt_cbc(iv, value.encode())
    mac = sm3_hex(key + iv + ciphertext)
    return f"sm4${iv.hex()}${ciphertext.hex()}${mac}"


def decrypt_sensitive(value: str) -> str:
    if not value.startswith("sm4$"):
        return value
    _, iv_hex, cipher_hex, mac = value.split("$", 3)
    key, iv, ciphertext = sm4_key(), bytes.fromhex(iv_hex), bytes.fromhex(cipher_hex)
    if not secrets.compare_digest(sm3_hex(key + iv + ciphertext), mac):
        raise ValueError("审计详情完整性校验失败")
    cipher = CryptSM4()
    cipher.set_key(key, SM4_DECRYPT)
    return cipher.crypt_cbc(iv, ciphertext).decode()


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
        conn.execute("INSERT OR IGNORE INTO employees VALUES ('admin','admin',?,'系统管理员','engineering','admin',1,?)", (password_hash(os.getenv("ERP_BOOTSTRAP_PASSWORD", "admin")), now()))
        # 明文演示口令可启动时迁移；scrypt 口令将在首次成功登录时迁移，避免丢失校验能力。
        legacy = conn.execute("SELECT password FROM employees WHERE id='admin'").fetchone()
        if legacy and not legacy["password"].startswith(("sm3$", "scrypt$")):
            conn.execute("UPDATE employees SET password=? WHERE id='admin'", (password_hash(legacy["password"]),))


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


class DepartmentInput(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,64}$")
    name: str = Field(min_length=2, max_length=80)


def actor(x_user_id: str | None) -> sqlite3.Row:
    if not x_user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请提供 X-User-Id")
    with db() as conn:
        row = conn.execute("SELECT * FROM employees WHERE id=? AND active=1", (x_user_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return row


def audit(conn: sqlite3.Connection, actor_id: str, action: str, detail: str = "") -> None:
    conn.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?)", (str(uuid4()), actor_id, action, encrypt_sensitive(detail), now()))


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.post("/api/auth/login")
def login(payload: LoginInput) -> dict[str, str]:
    with db() as conn:
        row = conn.execute("SELECT * FROM employees WHERE username=? AND active=1", (payload.username,)).fetchone()
        if not row or not password_matches(payload.password, row["password"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码错误")
        if not row["password"].startswith("sm3$"):
            conn.execute("UPDATE employees SET password=? WHERE id=?", (password_hash(payload.password), row["id"]))
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
            if not conn.execute("SELECT 1 FROM departments WHERE id=?", (payload.department,)).fetchone():
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "部门不存在")
            conn.execute("INSERT INTO employees VALUES (?,?,?,?,?,?,1,?)", (employee_id, payload.username, password_hash(payload.password), payload.name, payload.department, payload.role, now()))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "ERP 账号已存在") from exc
        audit(conn, current["id"], "employee.created", payload.username)
    return {"id": employee_id, "message": "员工已创建"}


@app.patch("/api/employees/{employee_id}/status")
def update_employee_status(employee_id: str, active: bool, x_user_id: str | None = Header(default=None)) -> dict[str, str]:
    current = actor(x_user_id)
    if current["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    if employee_id == current["id"] and not active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "不能停用当前管理员账号")
    with db() as conn:
        if conn.execute("UPDATE employees SET active=? WHERE id=?", (int(active), employee_id)).rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "员工不存在")
        audit(conn, current["id"], "employee.status_changed", f"employee={employee_id} active={active}")
    return {"message": "员工状态已更新"}


@app.get("/api/departments")
def departments(x_user_id: str | None = Header(default=None)) -> list[dict[str, object]]:
    actor(x_user_id)
    with db() as conn:
        rows = conn.execute("SELECT d.*,COUNT(e.id) employee_count FROM departments d LEFT JOIN employees e ON e.department=d.id AND e.active=1 GROUP BY d.id ORDER BY d.name").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/departments", status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentInput, x_user_id: str | None = Header(default=None)) -> dict[str, str]:
    current = actor(x_user_id)
    if current["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    with db() as conn:
        try:
            conn.execute("INSERT INTO departments VALUES (?,?,NULL)", (payload.id, payload.name))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "部门 ID 或名称已存在") from exc
        audit(conn, current["id"], "department.created", payload.id)
    return {"id": payload.id, "message": "部门已创建"}


@app.get("/api/audit-logs")
def audit_logs(x_user_id: str | None = Header(default=None)) -> list[dict[str, object]]:
    current = actor(x_user_id)
    if current["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    with db() as conn:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100").fetchall()
    logs = []
    for row in rows:
        item = dict(row)
        try:
            item["detail"] = decrypt_sensitive(item["detail"])
        except ValueError:
            item["detail"] = "[完整性校验失败]"
        logs.append(item)
    return logs


@app.get("/api/dashboard")
def dashboard_data(x_user_id: str | None = Header(default=None)) -> dict[str, object]:
    current = actor(x_user_id)
    with db() as conn:
        employee_count = conn.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
        department_count = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
        logs = conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 8").fetchall()
    return {"user": {"id": current["id"], "name": current["name"], "role": current["role"], "department": current["department"]}, "employees": employee_count, "departments": department_count, "activities": [dict(row) for row in logs]}
