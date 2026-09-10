"""ERP 身份域 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=256)
    name: str = Field(min_length=1, max_length=80)
    department: str = Field(min_length=1, max_length=64)
    role: Literal["employee", "manager", "admin"] = "employee"


class EmployeeStatusUpdate(BaseModel):
    active: bool


class DepartmentCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,64}$")
    name: str = Field(min_length=2, max_length=80)
