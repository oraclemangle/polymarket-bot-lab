from __future__ import annotations

import csv
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.bot_e_fill_conditioned_replay import run_replay, write_csv


def _ms(dt: datetime) -> int:
    return int(dt.astimezone(UTC).timestamp() * 1000)


def _make_recorder_db(tmp_path: Path) -> Path:
    db = tmp_path / "recorder.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE pm_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at_ms INTEGER NOT NULL,
                subscription_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                asset_id TEXT,
                condition_id TEXT,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE cex_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at_ms INTEGER NOT NULL,
                trade_time_ms INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                size REAL NOT NULL,
                is_buyer_maker INTEGER NOT NULL
            );
            CREATE TABLE markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_at_ms INTEGER NOT NULL,
                condition_id TEXT NOT NULL,
                question TEXT NOT NULL,
                end_date_iso TEXT,
                yes_token_id TEXT,
                no_token_id TEXT,
                volume_24h_usd REAL,
                yes_price REAL,
                category TEXT DEFAULT 'crypto',
                raw_json TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _make_main_db(tmp_path: Path) -> Path:
    db = tmp_path / "main.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                bot_id TEXT,
                condition_id TEXT,
                token_id TEXT,
                side TEXT,
                price NUMERIC,
                status TEXT,
                placed_at TEXT,
                last_updated TEXT
            );
            CREATE TABLE trades (
                trade_id TEXT PRIMARY KEY,
                bot_id TEXT,
                order_id TEXT,
                condition_id TEXT,
                token_id TEXT,
                side TEXT,
                price NUMERIC,
                filled_at TEXT
            );
            CREATE TABLE books (
                token_id TEXT,
                snapshot_at TEXT,
                asks TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _insert_market(
    conn: sqlite3.Connection,
    *,
    condition_id: str,
    start: datetime,
    end: datetime,
    yes_token: str,
    no_token: str,
) -> None:
    conn.execute(
        """
        INSERT INTO markets (
            scan_at_ms, condition_id, question, end_date_iso, yes_token_id,
            no_token_id, volume_24h_usd, yes_price, category, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _ms(start),
            condition_id,
            "Bitcoin Up or Down - May 3, 12:00PM-12:15PM ET",
            end.isoformat(),
            yes_token,
            no_token,
            1000.0,
            0.5,
            "crypto",
            "{}",
        ),
    )


def _insert_trade_event(
    conn: sqlite3.Connection,
    *,
    ts_ms: int,
    sub_id: str,
    asset_id: str,
    condition_id: str,
    price: float,
    size: float,
) -> None:
    conn.execute(
        """
        INSERT INTO pm_events (
            received_at_ms, subscription_id, event_type, asset_id,
            condition_id, payload_json
        ) VALUES (?, ?, 'last_trade_price', ?, ?, ?)
        """,
        (ts_ms, sub_id, asset_id, condition_id, json.dumps({"price": price, "size": size})),
    )


def _insert_book_event(
    conn: sqlite3.Connection,
    *,
    ts_ms: int,
    sub_id: str,
    asset_id: str,
    condition_id: str,
) -> None:
    conn.execute(
        """
        INSERT INTO pm_events (
            received_at_ms, subscription_id, event_type, asset_id,
            condition_id, payload_json
        ) VALUES (?, ?, 'book', ?, ?, ?)
        """,
        (
            ts_ms,
            sub_id,
            asset_id,
            condition_id,
            json.dumps({"bids": [["0.50", "10"]], "asks": [["0.50", "100"]]}),
        ),
    )


def _insert_main_order(
    conn: sqlite3.Connection,
    *,
    order_id: str,
    condition_id: str,
    token_id: str,
    side: str,
    price: float,
    status: str,
    placed_at: datetime,
    last_updated: datetime,
) -> None:
    conn.execute(
        """
        INSERT INTO orders (
            order_id, bot_id, condition_id, token_id, side, price, status,
            placed_at, last_updated
        ) VALUES (?, 'bot_e', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            condition_id,
            token_id,
            side,
            price,
            status,
            placed_at.strftime("%Y-%m-%d %H:%M:%S.%f"),
            last_updated.strftime("%Y-%m-%d %H:%M:%S.%f"),
        ),
    )


def _insert_main_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: str,
    order_id: str,
    condition_id: str,
    token_id: str,
    side: str,
    price: float,
    filled_at: datetime,
) -> None:
    conn.execute(
        """
        INSERT INTO trades (
            trade_id, bot_id, order_id, condition_id, token_id, side, price,
            filled_at
        ) VALUES (?, 'bot_e', ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            order_id,
            condition_id,
            token_id,
            side,
            price,
            filled_at.strftime("%Y-%m-%d %H:%M:%S.%f"),
        ),
    )


def _insert_main_book(
    conn: sqlite3.Connection,
    *,
    token_id: str,
    snapshot_at: datetime,
) -> None:
    conn.execute(
        "INSERT INTO books VALUES (?, ?, ?)",
        (
            token_id,
            snapshot_at.strftime("%Y-%m-%d %H:%M:%S.%f"),
            json.dumps([["0.50", "100"]]),
        ),
    )


def _insert_cex_outcome(
    conn: sqlite3.Connection,
    *,
    start: datetime,
    end: datetime,
    start_price: float = 100.0,
    end_price: float = 101.0,
) -> None:
    for dt, price in ((start, start_price), (end, end_price)):
        conn.execute(
            """
            INSERT INTO cex_trades (
                received_at_ms, trade_time_ms, symbol, price, size, is_buyer_maker
            ) VALUES (?, ?, 'BTCUSDT', ?, 1.0, 0)
            """,
            (_ms(dt), _ms(dt), price),
        )


def _base_times() -> tuple[datetime, datetime, int]:
    start = datetime(2026, 5, 3, 16, 0, tzinfo=UTC)
    end = start + timedelta(minutes=15)
    t0_ms = _ms(end - timedelta(minutes=6))
    return start, end, t0_ms


def test_no_fill_rows_are_included(tmp_path: Path):
    db = _make_recorder_db(tmp_path)
    start, end, t0_ms = _base_times()
    conn = sqlite3.connect(db)
    try:
        _insert_market(
            conn,
            condition_id="cid-no-fill",
            start=start,
            end=end,
            yes_token="yes-no-fill",
            no_token="no-no-fill",
        )
        _insert_cex_outcome(conn, start=start, end=end)
        _insert_trade_event(
            conn,
            ts_ms=t0_ms - 1000,
            sub_id="btc-sig",
            asset_id="yes-no-fill",
            condition_id="cid-no-fill",
            price=0.52,
            size=3,
        )
        _insert_trade_event(
            conn,
            ts_ms=t0_ms,
            sub_id="btc-sig",
            asset_id="yes-no-fill",
            condition_id="cid-no-fill",
            price=0.52,
            size=3,
        )
        _insert_trade_event(
            conn,
            ts_ms=t0_ms + 10_000,
            sub_id="btc-fill-feed",
            asset_id="yes-no-fill",
            condition_id="cid-no-fill",
            price=0.515,
            size=0,
        )
        conn.commit()
    finally:
        conn.close()

    report = run_replay(db, since_ms=_ms(start), until_ms=_ms(end), fill_timeout_sec=60)

    assert report["summary"]["signals"] == 1
    row = report["rows"][0]
    assert row["filled"] is False
    assert row["fill_delay_sec"] is None
    assert "no_crossing_trade_within_timeout" in row["notes"]


def test_filled_rows_get_delay_adverse_depth_and_outcome(tmp_path: Path):
    db = _make_recorder_db(tmp_path)
    start, end, t0_ms = _base_times()
    fill_ms = t0_ms + 20_000
    conn = sqlite3.connect(db)
    try:
        _insert_market(
            conn,
            condition_id="cid-fill",
            start=start,
            end=end,
            yes_token="yes-fill",
            no_token="no-fill",
        )
        _insert_cex_outcome(conn, start=start, end=end, start_price=100, end_price=101)
        _insert_trade_event(
            conn,
            ts_ms=t0_ms - 1000,
            sub_id="btc-sig",
            asset_id="yes-fill",
            condition_id="cid-fill",
            price=0.52,
            size=3,
        )
        _insert_trade_event(
            conn,
            ts_ms=t0_ms,
            sub_id="btc-sig",
            asset_id="yes-fill",
            condition_id="cid-fill",
            price=0.52,
            size=3,
        )
        _insert_book_event(
            conn,
            ts_ms=fill_ms,
            sub_id="btc-book",
            asset_id="yes-fill",
            condition_id="cid-fill",
        )
        _insert_trade_event(
            conn,
            ts_ms=fill_ms,
            sub_id="btc-fill-feed",
            asset_id="yes-fill",
            condition_id="cid-fill",
            price=0.50,
            size=0,
        )
        _insert_trade_event(
            conn,
            ts_ms=fill_ms + 30_000,
            sub_id="btc-fill-feed",
            asset_id="yes-fill",
            condition_id="cid-fill",
            price=0.49,
            size=0,
        )
        conn.commit()
    finally:
        conn.close()

    report = run_replay(db, since_ms=_ms(start), until_ms=_ms(end), fill_timeout_sec=60)

    row = report["rows"][0]
    assert row["filled"] is True
    assert row["fill_delay_sec"] == 20.0
    assert row["fill_price"] == 0.50
    assert row["book_covered"] is True
    assert row["depth_notional"] == 50.0
    assert row["adverse_30s_price"] == 0.49
    assert row["adverse_30s_delta"] == -0.01
    assert row["adverse_30s_moved_against"] is True
    assert row["outcome_label"] == "YES"
    assert row["signal_won"] is True


def test_bounded_window_filters_signals_and_csv_rows(tmp_path: Path):
    db = _make_recorder_db(tmp_path)
    start, end, t0_ms = _base_times()
    outside_t0_ms = t0_ms - 120_000
    conn = sqlite3.connect(db)
    try:
        _insert_market(
            conn,
            condition_id="cid-window",
            start=start,
            end=end,
            yes_token="yes-window",
            no_token="no-window",
        )
        _insert_cex_outcome(conn, start=start, end=end)
        for base_ms, sub_id in ((outside_t0_ms, "btc-outside"), (t0_ms, "btc-inside")):
            _insert_trade_event(
                conn,
                ts_ms=base_ms - 1000,
                sub_id=sub_id,
                asset_id="yes-window",
                condition_id="cid-window",
                price=0.52,
                size=3,
            )
            _insert_trade_event(
                conn,
                ts_ms=base_ms,
                sub_id=sub_id,
                asset_id="yes-window",
                condition_id="cid-window",
                price=0.52,
                size=3,
            )
        conn.commit()
    finally:
        conn.close()

    report = run_replay(
        db,
        since_ms=t0_ms - 10_000,
        until_ms=_ms(end),
        fill_timeout_sec=60,
    )
    out = tmp_path / "replay.csv"
    assert write_csv(report, out) == 1

    with out.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["subscription_id"] == "btc-inside"


def test_no_future_leak_for_outcome_or_adverse(tmp_path: Path):
    db = _make_recorder_db(tmp_path)
    start, end, t0_ms = _base_times()
    fill_ms = t0_ms + 5_000
    conn = sqlite3.connect(db)
    try:
        _insert_market(
            conn,
            condition_id="cid-leak",
            start=start,
            end=end,
            yes_token="yes-leak",
            no_token="no-leak",
        )
        # Outcome data exists in the DB, but until_ms below stops before resolution.
        _insert_cex_outcome(conn, start=start, end=end, start_price=100, end_price=101)
        _insert_trade_event(
            conn,
            ts_ms=t0_ms - 1000,
            sub_id="btc-sig",
            asset_id="yes-leak",
            condition_id="cid-leak",
            price=0.52,
            size=3,
        )
        _insert_trade_event(
            conn,
            ts_ms=t0_ms,
            sub_id="btc-sig",
            asset_id="yes-leak",
            condition_id="cid-leak",
            price=0.52,
            size=3,
        )
        _insert_trade_event(
            conn,
            ts_ms=fill_ms,
            sub_id="btc-fill-feed",
            asset_id="yes-leak",
            condition_id="cid-leak",
            price=0.50,
            size=0,
        )
        # This is after t0 and before fill+30s. It must not satisfy the 30s horizon.
        _insert_trade_event(
            conn,
            ts_ms=fill_ms + 29_000,
            sub_id="btc-fill-feed",
            asset_id="yes-leak",
            condition_id="cid-leak",
            price=0.49,
            size=0,
        )
        conn.commit()
    finally:
        conn.close()

    report = run_replay(
        db,
        since_ms=_ms(start),
        until_ms=fill_ms + 29_000,
        fill_timeout_sec=60,
    )

    row = report["rows"][0]
    assert row["filled"] is True
    assert row["adverse_30s_price"] is None
    assert row["adverse_30s_moved_against"] is None
    assert row["outcome_label"] is None
    assert "outcome_unavailable_in_window" in row["notes"]


def test_main_order_rows_include_cancel_and_buy_no_fill_denominator(tmp_path: Path):
    recorder_db = _make_recorder_db(tmp_path)
    main_db = _make_main_db(tmp_path)
    start, end, t0_ms = _base_times()
    placed_at = end - timedelta(minutes=7)
    fill_at = placed_at + timedelta(seconds=12)

    rec = sqlite3.connect(recorder_db)
    try:
        _insert_market(
            rec,
            condition_id="cid-main",
            start=start,
            end=end,
            yes_token="yes-main",
            no_token="no-main",
        )
        _insert_cex_outcome(rec, start=start, end=end)
        _insert_trade_event(
            rec,
            ts_ms=t0_ms - 1000,
            sub_id="btc-sig",
            asset_id="yes-main",
            condition_id="cid-main",
            price=0.52,
            size=3,
        )
        _insert_trade_event(
            rec,
            ts_ms=t0_ms,
            sub_id="btc-sig",
            asset_id="yes-main",
            condition_id="cid-main",
            price=0.52,
            size=3,
        )
        _insert_trade_event(
            rec,
            ts_ms=_ms(fill_at + timedelta(seconds=30)),
            sub_id="btc-fill-feed",
            asset_id="no-main",
            condition_id="cid-main",
            price=0.47,
            size=0,
        )
        rec.commit()
    finally:
        rec.close()

    main = sqlite3.connect(main_db)
    try:
        _insert_main_order(
            main,
            order_id="paper-filled",
            condition_id="cid-main",
            token_id="no-main",
            side="BUY_NO",
            price=0.50,
            status="matched",
            placed_at=placed_at,
            last_updated=fill_at,
        )
        _insert_main_trade(
            main,
            trade_id="trade-1",
            order_id="paper-filled",
            condition_id="cid-main",
            token_id="no-main",
            side="BUY_NO",
            price=0.50,
            filled_at=fill_at,
        )
        _insert_main_book(main, token_id="no-main", snapshot_at=fill_at)
        _insert_main_order(
            main,
            order_id="paper-cancelled",
            condition_id="cid-main",
            token_id="yes-main",
            side="BUY_YES",
            price=0.51,
            status="CANCELLED",
            placed_at=placed_at + timedelta(seconds=1),
            last_updated=placed_at + timedelta(minutes=5),
        )
        main.commit()
    finally:
        main.close()

    report = run_replay(
        recorder_db,
        main_db=main_db,
        since_ms=_ms(start),
        until_ms=_ms(end),
        fill_timeout_sec=60,
    )

    orders = [row for row in report["rows"] if row["row_type"] == "main_order"]
    assert report["summary"]["main_orders"] == 2
    assert len(orders) == 2
    filled = next(row for row in orders if row["order_id"] == "paper-filled")
    assert filled["filled"] is True
    assert filled["fill_source"] == "main_order_trade"
    assert filled["side"] == "BUY_NO"
    assert filled["adverse_30s_moved_against"] is True
    cancelled = next(row for row in orders if row["order_id"] == "paper-cancelled")
    assert cancelled["filled"] is False
    assert "cancel_or_closed_order" in cancelled["notes"]
