from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from scripts.bot_g_cex_gate_replay_report import (
    build_report,
    cex_tag_for_move,
    reconstruct_cex_state,
)


def _main_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            status TEXT,
            placed_at TEXT
        );
        CREATE TABLE trades (
            trade_id TEXT PRIMARY KEY,
            bot_id TEXT,
            order_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            fee_usd REAL,
            filled_at TEXT,
            usd_gbp_rate REAL,
            gbp_notional REAL
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT,
            event_type TEXT,
            severity TEXT,
            message TEXT,
            payload TEXT,
            created_at TEXT
        );
        CREATE TABLE markets (
            condition_id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT
        );
        """
    )
    return con


def _recorder_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_at_ms INTEGER,
            condition_id TEXT,
            question TEXT,
            end_date_iso TEXT,
            yes_token_id TEXT,
            no_token_id TEXT,
            symbol TEXT,
            duration_minutes INTEGER,
            volume_24h_usd REAL,
            yes_price REAL
        );
        CREATE TABLE cex_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER,
            trade_time_ms INTEGER,
            symbol TEXT,
            price REAL,
            size REAL,
            is_buyer_maker INTEGER
        );
        """
    )
    return con


def _insert_order(
    con: sqlite3.Connection,
    *,
    order_id: str,
    bot_id: str,
    condition_id: str,
    token_id: str,
    side_token: str,
    price: float,
    placed_at: str,
    cex_json: str,
) -> None:
    con.execute(
        """
        INSERT INTO orders (
            order_id, bot_id, condition_id, token_id, side, price, size, status, placed_at
        ) VALUES (?, ?, ?, ?, 'BUY', ?, 100, 'MATCHED', ?)
        """,
        (order_id, bot_id, condition_id, token_id, price, placed_at),
    )
    con.execute(
        """
        INSERT INTO events (bot_id, event_type, severity, message, payload, created_at)
        VALUES (?, 'bot_g.entry_placed', 'info', '', ?, ?)
        """,
        (
            bot_id,
            (
                '{"order_id":"%s","side_token":"%s","execution_mode":"%s",'
                '"fresh_t_to_res_sec":40,"cex":%s}'
                % (
                    order_id,
                    side_token,
                    "live" if bot_id == "bot_g_prime_live" else "paper",
                    cex_json,
                )
            ),
            placed_at,
        ),
    )
    con.execute(
        """
        INSERT INTO trades (
            trade_id, bot_id, order_id, condition_id, token_id, side, price,
            size, fee_usd, filled_at, usd_gbp_rate, gbp_notional
        ) VALUES (?, ?, ?, ?, ?, 'BUY', ?, 100, 0, ?, 1, 0)
        """,
        (f"buy-{order_id}", bot_id, order_id, condition_id, token_id, price, placed_at),
    )


def _insert_settlement(
    con: sqlite3.Connection,
    *,
    order_id: str,
    bot_id: str,
    condition_id: str,
    token_id: str,
    price: float,
    filled_at: str,
) -> None:
    con.execute(
        """
        INSERT INTO trades (
            trade_id, bot_id, order_id, condition_id, token_id, side, price,
            size, fee_usd, filled_at, usd_gbp_rate, gbp_notional
        ) VALUES (?, ?, '', ?, ?, 'SELL', ?, 100, 0, ?, 1, 0)
        """,
        (f"sell-{order_id}", bot_id, condition_id, token_id, price, filled_at),
    )


def test_cex_tag_for_move_is_side_aware():
    assert cex_tag_for_move(side_token="YES", move_bps=2.0, min_move_bps=1.5) == "agree"
    assert cex_tag_for_move(side_token="YES", move_bps=-2.0, min_move_bps=1.5) == "disagree"
    assert cex_tag_for_move(side_token="NO", move_bps=-2.0, min_move_bps=1.5) == "agree"
    assert cex_tag_for_move(side_token="NO", move_bps=0.4, min_move_bps=1.5) == "flat"


def test_reconstruct_cex_state_matches_bot_g_query_window():
    recorder = _recorder_db()
    recorder.executemany(
        """
        INSERT INTO cex_trades (
            received_at_ms, trade_time_ms, symbol, price, size, is_buyer_maker
        ) VALUES (?, ?, 'BTCUSDT', ?, 1, 0)
        """,
        [
            (1000, 1000, 100.0),
            (46_000, 46_000, 99.97),
        ],
    )

    state = reconstruct_cex_state(
        recorder,
        symbol="BTCUSDT",
        side_token="NO",
        at_ms=46_000,
        window_sec=45,
        min_move_bps=1.5,
    )

    assert state.tag == "agree"
    assert state.confirmed is True
    assert round(state.move_bps or 0, 3) == -3.0


def test_build_report_uses_payload_cex_for_paper_and_recorder_cex_for_live():
    main = _main_db()
    recorder = _recorder_db()
    cutoff = datetime(2026, 5, 6, tzinfo=UTC)
    recorder.executemany(
        """
        INSERT INTO markets (
            scan_at_ms, condition_id, question, end_date_iso, yes_token_id,
            no_token_id, symbol, duration_minutes, volume_24h_usd, yes_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 15, 100, 0.95)
        """,
        [
            (1, "c1", "Bitcoin Up or Down", "2026-05-06T00:01:00+00:00", "yes1", "no1", "BTC"),
            (2, "c2", "Ethereum Up or Down", "2026-05-06T00:01:00+00:00", "yes2", "no2", "ETH"),
        ],
    )
    _insert_order(
        main,
        order_id="paper-win",
        bot_id="bot_g_prime",
        condition_id="c1",
        token_id="no1",
        side_token="NO",
        price=0.04,
        placed_at="2026-05-06 00:00:20",
        cex_json='{"symbol":"BTCUSDT","move_bps":"-2.0","confirmed":true,"window_sec":45}',
    )
    _insert_settlement(
        main,
        order_id="paper-win",
        bot_id="bot_g_prime",
        condition_id="c1",
        token_id="no1",
        price=1.0,
        filled_at="2026-05-06 00:01:00",
    )
    _insert_order(
        main,
        order_id="live-loss",
        bot_id="bot_g_prime_live",
        condition_id="c2",
        token_id="yes2",
        side_token="YES",
        price=0.04,
        placed_at="2026-05-06 00:00:45",
        cex_json='{"skipped":true,"reason":"live_gate_disabled_pre_submit"}',
    )
    _insert_settlement(
        main,
        order_id="live-loss",
        bot_id="bot_g_prime_live",
        condition_id="c2",
        token_id="yes2",
        price=0.0,
        filled_at="2026-05-06 00:01:00",
    )
    recorder.executemany(
        """
        INSERT INTO cex_trades (
            received_at_ms, trade_time_ms, symbol, price, size, is_buyer_maker
        ) VALUES (?, ?, 'ETHUSDT', ?, 1, 0)
        """,
        [
            (1778025600000, 1778025600000, 100.0),
            (1778025645000, 1778025645000, 99.98),
        ],
    )

    report = build_report(
        main,
        recorder,
        bot_ids=("bot_g_prime", "bot_g_prime_live"),
        cutoff=cutoff,
        default_window_sec=45,
        min_move_bps=1.5,
    )

    assert report["by_cex_tag"]["agree"]["won"] == 1
    assert report["by_cex_tag"]["disagree"]["lost"] == 1
    assert report["by_bot_cex_tag"]["bot_g_prime|agree"]["orders"] == 1
    assert report["by_bot_cex_tag"]["bot_g_prime_live|disagree"]["orders"] == 1
    assert report["by_counterfactual"]["bot_g_prime|would_enter"]["won"] == 1
    assert report["by_counterfactual"]["bot_g_prime_live|would_skip"]["lost"] == 1
