"""Phase 4 audit remediation tests — realistic maker-fill sim, per-fill
Event emission, adverse-selection halt wiring, calibration-gate runner."""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest


def _make_spike_db(
    tmp_path: Path,
    *,
    signal_time_ms: int,
    asset_id: str,
    post_signal_trades: list[tuple[int, float]],
) -> Path:
    """Create a minimal recorder-shaped DB for fill-sim tests."""
    db = tmp_path / "r.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "CREATE TABLE pm_events (received_at_ms INTEGER, subscription_id TEXT, "
            "event_type TEXT, asset_id TEXT, condition_id TEXT, payload_json TEXT)"
        )
        # Write last_trade_price events for the target asset at the given times.
        for ts, price in post_signal_trades:
            conn.execute(
                "INSERT INTO pm_events VALUES (?, 's1', 'last_trade_price', ?, 'c1', ?)",
                (ts, asset_id, json.dumps({"price": price, "size": 1.0})),
            )
        conn.commit()
    finally:
        conn.close()
    return db


class TestMakerFillSim:
    def test_no_fill_when_no_trades_cross_limit(self, tmp_path):
        from scripts.bot_e_calibration_spike import SignalObs, simulate_maker_fills
        db_path = _make_spike_db(
            tmp_path,
            signal_time_ms=1_000_000,
            asset_id="TKY",
            post_signal_trades=[
                (1_001_000, 0.50),  # above our maker limit 0.49
                (1_050_000, 0.495),
            ],
        )
        sig = SignalObs(
            sub_id="s1", obi=0.3, abs_obi=0.3, side="BUY_YES",
            ts_ms=1_000_000, end_ms=2_000_000, min_to_expiry=8.0,
            asset_id_at_signal="TKY",
            signal_price=0.50,
            maker_limit=0.49,
        )
        conn = sqlite3.connect(str(db_path))
        try:
            simulate_maker_fills(conn, [sig], fill_timeout_sec=60.0)
        finally:
            conn.close()
        assert sig.filled is False

    def test_fill_when_trade_crosses_limit(self, tmp_path):
        from scripts.bot_e_calibration_spike import SignalObs, simulate_maker_fills
        db_path = _make_spike_db(
            tmp_path,
            signal_time_ms=1_000_000,
            asset_id="TKY",
            post_signal_trades=[
                (1_001_000, 0.50),
                (1_005_000, 0.49),  # crosses our 0.49 limit
                (1_010_000, 0.48),
            ],
        )
        sig = SignalObs(
            sub_id="s1", obi=0.3, abs_obi=0.3, side="BUY_YES",
            ts_ms=1_000_000, end_ms=2_000_000, min_to_expiry=8.0,
            asset_id_at_signal="TKY",
            signal_price=0.50,
            maker_limit=0.49,
        )
        conn = sqlite3.connect(str(db_path))
        try:
            simulate_maker_fills(conn, [sig], fill_timeout_sec=60.0)
        finally:
            conn.close()
        assert sig.filled is True
        assert sig.fill_price == 0.49
        assert sig.fill_ts_ms == 1_005_000

    def test_timeout_blocks_late_fill(self, tmp_path):
        from scripts.bot_e_calibration_spike import SignalObs, simulate_maker_fills
        db_path = _make_spike_db(
            tmp_path,
            signal_time_ms=1_000_000,
            asset_id="TKY",
            post_signal_trades=[
                (1_999_999, 0.40),  # crosses limit but after 60s timeout
            ],
        )
        sig = SignalObs(
            sub_id="s1", obi=0.3, abs_obi=0.3, side="BUY_YES",
            ts_ms=1_000_000, end_ms=2_000_000, min_to_expiry=8.0,
            asset_id_at_signal="TKY",
            signal_price=0.50,
            maker_limit=0.49,
        )
        conn = sqlite3.connect(str(db_path))
        try:
            simulate_maker_fills(conn, [sig], fill_timeout_sec=60.0)
        finally:
            conn.close()
        assert sig.filled is False

    def test_since_until_filter_excludes_out_of_window_cross(self, tmp_path):
        from scripts.bot_e_calibration_spike import SignalObs, simulate_maker_fills
        db_path = _make_spike_db(
            tmp_path,
            signal_time_ms=1_000_000,
            asset_id="TKY",
            post_signal_trades=[
                (1_005_000, 0.49),
            ],
        )
        sig = SignalObs(
            sub_id="s1", obi=0.3, abs_obi=0.3, side="BUY_YES",
            ts_ms=1_000_000, end_ms=2_000_000, min_to_expiry=8.0,
            asset_id_at_signal="TKY",
            signal_price=0.50,
            maker_limit=0.49,
        )
        conn = sqlite3.connect(str(db_path))
        try:
            simulate_maker_fills(
                conn,
                [sig],
                fill_timeout_sec=60.0,
                since_ms=1_006_000,
                until_ms=1_100_000,
            )
        finally:
            conn.close()
        assert sig.filled is False


class TestAdverseSelectionMeasurement:
    def test_adverse_when_price_falls_after_fill(self, tmp_path):
        from scripts.bot_e_calibration_spike import (
            SignalObs,
            measure_adverse_selection,
        )
        db_path = _make_spike_db(
            tmp_path,
            signal_time_ms=1_000_000,
            asset_id="TKY",
            post_signal_trades=[
                (1_005_000, 0.49),  # fill
                (1_010_000, 0.48),  # 5s after fill
                (1_030_000, 0.45),  # 25s after fill (before 30s window)
                (1_040_000, 0.44),  # 35s after fill (past window)
            ],
        )
        sig = SignalObs(
            sub_id="s1", obi=0.3, abs_obi=0.3, side="BUY_YES",
            ts_ms=1_000_000, end_ms=2_000_000, min_to_expiry=8.0,
            asset_id_at_signal="TKY",
            signal_price=0.50, maker_limit=0.49,
            filled=True, fill_ts_ms=1_005_000, fill_price=0.49,
        )
        conn = sqlite3.connect(str(db_path))
        try:
            measure_adverse_selection(conn, [sig], measure_window_sec=30.0)
        finally:
            conn.close()
        assert sig.midpoint_after_fill == 0.45
        assert sig.moved_against is True

    def test_not_adverse_when_price_rises(self, tmp_path):
        from scripts.bot_e_calibration_spike import (
            SignalObs,
            measure_adverse_selection,
        )
        db_path = _make_spike_db(
            tmp_path,
            signal_time_ms=1_000_000,
            asset_id="TKY",
            post_signal_trades=[
                (1_005_000, 0.49),
                (1_020_000, 0.55),
            ],
        )
        sig = SignalObs(
            sub_id="s1", obi=0.3, abs_obi=0.3, side="BUY_YES",
            ts_ms=1_000_000, end_ms=2_000_000, min_to_expiry=8.0,
            asset_id_at_signal="TKY",
            signal_price=0.50, maker_limit=0.49,
            filled=True, fill_ts_ms=1_005_000, fill_price=0.49,
        )
        conn = sqlite3.connect(str(db_path))
        try:
            measure_adverse_selection(conn, [sig], measure_window_sec=30.0)
        finally:
            conn.close()
        assert sig.moved_against is False


class TestComputeFillAndAdverseRates:
    def test_rates_on_mixed_population(self):
        from scripts.bot_e_calibration_spike import (
            SignalObs,
            compute_fill_and_adverse_rates,
        )
        def mk(filled, moved_against=None):
            s = SignalObs(
                sub_id="s", obi=0.3, abs_obi=0.3, side="BUY_YES",
                ts_ms=0, end_ms=1, min_to_expiry=8.0,
                asset_id_at_signal="TKY",
                signal_price=0.5, maker_limit=0.49,
            )
            s.filled = filled
            if filled:
                s.fill_ts_ms = 1000
                s.fill_price = 0.49
                s.moved_against = moved_against
            return s
        sigs = [
            mk(True, moved_against=True),
            mk(True, moved_against=False),
            mk(True, moved_against=True),
            mk(False),
            mk(False),
            mk(False),
        ]
        stats = compute_fill_and_adverse_rates(sigs)
        assert stats["n_signals_eligible"] == 6
        assert stats["n_signals_filled"] == 3
        assert stats["fill_rate"] == pytest.approx(0.5)
        assert stats["n_fills_measured"] == 3
        assert stats["n_fills_adverse"] == 2
        assert stats["adverse_rate"] == pytest.approx(2 / 3)


class TestDecideFillGates:
    def test_fill_rate_below_threshold_blocks_go(self):
        from scripts.bot_e_calibration_spike import BucketStats, decide
        go, reasons = decide(
            buckets={"0.20-0.30": BucketStats("0.20-0.30", n=200, n_win=104, sum_abs_obi=50)},
            overall_wr=0.52,
            overall_n=200,
            weighted_ece=0.05,
            fill_stats={
                "n_signals_eligible": 200,
                "n_signals_filled": 40,
                "fill_rate": 0.20,  # below 0.30 threshold
                "n_fills_measured": 30,
                "n_fills_adverse": 10,
                "adverse_rate": 0.33,
            },
        )
        assert go is False
        assert any("fill rate" in r for r in reasons)

    def test_adverse_rate_above_threshold_blocks_go(self):
        from scripts.bot_e_calibration_spike import BucketStats, decide
        go, reasons = decide(
            buckets={"0.20-0.30": BucketStats("0.20-0.30", n=200, n_win=104, sum_abs_obi=50)},
            overall_wr=0.52,
            overall_n=200,
            weighted_ece=0.05,
            fill_stats={
                "n_signals_eligible": 200,
                "n_signals_filled": 80,
                "fill_rate": 0.40,
                "n_fills_measured": 80,
                "n_fills_adverse": 55,
                "adverse_rate": 0.6875,  # above 0.60 threshold
            },
        )
        assert go is False
        assert any("adverse" in r.lower() for r in reasons)

    def test_all_gates_green(self):
        from scripts.bot_e_calibration_spike import BucketStats, decide
        go, reasons = decide(
            buckets={"0.20-0.30": BucketStats("0.20-0.30", n=200, n_win=120, sum_abs_obi=50)},
            overall_wr=0.60,
            overall_n=250,
            weighted_ece=0.05,
            fill_stats={
                "n_signals_eligible": 250,
                "n_signals_filled": 100,
                "fill_rate": 0.40,
                "n_fills_measured": 100,
                "n_fills_adverse": 40,
                "adverse_rate": 0.40,
            },
        )
        assert go is True
        assert reasons == []


class TestFillEventEmission:
    def test_emits_event_for_new_fill(self, tmp_db, monkeypatch):
        """_emit_new_fill_events_and_track writes a bot_e.fill Event for
        each new Trade row and registers it with the tracker."""
        from sqlalchemy import select

        from bots.bot_e_btc_scalp.__main__ import (
            _emit_new_fill_events_and_track,
            _emitted_fill_trade_ids,
        )
        from bots.bot_e_btc_scalp.adverse_selection import AdverseSelectionTracker
        from core.db import Event, Trade, get_session_factory
        # Clear module-level set (tests share interpreter).
        _emitted_fill_trade_ids.clear()
        with get_session_factory()() as s:
            s.add(Trade(
                trade_id="t_phase4", bot_id="bot_e", order_id=None,
                condition_id="c1", token_id="TK1", side="BUY",
                price=Decimal("0.50"), size=Decimal("10"),
                fee_usd=Decimal("0"),
                filled_at=datetime.now(UTC),
                usd_gbp_rate=Decimal("0.80"), gbp_notional=Decimal("4"),
            ))
            s.commit()
        tracker = AdverseSelectionTracker()
        count = _emit_new_fill_events_and_track(tracker)
        assert count == 1
        with get_session_factory()() as s:
            evs = list(s.scalars(
                select(Event).where(Event.event_type == "bot_e.fill")
            ))
            assert len(evs) == 1
            assert evs[0].payload["trade_id"] == "t_phase4"

    def test_idempotent_on_same_trade(self, tmp_db, monkeypatch):
        from bots.bot_e_btc_scalp.__main__ import (
            _emit_new_fill_events_and_track,
            _emitted_fill_trade_ids,
        )
        from bots.bot_e_btc_scalp.adverse_selection import AdverseSelectionTracker
        from core.db import Trade, get_session_factory
        _emitted_fill_trade_ids.clear()
        with get_session_factory()() as s:
            s.add(Trade(
                trade_id="t_once", bot_id="bot_e", order_id=None,
                condition_id="c1", token_id="TK1", side="BUY",
                price=Decimal("0.50"), size=Decimal("10"),
                fee_usd=Decimal("0"),
                filled_at=datetime.now(UTC),
                usd_gbp_rate=Decimal("0.80"), gbp_notional=Decimal("4"),
            ))
            s.commit()
        tracker = AdverseSelectionTracker()
        n1 = _emit_new_fill_events_and_track(tracker)
        n2 = _emit_new_fill_events_and_track(tracker)
        assert n1 == 1
        assert n2 == 0
