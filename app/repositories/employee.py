"""ERP 身份域仓储：员工与部门异步数据访问。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee


async def get_department(session: AsyncSession, dept_id: str) -> Department | None:
    result = await session.execute(select(Department).where(Department.id == dept_id))
    return result.scalar_one_or_none()


async def list_departments(session: AsyncSession) -> list[Department]:
    result = await session.execute(select(Department).order_by(Department.name))
    return list(result.scalars().all())


async def employee_count_by_department(session: AsyncSession, dept_id: str) -> int:
    result = await session.execute(
        select(func.count(Employee.id)).where(
            Employee.department == dept_id, Employee.active.is_(True)
        )
    )
    return int(result.scalar_one())


async def create_department(session: AsyncSession, dept: Department) -> Department:
    session.add(dept)
    await session.commit()
    await session.refresh(dept)
    return dept


async def get_employee(session: AsyncSession, emp_id: str) -> Employee | None:
    result = await session.execute(select(Employee).where(Employee.id == emp_id))
    return result.scalar_one_or_none()


async def get_employee_by_username(session: AsyncSession, username: str) -> Employee | None:
    result = await session.execute(select(Employee).where(Employee.username == username))
    return result.scalar_one_or_none()


async def list_employees(session: AsyncSession, limit: int = 200) -> list[Employee]:
    result = await session.execute(
        select(Employee).order_by(Employee.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def create_employee(session: AsyncSession, emp: Employee) -> Employee:
    session.add(emp)
    await session.commit()
    await session.refresh(emp)
    return emp


async def count_active_employees(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(Employee.id)).where(Employee.active.is_(True))
    )
    return int(result.scalar_one())


async def count_departments(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Department.id)))
    return int(result.scalar_one())
