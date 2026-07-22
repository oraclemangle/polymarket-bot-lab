"""Basket arbitrage and coherence violation detection.

Formula source: ``docs/reports/math-formula-roadmap-split-2026-05-08.md``
§6.6.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class BasketArbViolation:
    """A detected basket-arb opportunity.

    Attributes:
        kind: ``"BUY_BASKET"`` or ``"SELL_BASKET"``
        legs: list of (market_id, side, price, size) tuples for each leg
        gross_edge: edge before fees (theoretical)
        net_edge: edge after parabolic taker fees per share
        fillable_size: minimum top-of-book depth across legs (USD)
        expected_profit_usd: net_edge * fillable_size
    """

    kind: str
    legs: list[tuple[str, str, float, float]]
    gross_edge: float
    net_edge: float
    fillable_size: float
    expected_profit_usd: float


def _taker_fee_per_share(price: float, fee_rate: float) -> float:
    """Parabolic taker fee per share at given price.

    Mirrors ``core.fees.taker_fee_per_share`` for category-aware rates.
    """
    if not 0.0 < price < 1.0:
        return 0.0
    return fee_rate * price * (1.0 - price)


def detect_basket_arb(
    *,
    legs: Sequence[dict],
    fee_rate: float,
    min_edge: float = 0.005,
) -> BasketArbViolation | None:
    """Detect a basket arb violation across mutually exclusive legs.

    Each leg is a dict with keys: ``market_id``, ``best_bid``,
    ``best_ask``, ``top_bid_size``, ``top_ask_size``. Sizes are in
    shares.

    Returns the BUY_BASKET or SELL_BASKET candidate if its post-fee
    edge exceeds ``min_edge`` per basket; else ``None``.
    """
    if len(legs) < 2:
        return None
    asks = [float(leg["best_ask"]) for leg in legs]
    bids = [float(leg["best_bid"]) for leg in legs]
    ask_sizes = [float(leg["top_ask_size"]) for leg in legs]
    bid_sizes = [float(leg["top_bid_size"]) for leg in legs]

    # Buy basket: pay sum_k ask_k + fees, get $1 back when one wins
    sum_ask = sum(asks)
    fee_buy = sum(_taker_fee_per_share(a, fee_rate) for a in asks)
    gross_edge_buy = 1.0 - sum_ask
    net_edge_buy = gross_edge_buy - fee_buy
    # Sell basket: receive sum_k bid_k - fees, owe $1 when one wins
    sum_bid = sum(bids)
    fee_sell = sum(_taker_fee_per_share(b, fee_rate) for b in bids)
    gross_edge_sell = sum_bid - 1.0
    net_edge_sell = gross_edge_sell - fee_sell

    if net_edge_buy >= min_edge and net_edge_buy >= net_edge_sell:
        fillable = min(ask_sizes)
        return BasketArbViolation(
            kind="BUY_BASKET",
            legs=[
                (str(leg["market_id"]), "BUY", float(leg["best_ask"]), float(leg["top_ask_size"]))
                for leg in legs
            ],
            gross_edge=gross_edge_buy,
            net_edge=net_edge_buy,
            fillable_size=fillable,
            expected_profit_usd=net_edge_buy * fillable,
        )
    if net_edge_sell >= min_edge:
        fillable = min(bid_sizes)
        return BasketArbViolation(
            kind="SELL_BASKET",
            legs=[
                (str(leg["market_id"]), "SELL", float(leg["best_bid"]), float(leg["top_bid_size"]))
                for leg in legs
            ],
            gross_edge=gross_edge_sell,
            net_edge=net_edge_sell,
            fillable_size=fillable,
            expected_profit_usd=net_edge_sell * fillable,
        )
    return None


def detect_threshold_ladder_violations(
    rungs: Sequence[dict],
) -> list[dict]:
    """Detect monotonicity violations in a threshold ladder.

    Input: a list of rungs sorted by threshold ascending. Each rung
    is ``{threshold, p_at_or_above}``. For a coherent ladder,
    ``p_at_or_above`` must be non-increasing in ``threshold``.

    Returns: list of violations
    ``{i, j, threshold_i, threshold_j, p_i, p_j, magnitude}``
    where ``p_j > p_i`` for ``i < j`` (a free-money signal in
    expectation, before considering execution).
    """
    out: list[dict] = []
    sorted_rungs = sorted(rungs, key=lambda r: float(r["threshold"]))
    for i in range(len(sorted_rungs)):
        for j in range(i + 1, len(sorted_rungs)):
            r_i = sorted_rungs[i]
            r_j = sorted_rungs[j]
            p_i = float(r_i["p_at_or_above"])
            p_j = float(r_j["p_at_or_above"])
            if p_j > p_i:
                out.append(
                    {
                        "i": i,
                        "j": j,
                        "threshold_i": float(r_i["threshold"]),
                        "threshold_j": float(r_j["threshold"]),
                        "p_i": p_i,
                        "p_j": p_j,
                        "magnitude": p_j - p_i,
                    }
                )
    return out


def detect_linked_time_bucket_violation(
    sub_window_probs: Sequence[float],
    parent_window_prob: float,
    *,
    tolerance: float = 0.05,
) -> dict | None:
    """Detect coherence violation between sub-window and parent markets.

    For 5m x 3 vs 15m "Up" markets: under independence, the parent
    "Up" probability equals ``1 - prod_k (1 - p_5m_k)``. A real
    Brownian process is positively correlated, so the actual parent
    probability should be at least the independence bound. If it
    falls below by more than ``tolerance``, that's a coherence flag.
    """
    if not sub_window_probs:
        return None
    p_independent = 1.0
    for p in sub_window_probs:
        p = max(0.0, min(1.0, float(p)))
        p_independent *= 1.0 - p
    p_independent = 1.0 - p_independent
    p_parent = max(0.0, min(1.0, float(parent_window_prob)))
    gap = p_independent - p_parent
    if gap > tolerance:
        return {
            "p_independent_bound": p_independent,
            "p_parent_observed": p_parent,
            "gap": gap,
            "kind": "parent_below_independence_bound",
        }
    return None


def expected_profit_per_dollar_per_day(
    *,
    expected_profit_usd: float,
    capital_required_usd: float,
    settlement_lag_days: float,
) -> float:
    """Capital-lockup-adjusted return.

    ``expected_profit_per_dollar_per_day = expected_profit /
    (capital_required * lag_days)``. Compare to the operator's
    risk-free daily rate (about 0.014% / day for 5% APR).
    """
    if capital_required_usd <= 0:
        return 0.0
    if settlement_lag_days <= 0:
        return float("inf") if expected_profit_usd > 0 else 0.0
    return expected_profit_usd / (capital_required_usd * settlement_lag_days)
