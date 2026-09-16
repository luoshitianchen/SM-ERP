"""ERP 采购域 Pydantic 模型。"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class PurchaseRequestCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    requester_id: str = Field(default="", max_length=64)
    department_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=128)
    reason: str = Field(default="", max_length=512)
    amount: float = Field(ge=0)


class PurchaseOrderCreate(BaseModel):
    pr_id: str = Field(min_length=1, max_length=64)
    supplier: str = Field(min_length=1, max_length=128)
    amount: float = Field(ge=0)
    order_date: date


class RequestStatusUpdate(BaseModel):
    """采购申请状态流转目标（由服务端校验合法迁移）。"""

    action: Literal["submit", "approve", "reject", "cancel"]


class OrderStatusUpdate(BaseModel):
    action: Literal["receive", "close", "cancel"]
