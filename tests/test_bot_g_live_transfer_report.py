from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from scripts.bot_g_live_transfer_report import build_report, render_markdown


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_live_transfer_report_counts_fills_no_fills_stale_and_pairing():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE events (
            bot_id TEXT,
            event_type TEXT,
            created_at TEXT,
            payload TEXT
        );
        CREATE TABLE orders (
            order_id TEXT,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            price REAL,
            size REAL,
            status TEXT,
            placed_at TEXT
        );
        CREATE TABLE trades (
            trade_id TEXT,
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
        CREATE TABLE markets (
            condition_id TEXT,
            question TEXT,
            category TEXT
        );
        """
    )
    now = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    cutoff = now - timedelta(hours=1)

    live_payload = {
        "order_id": "live-fill",
        "condition_id": "cond-live",
        "token_id": "tok-live",
        "observed_ask_price": "0.045",
        "fresh_t_to_res_sec": 22,
        "cex": {"move_bps": "2.0", "confirmed": True},
        "timing_ms": {"book_lookup_ms": 8.0, "submit_response_ms": 120.0},
    }
    no_fill_payload = {
        "order_id": "live-nofill",
        "condition_id": "cond-nofill",
        "token_id": "tok-nofill",
        "observed_ask_price": "0.052",
        "fresh_t_to_res_sec": 18,
        "cex": {"move_bps": "0.2", "confirmed": False},
        "timing_ms": {"book_lookup_ms": 10.0, "submit_response_ms": 130.0},
    }
    stale_payload = {
        "condition_id": "cond-stale",
        "observed_ask_price": "0.045",
        "initial_t_to_res_sec": 40,
        "fresh_t_to_res_sec": -2,
        "timing_ms": {"book_lookup_ms": 20.0, "fresh_clock_ms": 80.0},
    }
    paper_payload = {
        "order_id": "paper-fill",
        "condition_id": "cond-live",
        "token_id": "tok-live",
        "observed_ask_price": "0.045",
    }
    con.executemany(
        "INSERT INTO events VALUES (?, ?, ?, ?)",
        [
            ("bot_g_prime_live", "bot_g.entry_placed", _iso(now), json.dumps(live_payload)),
            ("bot_g_prime_live", "bot_g.entry_placed", _iso(now), json.dumps(no_fill_payload)),
            (
                "bot_g_prime_live",
                "bot_g.entry_stale_time_rejected",
                _iso(now),
                json.dumps(stale_payload),
            ),
            ("bot_g_prime", "bot_g.entry_placed", _iso(now), json.dumps(paper_payload)),
        ],
    )
    con.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("live-fill", "bot_g_prime_live", "cond-live", "tok-live", 0.055, 90.0, "matched", _iso(now)),
            (
                "live-nofill",
                "bot_g_prime_live",
                "cond-nofill",
                "tok-nofill",
                0.055,
                90.0,
                "EXCHANGE_CLOSED",
                _iso(now),
            ),
            (
                "live-noevent",
                "bot_g_prime_live",
                "cond-noevent",
                "tok-noevent",
                0.05,
                20.0,
                "matched",
                _iso(now),
            ),
        ],
    )
    con.executemany(
        "INSERT INTO markets VALUES (?, ?, ?)",
        [
            ("cond-live", "Bitcoin Up or Down", "crypto"),
            ("cond-nofill", "Ethereum Up or Down", "crypto"),
            ("cond-noevent", "Solana Up or Down", "crypto"),
        ],
    )
    con.executemany(
        "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "buy-live-fill",
                "bot_g_prime_live",
                "live-fill",
                "cond-live",
                "tok-live",
                "BUY",
                0.01,
                90.0,
                0.0,
                _iso(now),
                None,
                None,
            ),
            (
                "sell-live-fill",
                "bot_g_prime_live",
                "live-fill",
                "cond-live",
                "tok-live",
                "SELL",
                0.0,
                90.0,
                0.0,
                _iso(now + timedelta(minutes=5)),
                None,
                None,
            ),
            (
                "buy-live-noevent",
                "bot_g_prime_live",
                "live-noevent",
                "cond-noevent",
                "tok-noevent",
                "BUY",
                0.01,
                20.0,
                0.0,
                _iso(now),
                None,
                None,
            ),
            (
                "sell-live-noevent",
                "bot_g_prime_live",
                "live-noevent",
                "cond-noevent",
                "tok-noevent",
                "SELL",
                0.0,
                20.0,
                0.0,
                _iso(now + timedelta(minutes=5)),
                None,
                None,
            ),
        ],
    )

    report = build_report(
        con,
        cutoff=cutoff,
        live_bot_id="bot_g_prime_live",
        paper_bot_id="bot_g_prime",
    )

    assert report["overall"]["placed"] == 3
    assert report["overall"]["filled"] == 2
    assert report["overall"]["exchange_closed_no_fill"] == 1
    assert report["overall"]["stale_rejected"] == 1
    assert report["funnel"]["placed"] == 3
    assert report["funnel"]["filled"] == 2
    assert report["funnel"]["submit_failed"] == 0
    assert report["by_price_zone"]["4c-5c"]["filled"] == 2
    assert report["by_price_zone"]["5c-5.5c"]["exchange_closed_no_fill"] == 1
    assert report["by_setup_label"]["continuation"]["filled"] == 1
    assert report["by_setup_label"]["dead_market"]["exchange_closed_no_fill"] == 1
    assert report["by_symbol"]["BTC"]["filled"] == 1
    assert report["by_symbol"]["ETH"]["exchange_closed_no_fill"] == 1
    assert report["by_fresh_lead"]["15s-30s"]["filled"] == 1
    assert report["live_roi_by_price_zone"]["4c-5c"]["closed"] == 2
    assert "<3.5c" not in report["live_roi_by_price_zone"]
    assert report["paper_live_pairing"]["paper_entries_with_matching_live_entry"] == 1
    assert report["timing"]["book_lookup_ms"]["n"] == 3

    markdown = render_markdown(report)
    assert "exchange-closed/no-fill" in markdown
    assert "## Funnel" in markdown
    assert "## Fresh Lead" in markdown
    assert "4c-5c" in markdown
