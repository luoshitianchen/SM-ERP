"""ERP 库存域 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StockItemCreate(BaseModel):
    sku: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)
    unit: str = Field(default="个", max_length=16)
    quantity: int = Field(default=0, ge=0)
    safety_stock: int = Field(default=0, ge=0)
    unit_price: float = Field(default=0.0, ge=0)


class StockItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    unit: str | None = Field(default=None, max_length=16)
    safety_stock: int | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    status: Literal["active", "inactive", "discontinued"] | None = None


class StockStatusUpdate(BaseModel):
    status: Literal["active", "inactive", "discontinued"]


class StockTransactionCreate(BaseModel):
    stock_item_id: str = Field(min_length=1, max_length=64)
    direction: Literal["in", "out"]
    change_qty: int = Field(gt=0)
    remark: str = Field(default="", max_length=256)
    operator_id: str = Field(default="", max_length=64)
