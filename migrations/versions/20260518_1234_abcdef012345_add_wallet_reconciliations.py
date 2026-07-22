"""add wallet_reconciliations table (OQ-123 dry-run backfill foundation)

Revision ID: 1234abcdef01
Revises: d2f8a94c5b7e
Create Date: 2026-05-18 12:34:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '1234abcdef01'
down_revision: str | None = 'd2f8a94c5b7e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallet_reconciliations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wallet_address", sa.String, nullable=False),
        sa.Column("condition_id", sa.String, nullable=True),
        sa.Column("token_id", sa.String, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("event_type", sa.String, nullable=True),
        sa.Column("amount_token", sa.Numeric(18, 8), nullable=True),
        sa.Column("amount_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("price", sa.Numeric(18, 8), nullable=True),
        sa.Column("timestamp_ms", sa.Integer, nullable=True),
        sa.Column("bot_id", sa.String, nullable=True),
        sa.Column("db_location", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("notes", sa.String, nullable=True),
    )
    with op.batch_alter_table("wallet_reconciliations") as batch:
        batch.create_index("ix_wallet_reconciliations_run_at", ["run_at"])
        batch.create_index("ix_wallet_reconciliations_wallet_token", ["wallet_address", "token_id"])
    # UNIQUE is declared via __table_args__ in model; recreate here for SQLite safety
    # (Alembic batch for SQLite does not auto-port complex constraints in all cases)
    op.create_unique_constraint(
        "uq_wallet_reconciliations_row",
        "wallet_reconciliations",
        ["wallet_address", "token_id", "timestamp_ms", "event_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_wallet_reconciliations_row", "wallet_reconciliations", type_="unique")
    with op.batch_alter_table("wallet_reconciliations") as batch:
        batch.drop_index("ix_wallet_reconciliations_wallet_token")
        batch.drop_index("ix_wallet_reconciliations_run_at")
    op.drop_table("wallet_reconciliations")
