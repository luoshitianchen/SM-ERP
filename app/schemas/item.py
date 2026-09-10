"""业务项相关 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    owner: str = Field(default="平台运营部", min_length=1, max_length=80)
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    status: Literal["planned", "active", "review", "closed"] = "active"


class ItemResponse(BaseModel):
    id: str
    name: str
    owner: str
    priority: str
    status: str
    created_at: datetime | str


class ItemStatusUpdate(BaseModel):
    status: Literal["planned", "active", "review", "closed"]
