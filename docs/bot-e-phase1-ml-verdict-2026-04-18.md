# Bot E Phase 1 ML Verdict — 2026-04-18

**Context:** Phase 1 P1.2 per `docs/session-17m-phase-plan.md` called for an E-2 ML replacement model: replace `predicted_wr = 0.5 + |OBI|/2` in `bots/bot_e_btc_scalp/signal.py` with a logistic regression fit on `data/bot_e_recorder.db`. Validation gate: Brier ≤ 0.10, predicted WR within ±5pp of realised per bucket, ≥ 200 held-out signals. Deadline 2026-05-02.

**Actual deliverable:** training ran on the bot LXC container at 2026-04-18 22:15 UTC against 2.5GB recorder DB (60 hours of data, 1.25M pm_events, 12.2M cex_trades, 16.7k markets observed). The pre-existing `scripts/bot_e_fit_model.py` (Session 17g, 491 lines) was used after a 2-line API-mismatch fix (`detect_resolutions_via_cex` missing `db_start_ms`; `attach_outcomes` missing `sub_to_meta`). Two horizons trained; full four-horizon sweep running in background.

## Results (5-10min horizon, representative)

```json
{
  "train_n": 143,
  "val_n": 30,
  "heldout_n": 32,
  "heldout_ece": 0.025,
  "heldout_brier": 0.243,
  "heldout_calibration_slope": 7.568,
  "passed_acceptance": false,
  "notes": "heldout_n=32 below 45; brier=0.243 above 0.22; slope=7.568 outside [0.8, 1.2]"
}
```

| Metric | Threshold | Actual | Pass? |
|---|---|---|---|
| Held-out sample size | ≥ 45 | 32 | **FAIL** |
| Brier score | ≤ 0.22 | 0.243 | **FAIL** |
| Calibration slope | [0.8, 1.2] | 7.568 | **FAIL** (extreme) |
| ECE | ≤ 0.15 | 0.025 | pass (but see note) |

ECE passes in isolation but is not trustworthy alongside the 7.57 calibration slope and 0.243 Brier — likely a binning artefact on 32 samples rather than real calibration.

## Verdict

**The ML replacement cannot be validated on current data. Phase 1 P1.2 fails its acceptance gate.**

**Root causes (ranked by evidence strength):**

1. **Sample insufficiency — held-out 32 < min 45.** 205 total resolved signals over 60 hours = ~82/day. At the acceptance threshold (45 × 0.15 = 300 trades), current ingest rate gets us there in ~15 days of additional recording. The PM-resolution detection (`detect_resolutions_via_cex`) only labels markets whose CEX reference price resolves within the recorder window; many markets end after the window and drop out.

2. **Calibration slope 7.57 is a decisive signal, not a sample-size artefact.** A slope of 1.0 is perfect; 7.57 means the model is absurdly overconfident — predicting probabilities ~7× more extreme than reality. Even with 10× more data, a slope this far off suggests the feature set does not actually predict outcome in a calibrated way. This echoes the ADR-030 POC finding: the structural issue (market-efficient equilibrium where spread exists → no flow) wasn't a calibration bug, it was a *missing edge*.

3. **Horizon-sweep implementation is broken.** The two completed horizons (`5-10min` and `30s-60s`) produced **byte-identical metrics**. Per `scripts/bot_e_fit_model.py:_extract_training_matrix`, the script warns "horizon sweep is a future enhancement" and falls back to the 5-10min extraction regardless of the requested horizon. Shipping real horizon sweep is pre-P-1.2-retry work.

## Recommendation (for operator decision)

Three paths, in order of escalation:

### Path 1 — Accept Phase 1 P1.2 defer, keep recorder running, retry 2026-05-02

- Cost: zero code work this session. Recorder is already running and producing data.
- Gives: 14 more days of data = ~3× the current sample. Retry same acceptance gate.
- Risk: the calibration slope of 7.57 suggests a feature-level problem, not a sample problem. More data may fail the same gates.

### Path 2 — Fix the horizon-sweep bug + widen features, then retry

- Cost: 1–2 day session. Fix `_extract_training_matrix` to actually re-run signal extraction per horizon; add features the POC flagged as missing (e.g. queue-imbalance, signed aggressor, CEX CVD at multiple windows).
- Gives: real horizon comparison + chance to find a predictive feature set.
- Risk: same as Path 1 plus the risk that the underlying edge truly isn't there (ADR-030 structural finding).

### Path 3 — Re-archive Bot E per ADR-030; keep recorder as dataset asset

- Cost: ADR-035 + env guard (ADR-033/034 pattern). Recorder continues.
- Gives: compute reclaimed, no further dev time on a structurally-questioned strategy.
- Risk: if a future operator wants to resume, they inherit 3+ weeks of unexamined recorder data.

**Default recommendation for this session: Path 1 (defer + keep recording).**

Rationale: operator specifically said "Bot E is no longer archived" and emphasised data collection. Re-archiving (Path 3) contradicts that instruction. Path 2 is speculative feature engineering — more honest to let the data accumulate first and see if the structural issue is truly determinative. Path 1 is the cheapest honest waypoint.

**Action items if Path 1:**
1. Do nothing to the trader (it's paper-mode, low-stakes).
2. Keep recorder running (already deployed).
3. Calendar reminder 2026-05-02: retry `scripts/bot_e_fit_model.py --horizon-sweep` with 3–5× the data. Also fix horizon-sweep implementation bug before the retry.
4. If 2026-05-02 retry also fails the same gates, escalate to Path 3 (re-archive).

## What this session shipped

- Two API bugs in `scripts/bot_e_fit_model.py` fixed (`db_start_ms`, `sub_to_meta`).
- 2 of 4 horizons trained; outputs persisted with `passed_acceptance=false` via `--force-write`. Artifacts in `/home/bot/polymarket-bot/data/bot_e_models/`.
- This verdict doc.
- **Not shipped:** the ML-predictor wiring in `signal.py` (no model passes acceptance).
- **Not shipped:** `BOT_E_USE_ML_PREDICTOR` env flag (no model to guard).

## Open questions created

- **OQ-035**: fix `_extract_training_matrix` so `--horizon-sweep` actually varies the extraction windows. Owner: next Phase 1 session if Path 1 retry is attempted. Target: 2026-05-02.
- **OQ-036**: investigate whether the 7.57 calibration slope is feature-set noise or a structural "no edge" finding. May require a holdout of just `obi_30s` + `obi_60s` vs a richer feature set to see if simpler models calibrate better.

## Appendix: what the trainer actually consumed

- Recorder DB: `data/bot_e_recorder.db` (2.5GB, 60 hours 2026-04-16 02:34 → 2026-04-18 15:18 UTC).
- Markets: 16,741 observed across 60 hours.
- Candidate signals: 205 total (143 train + 30 val + 32 heldout) after filtering on OBI threshold + regime gate + market-resolution detection.
- Features: 16 (obi_30s/60s/120s/300s, depth_log_ratio, cex_cvd_signed_2m, vol_5m, mid_distance_50c, tte_bucket_3_5/5_7/7_10/10_15, regime_trend_bps, symbol_btc/eth/sol).
- Model kind: logistic (L2 regularised per `scripts/bot_e_fit_model.py`).
- Label: `outcome_yes_won` from CEX reference-price resolution.
