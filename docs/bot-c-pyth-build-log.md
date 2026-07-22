# Bot C (Pyth) — Build Log

**Branch:** merged onto `main`.
**Last updated:** 2026-04-15.
**Status:** Ingest daemon works end-to-end against live Pyth Lazer Pro feed. Audit follow-up fixed the two production-footgun edges discovered after merge: silent idle startup with no Pro token, and loss of the final in-memory bar on shutdown.

## What's built

- `core/pyth_feeds.py` — Feed registry. 5 verified ids (GOLD 346, SILVER 345, AAPL 922, TSLA 1435, NVDA 1314); 10 TODOs pending Pyth Terminal id lookup.
- `core/pyth_models.py` — SQLAlchemy 2.x models: `PythBarPro`, `PythBarHermes`, `PythTickRecent`. Registered on import.
- `core/pyth_ingest.py` — Async ingest daemon. Dual-endpoint skeleton: Pro subscriber is fully functional; Hermes is a documented stub. Features: exponential-backoff reconnect (1s → 60s cap), 200ms→1s OHLC bar aggregation, raw-tick table with 2h retention, 30s heartbeat, trial-expiry alarm (loud warn after 2026-04-22), fail-fast startup when no subscriber can actually start, and shutdown flush of open bars.
- `migrations/versions/20260415_1800_c9e1f4a82b7d_add_pyth_tables.py` — Alembic migration for the three new tables.
- `bots/bot_c_pyth/{__init__,__main__,config}.py` — CLI daemon. `python -m bots.bot_c_pyth --endpoint {both,pro,hermes}`. Endpoint selection now also honors `BOT_C_ENDPOINT` when the CLI flag is omitted.
- `tests/bot_c_pyth/test_pyth_ingest.py` — 13 tests, zero network IO. Covers decode, bar aggregation, rollover, prune, reconnect backoff, WS frame parsing, Hermes stub, shutdown flush, and fail-fast startup on bad config.

## Verification

- **13/13 Bot C tests pass.**
- **Full repo suite: 176/176 pass** — no regression on existing Bot A/B/core tests.
- **Live feed smoke test (12 seconds):** 265 ticks → 55 flushed 1s bars across 5 feeds. Prices sanity-check against real market quotes (GOLD $4802, AAPL $264, TSLA $387, NVDA $196, SILVER $79).

## Known limitations

1. **Hermes subscriber is a stub.** Needs Pyth Hermes hex-encoded feed-id mapping (different schema from Lazer numeric ids). TODO flagged in code.
2. **Feed registry partial.** Only 5 of 15 target symbols have verified ids; SPY, QQQ, EWY, WTI, NATGAS, COIN, PLTR, BTC, ETH, SOL are None-placeholders. Look up on Pyth Terminal and fill in.
3. **No Pro-vs-Hermes diff report yet.** Day-8 comparison script `scripts/pyth_pro_vs_hermes_diff.py` not built (blocked on Hermes being functional).
4. **No trading path.** Ingest-only by design. Strategy layer comes after the 7-day data hoover.

## Open risks

- **Pyth Pro trial expires 2026-04-22.** After that, $5k/month. The daemon logs a loud WARNING every minute once expired. Action required on day 7: restart Bot C with `--endpoint hermes` or `BOT_C_ENDPOINT=hermes`, and fix the Hermes stub.
- **`.env` contains PYTH_TOKEN in plaintext.** Consistent with existing repo convention (GOOGLE_API_KEY, GROQ_API_KEY, etc. stored the same way). Escalation path if needed: keystore pattern used for POLYMARKET_PASSPHRASE_PATH.

## Isolation posture

Primary implementation stayed isolated to `core/pyth_*`, `bots/bot_c_pyth/`, `tests/bot_c_pyth/`, `migrations/versions/*pyth*`, and `systemd/polymarket-bot-c.service`. Audit follow-up also touched Bot C config/service wiring and this log; shared Bot A/B trading modules were not changed.

## Next actions (in order)

1. Let the daemon run continuously for the remaining ~7 days to build calibration dataset. Run under `tmux` or systemd; DB file at `data/bot_c_pyth.db` (add to backup rota).
2. On Pyth Terminal, look up feed ids for the 10 TODO symbols (esp. SPY, QQQ, BTC, ETH, SOL) and fill into `core/pyth_feeds.py`.
3. Build `core/pyth_hermes.py` — port the Hermes price-feed-v2 stream schema; promote the stub to real subscriber. Then pyth_pro_vs_hermes diff is meaningful.
4. First strategy slice: Pyth→Polymarket latency arb on traditional-asset daily Up/Down. Lives in `bots/bot_c_pyth/{filters,sizer,executor,lifecycle}.py`, mirroring Bot B's layout.
