"""Sanitized pseudocode for the Bot D weather strategy.

This is not production code. It intentionally excludes wallet integration,
API keys, database paths, hostnames, and private deployment details.
"""

from dataclasses import dataclass


@dataclass
class Market:
    city: str
    temp_type: str
    bucket_low_f: float | None
    bucket_high_f: float | None
    yes_price: float
    settlement_verified: bool


@dataclass
class Forecast:
    source: str
    mean_f: float
    std_f: float
    nws_value_f: float | None
    model_probability: float
    api_agreement_count: int
    api_agreement_max_gap_f: float | None


def setup_tier(market: Market, forecast: Forecast, net_edge: float) -> str:
    if not market.settlement_verified:
        return "C"
    if abs(net_edge) < 0.10:
        return "C"
    if forecast.source in {"multi_model", "noaa_nbm"} and abs(net_edge) >= 0.15:
        return "A"
    if forecast.source in {"multi_model", "noaa_nbm"}:
        return "B"
    return "C"


def should_skip(market: Market, forecast: Forecast, net_edge: float) -> str | None:
    if not market.settlement_verified:
        return "unverified_settlement"
    if forecast.source == "nws_fallback":
        return "nws_fallback_blocked"
    if abs(net_edge) < 0.07:
        return "edge_too_small"
    if forecast.nws_value_f is not None:
        if abs(forecast.mean_f - forecast.nws_value_f) > 3.0:
            return "nws_disagrees"
    if forecast.api_agreement_count < 2:
        return "weak_source_agreement"
    return None


def side_from_edge(net_edge: float) -> str:
    return "BUY_YES" if net_edge > 0 else "BUY_NO"


def evidence_gated_shares(
    *,
    entry_price: float,
    city: str,
    forecast_source: str,
    tier: str,
    fixed_shares: int = 5,
    max_dynamic_shares: int = 40,
) -> int:
    scaled = (
        tier == "B"
        and forecast_source in {"noaa_nbm", "multi_model"}
        and city not in {"Seattle", "Denver"}
    )
    if not scaled:
        return fixed_shares
    if entry_price < 0.10:
        return min(30, max_dynamic_shares)
    if entry_price < 0.20:
        return min(20, max_dynamic_shares)
    if entry_price < 0.50:
        return fixed_shares
    return min(10, max_dynamic_shares)


def evaluate_market(market: Market, forecast: Forecast) -> dict:
    net_edge = forecast.model_probability - market.yes_price
    skip_reason = should_skip(market, forecast, net_edge)
    if skip_reason:
        return {"action": "SKIP", "reason": skip_reason}

    side = side_from_edge(net_edge)
    entry_price = market.yes_price if side == "BUY_YES" else 1.0 - market.yes_price
    tier = setup_tier(market, forecast, net_edge)
    shares = evidence_gated_shares(
        entry_price=entry_price,
        city=market.city,
        forecast_source=forecast.source,
        tier=tier,
    )
    notional = shares * entry_price

    if notional > 10.00:
        return {"action": "SKIP", "reason": "max_order_cap"}

    return {
        "action": side,
        "entry_price": round(entry_price, 3),
        "shares": shares,
        "notional": round(notional, 2),
        "tier": tier,
        "net_edge": round(net_edge, 4),
    }

