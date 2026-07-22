from __future__ import annotations

import sqlite3

from scripts.bot_g_feature_analysis import (
    book_capacity_at_entry,
    capacity_label,
    depletion_label,
    live_candidate_gate,
    live_transfer_summary,
    outlier_adjusted_summary,
    validation_splits,
)


def test_outlier_adjusted_summary_removes_jackpot_wins():
    closed = [
        {"buy_price": 0.05, "size": 100, "pnl_usd": 95.0},
        {"buy_price": 0.05, "size": 100, "pnl_usd": -5.0},
        {"buy_price": 0.06, "size": 100, "pnl_usd": -6.0},
    ]

    summary = outlier_adjusted_summary(closed)

    assert summary["all"]["roi_pct"] == 525.0
    assert summary["largest_win_pnl"] == 95.0
    assert summary["ex_largest_win"]["pnl"] == -11.0
    assert summary["ex_largest_win"]["roi_pct"] == -100.0
    assert summary["ex_largest_two_wins"]["pnl"] == -11.0


def test_book_capacity_reports_depth_at_limit_and_next_ticks(tmp_path):
    db = tmp_path / "main.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE books (token_id TEXT, snapshot_at TEXT, asks TEXT)")
    con.execute(
        "INSERT INTO books VALUES (?, ?, ?)",
        (
            "tok",
            "2026-05-01 12:00:00",
            '[{"price": "0.05", "size": "500"}, {"price": "0.06", "size": "500"}]',
        ),
    )
    con.commit()

    capacity = book_capacity_at_entry(con, "tok", "2026-05-01 12:00:01", 0.05)

    assert capacity["notional_at_limit"] == 25.0
    assert capacity["depth_by_tick"][0]["notional_usd"] == 25.0
    assert capacity["depth_by_tick"][1]["notional_usd"] == 55.0
    assert capacity["depth_by_tick"][2]["notional_usd"] == 55.0
    assert capacity["depth_by_tick"][0]["targets"]["25"] is True
    assert capacity["depth_by_tick"][0]["targets"]["50"] is False
    assert capacity["depth_by_tick"][1]["targets"]["50"] is True
    con.close()


def test_capacity_and_depletion_labels_are_observational():
    capacity = {
        "depth_by_tick": [
            {"targets": {"25": False, "50": False}},
            {"targets": {"25": True, "50": False}},
            {"targets": {"25": True, "50": True}},
        ]
    }

    assert capacity_label(capacity, 25) == "sizeable_at_plus1"
    assert capacity_label(capacity, 50) == "sizeable_at_plus2"
    assert capacity_label({"depth_by_tick": []}, 25) == "toy_fill_only"
    assert depletion_label(1.2) == "refilled"
    assert depletion_label(1.0) == "depleted_or_slight_drop"
    assert depletion_label(None) == "unknown"


def test_validation_splits_include_all_4c_8c_and_cex():
    closed = [
        {
            "buy_price": 0.05,
            "size": 100,
            "pnl_usd": 95.0,
            "win": True,
            "cex_confirmed": True,
            "capacity_label_25": "sizeable_at_limit",
            "capacity_label_50": "toy_fill_only",
            "depletion_label": "refilled",
            "capacity": {"depth_by_tick": [{"targets": {"25": True, "50": False}}]},
        },
        {
            "buy_price": 0.07,
            "size": 100,
            "pnl_usd": -7.0,
            "win": False,
            "cex_confirmed": False,
            "capacity_label_25": "toy_fill_only",
            "capacity_label_50": "toy_fill_only",
            "depletion_label": "depleted_or_slight_drop",
            "capacity": {"depth_by_tick": [{"targets": {"25": False, "50": False}}]},
        },
    ]

    splits = validation_splits(closed)

    assert splits["3_5c_5_5c"]["closed"] == 1
    assert splits["4c_5c"]["closed"] == 1
    assert splits["5c_8c"]["closed"] == 1
    assert splits["all_4c_8c"]["closed"] == 2
    assert splits["all_4c_8c"]["cex"]["confirmed"]["closed"] == 1
    assert splits["all_4c_8c"]["cex"]["unconfirmed"]["closed"] == 1
    assert splits["all_4c_8c"]["capacity"]["targets_usd"]["25"]["0"]["covered"] == 1
    labels = splits["all_4c_8c"]["diagnostic_labels"]
    assert labels["capacity_25"]["sizeable_at_limit"]["closed"] == 1
    assert labels["capacity_25"]["toy_fill_only"]["closed"] == 1
    assert labels["depletion"]["refilled"]["closed"] == 1


def test_validation_splits_include_exploratory_3_5c_5_5c_overlap():
    closed = [
        {"buy_price": 0.03, "size": 100, "pnl_usd": 97.0, "win": True},
        {"buy_price": 0.04, "size": 100, "pnl_usd": 96.0, "win": True},
        {"buy_price": 0.055, "size": 100, "pnl_usd": -5.5, "win": False},
        {"buy_price": 0.06, "size": 100, "pnl_usd": -6.0, "win": False},
    ]

    splits = validation_splits(closed)

    assert splits["3_5c_5_5c"]["closed"] == 2
    assert splits["3_5c_5_5c"]["wins"] == 1
    assert splits["4c_5c"]["closed"] == 1
    assert splits["5c_8c"]["closed"] == 2


def test_live_transfer_summary_flags_paper_win_without_live_fill(tmp_path):
    db = tmp_path / "main.db"
    con = sqlite3.connect(db)
    con.execute(
        """
        CREATE TABLE orders (
            order_id TEXT,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            status TEXT,
            placed_at TEXT
        )
        """
    )
    con.execute(
        """
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
            filled_at TEXT
        )
        """
    )
    con.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("live-order-1", "bot_g_prime_live", "cond-1", "tok-1", "BUY", 0.04, 125, "live", "2026-05-02 18:25:01"),
    )
    closed = [
        {
            "bot_id": "bot_g_prime",
            "buy_price": 0.04,
            "size": 125,
            "pnl_usd": 120.0,
            "win": True,
            "condition_id": "cond-1",
            "token_id": "tok-1",
            "order_id": "paper-order-1",
            "buy_filled_at": "2026-05-02 18:25:00",
            "sell_filled_at": "2026-05-02 18:30:34",
            "capacity": {
                "depth_by_tick": [
                    {"notional_usd": 0.0, "targets": {"25": False}},
                    {"notional_usd": 0.0, "targets": {"25": False}},
                    {"notional_usd": 0.0, "targets": {"25": False}},
                ],
            },
            "capacity_label_25": "toy_fill_only",
        }
    ]

    summary = live_transfer_summary(con, closed)

    assert summary["available"] is True
    assert summary["paper_closed_4c_5c"] == 1
    assert summary["paper_wins_4c_5c"] == 1
    assert summary["paper_orders_with_live_order"] == 1
    assert summary["paper_orders_with_live_fill"] == 0
    assert summary["paper_win_no_live_fill"] == 1
    assert summary["paper_win_zero_at_limit_depth"] == 1
    assert summary["paper_win_transfer_rate_pct"] == 0.0
    assert summary["examples"][0]["live_orders"][0]["order_id"] == "live-order-1"
    con.close()


def _closed_row(
    *,
    price: float = 0.05,
    pnl: float = 95.0,
    win: bool = True,
    cap25: bool = True,
    cap50_plus2: bool = True,
) -> dict:
    return {
        "buy_price": price,
        "size": 100,
        "pnl_usd": pnl,
        "win": win,
        "cex_confirmed": None,
        "capacity": {
            "depth_by_tick": [
                {"targets": {"25": cap25, "50": False}, "notional_usd": 25.0 if cap25 else 5.0},
                {"targets": {"25": cap25, "50": False}, "notional_usd": 35.0 if cap25 else 10.0},
                {"targets": {"25": cap25, "50": cap50_plus2}, "notional_usd": 55.0 if cap50_plus2 else 20.0},
            ],
        },
    }


def test_live_candidate_gate_blocks_on_trimmed_roi_before_capacity():
    rows = [
        _closed_row(pnl=95.0, win=True, cap25=False, cap50_plus2=False),
        *[
            _closed_row(pnl=-5.0, win=False, cap25=False, cap50_plus2=False)
            for _ in range(20)
        ],
    ]

    gate = live_candidate_gate(validation_splits(rows))

    assert gate["status"] == "blocked_by_trimmed_roi"
    assert gate["live_ready"] is False
    assert "ex_largest_two_roi_positive" in gate["reasons"]
    assert gate["checks"]["capacity_25_at_limit"]["pass"] is False


def test_live_candidate_gate_candidate_when_trimmed_roi_and_capacity_pass():
    rows = [
        _closed_row(pnl=95.0, win=True),
        _closed_row(pnl=95.0, win=True),
        _closed_row(pnl=95.0, win=True),
        *[_closed_row(pnl=-1.0, win=False) for _ in range(17)],
    ]

    gate = live_candidate_gate(validation_splits(rows))

    assert gate["status"] == "candidate"
    assert gate["live_ready"] is True
    assert gate["reasons"] == []
    assert gate["capacity_policy"]["targets_usd"]["25"]["at_limit"] == 100.0
