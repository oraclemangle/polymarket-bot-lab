# Bot E Fill-Conditioned Replay Plan — 2026-05-03

**Status:** Phase 3 complete for the first 24h copied-snapshot run.
**Scope:** Research and read-only analysis only. No Bot E runtime settings,
thresholds, services, sizing, or live-money posture change in this plan.

## Goal

Determine whether Maker Flow (Bot E) has a fill-conditioned, transferable
edge, or whether the strategy is only profitable on paper because the
unfilled/toxic-fill denominator is missing.

The answer must separate:

1. Signal edge: all eligible OBI/CEX/depth signals, filled or not.
2. Execution edge: orders that would realistically fill under maker-only
   constraints.
3. Fill toxicity: whether fills are disproportionately followed by adverse
   short-horizon midpoint movement.
4. Model edge: whether pre-fill features improve calibrated outcome
   prediction versus market-price and simple OBI baselines.

## Phase To-Do List

### Phase 0 — Discovery and Guardrails

**Status:** Complete on 2026-05-03.

- Inventory the existing Bot E ADR/OQ constraints.
- Inventory existing replay, autopsy, model, feature, and recorder tooling.
- Identify what can be reused versus what is prototype-only.
- Define hard gates that block any future tuning proposal.
- Confirm current-production data access constraints without changing
  services or touching order paths.

### Phase 1 — Build the Replay Dataset

**Status:** Complete on 2026-05-03.

- Work from copied DB files, or from strict bounded windows. Do not run
  unbounded replay queries against the live recorder DB.
- Produce one row per signal/order candidate with the full denominator:
  signal, skips, rejection reason, placement, cancel, no-fill, fill, fill
  delay, depth, adverse movement, and resolved outcome.
- Reuse `scripts/bot_e_calibration_spike.py` for recorder signal replay,
  market metadata, CEX labels, TTE buckets, and existing calibration stats.
- Reuse `scripts/bot_e_cancel_autopsy.py` for actual paper-order/books
  fillability and adverse-movement measurement.
- Include both rows that filled and rows that did not fill. Fill-conditioned
  EV without the no-fill denominator is not a valid strategy proof.

**Shipped:** `scripts/bot_e_fill_conditioned_replay.py` plus fixture coverage
in `tests/test_bot_e_fill_conditioned_replay.py`.

Phase 1 emits bounded, read-only replay rows from recorder data and optional
`main.db` paper-order data. It includes replay-signal rows and actual
`main_order` denominator rows, uses SQLite read-only URI connections for input
DBs, requires explicit time bounds or lookback, warms up OBI replay without
emitting pre-window signals, and keeps depth/adverse/outcome evidence bounded
inside the requested window. It does not alter Bot E runtime behavior.

### Phase 2 — Maker Fill Realism

**Status:** Complete for first 24h copied-snapshot run on 2026-05-03.

- Compare fill scenarios: observed paper books, conservative queue model,
  optimistic last-trade ceiling.
- Report fill rate by TTL, maker offset, TTE bucket, depth bucket, symbol,
  and CEX regime.
- Treat the current `simulate_maker_fills` last-trade method as an optimistic
  ceiling because it ignores queue position.
- Exclude recorder-quality gaps and unreliable windows before computing
  graduation metrics.

**Shipped:** `docs/reports/bot-e-phase2-fill-replay-2026-05-03.md`.

The first Phase 2 run used copied 24h slices from the bot LXC container, not the live
production DBs. It produced `270` denominator rows: `241` optimistic
`replay_signal` rows and `29` actual `main_order` rows. Actual Bot E paper
orders filled `15/29` (`51.7%`) but had 30s adverse movement of `9/14`
(`64.3%`), above the existing 60% toxicity stop line. Optimistic replay
signals looked less toxic (`52/120`, `43.3%` 30s adverse), so the last-trade
ceiling cannot be used alone for tuning.

### Phase 3 — Toxicity and EV Report

**Status:** Complete for first 24h copied-snapshot run on 2026-05-03.

- Report post-fill adverse movement at 30s, 60s, and 300s.
- Report settlement P&L and expected value after Polymarket fees, realistic
  slippage, and cancelled/no-fill opportunity cost.
- Split signal-only EV from fill-conditioned EV.
- Include missed-winner analysis: profitable signals that never filled versus
  filled orders that moved against the bot.

**Shipped:** `docs/reports/bot-e-phase3-ev-2026-05-03.md`.

The first Phase 3 run labels `16/29` actual paper orders and `8/15` actual
fills. Actual labelled fills produced `-0.55` P&L/share on `5.55` cost basis
(`-9.9%` ROI) despite `62.5%` WR. Optimistic replay fills produced only
`+0.57` P&L/share on `59.43` cost basis (`+1.0%` ROI) before costs; a flat
`1c`/share execution haircut turns replay negative. Actual unfilled labelled
orders missed `7` winners and avoided `1` loser. Actual 30s-adverse labelled
fills were `0%` WR and `-100%` ROI. This packet does not support any Bot E
threshold, offset, TTL, sizing, or runtime change.

**72h follow-up shipped:** `docs/reports/bot-e-phase3-72h-ev-2026-05-03.md`.

The 72h packet produced `807` denominator rows: `737` optimistic replay
signals and `70` actual paper orders. Outcome coverage was `721/807` rows and
`377/419` filled rows. Actual labelled fills produced `-2.189` P&L/share on
`17.189` cost basis (`-12.7%` ROI) before costs. Optimistic replay fills
produced only `+2.082` P&L/share on `174.918` cost basis (`+1.2%` ROI) before
costs and turned negative with a flat `1c`/share haircut. Actual unfilled
labelled orders missed `19` winners and avoided only `3` losers. The 24h
packet's apparently interesting `75c+` actual bucket collapsed to `+1.0%`
before costs and negative after a `1c`/share haircut.

### Phase 4 — Predictive Edge Test

**Status:** Pending Phase 1/2 evidence.

- Use the canonical feature schema in `bots/bot_e_btc_scalp/features.py`.
- Run chronological train/validation/test splits only.
- Compare against simple baselines: market mid, OBI-only, and CEX-flow-only.
- Keep model tests offline; do not wire any model into Bot E runtime.

### Phase 5 — Decision Packet

**Status:** Pending Phase 3/4.

Produce one of four outcomes:

1. **Continue recorder-only:** data quality/sample still insufficient.
2. **Narrow paper experiment:** specific bucket has positive fill-conditioned
   EV and toxicity below gate.
3. **Retire active tuning:** fill-conditioned EV remains negative or toxic.
4. **Request ADR for a change:** only if current data supports a bounded
   paper-only threshold/execution/model change under ADR-058.

### Phase 6 — Verification and Closeout

**Status:** Pending implementation.

- Add a small fixture test for signal to fill to adverse movement to outcome.
- Verify no future leak in feature extraction.
- Verify BUY_NO label inversion if BUY_NO enters the replay path.
- Update `MEMORY.md`, `CHANGELOG.md`, and `docs/open-questions.md`.
- Run the repo secret scan before any commit or deployment discussion.

## Hard Gates

Bot E remains paper-only unless a later ADR explicitly says otherwise.

The current maker-flow method is considered flawed for live-transfer purposes
if any of these hold out of sample:

- Fill-conditioned net EV is less than or equal to zero after fees and
  realistic execution assumptions.
- Post-fill adverse rate is at or above `60%`.
- Realistic fill rate is below `30%`.
- A winning signal bucket only wins in the optimistic last-trade fill model,
  not in observed-book or conservative-queue models.
- The apparent edge disappears after excluding recorder gaps, dropped-event
  windows, or stale-market windows.

A predictive model is not a runtime candidate unless it also clears the
existing model gates:

- Held-out sample is large enough for the bucket being claimed.
- Brier score and ECE beat the baseline, not just an absolute threshold.
- Calibration slope stays near 1.0.
- Chronological holdout performance is stable across market regimes.

Maker rebates must not be the core edge. Rebates can be reported as a
separate sensitivity line, but the base case should stand without them.

## Phase 0 Findings

### Current Status

Maker Flow (Bot E) is operational in paper mode and lower priority under the
active operating model. ADR-037 un-archives Bot E for paper data collection
only; Bot E is not a live-money candidate without a new ADR.

### Binding Constraints

- ADR-022 requires recorder-first validation and positive EV after fees,
  slippage, latency, and bucketed out-of-sample checks.
- ADR-023 requires maker-only paper calibration for transferability.
- ADR-026 requires realistic maker-fill simulation plus adverse-selection
  measurement.
- ADR-027 requires TTE, CEX CVD, and depth accounting.
- ADR-049 requires excluding unreliable recorder intervals from calibration.
- ADR-057 rejects heavyweight Kronos complexity for Bot E.
- ADR-058 blocks any threshold, model, sizing, execution, or graduation change
  until a fresh validation packet exists.
- ADR-059 allows paper-only execution loosening already shipped, but further
  loosening or crossing/taker behavior needs a new ADR.

OQ-048 is the active umbrella question for this work. A new OQ number is not
needed unless the replay becomes independent of OQ-048.

### Reusable Tooling

- `scripts/bot_e_calibration_spike.py`: best base for recorder replay,
  CEX-derived labels, maker-fill simulation, adverse-selection stats, and
  pass/fail gates.
- `scripts/bot_e_cancel_autopsy.py`: best base for fill-conditioned analysis
  against actual paper orders and stored books in `main.db`.
- `scripts/bot_e_extract_features.py`: reusable feature-context construction,
  but not safe for unbounded live-DB runs.
- `scripts/bot_e_fit_model.py`: reusable model metrics, chronological split,
  and current model acceptance gates.
- `bots/bot_e_btc_scalp/features.py`: canonical offline feature schema.
- `bots/bot_e_recorder/schema.py`: canonical recorder tape schema.

### Known Gaps

- `core/backtest_bot_e.py` is prototype-grade for this job; it contains useful
  concepts but is not the Phase 1 base.
- The current last-trade maker-fill simulation is optimistic because it
  ignores queue position.
- Replay and adverse-selection paths still need a unified fill-evidence layer.
- Feature extraction/model fitting can load too much CEX history unless
  bounded by time window or copied DB.
- There is no single fixture test covering signal, fill, feature, adverse
  movement, and final outcome together.
- Read-only production DB inventory over SSH can hang when queries touch large
  recorder/main SQLite files. Phase 1 should use copied DB snapshots or strict
  bounded queries.

## Next Action

Prepare a decision packet for an ADR to retire active Bot E tuning and keep
only recorder/data reuse, unless the operator wants one final 7d packet for closure.
No Bot E strategy change is authorized by the 24h or 72h evidence packets.
