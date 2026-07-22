# Becker Maker-Side ROI + Wallet Persistence Analysis

Generated: `2026-05-06T15:57:08.891346+00:00`
Becker data: `/home/operator/Data/longshot-research/external/prediction-market-analysis/repo/data`
Walk-forward cutoff: `2025-12-01`

## Read this first

Read-only research. Two foundational tests that the prior `becker_hypothesis_validation_report.py` did not run:

1. **Maker-side ROI with realistic fees** — the prior validation used a uniform `2c/share` fee proxy. That is roughly `22x` too punitive for cheap entries. This report computes per-fill ROI with three fee regimes side-by-side: `2c/share` audit proxy, realistic taker fee from Becker's recorded `fee_usd`, and zero maker fee.
2. **Wallet performance persistence** with Beta-Binomial-style shrinkage on prior train split, applied to test fills.

Per OQ-081 audit: this report does not authorize any bot/service/config/cap/wallet/order-path change.

## Coverage

- Resolved 15m BTC/ETH/SOL Up/Down tokens: `73,900`
- Fills in lead `5-600s` window: `66,079,487`

## Baseline by split — three fee regimes

`buyer_*` rows: someone took the offer (bought the token at `price`).  `seller_*` rows: someone hit a bid (sold the token at `price`). The `_2c` columns reproduce the audit. The `_real` columns use Becker's actual `fee_usd`. The `_maker_zero` columns model maker fees as zero.

| split | fills | win % | avg price | fee/price | buyer ROI 2c (audit) | buyer ROI real-fee | seller ROI 0 fee |
|---|---:|---:|---:|---:|---:|---:|---:|
| test | 55,595,402 | 51.31% | 0.5121 | 0.29% | -9.40% | -9.59% | -2.58% |
| train | 10,484,085 | 50.87% | 0.5056 | 0.00% | -10.35% | -0.98% | -4.27% |

**Read:** if `buyer_avg_roi_real` is much closer to zero than `buyer_avg_roi_2c`, the audit's fee proxy was too punitive. If `seller_avg_roi_maker_zero` is positive on test, maker-side has expected edge that the audit missed.

## ROI by price band, three fee regimes

`buyer ROI 2c`: replay of audit. `buyer ROI real`: realistic taker fees from Becker. `maker-seller ROI 0`: counterparty (the maker selling cheap tails to buyers like Bot G) at zero maker fees.

| price band | split | fills | win % | avg price | fee/price | buyer ROI 2c | buyer ROI real | maker-sell ROI 0 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 10-15c | test | 2,712,255 | 11.53% | 0.1198 | 0.32% | -17.65% | -21.59% | 0.51% |
| 10-15c | train | 487,259 | 10.74% | 0.1187 | 0.00% | -22.70% | -9.49% | 1.29% |
| 15-20c | test | 2,611,784 | 16.51% | 0.1700 | 0.23% | -13.10% | -17.66% | 0.59% |
| 15-20c | train | 451,232 | 15.86% | 0.1697 | 0.00% | -16.51% | -6.62% | 1.33% |
| 20-30c | test | 5,303,666 | 23.96% | 0.2443 | 0.16% | -9.39% | -13.71% | 0.64% |
| 20-30c | train | 963,241 | 23.64% | 0.2441 | 0.00% | -10.52% | -3.09% | 1.03% |
| 3.5-5.5c | test | 1,270,065 | 4.24% | 0.0452 | 0.90% | -35.07% | -35.81% | 0.29% |
| 3.5-5.5c | train | 263,427 | 3.77% | 0.0450 | 0.00% | -42.16% | -16.19% | 0.77% |
| 30-50c | test | 9,670,791 | 38.56% | 0.3934 | 0.10% | -6.94% | -10.01% | 1.26% |
| 30-50c | train | 1,809,009 | 39.42% | 0.3935 | 0.00% | -4.86% | 0.07% | -0.16% |
| 5.5-8c | test | 1,126,866 | 5.76% | 0.0649 | 0.61% | -32.27% | -34.72% | 0.78% |
| 5.5-8c | train | 207,034 | 5.39% | 0.0648 | 0.00% | -36.46% | -16.73% | 1.17% |
| 50c+ | test | 28,802,049 | 78.22% | 0.7751 | 0.02% | -1.69% | -0.94% | -5.69% |
| 50c+ | train | 5,382,696 | 78.41% | 0.7738 | 0.00% | -1.35% | 1.31% | -8.79% |
| 8-10c | test | 1,068,502 | 7.62% | 0.0850 | 0.45% | -27.48% | -31.57% | 0.97% |
| 8-10c | train | 184,642 | 7.46% | 0.0848 | 0.00% | -28.91% | -12.10% | 1.11% |
| <3.5c | test | 3,029,424 | 1.82% | 0.0182 | 3.38% | -54.41% | -37.47% | 0.00% |
| <3.5c | train | 735,545 | 1.81% | 0.0183 | 0.00% | -54.13% | 4.23% | 0.03% |

## Maker-seller ROI by price band × lead bucket (test split, ≥1000 fills)

| price band | lead | split | fills | win % | avg price | $/share | maker-sell ROI 0 |
|---|---|---|---:|---:|---:|---:|---:|
| 10-15c | 120_to_300s | test | 897,052 | 11.57% | 0.1193 | 0.0036 | 0.41% |
| 10-15c | 120_to_300s | train | 168,230 | 10.50% | 0.1187 | 0.0136 | 1.55% |
| 10-15c | 300_to_600s | test | 1,421,940 | 11.43% | 0.1203 | 0.0059 | 0.67% |
| 10-15c | 300_to_600s | train | 236,626 | 11.40% | 0.1188 | 0.0048 | 0.55% |
| 10-15c | 30_to_60s | test | 91,605 | 12.39% | 0.1194 | -0.0045 | -0.49% |
| 10-15c | 30_to_60s | train | 21,691 | 9.76% | 0.1182 | 0.0206 | 2.33% |
| 10-15c | 5_to_30s | test | 67,892 | 11.21% | 0.1186 | 0.0065 | 0.75% |
| 10-15c | 5_to_30s | train | 15,150 | 9.29% | 0.1180 | 0.0252 | 2.86% |
| 10-15c | 60_to_120s | test | 233,766 | 11.75% | 0.1191 | 0.0016 | 0.17% |
| 10-15c | 60_to_120s | train | 45,562 | 9.09% | 0.1185 | 0.0276 | 3.13% |
| 15-20c | 120_to_300s | test | 784,737 | 17.00% | 0.1697 | -0.0003 | -0.03% |
| 15-20c | 120_to_300s | train | 145,646 | 15.53% | 0.1697 | 0.0144 | 1.74% |
| 15-20c | 300_to_600s | test | 1,507,758 | 16.36% | 0.1702 | 0.0066 | 0.80% |
| 15-20c | 300_to_600s | train | 238,603 | 16.71% | 0.1698 | 0.0027 | 0.32% |
| 15-20c | 30_to_60s | test | 75,961 | 16.51% | 0.1695 | 0.0044 | 0.53% |
| 15-20c | 30_to_60s | train | 16,840 | 13.79% | 0.1695 | 0.0315 | 3.81% |
| 15-20c | 5_to_30s | test | 53,049 | 15.95% | 0.1690 | 0.0095 | 1.15% |
| 15-20c | 5_to_30s | train | 11,461 | 11.47% | 0.1694 | 0.0547 | 6.60% |
| 15-20c | 60_to_120s | test | 190,279 | 15.81% | 0.1698 | 0.0117 | 1.42% |
| 15-20c | 60_to_120s | train | 38,682 | 14.12% | 0.1696 | 0.0285 | 3.43% |
| 3.5-5.5c | 120_to_300s | test | 1,843,946 | 2.67% | 0.0263 | -0.0004 | -0.04% |
| 3.5-5.5c | 120_to_300s | train | 455,379 | 2.13% | 0.0251 | 0.0037 | 0.39% |
| 3.5-5.5c | 300_to_600s | test | 877,077 | 2.39% | 0.0339 | 0.0101 | 1.05% |
| 3.5-5.5c | 300_to_600s | train | 172,658 | 2.86% | 0.0329 | 0.0043 | 0.45% |
| 3.5-5.5c | 30_to_60s | test | 417,913 | 2.65% | 0.0214 | -0.0051 | -0.53% |
| 3.5-5.5c | 30_to_60s | train | 100,440 | 2.49% | 0.0218 | -0.0031 | -0.31% |
| 3.5-5.5c | 5_to_30s | test | 388,694 | 2.44% | 0.0198 | -0.0047 | -0.48% |
| 3.5-5.5c | 5_to_30s | train | 84,674 | 2.42% | 0.0212 | -0.0030 | -0.30% |
| 3.5-5.5c | 60_to_120s | test | 771,859 | 2.38% | 0.0229 | -0.0009 | -0.09% |
| 3.5-5.5c | 60_to_120s | train | 185,821 | 2.18% | 0.0230 | 0.0013 | 0.13% |
| 5.5-8c | 120_to_300s | test | 444,922 | 6.31% | 0.0648 | 0.0017 | 0.18% |
| 5.5-8c | 120_to_300s | train | 84,888 | 5.21% | 0.0647 | 0.0126 | 1.35% |
| 5.5-8c | 300_to_600s | test | 458,208 | 5.05% | 0.0651 | 0.0146 | 1.56% |
| 5.5-8c | 300_to_600s | train | 77,883 | 5.35% | 0.0650 | 0.0115 | 1.23% |
| 5.5-8c | 30_to_60s | test | 56,253 | 6.10% | 0.0646 | 0.0036 | 0.39% |
| 5.5-8c | 30_to_60s | train | 11,610 | 6.78% | 0.0645 | -0.0033 | -0.35% |
| 5.5-8c | 5_to_30s | test | 40,190 | 6.88% | 0.0644 | -0.0044 | -0.47% |
| 5.5-8c | 5_to_30s | train | 8,199 | 6.63% | 0.0645 | -0.0018 | -0.20% |
| 5.5-8c | 60_to_120s | test | 127,293 | 5.89% | 0.0649 | 0.0060 | 0.65% |
| 5.5-8c | 60_to_120s | train | 24,454 | 5.05% | 0.0646 | 0.0141 | 1.51% |
| 8-10c | 120_to_300s | test | 398,040 | 8.12% | 0.0850 | 0.0038 | 0.41% |
| 8-10c | 120_to_300s | train | 71,663 | 7.03% | 0.0847 | 0.0144 | 1.57% |
| 8-10c | 300_to_600s | test | 481,088 | 7.26% | 0.0851 | 0.0125 | 1.37% |
| 8-10c | 300_to_600s | train | 75,666 | 8.11% | 0.0849 | 0.0038 | 0.42% |
| 8-10c | 30_to_60s | test | 45,631 | 6.52% | 0.0849 | 0.0197 | 2.16% |
| 8-10c | 30_to_60s | train | 9,661 | 6.79% | 0.0848 | 0.0169 | 1.85% |
| 8-10c | 5_to_30s | test | 32,419 | 9.11% | 0.0850 | -0.0061 | -0.67% |
| 8-10c | 5_to_30s | train | 7,030 | 8.05% | 0.0847 | 0.0042 | 0.46% |
| 8-10c | 60_to_120s | test | 111,324 | 7.38% | 0.0849 | 0.0110 | 1.21% |
| 8-10c | 60_to_120s | train | 20,622 | 6.66% | 0.0847 | 0.0181 | 1.98% |

## Maker-seller ROI by symbol × side × price band (test split, ≥500 fills)

| symbol | side | price band | fills | win % | avg price | maker-sell ROI 0 |
|---|---|---|---:|---:|---:|---:|
| BTC | DOWN | 10-15c | 936,015 | 12.70% | 0.1199 | -0.81% |
| BTC | DOWN | 3.5-5.5c | 1,338,126 | 2.73% | 0.0270 | -0.03% |
| BTC | DOWN | 5.5-8c | 381,751 | 6.41% | 0.0649 | 0.08% |
| BTC | DOWN | 8-10c | 360,629 | 8.50% | 0.0850 | -0.00% |
| BTC | UP | 10-15c | 928,077 | 10.81% | 0.1197 | 1.32% |
| BTC | UP | 3.5-5.5c | 1,295,819 | 2.45% | 0.0269 | 0.25% |
| BTC | UP | 5.5-8c | 372,403 | 5.02% | 0.0650 | 1.58% |
| BTC | UP | 8-10c | 362,825 | 6.70% | 0.0850 | 1.97% |
| ETH | DOWN | 10-15c | 333,262 | 11.84% | 0.1201 | 0.19% |
| ETH | DOWN | 3.5-5.5c | 545,903 | 2.57% | 0.0261 | 0.05% |
| ETH | DOWN | 5.5-8c | 140,917 | 6.32% | 0.0649 | 0.18% |
| ETH | DOWN | 8-10c | 134,492 | 8.22% | 0.0851 | 0.31% |
| ETH | UP | 10-15c | 305,846 | 10.06% | 0.1201 | 2.23% |
| ETH | UP | 3.5-5.5c | 524,929 | 2.46% | 0.0257 | 0.11% |
| ETH | UP | 5.5-8c | 132,773 | 5.24% | 0.0648 | 1.33% |
| ETH | UP | 8-10c | 124,176 | 6.85% | 0.0851 | 1.81% |
| SOL | DOWN | 10-15c | 109,621 | 12.13% | 0.1189 | -0.27% |
| SOL | DOWN | 3.5-5.5c | 303,584 | 2.44% | 0.0236 | -0.08% |
| SOL | DOWN | 5.5-8c | 51,056 | 6.49% | 0.0649 | 0.00% |
| SOL | DOWN | 8-10c | 44,917 | 8.47% | 0.0850 | 0.03% |
| SOL | UP | 10-15c | 99,434 | 10.20% | 0.1188 | 1.91% |
| SOL | UP | 3.5-5.5c | 291,128 | 2.23% | 0.0233 | 0.10% |
| SOL | UP | 5.5-8c | 47,966 | 5.35% | 0.0647 | 1.19% |
| SOL | UP | 8-10c | 41,463 | 7.36% | 0.0850 | 1.25% |

## Wallet performance persistence with shrinkage

Train-split global win rate: `50.87%`
Train fills: `10,484,085`
Shrinkage alpha (virtual count): `50`

**Wallet volume distribution (training population):**

| volume | wallets | avg shrunken score | min | max |
|---|---:|---:|---:|---:|
| tiny_<100 | 24,357 | 50.90% | 23.60% | 78.08% |
| small_100-1k | 5,541 | 47.46% | 9.92% | 87.80% |
| mid_1k-10k | 1,186 | 41.42% | 10.74% | 84.67% |
| large_>=10k | 151 | 43.14% | 7.46% | 76.04% |

**Test fills filtered by COUNTERPARTY (maker) shrunken score quintile:**

| quintile | min score | max score | fills | win % | avg price | buyer ROI real | maker-sell ROI 0 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 7.46% | 45.69% | 3,879,644 | 63.57% | 0.6319 | -4.39% | -6.42% |
| 2 | 45.69% | 48.80% | 3,879,644 | 48.52% | 0.4801 | -7.37% | -4.17% |
| 3 | 48.80% | 50.35% | 3,879,643 | 49.90% | 0.4964 | -8.52% | -4.33% |
| 4 | 50.35% | 53.52% | 3,879,643 | 48.38% | 0.4785 | -5.74% | -3.99% |
| 5 | 53.52% | 84.67% | 3,879,643 | 45.63% | 0.4552 | -6.86% | -3.29% |

**Test fills filtered by TAKER's own shrunken score quintile:**

| quintile | min score | max score | fills | win % | avg price | buyer ROI real | maker-sell ROI 0 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 7.46% | 50.93% | 5,675,760 | 43.54% | 0.4372 | -8.65% | -1.70% |
| 2 | 50.93% | 59.08% | 5,675,759 | 56.00% | 0.5575 | -8.64% | -6.44% |
| 3 | 59.08% | 59.08% | 5,675,759 | 58.17% | 0.5814 | -7.45% | -2.25% |
| 4 | 59.08% | 59.08% | 5,675,759 | 58.29% | 0.5824 | -6.35% | -1.26% |
| 5 | 59.08% | 84.67% | 5,675,759 | 58.22% | 0.5811 | -6.45% | -0.22% |

## How to read this report

1. **If `seller_avg_roi_maker_zero` baseline is positive** AND `maker_seller_roi_zero` is positive in cheap price bands on the test split AND survives the `≥1000` fills lead-band filter, **maker-side at cheap tails is the missed edge.** The audit's `2c/share` proxy hid it.
2. **If buyer_avg_roi_real is materially closer to zero** than `buyer_avg_roi_2c`, the audit's fee proxy was too punitive but doesn't change the rejection (still negative — just less negative).
3. **If the wallet quintile table shows monotonic ROI gradient** (e.g. quintile 5 of maker shrunken score has materially better buyer ROI on test), there is a tradeable counterparty signal.
4. **If quintiles are flat**, wallet persistence at the shrinkage level chosen is not a useful filter at this granularity.

## Next steps

- If maker-side surfaces edge: build a maker-only paper bot research lane (separate from Bot G) that simulates posting at the indicated bands and lead buckets, with realistic fill probability modeling. Forward paper validation per OQ-081.
- If wallet shrinkage shows monotonic signal: build a counterparty-filter feature for Bot G and validate on Bot G's own forward fills before any operating change.
- If neither surfaces: move to LightGBM multi-feature model on the same feature set.
