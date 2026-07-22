# Bot F Crowd Momentum EV Report

Generated: `2026-05-08T21:28:54.612152+00:00`
Bot F DB: `/home/bot/polymarket-bot/data/bot_f.db`
Since: `all`

## Verdict

- PASS: `8` cells clear the sample, net-edge, CI, and concentration gate.

## Sample

- Signals loaded: `500`
- Markets requested: `64`
- Markets fetched: `64`
- Observations measured: `1340`
- Tolerance seconds: `300`
- Bootstrap resamples: `5000` by market/day cluster

API errors: fetch_failed:HTTPError=4

## Best Cells

| Horizon | Mode | Cost | Group | Segment | n | Market-days | Net edge | CI95 | Net+ | Top2 | Gate |
|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| 1800s | same_side | 1c | price_bucket | 25c-50c | 117 | 27 | +10.92c | +0.23c..+21.00c | 61.5% | 11.2% | PASS |
| 1800s | same_side | 1c | signal_age_bucket | 90s-5m | 235 | 34 | +6.26c | +2.73c..+9.83c | 63.0% | 9.2% | PASS |
| 1800s | same_side | 2c | signal_age_bucket | 90s-5m | 235 | 34 | +5.26c | +1.69c..+8.93c | 58.3% | 10.7% | PASS |
| 1800s | same_side | 1c | trade_size_bucket | <100 | 213 | 37 | +5.16c | +1.59c..+9.57c | 62.4% | 13.0% | PASS |
| 1800s | same_side | 1c | all | all | 380 | 42 | +4.27c | +0.79c..+7.97c | 61.1% | 8.8% | PASS |
| 1800s | same_side | 1c | wallet_cohort | rank_11_40 | 380 | 42 | +4.27c | +0.74c..+7.96c | 61.1% | 8.8% | PASS |
| 1800s | same_side | 2c | trade_size_bucket | <100 | 213 | 37 | +4.16c | +0.58c..+8.47c | 58.7% | 15.9% | PASS |
| 1800s | same_side | 1c | category | sports | 376 | 41 | +4.16c | +0.63c..+8.06c | 60.9% | 9.1% | PASS |
| 21600s | same_side | 1c | trade_size_bucket | <100 | 6 | 3 | +22.27c | -1.54c..+45.23c | 66.7% | 68.7% | FAIL |
| 21600s | same_side | 1c | signal_age_bucket | 90s-5m | 11 | 4 | +21.86c | +12.83c..+37.55c | 100.0% | 36.9% | FAIL |
| 21600s | same_side | 2c | trade_size_bucket | <100 | 6 | 3 | +21.27c | -2.54c..+44.23c | 50.0% | 70.4% | FAIL |
| 21600s | same_side | 2c | signal_age_bucket | 90s-5m | 11 | 4 | +20.86c | +11.83c..+36.55c | 90.9% | 37.8% | FAIL |
| 21600s | same_side | 1c | price_bucket | 50c-75c | 19 | 5 | +20.55c | +12.92c..+37.46c | 89.5% | 23.5% | FAIL |
| 21600s | same_side | 2c | price_bucket | 50c-75c | 19 | 5 | +19.55c | +12.08c..+36.46c | 89.5% | 24.2% | FAIL |
| 21600s | same_side | 4c | trade_size_bucket | <100 | 6 | 3 | +19.27c | -4.54c..+42.23c | 50.0% | 74.2% | FAIL |
| 21600s | same_side | 4c | signal_age_bucket | 90s-5m | 11 | 4 | +18.86c | +9.83c..+34.55c | 90.9% | 39.9% | FAIL |
| 21600s | same_side | 1c | all | all | 24 | 7 | +17.60c | +10.12c..+32.38c | 83.3% | 21.7% | FAIL |
| 21600s | same_side | 1c | category | sports | 24 | 7 | +17.60c | +10.02c..+31.92c | 83.3% | 21.7% | FAIL |
| 21600s | same_side | 1c | wallet_cohort | rank_11_40 | 24 | 7 | +17.60c | +9.87c..+31.56c | 83.3% | 21.7% | FAIL |
| 21600s | same_side | 4c | price_bucket | 50c-75c | 19 | 5 | +17.55c | +9.92c..+36.60c | 89.5% | 25.7% | FAIL |
| 21600s | same_side | 1c | trade_size_bucket | 1k-10k | 6 | 4 | +17.31c | +7.33c..+28.93c | 83.3% | 55.7% | FAIL |
| 21600s | same_side | 1c | trade_size_bucket | 100-1k | 11 | 3 | +17.16c | +15.00c..+24.90c | 100.0% | 26.4% | FAIL |
| 21600s | same_side | 2c | all | all | 24 | 7 | +16.60c | +9.11c..+31.00c | 79.2% | 22.5% | FAIL |
| 21600s | same_side | 2c | category | sports | 24 | 7 | +16.60c | +8.75c..+31.10c | 79.2% | 22.5% | FAIL |
| 21600s | same_side | 2c | wallet_cohort | rank_11_40 | 24 | 7 | +16.60c | +8.35c..+31.10c | 79.2% | 22.5% | FAIL |
| 21600s | same_side | 2c | trade_size_bucket | 1k-10k | 6 | 4 | +16.31c | +6.33c..+27.93c | 83.3% | 57.1% | FAIL |
| 21600s | same_side | 2c | trade_size_bucket | 100-1k | 11 | 3 | +16.16c | +14.00c..+23.90c | 100.0% | 26.9% | FAIL |
| 21600s | same_side | 4c | all | all | 24 | 7 | +14.60c | +7.04c..+28.92c | 79.2% | 24.5% | FAIL |
| 21600s | same_side | 4c | category | sports | 24 | 7 | +14.60c | +6.88c..+28.92c | 79.2% | 24.5% | FAIL |
| 21600s | same_side | 4c | wallet_cohort | rank_11_40 | 24 | 7 | +14.60c | +7.12c..+28.79c | 79.2% | 24.5% | FAIL |
| 21600s | same_side | 4c | trade_size_bucket | 1k-10k | 6 | 4 | +14.31c | +4.33c..+25.93c | 83.3% | 60.4% | FAIL |
| 21600s | same_side | 4c | trade_size_bucket | 100-1k | 11 | 3 | +14.16c | +12.00c..+21.90c | 100.0% | 28.1% | FAIL |
| 1800s | same_side | 1c | category | weather | 4 | 1 | +14.16c | +14.16c..+14.16c | 75.0% | 79.5% | FAIL |
| 21600s | same_side | 1c | signal_age_bucket | <=90s | 13 | 5 | +13.98c | +3.54c..+31.75c | 69.2% | 43.9% | FAIL |
| 1800s | same_side | 2c | category | weather | 4 | 1 | +13.16c | +13.16c..+13.16c | 75.0% | 81.7% | FAIL |
| 300s | same_side | 1c | category | weather | 4 | 1 | +13.00c | +13.00c..+13.00c | 100.0% | 53.8% | FAIL |
| 21600s | same_side | 2c | signal_age_bucket | <=90s | 13 | 5 | +12.98c | +2.54c..+30.75c | 69.2% | 46.1% | FAIL |
| 300s | same_side | 2c | category | weather | 4 | 1 | +12.00c | +12.00c..+12.00c | 100.0% | 54.2% | FAIL |
| 21600s | same_side | 1c | price_bucket | 25c-50c | 3 | 2 | +11.67c | +1.00c..+17.00c | 100.0% | 97.1% | FAIL |
| 1800s | same_side | 4c | category | weather | 4 | 1 | +11.16c | +11.16c..+11.16c | 75.0% | 87.4% | FAIL |
| 21600s | same_side | 4c | signal_age_bucket | <=90s | 13 | 5 | +10.98c | +0.54c..+28.75c | 69.2% | 51.7% | FAIL |
| 21600s | same_side | 2c | price_bucket | 25c-50c | 3 | 2 | +10.67c | -0.00c..+16.00c | 66.7% | 100.0% | FAIL |
| 300s | same_side | 4c | category | weather | 4 | 1 | +10.00c | +10.00c..+10.00c | 100.0% | 55.0% | FAIL |
| 1800s | same_side | 2c | price_bucket | 25c-50c | 117 | 27 | +9.92c | -0.96c..+19.65c | 59.0% | 12.1% | FAIL |
| 21600s | same_side | 4c | price_bucket | 25c-50c | 3 | 2 | +8.67c | -2.00c..+14.00c | 66.7% | 107.7% | FAIL |
| 1800s | same_side | 4c | price_bucket | 25c-50c | 117 | 27 | +7.92c | -3.23c..+17.79c | 55.6% | 14.8% | FAIL |
| 1800s | same_side | 1c | signal_age_bucket | 5m-30m | 16 | 8 | +7.86c | -12.38c..+17.78c | 68.8% | 41.6% | FAIL |
| 300s | fade | 1c | signal_age_bucket | 5m-30m | 14 | 9 | +6.92c | +0.92c..+14.17c | 71.4% | 47.5% | FAIL |
| 1800s | same_side | 2c | signal_age_bucket | 5m-30m | 16 | 8 | +6.86c | -13.50c..+17.08c | 68.8% | 45.8% | FAIL |
| 1800s | fade | 1c | price_bucket | 10c-25c | 16 | 11 | +6.56c | +1.34c..+11.31c | 81.2% | 31.5% | FAIL |
| 300s | fade | 2c | signal_age_bucket | 5m-30m | 14 | 9 | +5.92c | +0.07c..+12.90c | 64.3% | 53.1% | FAIL |
| 1800s | fade | 2c | price_bucket | 10c-25c | 16 | 11 | +5.56c | +0.40c..+10.34c | 68.8% | 34.9% | FAIL |
| 1800s | same_side | 4c | signal_age_bucket | 5m-30m | 16 | 8 | +4.86c | -14.69c..+14.56c | 62.5% | 59.5% | FAIL |
| 300s | fade | 4c | signal_age_bucket | 5m-30m | 14 | 9 | +3.92c | -2.10c..+11.18c | 64.3% | 73.0% | FAIL |
| 1800s | fade | 4c | price_bucket | 10c-25c | 16 | 11 | +3.56c | -1.63c..+8.36c | 68.8% | 47.5% | FAIL |
| 1800s | same_side | 1c | trade_size_bucket | 100-1k | 119 | 25 | +3.51c | -3.50c..+10.49c | 65.5% | 28.5% | FAIL |
| 1800s | same_side | 2c | all | all | 380 | 42 | +3.27c | -0.14c..+7.08c | 55.5% | 11.3% | FAIL |
| 1800s | same_side | 2c | wallet_cohort | rank_11_40 | 380 | 42 | +3.27c | -0.15c..+6.99c | 55.5% | 11.3% | FAIL |
| 1800s | same_side | 4c | signal_age_bucket | 90s-5m | 235 | 34 | +3.26c | -0.31c..+6.85c | 52.3% | 16.8% | FAIL |
| 1800s | same_side | 2c | category | sports | 376 | 41 | +3.16c | -0.42c..+6.86c | 55.3% | 11.8% | FAIL |
| 1800s | same_side | 1c | price_bucket | 75c+ | 93 | 22 | +2.90c | -3.55c..+7.87c | 67.7% | 17.2% | FAIL |
| 1800s | same_side | 2c | trade_size_bucket | 100-1k | 119 | 25 | +2.51c | -4.23c..+9.87c | 58.8% | 39.2% | FAIL |
| 1800s | same_side | 1c | trade_size_bucket | 1k-10k | 47 | 19 | +2.25c | -3.60c..+11.88c | 44.7% | 114.3% | FAIL |
| 1800s | same_side | 4c | trade_size_bucket | <100 | 213 | 37 | +2.16c | -1.54c..+6.48c | 53.1% | 29.7% | FAIL |
| 21600s | fade | 1c | trade_size_bucket | 10k-100k | 1 | 1 | +2.00c | +2.00c..+2.00c | 100.0% | 100.0% | FAIL |
| 1800s | same_side | 2c | price_bucket | 75c+ | 93 | 22 | +1.90c | -4.72c..+6.82c | 62.4% | 25.1% | FAIL |
| 60s | same_side | 1c | signal_age_bucket | 5m-30m | 12 | 8 | +1.67c | -4.17c..+6.44c | 58.3% | 100.0% | FAIL |
| 60s | same_side | 1c | price_bucket | 10c-25c | 37 | 19 | +1.59c | -0.36c..+3.59c | 56.8% | 57.7% | FAIL |
| 1800s | same_side | 1c | price_bucket | 50c-75c | 147 | 27 | +1.44c | -9.57c..+13.61c | 62.6% | 45.7% | FAIL |
| 1800s | same_side | 4c | all | all | 380 | 42 | +1.27c | -2.33c..+5.09c | 50.5% | 28.4% | FAIL |
| 1800s | same_side | 4c | wallet_cohort | rank_11_40 | 380 | 42 | +1.27c | -2.25c..+4.98c | 50.5% | 28.4% | FAIL |
| 1800s | same_side | 2c | trade_size_bucket | 1k-10k | 47 | 19 | +1.25c | -4.65c..+10.29c | 34.0% | 202.2% | FAIL |
| 300s | same_side | 1c | price_bucket | 50c-75c | 158 | 32 | +1.24c | -1.28c..+4.20c | 54.4% | 46.9% | FAIL |
| 1800s | same_side | 4c | category | sports | 376 | 41 | +1.16c | -2.33c..+4.95c | 50.3% | 31.3% | FAIL |
| 21600s | fade | 2c | trade_size_bucket | 10k-100k | 1 | 1 | +1.00c | +1.00c..+1.00c | 100.0% | 100.0% | FAIL |
| 60s | same_side | 1c | category | weather | 4 | 1 | +1.00c | +1.00c..+1.00c | 50.0% | 225.0% | FAIL |
| 300s | same_side | 1c | category | unknown | 1 | 1 | +1.00c | +1.00c..+1.00c | 100.0% | 100.0% | FAIL |
| 60s | same_side | 1c | category | unknown | 1 | 1 | +1.00c | +1.00c..+1.00c | 100.0% | 100.0% | FAIL |
| 300s | same_side | 1c | trade_size_bucket | <100 | 286 | 53 | +0.97c | -0.21c..+2.32c | 48.3% | 27.4% | FAIL |
| 60s | same_side | 1c | price_bucket | 75c+ | 116 | 27 | +0.77c | -0.22c..+1.99c | 44.0% | 32.1% | FAIL |

## Caveats and known limitations

- Public trade prints are not executable order-book quotes; treat this as signal discovery, not tradable EV.
- Same-side mode for SELL signals means the token price fell after the crowd sold; it does not imply a live short route exists.
- Cost stress is per share and does not model queue position, market impact, or minimum order constraints.
- Bootstrap resamples market/day clusters, but clustered wallet behavior can still overstate independence.
- No live bot state, service, wallet, cap, or systemd unit is touched.