"""Bot F SQLite schema — separate from main.db.

Tables:
  hunter_rankings — latest Hunter run output (ranked top-N wallets + metrics)
  mirror_signals  — Phase 1 read-only signal log (populated by Mirror when built)
  category_crowd_edge — rolling crowd-edge metrics per category for filter inputs
"""
from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


DEFAULT_BOT_F_DB = Path(
    os.environ.get("BOT_F_DB_PATH", "./data/bot_f.db")
).resolve()


class BotFBase(DeclarativeBase):
    pass


class HunterRanking(BotFBase):
    __tablename__ = "hunter_rankings"
    __table_args__ = (
        Index("ix_hunter_run_rank", "run_id", "rank"),
        Index("ix_hunter_wallet", "wallet"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    wallet: Mapped[str] = mapped_column(String, nullable=False)
    pseudonym: Mapped[str | None] = mapped_column(String, nullable=True)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    profit_factor: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe: Mapped[float] = mapped_column(Float, nullable=False)
    realised_pnl_usd: Mapped[float] = mapped_column(Float, nullable=False)
    total_notional_usd: Mapped[float] = mapped_column(Float, nullable=False)
    # Recent-edge ratio: trailing-30d / (trailing-6m median monthly) P&L
    recent_edge_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 7d-vs-30d P&L share (Grok addition)
    p7d_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_categories: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MirrorSignal(BotFBase):
    __tablename__ = "mirror_signals"
    __table_args__ = (
        Index("ix_mirror_ts", "detected_at"),
        Index("ix_mirror_wallet", "wallet"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    wallet: Mapped[str] = mapped_column(String, nullable=False)
    condition_id: Mapped[str] = mapped_column(String, nullable=False)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    size_shares: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    # Latency metrics for the 2-week measurement phase
    whale_tx_ts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_age_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Detected-but-NOT-traded: rejection reason (for Phase-1 telemetry)
    would_have_traded: Mapped[int] = mapped_column(Integer, default=0)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)


class CategoryCrowdEdge(BotFBase):
    __tablename__ = "category_crowd_edge"
    __table_args__ = (
        Index("ix_crowd_category_ts", "category", "computed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    rolling_30d_roi: Mapped[float] = mapped_column(Float, nullable=False)
    rolling_6m_median_roi: Mapped[float] = mapped_column(Float, nullable=False)
    roi_drop_pct: Mapped[float] = mapped_column(Float, nullable=False)


class CrowdCascade(BotFBase):
    """Daily-cron output — detected copy-bot cascades on a market.

    Populated by `bots/bot_f/crowd_signals.py::detect_cascades`. Consumers:
      - Bot B ensemble E4 estimator (aggregated net-flow as probability prior).
      - Bot A / Bot D entry filters (skip/halve on same-direction cascade
        within 6h — front-run-fade avoidance).

    Cascade definition (ADR-032): within a rolling 60s window on one market,
    >= min_wallets distinct ranked wallets traded the same side with
    >= min_gross_usd total notional, that side >= dominance_ratio * other.
    """
    __tablename__ = "crowd_signals"
    __table_args__ = (
        Index("ix_cascade_market_ts", "market_id", "cascade_start_ts"),
        Index("ix_cascade_detected", "detected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    market_id: Mapped[str] = mapped_column(String, nullable=False)
    cascade_start_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    cascade_end_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    n_wallets: Mapped[int] = mapped_column(Integer, nullable=False)
    dominant_side: Mapped[str] = mapped_column(String, nullable=False)
    gross_usd: Mapped[float] = mapped_column(Float, nullable=False)
    dominant_ratio: Mapped[float] = mapped_column(Float, nullable=False)


def get_bot_f_engine(path: Path | None = None):
    p = path or DEFAULT_BOT_F_DB
    p.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{p}"
    engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    BotFBase.metadata.create_all(engine)
    return engine


def get_bot_f_session_factory(path: Path | None = None):
    engine = get_bot_f_engine(path)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
