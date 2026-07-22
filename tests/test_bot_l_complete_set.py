from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from bots.bot_e_recorder.schema import init_db as init_recorder_db
from bots.bot_l_complete_set.simulator import parse_quote, run_once
from scripts.bot_l_complete_set_daily_report import (
    build_report as build_daily_report,
)
from scripts.bot_l_complete_set_daily_report import (
    render_markdown as render_daily_markdown,
)
from scripts.bot_l_complete_set_depth_probe import probe_depth_sources
from scripts.bot_l_complete_set_sensitivity_sweep import (
    render_markdown as render_sweep_markdown,
)
from scripts.bot_l_complete_set_sensitivity_sweep import (
    run_sweep,
)


def _insert_market(
    conn: sqlite3.Connection,
    *,
    condition_id: str = "cond-btc-1",
    yes_token_id: str = "yes-btc-1",
    no_token_id: str = "no-btc-1",
    symbol: str = "BTC",
    duration_minutes: int = 5,
    end_date_iso: str = "2027-05-13T17:50:00Z",
) -> None:
    conn.execute(
        """
        INSERT INTO markets (
            scan_at_ms, condition_id, question, end_date_iso, yes_token_id,
            no_token_id, symbol, duration_minutes, volume_24h_usd, yes_price
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1_778_000_000_000,
            condition_id,
            "Bitcoin Up or Down - May 13, 1:45PM-1:50PM ET",
            end_date_iso,
            yes_token_id,
            no_token_id,
            symbol,
            duration_minutes,
            10_000.0,
            0.5,
        ),
    )


def _insert_tob(
    conn: sqlite3.Connection,
    *,
    event_id_time: int,
    asset_id: str,
    condition_id: str = "cond-btc-1",
    bid: float = 0.49,
    ask: float = 0.50,
    bid_size: float | None = None,
    ask_size: float | None = None,
) -> None:
    payload = {
        "asset_id": asset_id,
        "best_bid": str(bid),
        "best_ask": str(ask),
    }
    if bid_size is not None:
        payload["best_bid_size"] = str(bid_size)
    if ask_size is not None:
        payload["best_ask_size"] = str(ask_size)
    conn.execute(
        """
        INSERT INTO pm_events (
            received_at_ms, subscription_id, event_type, asset_id,
            condition_id, payload_json
        )
        VALUES (?, ?, 'best_bid_ask', ?, ?, ?)
        """,
        (
            event_id_time,
            "btc-test",
            asset_id,
            condition_id,
            json.dumps(payload),
        ),
    )


def _insert_book(
    conn: sqlite3.Connection,
    *,
    event_id_time: int,
    asset_id: str,
    condition_id: str = "cond-btc-1",
    bid: float = 0.49,
    ask: float = 0.50,
    bid_size: float = 10.0,
    ask_size: float = 10.0,
) -> None:
    payload = {
        "market": condition_id,
        "bids": [{"price": str(bid), "size": str(bid_size)}],
        "asks": [{"price": str(ask), "size": str(ask_size)}],
    }
    conn.execute(
        """
        INSERT INTO pm_events (
            received_at_ms, subscription_id, event_type, asset_id,
            condition_id, payload_json
        )
        VALUES (?, ?, 'book', ?, ?, ?)
        """,
        (
            event_id_time,
            "btc-test",
            asset_id,
            condition_id,
            json.dumps(payload),
        ),
    )


def test_parse_quote_handles_best_bid_ask(tmp_path: Path):
    db = tmp_path / "recorder.db"
    conn = init_recorder_db(db)
    _insert_market(conn)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.45, ask=0.46)
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pm_events").fetchone()

    quote = parse_quote(row)

    assert quote is not None
    assert quote.asset_id == "yes-btc-1"
    assert quote.bid == 0.45
    assert quote.ask == 0.46
    assert quote.diagnostics["best_bid_size"] == "missing"
    assert quote.diagnostics["best_ask_size"] == "missing"


def test_parse_quote_rejects_crossed_book(tmp_path: Path):
    db = tmp_path / "recorder.db"
    conn = init_recorder_db(db)
    _insert_market(conn)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.51, ask=0.48)
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pm_events").fetchone()

    assert parse_quote(row) is None


def test_parse_quote_depth_diagnostics_distinguish_missing_and_zero(tmp_path: Path):
    db = tmp_path / "recorder.db"
    conn = init_recorder_db(db)
    _insert_market(conn)
    _insert_tob(
        conn,
        event_id_time=1_778_000_001_000,
        asset_id="yes-btc-1",
        bid=0.45,
        ask=0.46,
        bid_size=0.0,
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pm_events").fetchone()

    quote = parse_quote(row)

    assert quote is not None
    assert quote.bid_size is None
    assert quote.ask_size is None
    assert quote.diagnostics["best_bid_size"] == "zero_or_negative"
    assert quote.diagnostics["best_ask_size"] == "missing"


def test_parse_quote_uses_book_sizes_when_direct_sizes_are_missing(tmp_path: Path):
    db = tmp_path / "recorder.db"
    conn = init_recorder_db(db)
    _insert_market(conn)
    payload = {
        "market": "cond-btc-1",
        "bids": [{"price": "0.44", "size": "12"}, {"price": "0.43", "size": "3"}],
        "asks": [{"price": "0.46", "size": "9"}, {"price": "0.47", "size": "4"}],
    }
    conn.execute(
        """
        INSERT INTO pm_events (
            received_at_ms, subscription_id, event_type, asset_id,
            condition_id, payload_json
        )
        VALUES (?, ?, 'book', ?, ?, ?)
        """,
        (1_778_000_001_000, "btc-test", "yes-btc-1", "cond-btc-1", json.dumps(payload)),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pm_events").fetchone()

    quote = parse_quote(row)

    assert quote is not None
    assert quote.bid == 0.44
    assert quote.ask == 0.46
    assert quote.bid_size == 12
    assert quote.ask_size == 9
    assert quote.diagnostics["bid_size_source"] == "book"
    assert quote.diagnostics["ask_size_source"] == "book"


def test_run_once_records_buy_complete_set_signal(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    paper_db = tmp_path / "paper.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.47, ask=0.48)
    _insert_tob(conn, event_id_time=1_778_000_001_200, asset_id="no-btc-1", bid=0.48, ask=0.49)
    conn.commit()
    conn.close()

    report = run_once(
        recorder_db_path=recorder_db,
        paper_db_path=paper_db,
        lookback_hours=100_000,
        raw_buy_threshold=0.995,
        adjusted_buy_threshold=0.995,
        raw_sell_threshold=1.005,
        adjusted_sell_threshold=1.005,
        slippage_per_leg=0.0,
        gross_cost_usd=1.0,
        min_depth_shares=0.0,
        max_pair_age_ms=1000,
        incremental=False,
    )

    assert report["signals"] == 1
    assert report["by_type"]["BUY_COMPLETE_SET"]["signals"] == 1
    assert "SELL_COMPLETE_SET" not in report["by_type"]
    assert report["buy_executable_signals"] == 1
    assert report["sell_executable_signals"] == 0
    assert report["buy_executable_pnl_usd"] > 0
    assert report["sell_executable_pnl_usd"] == 0
    assert report["pnl_usd"] > 0

    daily = build_daily_report(paper_db)
    markdown = render_daily_markdown(daily)
    assert daily["posture"]["paper_only"] is True
    assert daily["summary"]["buy_executable_signals"] == 1
    assert "BUY_COMPLETE_SET" in daily["depth_diagnostics"]
    assert daily["gate_slices"]["top_1_concentration_pct"] == 100.0
    assert "Depth Diagnostics" in markdown
    assert "Gate Slices" in markdown


def test_run_once_requires_fresh_book_depth_when_enabled(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    paper_db = tmp_path / "paper.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.47, ask=0.48)
    _insert_tob(conn, event_id_time=1_778_000_001_200, asset_id="no-btc-1", bid=0.48, ask=0.49)
    conn.commit()
    conn.close()

    report = run_once(
        recorder_db_path=recorder_db,
        paper_db_path=paper_db,
        lookback_hours=100_000,
        raw_buy_threshold=0.995,
        adjusted_buy_threshold=0.995,
        raw_sell_threshold=1.005,
        adjusted_sell_threshold=1.005,
        slippage_per_leg=0.0,
        gross_cost_usd=1.0,
        min_depth_shares=0.0,
        require_depth=True,
        max_pair_age_ms=1000,
        max_depth_age_ms=1000,
        incremental=False,
    )

    assert report["signals"] == 1
    assert report["executable_signals"] == 0
    row = sqlite3.connect(paper_db).execute(
        "SELECT reason, executable, yes_size, no_size, payload_json FROM bot_l_complete_set_signals"
    ).fetchone()
    payload = json.loads(row[4])
    assert row[0] == "depth_missing_or_insufficient"
    assert row[1] == 0
    assert row[2] is None
    assert row[3] is None
    assert payload["required_depth_shares"] > 1.0
    assert payload["yes_quote_diagnostics"]["depth_join"] == "missing_book"


def test_run_once_uses_fresh_book_depth_for_executable_signal(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    paper_db = tmp_path / "paper.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn)
    _insert_book(conn, event_id_time=1_778_000_000_500, asset_id="yes-btc-1", bid=0.47, ask=0.48)
    _insert_book(conn, event_id_time=1_778_000_000_600, asset_id="no-btc-1", bid=0.48, ask=0.49)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.47, ask=0.48)
    _insert_tob(conn, event_id_time=1_778_000_001_200, asset_id="no-btc-1", bid=0.48, ask=0.49)
    conn.commit()
    conn.close()

    report = run_once(
        recorder_db_path=recorder_db,
        paper_db_path=paper_db,
        lookback_hours=100_000,
        raw_buy_threshold=0.995,
        adjusted_buy_threshold=0.995,
        raw_sell_threshold=1.005,
        adjusted_sell_threshold=1.005,
        slippage_per_leg=0.0,
        gross_cost_usd=1.0,
        min_depth_shares=0.0,
        require_depth=True,
        max_pair_age_ms=1000,
        max_depth_age_ms=1000,
        incremental=False,
    )

    assert report["signals"] == 3
    assert report["executable_signals"] == 3
    row = sqlite3.connect(paper_db).execute(
        """
        SELECT reason, executable, yes_size, no_size, payload_json
        FROM bot_l_complete_set_signals
        WHERE reason='passes_haircut'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    payload = json.loads(row[4])
    assert row[0] == "passes_haircut"
    assert row[1] == 1
    assert row[2] == 10
    assert row[3] == 10
    assert payload["yes_quote_diagnostics"]["depth_join"] == "book"


def test_run_once_records_sell_complete_set_signal(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    paper_db = tmp_path / "paper.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.51, ask=0.52)
    _insert_tob(conn, event_id_time=1_778_000_001_200, asset_id="no-btc-1", bid=0.50, ask=0.51)
    conn.commit()
    conn.close()

    report = run_once(
        recorder_db_path=recorder_db,
        paper_db_path=paper_db,
        lookback_hours=100_000,
        raw_buy_threshold=0.995,
        adjusted_buy_threshold=0.995,
        raw_sell_threshold=1.005,
        adjusted_sell_threshold=1.005,
        slippage_per_leg=0.0,
        gross_cost_usd=1.0,
        min_depth_shares=0.0,
        max_pair_age_ms=1000,
        incremental=False,
    )

    assert report["signals"] == 1
    assert "BUY_COMPLETE_SET" not in report["by_type"]
    assert report["by_type"]["SELL_COMPLETE_SET"]["signals"] == 1
    assert report["buy_executable_signals"] == 0
    assert report["sell_executable_signals"] == 1
    assert report["buy_executable_pnl_usd"] == 0
    assert report["sell_executable_pnl_usd"] > 0


def test_run_once_keeps_raw_only_when_haircut_fails(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    paper_db = tmp_path / "paper.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.48, ask=0.49)
    _insert_tob(conn, event_id_time=1_778_000_001_100, asset_id="no-btc-1", bid=0.48, ask=0.49)
    conn.commit()
    conn.close()

    report = run_once(
        recorder_db_path=recorder_db,
        paper_db_path=paper_db,
        lookback_hours=100_000,
        raw_buy_threshold=0.995,
        adjusted_buy_threshold=0.985,
        raw_sell_threshold=1.005,
        adjusted_sell_threshold=1.015,
        slippage_per_leg=0.005,
        gross_cost_usd=1.0,
        min_depth_shares=0.0,
        max_pair_age_ms=1000,
        incremental=False,
    )

    assert report["signals"] == 1
    assert report["executable_signals"] == 0
    row = sqlite3.connect(paper_db).execute(
        "SELECT reason, executable, raw_sum, adjusted_sum FROM bot_l_complete_set_signals"
    ).fetchone()
    assert row[0] == "raw_only"
    assert row[1] == 0
    assert row[2] == 0.98
    assert row[3] == 0.99


def test_run_once_marks_after_end_date_signals_non_executable(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    paper_db = tmp_path / "paper.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn, end_date_iso="2026-01-01T00:00:00Z")
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.47, ask=0.48)
    _insert_tob(conn, event_id_time=1_778_000_001_200, asset_id="no-btc-1", bid=0.48, ask=0.49)
    conn.commit()
    conn.close()

    report = run_once(
        recorder_db_path=recorder_db,
        paper_db_path=paper_db,
        lookback_hours=100_000,
        raw_buy_threshold=0.995,
        adjusted_buy_threshold=0.995,
        raw_sell_threshold=1.005,
        adjusted_sell_threshold=1.005,
        slippage_per_leg=0.0,
        gross_cost_usd=1.0,
        min_depth_shares=0.0,
        max_pair_age_ms=1000,
        incremental=False,
    )

    assert report["signals"] == 1
    assert report["executable_signals"] == 0
    assert report["failure_counts_this_run"]["stale_after_end_date"] == 1
    row = sqlite3.connect(paper_db).execute(
        "SELECT reason, executable FROM bot_l_complete_set_signals"
    ).fetchone()
    assert row[0] == "stale_after_end_date"
    assert row[1] == 0


def test_run_once_ignores_non_btc_5m_markets(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    paper_db = tmp_path / "paper.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn, symbol="ETH", duration_minutes=5)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", ask=0.48)
    _insert_tob(conn, event_id_time=1_778_000_001_100, asset_id="no-btc-1", ask=0.49)
    conn.commit()
    conn.close()

    report = run_once(
        recorder_db_path=recorder_db,
        paper_db_path=paper_db,
        lookback_hours=100_000,
        raw_buy_threshold=0.995,
        adjusted_buy_threshold=0.995,
        raw_sell_threshold=1.005,
        adjusted_sell_threshold=1.005,
        slippage_per_leg=0.0,
        gross_cost_usd=1.0,
        min_depth_shares=0.0,
        max_pair_age_ms=1000,
        incremental=False,
    )

    assert report["signals"] == 0


def test_sensitivity_sweep_uses_disposable_paper_dbs(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn)
    _insert_tob(conn, event_id_time=1_778_000_001_000, asset_id="yes-btc-1", bid=0.47, ask=0.48)
    _insert_tob(conn, event_id_time=1_778_000_001_200, asset_id="no-btc-1", bid=0.48, ask=0.49)
    conn.commit()
    conn.close()

    report = run_sweep(
        recorder_db_path=recorder_db,
        lookback_hours=100_000,
        raw_buy_thresholds=[0.995],
        raw_sell_thresholds=[1.005],
        slippage_per_legs=[0.0],
        max_pair_age_ms_values=[1000],
        gross_cost_usd=1.0,
        min_depth_shares=0.0,
    )
    markdown = render_sweep_markdown(report)

    assert len(report["results"]) == 1
    assert report["results"][0]["summary"]["signals"] == 1
    assert report["results"][0]["summary"]["buy_executable_signals"] == 1
    assert "Sensitivity Sweep" in markdown


def test_depth_probe_counts_book_sizes(tmp_path: Path):
    recorder_db = tmp_path / "recorder.db"
    conn = init_recorder_db(recorder_db)
    _insert_market(conn)
    payload = {
        "market": "cond-btc-1",
        "bids": [{"price": "0.44", "size": "12"}],
        "asks": [{"price": "0.46", "size": "9"}],
    }
    conn.execute(
        """
        INSERT INTO pm_events (
            received_at_ms, subscription_id, event_type, asset_id,
            condition_id, payload_json
        )
        VALUES (?, ?, 'book', ?, ?, ?)
        """,
        (1_778_000_001_000, "btc-test", "yes-btc-1", "cond-btc-1", json.dumps(payload)),
    )
    conn.commit()
    conn.close()

    report = probe_depth_sources(recorder_db, lookback_hours=100_000)

    assert report["by_event_type"]["book"]["book_bid_size"] == 1
    assert report["by_event_type"]["book"]["book_ask_size"] == 1
