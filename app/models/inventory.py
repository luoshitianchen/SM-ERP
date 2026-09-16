"""ERP 库存域模型：库存物料与库存流水。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class StockItem(Base):
    """库存物料：以 SKU 为唯一标识的可采购/可领用物资。"""

    __tablename__ = "erp_stock_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(16), default="个")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    safety_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InventoryTransaction(Base):
    """库存流水：每次入库/出库的明细记录，用于追溯库存变动。"""

    __tablename__ = "erp_inventory_transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stock_item_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("erp_stock_items.id"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # in=入库 / out=出库
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    remark: Mapped[str] = mapped_column(Text, default="")
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
