# Bot B Scorer Calibration — ollama-kimi

**Generated:** 2026-04-17T22:39:34.194602+00:00
**Sample size:** 20 resolved markets
**Scored usable:** 7
**Skipped by model:** 1

## Overall metrics

- Brier score: **0.1788**
- Weighted ECE: **0.3243**
- Acceptance (Brier ≤ 0.06, per-decile gap ≤ 0.05): **FAILED**
- Verdict: brier=0.1788 above threshold 0.06

## Per-decile calibration

| bucket | n | mean_predicted | realised_rate | gap |
|---|---|---|---|---|
| 0.0-0.1 | 2 | 0.055 | 0.5 | 0.445 |
| 0.1-0.2 | 1 | 0.18 | 0.0 | 0.18 |
| 0.2-0.3 | 1 | 0.22 | 0.0 | 0.22 |
| 0.3-0.4 | 2 | 0.35 | 0.0 | 0.35 |
| 0.4-0.5 | 0 | — | — | — |
| 0.5-0.6 | 0 | — | — | — |
| 0.6-0.7 | 0 | — | — | — |
| 0.7-0.8 | 1 | 0.72 | 1.0 | 0.28 |
| 0.8-0.9 | 0 | — | — | — |
| 0.9-1.0 | 0 | — | — | — |

## Failure analysis

brier=0.1788 above threshold 0.06
