"""add bot_c_decisions table

Revision ID: d2f8a94c5b7e
Revises: c9e1f4a82b7d
Create Date: 2026-04-15 19:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd2f8a94c5b7e'
down_revision: str | None = 'c9e1f4a82b7d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bot_c_decisions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gamma_id", sa.String, nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("question", sa.String, nullable=False),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("direction", sa.String, nullable=False),
        sa.Column("strike_low", sa.Numeric(20, 10), nullable=True),
        sa.Column("strike_high", sa.Numeric(20, 10), nullable=True),
        sa.Column("resolution_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spot_price", sa.Numeric(20, 10), nullable=False),
        sa.Column("annualised_vol", sa.Numeric(20, 10), nullable=False),
        sa.Column("hours_to_resolution", sa.Numeric(20, 6), nullable=False),
        sa.Column("model_p_yes", sa.Numeric(10, 6), nullable=False),
        sa.Column("market_p_yes", sa.Numeric(10, 6), nullable=False),
        sa.Column("edge", sa.Numeric(10, 6), nullable=False),
        sa.Column("side", sa.String, nullable=False),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column("yes_token_id", sa.String, nullable=False),
        sa.Column("no_token_id", sa.String, nullable=False),
        sa.Column("volume_24h_usd", sa.Numeric(20, 2), nullable=True),
    )
    with op.batch_alter_table("bot_c_decisions") as batch:
        batch.create_index("ix_bot_c_decisions_decided_at", ["decided_at"])
        batch.create_index("ix_bot_c_decisions_gamma_id", ["gamma_id"])


def downgrade() -> None:
    with op.batch_alter_table("bot_c_decisions") as batch:
        batch.drop_index("ix_bot_c_decisions_gamma_id")
        batch.drop_index("ix_bot_c_decisions_decided_at")
    op.drop_table("bot_c_decisions")
