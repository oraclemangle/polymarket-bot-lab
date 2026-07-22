"""add pyth ingest tables

Revision ID: c9e1f4a82b7d
Revises: b4d6e3f1a9c2
Create Date: 2026-04-15 18:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c9e1f4a82b7d'
down_revision: str | None = 'b4d6e3f1a9c2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NUMERIC = sa.Numeric(20, 10)


def upgrade() -> None:
    op.create_table(
        "pyth_bars_pro",
        sa.Column("ts", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("feed_id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("open", _NUMERIC, nullable=False),
        sa.Column("high", _NUMERIC, nullable=False),
        sa.Column("low", _NUMERIC, nullable=False),
        sa.Column("close", _NUMERIC, nullable=False),
        sa.Column("bid", _NUMERIC, nullable=True),
        sa.Column("ask", _NUMERIC, nullable=True),
        sa.Column("confidence", _NUMERIC, nullable=True),
        sa.Column("publisher_count", sa.Integer, nullable=True),
        sa.Column("market_session", sa.String, nullable=True),
        sa.Column("tick_count", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "pyth_bars_hermes",
        sa.Column("ts", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("feed_id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("open", _NUMERIC, nullable=False),
        sa.Column("high", _NUMERIC, nullable=False),
        sa.Column("low", _NUMERIC, nullable=False),
        sa.Column("close", _NUMERIC, nullable=False),
        sa.Column("bid", _NUMERIC, nullable=True),
        sa.Column("ask", _NUMERIC, nullable=True),
        sa.Column("confidence", _NUMERIC, nullable=True),
        sa.Column("publisher_count", sa.Integer, nullable=True),
        sa.Column("market_session", sa.String, nullable=True),
        sa.Column("tick_count", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "pyth_ticks_recent",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("endpoint", sa.String, nullable=False),
        sa.Column("ts_ms", sa.Integer, nullable=False),
        sa.Column("feed_id", sa.Integer, nullable=False),
        sa.Column("price", _NUMERIC, nullable=True),
        sa.Column("bid", _NUMERIC, nullable=True),
        sa.Column("ask", _NUMERIC, nullable=True),
    )

    with op.batch_alter_table("pyth_ticks_recent") as batch:
        batch.create_index("ix_pyth_ticks_recent_ts_ms", ["ts_ms"])
        batch.create_index("ix_pyth_ticks_recent_feed_id", ["feed_id"])
        batch.create_index("ix_pyth_ticks_endpoint_ts", ["endpoint", "ts_ms"])


def downgrade() -> None:
    with op.batch_alter_table("pyth_ticks_recent") as batch:
        batch.drop_index("ix_pyth_ticks_endpoint_ts")
        batch.drop_index("ix_pyth_ticks_recent_feed_id")
        batch.drop_index("ix_pyth_ticks_recent_ts_ms")

    op.drop_table("pyth_ticks_recent")
    op.drop_table("pyth_bars_hermes")
    op.drop_table("pyth_bars_pro")
