# Bot E Model Replacement Plan — From Linear Proxy to Fit Model

**Date:** 2026-04-17 (Session 17g execution).
**Owner:** Claude proposes; model fit + calibration run requires recorder DB on the bot LXC container.
**Objective:** replace `predicted_wr = 0.5 + |OBI|/2` with a model fit on recorded signals. The current formula is systematically overconfident at every strength bucket; the data says the model is wrong, not the sample size.

---

## The calibration evidence (why this is P0)

From `data/bot_e_calibration.json` (2026-04-17 09:06 UTC, 4.6h of recorder data):

| OBI bucket | N | Predicted WR | Realised WR | ECE |
|---|---|---|---|---|
| 0.20-0.30 | 5 | 0.632 | 0.200 | 0.432 |
| 0.40-0.50 | 1 | 0.743 | 0.000 | 0.743 |
| 0.50-0.65 | 2 | 0.790 | 0.500 | 0.290 |
| 0.65+ | 14 | **0.965** | **0.643** | 0.322 |

Overall: WR 0.500 (coin flip) on 22 signals. Weighted ECE 0.351 against a 0.10 threshold.

**The pattern is not noise.** Every bucket is overconfident in the same direction. 200 more samples will give you the same wrong answer with tighter bars. The formula `0.5 + |OBI|/2` is a straight-line proxy; the data is saying the relationship between OBI and outcome is either non-monotonic, horizon-dependent in a way we haven't captured, or simply not load-bearing at the 5-10min window.

---

## Replacement model specification

### Model class

Start with **logistic regression with L2 regularization**. Reasons:
- Interpretable coefficients (we can see which features matter).
- Minimal hyperparameters (less overfit risk on small N).
- Probabilistic output is natively calibrated-ish.
- Baseline before graduating to GBDT if coefficients say the relationship is non-linear.

Graduate to **gradient-boosted decision trees** (LightGBM, `num_leaves=7`, `min_data_in_leaf=20`) only if logistic regression's calibration curve shows obvious non-linearities after 200+ signals accumulated.

### Feature set (first pass)

Per `bots/bot_e_btc_scalp/CLAUDE.md` E-3:

1. **OBI at multiple windows** — rolling imbalance at 30s, 60s, 120s, 300s. Current code uses 120s only.
2. **Depth asymmetry** — notional at best-bid vs notional at best-ask, log ratio.
3. **CEX CVD (signed)** — Binance aggressor flow over last 2 minutes. Already wired in Phase 5; elevate to model feature, not just a gate.
4. **Time-to-expiry (bucketed)** — `tte_3-5`, `tte_5-7`, `tte_7-10`, `tte_10-15`. Already stratified; feed as one-hot.
5. **Regime label** — basis-points-normalized trend (already in code, currently a hard gate; feed as continuous feature).
6. **Realized volatility** — 5-min stddev of CEX trades.
7. **Polymarket mid distance from 50¢** — `abs(mid - 0.5)`; fee-peak proximity.
8. **Symbol** — BTC / ETH / SOL one-hot (the existing calibration shows BTC 0.143 WR vs ETH 0.692 WR on n=7/13; the symbol effect may be real).

### Train / test split

- **Chronological split.** First 70% of recorded signals → train, next 15% → validation, last 15% → test. Never random-shuffle time-series.
- **Never use look-ahead features.** Every feature computed strictly from data available at signal generation time. Paranoid review.

### Acceptance criteria (before writing the GO-file)

On held-out 15%:
- **ECE ≤ 0.15** (current is 0.351). Target 0.10 but 0.15 is the gate for GO-file.
- **Brier ≤ 0.22** (coin-flip Brier = 0.25; anything below beats chance).
- **Calibration curve slope 0.8-1.2** per decile bucket (no bucket over-confident by >20 points).
- **N(held-out) ≥ 45** (so the measurement itself has signal; current 22 total is below this threshold on any split).

### Anti-cheating rules

- **No parameter tuning on the held-out set.** Pick hyperparameters on the validation set only. Run held-out once at the end.
- **No retroactive feature addition.** If held-out fails, add feature, re-run entire train/val/test pipeline from scratch. Document every iteration in `docs/bot-e-model-iterations.md`.
- **Run the regime-skip gate on the SAME rule as live.** Don't evaluate on all signals if live will only trade non-choppy; stratify by regime.

---

## Horizon sweep (E-4)

If logistic regression on the default 5-10min window fails the acceptance criteria, don't escalate to GBDT yet. First try alternative horizons:

1. **30-60s forward:** shorter horizon, more samples per market. Requires re-extracting labels from recorder data.
2. **60-180s forward:** intermediate.
3. **Mean-reversion framing:** predict `mid reverts toward 0.5 by T+60s`, not `direction(mid) at T+300s`. Different target, same features.

Each horizon gets a full train/val/test pipeline. The winning horizon is the one with the best held-out ECE + Brier, assuming sample size is adequate.

---

## Implementation sequence

### Script 1: `scripts/bot_e_extract_features.py`

Reads recorder DB on the bot LXC container (`data/bot_e_recorder.db`), emits CSV:
```
signal_id, subscription_id, tte_bucket, regime, obi_30s, obi_60s, obi_120s, obi_300s,
depth_log_ratio, cex_cvd_2m, vol_5m, mid_distance_50c, symbol, outcome
```

One row per qualifying signal (currently: 22 rows for 4.6h of data; expected growth ~5-10x/day if the recorder stays up).

### Script 2: `scripts/bot_e_fit_model.py`

Inputs: CSV from Script 1, horizon spec.
Outputs:
- Trained model pickle (`data/bot_e_model_<horizon>_<date>.pkl`).
- Calibration report (`docs/bot-e-model-calibration-<date>.md`).
- Feature importance table.
- Held-out decision: GO / NO-GO.

Refuses to write a GO decision unless acceptance criteria met.

### Script 3: Integration

`bots/bot_e_btc_scalp/model.py` (new) loads the pickle at startup and exposes:
```python
class Predictor:
    def predict_p_up(self, features: dict) -> float: ...
```

Replaces the linear proxy in `bot_e_calibration_spike.py` AND in `bots/bot_e_btc_scalp/__main__.py`'s decision path.

---

## Extraction of __main__.py (E-5)

Secondary to model replacement but same session if possible. `bots/bot_e_btc_scalp/__main__.py` (44KB) is unreviewable. Proposed split:

- `bots/bot_e_btc_scalp/scanner.py` — subscription discovery, book snapshot loop.
- `bots/bot_e_btc_scalp/decide.py` — feature extraction + `Predictor.predict_p_up` + size/price decision.
- `bots/bot_e_btc_scalp/halts.py` — consecutive-loss halt, adverse-selection halt, feed-freshness halt, emergency halt composition.
- `bots/bot_e_btc_scalp/__main__.py` — orchestration only (≤ 15KB).

---

## Files touched

**New:**
- `scripts/bot_e_extract_features.py`
- `scripts/bot_e_fit_model.py`
- `bots/bot_e_btc_scalp/model.py`
- `bots/bot_e_btc_scalp/features.py`
- `docs/bot-e-model-calibration-<date>.md` (script output)
- `docs/bot-e-model-iterations.md` (log of each attempt)
- `tests/test_bot_e_model.py`

**Modified:**
- `scripts/bot_e_calibration_spike.py` — call `Predictor.predict_p_up` instead of `0.5 + |OBI|/2`.
- `scripts/bot_e_calibration_gate.py` — acceptance criteria use model outputs.
- `bots/bot_e_btc_scalp/__main__.py` — call `Predictor`, later split per E-5.

**Deleted:**
- The `0.5 + |OBI|/2` formula. Not replaced, not moved — deleted. If it appears in any file, it's a bug.

---

## Dependencies

- Python packages: `scikit-learn` (logistic regression), `numpy`, `pandas` for the fit scripts. `lightgbm` if GBDT needed. Add to `pyproject.toml` under a new `[project.optional-dependencies]` group `ml`, not core, so the trader daemon doesn't pay the import cost.
- Recorder data access: the fit scripts need to run on the bot LXC container where `data/bot_e_recorder.db` lives. Alternative: rsync a snapshot to Mac and fit locally; that's likely faster iteration but adds a step each time.

---

## Kill criteria

If after 3 documented model iterations (each with a fresh train/val/test run and calibration report) no model meets the acceptance criteria on any tested horizon, Bot E archives per `docs/kill-dates.md` 2026-06-30. The recorder DB becomes a research dataset. No Phase 6 / Phase 7 extensions.

---

## Anti-patterns to refuse

- "The sample is too small, let's keep collecting and try again" → allowed ONCE, and only with a documented reason for why the current sample is insufficient (e.g., zero regime diversity). After that, the model that fails on held-out is a failed model.
- "Let's add a calibration layer on top" (Platt / isotonic) → rejected. Fixing calibration by post-hoc scaling hides a specification error. Fix the model first.
- "Let's ensemble" → rejected until a single model has been shown to work. Ensembling weak models is how small-sample overfit becomes institutionalized.
- "Adaptive thresholds per regime" → rejected until a single fixed-threshold model works. Complexity must follow evidence.
