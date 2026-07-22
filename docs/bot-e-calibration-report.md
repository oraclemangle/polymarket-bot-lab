# Bot E Phase 0d Calibration Report

**Generated:** 2026-04-17 09:06 UTC
**Verdict: NO-GO**

insufficient sample size: 22 qualifying signals (need >= 200); realised win rate 0.500 below threshold 0.52; weighted ECE 0.351 above threshold 0.1; live-window (5-10min) WR 0.500 below threshold 0.52 (n=22); live-window (5-10min) ECE 0.363 above threshold 0.1 (n=22)

---

## Data

| Field | Value |
|---|---|
| Data window | 2026-04-16 09:14 UTC to 2026-04-16 13:53 UTC |
| Duration | ~4.6 hours (single day, 2026-04-16) |
| Raw OBI signals in entry window | 47 |
| Signals with resolved outcomes | 47 |
| Regime-skipped (choppy BTC) | 0 |
| Final calibration signals | 22 |

---

## Methodology

1. **OBI reconstruction**: Rolled `last_trade_price` events through 120s window per
   subscription. Signal fires if `abs(OBI) >= 0.2` and timestamp
   falls in t-10min to t-5min entry window. 30s cooldown per subscription.

2. **Resolution outcome**: For "Up or Down" markets, CEX price (Binance) at market
   START vs END determines YES (price UP) or NO (price DOWN). 30s averaging window
   at each timestamp. This works for all resolved markets, not just those with
   post-expiry WSS events.

3. **Win condition**: OBI sign predicts direction (BUY_YES / BUY_NO). Win if outcome
   matches predicted direction.

4. **Regime gate**: Choppiness ratio from 10-min BTC CEX window. Skip if > 0.65.
   Applied to BTC subscriptions only.

5. **Predicted WR model**: `predicted_wr = 0.5 + abs(OBI)/2` (conservative linear
   proxy used only for ECE; not a calibrated probability model).

---

## Per-Bucket Results

| OBI bucket | N signals | Predicted WR | Realised WR | ECE |
|---|---|---|---|---|
| 0.20-0.30 | 5 | 0.632 | 0.200 | 0.432 |
| 0.30-0.40 | 0 | — | — | — |
| 0.40-0.50 | 1 | 0.743 | 0.000 | 0.743 |
| 0.50-0.65 | 2 | 0.790 | 0.500 | 0.290 |
| 0.65+ | 14 | 0.965 | 0.643 | 0.322 |

**Overall**: 22 signals, realised WR = 0.500, weighted ECE = 0.351

95% confidence interval on WR (binomial, N=22): ±0.209

---

## By Symbol

| Symbol | N | Win Rate |
|---|---|---|
| BTC | 7 | 0.143 |
| ETH | 13 | 0.692 |
| SOL | 2 | 0.500 |


---

## Red Flags

- **Single-day data (4.6 hours)**: All data is from 2026-04-16. No multi-day variance
  captured. Standard error at N=22 is ±0.209 — treat win rate estimate
  as very uncertain.

- **Recorder closes subscriptions on resolution**: The recorder design closes WSS when
  a market expires. This is correct operationally but means post-expiry price cascades
  are only captured for markets that resolve while a new subscription is starting up.
  CEX-based outcome detection was used to work around this.

- **OBI entry window low coverage**: Most subscriptions had low trade counts in the
  t-10min to t-5min window. The 30s cooldown limited signals to ~1 per subscription
  per 30s, reducing the dataset.

- **Maker fill not modelled**: We assume entry fills. In practice, maker-only orders
  may not fill in the 5-min entry window. Fill rate is a separate open question.

- **No overnight or multi-session variance**: Only covers ~09:14-13:53 UTC European
  morning and US pre-market session.

---

## GO/NO-GO Decision

**NO-GO**

Threshold criteria:
- Minimum 200 calibrated signals: FAIL (22 signals)
- Realised WR >= 0.52: FAIL (0.500)
- Weighted ECE <= 0.1: FAIL (0.351)

Primary blocker: insufficient sample size: 22 qualifying signals (need >= 200)

---

## Recommendation

Do not activate paper trading yet. Continue recording for at least 7 additional days to accumulate sufficient signal volume. The architecture appears sound — the blocker is sample size, not signal quality. Re-run this script after 7+ days of recording. The directional bias in existing signals (where measured) provides preliminary evidence but is not statistically reliable at this sample size.
