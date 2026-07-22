from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from scripts.wallet_tag_feature_shadow import run_once


def _seed_observer(path):
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE observed_trades (
            wallet TEXT,
            asset_id TEXT,
            timestamp_s INTEGER,
            taker_direction TEXT,
            price REAL,
            token_amount REAL,
            condition_id TEXT,
            market_id TEXT,
            outcome TEXT,
            outcome_index INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE observed_markets (
            condition_id TEXT PRIMARY KEY,
            yes_won INTEGER,
            settled INTEGER,
            proxy_settled INTEGER
        )
        """
    )
    con.executemany(
        "INSERT INTO observed_markets VALUES (?, ?, ?, ?)",
        [
            ("c1", 1, 1, 0),
            ("c2", 0, 1, 0),
            ("c3", None, 0, 0),
        ],
    )
    con.executemany(
        "INSERT INTO observed_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("0xabc95618e", "a1", 100, "BUY", 0.25, 100.0, "c1", "m1", "Yes", 0),
            # Duplicate wallet/market should be skipped in elite capped mode.
            ("0xabc95618e", "a2", 101, "BUY", 0.25, 100.0, "c1", "m1", "Yes", 0),
            # Losing closed row for an allowlisted wallet.
            ("0xdef0dfdce", "a3", 102, "BUY", 0.50, 100.0, "c2", "m2", "Yes", 0),
            # Open row that fits the $1 open exposure cap.
            ("0xaaa67e9ca", "a4", 103, "BUY", 0.10, 100.0, "c3", "m3", "Yes", 0),
            # Open row skipped by the $1 open exposure cap.
            ("0xbbb8c9c23", "a5", 104, "BUY", 0.10, 100.0, "c3", "m4", "Yes", 0),
            # Non-allowlisted wallet should be ignored.
            ("0xnotlisted", "a6", 105, "BUY", 0.10, 100.0, "c1", "m5", "Yes", 0),
        ],
    )
    con.commit()
    con.close()


def test_elite_cap_filters_wallets_caps_size_and_limits_open_exposure(tmp_path):
    observer = tmp_path / "observer.db"
    shadow = tmp_path / "shadow.db"
    report_dir = tmp_path / "reports"
    _seed_observer(observer)

    report = run_once(
        observer_db=observer,
        shadow_db=shadow,
        report_dir=report_dir,
        fee_rate=0.04,
        min_observed_at=datetime.fromtimestamp(0, UTC),
        wallet_suffixes=("95618e", "0dfdce", "67e9ca", "8c9c23"),
        max_entry_cost_usd=1.0,
        max_open_exposure_usd=1.0,
        one_entry_per_wallet_market=True,
    )

    assert report["scanned_buy_rows"] == 5
    assert report["n_entries"] == 3
    assert report["closed"] == 2
    assert report["open_entries"] == 1
    assert report["skipped_duplicate_wallet_market"] == 1
    assert report["skipped_open_exposure_cap"] == 1

    con = sqlite3.connect(shadow)
    try:
        costs = [row[0] for row in con.execute("SELECT entry_cost_usd FROM paper_entries")]
    finally:
        con.close()
    assert costs
    assert max(costs) <= 1.0000001
