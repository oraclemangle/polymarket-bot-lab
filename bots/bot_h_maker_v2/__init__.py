"""Bot H Maker V2 — paper-only maker-flow bot per ADR-134.

Phase 1 (this module's current scope): wide CLOB recorder for politics +
sports + awards + crypto cheap-to-mid markets (0c-50c). Persists every
WSS book/trade event to a dedicated SQLite DB (`data/maker_recorder.db`)
so the operator can:

- Re-run the maker-flow simulator on real V2 forward data when enough
  accumulates (counterfactual analysis).
- Test the AS-proxy at alternative horizons (5-min, 15-min, 60-min,
  resolution).
- Validate or invalidate the killed-cell verdicts on forward evidence.

Phase 2 (subsequent sessions): quote engine + paper-fill simulator +
adverse-selection tracker. Quotes posted ONLY on:

  - politics 0-10c
  - sports 10-20c

per the 2026-05-08 outlier-robustness probe
(`docs/reports/track1-maker-flow-robustness-probe-2026-05-08.md`).

Paper-only. Live promotion requires a separate ADR.
"""

BOT_ID = "bot_h_maker_v2"

__all__ = ["BOT_ID"]
