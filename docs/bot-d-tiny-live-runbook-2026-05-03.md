# Bot D Tiny-Live Probe Runbook

**Date:** 2026-05-03
**Status:** Active tiny-live probe; loosened for live-data collection.
**Decision:** ADR-084.

## Purpose

Run a minimum-size live plumbing probe for Bot D while the existing `bot_d`
paper service continues in parallel. The probe is designed to measure live
fill transfer, slippage, reconciliation, and exit behaviour. It is not a full
Bot D live-readiness approval.

## Approved Packet

| Setting | Value |
|---|---:|
| Live bot id | `bot_d_live_probe` |
| Paper shadow bot id | `bot_d` |
| Wallet allocation posture | `$200` |
| Entry sizing | Evidence-gated ladder; `5` share fallback |
| Sizing ladder | `<10c=30`, `10-20c=20`, `20-50c=5`, `>=50c=10` |
| Cheap YES collection lane | `<10c` YES with NOAA/multi-model + 2-source agreement gets at least `20` shares and auto-lifts to the exchange `$1` marketable-BUY floor, capped at `40` shares |
| Sizing exclusions | Do not scale Tier `C`, Seattle/Denver, or GribStream-primary entries except the cheap-YES collection lane |
| Max dynamic shares | `40` |
| Max order notional | `$10` |
| Internal live min notional | `$0` (exchange rejects, if any, are recorded as live evidence) |
| Max daily gross notional | `$100` |
| Max open exposure | `$150` |
| Max concurrent positions | `20` |
| Verified settlement required | `true` |
| Known end date required | `true` |
| Wave required | `false` |
| Depth gate required | `false` |
| Minimum entry depth evidence | `$0` |
| NWS fallback entries | `false` |
| GribStream NBM fallback | `true` when `GRIBSTREAM_API_TOKEN` is present |
| NOAA NBM fallback | `true` |
| Take-profit auto-sell | `true`, verified live on 2026-05-05 |
| Paper Bot D | Keep running with matching non-wallet data/strategy settings |

## Service

Prepared unit:

`systemd/polymarket-bot-d-live.service`

Required live-probe environment carried by the unit:

- `BOT_D_ID_OVERRIDE=bot_d_live_probe`
- `BOT_D_ENV=live`
- `POLYMARKET_ENV=live`
- `BOT_D_LIVE_AUTHORIZED=true`
- `BOT_D_LIVE_APPROVED_AT=2026-05-03`
- `BOT_D_LIVE_PROBE_MODE=plumbing`
- `BOT_D_LIVE_WALLET_USD=200`
- `BOT_D_LIVE_FIXED_SHARES=5`
- `BOT_D_LIVE_SIZING_MODE=evidence_gated`
- `BOT_D_LIVE_MAX_DYNAMIC_SHARES=40`
- `BOT_D_LIVE_MAX_ORDER_USD=10`
- `BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=0`
- `BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=100`
- `BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD=150`
- `BOT_D_LIVE_MAX_CONCURRENT_POSITIONS=20`
- `BOT_D_REQUIRE_VERIFIED_SETTLEMENT=true`
- `BOT_D_REQUIRE_KNOWN_END_DATE=true`
- `BOT_D_REQUIRE_WAVE_FOR_ENTRY=false`
- `BOT_D_EDGE_THRESHOLD=0.07`
- `BOT_D_LIMIT_OFFSET=0.012`
- `BOT_D_GRIBSTREAM_ENABLED=true`
- `BOT_D_GRIBSTREAM_MODEL=nbm`
- `BOT_D_GRIBSTREAM_CACHE_TTL_SEC=21600`
- `GRIBSTREAM_API_TOKEN` must be present in runtime `.env`; never commit it.
- `BOT_D_NOAA_NBM_ENABLED=true`
- `BOT_D_NOAA_NBM_CACHE_TTL_SEC=3600`
- `BOT_D_NWS_OUTLIER_PROBE_ENABLED=true`
- `BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE=0.08`
- `BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F=2.0`
- `BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F=6.0`
- `BOT_D_DEPTH_GATE_ENABLED=false`
- `BOT_D_MIN_ENTRY_DEPTH_USD=0`
- `BOT_D_TAKE_PROFIT_ENABLED=true`
- `BOT_D_TAKE_PROFIT_MIN_BID=0.99`
- `BOT_D_TAKE_PROFIT_LIMIT_OFFSET=0.001`
- `BOT_D_TAKE_PROFIT_MIN_HOURS_TO_END=0`

Production note (2026-05-05): take-profit is verified live. The first
post-fix automated exit sold `5` NO shares at `0.994` and closed position
`632` under `bot_d_live_probe`.

Production note (2026-05-06): paper Bot D was aligned to the live probe's
non-wallet data and strategy settings so paper remains a useful shadow lane.
Live-only settings remain isolated to `bot_d_live_probe`.

## Activation Gate

Do not start or enable `polymarket-bot-d-live.service` during prep. Activation
requires a fresh explicit operator instruction after:

1. Local tests pass.
2. Production deploy/preflight passes.
3. The unit is installed but inactive.
4. Dashboard shows `bot_d_live_probe` separately from `bot_d`.
5. The production venv imports `scipy.stats.skewnorm` cleanly.
6. Watchdog logs show `bot_d_live_probe` uses live cancel routing.
7. The operator confirms the probe should start now.

## Stop Conditions

Stop `polymarket-bot-d-live.service` immediately if any of these occur:

- any live fill appears in the Polymarket UI but is not recorded under
  `bot_d_live_probe`;
- any local live order is absent from CLOB open orders and not closed locally;
- any live exit is stale, unmatched, or cannot be reconciled;
- daily gross notional exceeds `$100`;
- open exposure exceeds `$150`;
- a single submitted order exceeds `$10`;
- a forecast entry uses `forecast_source=nws_fallback`;
- scipy/skew-normal fallback is active;
- the service writes live rows under `bot_d` instead of `bot_d_live_probe`.

## Proof Milestones

After `5` live fills:

- Verify every fill is recorded under `bot_d_live_probe`.
- Verify no `bot_d` paper rows were polluted by live trades.
- Verify no untracked wallet positions exist.

After `10` live fills:

- Report fill rate versus paper candidates.
- Report median live entry slippage.
- Report open-order reject/cancel counts.

After `20` live fills:

- Report realised ROI, ex-largest-win ROI, and ex-largest-two ROI.
- Report stale exit count and exit slippage.
- Decide whether to continue, stop, or propose a revised probe.

No size increase is allowed from this runbook alone.
