# Bot D Audit Rollout — Phases 2–4

**Created:** 2026-05-10
**Source:** Bot D comprehensive audit (Session 328 continuation)
**Phases 0–1:** Executed 2026-05-10 (docs + config alignment)
**Last reviewed:** 2026-05-11

---

## 2026-05-11 Safe Cleanup Completed

These items were pulled forward because live telemetry showed real failed
entry attempts rather than theoretical cleanup work:

- Added a finite-number entry guard in `BotDExecutor.try_enter()` so NaN/inf
  forecast values, probabilities, edges, prices, and size multipliers are
  blocked before sizing or order placement.
- Added a hard live exchange floor: live BUY orders below Polymarket's observed
  `$1.00` marketable-BUY notional floor are blocked even when
  `BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=0` for the cheap-YES lane.
- Kept ADR-148 cheap-YES collection intact: two-source cheap YES trades can
  still auto-lift to the `$1.00` floor when the lane qualifies and the dynamic
  share cap allows it.
- Added Wuhan, Guangzhou, Karachi, Panama City, and Ankara to the city registry
  as `candidate` / live-ineligible cities so they are no longer invisible
  unknowns in discovery.
- Updated the dashboard cap reader to use the live systemd unit environment for
  `bot_d_live_probe`, preventing stale dashboard defaults from showing `20`
  positions when the live unit is configured for `50`.

## Phase 2 — Code Hardening (in progress)

### 2.1 Consecutive-loss circuit breaker
**Severity:** High | **Risk:** Low (paper-only while enabled)

Bot D has no per-bot circuit breaker. If the model is systematically wrong for a weather regime (e.g., a stalled front producing multi-day outliers), Bot D will keep entering at full size until bankroll exhaustion.

- Add `BOT_D_MAX_CONSECUTIVE_LOSSES` env var (default 5).
- Track consecutive resolved losses in `executor.py`.
- On breach: halt entries, log `bot_d.circuit_breaker.losses`, require manual reset.
- Separate counter for paper vs live.

### 2.2 Async weather fetcher refactor
**Severity:** Medium | **Risk:** Medium (touches core fetch path)

`weather_fetcher.py` (47.3K) makes sequential HTTP calls to Open-Meteo, NOAA NBM, NWS gridpoint, GribStream, and METAR endpoints. A single slow endpoint blocks the entire scan.

- Convert `fetch_all_forecasts()` to `asyncio.gather()` with per-endpoint timeouts.
- Keep `_FORECAST_CACHE` thread-safe (already has threading lock; switch to asyncio lock).
- Fallback: if any source fails, run with remaining sources rather than aborting.
- Add `bot_d.fetch_latency` telemetry per source.

### 2.3 Depth gate invariant
**Severity:** Medium | **Risk:** Low

Live service has `BOT_D_DEPTH_GATE_ENABLED=false` and `BOT_D_MIN_ENTRY_DEPTH_USD=0`. This means the live probe enters regardless of ask-side capacity. In thin weather markets, a $1 order can clear the book and produce fills at prices that don't reflect real liquidity.

- Enable depth gate in live service once the plumbing probe graduates from `BOT_D_LIVE_FIXED_SHARES=5` testing.
- Set `BOT_D_MIN_ENTRY_DEPTH_USD=25` (matching paper default).
- Add a `bot_d.depth_gate.rejected` metric to quantify how many entries are blocked.

### 2.4 Unknown-city tracking
**Severity:** Low | **Risk:** Low | **Status:** Partially complete 2026-05-11

When `resolve_city()` returns None, the market is logged but no structured tracking exists. New Polymarket cities can go unnoticed for days.

- Done: five recently seen cities are now registered as candidate/shadow-only
  entries so discovery can classify them safely.
- Still pending: write unknown-city events to a `bot_d_unknown_cities` table or structured log.
- Include question text, timestamp, and attempted aliases.
- Add a weekly summary to the dashboard: "N new cities this week, M unresolved."

### 2.5 METAR UHI offset audit
**Severity:** Medium | **Risk:** Low

METAR urban heat island offsets (NYC/Miami/Dallas +2F, Chicago/Atlanta +1F) are applied unconditionally. No backtest validates whether these offsets improve or degrade edge measurement.

- Run a shadow lane with UHI disabled (`BOT_D_UHI_ENABLED=false`).
- After 30 resolved positions in each lane, compare P&L.
- If UHI-disabled lane outperforms, drop the offsets.

### 2.6 Edge-collapse exit path hardening
**Severity:** Medium | **Risk:** Low

`review_open_positions()` at executor.py:1261 has an edge-collapse exit (K2.6 fix). This path exits positions when the measured edge drops below threshold, but the exit logic uses current market price rather than a limit order.

- Verify the exit uses `BOT_D_LIVE_EXIT_LIMIT_OFFSET` for live orders.
- Add `bot_d.edge_collapse.exit` telemetry with before/after edge values.
- Ensure the exit doesn't fire on transient edge dips (consider a 2-scan cooldown).

---

## Phase 3 — Operator Decisions (requires user input)

### 3.1 Station-divergence thesis viability
**Category:** Strategy | **Decision needed by:** 2026-05-31 (kill date)

The station-divergence report (`docs/reports/bot-d-station-divergence-2026-05-10.md`) shows 10/28 markets (35.7%) had outcome-flipping divergence between forecast and station, with avg 3.4F. But the station-informed P&L (-$68.78) is worse than forecast-only (-$6.38).

Questions for operator:
1. Does the station-divergence thesis survive the 28-market sample, or does it invert (station adjustments hurt, not help)?
2. Should Bot D pause station-informed entries and run forecast-only until n=50 resolved?
3. Is the Seattle outlier (7 markets, 4 flips) a model problem or a station problem?

### 3.2 City-specific allowlists
**Category:** Configuration | **Decision needed by:** Before next live expansion

17 new cities were added in the 2026-05-10 expansion. Only 8 have verified settlement specs. The operator needs to decide:

1. Which of the shadow/candidate cities to prioritize for settlement verification?
2. Should international live (`BOT_D_INTERNATIONAL_LIVE_ENABLED`) stay false until US-only live proves edge?
3. Should any cities be explicitly allowlisted/blocklisted for paper vs live?

### 3.3 Drawdown kill test
**Category:** Risk | **Decision needed by:** Before live sizing increase

The live probe has no per-bot drawdown kill switch. Propose:
- `BOT_D_LIVE_MAX_DRAWDOWN_USD=50` (25% of $200 wallet).
- On breach: halt entries, log `bot_d.kill_switch.drawdown`, require operator reset.
- Question: is this the right threshold for a $200 wallet?

### 3.4 Kill date extension evaluation
**Category:** Timeline | **Decision needed by:** 2026-05-31

Current kill date is 2026-05-31. Requirements: net realised edge < 2.5% per position after 1.25% fees on >= 15 resolved positions.

Questions:
1. How many resolved positions are expected by 2026-05-31 given current entry rate?
2. If n < 15 by kill date, extend or archive on insufficient data?
3. Does the +$13.31 realised P&L on the dashboard change the kill-date posture?

### 3.5 Edge threshold divergence resolution
**Category:** Configuration | **Decision needed by:** After 20 live resolved positions

Paper default: `BOT_D_EDGE_THRESHOLD=0.10`. Live service override: `0.07`. This divergence is now documented (Phase 1) but not resolved.

After 20 live fills, compare:
- Entries that would have been blocked at 0.10 vs allowed at 0.07.
- Win rate and P&L of the 0.07-0.10 band specifically.
- Decide: unify at 0.10, unify at 0.07, or keep the split permanently.

---

## Phase 4 — Backlog (nice-to-have, no urgency)

### 4.1 Polymarket oracle divergence monitoring
Add a comparison between Polymarket's actual temperature resolution and the Bot D source snapshot. Track `bot_d.oracle_divergence` events when Polymarket's published settlement temperature differs from the station reading by >1F.

### 4.2 Seasonal RMSE backtest
The seasonal multipliers (winter x1.40, summer x0.70) are theoretically sound but not empirically validated against Bot D's own resolved positions. Run a backtest comparing seasonal vs flat RMSE on the resolved sample once n >= 50.

### 4.3 Forecast cache warming
Pre-warm the forecast cache before each scan window instead of fetching on-demand. This eliminates cold-start latency on the first market evaluation of each scan.

### 4.4 Multi-model ensemble weighting
The current ensemble treats GFS (31 members) and ECMWF (51 members) with equal per-member weight. Consider Bayesian model averaging or performance-based weighting once enough resolved positions exist to measure per-model skill.

### 4.5 Dashboard settlement coverage view
Add a dashboard panel showing verification_status breakdown across all 39 cities: verified / shadow / candidate / rejected / unknown counts.

### 4.6 Historical replay for new cities
When a new city is added, replay historical Polymarket markets to backfill the paper trading record. This accelerates the "time-to-evidence" for newly added cities.

### 4.7 Istanbul settlement investigation
Istanbul is the largest candidate-status city by market volume. Investigate which station Polymarket uses (LTFM new airport vs LTBA Ataturk) and verify.

### 4.8 Cape Town station verification
Southern-hemisphere city with `verification_status="shadow"`. Verify whether Polymarket settles off FACT (Cape Town Intl) or another station.

---

## Summary

| Phase | Items | Effort | Blocker |
|---|---|---|---|
| Phase 2 | 6 code-hardening items; 1 partial done | ~2 sessions | None (can start anytime) |
| Phase 3 | 5 operator decisions | ~1 session discussion | Operator availability |
| Phase 4 | 8 backlog items | ~3-4 sessions | None (do when idle) |

**Next action:** implement the consecutive-loss/drawdown circuit breaker before
any further Bot D cap or size increase, then review Phase 3 items before the
2026-05-31 kill date.
