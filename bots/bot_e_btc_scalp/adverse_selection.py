"""Bot E adverse-selection guard.

Audit 2026-04-17 Phase 3 (Bot E §What I would change). A maker fill
happens only when a counterparty crosses your quote. On adversely-
selected markets (where the counterparty has information you don't),
the price moves against your fill in the seconds AFTER it happens.
If that happens >60% of the time, the signal is either non-predictive
or inverted.

This module tracks post-fill price movement and emits two signals:
  1. `register_fill(fill)` — call immediately after a paper or live fill.
  2. `measure_adverse_rate(window_s=30)` — returns the fraction of
     recent fills where the book moved against the fill within the window.

Storage: in-memory deque for the running window; persisted to the Event
table on every fill so post-session analysis is possible.

Hard gate: when adverse rate on the last N fills exceeds the threshold,
the caller (Bot E main loop) SHOULD halt or widen its maker offset.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Deque

log = logging.getLogger(__name__)


@dataclass
class FillOutcome:
    order_id: str
    fill_price: Decimal
    fill_side: str                  # "BUY_YES" | "BUY_NO"
    fill_ts_ms: int
    # Populated by `measure` after observing the book N seconds later:
    midpoint_after: Decimal | None = None
    moved_against: bool | None = None


@dataclass
class AdverseSelectionTracker:
    """Ring-buffer tracker of recent maker fills and post-fill price moves."""
    window: Deque[FillOutcome] = field(default_factory=lambda: deque(maxlen=50))

    def register(
        self,
        *,
        order_id: str,
        fill_price: Decimal,
        fill_side: str,
        fill_ts_ms: int | None = None,
    ) -> FillOutcome:
        outcome = FillOutcome(
            order_id=order_id,
            fill_price=fill_price,
            fill_side=fill_side,
            fill_ts_ms=fill_ts_ms or int(time.time() * 1000),
        )
        self.window.append(outcome)
        return outcome

    def measure(
        self,
        order_id: str,
        midpoint_after: Decimal,
    ) -> FillOutcome | None:
        """Update a tracked fill with the midpoint observed N seconds later.

        Both `fill_price` and `midpoint_after` are denominated in the
        SAME side (YES price for BUY_YES, NO price for BUY_NO).

        "Moved against" convention (adverse-selection for a maker fill):
          - BUY_YES: adverse = YES midpoint fell below fill_price
          - BUY_NO:  adverse = NO midpoint fell below fill_price

        Both branches use the SAME comparison because the sign convention
        is per-side: if you filled at `p` and the same-side midpoint
        settles below `p`, you got picked off. Prior 2026-04-22 GLM-5.1
        review (A6) flagged this as a bug because the old docstring said
        BUY_NO adverse = "rose"; that was a stale docstring, not a code
        bug (docstring didn't match the same-side convention above).
        """
        for outcome in reversed(self.window):
            if outcome.order_id != order_id:
                continue
            outcome.midpoint_after = midpoint_after
            # Same-side comparison: adverse = midpoint fell below fill price.
            outcome.moved_against = midpoint_after < outcome.fill_price
            return outcome
        return None

    def adverse_rate(self, last_n: int = 20) -> float | None:
        """Return fraction of the last N measured fills that moved against.

        None if fewer than `last_n` measured fills exist yet (insufficient data).
        """
        measured = [o for o in self.window if o.moved_against is not None]
        if len(measured) < last_n:
            return None
        recent = measured[-last_n:]
        return sum(1 for o in recent if o.moved_against) / len(recent)

    def should_halt(
        self,
        *,
        last_n: int = 20,
        adverse_threshold: float = 0.60,
    ) -> tuple[bool, str]:
        rate = self.adverse_rate(last_n=last_n)
        if rate is None:
            return False, f"insufficient_data n_measured={sum(1 for o in self.window if o.moved_against is not None)}"
        if rate >= adverse_threshold:
            return True, f"adverse_rate={rate:.2f} over last {last_n} fills >= {adverse_threshold}"
        return False, f"adverse_rate={rate:.2f} ok"
