"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-10
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("settings",
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table("audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("service", sa.String(64), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("integrity", sa.String(128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_event_id", "audit_events", ["event_id"])
    op.create_index("ix_audit_events_service", "audit_events", ["service"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_table("items",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("owner", sa.String(80), nullable=False),
        sa.Column("priority", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_name", "items", ["name"])
    op.create_index("ix_items_status", "items", ["status"])


def downgrade() -> None:
    op.drop_index("ix_items_status", table_name="items")
    op.drop_index("ix_items_name", table_name="items")
    op.drop_table("items")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_service", table_name="audit_events")
    op.drop_index("ix_audit_events_event_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("settings")
