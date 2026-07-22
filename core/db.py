"""SQLAlchemy models + session factory.

Schema matches specs/shared-infra.md §4.  SQLite in v1; Postgres-compatible
types used throughout so the v2 migration (OQ-013) is a URL swap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from core.config import get_settings


class Base(DeclarativeBase):
    pass


def _now_utc() -> datetime:
    return datetime.now(UTC)


# --- Market catalogue (shared) ---
class Market(Base):
    __tablename__ = "markets"

    condition_id: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fee_rate_bps: Mapped[int | None] = mapped_column(Integer)
    yes_token_id: Mapped[str | None] = mapped_column(String)
    no_token_id: Mapped[str | None] = mapped_column(String)
    is_neg_risk: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    volume_24h_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )
    # Gamma-reported YES outcome price. Used by Bot A to pre-filter book
    # snapshot targets without touching the CLOB for every market.
    # Null until a Gamma scrape has observed the market.
    yes_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )


# --- Book snapshots ---
class Book(Base):
    __tablename__ = "books"
    __table_args__ = (UniqueConstraint("token_id", "snapshot_at", name="uq_books_token_snap"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False, index=True
    )
    bids: Mapped[list] = mapped_column(JSON, default=list)  # [[price, size], ...]
    asks: Mapped[list] = mapped_column(JSON, default=list)


# --- Orders (per-bot) ---
class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    condition_id: Mapped[str] = mapped_column(String, nullable=False)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)  # BUY | SELL
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    size: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN", index=True)
    order_type: Mapped[str] = mapped_column(String, default="GTC")
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, onupdate=_now_utc, nullable=False
    )


# --- Fills ---
class Trade(Base):
    __tablename__ = "trades"

    trade_id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(String, ForeignKey("orders.order_id"))
    condition_id: Mapped[str] = mapped_column(String, nullable=False)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    fee_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # HMRC-ready fields (per ADR-010)
    usd_gbp_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    gbp_notional: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)


# --- Positions (per-bot) ---
class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    condition_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)  # YES | NO
    size: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    cost_basis_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN", index=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Daily PnL snapshots ---
class PnlSnapshot(Base):
    __tablename__ = "pnl_snapshots"

    bot_id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    realised_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    unrealised_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    open_exposure_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"))


# --- Events (kill-switches, halts, alerts) ---
class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str | None] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)  # info | warn | kill
    message: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False, index=True
    )


# --- Bot B only: scores ---
class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False, index=True
    )
    dispute_risk: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    claude_pick: Mapped[str | None] = mapped_column(String)  # YES | NO | SKIP
    claude_confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    claude_implied_prob: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    resolution_prediction: Mapped[str | None] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String, nullable=False)


# --- Bot B only: RAG corpus passthrough ---
class PriceRequest(Base):
    __tablename__ = "price_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ancillary_decoded: Mapped[str | None] = mapped_column(String)
    resolved_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    is_resolved: Mapped[int] = mapped_column(Integer, default=0)
    dispute_count: Mapped[int] = mapped_column(Integer, default=0)
    final_outcome: Mapped[str | None] = mapped_column(String)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )


# --- Halt flag (watchdog sets this; bots check before entries) ---
class HaltFlag(Base):
    __tablename__ = "halt_flags"

    bot_id: Mapped[str] = mapped_column(String, primary_key=True)
    halted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reason: Mapped[str | None] = mapped_column(String)
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )


# --- Wallet/Data API reconciliation (OQ-123, dry-run first per 2026-05-18 spec) ---
# Table populated by wallet_data_api_backfill.py (write path gated behind --execute + env confirm).
# Never mutated by trading paths.
class WalletReconciliation(Base):
    __tablename__ = "wallet_reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )
    wallet_address: Mapped[str] = mapped_column(String, nullable=False)
    condition_id: Mapped[str | None] = mapped_column(String)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 'data_api_positions' | 'data_api_trades' | 'data_api_activity' | 'manual'
    event_type: Mapped[str | None] = mapped_column(
        String
    )  # BUY/SELL/REDEEM/REBATE/POSITION_SNAPSHOT
    amount_token: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    timestamp_ms: Mapped[int | None] = mapped_column(Integer)
    bot_id: Mapped[str | None] = mapped_column(String)
    db_location: Mapped[str | None] = mapped_column(
        String
    )  # 'main.db' | 'persistence_live.db' | 'unowned'
    status: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 'owned' | 'unowned' | 'rebate' | 'reconciliation_only'
    notes: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        UniqueConstraint(
            "wallet_address",
            "token_id",
            "timestamp_ms",
            "event_type",
            name="uq_wallet_reconciliations_row",
        ),
    )


# --- Engine / session factory ---
def _make_engine(db_path: Path | None = None) -> Engine:
    path = db_path or get_settings().polymarket_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{path}"
    engine = create_engine(
        url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )
    # Enable WAL + foreign keys on every connection.
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _pragma_on_connect(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _make_engine()
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db(db_path: Path | None = None) -> Engine:
    """Create all tables.  Used for test DBs and first-run bootstrap.

    Production uses Alembic migrations.
    """
    engine = _make_engine(db_path) if db_path else get_engine()
    Base.metadata.create_all(engine)
    return engine


def reset_engine() -> None:
    """Test helper."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def upsert_market_minimal(
    session,
    *,
    condition_id: str,
    category: str,
    question: str,
    yes_token_id: str | None = None,
    no_token_id: str | None = None,
    end_date: datetime | None = None,
    yes_price: Decimal | None = None,
    volume_24h_usd: Decimal | None = None,
    fee_rate_bps: int | None = None,
    is_neg_risk: int = 0,
) -> Market:
    """Insert-or-update a Market row. Caller commits.

    Used by bot-owned flows (e.g. Bot D's discovery bypasses the main ingest,
    which only captures a subset of Gamma). Keeping a minimal row keyed on
    condition_id lets every analytic that joins orders->markets succeed.

    If a row already exists, non-None fields overwrite existing values and
    last_updated is refreshed; pass None to leave a column untouched.

    ADR-021 (Bot D dual-writes minimal markets row) — does NOT replace the
    main ingest. The long-term fix tracked as OQ-028: widen ingest to cover
    weather markets.
    """
    existing = session.get(Market, condition_id)
    if existing is None:
        new_market = Market(
            condition_id=condition_id,
            category=category,
            question=question,
            end_date=end_date,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            is_neg_risk=is_neg_risk,
            volume_24h_usd=volume_24h_usd if volume_24h_usd is not None else Decimal("0"),
            yes_price=yes_price,
            fee_rate_bps=fee_rate_bps,
            last_updated=_now_utc(),
        )
        session.add(new_market)
        # SECURITY_AUDIT.md M-3: flush + return the new instance directly.
        # Previous code re-queried via session.get which could return None
        # before the flush wrote the row, leaving callers with no Market
        # to work with on first-create.
        session.flush()
        return new_market
    # Update only fields the caller supplied (None = leave as-is).
    if category:
        existing.category = category
    if question:
        existing.question = question
    if end_date is not None:
        existing.end_date = end_date
    if yes_token_id is not None:
        existing.yes_token_id = yes_token_id
    if no_token_id is not None:
        existing.no_token_id = no_token_id
    if yes_price is not None:
        existing.yes_price = yes_price
    if volume_24h_usd is not None:
        existing.volume_24h_usd = volume_24h_usd
    if fee_rate_bps is not None:
        existing.fee_rate_bps = fee_rate_bps
    existing.last_updated = _now_utc()
    return existing
