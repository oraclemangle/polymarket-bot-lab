from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def test_cancel_autopsy_counts_ttl_and_offset_scenarios(tmp_path):
    from scripts.bot_e_cancel_autopsy import run_autopsy

    db = tmp_path / "main.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                bot_id TEXT,
                condition_id TEXT,
                token_id TEXT,
                side TEXT,
                price NUMERIC,
                size NUMERIC,
                status TEXT,
                placed_at TEXT,
                last_updated TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE books (
                token_id TEXT,
                snapshot_at TEXT,
                bids TEXT,
                asks TEXT
            )
            """
        )
        now = datetime.now(UTC) - timedelta(minutes=5)
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "paper-1",
                "bot_e",
                "cid",
                "tok",
                "BUY",
                "0.499",
                "10",
                "CANCELLED",
                _iso(now),
                _iso(now + timedelta(minutes=5)),
            ),
        )
        # Does not fill at 0.499 within 300s, but does fill at 0.500.
        conn.execute(
            "INSERT INTO books VALUES (?, ?, ?, ?)",
            (
                "tok",
                _iso(now + timedelta(seconds=10)),
                json.dumps([["0.498", "10"]]),
                json.dumps([["0.500", "100"]]),
            ),
        )
        conn.execute(
            "INSERT INTO books VALUES (?, ?, ?, ?)",
            (
                "tok",
                _iso(now + timedelta(seconds=40)),
                json.dumps([["0.490", "10"]]),
                json.dumps([["0.501", "10"]]),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    report = run_autopsy(
        db,
        bot_id="bot_e",
        lookback_hours=1,
        ttls=[300.0],
        offsets=[Decimal("0.001"), Decimal("0.000")],
        baseline_offset=Decimal("0.001"),
        adverse_horizons=[30.0],
    )

    assert report["orders_seen"] == 1
    assert report["scenarios"]["ttl=300s offset=0.001"]["orders_with_book_coverage"] == 1
    assert report["scenarios"]["ttl=300s offset=0.001"]["would_fill"] == 0
    less_passive = report["scenarios"]["ttl=300s offset=0.000"]
    assert less_passive["would_fill"] == 1
    assert less_passive["capacity"]["targets_usd"]["25"]["covered"] == 1
    assert less_passive["capacity"]["targets_usd"]["50"]["covered"] == 1
    assert less_passive["adverse"]["30"]["adverse"] == 1


def test_bot_e_zero_maker_offset_is_valid(monkeypatch):
    import bots.bot_e_btc_scalp.config as cfg

    monkeypatch.setattr(cfg, "BOT_E_MAKER_OFFSET", Decimal("0"))
    errors = cfg.validate()
    assert "BOT_E_MAKER_OFFSET must be non-negative" not in errors
