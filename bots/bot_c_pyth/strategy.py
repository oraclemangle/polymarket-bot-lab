"""Edge calculator: Pyth spot + rolling vol → P(strike hit) → edge vs Polymarket mid.

Supports both terminal probability (GBM at expiry) and barrier probability
(running max/min touches strike at any point during the period). Market
question type determines which formula is used.

Incorporates per-asset-class annualisation, optional drift, and fee netting.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from bots.bot_c_pyth.discovery import ParsedMarket
from core.pyth_feeds import Feed, feed_by_symbol
from core.pyth_models import PythBarHermes, PythBarPro

log = logging.getLogger(__name__)

# --- Per-asset-class annualisation (Fix 3) -----------------------------------
# Seconds of active trading per year. Used to convert per-bar (1-second)
# realised volatility into annualised σ.
BARS_PER_YEAR: dict[str, int] = {
    "equity": 252 * int(6.5 * 3600),     # 5_896_800 — NYSE regular session
    "etf":    252 * int(6.5 * 3600),     # same as equity
    "commodity": 252 * int(8 * 3600),    # 7_257_600 — NYMEX/COMEX ~8h
    "crypto": 365 * 24 * 3600,           # 31_536_000 — 24/7
}
DEFAULT_BARS_PER_YEAR = BARS_PER_YEAR["equity"]

# --- Drift estimates (Fix 4) -------------------------------------------------
# Simple annualised drift per asset class. Equities get a ~7%/yr equity
# premium proxy. Crypto/commodities get 0 (no reliable long-run drift).
# These are deliberately conservative: we'd rather understate drift and
# miss some edges than overstate it and lose money on biased signals.
ANNUALISED_DRIFT: dict[str, float] = {
    "equity": 0.07,
    "etf":    0.07,
    "commodity": 0.0,
    "crypto": 0.0,
}

# --- Polymarket taker fee curve (Fix 2) --------------------------------------
# Polymarket V2 fee schedule: dynamic taker fee peaks near 50% probability.
# Approximated as a parabola: fee = 4 * MAX_FEE * p * (1 - p), where
# MAX_FEE is the peak rate at p=0.50. Currently ~3% at the peak.
POLYMARKET_MAX_TAKER_FEE_RATE = 0.03  # 3% at p=0.50


def _polymarket_taker_fee(p: float) -> float:
    """Estimate the taker fee as a fraction of trade value.

    Polymarket's fee curve is roughly parabolic: zero at the tails (0% and
    100% probability), peaking at ~3% near 50%. We approximate with
    fee_rate = 4 * 0.03 * p * (1 − p).
    """
    p_clamped = max(0.001, min(0.999, p))
    return 4.0 * POLYMARKET_MAX_TAKER_FEE_RATE * p_clamped * (1.0 - p_clamped)


# --- Data types ---------------------------------------------------------------

@dataclass(frozen=True)
class EdgeDecision:
    market: ParsedMarket
    model_p_yes: float
    market_p_yes: float
    gross_edge: float         # model_p_yes - market_p_yes (before fees)
    net_edge: float           # gross_edge minus estimated fee impact
    edge: float               # alias for net_edge (backward compat)
    side: str                 # "BUY_YES" | "BUY_NO" | "SKIP"
    reason: str
    spot_price: Decimal
    annualised_vol: float
    hours_to_resolution: float
    decided_at: datetime
    drift_used: float = 0.0   # for audit trail
    question_kind: str = "terminal"


# --- Volatility ---------------------------------------------------------------

def get_spot_and_vol(
    session_factory: sessionmaker,
    feed_id: int,
    category: str = "equity",
    lookback_bars: int = 1800,
    long_lookback_bars: int = 18000,
    bar_model: type = PythBarPro,
) -> tuple[Decimal | None, float | None]:
    """Latest close + blended annualised volatility from a Pyth bar table.

    Fix 8 (vol term-structure blend): uses a weighted blend of short-term
    (30-min, ~1800 bars) and long-term (5-hour, ~18000 bars) realised vol.
    Short-term σ gets 60% weight for horizons ≤ 48h; 30% for longer.

    SECURITY_AUDIT.md H-2 fix: bar_model is now a parameter (defaults to
    PythBarPro for backwards compat). Pass PythBarHermes when running
    Bot C against the Hermes (free) endpoint instead of Pro Lazer.
    Operators on Hermes were getting None back from this function and
    Bot C was silently producing zero edge signals.
    """
    with session_factory() as s:
        rows = s.execute(
            select(bar_model.close)
            .where(bar_model.feed_id == feed_id)
            .order_by(bar_model.ts.desc())
            .limit(long_lookback_bars)
        ).scalars().all()
    if not rows or len(rows) < 30:
        return None, None
    prices = [float(p) for p in reversed(rows)]
    spot = Decimal(str(prices[-1]))
    bpy = BARS_PER_YEAR.get(category, DEFAULT_BARS_PER_YEAR)

    def _sigma(price_series: list[float]) -> float | None:
        rets: list[float] = []
        for i in range(1, len(price_series)):
            p0, p1 = price_series[i - 1], price_series[i]
            if p0 <= 0 or p1 <= 0:
                continue
            rets.append(math.log(p1 / p0))
        if len(rets) < 10:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(var) * math.sqrt(bpy)

    short_prices = prices[-lookback_bars:] if len(prices) > lookback_bars else prices
    sigma_short = _sigma(short_prices)
    sigma_long = _sigma(prices) if len(prices) >= lookback_bars * 2 else None

    if sigma_short is None:
        return spot, None
    if sigma_long is None:
        return spot, sigma_short

    # Blend: short-term weighted higher for responsiveness, but anchored
    # by long-term to reduce microstructure noise on multi-day horizons.
    # The caller doesn't currently pass horizon, so we use a fixed 50/50.
    sigma_blended = 0.5 * sigma_short + 0.5 * sigma_long
    return spot, sigma_blended


# --- Probability functions ----------------------------------------------------

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))


def gbm_prob_above(
    spot: float, strike: float, sigma: float, t_years: float,
    drift: float = 0.0,
) -> float:
    """P(S_T > K) — terminal probability (for 'finish above' / 'settle over')."""
    if t_years <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        return 1.0 if spot > strike else 0.0
    mu = drift - 0.5 * sigma ** 2  # log-return drift
    d = (math.log(spot / strike) + mu * t_years + 0.5 * sigma ** 2 * t_years) / (
        sigma * math.sqrt(t_years)
    )
    # Simplifies to: d = (ln(S/K) + drift*T) / (σ√T) when expanding
    return _norm_cdf(d)


def gbm_prob_below(
    spot: float, strike: float, sigma: float, t_years: float,
    drift: float = 0.0,
) -> float:
    return 1.0 - gbm_prob_above(spot, strike, sigma, t_years, drift)


def gbm_prob_between(
    spot: float, low: float, high: float,
    sigma: float, t_years: float, drift: float = 0.0,
) -> float:
    return max(
        0.0,
        gbm_prob_above(spot, low, sigma, t_years, drift)
        - gbm_prob_above(spot, high, sigma, t_years, drift),
    )


# --- Barrier probability functions (Fix 1) ------------------------------------

def gbm_barrier_above(
    spot: float, strike: float, sigma: float, t_years: float,
    drift: float = 0.0,
) -> float:
    """P(max_{0≤t≤T} S_t ≥ K) — running maximum touches or exceeds K.

    For 'hit (HIGH)' markets. Under GBM with drift μ_price and vol σ:
      P(max ≥ K) = Φ(d1) + (K/S)^{2μ_log/σ²} · Φ(d2)
    where μ_log = μ_price − σ²/2, and:
      d1 = (ln(S/K) + μ_log·T) / (σ√T)
      d2 = (−ln(S/K) + μ_log·T) / (σ√T)
    """
    if spot <= 0 or strike <= 0:
        return 0.0
    if spot >= strike:
        return 1.0  # already at or above the barrier
    if t_years <= 0 or sigma <= 0:
        return 1.0 if spot >= strike else 0.0

    mu_log = drift - 0.5 * sigma ** 2
    sqrt_t = sigma * math.sqrt(t_years)
    log_ratio = math.log(spot / strike)  # negative when spot < strike

    d1 = (log_ratio + mu_log * t_years) / sqrt_t
    d2 = (-log_ratio + mu_log * t_years) / sqrt_t

    exponent = 2.0 * mu_log / (sigma ** 2)
    # (K/S)^exponent = exp(exponent * ln(K/S)) = exp(-exponent * ln(S/K))
    power_term = math.exp(-exponent * log_ratio)

    return _norm_cdf(d1) + power_term * _norm_cdf(d2)


def gbm_barrier_below(
    spot: float, strike: float, sigma: float, t_years: float,
    drift: float = 0.0,
) -> float:
    """P(min_{0≤t≤T} S_t ≤ K) — running minimum touches or goes below K.

    For 'hit (LOW)' markets. Under GBM:
      P(min ≤ K) = Φ(d1_down) + (S/K)^{2μ_log/σ²} · Φ(d2_down)
    where:
      d1_down = (ln(K/S) + μ_log·T) / (σ√T)
      d2_down = (ln(K/S) − μ_log·T) / (σ√T)

    Wait — let me derive this cleanly. For X_t = ln(S_t/S_0):
      X_t = μ_log·t + σ·W_t
    We want P(min_{0≤t≤T} X_t ≤ a) where a = ln(K/S) < 0 (since K < S).
      = Φ((a − μ_log·T)/(σ√T)) + exp(2·μ_log·a/σ²)·Φ((a + μ_log·T)/(σ√T))
    """
    if spot <= 0 or strike <= 0:
        return 0.0
    if spot <= strike:
        return 1.0  # already at or below the barrier
    if t_years <= 0 or sigma <= 0:
        return 1.0 if spot <= strike else 0.0

    mu_log = drift - 0.5 * sigma ** 2
    sqrt_t = sigma * math.sqrt(t_years)
    a = math.log(strike / spot)  # negative when strike < spot

    d1 = (a - mu_log * t_years) / sqrt_t
    d2 = (a + mu_log * t_years) / sqrt_t

    exp_term = math.exp(2.0 * mu_log * a / (sigma ** 2))

    return _norm_cdf(d1) + exp_term * _norm_cdf(d2)


# --- Main evaluator -----------------------------------------------------------

def evaluate_market(
    market: ParsedMarket,
    spot: Decimal,
    sigma_ann: float,
    *,
    now: datetime | None = None,
    edge_threshold: float = 0.10,
    drift: float | None = None,
) -> EdgeDecision:
    """Compute the net edge for one market and return a trade decision.

    If drift is None, looks up the default from ANNUALISED_DRIFT by the
    market's symbol category.
    """
    now = now or datetime.now(UTC)
    dt = max((market.resolution_date - now).total_seconds(), 0.0)
    t_years = dt / 31_557_600.0
    hours = dt / 3600.0
    spot_f = float(spot)

    # Resolve drift (Fix 4).
    if drift is None:
        feed = feed_by_symbol(market.symbol)
        category = feed.category if feed else "equity"
        drift_used = ANNUALISED_DRIFT.get(category, 0.0)
    else:
        drift_used = drift

    # Choose terminal vs barrier (Fix 1) based on question_kind.
    kind = getattr(market, "question_kind", "terminal")

    if kind == "barrier":
        if market.direction == "above":
            p_yes = gbm_barrier_above(spot_f, float(market.strike_low), sigma_ann, t_years, drift_used)
        elif market.direction == "below":
            p_yes = gbm_barrier_below(spot_f, float(market.strike_low), sigma_ann, t_years, drift_used)
        else:
            # "between" barrier is exotic (double barrier); approximate as terminal.
            p_yes = gbm_prob_between(
                spot_f, float(market.strike_low), float(market.strike_high or 0),
                sigma_ann, t_years, drift_used,
            )
    else:
        # terminal
        if market.direction == "above":
            p_yes = gbm_prob_above(spot_f, float(market.strike_low), sigma_ann, t_years, drift_used)
        elif market.direction == "below":
            p_yes = gbm_prob_below(spot_f, float(market.strike_low), sigma_ann, t_years, drift_used)
        elif market.direction == "between":
            p_yes = gbm_prob_between(
                spot_f, float(market.strike_low), float(market.strike_high or 0),
                sigma_ann, t_years, drift_used,
            )
        else:
            p_yes = 0.5

    market_p = float(market.yes_price) if market.yes_price is not None else 0.5

    # Gross edge (before fees).
    gross_edge = p_yes - market_p

    # Fee-adjusted net edge (Fix 2, corrected 2026-04-18 U-15).
    #
    # `_polymarket_taker_fee(p)` returns a fraction of NOTIONAL
    # (rate × price × size). Per-share fee = rate × entry_price.
    # The prior comment ("fee_rate * notional / notional = fee_rate")
    # was wrong: `gross_edge` is in per-share units (two probabilities
    # subtracted), so the fee must be converted to per-share too.
    # Prior code over-stated fees by factor 1/entry_price (2× at 0.5).
    if gross_edge > 0:
        # buying YES at entry_price = market_p
        fee_rate = _polymarket_taker_fee(market_p)
        entry_price = market_p
    elif gross_edge < 0:
        # buying NO at entry_price = (1 - market_p)
        fee_rate = _polymarket_taker_fee(1.0 - market_p)
        entry_price = 1.0 - market_p
    else:
        fee_rate = 0.0
        entry_price = 1.0
    fee_per_share = fee_rate * entry_price
    # Defensive clamp (Gemini 3.1 Pro audit 2026-04-19 F-001): see the
    # matching comment in bots/bot_d_weather/strategy.py. Prevents the
    # sign-flip edge case where fees exceed gross_edge magnitude.
    if gross_edge > 0:
        net_edge = max(0.0, gross_edge - fee_per_share)
    elif gross_edge < 0:
        net_edge = min(0.0, gross_edge + fee_per_share)
    else:
        net_edge = 0.0

    if abs(net_edge) < edge_threshold:
        side = "SKIP"
        reason = f"net_edge |{net_edge:+.3f}| below threshold {edge_threshold}"
    elif net_edge > 0:
        side = "BUY_YES"
        reason = f"model {p_yes:.3f} > market {market_p:.3f} (net {net_edge:+.3f})"
    else:
        side = "BUY_NO"
        reason = f"model {p_yes:.3f} < market {market_p:.3f} (net {net_edge:+.3f})"

    return EdgeDecision(
        market=market,
        model_p_yes=p_yes,
        market_p_yes=market_p,
        gross_edge=gross_edge,
        net_edge=net_edge,
        edge=net_edge,
        side=side,
        reason=reason,
        spot_price=spot,
        annualised_vol=sigma_ann,
        hours_to_resolution=hours,
        decided_at=now,
        drift_used=drift_used,
        question_kind=kind,
    )
