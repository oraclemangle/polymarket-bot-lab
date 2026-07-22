"""Bot A flow source — builds FlowWindow snapshots for the exec-policy toxicity check.

**MVP scope (2026-04-18):** stub implementation that returns zero-flow windows.
Zero flow => toxicity always 0 => `should_place` always allows placement.
This lets us ship the exec-policy wiring to production with the feature flag
flipped ON, measure that the plumbing is stable, and then replace the stub
with a real data source in a follow-up session WITHOUT touching the executor.

Real-flow candidates for the follow-up (none built yet):
1. HTTP-polled `https://clob.polymarket.com/trades?market={cid}&limit=100`
   at placement time, filter to last 60s, classify side. Stale but simple.
2. Subscribe Bot A to the existing `core/polymarket_ws.py` feed for its active
   candidate markets, maintain an in-process rolling window per market. More
   code but zero round-trip latency.
3. Ingest into a shared `aggressive_flow` table populated by a dedicated
   market-flow service. Heaviest but fleet-wide reusable.

**Do not block on "but the stub returns zero flow."** Zero flow is correct
pre-measurement behaviour: allow every placement, see how often toxicity
would have fired on real flow data (instrumented in a future pass).
"""
from __future__ import annotations

import logging
import time

from core.exec_policy import FlowWindow

log = logging.getLogger(__name__)


def build_flow_window(
    market_id: str,
    lookback_s: int = 60,
    now_ts: float | None = None,
) -> FlowWindow:
    """Return a FlowWindow for the given market.

    MVP STUB: returns an all-zero FlowWindow. See module docstring.
    """
    ts_end = now_ts if now_ts is not None else time.time()
    ts_start = ts_end - lookback_s
    return FlowWindow(
        ts_start=ts_start,
        ts_end=ts_end,
        aggressive_buy_yes_usd=0.0,
        aggressive_sell_yes_usd=0.0,
        aggressive_buy_no_usd=0.0,
        aggressive_sell_no_usd=0.0,
    )
