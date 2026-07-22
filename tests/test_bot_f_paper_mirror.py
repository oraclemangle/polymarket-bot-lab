"""Tests for bots/bot_f/paper_mirror.py — Step 1 of ADR-037 Bot F graduation."""
from __future__ import annotations

import os
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from bots.bot_f import paper_mirror


def test_sharps_allowlist_is_frozenset_of_4():
    """Guard against accidental expansion. Adding a wallet needs an ADR."""
    assert isinstance(paper_mirror.SHARPS_ALLOWLIST, frozenset)
    assert len(paper_mirror.SHARPS_ALLOWLIST) == 4


def test_sharps_allowlist_excludes_suspicious_100pct_wallet():
    """The 0xe9ad918c wallet had 100% WR / 28 closes — almost certainly a
    market maker or contract wallet. Must NOT be mirrored."""
    banned = "0xF00D000000000000000000000000000000000018"
    assert banned not in paper_mirror.SHARPS_ALLOWLIST


def test_assert_paper_mode_exits_when_env_missing(monkeypatch, capsys):
    monkeypatch.delenv("BOT_F_MIRROR_ENV", raising=False)
    with pytest.raises(SystemExit) as e:
        paper_mirror._assert_paper_mode()
    assert e.value.code == 2
    captured = capsys.readouterr()
    assert "paper" in captured.err.lower()


def test_assert_paper_mode_exits_when_env_is_live(monkeypatch):
    monkeypatch.setenv("BOT_F_MIRROR_ENV", "live")
    with pytest.raises(SystemExit) as e:
        paper_mirror._assert_paper_mode()
    assert e.value.code == 2


def test_assert_paper_mode_passes_when_env_is_paper(monkeypatch):
    monkeypatch.setenv("BOT_F_MIRROR_ENV", "paper")
    # Should not raise.
    paper_mirror._assert_paper_mode()


def test_read_new_signals_filters_to_allowlist(tmp_path):
    """Signals from non-allowlist wallets must be skipped even if they're
    would_have_traded=1."""
    db = tmp_path / "bot_f.db"
    c = sqlite3.connect(str(db))
    c.executescript(
        """
        CREATE TABLE mirror_signals (
            id INTEGER PRIMARY KEY,
            detected_at DATETIME,
            wallet TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size_shares REAL,
            whale_tx_ts INTEGER,
            signal_age_ms INTEGER,
            would_have_traded INTEGER
        );
        """
    )
    allow = next(iter(paper_mirror.SHARPS_ALLOWLIST))
    c.executemany(
        "INSERT INTO mirror_signals (detected_at, wallet, condition_id, token_id, "
        "side, price, size_shares, whale_tx_ts, signal_age_ms, would_have_traded) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("2026-04-22 17:00:00", allow, "0xabc", "tok1", "BUY", 0.5, 10, 0, 30000, 1),
            ("2026-04-22 17:00:01", "0xNOT_ALLOWED", "0xdef", "tok2", "BUY", 0.6, 10, 0, 45000, 1),
            ("2026-04-22 17:00:02", allow, "0xxyz", "tok3", "BUY", 0.4, 10, 0, 50000, 0),  # not wtrd
        ],
    )
    c.commit()
    c.close()

    import datetime as dt
    cutoff = dt.datetime(2026, 4, 22, 16, 59, 0, tzinfo=dt.timezone.utc)
    results = paper_mirror._read_new_signals(db, cutoff)
    # Only the first row survives: allowlist + would_have_traded=1.
    assert len(results) == 1
    assert results[0]["condition_id"] == "0xabc"
    assert results[0]["wallet"] == allow


def test_read_new_signals_no_db(tmp_path):
    """Returns empty list, does not raise, when DB does not exist."""
    import datetime as dt
    cutoff = dt.datetime(2026, 4, 22, tzinfo=dt.timezone.utc)
    out = paper_mirror._read_new_signals(tmp_path / "nope.db", cutoff)
    assert out == []


def test_read_new_signals_matches_checksummed_wallet(tmp_path):
    """Polymarket data-api returns checksummed addresses (0x17Db3fCd...).
    Our allowlist is lowercase. Security review found that the match was
    case-sensitive — legitimate signals were silently dropped. Regression
    test: a checksummed version of an allowlisted wallet must now match.
    """
    import sqlite3
    import datetime as dt

    db = tmp_path / "bot_f.db"
    c = sqlite3.connect(str(db))
    c.executescript(
        """
        CREATE TABLE mirror_signals (
            id INTEGER PRIMARY KEY,
            detected_at DATETIME,
            wallet TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size_shares REAL,
            whale_tx_ts INTEGER,
            signal_age_ms INTEGER,
            would_have_traded INTEGER
        );
        """
    )
    allow_lower = next(iter(paper_mirror.SHARPS_ALLOWLIST))
    # Build the checksummed form by mixing case.
    checksummed = "0x" + "".join(
        ch.upper() if i % 2 == 0 else ch
        for i, ch in enumerate(allow_lower[2:])
    )
    assert checksummed != allow_lower  # sanity: they're not the same string

    c.execute(
        "INSERT INTO mirror_signals (detected_at, wallet, condition_id, token_id, "
        "side, price, size_shares, whale_tx_ts, signal_age_ms, would_have_traded) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-04-22 17:00:00", checksummed, "0xabc", "tok1", "BUY", 0.5, 10, 0, 30000, 1),
    )
    c.commit()
    c.close()

    cutoff = dt.datetime(2026, 4, 22, 16, 59, 0, tzinfo=dt.timezone.utc)
    results = paper_mirror._read_new_signals(db, cutoff)
    # Must match and return normalised-lowercase wallet.
    assert len(results) == 1
    assert results[0]["wallet"] == allow_lower  # normalised in output


class _FakeClob:
    """Minimal spy: records the call form without importing the real wrapper."""
    def __init__(self):
        self.paper_override = True
        self.calls = []

    def place_limit(self, *, token_id, price, size, side, order_type):
        self.calls.append({
            "token_id": token_id, "price": price, "size": size,
            "side": side, "order_type": order_type,
        })
        class R:
            order_id = "paper-test-123"
        return R()


def test_mirror_signal_uses_positional_kwargs_not_orderargs(tmp_db):
    """Security review found paper_mirror called clob.place_limit(OrderArgs(...)),
    but ClobWrapper.place_limit takes positional (token_id, price, size, side,
    order_type). Regression test: the call must succeed with kwarg form and
    pass Side enum, not a string.
    """
    from core.clob import Side, OrderType
    from decimal import Decimal

    fake_clob = _FakeClob()
    sig = {
        "wallet": "0xtest",
        "condition_id": "0xabc",
        "token_id": "tok1",
        "side": "BUY",
        "price": 0.5,
    }
    placed = paper_mirror._mirror_signal(
        sig=sig,
        clob=fake_clob,
        portfolio=None,
        trade_size_usd=Decimal("5"),
        recent=set(),
    )
    assert placed is True
    assert len(fake_clob.calls) == 1
    call = fake_clob.calls[0]
    assert call["token_id"] == "tok1"
    assert call["side"] is Side.BUY  # enum, not string
    assert call["order_type"] is OrderType.GTC
    assert call["price"] == Decimal("0.5")


def test_mirror_signal_maps_sell_side(tmp_db):
    from core.clob import Side
    from decimal import Decimal
    fake_clob = _FakeClob()
    sig = {"wallet": "0x", "condition_id": "0x", "token_id": "t", "side": "SELL", "price": 0.6}
    paper_mirror._mirror_signal(
        sig=sig, clob=fake_clob, portfolio=None, trade_size_usd=Decimal("5"),
        recent=set(),
    )
    assert fake_clob.calls[0]["side"] is Side.SELL


def test_mirror_signal_refuses_non_paper_clob():
    """Layer 3 of the paper-mode lock: even if a non-paper ClobWrapper
    somehow reached this function, place_limit must not be called."""
    from decimal import Decimal
    fake_clob = _FakeClob()
    fake_clob.paper_override = False
    sig = {"wallet": "0x", "condition_id": "0x", "token_id": "t", "side": "BUY", "price": 0.5}
    placed = paper_mirror._mirror_signal(
        sig=sig, clob=fake_clob, portfolio=None, trade_size_usd=Decimal("5"),
        recent=set(),
    )
    assert placed is False
    assert fake_clob.calls == []


def test_mirror_signal_dedup_blocks_second_same_market_side(tmp_db):
    """Regression test for the `_recent_mirrors` guard wired in during the
    Session 20 audit remediation. Two signals on the same (condition_id,
    side) produce one place_limit call; the second is a no-op."""
    from decimal import Decimal
    fake_clob = _FakeClob()
    sig = {"wallet": "0x", "condition_id": "0xdup", "token_id": "t", "side": "BUY", "price": 0.5}
    recent: set[tuple[str, str, str]] = set()
    first = paper_mirror._mirror_signal(
        sig=sig, clob=fake_clob, portfolio=None, trade_size_usd=Decimal("5"),
        recent=recent,
    )
    second = paper_mirror._mirror_signal(
        sig=sig, clob=fake_clob, portfolio=None, trade_size_usd=Decimal("5"),
        recent=recent,
    )
    assert first is True
    assert second is False
    assert len(fake_clob.calls) == 1


# ---------------------------------------------------------------------------
# T2-E: trailing-stop + staleness + proximity-to-resolution filters (2026-04-23)
# ---------------------------------------------------------------------------


def _make_recorder_fixture(tmp_path, *, rows_pm=None, rows_mk=None) -> Path:
    """Create a minimal recorder DB with pm_events + markets tables."""
    path = tmp_path / "recorder.db"
    c = sqlite3.connect(str(path))
    c.execute(
        "CREATE TABLE pm_events ("
        "received_at_ms INTEGER, event_type TEXT, asset_id TEXT,"
        " condition_id TEXT, payload_json TEXT)"
    )
    c.execute(
        "CREATE TABLE markets ("
        "scan_at_ms INTEGER, condition_id TEXT, end_date_iso TEXT,"
        " yes_token_id TEXT, no_token_id TEXT)"
    )
    for r in (rows_pm or []):
        c.execute(
            "INSERT INTO pm_events (received_at_ms, event_type, asset_id,"
            " condition_id, payload_json) VALUES (?,?,?,?,?)",
            (r["received_at_ms"], r["event_type"], r["asset_id"],
             r.get("condition_id"), r["payload_json"]),
        )
    for r in (rows_mk or []):
        c.execute(
            "INSERT INTO markets (scan_at_ms, condition_id, end_date_iso,"
            " yes_token_id, no_token_id) VALUES (?,?,?,?,?)",
            (r["scan_at_ms"], r["condition_id"], r["end_date_iso"],
             r.get("yes_token_id"), r.get("no_token_id")),
        )
    c.commit()
    c.close()
    return path


def test_current_ask_reads_price_change(tmp_path, monkeypatch):
    import time as t
    import json
    now_ms = int(t.time() * 1000)
    db = _make_recorder_fixture(tmp_path, rows_pm=[
        {
            "received_at_ms": now_ms - 5000,
            "event_type": "price_change",
            "asset_id": "tokA",
            "condition_id": None,
            "payload_json": json.dumps({
                "market": "cidA",
                "price_changes": [
                    {"asset_id": "tokA", "best_bid": "0.30", "best_ask": "0.32"}
                ],
            }),
        },
    ])
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db))
    ask = paper_mirror._current_ask_from_recorder("tokA", "cidA")
    assert ask == Decimal("0.32")


def test_current_ask_returns_none_when_stale(tmp_path, monkeypatch):
    import time as t
    import json
    now_ms = int(t.time() * 1000)
    db = _make_recorder_fixture(tmp_path, rows_pm=[
        {
            "received_at_ms": now_ms - 200_000,  # >120s cutoff
            "event_type": "best_bid_ask",
            "asset_id": "tokA",
            "condition_id": None,
            "payload_json": json.dumps({"best_bid": "0.30", "best_ask": "0.32"}),
        },
    ])
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db))
    assert paper_mirror._current_ask_from_recorder("tokA", "cidA") is None


def test_entry_ttr_blocks_too_close_to_resolution(tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    # Market resolves in 60s — below default MIN_TTR_FOR_ENTRY_SECONDS (300)
    end_iso = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    db = _make_recorder_fixture(tmp_path, rows_mk=[
        {"scan_at_ms": 1, "condition_id": "cidX",
         "end_date_iso": end_iso, "yes_token_id": "y", "no_token_id": "n"},
    ])
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db))
    ok, reason = paper_mirror._entry_ttr_ok("cidX")
    assert ok is False
    assert "ttr=" in reason


def test_entry_ttr_allows_far_future_resolution(tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    end_iso = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    db = _make_recorder_fixture(tmp_path, rows_mk=[
        {"scan_at_ms": 1, "condition_id": "cidY",
         "end_date_iso": end_iso, "yes_token_id": "y", "no_token_id": "n"},
    ])
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db))
    ok, reason = paper_mirror._entry_ttr_ok("cidY")
    assert ok is True
    assert reason == "ok"


def test_entry_ttr_unknown_market_allows(tmp_path, monkeypatch):
    """Absence of market data in recorder must NOT block — the gate is
    advisory; the existing ingest-side checks remain authoritative."""
    db = _make_recorder_fixture(tmp_path)  # empty
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db))
    ok, reason = paper_mirror._entry_ttr_ok("cidMissing")
    assert ok is True


def test_mirror_signal_rejects_stale_signal(monkeypatch, tmp_db):
    """Signal with signal_age_ms > MAX_SIGNAL_AGE_SECONDS must be rejected."""
    fake_clob = _FakeClob()
    sig = {
        "wallet": "0xstale", "condition_id": "0xccc", "token_id": "tok",
        "side": "BUY", "price": 0.5,
        "signal_age_ms": 200_000,  # 200s, well beyond 90s default
    }
    placed = paper_mirror._mirror_signal(
        sig=sig, clob=fake_clob, portfolio=None,
        trade_size_usd=Decimal("5"), recent=set(),
    )
    assert placed is False
    assert fake_clob.calls == []


def test_mirror_signal_allows_fresh_signal(monkeypatch, tmp_db):
    fake_clob = _FakeClob()
    sig = {
        "wallet": "0xfresh", "condition_id": "0xddd", "token_id": "tok",
        "side": "BUY", "price": 0.5,
        "signal_age_ms": 30_000,  # 30s, well inside 90s default
    }
    placed = paper_mirror._mirror_signal(
        sig=sig, clob=fake_clob, portfolio=None,
        trade_size_usd=Decimal("5"), recent=set(),
    )
    assert placed is True


def test_crossing_recorder_ask_creates_position(tmp_db, monkeypatch):
    from datetime import datetime, timezone

    from core import portfolio as portfolio_mod
    from core.db import Market, Order, Position, get_session_factory
    from core.portfolio import Portfolio
    from sqlalchemy import select

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))
    monkeypatch.setattr(paper_mirror, "_current_ask_from_recorder", lambda *_a, **_k: Decimal("0.51"))

    sf = get_session_factory()
    with sf() as s:
        s.add(Market(
            condition_id="cidFill",
            category="politics",
            question="q",
            yes_token_id="tokFill",
            no_token_id="noTok",
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=datetime.now(timezone.utc),
        ))
        s.commit()

    fake_clob = _FakeClob()
    sig = {
        "wallet": "0xfresh",
        "condition_id": "cidFill",
        "token_id": "tokFill",
        "side": "BUY",
        "price": 0.50,
        "signal_age_ms": 30_000,
    }

    placed = paper_mirror._mirror_signal(
        sig=sig,
        clob=fake_clob,
        portfolio=Portfolio(),
        trade_size_usd=Decimal("5"),
        recent=set(),
    )

    assert placed is True
    assert fake_clob.calls[0]["price"] == Decimal("0.51")
    with sf() as s:
        order = s.scalars(select(Order).where(
            Order.bot_id == paper_mirror.BOT_ID,
            Order.condition_id == "cidFill",
        )).one()
        pos = s.scalars(select(Position).where(
            Position.bot_id == paper_mirror.BOT_ID,
            Position.condition_id == "cidFill",
        )).one()
        assert order.status == "FILLED"
        assert pos.status == "OPEN"
        assert pos.avg_price == Decimal("0.51")


def test_recorder_ask_above_slippage_band_skips_copy(tmp_db, monkeypatch):
    from core.portfolio import Portfolio

    fake_clob = _FakeClob()
    monkeypatch.setattr(paper_mirror, "_current_ask_from_recorder", lambda *_a, **_k: Decimal("0.55"))

    sig = {
        "wallet": "0xfresh",
        "condition_id": "cidSlip",
        "token_id": "tokSlip",
        "side": "BUY",
        "price": 0.50,
        "signal_age_ms": 30_000,
    }

    placed = paper_mirror._mirror_signal(
        sig=sig,
        clob=fake_clob,
        portfolio=Portfolio(),
        trade_size_usd=Decimal("5"),
        recent=set(),
    )

    assert placed is False
    assert fake_clob.calls == []


def test_trailing_stop_arms_after_peak_and_exits_on_drawdown(tmp_db, monkeypatch, tmp_path):
    """Full-path trailing-stop test: buy at 0.30, price rises to 0.50,
    falls back to 0.39 (22% off peak) — stop must fire."""
    import json
    from datetime import datetime, timezone
    from core.db import Position, get_session_factory
    from core.portfolio import Portfolio

    sf = get_session_factory()
    with sf() as s:
        pos = Position(
            bot_id=paper_mirror.BOT_ID,
            condition_id="cidTrail",
            token_id="tokTrail",
            side="YES",
            size=Decimal("16.67"),  # ~$5 / 0.30
            avg_price=Decimal("0.30"),
            cost_basis_usd=Decimal("5.00"),
            status="OPEN",
            opened_at=datetime.now(timezone.utc),
        )
        s.add(pos)
        s.commit()
        pos_id = pos.id

    import time as t
    now_ms = int(t.time() * 1000)
    # Step 1: book at 0.50 — peak rises, no exit yet
    db = _make_recorder_fixture(tmp_path, rows_pm=[{
        "received_at_ms": now_ms - 1000, "event_type": "price_change",
        "asset_id": "tokTrail", "condition_id": None,
        "payload_json": json.dumps({
            "market": "cidTrail",
            "price_changes": [{"asset_id": "tokTrail",
                               "best_bid": "0.49", "best_ask": "0.50"}],
        }),
    }])
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db))
    paper_mirror._POSITION_PEAK_PRICE.clear()
    exits = paper_mirror._update_trailing_stops(Portfolio())
    assert exits == 0
    assert paper_mirror._POSITION_PEAK_PRICE[pos_id] == Decimal("0.50")

    # Step 2: book drops to 0.39 (22% below 0.50 peak), default stop is 20%
    sub = tmp_path / "r2"
    sub.mkdir()
    db2 = _make_recorder_fixture(sub, rows_pm=[{
        "received_at_ms": now_ms - 500, "event_type": "price_change",
        "asset_id": "tokTrail", "condition_id": None,
        "payload_json": json.dumps({
            "market": "cidTrail",
            "price_changes": [{"asset_id": "tokTrail",
                               "best_bid": "0.38", "best_ask": "0.39"}],
        }),
    }])
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db2))
    exits = paper_mirror._update_trailing_stops(Portfolio())
    assert exits == 1
    # Position should now be CLOSED
    with sf() as s:
        pos = s.get(Position, pos_id)
        assert pos.status == "CLOSED"


def test_trailing_stop_does_not_fire_before_min_unrealised(tmp_db, monkeypatch, tmp_path):
    """If price dips but peak never exceeded entry by MIN_UNREALISED_FOR_STOP_PCT,
    trailing stop is not armed. max-drawdown gate is separate."""
    import json
    from datetime import datetime, timezone
    from core.db import Position, get_session_factory
    from core.portfolio import Portfolio

    sf = get_session_factory()
    with sf() as s:
        pos = Position(
            bot_id=paper_mirror.BOT_ID, condition_id="cidQuiet",
            token_id="tokQuiet", side="YES",
            size=Decimal("10"), avg_price=Decimal("0.50"),
            cost_basis_usd=Decimal("5.00"), status="OPEN",
            opened_at=datetime.now(timezone.utc),
        )
        s.add(pos)
        s.commit()
        pos_id = pos.id

    import time as t
    now_ms = int(t.time() * 1000)
    # Current price 0.45 → dip of 10% from entry, but MAX_DD default is 40%
    # so neither trailing nor max-DD fires.
    db = _make_recorder_fixture(tmp_path, rows_pm=[{
        "received_at_ms": now_ms - 500, "event_type": "price_change",
        "asset_id": "tokQuiet", "condition_id": None,
        "payload_json": json.dumps({
            "market": "cidQuiet",
            "price_changes": [{"asset_id": "tokQuiet",
                               "best_bid": "0.44", "best_ask": "0.45"}],
        }),
    }])
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db))
    paper_mirror._POSITION_PEAK_PRICE.clear()
    exits = paper_mirror._update_trailing_stops(Portfolio())
    assert exits == 0
    with sf() as s:
        pos = s.get(Position, pos_id)
        assert pos.status == "OPEN"


def test_max_drawdown_fires_even_without_peak_gain(tmp_db, monkeypatch, tmp_path):
    """Hard drawdown floor: price drops 45% below entry → exit regardless
    of whether the trailing stop has been armed."""
    import json
    from datetime import datetime, timezone
    from core.db import Position, get_session_factory
    from core.portfolio import Portfolio

    sf = get_session_factory()
    with sf() as s:
        pos = Position(
            bot_id=paper_mirror.BOT_ID, condition_id="cidPlunge",
            token_id="tokPlunge", side="YES",
            size=Decimal("10"), avg_price=Decimal("0.50"),
            cost_basis_usd=Decimal("5.00"), status="OPEN",
            opened_at=datetime.now(timezone.utc),
        )
        s.add(pos)
        s.commit()
        pos_id = pos.id

    import time as t
    now_ms = int(t.time() * 1000)
    db = _make_recorder_fixture(tmp_path, rows_pm=[{
        "received_at_ms": now_ms - 500, "event_type": "price_change",
        "asset_id": "tokPlunge", "condition_id": None,
        "payload_json": json.dumps({
            "market": "cidPlunge",
            "price_changes": [{"asset_id": "tokPlunge",
                               "best_bid": "0.26", "best_ask": "0.27"}],  # -46%
        }),
    }])
    monkeypatch.setenv("BOT_E_RECORDER_DB", str(db))
    paper_mirror._POSITION_PEAK_PRICE.clear()
    exits = paper_mirror._update_trailing_stops(Portfolio())
    assert exits == 1
    with sf() as s:
        pos = s.get(Position, pos_id)
        assert pos.status == "CLOSED"
