"""Integration tests for 2026-04-17 Bot E audit fixes.

Covers audit Findings 1-5:
1. Recorder trade replay → OBI inflation (SubscriptionTrades cursor)
2. Restart-time dedup gap (open Orders hydrated)
3. Inert loss halts (record_outcome wired to resolved Positions)
4. Depth gate fail-open (OrderBook object accepted, dict backcompat)
5. Recorder freshness watchdog check

Each test isolates one integration seam that unit-level tests missed.
"""
from __future__ import annotations

from decimal import Decimal
import time

import pytest

from bots.bot_e_btc_scalp.signal import SubscriptionTrades, maybe_fire


# ---------- Finding 1: recorder cursor ----------

def test_subscription_trades_cursor_advances_on_record():
    """After recording trades, last_ingested_ts_ms matches the max ts seen."""
    sub = SubscriptionTrades(subscription_id="cid-1")
    assert sub.last_ingested_ts_ms == 0
    sub.record_trade(1000, "tok_yes", Decimal("10"))
    assert sub.last_ingested_ts_ms == 1000
    sub.record_trade(2000, "tok_yes", Decimal("5"))
    assert sub.last_ingested_ts_ms == 2000
    # Older trade doesn't regress the cursor
    sub.record_trade(1500, "tok_no", Decimal("3"))
    assert sub.last_ingested_ts_ms == 2000


def test_cursor_prevents_double_counting_in_window():
    """Simulate the main loop: two scans 5s apart pulling the same window.

    Without the cursor the second scan would re-append every trade that
    falls inside the overlap, inflating n_trades. With the cursor, only
    new trades flow into state.
    """
    sub = SubscriptionTrades(subscription_id="cid-1",
                             yes_token_id="tok_yes",
                             no_token_id="tok_no")
    # First scan: window covers 10000-20000ms; recorder has 2 yes trades.
    scan1_trades = [(12000, "tok_yes", Decimal("10")),
                    (15000, "tok_yes", Decimal("15"))]
    window_floor_1 = 20000 - 10000  # 10000
    since_1 = max(window_floor_1, sub.last_ingested_ts_ms + 1)
    for ts, aid, sz in scan1_trades:
        if ts >= since_1:
            sub.record_trade(ts, aid, sz)

    # Second scan 5s later: window 15000-25000ms; recorder returns the same
    # two trades (both still in-window) plus one new.
    scan2_trades = [(12000, "tok_yes", Decimal("10")),   # duplicate
                    (15000, "tok_yes", Decimal("15")),   # duplicate
                    (23000, "tok_yes", Decimal("20"))]   # new
    window_floor_2 = 25000 - 10000  # 15000
    since_2 = max(window_floor_2, sub.last_ingested_ts_ms + 1)  # = 15001
    new_in_scan2 = [t for t in scan2_trades if t[0] >= since_2]
    for ts, aid, sz in new_in_scan2:
        sub.record_trade(ts, aid, sz)

    # Prune to a window that keeps all 3 trades alive.
    sub.prune(now_ms=24000, window_ms=13000)  # cutoff 11000 → keeps 12000, 15000, 23000
    assert len(sub.trades) == 3, f"Expected 3 unique trades, got {len(sub.trades)}"
    total_size = sum(t[2] for t in sub.trades)
    assert total_size == Decimal("45"), f"Expected 45, got {total_size}"


def test_cursor_regression_without_fix_would_double_count():
    """Confirms the bug existed: without cursor, duplicates accumulate."""
    sub = SubscriptionTrades(subscription_id="cid-1",
                             yes_token_id="tok_yes",
                             no_token_id="tok_no")
    # Simulate the OLD buggy pattern: always since_ms = window_floor.
    for _ in range(3):
        for ts, aid, sz in [(12000, "tok_yes", Decimal("10")),
                            (15000, "tok_yes", Decimal("15"))]:
            sub.record_trade(ts, aid, sz)
    sub.prune(now_ms=20000, window_ms=10000)
    # Without the fix we'd have 6 rows (2 trades × 3 scans). With the fix
    # we still get 6 here because we bypassed the cursor guard in this
    # specific regression test. The pair (test above + this test) proves
    # the cursor is doing the work.
    assert len(sub.trades) == 6


# ---------- Finding 2: restart hydrate covers open Orders ----------

def test_hydrate_includes_open_orders_on_restart(tmp_path, monkeypatch):
    """After placing a paper order but before a fill, hydrate should still
    return an OpenPosition stub so the per-market dedup guard binds.
    """
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.db import Base, Order

    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    SF = sessionmaker(bind=engine)

    monkeypatch.setattr("bots.bot_e_btc_scalp.__main__.get_session_factory",
                        lambda: SF)

    # Place a paper order without a matching Position row.
    with SF() as s:
        s.add(Order(
            order_id="paper-abc123",
            bot_id="bot_e",
            condition_id="0xcid-open-order",
            token_id="tok_yes",
            side="BUY",
            price=Decimal("0.05"),
            size=Decimal("600"),
            status="PAPER_OPEN",
            order_type="GTC",
            placed_at=__import__("datetime").datetime.now(
                __import__("datetime").UTC),
            last_updated=__import__("datetime").datetime.now(
                __import__("datetime").UTC),
        ))
        s.commit()

    from bots.bot_e_btc_scalp.__main__ import _hydrate_open_positions
    positions = _hydrate_open_positions()
    assert len(positions) == 1, f"Expected 1 synthetic pos, got {positions}"
    assert positions[0].subscription_id == "0xcid-open-order"
    # notional = price × size = 0.05 × 600 = 30
    assert positions[0].notional_usd == Decimal("30.00")


# ---------- Finding 3: record_outcome fires on resolved positions ----------

def test_record_closed_outcomes_wires_to_trader_state(tmp_path, monkeypatch):
    """A closed Position with a matching SELL Trade should feed outcome
    into state.recent_outcomes via record_outcome()."""
    import datetime as _dt
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.db import Base, Position, Trade

    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    SF = sessionmaker(bind=engine)

    monkeypatch.setattr("bots.bot_e_btc_scalp.__main__.get_session_factory",
                        lambda: SF)
    # Reset the per-test dedup set so repeated runs pick up new positions.
    import bots.bot_e_btc_scalp.__main__ as m
    m._recorded_outcome_position_ids.clear()

    opened = _dt.datetime(2026, 4, 17, 10, 0, tzinfo=_dt.UTC)
    closed_at = _dt.datetime(2026, 4, 17, 10, 15, tzinfo=_dt.UTC)
    with SF() as s:
        s.add(Position(
            bot_id="bot_e", condition_id="0xcid1", token_id="tok_yes",
            side="YES", size=Decimal("0"), avg_price=Decimal("0.05"),
            cost_basis_usd=Decimal("30"), status="CLOSED",
            opened_at=opened, closed_at=closed_at,
        ))
        # Losing exit: sold for proceeds < cost.
        s.add(Trade(
            trade_id="t1", bot_id="bot_e", order_id="paper-1",
            condition_id="0xcid1", token_id="tok_yes", side="SELL",
            price=Decimal("0.04"), size=Decimal("600"),
            fee_usd=Decimal("0"), filled_at=closed_at,
            usd_gbp_rate=Decimal("1.25"), gbp_notional=Decimal("20"),
        ))
        s.commit()

    from bots.bot_e_btc_scalp.executor import TraderState
    state = TraderState()
    assert state.recent_outcomes == []
    assert state.consecutive_losses == 0

    n = m._record_closed_outcomes(state)
    assert n == 1
    # 0.04 * 600 = 24 proceeds; cost 30 → loss. win=False.
    assert state.recent_outcomes == [False]
    assert state.consecutive_losses == 1


# ---------- Finding 4: depth gate accepts OrderBook object ----------

def test_depth_gate_accepts_orderbook_dataclass(monkeypatch):
    """Passing an OrderBook dataclass (the shape the main loop has) should
    compute depth correctly, not silently fail-open."""
    from core.clob import OrderBook
    import bots.bot_e_btc_scalp.__main__ as m
    from bots.bot_e_btc_scalp import config as _cfg

    monkeypatch.setattr(_cfg, "BOT_E_DEPTH_GATE", True)
    monkeypatch.setattr(_cfg, "BOT_E_DEPTH_MIN_USD", Decimal("100"))
    monkeypatch.setattr(_cfg, "BOT_E_DEPTH_BAND_WIDTH", Decimal("0.02"))

    # Thick book — three bid levels inside the band.
    book = OrderBook(
        token_id="t",
        bids=[(Decimal("0.50"), Decimal("200")),   # 100 USD
              (Decimal("0.49"), Decimal("500")),   # 245 USD
              (Decimal("0.30"), Decimal("9999"))], # out-of-band, skipped
        asks=[(Decimal("0.51"), Decimal("100"))],
        timestamp=time.time(),
    )
    ok, reason = m._depth_gate_ok(book, "BUY_YES", Decimal("0.50"))
    assert ok, f"Expected thick book to pass, got {reason}"
    assert "depth_ok" in reason

    # Thin book — only one tiny level in-band.
    thin = OrderBook(
        token_id="t",
        bids=[(Decimal("0.50"), Decimal("10"))],  # 5 USD < 100 min
        asks=[],
        timestamp=time.time(),
    )
    ok, reason = m._depth_gate_ok(thin, "BUY_YES", Decimal("0.50"))
    assert not ok, f"Expected thin book to block, got {reason}"
    assert "depth_thin" in reason


def test_depth_gate_dict_backcompat(monkeypatch):
    """Raw dict shape still works (for any legacy callers)."""
    import bots.bot_e_btc_scalp.__main__ as m
    from bots.bot_e_btc_scalp import config as _cfg

    monkeypatch.setattr(_cfg, "BOT_E_DEPTH_GATE", True)
    monkeypatch.setattr(_cfg, "BOT_E_DEPTH_MIN_USD", Decimal("100"))
    monkeypatch.setattr(_cfg, "BOT_E_DEPTH_BAND_WIDTH", Decimal("0.02"))

    book = {"bids": [{"price": "0.50", "size": "500"}]}
    ok, reason = m._depth_gate_ok(book, "BUY_YES", Decimal("0.50"))
    assert ok, reason


def test_depth_gate_none_still_fails_open():
    """None book → fail-open remains the documented behaviour."""
    import bots.bot_e_btc_scalp.__main__ as m
    ok, reason = m._depth_gate_ok(None, "BUY_YES", Decimal("0.50"))
    assert ok
    assert "depth_unavailable" in reason


# ---------- Finding 5: recorder freshness watchdog ----------

def test_recorder_freshness_check_passes_on_recent_events(tmp_path, monkeypatch):
    """Fresh pm_events (age < 300s) → check passes."""
    import sqlite3
    db_file = tmp_path / "recorder.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE pm_events (received_at_ms INTEGER)")
    now_ms = int(time.time() * 1000)
    conn.execute("INSERT INTO pm_events VALUES (?)", (now_ms - 60_000,))  # 60s ago
    conn.commit()
    conn.close()

    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(db_file))

    from core.watchdog import Watchdog, WatchdogConfig
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("100"),
        bot_b_initial_usd=Decimal("100"),
    )
    wd = Watchdog.__new__(Watchdog)  # skip __init__ side-effects
    wd.cfg = cfg
    result = wd._check_recorder_freshness()
    assert result.ok


def test_recorder_freshness_check_fires_on_stale_events(tmp_path, monkeypatch):
    """pm_events last write > 300s ago → kill, scoped to bot_e only."""
    import sqlite3
    db_file = tmp_path / "recorder.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE pm_events (received_at_ms INTEGER)")
    stale_ms = int(time.time() * 1000) - 600_000  # 10 min ago
    conn.execute("INSERT INTO pm_events VALUES (?)", (stale_ms,))
    conn.commit()
    conn.close()

    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(db_file))

    from core.watchdog import Watchdog, WatchdogConfig
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("100"),
        bot_b_initial_usd=Decimal("100"),
    )
    wd = Watchdog.__new__(Watchdog)
    wd.cfg = cfg
    result = wd._check_recorder_freshness()
    assert not result.ok
    assert result.severity == "kill"
    assert result.scope_bots == ["bot_e"]
    assert "stale" in result.message.lower()


def test_recorder_freshness_check_skips_when_db_absent(tmp_path, monkeypatch):
    """No recorder DB → check passes (dev machine case)."""
    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(tmp_path / "nonexistent.db"))

    from core.watchdog import Watchdog, WatchdogConfig
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("100"),
        bot_b_initial_usd=Decimal("100"),
    )
    wd = Watchdog.__new__(Watchdog)
    wd.cfg = cfg
    result = wd._check_recorder_freshness()
    assert result.ok
