"""SQLAlchemy models for Pyth ingest tables. Registered on import."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class PythBarPro(Base):
    __tablename__ = "pyth_bars_pro"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    feed_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    publisher_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_session: Mapped[str | None] = mapped_column(String, nullable=True)
    tick_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PythBarHermes(Base):
    __tablename__ = "pyth_bars_hermes"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    feed_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    publisher_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_session: Mapped[str | None] = mapped_column(String, nullable=True)
    tick_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PythTickRecent(Base):
    __tablename__ = "pyth_ticks_recent"
    __table_args__ = (
        Index("ix_pyth_ticks_endpoint_ts", "endpoint", "ts_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    ts_ms: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    feed_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)


class BotCDecision(Base):
    """Analysis-mode decision log: one row per (market, scan) evaluation."""
    __tablename__ = "bot_c_decisions"
    __table_args__ = (
        Index("ix_bot_c_decisions_decided_at", "decided_at"),
        Index("ix_bot_c_decisions_gamma_id", "gamma_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gamma_id: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    strike_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    strike_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    resolution_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spot_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    annualised_vol: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    hours_to_resolution: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    model_p_yes: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    market_p_yes: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    edge: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    yes_token_id: Mapped[str] = mapped_column(String, nullable=False)
    no_token_id: Mapped[str] = mapped_column(String, nullable=False)
    volume_24h_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
