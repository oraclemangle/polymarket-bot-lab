# Bot B Scorer Calibration — groq-qwen3

**Generated:** 2026-04-17T22:21:14.126569+00:00
**Sample size:** 20 resolved markets
**Scored usable:** 2
**Skipped by model:** 1

## Overall metrics

- Brier score: **0.3912**
- Weighted ECE: **0.6250**
- Acceptance (Brier ≤ 0.06, per-decile gap ≤ 0.05): **FAILED**
- Verdict: brier=0.3912 above threshold 0.06

## Per-decile calibration

| bucket | n | mean_predicted | realised_rate | gap |
|---|---|---|---|---|
| 0.0-0.1 | 0 | — | — | — |
| 0.1-0.2 | 0 | — | — | — |
| 0.2-0.3 | 0 | — | — | — |
| 0.3-0.4 | 0 | — | — | — |
| 0.4-0.5 | 0 | — | — | — |
| 0.5-0.6 | 0 | — | — | — |
| 0.6-0.7 | 2 | 0.625 | 0.0 | 0.625 |
| 0.7-0.8 | 0 | — | — | — |
| 0.8-0.9 | 0 | — | — | — |
| 0.9-1.0 | 0 | — | — | — |

## Failure analysis

brier=0.3912 above threshold 0.06
