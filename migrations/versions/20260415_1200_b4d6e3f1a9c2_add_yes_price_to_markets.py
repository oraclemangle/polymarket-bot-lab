"""add yes_price to markets

Revision ID: b4d6e3f1a9c2
Revises: 2a92772f19ea
Create Date: 2026-04-15 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d6e3f1a9c2'
down_revision: str | None = '2a92772f19ea'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('markets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('yes_price', sa.Numeric(precision=10, scale=6), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('markets', schema=None) as batch_op:
        batch_op.drop_column('yes_price')
