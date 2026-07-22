# Fast ROI To-Do

**Date:** 2026-05-01
**Status:** Superseded/closed 2026-05-18 by the active operating model,
ADR-181, and OQ-123. Completed checklist items remain as historical evidence;
open items have been carried forward only where still current in
`docs/open-questions.md` or `docs/active-operating-model-2026-05-02.md`.
**Goal:** identify the fastest credible path to profitable turnover without
pretending Bot F direct whale-copying is a good standalone bot.

## Decision

Bot F is demoted as a direct ROI bot. Its useful functions are now shared
infrastructure:

- crowd/cascade detection;
- wallet-flow pressure;
- market crowding warnings;
- future veto/fade/confirm features for Bot E, Bot G, Bot D, and Bot B.

The direct mirror stays paper/measurement only unless a future report proves
latency-adjusted copy P&L beats using Bot F as a sensor.

## Priority Order

### P0 — Fast ROI Report and Ranking

- [x] Add read-only `scripts/fast_roi_report.py`.
- [x] Include Bot E, Bot G Prime, and Bot D in the report.
- [x] Include Bot F crowd-sensor summary without treating Bot F as a trader.
- [x] Run the report on the bot LXC container and archive JSON/Markdown output.
- [x] Add hourly systemd timer for the report on the bot LXC container.
- [x] Add dashboard summary for Bot D wallet-readiness blockers.
- [ ] Add Telegram summary once the output stabilizes.

### P0 — Bot E Fast ROI Sprint

- [x] Run Bot E cancel/autopsy report with current book coverage.
- [x] Report fill rate by TTL/offset.
- [x] Report adverse movement after fill at 30s/60s/300s.
- [x] Simulate `$25` and `$50` maker order sizes against observed depth.
- [ ] Compute maker-reward break-even only after reward reconciliation is
  available.
- [ ] Promote only if fills are not toxic after fees/slippage.

**2026-05-01 production read:** loosening TTL/offset is not the next move.
Current fills already arrive, but 30s adverse movement is about `61-65%` in
the tested scenarios. Improve fill quality before chasing higher fill count.

**2026-05-01 Phase 0/1 read:** cancel autopsy now reports `$25`/`$50`
depth coverage per TTL/offset scenario. the bot LXC container saw `20` recent orders; first
scenarios filled `14/20`, with `$25` coverage `12/14` and `$50` coverage
`9/14`. Capacity visibility improved, but toxic-fill proof remains the gate.

### P0 — Bot G Prime Fast Challenger

- [x] Run Prime cohort report: 4c-5c vs 5c-8c.
- [x] Report ex-largest-win and ex-largest-two-wins ROI.
- [x] Split confirmed vs unconfirmed entries.
- [x] Check causal depletion/reload feature without lookahead.
- [x] Simulate `$25` and `$50` capacity.
- [x] Add V2 crypto fee stress: maker-entry, taker-entry, and mixed legs.
- [x] Add dashboard panel for Bot G cohort P&L and fee-adjusted P&L basis.
- [ ] Extract useful execution patterns from
  `lihanyu81/polymarket_lp_tool`: post-only replace safety, reward scoring
  visibility, fill-risk telemetry, and Telegram alerts.
- [ ] Pause Prime if positive results vanish after trimming outliers.

**2026-05-01 production read:** Prime headline ROI is positive, but only
because one `+$120.00` win offsets thirteen losing round trips. Ex-largest-win
and ex-largest-two-wins ROI are both `-100.0%`, so Prime stays paper.

**2026-05-01 V2 fee review:** Bot G now gets the same strategic focus as
Bot D, but must prove the `4c-5c` Prime subset under current CLOB V2 crypto
fees. The live path is maker-first unless taker entries still clear fees,
spread, slippage, and latency at `$25` and `$50`. The LP tool review found
useful execution infrastructure patterns, not a strategy to copy.

**2026-05-01 Phase 0/1 read:** fresh `bot_g.entry_placed` capacity telemetry
is verified. Causal depletion/reload can now be checked via
`scripts/bot_g_book_reload_signal.py --main-db`; the bot LXC container `14` realised Prime
entries showed refilled entries (`>1.1`) were `0/8` and
depleted/slight-drop entries were `2/5`. Treat this as a research veto
candidate, not a hard gate.

**2026-05-02 active-fleet read:** Longshot Prime is now the primary
engineering sprint, but still paper-only. The dashboard makes the distinction
explicit: `4c-8c` is the collection band, while only `4c-5c` has positive
signal evidence.

### P0 — Bot D Daily/Low-Lock-Up Subset

- [x] Keep Bot D as the first real-wallet candidate track if its daily subset
  clears lock-up, settlement, depth, and trimmed-ROI proof.
- [x] Split Bot D daily contracts from weekly contracts.
- [x] Report capital lock-up by hold time.
- [x] Reconcile or explain stale Bot D open paper positions and orders.
- [x] Report order-book depth/slippage at `$25` and `$50`.
- [ ] Apply Bot-A-shaped risk check: high hit rate plus negative trimmed ROI
  means archive/pause, not tune.
- [ ] Keep NWS override paper-only until override-tagged trades settle.
- [x] Surface Bot D readiness and lock-up blockers on the dashboard.
- [x] Capture Bot D order books so paper fills are measured from observed
  CLOB books.

**2026-05-01 production read:** Bot D remains priority for eventual real
wallet, but today's blocker is not bankroll. It has zero fills in the 24h
fast-ROI window and visible stale/open lock-up that must be separated from
fresh daily weather flow.

**2026-05-01 readiness read:** Bot D has `15` open paper orders
(`$321.33`), of which `13` are daily/low-lock-up and `2` are weekly. It also
has `8` stale orders and `3` stale open positions. Dashboard live-readiness is
therefore `NO` until stale paper state is reconciled and fresh daily fills are
observed.

**2026-05-01 daily-cleanup read:** stale paper state was cleaned: `8` expired
paper orders cancelled, `3` blank-condition orphan positions archived, and
`1` weekly-lock paper order cancelled. Bot D now has `6` open daily orders,
`3` open daily positions, `$130.00` open order notional, `$75.00` open
position cost, and `3` recent fills. First-wallet proof remains daily-only.

**2026-05-01 Phase 0/1 read:** readiness/dashboard now show forecast-entry
payload proof, model-vs-market probability samples, model timestamp buckets,
entry depth, and resolved FIFO daily P&L. the bot LXC container daily/low-lock-up ROI is
positive headline (`+61.23%`) but fails outlier adjustment
(`-31.32%` ex-largest-win), so no live proposal yet.

**2026-05-02 active-fleet read:** Weather Fade remains operational and is
still the first likely real-wallet candidate unless Longshot Prime proves
capacity and outlier-adjusted ROI first.

### P1 — Crowd Sensor Merge (legacy Bot F)

- [x] Add `core.crowd_signals` read-only accessors for Bot F cascade data.
- [x] Wire crowd pressure as a report-only field in Bot E/G/D decisions.
- [ ] After 7 days, test whether crowd pressure would have avoided
  losing E/G/D trades or confirmed winners.
- [ ] Only then consider a live veto/fade gate.

**2026-05-01 Phase 0/1 read:** fast-ROI reports legacy mirror-signal drift at
`1m`, `5m`, `30m`, and `6h`. the bot LXC container sampled `500` signals but measured `0`
horizons because matching book snapshots were absent; the next step is book
coverage, not execution.

**2026-05-02 active-fleet read:** legacy Bot F is archived as a standalone
bot. Its crowd/cascade outputs remain shared sensor infrastructure only.

### P2 — Bot B Background Moat

- [x] Stop halted Bot B from running scorer sweeps unless explicitly
  overridden.
- [ ] Keep scorer ownership/calibration work moving, but do not market Bot B
  as fast ROI.

## What I Need From the operator Later

Closed 2026-05-18: no direct action should be taken from this old to-do file.
Use the canonical open-question list and active operating model instead.

Needed before real-money changes:

1. Whether `$100` plumbing-live is allowed for execution validation.
2. Whether `$500-$1,000` ROI-live allocation is acceptable if Bot E/G/D earns
   it.
3. Preferred live candidate if Bot E and Bot G both pass.
