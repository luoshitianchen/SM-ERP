"""ERP 身份域 Pydantic 模型。"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=256)
    name: str = Field(min_length=1, max_length=80)
    department: str = Field(min_length=1, max_length=64)
    role: Literal["employee", "manager", "admin"] = "employee"
    # 入职日期：业务规则校验不得晚于当前日期
    hire_date: date | None = None


class EmployeeStatusUpdate(BaseModel):
    active: bool


class DepartmentCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,64}$")
    name: str = Field(min_length=2, max_length=80)
    # 父部门 ID，空串表示顶级部门
    parent_id: str = Field(default="", max_length=64)
