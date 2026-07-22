"""Bot E feature extraction for the replacement predictor.

Per `docs/bot-e-model-replacement-plan.md` E-3, this module extracts the
feature vector for a single OBI signal from:

  - Recorded Polymarket WSS events (`pm_events` table in recorder DB).
  - Recorded CEX trade stream (`cex_trades`).
  - The signal's own subscription metadata (tte, regime, symbol).

**Paranoid rule:** every feature must be computable from data that existed
STRICTLY BEFORE the signal's generation time `t0`. Future-leak is the #1
way a model looks good in backtest and fails live.

This module is import-safe (no heavy deps); the fit scripts
(`scripts/bot_e_fit_model.py`) pull pandas/numpy only when needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


# --- Feature schema ---

FEATURE_NAMES: tuple[str, ...] = (
    "obi_30s",
    "obi_60s",
    "obi_120s",
    "obi_300s",
    "depth_log_ratio",
    "cex_cvd_signed_2m",
    "vol_5m",
    "mid_distance_50c",
    "tte_bucket_3_5",     # one-hot
    "tte_bucket_5_7",
    "tte_bucket_7_10",
    "tte_bucket_10_15",
    "regime_trend_bps",
    "symbol_btc",         # one-hot
    "symbol_eth",
    "symbol_sol",
)


@dataclass(frozen=True)
class FeatureVector:
    """Feature vector for one signal. Ordered to match FEATURE_NAMES."""
    values: tuple[float, ...]
    signal_id: str = ""  # Subscription ID or similar, for joins + debugging.

    def as_dict(self) -> dict[str, float]:
        return dict(zip(FEATURE_NAMES, self.values, strict=True))


@dataclass
class TradeTick:
    """Minimal CEX trade representation for feature extraction."""
    ts_ms: int
    price: float
    size: float
    is_buyer_maker: bool  # True = aggressor sold into bid


# --- OBI across windows ---

def obi_window(
    trades: Sequence[TradeTick],
    t0_ms: int,
    window_ms: int,
) -> float:
    """Compute OBI over (t0 - window, t0].

    Defined as `(buy_volume - sell_volume) / (buy_volume + sell_volume)`
    in the window ending at t0. Buyer-maker trades count as SELLs (taker
    sold into bid); non-buyer-maker as BUYs. Returns 0.0 if no volume.
    """
    if window_ms <= 0:
        return 0.0
    start = t0_ms - window_ms
    buy_vol = 0.0
    sell_vol = 0.0
    for t in trades:
        if t.ts_ms <= start or t.ts_ms > t0_ms:
            continue
        if t.is_buyer_maker:
            sell_vol += t.size
        else:
            buy_vol += t.size
    total = buy_vol + sell_vol
    if total <= 0.0:
        return 0.0
    return (buy_vol - sell_vol) / total


def depth_log_ratio(bid_notional: float, ask_notional: float) -> float:
    """log((bid_notional + 1) / (ask_notional + 1)).

    Positive → more buy-side depth. The +1 smoothing prevents log(0) on
    empty books and keeps the feature dimensionless at the thin-book
    extremes. Capped at ±6 (~depth ratio of 400x) to prevent outliers
    from dominating the model.
    """
    numer = max(bid_notional + 1.0, 1.0)
    denom = max(ask_notional + 1.0, 1.0)
    raw = math.log(numer / denom)
    return max(-6.0, min(6.0, raw))


def cex_cvd_signed_window(
    trades: Sequence[TradeTick],
    t0_ms: int,
    window_ms: int,
) -> float:
    """Signed CVD in USD over the window (buy_notional - sell_notional).

    No normalization by absolute volume — magnitude itself is the feature.
    Complements OBI, which is normalized.
    """
    start = t0_ms - window_ms
    cvd = 0.0
    for t in trades:
        if t.ts_ms <= start or t.ts_ms > t0_ms:
            continue
        notional = t.price * t.size
        cvd += -notional if t.is_buyer_maker else notional
    return cvd


def realized_vol_window(
    trades: Sequence[TradeTick],
    t0_ms: int,
    window_ms: int,
) -> float:
    """Realized volatility: stddev of log-returns between consecutive trades.

    Returns 0.0 if fewer than 2 trades in window.
    """
    start = t0_ms - window_ms
    in_window = [t for t in trades if start < t.ts_ms <= t0_ms and t.price > 0]
    if len(in_window) < 2:
        return 0.0
    returns = []
    for a, b in zip(in_window[:-1], in_window[1:], strict=True):
        if a.price > 0 and b.price > 0:
            returns.append(math.log(b.price / a.price))
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var)


# --- TTE bucket one-hot ---

def tte_bucket_onehot(tte_minutes: float) -> tuple[float, float, float, float]:
    """Return (3_5, 5_7, 7_10, 10_15) one-hot. Returns zeros if out of range."""
    if 3.0 <= tte_minutes < 5.0:
        return (1.0, 0.0, 0.0, 0.0)
    if 5.0 <= tte_minutes < 7.0:
        return (0.0, 1.0, 0.0, 0.0)
    if 7.0 <= tte_minutes < 10.0:
        return (0.0, 0.0, 1.0, 0.0)
    if 10.0 <= tte_minutes < 15.0:
        return (0.0, 0.0, 0.0, 1.0)
    return (0.0, 0.0, 0.0, 0.0)


# --- Symbol one-hot ---

def symbol_onehot(symbol: str) -> tuple[float, float, float]:
    """Return (BTC, ETH, SOL) one-hot. Returns zeros if symbol unknown."""
    s = symbol.upper()
    return (
        1.0 if "BTC" in s else 0.0,
        1.0 if "ETH" in s else 0.0,
        1.0 if "SOL" in s else 0.0,
    )


# --- Mid distance ---

def mid_distance_from_50c(polymarket_mid: float) -> float:
    """abs(mid - 0.5). Fee-peak proximity indicator (fees peak at 50¢)."""
    if polymarket_mid is None:
        return 0.0
    return abs(polymarket_mid - 0.5)


# --- Regime trend (bps-normalized) ---

def regime_trend_bps(
    cex_price_at_t0: float, cex_price_10m_ago: float
) -> float:
    """Trend in basis points: (price_t0 - price_10m_ago) / price_10m_ago * 10000.

    Sign-preserving. Matches the live regime gate's dimensional convention
    per ADR-022 Phase 0a. Returns 0.0 if baseline invalid.
    """
    if cex_price_10m_ago is None or cex_price_10m_ago <= 0:
        return 0.0
    if cex_price_at_t0 is None:
        return 0.0
    return (cex_price_at_t0 - cex_price_10m_ago) / cex_price_10m_ago * 10_000.0


# --- Composition ---

@dataclass
class SignalContext:
    """All data available at signal time t0. No look-ahead past this."""
    t0_ms: int
    tte_minutes: float
    symbol: str
    polymarket_mid: float | None
    bid_notional: float
    ask_notional: float
    cex_trades_up_to_t0: Sequence[TradeTick]
    cex_price_at_t0: float | None
    cex_price_10m_ago: float | None


def extract_features(ctx: SignalContext, signal_id: str = "") -> FeatureVector:
    """Compute the full feature vector for a signal context.

    Output order matches FEATURE_NAMES exactly.
    """
    obi_30 = obi_window(ctx.cex_trades_up_to_t0, ctx.t0_ms, 30_000)
    obi_60 = obi_window(ctx.cex_trades_up_to_t0, ctx.t0_ms, 60_000)
    obi_120 = obi_window(ctx.cex_trades_up_to_t0, ctx.t0_ms, 120_000)
    obi_300 = obi_window(ctx.cex_trades_up_to_t0, ctx.t0_ms, 300_000)
    depth_lr = depth_log_ratio(ctx.bid_notional, ctx.ask_notional)
    cvd_2m = cex_cvd_signed_window(ctx.cex_trades_up_to_t0, ctx.t0_ms, 120_000)
    vol_5m = realized_vol_window(ctx.cex_trades_up_to_t0, ctx.t0_ms, 300_000)
    mid_d = mid_distance_from_50c(ctx.polymarket_mid or 0.5)
    tte_35, tte_57, tte_710, tte_1015 = tte_bucket_onehot(ctx.tte_minutes)
    regime = regime_trend_bps(
        ctx.cex_price_at_t0 or 0.0,
        ctx.cex_price_10m_ago or 0.0,
    )
    sym_btc, sym_eth, sym_sol = symbol_onehot(ctx.symbol)
    return FeatureVector(
        values=(
            obi_30, obi_60, obi_120, obi_300,
            depth_lr,
            cvd_2m,
            vol_5m,
            mid_d,
            tte_35, tte_57, tte_710, tte_1015,
            regime,
            sym_btc, sym_eth, sym_sol,
        ),
        signal_id=signal_id,
    )
