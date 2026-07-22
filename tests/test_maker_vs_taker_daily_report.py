from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.maker_vs_taker_daily_report import build_report


def _main_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
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
            order_type TEXT,
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
            size NUMERIC,
            fee_usd NUMERIC,
            filled_at TEXT,
            usd_gbp_rate NUMERIC,
            gbp_notional NUMERIC
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            bot_id TEXT,
            event_type TEXT,
            severity TEXT,
            message TEXT,
            payload TEXT,
            created_at TEXT
        );
        """
    )
    con.execute(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("o1", "bot_g_prime", "c1", "t1", "BUY", 0.1, 10, "FILLED", "GTC", "2026-05-15", "2026-05-15"),
    )
    con.execute(
        "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("b1", "bot_g_prime", "o1", "c1", "t1", "BUY", 0.1, 10, 0, "2026-05-15", 0.8, 0.8),
    )
    con.execute(
        "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("s1", "bot_g_prime", "o1", "c1", "t1", "SELL", 1.0, 10, 0, "2026-05-15", 0.8, 8),
    )
    con.commit()
    con.close()


def _persistence_db(path: Path, style: str, *, rows: int = 1, pnl_usd: float = 0.9) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE paper_entries (
            execution_style TEXT,
            cell_label TEXT,
            won INTEGER,
            pnl_usd REAL,
            fee_usd REAL,
            bid_high REAL,
            ask_high REAL
        );
        """
    )
    con.executemany(
        "INSERT INTO paper_entries VALUES (?,?,?,?,?,?,?)",
        [
            (
                style,
                "C_tail_5m_15m_95_99",
                1,
                pnl_usd,
                0 if style == "maker" else 0.01,
                0.1,
                0.11,
            )
            for _ in range(rows)
        ],
    )
    con.commit()
    con.close()


def _legacy_persistence_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE paper_entries (
            won INTEGER,
            pnl_usd REAL,
            fee_usd REAL,
            bid_high REAL,
            ask_high REAL
        );
        """
    )
    con.execute("INSERT INTO paper_entries VALUES (?,?,?,?,?)", (1, 0.9, 0.01, 0.1, 0.11))
    con.commit()
    con.close()


def _crypto_fv_signal(
    con: sqlite3.Connection, bot_id: str, *, fee_usd: float, suffix: str = "0"
) -> None:
    condition_id = f"cid-{bot_id}-{suffix}"
    token_id = f"token-{bot_id}-{suffix}"
    payload = {
        "condition_id": condition_id,
        "token_id": token_id,
        "main_fill_track": "main",
        "fill_tracks": [
            {
                "fill_track": "main",
                "filled": True,
                "stake_usd": 1.0,
                "size": 10.0,
                "fee_usd": fee_usd,
            }
        ],
    }
    con.execute(
        "INSERT INTO events (bot_id, event_type, severity, message, payload, created_at) VALUES (?,?,?,?,?,?)",
        (
            bot_id,
            "crypto_fair_value.signal",
            "INFO",
            "signal",
            json.dumps(payload),
            "2026-05-15",
        ),
    )


def _crypto_fv_resolve(con: sqlite3.Connection, bot_id: str, *, suffix: str = "0") -> None:
    payload = {
        "condition_id": f"cid-{bot_id}-{suffix}",
        "token_id": f"token-{bot_id}-{suffix}",
        "settle_price": "1",
    }
    con.execute(
        "INSERT INTO events (bot_id, event_type, severity, message, payload, created_at) VALUES (?,?,?,?,?,?)",
        (
            bot_id,
            "portfolio.paper_resolve",
            "INFO",
            "settled",
            json.dumps(payload),
            "2026-05-15",
        ),
    )


def test_build_report_includes_gate_status(tmp_path):
    main_db = tmp_path / "main.db"
    taker_db = tmp_path / "taker.db"
    maker_db = tmp_path / "maker.db"
    live_maker_db = tmp_path / "live_maker.db"
    _main_db(main_db)
    _persistence_db(taker_db, "taker")
    _persistence_db(maker_db, "maker")
    _persistence_db(live_maker_db, "maker")

    report = build_report(
        main_db=main_db,
        persistence_taker_db=taker_db,
        persistence_maker_db=maker_db,
        persistence_live_maker_db=live_maker_db,
    )

    assert "Bot G Prime paper" in report
    assert "Bot G live-mirror paper" in report
    assert "Bot G high-tail paper" in report
    assert "Bot I Persistence" in report
    assert "Bot I Cell C maker candidate" in report
    assert "Fleet Lift Snapshot" in report
    assert "WAIT until resolved maker sample reaches n>=50" in report


def test_build_report_accepts_legacy_persistence_db_without_execution_style(tmp_path):
    main_db = tmp_path / "main.db"
    taker_db = tmp_path / "legacy_taker.db"
    maker_db = tmp_path / "maker.db"
    live_maker_db = tmp_path / "live_maker.db"
    _main_db(main_db)
    _legacy_persistence_db(taker_db)
    _persistence_db(maker_db, "maker")
    _persistence_db(live_maker_db, "maker")

    report = build_report(
        main_db=main_db,
        persistence_taker_db=taker_db,
        persistence_maker_db=maker_db,
        persistence_live_maker_db=live_maker_db,
    )

    assert "Bot I Persistence" in report
    assert "+809.09%" in report


def test_cell_c_gate_status_switches_to_borderline_after_sample_gate(tmp_path):
    main_db = tmp_path / "main.db"
    taker_db = tmp_path / "taker.db"
    maker_db = tmp_path / "maker.db"
    live_maker_db = tmp_path / "live_maker.db"
    cell_c_db = tmp_path / "cell_c.db"
    _main_db(main_db)
    _persistence_db(taker_db, "taker")
    _persistence_db(maker_db, "maker")
    _persistence_db(live_maker_db, "maker")
    _persistence_db(cell_c_db, "maker", rows=50, pnl_usd=0.0005)

    report = build_report(
        main_db=main_db,
        persistence_taker_db=taker_db,
        persistence_maker_db=maker_db,
        persistence_live_maker_db=live_maker_db,
        cell_c_maker_db=cell_c_db,
    )

    cell_c_row = next(
        line for line in report.splitlines() if line.startswith("| Bot I Cell C maker candidate |")
    )
    assert "50/50/50" in cell_c_row
    assert "S7_BORDERLINE" in cell_c_row
    assert "S7 Cell C: BORDERLINE" in report
    assert "below the n>=50 decision gate" not in report


def test_crypto_fv_readiness_requires_closed_maker_outcomes(tmp_path):
    main_db = tmp_path / "main.db"
    taker_db = tmp_path / "taker.db"
    maker_db = tmp_path / "maker.db"
    live_maker_db = tmp_path / "live_maker.db"
    _main_db(main_db)
    _persistence_db(taker_db, "taker")
    _persistence_db(maker_db, "maker")
    _persistence_db(live_maker_db, "maker")

    con = sqlite3.connect(main_db)
    for _ in range(9):
        _crypto_fv_signal(con, "crypto_brownian_fv_paper", fee_usd=0.03)
    for _ in range(52):
        _crypto_fv_signal(con, "crypto_brownian_fv_paper_maker", fee_usd=0)
    con.commit()
    con.close()

    report = build_report(
        main_db=main_db,
        persistence_taker_db=taker_db,
        persistence_maker_db=maker_db,
        persistence_live_maker_db=live_maker_db,
    )

    brownian_row = next(
        line for line in report.splitlines() if line.startswith("| Crypto FV Brownian |")
    )
    assert "52/52/0" in brownian_row
    assert "WAIT: resolved maker sample < n>=50" in brownian_row
    assert "S6_READY" not in brownian_row


def test_crypto_fv_readiness_uses_settlement_events(tmp_path):
    main_db = tmp_path / "main.db"
    taker_db = tmp_path / "taker.db"
    maker_db = tmp_path / "maker.db"
    live_maker_db = tmp_path / "live_maker.db"
    _main_db(main_db)
    _persistence_db(taker_db, "taker")
    _persistence_db(maker_db, "maker")
    _persistence_db(live_maker_db, "maker")

    con = sqlite3.connect(main_db)
    for i in range(50):
        suffix = str(i)
        _crypto_fv_signal(con, "crypto_brownian_fv_paper_maker", fee_usd=0, suffix=suffix)
        _crypto_fv_resolve(con, "crypto_brownian_fv_paper_maker", suffix=suffix)
    con.commit()
    con.close()

    report = build_report(
        main_db=main_db,
        persistence_taker_db=taker_db,
        persistence_maker_db=maker_db,
        persistence_live_maker_db=live_maker_db,
    )

    brownian_row = next(
        line for line in report.splitlines() if line.startswith("| Crypto FV Brownian |")
    )
    assert "50/50/50" in brownian_row
    assert "+900.00%" in brownian_row
    assert "S6_REVIEW" in brownian_row
    assert "S6 live conversion: REVIEW required" in report
