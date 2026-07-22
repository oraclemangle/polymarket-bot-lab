"""Position sizing for Bot A.

Per spec:
    position_size = min($30 fixed, 1% of bankroll, 2% of book depth)

Deliberately conservative; $30 is the hard cap even at full bankroll scale.
"""

from __future__ import annotations

from decimal import Decimal

from bots.bot_a.config import (
    BANKROLL_FRACTION_CAP,
    BOOK_DEPTH_FRACTION_CAP,
    ENTRY_SIZE_USD,
)


def size_position(
    bankroll_usd: Decimal,
    no_ask_depth_usd: Decimal,
) -> Decimal:
    """Return the USD notional to allocate for a single entry.

    Inputs are all in USD (the venue's quote currency).  Callers convert
    from GBP bankroll using a current spot rate before calling.
    """
    fixed = ENTRY_SIZE_USD
    bankroll_cap = bankroll_usd * BANKROLL_FRACTION_CAP
    depth_cap = no_ask_depth_usd * BOOK_DEPTH_FRACTION_CAP
    return min(fixed, bankroll_cap, depth_cap).quantize(Decimal("0.01"))


def shares_from_notional(notional_usd: Decimal, no_price: Decimal) -> Decimal:
    """Convert USD notional to share count at the NO-ask price.

    A Polymarket share pays out $1 at resolution, so price is in (0, 1).
    """
    if no_price <= Decimal("0"):
        raise ValueError(f"no_price must be positive, got {no_price}")
    return (notional_usd / no_price).quantize(Decimal("0.01"))
