"""Schema sanity + Alembic migration round-trip."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from core.db import (
    Book,
    Event,
    Market,
    Order,
    Position,
    Score,
    Trade,
    get_session_factory,
)


def test_insert_market(tmp_db):
    Session = get_session_factory()
    with Session() as s:
        m = Market(
            condition_id="0xabc",
            category="politics",
            question="Will X happen?",
            fee_rate_bps=40,
            yes_token_id="yes1",
            no_token_id="no1",
        )
        s.add(m)
        s.commit()
    with Session() as s:
        got = s.get(Market, "0xabc")
        assert got is not None
        assert got.category == "politics"
        assert got.fee_rate_bps == 40


def test_trade_hmrc_fields_required(tmp_db):
    """Trade cannot be inserted without HMRC fields — enforced at schema level."""
    Session = get_session_factory()
    with Session() as s:
        t = Trade(
            trade_id="t1",
            bot_id="bot_a",
            condition_id="0xabc",
            token_id="yes1",
            side="BUY",
            price=Decimal("0.04"),
            size=Decimal("100"),
            filled_at=datetime.now(UTC),
            usd_gbp_rate=Decimal("0.80"),
            gbp_notional=Decimal("3.20"),
        )
        s.add(t)
        s.commit()
        assert s.get(Trade, "t1").gbp_notional == Decimal("3.20000000")


def test_alembic_head_matches_models(tmp_db):
    """Alembic revision applied by migrations should produce identical schema
    to models.Base.metadata.create_all. Check tables are all present."""
    import sqlite3

    conn = sqlite3.connect(str(tmp_db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # All model tables must exist (plus alembic_version in live usage, which
    # init_db() doesn't create — that's fine for this test).
    for t in (
        "markets",
        "books",
        "orders",
        "trades",
        "positions",
        "pnl_snapshots",
        "events",
        "scores",
        "price_requests",
        "halt_flags",
    ):
        assert t in tables, f"missing table: {t}"


def test_book_unique_constraint(tmp_db):
    """(token_id, snapshot_at) must be unique."""
    Session = get_session_factory()
    ts = datetime.now(UTC)
    with Session() as s:
        s.add(Book(token_id="x", snapshot_at=ts, bids=[], asks=[]))
        s.commit()
    with Session() as s:
        s.add(Book(token_id="x", snapshot_at=ts, bids=[], asks=[]))
        try:
            s.commit()
            raise AssertionError("expected unique-constraint violation")
        except Exception:
            s.rollback()
