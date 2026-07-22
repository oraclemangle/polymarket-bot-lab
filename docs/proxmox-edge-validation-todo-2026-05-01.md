# the homelab hypervisor Edge Validation To-Do

**Date:** 2026-05-01
**Status:** Superseded/closed 2026-05-18 by the active operating model,
later ADRs, and the profitability/ROI goal. Completed checklist items remain
as historical evidence; still-valid blockers live in `docs/open-questions.md`.
**Owner:** Claude.
**Purpose:** preserve the next validation steps if the session compacts or is
resumed by another model.

## Data Assets Confirmed

the bot LXC container has enough recorder data to validate the current edge hypotheses:

- `data/main.db`: orders, trades, events, and `5M+` book snapshots.
- `data/bot_e_recorder.db`: `19M+` Polymarket events, `56M+` CEX trades,
  `1.2M+` heartbeats, and `85k+` market rows.

The data is read-only for this work. No live wallet action is authorized.

## P0 — Bot G Prime Validation

Goal: prove or reject the `4c-5c` late-tail edge before any live discussion.

- [x] Run `scripts/bot_g_feature_analysis.py` on the bot LXC container scoped to
  `BOT_G_FEATURE_BOT_IDS=bot_g_prime`.
- [x] Preserve output under `docs/reports/`.
- [x] Split `4c-5c` from `5c-8c`; if the current script buckets too coarsely,
  patch it to expose exact `0.04-0.05` and `0.05-0.08` buckets.
- [x] Report all, ex-largest-win, and ex-largest-two-wins ROI.
- [x] Add V2 crypto fee stress for maker-entry, taker-entry, and mixed legs.
- [x] Estimate `$25` and `$50` capacity from recorded books.
- [x] Join against CEX tape where possible to split CEX-confirmed vs
  unconfirmed entries.
- [x] Add hourly Bot G paper-validation output to
  `scripts/fast_roi_report.py` and dashboard `/api/bot-g`: exact `4c-5c`,
  `5c-8c`, all `4c-8c`, ex-largest-win, ex-largest-two-wins, CEX split, and
  `$25`/`$50` capacity coverage.
- [x] Add forward Bot G entry capacity telemetry at entry limit, limit+1c,
  and limit+2c in `bot_g.entry_placed` payloads.
- [x] Deploy Bot G reporting/dashboard rollout to the bot LXC container and verify
  `/api/bot-g` plus hourly report output.
- [x] Validate the new `capacity_depth` field on a fresh post-deploy
  `bot_g.entry_placed` event after natural paper flow produces one.
- [x] Run or optimize `scripts/bot_g_book_reload_signal.py` to test whether
  cheap-side depth depletion/reload is causal and useful.
- [x] Add Bot G live-candidate reporting gate for trimmed ROI and `$25/$50`
  depth coverage at limit, limit+1c, and limit+2c.
- [x] Add Bot G tiny-live readiness surfaces: runbook, dashboard panel, and
  hourly report section. This is approval-gated prep only, not live
  authorization.
- [x] Apply Opus audit live-accounting fixes without reducing paper
  collection: live order status, live fill reconciliation, runtime-state
  telemetry, and live-only tiny caps.
- [x] Record the user-selected Bot G tiny-live wallet allocation as `$200`
  with `$5` fixed entries (`2.5%` of wallet), `$100` daily gross ceiling
  (`50%`), and `$50` max intended open stake (`25%`).
- [x] Operator decision: approve or reject Bot G tiny-live activation caps
  after ADR-073 gate status is reviewed. the operator approved ADR-078 on
  2026-05-02 with `20` entries/day, `$100` daily gross, `10` max open,
  `$200` wallet posture, and a separate `bot_g_prime_live` unit.
- [ ] Improve Bot G execution/capacity policy; current recorded depth only
  supported `$25` at the entry limit in `1/19` closed trades.
- [ ] Post-live decision rule: Bot G stays at `$5` fixed entries and `4c-5c`
  until OQ-063 clears live fill, slippage, reconciliation, and
  ex-largest-two ROI checks.

**2026-05-01 validation read:** Exact `4c-5c` is the only positive cohort
(`9` closed, `2` wins, `+$186.83`, `+489.5%` ROI). `5c-8c` is still dead
(`10` closed, `0` wins, `-100.0%`). CEX-confirmed entries were `0/3`.
Fee stress is not the blocker at low entry prices; capacity is.

**2026-05-01 Phase 0/1 follow-up:** Fresh post-deploy
`bot_g.entry_placed` at `2026-05-01 21:30:06 UTC` contains
`capacity_depth` with depth-by-tick fields, so the forward telemetry is now
verified. `scripts/bot_g_book_reload_signal.py` now has a fast
`--main-db` mode that reads causal depletion telemetry already captured at
entry and labels it with FIFO outcomes, avoiding a full recorder scan. the bot LXC container run on `14` realised Prime entries: refilled entries (`>1.1`) were `0/8`;
depleted/slight-drop buckets were `2/5`. This is promising as a veto/reload
feature, but sample size is too small for a hard gate.

**2026-05-02 capacity-gate follow-up:** Added the Bot G live-candidate
reporting gate from ADR-073 and capacity simulation visibility for `$25/$50`
at entry limit, limit+1c, and limit+2c. The policy is reporting-only and does
not alter Bot G paper order behavior. Remaining action: use the next paper
settlements to see whether the gate is blocked by trimmed ROI, depth, or
sample size.

**2026-05-02 production capacity-gate read:** `/api/bot-g` gate status is
`blocked_by_trimmed_roi`; failed checks are minimum `4c-5c` sample,
ex-largest-two ROI, `$25` at-limit capacity, and `$50` limit+2c capacity.
Fast-ROI read: `4c-5c` `12` closed / `2` wins / `+359.4%` ROI,
ex-largest-win `+127.4%`, ex-largest-two `-100.0%`, `$25` at-limit depth
`0/12`; all `4c-8c` `31` closed / `4` wins / `+142.9%` ROI, ex-largest-two
`-24.0%`, `$25` at-limit depth `1/31`.

**2026-05-02 observational-label follow-up:** Added paper-only capacity labels
and depletion/reload labels to Bot G reports and dashboard. Production read:
`toy_fill_only` has `30` closed / `4` wins / `+152.6%` ROI but ex-largest-two
`-20.7%`; the only `sizeable_at_limit` sample lost `-100.0%`. The current
tape says the edge is still concentrated in thin books, so execution policy
must remain a research/reporting task until more sizeable samples exist.

**2026-05-02 tiny-live prep follow-up:** Added ADR-074 and
`docs/bot-g-tiny-live-runbook-2026-05-02.md`. `/api/bot-g`, the dashboard,
and the hourly fast-ROI report now expose a tiny-live readiness plan with
proposed `$5` starting size, `10` entries/day, `$50` daily gross notional, and
`5` max open positions. This does not change Bot G behavior or authorize live
activation; OQ-062 blocks any env, wallet, or real-money order change until
the operator explicitly approves.

**2026-05-02 Opus audit follow-up:** Added ADR-075. Fixed Bot G live
accounting/readiness gaps while preserving paper collection behavior: live
orders persist with live status instead of hardcoded `PAPER_OPEN`, live mode
polls `Portfolio.reconcile_live_fills()`, the trader emits
`bot_g.runtime_state`, the dashboard/report show the three-flag posture
(`BOT_G_ENV`, `BOT_G_DRY_RUN`, `POLYMARKET_ENV`), and live-only tiny caps are
code-visible without lowering paper daily entries.

**2026-05-02 wallet-sizing follow-up:** the operator selected `$200` as the Bot G
tiny-live wallet allocation. Added ADR-076 and
`docs/bot-g-tiny-live-activation-packet-2026-05-02.md`; the proposed live
packet remains fixed `$5` entries.

**2026-05-02 cap-update follow-up:** the operator updated the prepared Bot G
tiny-live cap packet to `$100` daily gross notional and `10` max open
positions while keeping `$200` wallet, `$5` entries, and `10` entries/day.
ADR-077 records the updated cap packet. This changes reporting/prep only and
does not activate live mode or reduce paper collection.

**2026-05-02 live-approval follow-up:** the operator explicitly approved Bot G Prime
live activation. ADR-078 supersedes ADR-077: add
`polymarket-bot-g-prime-live.service` as `bot_g_prime_live` on `4c-5c`,
change the daily entry cap to `20`, keep `$100` gross notional and `10` max
open positions, and leave `polymarket-bot-g-prime.service` running as the
`4c-8c` paper shadow. Jackpot/scalp stay disabled because their archived
cohorts were negative/non-candidate and would add multi-unit live risk.

## P0 — Bot D Weather Validation

Goal: validate Grok's station-exact/model-lag thesis against our paper orders
and current weather data.

- [x] Run the current Bot D readiness report on the bot LXC container after the daily-only
  cleanup.
- [x] Report fresh daily fills, open daily positions, stale state, and lock-up.
- [x] Add a station/source coverage table for active Bot D cities.
- [x] Begin station forecast-entry capture by logging settlement station,
  source, rounding, forecast source, fetch timestamp, and model timestamp
  fields into `bot_d.forecast_entry` payloads.
- [x] Deploy Bot D station coverage/reporting rollout to the bot LXC container and verify
  dashboard station coverage plus fresh post-restart `bot_d.nws_veto` payload
  station/source/forecast fields.
- [x] Validate the new station forecast-entry capture on the bot LXC container production
  events after deployment.
- [x] Convert forecasts into bucket probabilities; point forecasts alone are
  not enough.
- [x] Join forecast probability vs Polymarket bucket price at entry time.
- [x] Compare post-model-update windows vs non-update windows.
- [x] Report order-book depth/slippage at `$25` and `$50`.
- [x] Add Open-Meteo 429 cooldown/cache/pacing so station forecast capture
  does not hammer the upstream API during rate-limit windows.
- [ ] Decision rule: Bot D remains first-wallet candidate only if daily-only
  resolved P&L and station-exact edge survive slippage/depth checks.

**2026-05-01 Phase 0/1 follow-up:** `/api/bot-d` now exposes forecast-entry
payload validation, model-vs-market probability samples, model timestamp
buckets, `$25`/`$50` entry-depth coverage, and FIFO resolved P&L for the
daily/low-lock-up cohort. Fresh production read: `15` forecast entries,
latest entry has station and forecast fields, average model-market gap
`0.2608`, depth samples `14`, average at-limit depth `$16.91`, `$25`
coverage `2/14`, `$50` coverage `1/14`. Daily/low-lock-up resolved FIFO P&L
is `56` closed / `26` wins / `+61.23%` ROI, but ex-largest-win ROI is
`-31.32%` and ex-largest-two ROI is `-33.86%`, so Bot D remains not
live-ready.

**2026-05-02 operational follow-up:** Bot D weather fetches now respect
Open-Meteo `Retry-After` on HTTP 429, keep a short in-process forecast cache,
use `max_connections=5`, and pace city requests. Deployed to the bot LXC container and
restarted with `BOT_D_ENV=paper`; post-restart scans completed with `0`
orders. This is reliability work for the paper proof, not a live-readiness
upgrade.

## P0 — Dashboard Reliability

Goal: keep the operator dashboard usable during large SQLite/WAL read edge
cases without weakening read-only trading discipline.

- [x] Diagnose `/api/overview` HTTP 500 on the bot LXC container.
- [x] Make the event-severity card fail soft instead of taking down the
  overview endpoint.
- [x] Keep dashboard SQLite temp query state in memory and update the
  dashboard systemd sandbox for SQLite sidecar/temp-file compatibility while
  preserving application-level `mode=ro` database access.
- [x] Verify `/`, `/api/overview`, `/api/bot-d`, and `/api/bot-g` return
  HTTP 200 on the bot LXC container.

**2026-05-02 read:** The 500 came from
`_event_severity_counts()` raising `sqlite3.OperationalError: disk I/O error`
inside the dashboard service sandbox. The final deployed fix returns real
7-day severity counts (`info=55931`, `warn=9118`, `kill=25412` at
`2026-05-02T05:06:51Z`) and leaves Bot G paper-only:
`collection_band=4c-8c`, `positive_signal_band=4c-5c`,
`live_ready=false`.

**2026-05-02 revamp follow-up:** Dashboard active surfaces now follow
ADR-071 and `docs/active-operating-model-2026-05-02.md`. Bot A and legacy
Bot F are removed from active dashboard/API tabs; archived Bot A/F database
rows are filtered out of aggregate orders, positions, and trade metrics by
default.

**2026-05-02 Bot B parking follow-up:** Bot B and Bot B Shadow now follow
ADR-072: parked from active dashboard/API/reboot-readiness surfaces while code
and OQ-060 spin-off planning remain intact. The active dashboard target is the
four monitored bots: Longshot Prime, Weather Fade, Pyth Directional, and Maker
Flow.

## P1 — Bot E Maker-Fill Quality

Goal: validate whether maker fills are useful or toxic under CLOB V2.

- [ ] Re-run `scripts/bot_e_cancel_autopsy.py` on the bot LXC container with current book
  coverage.
- [ ] Report adverse movement after 30s, 60s, and 300s.
- [x] Add `$25` and `$50` depth simulation.
- [ ] Track maker/taker economics separately; do not count rewards as edge
  until receipts are reconciled.
- [ ] Decision rule: no Bot E scaling while adverse movement dominates.

**2026-05-01 Phase 0/1 follow-up:** `scripts/bot_e_cancel_autopsy.py` now
reports `$25`/`$50` depth coverage for each TTL/offset scenario. the bot LXC container
read saw `20` recent Bot E orders; the first scenarios filled `14/20` and
had `$25` coverage `12/14`, `$50` coverage `9/14`. This improves capacity
visibility but does not clear the toxic-fill/adverse-selection gate.

## P1 — Crowd Sensor Feature Extraction (legacy Bot F)

Goal: test anti-crowd edge rather than direct copying.

- [ ] Confirm whether Bot F has fresh cascade rows.
- [ ] For each cascade, measure 1m, 5m, 30m, and 6h forward drift.
- [ ] Test fade, avoid, and confirm variants against Bot D/G/E decisions.
- [x] Remove legacy Bot F as an active dashboard/API surface while retaining
  crowd/cascade data as shared sensor infrastructure.
- [ ] Decision rule: legacy Bot F remains sensor-only unless a paper cohort
  shows positive forward EV after spread/fees and a new ADR reactivates it.

**2026-05-01 Phase 0/1 follow-up:** `scripts/fast_roi_report.py` now includes
Bot F mirror-signal drift scaffolding at `1m`, `5m`, `30m`, and `6h` using
main-db book mids. the bot LXC container sampled `500` recent mirror signals but measured
`0` horizons because matching book snapshots were unavailable, so legacy
Bot F remains sensor-only and needs better book coverage before drift claims.

## P1 — LP Tool Extraction

Goal: use `lihanyu81/polymarket_lp_tool` only as execution reference.

- [ ] Extract post-only cancel/replace safety patterns.
- [ ] Add reward scoring visibility to reports before any reward-aware sizing.
- [ ] Add fill-risk telemetry where it improves Bot G/E decisions.
- [ ] Add Telegram alert hooks for halt, replace failure, and toxic-fill
  warnings.
- [ ] Do not import the passive LP strategy wholesale.

## Session Closeout Requirements

- [x] Update `MEMORY.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `docs/open-questions.md` if new empirical gates are added.
- [x] Commit and push to `main`.
