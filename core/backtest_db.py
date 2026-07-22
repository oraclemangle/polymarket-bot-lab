"""Separate SQLite DB for backtest history.

Kept isolated from production main.db so backfill never pollutes the
live trading DB and so large history tables don't bloat it.

Schema:
  resolved_markets — one row per resolved Polymarket market
  price_history    — time-series of yes_price per token (from CLOB /prices-history)
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


DEFAULT_BACKTEST_DB = Path(
    os.environ.get("BACKTEST_DB_PATH", "./data/backtest.db")
).resolve()


class BTBase(DeclarativeBase):
    pass


class ResolvedMarket(BTBase):
    __tablename__ = "resolved_markets"

    condition_id: Mapped[str] = mapped_column(String, primary_key=True)
    question: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # outcome_yes_price: final settled price of YES token (0 or 1)
    outcome_yes_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    outcome_no_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    yes_token_id: Mapped[str | None] = mapped_column(String, nullable=True)
    no_token_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_neg_risk: Mapped[int] = mapped_column(Integer, default=0)
    volume_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PriceHistory(BTBase):
    __tablename__ = "price_history"
    __table_args__ = (
        Index("ix_price_history_token_ts", "token_id", "ts"),
    )

    token_id: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[int] = mapped_column(Integer, primary_key=True)  # unix seconds
    price: Mapped[float] = mapped_column(Float, nullable=False)


def get_backtest_engine(path: Path | None = None):
    p = path or DEFAULT_BACKTEST_DB
    p.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{p}"
    engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    BTBase.metadata.create_all(engine)
    return engine


def get_backtest_session_factory(path: Path | None = None):
    engine = get_backtest_engine(path)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
