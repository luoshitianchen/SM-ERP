"""ERP 身份域路由：员工、部门、仪表盘（迁移自 v2.5.0 main.py.bak）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.employee import DepartmentCreate, EmployeeCreate, EmployeeStatusUpdate
from app.services.employee import DashboardService, DepartmentService, EmployeeService

router = APIRouter(tags=["erp-identity"])


@router.get("/api/employees")
async def list_employees(session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await EmployeeService.list_employees(session)


@router.post("/api/employees", status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await EmployeeService.create_employee(session, payload, request)


@router.patch("/api/employees/{employee_id}/status")
async def update_employee_status(
    employee_id: str, payload: EmployeeStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await EmployeeService.set_status(session, employee_id, payload.active, request)


@router.get("/api/departments")
async def list_departments(session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await DepartmentService.list_departments(session)


@router.post("/api/departments", status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await DepartmentService.create_department(session, payload, request)


@router.get("/api/dashboard")
async def dashboard(session: AsyncSession = Depends(get_session)) -> dict:
    return await DashboardService.summary(session)
