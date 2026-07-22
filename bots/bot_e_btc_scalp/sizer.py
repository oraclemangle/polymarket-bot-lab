"""Bot E — position sizing.

v1 sizing per ADR-022 / Codex C-S3: **fixed $2 per trade** until 300+
calibrated paper trades exist. Kelly is in the config as a future switch
(`BOT_E_KELLY_FRACTION`); set it to 0 in v1.

Also enforces:
- Crypto-bucket correlation cap (Grok S3): all open BTC+ETH+SOL notional
  cannot exceed 15% of bankroll.
- Aggregate exposure cap: all open positions combined cannot exceed 30%.
- Per-trade cap as safety net (2.5% of bankroll).

All bounds env-overridable via config.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

log = logging.getLogger(__name__)


@dataclass
class OpenPosition:
    """Minimal representation of a currently-open position for sizing math."""
    subscription_id: str
    symbol: str                # "BTC" | "ETH" | "SOL" | ...
    side: str                  # "BUY_YES" | "BUY_NO"
    notional_usd: Decimal      # current exposure value
    is_crypto: bool = True


@dataclass
class SizingDecision:
    can_enter: bool
    reason: str
    proposed_notional: Decimal
    proposed_shares: Decimal


def size_maker_entry(
    *,
    signal_side: str,                   # "BUY_YES" | "BUY_NO"
    limit_price: Decimal,               # the price we'd place the maker order at
    bankroll_usd: Decimal,
    fixed_trade_usd: Decimal,
    per_trade_cap_frac: Decimal,
    crypto_bucket_cap_frac: Decimal,
    aggregate_cap_frac: Decimal,
    open_positions: list[OpenPosition],
    symbol: str,
    is_crypto: bool = True,
    # Audit 2026-04-17 (GLM-5.1/Codex Q21): correlation-adjusted effective
    # exposure for multi-asset crypto. When `crypto_correlation_adj=True`
    # and more than one crypto asset is held (distinct `symbol`), the
    # bucket-cap check compares sum(notionals) * sqrt(1 + avg_corr) against
    # the cap. Same-asset additions are not inflated.
    crypto_correlation_adj: bool = False,
    crypto_avg_correlation: Decimal = Decimal("0"),
) -> SizingDecision:
    """Decide how many shares to place at `limit_price`.

    Returns `can_enter=False` with a reason if any cap would be breached.
    """
    if limit_price <= 0 or limit_price >= 1:
        return SizingDecision(
            can_enter=False, reason=f"bad_limit_price={limit_price}",
            proposed_notional=Decimal("0"), proposed_shares=Decimal("0"),
        )

    # ADR-037 min-entry filter: [0.0, BOT_E_MIN_ENTRY_PRICE) bucket had 25% WR
    # on 4 trades. Noise floor; skip to preserve capital.
    from bots.bot_e_btc_scalp.config import BOT_E_MIN_ENTRY_PRICE
    if limit_price < BOT_E_MIN_ENTRY_PRICE:
        return SizingDecision(
            can_enter=False,
            reason=f"below_min_entry_price={limit_price}<{BOT_E_MIN_ENTRY_PRICE}",
            proposed_notional=Decimal("0"), proposed_shares=Decimal("0"),
        )

    # v1 notional — fixed $2, capped by per-trade cap.
    per_trade_cap_usd = bankroll_usd * per_trade_cap_frac
    notional = min(fixed_trade_usd, per_trade_cap_usd)
    if notional <= 0:
        return SizingDecision(
            can_enter=False, reason="notional_zero_after_cap",
            proposed_notional=Decimal("0"), proposed_shares=Decimal("0"),
        )

    # Crypto-bucket cap: all crypto positions + this new one.
    # Audit 2026-04-17: if correlation adjustment is enabled and the new
    # position diversifies across symbols, inflate effective exposure by
    # sqrt(1 + avg_correlation). Three positions at 3% each with 0.8 corr
    # appear as ~12% effective — breaches a 10% cap.
    if is_crypto:
        crypto_positions = [p for p in open_positions if p.is_crypto]
        crypto_now = sum((p.notional_usd for p in crypto_positions), Decimal("0"))
        raw_total = crypto_now + notional
        effective_total = raw_total
        if crypto_correlation_adj and crypto_avg_correlation > 0:
            symbols_after = {p.symbol for p in crypto_positions} | {symbol}
            if len(symbols_after) > 1:
                # sqrt(1 + rho) via Decimal's sqrt.
                from decimal import getcontext
                inflator = (Decimal("1") + crypto_avg_correlation).sqrt()
                effective_total = raw_total * inflator
        crypto_cap_usd = bankroll_usd * crypto_bucket_cap_frac
        if effective_total > crypto_cap_usd:
            return SizingDecision(
                can_enter=False,
                reason=(
                    f"crypto_bucket_cap: effective={effective_total} "
                    f"(raw={raw_total}) > {crypto_cap_usd}"
                ),
                proposed_notional=notional,
                proposed_shares=Decimal("0"),
            )

    # Aggregate cap: all open positions
    total_now = sum(
        (p.notional_usd for p in open_positions), Decimal("0"),
    )
    total_cap_usd = bankroll_usd * aggregate_cap_frac
    if total_now + notional > total_cap_usd:
        return SizingDecision(
            can_enter=False,
            reason=f"aggregate_cap: {total_now}+{notional} > {total_cap_usd}",
            proposed_notional=notional,
            proposed_shares=Decimal("0"),
        )

    # Compute share count at the limit price. Quantize to 0.01 shares
    # (Polymarket minimum share increment is typically 0.01).
    shares = (notional / limit_price).quantize(Decimal("0.01"))
    if shares <= 0:
        return SizingDecision(
            can_enter=False, reason="shares_zero_after_quantize",
            proposed_notional=notional,
            proposed_shares=Decimal("0"),
        )

    # ADR-037 tail-clip: cap single-fill share count so a low-price entry
    # can't size to 5-7x median and lose a month of edge in one trade.
    from bots.bot_e_btc_scalp.config import BOT_E_MAX_SHARES_PER_POSITION
    if shares > BOT_E_MAX_SHARES_PER_POSITION:
        shares = BOT_E_MAX_SHARES_PER_POSITION.quantize(Decimal("0.01"))
        notional = (shares * limit_price).quantize(Decimal("0.01"))

    return SizingDecision(
        can_enter=True, reason="ok",
        proposed_notional=notional,
        proposed_shares=shares,
    )
