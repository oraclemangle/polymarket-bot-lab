"""Bot A — Longshot Fade.

**STATUS: ARCHIVED 2026-04-18 (Session 17m) per ADR-033.**

Mechanical NO-side fader on tail-priced geopolitics/politics markets.
No LLM, no external-scorer dependency. Original spec: `specs/bot-a-spec.md`.

Archived after the 2026-04-18 walk-forward backtest against the
SII-WANGZJ trades.parquet dataset
(`docs/bot-a-walkforward-wangzj-2026-04-18.md`): 12,521 simulated
entries, 93.7% hit rate (thesis spec met), but **-$13,614 total PnL,
-$1.09 mean per trade**. Every category bucket negative, including
fee-free geopolitics (-2.42% mean edge, -$388 total on 535 trades).
The 1-in-16 full-loss dominates the 15 small wins — asymmetric loss,
not calibration.

Code preserved here so restoration is a single revert if new edge
evidence emerges. `bots/bot_a/__main__.py` early-exits when
`BOT_A_ARCHIVED` is unset or true (default) so a stray systemd
re-enable will not place orders. Tests and imports are intentionally
unchanged — they exercise dead-but-live code for future restoration.

**To bring back:** set `BOT_A_ARCHIVED=false`, re-enable the systemd
unit, update ADR-033 status to `reversed`, and pre-flight with a
fresh walk-forward on the new entry slice showing positive net PnL
before flipping the env var.
"""
