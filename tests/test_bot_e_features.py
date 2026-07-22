"""Tests for E-2: Bot E feature extraction.

Covers:
- OBI-window sign + magnitude semantics.
- No future-leak: ticks at or after t0 are excluded.
- Depth log-ratio bounds and empty-book handling.
- CEX CVD magnitude.
- Realized vol on sparse samples.
- TTE / symbol one-hot.
- End-to-end feature vector shape matches FEATURE_NAMES.
"""
from __future__ import annotations

import math
import pytest

from bots.bot_e_btc_scalp.features import (
    FEATURE_NAMES,
    FeatureVector,
    SignalContext,
    TradeTick,
    cex_cvd_signed_window,
    depth_log_ratio,
    extract_features,
    mid_distance_from_50c,
    obi_window,
    realized_vol_window,
    regime_trend_bps,
    symbol_onehot,
    tte_bucket_onehot,
)


def _trades_after_t0_excluded():
    """Helper: fixture with one trade before t0, one at t0, one after t0."""
    t0 = 1_000_000
    return [
        TradeTick(ts_ms=t0 - 10_000, price=100.0, size=1.0, is_buyer_maker=False),  # BUY
        TradeTick(ts_ms=t0, price=101.0, size=2.0, is_buyer_maker=False),            # at t0 — INCLUDED
        TradeTick(ts_ms=t0 + 5_000, price=102.0, size=3.0, is_buyer_maker=True),     # after — EXCLUDED
    ]


def test_obi_excludes_future_ticks():
    t0 = 1_000_000
    trades = _trades_after_t0_excluded()
    # Window 30s → includes trade at t0 and the -10s tick; excludes post-t0.
    # Both counted as BUY (is_buyer_maker=False), no SELL → OBI = +1.0.
    assert obi_window(trades, t0, window_ms=30_000) == pytest.approx(1.0)


def test_obi_empty_window_returns_zero():
    t0 = 1_000_000
    trades = []
    assert obi_window(trades, t0, window_ms=30_000) == 0.0


def test_obi_sign_negative_when_sells_dominate():
    t0 = 1_000_000
    trades = [
        TradeTick(ts_ms=t0 - 5_000, price=100.0, size=1.0, is_buyer_maker=False),  # BUY
        TradeTick(ts_ms=t0 - 4_000, price=100.0, size=3.0, is_buyer_maker=True),   # SELL
    ]
    # (1 - 3) / (1 + 3) = -0.5
    assert obi_window(trades, t0, 30_000) == pytest.approx(-0.5)


def test_obi_out_of_window_excluded():
    t0 = 1_000_000
    # Trade far in the past (older than window).
    trades = [TradeTick(ts_ms=t0 - 120_000, price=100.0, size=5.0, is_buyer_maker=False)]
    assert obi_window(trades, t0, window_ms=30_000) == 0.0


def test_obi_window_zero_returns_zero():
    t0 = 1_000_000
    trades = _trades_after_t0_excluded()
    assert obi_window(trades, t0, 0) == 0.0


def test_depth_log_ratio_symmetric():
    # Equal depth → 0.
    assert depth_log_ratio(100.0, 100.0) == 0.0


def test_depth_log_ratio_sign():
    # More bid depth → positive; more ask depth → negative.
    assert depth_log_ratio(1000.0, 100.0) > 0.0
    assert depth_log_ratio(100.0, 1000.0) < 0.0


def test_depth_log_ratio_capped():
    # Extreme imbalance capped to ±6.
    assert depth_log_ratio(1e12, 0.0) == 6.0
    assert depth_log_ratio(0.0, 1e12) == -6.0


def test_cex_cvd_signed():
    t0 = 1_000_000
    trades = [
        TradeTick(ts_ms=t0 - 60_000, price=100.0, size=1.0, is_buyer_maker=False),  # BUY 100 notional
        TradeTick(ts_ms=t0 - 30_000, price=100.0, size=2.0, is_buyer_maker=True),   # SELL 200 notional
    ]
    # CVD = 100 - 200 = -100.
    assert cex_cvd_signed_window(trades, t0, 120_000) == pytest.approx(-100.0)


def test_realized_vol_needs_two_samples():
    t0 = 1_000_000
    single = [TradeTick(ts_ms=t0 - 1000, price=100.0, size=1.0, is_buyer_maker=False)]
    assert realized_vol_window(single, t0, 300_000) == 0.0


def test_realized_vol_constant_price_zero():
    t0 = 1_000_000
    trades = [
        TradeTick(ts_ms=t0 - 60_000, price=100.0, size=1.0, is_buyer_maker=False),
        TradeTick(ts_ms=t0 - 30_000, price=100.0, size=1.0, is_buyer_maker=False),
        TradeTick(ts_ms=t0 - 15_000, price=100.0, size=1.0, is_buyer_maker=False),
    ]
    # All prices equal → log-returns = 0 → stddev = 0.
    assert realized_vol_window(trades, t0, 300_000) == 0.0


def test_realized_vol_positive_on_movement():
    t0 = 1_000_000
    trades = [
        TradeTick(ts_ms=t0 - 60_000, price=100.0, size=1.0, is_buyer_maker=False),
        TradeTick(ts_ms=t0 - 30_000, price=101.0, size=1.0, is_buyer_maker=False),
        TradeTick(ts_ms=t0 - 15_000, price=99.0, size=1.0, is_buyer_maker=False),
    ]
    vol = realized_vol_window(trades, t0, 300_000)
    assert vol > 0.0


def test_tte_bucket_matches_plan():
    assert tte_bucket_onehot(4.0) == (1.0, 0.0, 0.0, 0.0)
    assert tte_bucket_onehot(6.0) == (0.0, 1.0, 0.0, 0.0)
    assert tte_bucket_onehot(8.0) == (0.0, 0.0, 1.0, 0.0)
    assert tte_bucket_onehot(12.0) == (0.0, 0.0, 0.0, 1.0)
    # Out of range (negative / too large) returns zeros.
    assert tte_bucket_onehot(2.0) == (0.0, 0.0, 0.0, 0.0)
    assert tte_bucket_onehot(20.0) == (0.0, 0.0, 0.0, 0.0)


def test_symbol_onehot():
    assert symbol_onehot("BTC") == (1.0, 0.0, 0.0)
    assert symbol_onehot("eth") == (0.0, 1.0, 0.0)
    assert symbol_onehot("btc-up-2026-04-17-12:15") == (1.0, 0.0, 0.0)


def test_symbol_onehot_unknown():
    assert symbol_onehot("DOGE") == (0.0, 0.0, 0.0)


def test_mid_distance_at_50c_zero():
    assert mid_distance_from_50c(0.5) == 0.0


def test_mid_distance_symmetric():
    assert mid_distance_from_50c(0.3) == pytest.approx(0.2)
    assert mid_distance_from_50c(0.7) == pytest.approx(0.2)


def test_regime_trend_bps_sign():
    # Price went up 1% → +100 bps.
    assert regime_trend_bps(101.0, 100.0) == pytest.approx(100.0)
    # Price went down 1% → -100 bps.
    assert regime_trend_bps(99.0, 100.0) == pytest.approx(-100.0)


def test_regime_trend_bps_zero_baseline():
    assert regime_trend_bps(100.0, 0.0) == 0.0
    assert regime_trend_bps(100.0, None) == 0.0


def test_extract_features_matches_feature_names():
    """End-to-end: a signal context produces a vector of the right length and order."""
    t0 = 1_000_000
    ctx = SignalContext(
        t0_ms=t0,
        tte_minutes=6.5,
        symbol="BTC",
        polymarket_mid=0.48,
        bid_notional=500.0,
        ask_notional=400.0,
        cex_trades_up_to_t0=[
            TradeTick(ts_ms=t0 - 60_000, price=85_000.0, size=0.1, is_buyer_maker=False),
            TradeTick(ts_ms=t0 - 30_000, price=85_100.0, size=0.2, is_buyer_maker=False),
            TradeTick(ts_ms=t0 - 10_000, price=85_050.0, size=0.15, is_buyer_maker=True),
        ],
        cex_price_at_t0=85_050.0,
        cex_price_10m_ago=84_000.0,
    )
    fv = extract_features(ctx, signal_id="btc-test")
    assert len(fv.values) == len(FEATURE_NAMES)
    as_dict = fv.as_dict()
    # Spot-check a few.
    assert as_dict["symbol_btc"] == 1.0
    assert as_dict["symbol_eth"] == 0.0
    assert as_dict["tte_bucket_5_7"] == 1.0
    assert as_dict["mid_distance_50c"] == pytest.approx(0.02)
    assert as_dict["regime_trend_bps"] > 0.0  # Price rose from 84k → 85050.
    assert as_dict["obi_60s"] != 0.0  # Mixed buyer/seller in window.


def test_extract_features_deterministic():
    """Same input → same output (no clock-dependent features)."""
    t0 = 1_000_000
    ctx = SignalContext(
        t0_ms=t0,
        tte_minutes=6.5,
        symbol="BTC",
        polymarket_mid=0.5,
        bid_notional=100.0,
        ask_notional=100.0,
        cex_trades_up_to_t0=[],
        cex_price_at_t0=85_000.0,
        cex_price_10m_ago=85_000.0,
    )
    a = extract_features(ctx)
    b = extract_features(ctx)
    assert a.values == b.values
