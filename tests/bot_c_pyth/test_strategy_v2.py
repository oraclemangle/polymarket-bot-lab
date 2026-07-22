"""Tests for the 8 strategy fixes (barrier, fee, drift, annualisation, etc.)."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from bots.bot_c_pyth.discovery import ParsedMarket, parse_question
from bots.bot_c_pyth.strategy import (
    ANNUALISED_DRIFT,
    BARS_PER_YEAR,
    _polymarket_taker_fee,
    evaluate_market,
    gbm_barrier_above,
    gbm_barrier_below,
    gbm_prob_above,
    gbm_prob_below,
)


def _market(symbol, direction, lo, hi, hours, yes_price=0.5,
            question_kind="terminal", category="equity"):
    return ParsedMarket(
        gamma_id="g1", slug="s", question="q", symbol=symbol,
        direction=direction, strike_low=Decimal(str(lo)),
        strike_high=Decimal(str(hi)) if hi is not None else None,
        resolution_date=datetime.now(UTC) + timedelta(hours=hours),
        yes_token_id="y", no_token_id="n",
        yes_price=Decimal(str(yes_price)), volume_24h_usd=Decimal("1000"),
        question_kind=question_kind,
    )


# --- Fix 1: Barrier probability -----------------------------------------------

def test_barrier_above_exceeds_terminal_when_strike_above_spot():
    """P(max ≥ K) > P(S_T > K) when K > S, zero drift."""
    s, k, sigma, t = 100.0, 120.0, 0.30, 0.25  # 3 months
    p_terminal = gbm_prob_above(s, k, sigma, t)
    p_barrier = gbm_barrier_above(s, k, sigma, t)
    assert p_barrier > p_terminal, f"barrier {p_barrier:.4f} should exceed terminal {p_terminal:.4f}"
    # Roughly 2x for zero drift, ATM-ish
    assert p_barrier / p_terminal > 1.5


def test_barrier_above_is_1_when_spot_at_strike():
    assert gbm_barrier_above(100, 100, 0.2, 1.0) == 1.0


def test_barrier_above_is_1_when_spot_above_strike():
    assert gbm_barrier_above(150, 100, 0.2, 1.0) == 1.0


def test_barrier_below_exceeds_terminal_when_strike_below_spot():
    s, k, sigma, t = 100.0, 80.0, 0.30, 0.25
    p_terminal = gbm_prob_below(s, k, sigma, t)
    p_barrier = gbm_barrier_below(s, k, sigma, t)
    assert p_barrier > p_terminal


def test_barrier_below_is_1_when_spot_at_strike():
    assert gbm_barrier_below(100, 100, 0.2, 1.0) == 1.0


def test_barrier_below_is_1_when_spot_below_strike():
    assert gbm_barrier_below(50, 100, 0.2, 1.0) == 1.0


def test_barrier_above_approaches_terminal_for_deep_otm():
    """Far out-of-the-money barrier should still be ~2x terminal for zero drift."""
    s, k, sigma, t = 100.0, 200.0, 0.20, 1.0
    pt = gbm_prob_above(s, k, sigma, t)
    pb = gbm_barrier_above(s, k, sigma, t)
    # For zero drift GBM, ratio is exactly 2·N(d1)/N(d1) + tail term ~ 2x
    assert pb > pt


def test_barrier_with_drift():
    """Positive drift increases barrier probability."""
    s, k, sigma, t = 100.0, 120.0, 0.25, 0.5
    pb_nodrift = gbm_barrier_above(s, k, sigma, t, drift=0.0)
    pb_withdrift = gbm_barrier_above(s, k, sigma, t, drift=0.10)
    assert pb_withdrift > pb_nodrift


# --- Fix 1 integration: question_kind flows through evaluate_market -----------

def test_evaluate_uses_barrier_for_hit_market():
    """A 'barrier' market should produce higher p_yes than 'terminal' for same inputs."""
    m_barrier = _market("AAPL", "above", 280, None, 48, yes_price=0.5,
                        question_kind="barrier")
    m_terminal = _market("AAPL", "above", 280, None, 48, yes_price=0.5,
                         question_kind="terminal")
    spot = Decimal("270")
    dec_b = evaluate_market(m_barrier, spot, 0.30, drift=0.0)
    dec_t = evaluate_market(m_terminal, spot, 0.30, drift=0.0)
    # barrier probability should be strictly higher
    assert dec_b.model_p_yes > dec_t.model_p_yes


# --- Fix 1: question_kind in discovery parser ---------------------------------

def test_weekly_hit_is_barrier():
    r = parse_question("Will Tesla, Inc. (TSLA) hit (LOW) $337.50 Week of April 13 2026?")
    assert r is not None
    assert r["question_kind"] == "barrier"


def test_eom_hit_is_barrier():
    r = parse_question("Will Gold (GC) hit (HIGH) $9,000 by end of June?")
    assert r is not None
    assert r["question_kind"] == "barrier"


def test_weekly_finish_is_terminal():
    r = parse_question("Will NVIDIA (NVDA) finish week of April 13 above $175?")
    assert r is not None
    assert r["question_kind"] == "terminal"


def test_month_settle_is_terminal():
    r = parse_question("Will Silver (SI) settle over $60 on the final trading day of June 2026?")
    assert r is not None
    assert r["question_kind"] == "terminal"


def test_crypto_between_is_terminal():
    r = parse_question("Will the price of Bitcoin be between $95,000 and $100,000 in April?")
    assert r is not None
    assert r["question_kind"] == "terminal"


# --- Fix 2: Fee netting -------------------------------------------------------

def test_fee_parabola_peaks_at_50pct():
    fee_50 = _polymarket_taker_fee(0.5)
    fee_10 = _polymarket_taker_fee(0.1)
    fee_90 = _polymarket_taker_fee(0.9)
    assert fee_50 > fee_10
    assert fee_50 > fee_90
    assert abs(fee_50 - 0.03) < 0.001  # peak ~ 3%


def test_fee_near_zero_at_tails():
    assert _polymarket_taker_fee(0.01) < 0.002
    assert _polymarket_taker_fee(0.99) < 0.002


def test_net_edge_smaller_than_gross():
    m = _market("NVDA", "above", 175, None, 48, yes_price=0.50)
    dec = evaluate_market(m, Decimal("200"), 0.25, drift=0.0)
    assert abs(dec.net_edge) < abs(dec.gross_edge)


# --- Fix 3: Per-asset-class annualisation -------------------------------------

def test_crypto_bars_per_year_larger_than_equity():
    assert BARS_PER_YEAR["crypto"] > BARS_PER_YEAR["equity"] * 3


def test_commodity_bars_per_year_between_equity_and_crypto():
    assert BARS_PER_YEAR["commodity"] > BARS_PER_YEAR["equity"]
    assert BARS_PER_YEAR["commodity"] < BARS_PER_YEAR["crypto"]


# --- Fix 4: Drift term -------------------------------------------------------

def test_drift_raises_above_probability_for_equities():
    """Positive drift should increase P(above K) for all K."""
    p_no_drift = gbm_prob_above(100, 110, 0.25, 1.0, drift=0.0)
    p_with_drift = gbm_prob_above(100, 110, 0.25, 1.0, drift=0.07)
    assert p_with_drift > p_no_drift


def test_drift_default_for_equity():
    assert ANNUALISED_DRIFT["equity"] > 0


def test_drift_default_for_crypto():
    assert ANNUALISED_DRIFT["crypto"] == 0.0


# --- Fix 7: Year-rollover date parsing ----------------------------------------

def test_year_rollover_when_month_in_past():
    """'January' parsed in April 2026 should resolve to January 2027."""
    now = datetime(2026, 4, 15, tzinfo=UTC)
    r = parse_question("Will the price of Bitcoin be between $90,000 and $100,000 in January?",
                       now=now)
    assert r is not None
    assert r["resolution_date"].year == 2027


def test_year_rollover_not_applied_when_month_in_future():
    now = datetime(2026, 4, 15, tzinfo=UTC)
    r = parse_question("Will the price of Bitcoin be between $90,000 and $100,000 in June?",
                       now=now)
    assert r is not None
    assert r["resolution_date"].year == 2026


def test_year_rollover_not_applied_when_explicit_year():
    now = datetime(2026, 4, 15, tzinfo=UTC)
    r = parse_question("Will Gold (GC) hit (HIGH) $9,000 by end of June 2026?", now=now)
    assert r is not None
    assert r["resolution_date"].year == 2026
