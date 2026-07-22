"""Polymarket 2026 dynamic fee curve.

Polymarket charges PARABOLIC taker fees. Official formula (docs.polymarket.com/trading/fees):

    fee_usd = C * feeRate * p * (1 - p)

where C = shares traded and p = share price. The peak (at p=0.5) equals
`feeRate * 0.25` USDC *per share*. For 100 crypto shares at p=0.5 with
feeRate=0.072, peak fee = 100 * 0.018 = $1.80.

IMPORTANT (2026-04-22 audit fix — Codex fleet review Section A #7):
The prior implementation labelled the parabolic value as a "fraction of
notional" and then multiplied by `notional = price * size`. That added an
extra `price` factor, so realised fees were `feeRate * size * price^2 *
(1-price)` — understated by factor `price` (50% at p=0.50, 95% at
p=0.05). Every bot's P&L, EV filter, and graduation gate was affected.

Corrected semantics:
    taker_fee_per_share(p, cat) -> Decimal    # USDC charged per share
    fee_for_fill: gross_fee = size * taker_fee_per_share(p, cat)

Legacy name `taker_fee_rate` remains as an alias returning the same
value — callers must interpret it as "fee in USDC per share", not
"fraction of notional". Any `rate * notional` pattern in caller code
is the bug we just fixed.

Maker rebates are distributed as discretionary per-market daily pools
(docs: "Maker Rebates"), NOT guaranteed per-fill cash flow. We retain the
`maker_rebate_rate()` accessor for accounting/dashboard use, but EV and
edge calculations must treat the rebate as zero by default. Pass
`include_rebate_in_ev=True` to opt-in when caller has reconciled actual
rebate receipts against expected.

Shape source: Polymarket docs. Verified via WebFetch 2026-04-22.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

# Category-specific feeRate (bps of price). Peak fee (at p=0.5) = feeRate * 0.25.
# Source: Polymarket docs, cross-referenced with public fee schedule pages.
# Stored as feeRate (not peak) so the parabolic formula reads cleanly.
TAKER_FEE_RATE_BY_CATEGORY: dict[str, Decimal] = {
    "crypto":      Decimal("0.0720"),  # peak 1.80%
    "economics":   Decimal("0.0500"),  # peak 1.25% (was 1.50% — incorrect)
    "mentions":    Decimal("0.0400"),  # peak 1.00% (was 1.56% — incorrect)
    "culture":     Decimal("0.0500"),  # peak 1.25%
    "weather":     Decimal("0.0500"),  # peak 1.25%
    "finance":     Decimal("0.0400"),  # peak 1.00%
    "politics":    Decimal("0.0400"),  # peak 1.00%
    "tech":        Decimal("0.0400"),  # peak 1.00%
    "sports":      Decimal("0.0300"),  # peak 0.75%
    "geopolitics": Decimal("0"),       # zero-fee category (2026 schedule)
}

# Maker rebate as fraction of counterparty's taker fee.
# Docs: crypto = 20%, all other categories = 25%.
# Rebates are distributed as daily per-market pool payouts (not guaranteed
# per-fill revenue). EV calculations must NOT count on these by default.
_MAKER_REBATE_FRAC_CRYPTO = Decimal("0.20")
_MAKER_REBATE_FRAC_DEFAULT = Decimal("0.25")


def _maker_rebate_frac(category: str) -> Decimal:
    return (
        _MAKER_REBATE_FRAC_CRYPTO
        if category.lower() == "crypto"
        else _MAKER_REBATE_FRAC_DEFAULT
    )


# Shape of the fee curve. Parabolic per 2026 Polymarket docs.
TAKER_FEE_SHAPE: Literal["parabolic"] = "parabolic"


@dataclass(frozen=True)
class FeeBreakdown:
    """Per-share fee breakdown for a single fill."""
    gross_fee: Decimal      # absolute fee paid/received on notional
    rate: Decimal           # effective fee rate (0 for maker, positive for taker)
    is_maker_rebate: bool   # true when this is a rebate we receive


def taker_fee_per_share(price: Decimal | float, category: str) -> Decimal:
    """Return the taker fee in USDC per share at the given price.

    Parabolic: fee_per_share = feeRate * p * (1-p). Peak at p=0.5 equals
    feeRate * 0.25 USDC per share. For crypto (feeRate=0.072), peak =
    $0.018/share. Multiply by size (shares) to get fill fee in USDC.

    Price must be in (0, 1) exclusive; otherwise returns 0 (defensive).
    Unknown category returns 0 (conservative — caller should validate).
    """
    p = Decimal(str(price))
    if p <= Decimal("0") or p >= Decimal("1"):
        return Decimal("0")
    fee_rate = TAKER_FEE_RATE_BY_CATEGORY.get(category.lower(), Decimal("0"))
    if fee_rate == 0:
        return Decimal("0")
    return fee_rate * p * (Decimal("1") - p)


# Legacy alias — same value, semantically "fee in USDC per share". Kept so
# existing callers don't break during migration; new code should call
# `taker_fee_per_share` directly for clarity.
def taker_fee_rate(price: Decimal | float, category: str) -> Decimal:
    """Deprecated: alias for `taker_fee_per_share`. See module docstring."""
    return taker_fee_per_share(price, category)


def maker_rebate_per_share(
    price: Decimal | float,
    category: str,
    *,
    include_in_ev: bool = False,
) -> Decimal:
    """Return the maker rebate in USDC per share at the given price.

    Rebates are category-aware (crypto 20%, others 25% of counterparty taker fee).

    BY DEFAULT returns 0 for EV/edge purposes because Polymarket distributes
    rebates as discretionary daily per-market pools, not guaranteed per-fill
    revenue (docs: "Maker Rebates"). Callers that have reconciled actual
    rebate receipts may pass `include_in_ev=True` to use the nominal rate.

    The accounting path (fee_for_fill with is_maker=True) still uses the
    nominal rate regardless — that's for dashboard display, not for
    pre-trade decisions.
    """
    if not include_in_ev:
        return Decimal("0")
    return taker_fee_per_share(price, category) * _maker_rebate_frac(category)


def maker_rebate_rate(
    price: Decimal | float,
    category: str,
    *,
    include_in_ev: bool = False,
) -> Decimal:
    """Deprecated alias for `maker_rebate_per_share`. See module docstring."""
    return maker_rebate_per_share(price, category, include_in_ev=include_in_ev)


def _maker_rebate_per_share_nominal(price: Decimal | float, category: str) -> Decimal:
    """Internal: nominal rebate in USDC per share (ignores EV-safety default).

    Used by `fee_for_fill` for accounting; never for pre-trade EV math.
    """
    return taker_fee_per_share(price, category) * _maker_rebate_frac(category)


# Backwards-compat name — same value.
_maker_rebate_rate_nominal = _maker_rebate_per_share_nominal


def fee_for_fill(
    price: Decimal | float,
    size_shares: Decimal | float,
    category: str,
    *,
    is_maker: bool,
) -> FeeBreakdown:
    """Compute fee for a single fill (for accounting, not EV).

    Per Polymarket docs: fee_usd = size * baseRate * p * (1-p).
    `taker_fee_per_share(p, cat)` returns `baseRate * p * (1-p)` directly,
    so fill fee = size * taker_fee_per_share.

    Maker rebate is category-aware (crypto 20%, others 25% of counterparty
    taker fee). The accounting path records the nominal rebate even though
    actual distribution is a daily pool share.
    """
    p = Decimal(str(price))
    s = Decimal(str(size_shares))
    if is_maker:
        per_share = _maker_rebate_per_share_nominal(p, category)
        return FeeBreakdown(
            gross_fee=-(s * per_share),  # negative = we receive it
            rate=per_share,
            is_maker_rebate=True,
        )
    per_share = taker_fee_per_share(p, category)
    return FeeBreakdown(
        gross_fee=s * per_share,
        rate=per_share,
        is_maker_rebate=False,
    )


def round_trip_cost_rate(
    entry_price: Decimal | float,
    exit_price: Decimal | float,
    category: str,
    *,
    entry_is_maker: bool,
    exit_is_maker: bool,
    include_maker_rebate: bool = False,
) -> Decimal:
    """Return the total fee RATE (as fraction of entry notional) for a round trip.

    Helper for edge calculations: `edge_net = edge_gross - round_trip_cost_rate(...)`.

    By default `include_maker_rebate=False` — maker fills are priced at zero
    fee for EV purposes (rebate is pool-distributed, not guaranteed).
    Pass True only when the caller has empirically validated rebate receipt.

    Approximation: uses entry price to normalize. Fine for the 5–15 cent moves
    Bot E targets; revisit for longer-hold strategies.
    """
    entry_p = Decimal(str(entry_price))
    if entry_p == 0:
        return Decimal("0")

    def _leg(price: Decimal | float, is_maker: bool) -> Decimal:
        # Return fee in USDC per share for this leg.
        p = Decimal(str(price))
        if is_maker:
            if include_maker_rebate:
                return -_maker_rebate_per_share_nominal(p, category)
            return Decimal("0")  # EV-safe default: maker leg costs nothing, earns nothing
        return taker_fee_per_share(p, category)

    # Sum per-share fees on both legs, then normalise to fraction of entry
    # notional (per-share entry cost = entry_price).
    return (_leg(entry_price, entry_is_maker) + _leg(exit_price, exit_is_maker)) / entry_p
