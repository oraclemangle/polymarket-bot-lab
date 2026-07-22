"""Tests for Bot J — Near-Resolution Wallet paper lane."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from bots.bot_j_nr_wallet.config import WALLET_COHORT
from bots.bot_j_nr_wallet.executor import _is_sports, _qualifying_trades, run_once


@pytest.fixture
def tmp_observer_db(tmp_path: Path) -> Path:
    db = tmp_path / "observer.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE observed_trades (
            wallet TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            timestamp_s INTEGER NOT NULL,
            taker_direction TEXT NOT NULL,
            price REAL NOT NULL,
            token_amount REAL NOT NULL,
            condition_id TEXT,
            market_id TEXT,
            outcome TEXT,
            outcome_index INTEGER,
            usd_amount REAL,
            ingested_at TEXT NOT NULL,
            PRIMARY KEY (wallet, asset_id, timestamp_s, taker_direction, price, token_amount)
        );
        CREATE TABLE observed_markets (
            market_id TEXT PRIMARY KEY,
            condition_id TEXT,
            question TEXT,
            end_date_iso TEXT
        );
        """
    )

    wallets = list(WALLET_COHORT)
    # qualifying trade
    con.execute(
        """
        INSERT INTO observed_trades
        (wallet, asset_id, timestamp_s, taker_direction, price, token_amount,
         condition_id, market_id, outcome, outcome_index, usd_amount, ingested_at)
        VALUES (?, ?, ?, 'BUY', 0.55, 100, 'cond1', 'm1', 'Yes', 0, 55, '2026-05-10T20:00:00Z')
        """,
        (wallets[0], "asset-cond1-0", 1_777_000_000),
    )
    con.execute(
        "INSERT INTO observed_markets (market_id, condition_id, question) VALUES (?, ?, ?)",
        ("m1", "cond1", "Will Man United win on 2026-05-10?"),
    )

    # non-qualifying: wrong wallet
    con.execute(
        """
        INSERT INTO observed_trades
        (wallet, asset_id, timestamp_s, taker_direction, price, token_amount,
         condition_id, market_id, outcome, outcome_index, usd_amount, ingested_at)
        VALUES ('0xbad', ?, ?, 'BUY', 0.55, 100, 'cond2', 'm2', 'Yes', 0, 55, '2026-05-10T20:00:00Z')
        """,
        ("asset-cond2-0", 1_777_000_001),
    )
    con.execute(
        "INSERT INTO observed_markets (market_id, condition_id, question) VALUES (?, ?, ?)",
        ("m2", "cond2", "Will Man United win on 2026-05-10?"),
    )

    # non-qualifying: politics
    con.execute(
        """
        INSERT INTO observed_trades
        (wallet, asset_id, timestamp_s, taker_direction, price, token_amount,
         condition_id, market_id, outcome, outcome_index, usd_amount, ingested_at)
        VALUES (?, ?, ?, 'BUY', 0.55, 100, 'cond3', 'm3', 'Yes', 0, 55, '2026-05-10T20:00:00Z')
        """,
        (wallets[1], "asset-cond3-0", 1_777_000_002),
    )
    con.execute(
        "INSERT INTO observed_markets (market_id, condition_id, question) VALUES (?, ?, ?)",
        ("m3", "cond3", "Will Trump win the election?"),
    )

    # non-qualifying: price out of band
    con.execute(
        """
        INSERT INTO observed_trades
        (wallet, asset_id, timestamp_s, taker_direction, price, token_amount,
         condition_id, market_id, outcome, outcome_index, usd_amount, ingested_at)
        VALUES (?, ?, ?, 'BUY', 0.15, 100, 'cond4', 'm4', 'Yes', 0, 15, '2026-05-10T20:00:00Z')
        """,
        (wallets[2], "asset-cond4-0", 1_777_000_003),
    )
    con.execute(
        "INSERT INTO observed_markets (market_id, condition_id, question) VALUES (?, ?, ?)",
        ("m4", "cond4", "Will Man United win on 2026-05-10?"),
    )

    # non-qualifying: SELL
    con.execute(
        """
        INSERT INTO observed_trades
        (wallet, asset_id, timestamp_s, taker_direction, price, token_amount,
         condition_id, market_id, outcome, outcome_index, usd_amount, ingested_at)
        VALUES (?, ?, ?, 'SELL', 0.55, 100, 'cond5', 'm5', 'Yes', 0, 55, '2026-05-10T20:00:00Z')
        """,
        (wallets[3], "asset-cond5-0", 1_777_000_004),
    )
    con.execute(
        "INSERT INTO observed_markets (market_id, condition_id, question) VALUES (?, ?, ?)",
        ("m5", "cond5", "Will Man United win on 2026-05-10?"),
    )

    con.commit()
    con.close()
    return db


def test_is_sports():
    assert _is_sports("Will Man United win on 2026-05-10?")
    assert _is_sports("LoL: T1 vs Dplus KIA - Game 2 Winner")
    assert _is_sports("Counter-Strike: NAVI vs FaZe")
    assert not _is_sports("Will Trump win the election?")
    assert not _is_sports("Will it rain in London tomorrow?")
    assert not _is_sports("")
    assert not _is_sports(None)


def test_qualifying_trades(tmp_observer_db: Path):
    con = sqlite3.connect(f"file:{tmp_observer_db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    trades = _qualifying_trades(con)
    con.close()

    # Only cond1 should qualify: right wallet, sports, BUY, 30-70c
    assert len(trades) == 1
    assert trades[0]["condition_id"] == "cond1"
    assert trades[0]["price"] == pytest.approx(0.55)
    assert trades[0]["question"].startswith("Will Man United")


def test_run_once_scans_observer_rows_and_skips_duplicate_order_ids(tmp_db: Path, tmp_observer_db: Path):
    first = run_once(observer_db=tmp_observer_db)
    second = run_once(observer_db=tmp_observer_db)

    assert first == {"scanned": 1, "recorded": 1}
    assert second == {"scanned": 1, "recorded": 0}

    con = sqlite3.connect(tmp_db)
    try:
        assert con.execute(
            "SELECT COUNT(*) FROM orders WHERE bot_id='bot_j_nr_wallet'"
        ).fetchone()[0] == 1
    finally:
        con.close()
