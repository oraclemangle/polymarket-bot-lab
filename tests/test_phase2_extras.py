"""Phase 2 audit remediation extras — EWMA OBI, gap detection, lot-based PnL."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bots.bot_e_btc_scalp.signal import SubscriptionTrades
from bots.bot_e_btc_scalp.sizer import OpenPosition, size_maker_entry
from core.backtest_bot_e import (
    RecorderGap,
    detect_gaps,
    in_quarantine,
    quarantine_ranges,
)


# ---------------------------------------------------------------------------
# EWMA OBI (2.7)
# ---------------------------------------------------------------------------


def _sub_with(trades_yes: list[tuple[int, Decimal]], trades_no: list[tuple[int, Decimal]]):
    sub = SubscriptionTrades(subscription_id="s1")
    sub.set_tokens(yes_token_id="TY", no_token_id="TN")
    for ts, sz in trades_yes:
        sub.record_trade(ts, "TY", sz)
    for ts, sz in trades_no:
        sub.record_trade(ts, "TN", sz)
    return sub


class TestEwmaObi:
    def test_rectangular_matches_simple_sum(self):
        # YES 10 @ t-100s; NO 10 @ t-1s. Rectangular window → OBI = 0.
        now_ms = 120_000
        sub = _sub_with(
            trades_yes=[(20_000, Decimal("10"))],  # 100s old
            trades_no=[(119_000, Decimal("10"))],  # 1s old
        )
        obi, n, vol = sub.compute_obi(
            now_ms, window_sec=120, min_trades=1, min_volume=Decimal("1"),
            decay_half_life_sec=0.0,
        )
        assert obi == pytest.approx(0.0)
        assert n == 2
        assert vol == Decimal("20")

    def test_ewma_weights_recent_higher(self):
        # Same config as above, but EWMA with 30s half-life should favour
        # the recent NO trade heavily → negative OBI.
        now_ms = 120_000
        sub = _sub_with(
            trades_yes=[(20_000, Decimal("10"))],  # 100s old → 0.5^(100/30) ≈ 0.099
            trades_no=[(119_000, Decimal("10"))],  # 1s old  → 0.5^(1/30) ≈ 0.977
        )
        obi, n, _vol = sub.compute_obi(
            now_ms, window_sec=120, min_trades=1, min_volume=Decimal("1"),
            decay_half_life_sec=30.0,
        )
        assert obi is not None
        assert obi < -0.7  # strongly negative; NO flow dominates

    def test_ewma_symmetric_equal_weight_at_mirror_ages(self):
        # Two trades at identical ages should cancel exactly.
        now_ms = 100_000
        sub = _sub_with(
            trades_yes=[(90_000, Decimal("5"))],
            trades_no=[(90_000, Decimal("5"))],
        )
        obi, _n, _v = sub.compute_obi(
            now_ms, window_sec=60, min_trades=1, min_volume=Decimal("1"),
            decay_half_life_sec=30.0,
        )
        assert obi == pytest.approx(0.0)

    def test_volume_gate_uses_raw_not_decayed(self):
        # Two 0.6-size trades (raw total 1.2), decayed to ~0.02 each. Volume
        # gate of 1.0 should still pass because it checks the raw total.
        now_ms = 1_000_000
        sub = _sub_with(
            trades_yes=[(0, Decimal("0.6"))],
            trades_no=[(0, Decimal("0.6"))],
        )
        obi, _n, _v = sub.compute_obi(
            now_ms, window_sec=2000, min_trades=1, min_volume=Decimal("1"),
            decay_half_life_sec=30.0,
        )
        assert obi == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Gap detection (2.8)
# ---------------------------------------------------------------------------


def _make_recorder_db(tmp_path: Path, pm_ts: list[int], cex_ts: list[int]) -> Path:
    db_path = tmp_path / "recorder.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE pm_events (received_at_ms INTEGER, subscription_id TEXT, "
            "event_type TEXT, asset_id TEXT, condition_id TEXT, payload_json TEXT)"
        )
        conn.execute(
            "CREATE TABLE cex_trades (received_at_ms INTEGER, trade_time_ms INTEGER, "
            "symbol TEXT, price REAL, size REAL, is_buyer_maker INTEGER)"
        )
        for ts in pm_ts:
            conn.execute(
                "INSERT INTO pm_events VALUES (?, 's', 'book', 'a', 'c', '{}')",
                (ts,),
            )
        for ts in cex_ts:
            conn.execute(
                "INSERT INTO cex_trades VALUES (?, ?, 'BTC', 1.0, 0.1, 0)",
                (ts, ts),
            )
        conn.commit()
    finally:
        conn.close()
    return db_path


class TestGapDetection:
    def test_no_gaps_when_evenly_spaced(self, tmp_path):
        db = _make_recorder_db(tmp_path, pm_ts=[1000, 2000, 3000], cex_ts=[1000, 2000, 3000])
        assert detect_gaps(db, max_gap_ms=1500) == []

    def test_flags_pm_gap(self, tmp_path):
        db = _make_recorder_db(
            tmp_path,
            pm_ts=[1000, 2000, 30_000, 31_000],  # 28s gap between 2000 and 30000
            cex_ts=[1000, 2000, 3000],
        )
        gaps = detect_gaps(db, max_gap_ms=5000)
        assert len(gaps) == 1
        g = gaps[0]
        assert g.feed == "pm_events"
        assert g.start_ms == 2000
        assert g.end_ms == 30_000
        assert g.gap_ms == 28_000

    def test_flags_cex_gap_independently(self, tmp_path):
        db = _make_recorder_db(
            tmp_path,
            pm_ts=[1000, 2000, 3000],
            cex_ts=[1000, 50_000],  # 49s gap
        )
        gaps = detect_gaps(db, max_gap_ms=5000)
        assert len(gaps) == 1
        assert gaps[0].feed == "cex_trades"

    def test_quarantine_ranges_merge(self):
        g1 = RecorderGap("pm_events", 1000, 5000, 4000)
        g2 = RecorderGap("pm_events", 6000, 9000, 3000)  # buffers will overlap
        ranges = quarantine_ranges([g1, g2], buffer_ms=2000)
        # After buffer: (-1000, 7000) and (4000, 11000) → merge to (-1000, 11000)
        assert ranges == [(-1000, 11000)]

    def test_in_quarantine(self):
        ranges = [(1000, 2000), (5000, 7000)]
        assert in_quarantine(1500, ranges) is True
        assert in_quarantine(3000, ranges) is False
        assert in_quarantine(5000, ranges) is True
        assert in_quarantine(7000, ranges) is True
        assert in_quarantine(10_000, ranges) is False


# ---------------------------------------------------------------------------
# Lot-based realized PnL (2.5)
# ---------------------------------------------------------------------------


class TestLotBasedRealisedPnl:
    def test_single_round_trip(self, tmp_db):
        # BUY 10@0.50 then SELL 10@0.60 → realised = (0.60-0.50)*10 = 1.0 (minus fees)
        from core.db import Trade, get_session_factory
        from core.portfolio import Portfolio
        now = datetime.now(UTC)
        with get_session_factory()() as s:
            s.add(Trade(
                trade_id="t1", bot_id="bot_x", order_id=None,
                condition_id="c1", token_id="TK", side="BUY",
                price=Decimal("0.50"), size=Decimal("10"),
                fee_usd=Decimal("0"),
                filled_at=now,
                usd_gbp_rate=Decimal("0.80"), gbp_notional=Decimal("4"),
            ))
            s.add(Trade(
                trade_id="t2", bot_id="bot_x", order_id=None,
                condition_id="c1", token_id="TK", side="SELL",
                price=Decimal("0.60"), size=Decimal("10"),
                fee_usd=Decimal("0"),
                filled_at=now + timedelta(seconds=1),
                usd_gbp_rate=Decimal("0.80"), gbp_notional=Decimal("4.8"),
            ))
            s.commit()
        p = Portfolio()
        assert p.get_realised_pnl("bot_x") == Decimal("1.0")

    def test_re_entry_does_not_blend_lots(self, tmp_db):
        # BUY 10@0.50, SELL 10@0.60 (realised +1.0)
        # BUY 10@0.70, SELL 10@0.80 (realised +1.0)
        # Lifetime-average would blend to avg=(0.50+0.70)/2=0.60, so second
        # round would appear as 10*(0.80-0.60)=2.0 → distorted.
        # Lot-based FIFO: each round is independent. Total realised = +2.0.
        from core.db import Trade, get_session_factory
        from core.portfolio import Portfolio
        t0 = datetime.now(UTC)
        with get_session_factory()() as s:
            for i, (side, price, offset) in enumerate([
                ("BUY", "0.50", 0),
                ("SELL", "0.60", 1),
                ("BUY", "0.70", 2),
                ("SELL", "0.80", 3),
            ]):
                s.add(Trade(
                    trade_id=f"t{i}", bot_id="bot_x", order_id=None,
                    condition_id="c1", token_id="TK", side=side,
                    price=Decimal(price), size=Decimal("10"),
                    fee_usd=Decimal("0"),
                    filled_at=t0 + timedelta(seconds=offset),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal(price) * Decimal("10") * Decimal("0.80"),
                ))
            s.commit()
        p = Portfolio()
        # +1.0 + +1.0 = +2.0 — each round independent under lot-based.
        assert p.get_realised_pnl("bot_x") == Decimal("2.0")

    def test_orphan_sell_is_skipped(self, tmp_db, caplog):
        # SELL with no prior BUY → logged, not counted.
        import logging
        from core.db import Trade, get_session_factory
        from core.portfolio import Portfolio
        with get_session_factory()() as s:
            s.add(Trade(
                trade_id="orphan", bot_id="bot_x", order_id=None,
                condition_id="c1", token_id="TK", side="SELL",
                price=Decimal("0.90"), size=Decimal("5"),
                fee_usd=Decimal("0"),
                filled_at=datetime.now(UTC),
                usd_gbp_rate=Decimal("0.80"), gbp_notional=Decimal("3.6"),
            ))
            s.commit()
        p = Portfolio()
        with caplog.at_level(logging.WARNING):
            assert p.get_realised_pnl("bot_x") == Decimal("0")
        assert any("orphan_sell" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Correlation-adjusted crypto bucket cap (2.4)
# ---------------------------------------------------------------------------


class TestCorrelationAdjustedBucketCap:
    def test_single_symbol_not_inflated(self):
        # One existing BTC position + adding more BTC: correlation adj should
        # not apply (single-asset bucket).
        existing = [OpenPosition(
            subscription_id="btc1", symbol="BTC", side="BUY_YES",
            notional_usd=Decimal("8"), is_crypto=True,
        )]
        sd = size_maker_entry(
            signal_side="BUY_YES",
            limit_price=Decimal("0.50"),
            bankroll_usd=Decimal("100"),
            fixed_trade_usd=Decimal("2"),
            per_trade_cap_frac=Decimal("0.10"),
            crypto_bucket_cap_frac=Decimal("0.10"),
            aggregate_cap_frac=Decimal("0.25"),
            open_positions=existing,
            symbol="BTC",
            is_crypto=True,
            crypto_correlation_adj=True,
            crypto_avg_correlation=Decimal("0.80"),
        )
        # 8 + 2 = 10 == cap (10% of 100); allowed.
        assert sd.can_enter is True

    def test_multi_symbol_inflated_blocks(self):
        # BTC 3 + ETH 3 existing; adding SOL 3 → raw 9, effective 9*sqrt(1.8)≈12.08.
        # Cap at 10% of 100 = 10; effective 12.08 > 10 → blocked.
        existing = [
            OpenPosition("btc1", "BTC", "BUY_YES", Decimal("3"), True),
            OpenPosition("eth1", "ETH", "BUY_YES", Decimal("3"), True),
        ]
        sd = size_maker_entry(
            signal_side="BUY_YES",
            limit_price=Decimal("0.50"),
            bankroll_usd=Decimal("100"),
            fixed_trade_usd=Decimal("3"),
            per_trade_cap_frac=Decimal("0.10"),
            crypto_bucket_cap_frac=Decimal("0.10"),
            aggregate_cap_frac=Decimal("0.25"),
            open_positions=existing,
            symbol="SOL",
            is_crypto=True,
            crypto_correlation_adj=True,
            crypto_avg_correlation=Decimal("0.80"),
        )
        assert sd.can_enter is False
        assert "crypto_bucket_cap" in sd.reason

    def test_disabled_corr_adj_allows_raw(self):
        existing = [
            OpenPosition("btc1", "BTC", "BUY_YES", Decimal("3"), True),
            OpenPosition("eth1", "ETH", "BUY_YES", Decimal("3"), True),
        ]
        sd = size_maker_entry(
            signal_side="BUY_YES",
            limit_price=Decimal("0.50"),
            bankroll_usd=Decimal("100"),
            fixed_trade_usd=Decimal("3"),
            per_trade_cap_frac=Decimal("0.10"),
            crypto_bucket_cap_frac=Decimal("0.10"),
            aggregate_cap_frac=Decimal("0.25"),
            open_positions=existing,
            symbol="SOL",
            is_crypto=True,
            crypto_correlation_adj=False,
            crypto_avg_correlation=Decimal("0.80"),
        )
        # Raw 3+3+3=9 < cap 10 → allowed when adjustment disabled.
        assert sd.can_enter is True
