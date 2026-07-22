# Bot B Scorer Calibration — deepseek-v3

**Generated:** 2026-04-17T22:42:22.016419+00:00
**Sample size:** 20 resolved markets
**Scored usable:** 10
**Skipped by model:** 10

## Overall metrics

- Brier score: **0.3172**
- Weighted ECE: **0.3640**
- Acceptance (Brier ≤ 0.06, per-decile gap ≤ 0.05): **FAILED**
- Verdict: brier=0.3172 above threshold 0.06

## Per-decile calibration

| bucket | n | mean_predicted | realised_rate | gap |
|---|---|---|---|---|
| 0.0-0.1 | 0 | — | — | — |
| 0.1-0.2 | 6 | 0.135 | 0.5 | 0.365 |
| 0.2-0.3 | 1 | 0.2 | 0.0 | 0.2 |
| 0.3-0.4 | 1 | 0.35 | 0.0 | 0.35 |
| 0.4-0.5 | 0 | — | — | — |
| 0.5-0.6 | 0 | — | — | — |
| 0.6-0.7 | 0 | — | — | — |
| 0.7-0.8 | 0 | — | — | — |
| 0.8-0.9 | 1 | 0.82 | 0.0 | 0.82 |
| 0.9-1.0 | 1 | 0.92 | 1.0 | 0.08 |

## Failure analysis

brier=0.3172 above threshold 0.06
