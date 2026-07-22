"""Bot E — 15-minute BTC Up/Down OBI-directional trader.

Per ADR-022 (pivot from CEX-lag to OBI-directional): runs on the shared
the recorder host. Entry window: minutes 5–10 of each 15-min market.
Signal: order-book imbalance across the last N seconds of orders_matched.

**Activation is gated on Phase 0d go/no-go**. The recorder (see
`bots/bot_e_recorder/`) runs first for 3–4 days; the backtester
(`core/backtest_bot_e.py`) consumes the recorded data and produces a
per-bucket expectancy table. If positive EV after fees/slippage/latency
shows up in the (minute-to-expiry × OBI × regime) buckets we care about,
THEN this trader's thresholds are configured and paper trading starts.

Until then, `__main__.py` refuses to run outside `--dry-run` mode.

Maker-only entries (required by 2026 Polymarket dynamic fees — taker at 50¢
crypto costs 1.80% × 2 legs = 3.60% round trip, erasing any realistic edge).
All risk controls are env-overridable defaults per operator preference.
"""
