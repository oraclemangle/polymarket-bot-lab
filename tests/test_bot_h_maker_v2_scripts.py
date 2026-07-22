"""Tests for Bot H Maker V2 helper scripts.

Covers:

- `scripts/bot_h_maker_v2_recorder_daily_report.py`: recorder health
  flag derivation, disk-budget extrapolation, render of the empty-DB
  case.
- `scripts/research/maker_flow_recorder_replay.py`: pure-function
  pieces of the simulator kernel (rebate per share, gross PnL per
  share, toxicity score, robustness verdict). The end-to-end run
  needs a live DB and is exercised on the VPS via the `--min-events`
  guard.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bots.bot_h_maker_v2.schema import init_db

# ---------------------------------------------------------------------------
# Daily report — health flag derivation + render
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_recorder_db(tmp_path) -> Path:
    path = tmp_path / "test_maker_recorder.db"
    conn = init_db(path)
    conn.commit()
    conn.close()
    return path


def _insert_market(
    conn: sqlite3.Connection,
    *,
    condition_id: str,
    category: str,
    yes_token_id: str | None = None,
    no_token_id: str | None = None,
    now_ms: int,
    yes_won: int | None = None,
    status: str = "ACTIVE",
) -> None:
    conn.execute(
        """
        INSERT INTO markets (condition_id, yes_token_id, no_token_id, category, question,
                             end_date_ts, discovered_at_ms, last_seen_at_ms, status, yes_won)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            condition_id,
            yes_token_id or f"yes-{condition_id}",
            no_token_id or f"no-{condition_id}",
            category,
            f"Q {condition_id}",
            None,
            now_ms,
            now_ms,
            status,
            yes_won,
        ),
    )


def _insert_pm_event(
    conn: sqlite3.Connection,
    *,
    received_at_ms: int,
    event_type: str,
    asset_id: str | None = None,
    condition_id: str | None = None,
    subscription_id: str = "bot_h_maker_v2/all",
) -> None:
    conn.execute(
        """
        INSERT INTO pm_events (received_at_ms, subscription_id, event_type, asset_id,
                               condition_id, payload_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (received_at_ms, subscription_id, event_type, asset_id, condition_id, "{}"),
    )


def test_daily_report_handles_missing_db(tmp_path):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report

    nonexistent = tmp_path / "does_not_exist.db"
    report = build_report(db_path=nonexistent, lookback_hours=24)
    assert report["ok"] is False
    assert "not found" in report["reason"]


def test_daily_report_handles_empty_db(empty_recorder_db: Path):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report, render_markdown

    report = build_report(db_path=empty_recorder_db, lookback_hours=24)
    assert report["ok"] is True
    assert report["total_events_24h"] == 0
    assert report["total_events_lifetime"] == 0
    flags = report["health_flags"]
    assert "NO_HEARTBEATS_IN_LOOKBACK" in flags
    assert "NO_EVENTS_IN_LOOKBACK" in flags
    assert "NO_ACTIVE_MARKETS" in flags
    md = render_markdown(report)
    assert "NO_EVENTS_IN_LOOKBACK" in md


def test_daily_report_flags_stale_heartbeat(empty_recorder_db: Path):
    """If the most recent heartbeat is >120s old, the script must
    raise STALE_LAST_HEARTBEAT so the operator notices a silent stall."""
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report

    conn = sqlite3.connect(str(empty_recorder_db))
    very_old_ms = int(datetime.now(UTC).timestamp() * 1000) - 600_000  # 10 min ago
    conn.execute(
        "INSERT INTO heartbeats (received_at_ms, subscription_id, asset_id_count, note) "
        "VALUES (?, ?, ?, ?)",
        (very_old_ms, "test-sub", 5, "stale"),
    )
    conn.execute(
        "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, asset_id, condition_id, payload_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (very_old_ms, "test-sub", "book", "tok", "cond", "{}"),
    )
    conn.commit()
    conn.close()

    report = build_report(db_path=empty_recorder_db, lookback_hours=24)
    assert any("STALE_LAST_HEARTBEAT" in f for f in report["health_flags"])


def test_daily_report_renders_markdown_with_categories(empty_recorder_db: Path):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report, render_markdown

    conn = sqlite3.connect(str(empty_recorder_db))
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    for cat, n in (("politics", 5), ("sports", 2), ("crypto", 1)):
        conn.execute(
            """
            INSERT INTO markets (condition_id, yes_token_id, no_token_id, category, question,
                                 end_date_ts, discovered_at_ms, last_seen_at_ms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"cond-{cat}-{n}",
                f"yes-{cat}",
                f"no-{cat}",
                cat,
                f"Q{cat}",
                None,
                now_ms,
                now_ms,
                "ACTIVE",
            ),
        )
    conn.commit()
    conn.close()

    report = build_report(db_path=empty_recorder_db, lookback_hours=24)
    md = render_markdown(report)
    assert "politics" in md
    assert "sports" in md
    assert "crypto" in md


def test_daily_report_data_quality_flags_event_gaps(empty_recorder_db: Path):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report

    now = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    now_ms = int(now.timestamp() * 1000)
    conn = sqlite3.connect(str(empty_recorder_db))
    for offset_sec in (600, 570, 420, 390, 0):
        _insert_pm_event(
            conn,
            received_at_ms=now_ms - offset_sec * 1000,
            event_type="book",
            asset_id="tok",
            condition_id="cond",
        )
    conn.commit()
    conn.close()

    report = build_report(db_path=empty_recorder_db, lookback_hours=24, now=now)
    gaps = report["data_quality"]["event_gaps"]
    assert gaps["count"] == 2
    assert gaps["longest_gap_sec"] == pytest.approx(390.0)
    assert "EVENT_GAP_DETECTED(390s)" in report["health_flags"]


def test_daily_report_data_quality_detects_stale_top_of_book(empty_recorder_db: Path):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report, render_markdown

    now = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    now_ms = int(now.timestamp() * 1000)
    conn = sqlite3.connect(str(empty_recorder_db))
    token_pairs = []
    for idx, cat in enumerate(("politics", "sports", "awards", "crypto"), start=1):
        yes = f"yes-{idx}"
        no = f"no-{idx}"
        token_pairs.extend((yes, no))
        _insert_market(
            conn,
            condition_id=f"cond-{idx}",
            category=cat,
            yes_token_id=yes,
            no_token_id=no,
            now_ms=now_ms,
        )
    for token in token_pairs[:6]:
        _insert_pm_event(
            conn,
            received_at_ms=now_ms - 30_000,
            event_type="best_bid_ask",
            asset_id=token,
            condition_id=f"cond-{token[-1]}",
        )
    _insert_pm_event(
        conn,
        received_at_ms=now_ms - 300_000,
        event_type="book",
        asset_id=token_pairs[6],
        condition_id="cond-4",
    )
    conn.commit()
    conn.close()

    report = build_report(db_path=empty_recorder_db, lookback_hours=24, now=now)
    tob = report["data_quality"]["top_of_book"]
    assert tob["active_token_count"] == 8
    assert tob["fresh_token_count"] == 6
    assert tob["stale_token_count"] == 1
    assert tob["missing_token_count"] == 1
    md = render_markdown(report)
    assert "Top-of-book freshness" in md


def test_daily_report_data_quality_freshness_percentiles(empty_recorder_db: Path):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report

    now = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    now_ms = int(now.timestamp() * 1000)
    conn = sqlite3.connect(str(empty_recorder_db))
    ages_sec = [5, 10, 30, 60, 180, 300]
    for idx in range(3):
        _insert_market(
            conn,
            condition_id=f"cond-{idx}",
            category="politics",
            yes_token_id=f"yes-{idx}",
            no_token_id=f"no-{idx}",
            now_ms=now_ms,
        )
    for token, age_sec in zip(
        ["yes-0", "no-0", "yes-1", "no-1", "yes-2", "no-2"],
        ages_sec,
        strict=True,
    ):
        _insert_pm_event(
            conn,
            received_at_ms=now_ms - age_sec * 1000,
            event_type="best_bid_ask",
            asset_id=token,
            condition_id=f"cond-{token[-1]}",
        )
    conn.commit()
    conn.close()

    report = build_report(db_path=empty_recorder_db, lookback_hours=24, now=now)
    pct = report["data_quality"]["freshness_percentiles"]
    assert pct["count"] == 6
    assert pct["p50_sec"] == pytest.approx(30.0)
    assert pct["p90_sec"] == pytest.approx(300.0)
    assert pct["p95_sec"] == pytest.approx(300.0)
    assert pct["p99_sec"] == pytest.approx(300.0)
    assert pct["max_sec"] == pytest.approx(300.0)


def test_daily_report_data_quality_reconnect_heartbeat_timeline(empty_recorder_db: Path):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report

    now = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    now_ms = int(now.timestamp() * 1000)
    conn = sqlite3.connect(str(empty_recorder_db))
    for offset_sec in (300, 200, 100):
        conn.execute(
            "INSERT INTO heartbeats (received_at_ms, subscription_id, asset_id_count, note) "
            "VALUES (?, ?, ?, ?)",
            (now_ms - offset_sec * 1000, "bot_h_maker_v2/all", 5, "ok"),
        )
    _insert_pm_event(conn, received_at_ms=now_ms - 250_000, event_type="reconnect")
    _insert_pm_event(conn, received_at_ms=now_ms - 150_000, event_type="disconnect")
    _insert_pm_event(conn, received_at_ms=now_ms - 50_000, event_type="reconnect")
    conn.commit()
    conn.close()

    report = build_report(db_path=empty_recorder_db, lookback_hours=24, now=now)
    timeline = report["data_quality"]["reconnect_heartbeat_timeline"]
    assert timeline["reconnect_count"] == 2
    assert timeline["disconnect_count"] == 1
    assert timeline["heartbeat_count"] == 3
    timestamps = [e["timestamp_ms"] for e in timeline["events"]]
    assert timestamps == sorted(timestamps)
    assert {"timestamp_ms", "kind", "subscription_id"} <= timeline["events"][0].keys()


def test_daily_report_data_quality_markov_event_states(empty_recorder_db: Path):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report, render_markdown

    now = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    now_ms = int(now.timestamp() * 1000)
    conn = sqlite3.connect(str(empty_recorder_db))
    for idx, event_type in enumerate(
        ("best_bid_ask", "best_bid_ask", "last_trade_price", "price_change", "reconnect")
    ):
        _insert_pm_event(
            conn,
            received_at_ms=now_ms - (5 - idx) * 1000,
            event_type=event_type,
            asset_id="tok",
            condition_id="cond",
        )
    conn.commit()
    conn.close()

    report = build_report(db_path=empty_recorder_db, lookback_hours=24, now=now)
    markov = report["data_quality"]["markov_event_states"]
    assert markov["posture"] == "research_only_no_live_gate"
    assert markov["n_events"] == 5
    top_idx = markov["states"].index("top_of_book")
    trade_idx = markov["states"].index("trade")
    assert markov["transition_counts"][top_idx][top_idx] == 1
    assert markov["transition_counts"][top_idx][trade_idx] == 1
    assert "Markov event states" in render_markdown(report)


def test_daily_report_data_quality_category_coverage_includes_zero_categories(
    empty_recorder_db: Path,
):
    from scripts.bot_h_maker_v2_recorder_daily_report import build_report, render_markdown

    now = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    now_ms = int(now.timestamp() * 1000)
    conn = sqlite3.connect(str(empty_recorder_db))
    _insert_market(conn, condition_id="cond-politics", category="politics", now_ms=now_ms,
                   yes_won=1)
    _insert_market(conn, condition_id="cond-politics-resolved", category="politics",
                   now_ms=now_ms, yes_won=0, status="RESOLVED")
    _insert_market(conn, condition_id="cond-sports", category="sports", now_ms=now_ms)
    _insert_market(conn, condition_id="cond-crypto", category="crypto", now_ms=now_ms,
                   yes_won=0)
    _insert_pm_event(
        conn,
        received_at_ms=now_ms - 30_000,
        event_type="best_bid_ask",
        asset_id="yes-cond-politics",
        condition_id="cond-politics",
    )
    _insert_pm_event(
        conn,
        received_at_ms=now_ms - 30_000,
        event_type="best_bid_ask",
        asset_id="yes-cond-politics-resolved",
        condition_id="cond-politics-resolved",
    )
    _insert_pm_event(
        conn,
        received_at_ms=now_ms - 30_000,
        event_type="book",
        asset_id="yes-cond-crypto",
        condition_id="cond-crypto",
    )
    conn.commit()
    conn.close()

    report = build_report(db_path=empty_recorder_db, lookback_hours=24, now=now)
    coverage = report["data_quality"]["category_coverage"]
    assert coverage["expected_categories"] == ["politics", "sports", "awards", "crypto"]
    assert coverage["missing_categories"] == ["awards"]
    assert coverage["categories"]["awards"]["active_markets"] == 0
    assert coverage["categories"]["politics"]["active_markets"] == 1
    assert coverage["categories"]["politics"]["resolved_markets"] == 2
    assert coverage["categories"]["politics"]["replayable_markets"] == 2
    md = render_markdown(report)
    assert "Missing categories: `awards`" in md


# ---------------------------------------------------------------------------
# Replay simulator kernel
# ---------------------------------------------------------------------------


def test_rebate_per_share_matches_simulator():
    """Per-category rebate formula must exactly match the SQL CASE in
    `/tmp/track1_maker_sim.py` so recorder-replay numbers are
    comparable to the WANGZJ historical baseline."""
    from scripts.research.maker_flow_recorder_replay import _rebate_per_share

    # politics: 0.030 * p * (1-p) * 0.25 builder share
    assert abs(
        _rebate_per_share("politics", 0.05) - 0.030 * 0.05 * 0.95 * 0.25
    ) < 1e-9
    # sports: same formula
    assert abs(
        _rebate_per_share("sports", 0.15) - 0.030 * 0.15 * 0.85 * 0.25
    ) < 1e-9
    # crypto: 0.072 base x 0.20 share
    assert abs(
        _rebate_per_share("crypto", 0.05) - 0.072 * 0.05 * 0.95 * 0.20
    ) < 1e-9
    # weather: 0 (no rebate) — recorder excludes weather but kernel must still return 0
    assert _rebate_per_share("weather", 0.05) == 0.0


def test_gross_pnl_per_share_matches_simulator():
    """When YES wins, maker is short YES at entry_price and owes
    $1/share, net = -1 + entry_price. When NO wins, maker keeps
    entry_price."""
    from scripts.research.maker_flow_recorder_replay import _gross_pnl_per_share

    assert _gross_pnl_per_share(0.05, yes_won=1) == pytest.approx(-0.95)
    assert _gross_pnl_per_share(0.05, yes_won=0) == pytest.approx(0.05)
    # Unresolved → None (must not feed the simulator)
    assert _gross_pnl_per_share(0.05, yes_won=None) is None


def test_toxicity_score_returns_one_when_price_drifts_up():
    from scripts.research.maker_flow_recorder_replay import TradeObs, _toxicity_score

    trade = TradeObs(
        condition_id="c1",
        asset_id="t1",
        timestamp_ms=1_000_000,
        price=0.05,
        size_shares=100.0,
        usd_amount=5.0,
        category="politics",
        yes_won=None,
    )
    # Price drifted from 0.05 → 0.10 in next 15 min: toxic
    price_index = {
        "c1": [
            (1_060_000, 0.10),  # +1 min
            (1_400_000, 0.12),  # +6.67 min
            (1_800_000, 0.15),  # +13.33 min
        ]
    }
    assert _toxicity_score(trade=trade, price_index=price_index) == 1


def test_toxicity_score_returns_zero_when_price_flat_or_lower():
    from scripts.research.maker_flow_recorder_replay import TradeObs, _toxicity_score

    trade = TradeObs(
        condition_id="c1",
        asset_id="t1",
        timestamp_ms=1_000_000,
        price=0.05,
        size_shares=100.0,
        usd_amount=5.0,
        category="politics",
        yes_won=None,
    )
    price_index = {
        "c1": [
            (1_060_000, 0.06),
            (1_400_000, 0.05),
            (1_800_000, 0.04),
        ]
    }
    assert _toxicity_score(trade=trade, price_index=price_index) == 0


def test_toxicity_score_returns_zero_when_no_data():
    """Match simulator's `next_15min_avg_price IS NULL THEN 0` rule:
    treat absent follow-up data as benign so we don't artificially
    inflate AS adjustment."""
    from scripts.research.maker_flow_recorder_replay import TradeObs, _toxicity_score

    trade = TradeObs(
        condition_id="c1",
        asset_id="t1",
        timestamp_ms=1_000_000,
        price=0.05,
        size_shares=100.0,
        usd_amount=5.0,
        category="politics",
        yes_won=None,
    )
    assert _toxicity_score(trade=trade, price_index={}) == 0


def test_verdict_pass_when_all_combos_above_pass_bar():
    from scripts.research.maker_flow_recorder_replay import _verdict

    # All 5 sensitivity combos report excl-top-5 above +20%, ≥5 markets each
    combos = {
        f"combo-{i}": {
            "n_markets": 100,
            "excl_5": 30.0 + i,
        }
        for i in range(5)
    }
    assert _verdict(combos) == "PASS"


def test_verdict_fail_when_any_combo_below_pass_bar():
    from scripts.research.maker_flow_recorder_replay import _verdict

    combos = {
        "combo-1": {"n_markets": 100, "excl_5": 25.0},
        "combo-2": {"n_markets": 100, "excl_5": 15.0},  # below bar
    }
    assert _verdict(combos) == "FAIL"


def test_verdict_insufficient_data_when_too_few_markets():
    from scripts.research.maker_flow_recorder_replay import _verdict

    combos = {
        "combo-1": {"n_markets": 4, "excl_5": 50.0},  # not enough markets to drop 5
    }
    assert _verdict(combos) == "INSUFFICIENT_DATA"


def test_replay_returns_insufficient_data_on_low_event_count(empty_recorder_db: Path):
    from scripts.research.maker_flow_recorder_replay import run_replay

    report = run_replay(db_path=empty_recorder_db, min_events=1000)
    assert report["ok"] is False
    assert "≥" in report["reason"] or "need" in report["reason"]
    assert report["n_events"] == 0
