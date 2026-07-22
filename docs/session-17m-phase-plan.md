# Session 17m Phase Plan — Post-Bot-A Fleet Direction

**Date:** 2026-04-18
**Operator directive:** data collection, trades, metrics are top priority. Increase paper allowance where needed to gather actionable trades.
**Supersedes:** prior "kill Bot A" discussions in Session 17j meta-review.
**ADR:** ADR-033 (Bot A archival).

---

## Fleet state after this session

| Bot | State | Action window | Data focus |
|---|---|---|---|
| A | ARCHIVED (ADR-033) | — | Walk-forward data already captured (12,521 trades) |
| B | Halted | **Phase 2** | Ensemble scorer scaffold present; no live data until unhalt |
| C | Paper, no thesis | **Phase 1** | 1-sec Pyth bars already flowing; thesis + backtest next |
| D | Paper, entries halted, 11 open | Waiting | 11 positions resolving over 2-3 weeks — NO new config changes until resolution |
| E | Paper, OBI model falsified | **Phase 1** | 461 MB recorder DB already exists; rebuild predictor on existing data |
| F | Sensor | **Phase 1** | Cascade cron → `crowd_signals` table + Bot B ensemble E4 input |

---

## Phase 1 — this sprint (2026-04-18 → 2026-05-02)

Priority: **maximise actionable data per bot that can still hit a positive verdict.**

### P1.1 — Bot C thesis + backtest (2026-04-22 deadline, Pyth Pro expiry)

**Why first:** hard external deadline. Pyth Pro trial expires 2026-04-22. Either thesis ships, backtest runs, and decision is made by Monday — or Bot C archives automatically on cost grounds.

**Work:**
1. Write `docs/bot-c-thesis.md` — one page, one falsifiable claim, entry/exit rules spelled out.
2. Run backtest on existing 1-second Pyth bars (`core/pyth_models.PythBarPro`) against `markets.parquet` from the historical dataset already used for Bot A.
3. Must show positive net EV after 1.5-1.8% round-trip fees on ≥ 30 simulated trades.
4. If YES: commit thesis doc, continue Bot C paper with **elevated `BOT_C_BANKROLL_USD` = $500** (up from $50) to accelerate trade volume. Bot C holds for hours to 7 days, so 30 trades = ~1 week of paper data.
5. If NO: archive Bot C same-session using the Bot A ADR-033 pattern (env flag `BOT_C_ARCHIVED`, banner in `__init__.py`, systemd disable on LXC).

**Owner:** Claude Code — thesis doc is a single-session deliverable.
**Deliverable by:** 2026-04-22 end of day.

---

### P1.2 — Bot E E-2 replacement model + validation (2026-05-02 deadline)

**Why second:** operator-elevated priority (Bot E unarchived); recorder DB is 461 MB of ready-to-use calibration data; fastest hold time (minutes) means rapid paper feedback once deployed.

**Work:**
1. Add `scripts/bot_e_train_predictor.py`: load `data/bot_e_recorder.db`, extract OBI features (window × 3, depth asymmetry, CEX CVD, TTE, regime flag, realised vol), split 70/30 train/held-out, fit logistic regression or small GBDT.
2. Validation gate (must pass ALL):
   - Held-out Brier score ≤ 0.10.
   - Realised WR within ±5 percentage points of predicted WR per OBI-strength bucket (the bug in the linear model was predicting 96.5% and delivering 64.3% — this must close to ≤5pp).
   - At least 200 signals in held-out test set.
3. Replace `predicted_wr = 0.5 + |OBI|/2` in `bots/bot_e_btc_scalp/signal.py` with the trained model's output (pickle load at startup, guarded behind `BOT_E_USE_ML_PREDICTOR=true`).
4. If passes → paper with **elevated `BOT_E_BANKROLL_USD` = $500** (up from $100), $10 fixed trade, no Kelly. Run 2 weeks of paper with the new predictor to gather `≥ 300 trades` per ADR-022 gate.
5. If fails → per ADR-030 and the POC evidence, archive the trader (`BOT_E_ARCHIVED=true` pattern). Recorder continues indefinitely.

**Owner:** Claude Code (model build + validation). Operator: approve elevated bankroll.
**Deliverable by:** 2026-05-02.

**Data-collection note:** recorder DB already holds 4.6 hours of multi-market recordings. Running recorder through Phase 1 adds another 2 weeks of data = ~336 hours. If the ML model lives, that's the calibration sample; if it dies, it's dataset value for a future attempt.

---

### P1.3 — Bot F cascades cron + crowd_signals production (this week)

**Why third:** cheap, already scaffolded (Session 17i shipped `bots/bot_f/crowd_signals.py` + `scripts/detect_cascades.py`), just needs scheduled operation to start producing data.

**Work:**
1. Write `systemd/polymarket-bot-f-cascades.timer` + `.service` units.
2. Deploy to the bot LXC container; daily run emits `CrowdCascade` rows.
3. After 14 days: measure overlap between cascade flags and (a) Bot D entry candidates, (b) Bot B markets once unhalted. If cascades predict Bot D losses → wire as filter; if uncorrelated → archive the cascade output.
4. Bot F ADR-032 E4 estimator for Bot B ensemble: gated on Phase 2 Bot B work; scaffolded now, not wired.

**Owner:** Claude Code (systemd units + LXC deploy script) + operator (install timer).
**Deliverable by:** 2026-04-22 end of week; measurement period through 2026-05-06.

**Data-collection note:** local Bot F DB currently has 200 rejected signals (100% age-rejected). Cascade detection operates at the aggregate level, not the per-signal timing level — so the "too late to copy" problem doesn't invalidate cascade output. This is the right narrow role for Bot F.

---

### P1.4 — Bot D: passive observation, no tweaks

11 paper positions @ $834 cost basis. All resolve in ≤ 3 weeks. **No config changes until resolution sample is in.**

**Checkpoints:**
- 2026-05-02 (halfway): if ≥ 8 of 11 resolved and net realised edge < 0% after fees → archive early; don't wait for the full sample.
- 2026-05-31 (kill date): full sample decision per kill-dates.md criteria (net edge ≥ 2.5% on ≥ 15 resolutions).

**Data-collection note:** after the existing 11 resolve AND Bot D passes its kill gate, bankroll bumps to **$5,000** (already configured for paper headroom per bots/bot_d_weather/CLAUDE.md) and entries unhalt. Until then, measurement-over-tuning.

**Precondition:** ship Phase-B U-15 (Bot D fee-units fix) before computing net-edge verdict — current code over-states fees by factor 1/p.

---

## Phase 2 — next sprint (2026-05-03 → 2026-05-17)

Phase 2 is triggered when either (a) Phase 1 Bot C verdict is in, or (b) oraclemangle-ensemble-proposal verdict lands.

### P2.1 — Bot B E2 historical-baserate estimator + ECE validation

**Why Phase 2:** oraclemangle-ensemble-proposal verdict affects which codebase owns the E2/E3/E4 estimators. Building E2 locally now could duplicate work if the proposal lands with "migrate to oraclemangle" verdict.

**Work plan (when Phase 2 starts):**
1. Finalise ownership: oraclemangle or `bots/bot_b/scorer_ensemble/` here. Hard deadline 2026-04-22 for the verdict; if silent past that, default to building here.
2. Implement E2 historical-baserate: `bots/bot_b/scorer_ensemble/estimators/historical_baserate.py` already has Beta(2,2)-shrunk scaffold (ADR-029). Wire it to `bots/bot_b/scorer_ensemble/ensemble.py`.
3. Re-run calibration sweep on 2,870-market held-out (20%): Brier ≤ 0.06, calibration within 5pp per decile bucket.
4. If passes → 30 paper days with ≥ 15 filled trades. Bot B unhalts with **elevated `BOT_B_BANKROLL_GBP` = £500** (up from £200) to accelerate trade sample.
5. If fails → Bot B archives on the 2026-06-30 kill date.

**Blocker dependencies:**
- P1.1 (Bot C thesis) deliberately first — same thesis-rigour template needed here.
- M-04 (core SideEnum refactor) — not a hard blocker but would clean up BUY_YES/BUY_NO churn that Bot B touches too.

---

## Archived this session

- Bot A (ADR-033). Restoration path preserved per ADR.

## Not touched this session

- Polymarket V2 migration (OQ-034) — blocks any live graduation but no bot graduating in Phase 1.
- Dashboard overlap/archetype panels (Phase B from audit — U-09). Scheduled but not P1/P2.
- SideEnum refactor (M-04). Biggest cleanup but not blocking a specific bot's decision.

---

## Data-collection budget summary

After this session's Phase 1 actions:

| Bot | Paper bankroll (new) | Expected trades/week |
|---|---|---|
| A | $0 (archived) | 0 |
| B | £200 → £500 (Phase 2, post-unhalt) | 4-8 |
| C | $50 → $500 (Phase 1, if thesis passes) | 20-30 |
| D | current $5,000 (already elevated) | 3-5 (weather market cadence) |
| E | $100 → $500 (Phase 1, post-ML-validation) | 50-100 |
| F | sensor only | 6+ cascades/week |

Total weekly trade collection target after Phase 1: **~80-140/week**, up from ~20/week in current fleet (Bot D's halted + Bot E's questionable signals). This is the "actionable data" ramp the operator asked for.

---

## Open questions created this session

- OQ-035: does Bot C's 1-second Pyth bar history cover enough market-pair × time variety for a 30-trade backtest? If not, backtest waits for more historical data, pushing Bot C decision past the Pyth Pro expiry.
- OQ-036: when Bot F cascade cron deploys, does the daily cascade count justify keeping the daily poll of Hunter top-40 wallets, or should we drop to weekly? (Currently every 30 seconds.)

Add to `docs/open-questions.md` if they become live.
