from __future__ import annotations

import os
import re
import sqlite3
import hashlib
import secrets
import json
import logging
from contextvars import ContextVar
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from gmssl import func, sm3
from gmssl.sm4 import CryptSM4, SM4_DECRYPT, SM4_ENCRYPT

DATABASE = Path(os.getenv("ERP_DATABASE_PATH", "data/erp.db"))
DATABASE.parent.mkdir(parents=True, exist_ok=True)
Role = Literal["employee", "manager", "admin"]
ENVIRONMENT = os.getenv("ERP_ENV", "development").lower()
SESSION_COOKIE = "sm_erp_session"
SESSION_TTL_SECONDS = int(os.getenv("ERP_SESSION_TTL_SECONDS", "28800"))
LOGIN_MAX_FAILURES = int(os.getenv("ERP_LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCK_SECONDS = int(os.getenv("ERP_LOGIN_LOCK_SECONDS", "900"))
LOGIN_RATE_WINDOW_SECONDS = int(os.getenv("ERP_LOGIN_RATE_WINDOW_SECONDS", "60"))
LOGIN_RATE_MAX_REQUESTS = int(os.getenv("ERP_LOGIN_RATE_MAX_REQUESTS", "20"))
INTEGRATION_RATE_WINDOW_SECONDS = int(os.getenv("ERP_INTEGRATION_RATE_WINDOW_SECONDS", "60"))
INTEGRATION_RATE_MAX_REQUESTS = int(os.getenv("ERP_INTEGRATION_RATE_MAX_REQUESTS", "60"))
MAX_REQUEST_BYTES = int(os.getenv("ERP_MAX_REQUEST_BYTES", "1048576"))
login_rate_window: dict[str, tuple[int, int]] = {}
integration_rate_window: dict[str, tuple[int, int]] = {}
request_id_context: ContextVar[str] = ContextVar("request_id", default="system")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

allowed_hosts = [host.strip() for host in os.getenv("ERP_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger("sm_erp")


@contextmanager
def db():
    conn = sqlite3.connect(DATABASE, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now() -> str:
    return datetime.now(UTC).isoformat()


def timestamp() -> int:
    return int(datetime.now(UTC).timestamp())


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


def master_key() -> bytes:
    key_hex = os.getenv("ERP_SM4_KEY_HEX")
    if not key_hex:
        raise RuntimeError("必须配置 ERP_SM4_KEY_HEX")
    key = bytes.fromhex(key_hex)
    if len(key) != 16:
        raise RuntimeError("ERP_SM4_KEY_HEX 必须是 16 字节的十六进制密钥")
    return key


def derive_key(label: str) -> bytes:
    """从主密钥派生用途隔离的国密子密钥，避免加密和完整性复用同一密钥。"""
    return bytes.fromhex(sm3_hex(master_key() + label.encode()))[:16]


def encrypt_sensitive(value: str) -> str:
    """SM4-CBC 加密并追加 SM3 MAC，供审计详情等敏感字段使用。"""
    encryption_key, mac_key, iv = derive_key("sm4-encryption"), derive_key("sm3-audit-mac"), secrets.token_bytes(16)
    cipher = CryptSM4()
    cipher.set_key(encryption_key, SM4_ENCRYPT)
    ciphertext = cipher.crypt_cbc(iv, value.encode())
    mac = sm3_hex(mac_key + iv + ciphertext)
    return f"sm4${iv.hex()}${ciphertext.hex()}${mac}"


def decrypt_sensitive(value: str) -> str:
    if not value.startswith("sm4$"):
        return value
    _, iv_hex, cipher_hex, mac = value.split("$", 3)
    encryption_key, mac_key, iv, ciphertext = derive_key("sm4-encryption"), derive_key("sm3-audit-mac"), bytes.fromhex(iv_hex), bytes.fromhex(cipher_hex)
    if not secrets.compare_digest(sm3_hex(mac_key + iv + ciphertext), mac):
        raise ValueError("审计详情完整性校验失败")
    cipher = CryptSM4()
    cipher.set_key(encryption_key, SM4_DECRYPT)
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
        CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, employee_id TEXT NOT NULL, expires_at INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (username TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, locked_until INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "csrf_hash" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN csrf_hash TEXT")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("INSERT OR IGNORE INTO departments VALUES ('engineering','研发部',NULL)")
        conn.execute("INSERT OR IGNORE INTO departments VALUES ('finance','财务部',NULL)")
        bootstrap_password = os.getenv("ERP_BOOTSTRAP_PASSWORD")
        if not bootstrap_password:
            raise RuntimeError("必须配置 ERP_BOOTSTRAP_PASSWORD")
        conn.execute("INSERT OR IGNORE INTO employees VALUES ('admin','admin',?,'系统管理员','engineering','admin',1,?)", (password_hash(bootstrap_password), now()))
        # 明文演示口令可启动时迁移；scrypt 口令将在首次成功登录时迁移，避免丢失校验能力。
        legacy = conn.execute("SELECT password FROM employees WHERE id='admin'").fetchone()
        if legacy and not legacy["password"].startswith(("sm3$", "scrypt$")):
            conn.execute("UPDATE employees SET password=? WHERE id='admin'", (password_hash(legacy["password"]),))


def validate_runtime_config() -> None:
    if ENVIRONMENT == "production":
        master_key()
        if os.getenv("ERP_BOOTSTRAP_PASSWORD") in {None, "", "CHANGE_ME"}:
            raise RuntimeError("生产环境必须设置强 ERP_BOOTSTRAP_PASSWORD")
        if not integration_keys() or any(key.startswith("REPLACE_") for key in integration_keys()):
            raise RuntimeError("生产环境必须设置 ERP_KNOWLEDGE_BOT_INTEGRATION_KEY")
        if any(host in {"*", "0.0.0.0"} for host in allowed_hosts):
            raise RuntimeError("生产环境 ERP_ALLOWED_HOSTS 不可包含通配主机")


def startup() -> None:
    validate_runtime_config()
    initialize()


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup()
    yield


docs_enabled = os.getenv("ERP_ENABLE_DOCS", "false").lower() == "true"
app = FastAPI(title="SM ERP", version="1.1.1", description="企业资源与身份管理系统", docs_url="/docs" if docs_enabled else None, redoc_url=None, openapi_url="/openapi.json" if docs_enabled else None, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-Id", "")
    request_id = supplied_request_id if REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else str(uuid4())
    request.state.request_id = request_id
    context_token = request_id_context.set(request_id)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            body_size = int(content_length)
        except ValueError:
            request_id_context.reset(context_token)
            return Response(status_code=status.HTTP_400_BAD_REQUEST, content="Invalid Content-Length", headers={"X-Request-Id": request_id})
        if body_size < 0 or body_size > MAX_REQUEST_BYTES:
            request_id_context.reset(context_token)
            return Response(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, content="Request body too large", headers={"X-Request-Id": request_id})
    if request.method in {"POST", "PATCH", "PUT", "DELETE"} and request.url.path not in {"/api/auth/login", "/api/integrations/knowledge-bot/auth"}:
        session_token = request.cookies.get(SESSION_COOKIE)
        csrf_token = request.headers.get("X-CSRF-Token")
        if not session_token or not csrf_token:
            request_id_context.reset(context_token)
            return Response(status_code=status.HTTP_403_FORBIDDEN, content="CSRF validation failed", headers={"X-Request-Id": request_id})
        with db() as conn:
            row = conn.execute("SELECT csrf_hash,expires_at FROM sessions WHERE token_hash=?", (sm3_hex(session_token.encode()),)).fetchone()
        if not row or row["expires_at"] <= timestamp() or not secrets.compare_digest(row["csrf_hash"] or "", sm3_hex(csrf_token.encode())):
            request_id_context.reset(context_token)
            return Response(status_code=status.HTTP_403_FORBIDDEN, content="CSRF validation failed", headers={"X-Request-Id": request_id})
    response = await call_next(request)
    request_id_context.reset(context_token)
    response.headers["X-Request-Id"] = request.state.request_id
    logger.info(json.dumps({"request_id": request_id, "method": request.method, "path": request.url.path, "status": response.status_code}, ensure_ascii=False))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; base-uri 'self'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


def integration_keys() -> tuple[str, ...]:
    """返回有效集成密钥；逗号分隔的密钥列表支持无停机轮换。"""
    configured = os.getenv("ERP_KNOWLEDGE_BOT_INTEGRATION_KEYS") or os.getenv("ERP_KNOWLEDGE_BOT_INTEGRATION_KEY", "")
    keys = tuple(key.strip() for key in configured.split(",") if key.strip())
    if not keys:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "知识库集成密钥尚未配置")
    return keys


def consume_rate_limit(window: dict[str, tuple[int, int]], client_ip: str, period: int, maximum: int) -> None:
    """按来源限制认证接口，并及时回收过期条目。"""
    current_time = timestamp()
    for ip, (started, _) in list(window.items()):
        if current_time - started >= period:
            window.pop(ip, None)
    window_started, count = window.get(client_ip, (current_time, 0))
    if current_time - window_started >= period:
        window_started, count = current_time, 0
    if count >= maximum:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "认证请求过于频繁，请稍后重试")
    window[client_ip] = (window_started, count + 1)


class EmployeeInput(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=256)
    name: str = Field(min_length=1, max_length=80)
    department: str = Field(min_length=1, max_length=80)
    role: Role = "employee"


class DepartmentInput(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,64}$")
    name: str = Field(min_length=2, max_length=80)


def actor(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> sqlite3.Row:
    if not session_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录会话已失效")
    token_hash = sm3_hex(session_token.encode())
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at<?", (timestamp(),))
        row = conn.execute("""SELECT e.* FROM sessions s JOIN employees e ON e.id=s.employee_id
                            WHERE s.token_hash=? AND s.expires_at>? AND e.active=1""", (token_hash, timestamp())).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return row


def audit(conn: sqlite3.Connection, actor_id: str, action: str, detail: str = "") -> None:
    enriched = f"request_id={request_id_context.get()} {detail}".strip()
    conn.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?)", (str(uuid4()), actor_id, action, encrypt_sensitive(enriched), now()))


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "数据库不可用") from exc
    return {"status": "ok", "version": app.version, "database": "ok"}


@app.get("/readyz")
def ready() -> dict[str, str]:
    """编排平台就绪探针：确认数据库和生产密钥配置可用。"""
    with db() as conn:
        conn.execute("SELECT 1").fetchone()
    if ENVIRONMENT == "production":
        master_key()
    return {"status": "ready"}


@app.post("/api/auth/login")
def login(payload: LoginInput, response: Response, request: Request) -> dict[str, str]:
    client_ip = request.client.host if request.client else "unknown"
    consume_rate_limit(login_rate_window, client_ip, LOGIN_RATE_WINDOW_SECONDS, LOGIN_RATE_MAX_REQUESTS)
    with db() as conn:
        attempt = conn.execute("SELECT * FROM login_attempts WHERE username=?", (payload.username,)).fetchone()
        if attempt and attempt["locked_until"] > timestamp():
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "账号已临时锁定，请稍后重试")
        row = conn.execute("SELECT * FROM employees WHERE username=? AND active=1", (payload.username,)).fetchone()
        if not row or not password_matches(payload.password, row["password"]):
            failures = (attempt["failures"] if attempt else 0) + 1
            locked_until = timestamp() + LOGIN_LOCK_SECONDS if failures >= LOGIN_MAX_FAILURES else 0
            conn.execute("""INSERT INTO login_attempts VALUES (?,?,?) ON CONFLICT(username)
                         DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until""", (payload.username, failures, locked_until))
            audit(conn, "system", "auth.login_failed", f"username={payload.username}")
            # 认证失败会抛出 HTTPException；此处显式提交以保留锁定计数。
            conn.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码错误")
        if not row["password"].startswith("sm3$"):
            conn.execute("UPDATE employees SET password=? WHERE id=?", (password_hash(payload.password), row["id"]))
        conn.execute("DELETE FROM login_attempts WHERE username=?", (payload.username,))
        session_token, csrf_token = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        conn.execute("INSERT INTO sessions (token_hash,employee_id,expires_at,created_at,csrf_hash) VALUES (?,?,?,?,?)", (sm3_hex(session_token.encode()), row["id"], timestamp() + SESSION_TTL_SECONDS, now(), sm3_hex(csrf_token.encode())))
        audit(conn, row["id"], "auth.login")
    response.set_cookie(SESSION_COOKIE, session_token, max_age=SESSION_TTL_SECONDS, httponly=True, secure=ENVIRONMENT == "production", samesite="strict", path="/")
    return {"id": row["id"], "name": row["name"], "department": row["department"], "role": row["role"], "csrf_token": csrf_token}


@app.post("/api/integrations/knowledge-bot/auth")
def knowledge_bot_auth(payload: LoginInput, request: Request, x_integration_key: str | None = Header(default=None)) -> dict[str, str]:
    """供知识库后端调用的受密钥保护身份验证接口，不创建浏览器会话。"""
    client_ip = request.client.host if request.client else "unknown"
    consume_rate_limit(integration_rate_window, client_ip, INTEGRATION_RATE_WINDOW_SECONDS, INTEGRATION_RATE_MAX_REQUESTS)
    if not x_integration_key or not any(secrets.compare_digest(x_integration_key, key) for key in integration_keys()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "集成密钥无效")
    with db() as conn:
        row = conn.execute("SELECT * FROM employees WHERE username=? AND active=1", (payload.username,)).fetchone()
        if not row or not password_matches(payload.password, row["password"]):
            audit(conn, "system", "integration.login_failed", f"username={payload.username}")
            conn.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码错误")
        audit(conn, row["id"], "integration.knowledge_bot_authenticated")
    return {"id": row["id"], "name": row["name"], "department": row["department"], "role": row["role"]}


@app.post("/api/auth/logout")
def logout(response: Response, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, str]:
    if session_token:
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (sm3_hex(session_token.encode()),))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "已退出登录"}


@app.get("/api/employees")
def employees(current: sqlite3.Row = Depends(actor)) -> list[dict[str, object]]:
    if current["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    with db() as conn:
        rows = conn.execute("SELECT id,username,name,department,role,active,created_at FROM employees ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/employees", status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeInput, current: sqlite3.Row = Depends(actor)) -> dict[str, str]:
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
def update_employee_status(employee_id: str, active: bool, current: sqlite3.Row = Depends(actor)) -> dict[str, str]:
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
def departments(current: sqlite3.Row = Depends(actor)) -> list[dict[str, object]]:
    with db() as conn:
        rows = conn.execute("SELECT d.*,COUNT(e.id) employee_count FROM departments d LEFT JOIN employees e ON e.department=d.id AND e.active=1 GROUP BY d.id ORDER BY d.name").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/departments", status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentInput, current: sqlite3.Row = Depends(actor)) -> dict[str, str]:
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
def audit_logs(current: sqlite3.Row = Depends(actor)) -> list[dict[str, object]]:
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
def dashboard_data(current: sqlite3.Row = Depends(actor)) -> dict[str, object]:
    with db() as conn:
        employee_count = conn.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
        department_count = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
        logs = conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 8").fetchall()
    return {"user": {"id": current["id"], "name": current["name"], "role": current["role"], "department": current["department"]}, "employees": employee_count, "departments": department_count, "activities": [dict(row) for row in logs]}
