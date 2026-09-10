"""ERP 身份域服务：员工/部门业务规则、盐化口令哈希、引导种子。"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import internal_write_allowed, sm3_hex
from app.models.employee import Department, Employee
from app.repositories.employee import (
    count_active_employees,
    count_departments,
    employee_count_by_department,
    get_department,
    get_employee,
    get_employee_by_username,
    list_departments,
    list_employees,
)
from app.repositories.employee import (
    create_department as repo_create_dept,
)
from app.repositories.employee import (
    create_employee as repo_create_emp,
)
from app.schemas.employee import DepartmentCreate, EmployeeCreate
from app.services.audit import record_audit

# 盐化 SM3 迭代口令派生轮次（避免存储可逆口令）。
_PASSWORD_ROUNDS = 5000
_BOOTSTRAP_DEPARTMENTS = (("engineering", "研发部"), ("finance", "财务部"))


def _hash_password(password: str, salt: str | None = None, rounds: int | None = None) -> str:
    rounds = rounds or _PASSWORD_ROUNDS
    salt = salt or secrets.token_hex(16)
    digest = sm3_hex(salt + password)
    for _ in range(rounds - 1):
        digest = sm3_hex(salt + digest)
    return f"sm3${rounds}${salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    if not stored.startswith("sm3$"):
        return secrets.compare_digest(password, stored)
    try:
        _, rounds, salt, digest = stored.split("$", 3)
    except ValueError:
        return False
    candidate = _hash_password(password, salt, int(rounds))
    return secrets.compare_digest(candidate, stored)


async def _ensure_seed(session: AsyncSession) -> None:
    """惰性引导：写入默认部门与管理员账号（生产密码由环境变量注入）。"""
    for dept_id, name in _BOOTSTRAP_DEPARTMENTS:
        if not await get_department(session, dept_id):
            await repo_create_dept(session, Department(id=dept_id, name=name))
    if not await get_employee_by_username(session, "admin"):
        bootstrap_pw = settings.ERP_BOOTSTRAP_PASSWORD or "ChangeMe123!"
        await repo_create_emp(session, Employee(
            id=str(uuid.uuid4()), username="admin",
            password_hash=_hash_password(bootstrap_pw), name="系统管理员",
            department="engineering", role="admin", active=True,
        ))


class EmployeeService:
    @staticmethod
    async def list_employees(session: AsyncSession) -> list[dict]:
        await _ensure_seed(session)
        rows = await list_employees(session)
        return [
            {
                "id": e.id, "username": e.username, "name": e.name,
                "department": e.department, "role": e.role, "active": e.active,
                "created_at": e.created_at.isoformat() if e.created_at else "",
            }
            for e in rows
        ]

    @staticmethod
    async def create_employee(session: AsyncSession, payload: EmployeeCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        await _ensure_seed(session)
        if not await get_department(session, payload.department):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "部门不存在")
        emp = Employee(
            id=str(uuid.uuid4()), username=payload.username,
            password_hash=_hash_password(payload.password), name=payload.name,
            department=payload.department, role=payload.role, active=True,
        )
        try:
            emp = await repo_create_emp(session, emp)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "ERP 账号已存在") from exc
        await record_audit(session, "employee.created", "internal", f"employee_id={emp.id}", request)
        return {"id": emp.id, "username": emp.username, "name": emp.name, "message": "员工已创建"}

    @staticmethod
    async def set_status(session: AsyncSession, employee_id: str, active: bool, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        emp = await get_employee(session, employee_id)
        if not emp:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "员工不存在")
        emp.active = active
        await session.commit()
        await session.refresh(emp)
        await record_audit(session, "employee.status_changed", "internal",
                           f"employee={employee_id} active={active}", request)
        return {"id": emp.id, "active": emp.active, "message": "员工状态已更新"}


class DepartmentService:
    @staticmethod
    async def list_departments(session: AsyncSession) -> list[dict]:
        await _ensure_seed(session)
        rows = await list_departments(session)
        result = []
        for dept in rows:
            count = await employee_count_by_department(session, dept.id)
            result.append({
                "id": dept.id, "name": dept.name,
                "manager_id": dept.manager_id, "employee_count": count,
            })
        return result

    @staticmethod
    async def create_department(session: AsyncSession, payload: DepartmentCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        await _ensure_seed(session)
        dept = Department(id=payload.id, name=payload.name)
        try:
            dept = await repo_create_dept(session, dept)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "部门 ID 或名称已存在") from exc
        await record_audit(session, "department.created", "internal", f"department_id={dept.id}", request)
        return {"id": dept.id, "name": dept.name, "message": "部门已创建"}


class DashboardService:
    @staticmethod
    async def summary(session: AsyncSession) -> dict:
        await _ensure_seed(session)
        active_employees = await count_active_employees(session)
        departments = await count_departments(session)
        recent = await list_employees(session, limit=8)
        return {
            "service": settings.SERVICE_NAME, "version": settings.VERSION,
            "employees": active_employees, "departments": departments,
            "generated_at": datetime.now(UTC).isoformat(),
            "recent": [
                {"id": e.id, "name": e.name, "department": e.department, "role": e.role}
                for e in recent
            ],
        }
