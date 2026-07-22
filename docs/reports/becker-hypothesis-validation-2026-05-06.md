# Becker Hypothesis Validation

Generated: `2026-05-06T14:41:51.968419+00:00`
Becker data: `/home/operator/Data/longshot-research/external/prediction-market-analysis/repo/data`
Binance klines: `/home/operator/Data/longshot-research/external/cex/binance/klines/1m`
Walk-forward cutoff: `2025-12-01` (split = `train` if fill_ts < cutoff else `test`)

## Read this first

Read-only research. Tests Track 1 hypotheses on the 49M-fill Becker historical dataset using strictly causal time windows (prior minute only, never the bar containing the fill). Tier D items deliberately use post-fill data and are flagged as research validators only — they cannot become entry rules.

Per OQ-081 audit: this report does not authorize any Bot G, Bot D, Bot B, FV paper, or recorder service change. Authority comes from running these features on Bot G/FV-bot's own forward data and surviving forward paper.

## Coverage

- Resolved 15m BTC/ETH/SOL Up/Down tokens: `73,900`
- Fills in lead `5-600s` window: `66,079,487`

## Baseline

| split | fills | win % | avg price | ROI 0c | ROI 1c | ROI 2c |
|---|---:|---:|---:|---:|---:|---:|
| test | 55,595,402 | 51.31% | 0.5121 | -0.81% | -5.93% | -9.40% |
| train | 10,484,085 | 50.87% | 0.5056 | -0.98% | -6.70% | -10.35% |

Use this baseline as the reference. A hypothesis is supportive if its conditional cell shows higher win rate AND higher net ROI than the matching split row above, and the lift is consistent across train and test.

## Wallet archetype distribution

| archetype | wallets | total fills | as maker | as taker |
|---|---:|---:|---:|---:|
| taker_heavy | 522 | 46,847,214 | 8,980,280 | 37,866,934 |
| mm_l1 | 88 | 40,204,151 | 30,719,557 | 9,484,594 |
| mm_l2 | 570 | 14,805,709 | 10,999,835 | 3,805,874 |
| taker_active | 4,191 | 12,167,067 | 4,779,402 | 7,387,665 |
| mm_l3 | 3,249 | 9,746,786 | 6,620,936 | 3,125,850 |
| mixed_mid | 20,672 | 7,072,821 | 3,369,566 | 3,703,255 |
| light | 60,227 | 1,315,226 | 609,911 | 705,315 |

## Tier A #1 — counterparty maker archetype (taker = Bot G analogue)

**Maker archetype (Bot G analogue is taker, so this is who Bot G fades against):**

| maker archetype | fills | win % | avg price | ROI 0c | ROI 1c | ROI 2c |
|---|---:|---:|---:|---:|---:|---:|
| taker_heavy | 8,980,280 | 59.21% | 0.5886 | -0.08% | -3.50% | -6.17% |
| taker_active | 4,779,402 | 65.12% | 0.6523 | -1.99% | -4.87% | -7.14% |
| mm_l1 | 30,719,557 | 47.53% | 0.4714 | -0.16% | -4.53% | -7.89% |
| mixed_mid | 3,369,566 | 54.23% | 0.5490 | -4.98% | -10.06% | -13.34% |
| mm_l3 | 6,620,936 | 52.92% | 0.5325 | -3.04% | -9.69% | -13.57% |
| mm_l2 | 10,999,835 | 47.38% | 0.4736 | 0.46% | -8.83% | -13.81% |
| light | 609,911 | 47.23% | 0.4953 | -13.83% | -18.05% | -20.98% |

**Maker × taker archetype pairs by split (≥1k fills):**

| maker | taker | split | fills | win % | avg price | ROI 0c | ROI 1c | ROI 2c |
|---|---|---|---:|---:|---:|---:|---:|---:|
| mm_l1 | light | train | 114,966 | 53.12% | 0.4897 | 11.38% | 5.99% | 1.93% |
| taker_heavy | light | train | 4,294 | 67.79% | 0.6512 | 13.81% | 5.41% | 0.43% |
| taker_heavy | mm_l2 | train | 11,266 | 53.83% | 0.5375 | 10.90% | 2.78% | -2.81% |
| taker_heavy | mixed_mid | train | 14,274 | 62.48% | 0.6112 | 10.42% | 1.86% | -3.24% |
| mm_l1 | light | test | 306,325 | 55.10% | 0.5273 | 4.89% | 0.18% | -3.33% |
| taker_active | light | train | 1,852 | 79.37% | 0.7729 | 0.19% | -2.45% | -4.60% |
| taker_heavy | light | test | 16,509 | 66.27% | 0.6505 | 1.20% | -2.64% | -5.58% |
| taker_heavy | taker_heavy | train | 1,529,596 | 59.53% | 0.5896 | -0.23% | -3.40% | -5.93% |
| mm_l1 | mixed_mid | train | 418,934 | 47.67% | 0.4558 | 3.58% | -1.88% | -5.93% |
| mm_l2 | light | test | 107,894 | 54.71% | 0.5237 | 12.19% | 0.13% | -6.00% |
| taker_heavy | taker_heavy | test | 6,623,917 | 59.14% | 0.5882 | -0.04% | -3.42% | -6.06% |
| taker_heavy | mm_l1 | train | 44,466 | 59.96% | 0.6077 | -1.75% | -4.16% | -6.25% |
| taker_active | mm_l1 | train | 17,700 | 63.66% | 0.6388 | -2.04% | -4.32% | -6.40% |
| mm_l1 | mm_l1 | train | 965,457 | 49.66% | 0.4952 | -1.31% | -4.10% | -6.55% |
| taker_heavy | mm_l1 | test | 249,657 | 57.83% | 0.5836 | -1.04% | -4.07% | -6.57% |
| taker_active | mixed_mid | train | 6,077 | 76.30% | 0.7550 | 0.48% | -4.06% | -6.84% |
| taker_active | taker_heavy | test | 3,892,125 | 64.88% | 0.6496 | -1.92% | -4.71% | -6.95% |
| mm_l1 | mm_l1 | test | 4,915,096 | 51.24% | 0.5127 | -1.88% | -4.63% | -7.07% |
| taker_active | mm_l3 | train | 4,209 | 76.50% | 0.7568 | -2.21% | -5.08% | -7.28% |
| mm_l1 | mixed_mid | test | 1,821,187 | 49.82% | 0.4887 | 1.29% | -3.74% | -7.42% |
| taker_active | taker_heavy | train | 501,804 | 67.66% | 0.6771 | -2.48% | -5.33% | -7.48% |
| taker_heavy | taker_active | train | 16,342 | 56.32% | 0.5602 | 8.00% | -1.76% | -7.48% |
| taker_active | light | test | 7,979 | 73.34% | 0.7279 | -2.25% | -5.18% | -7.51% |
| taker_active | mm_l2 | test | 46,785 | 64.13% | 0.6412 | 0.95% | -4.28% | -7.58% |
| mm_l1 | taker_heavy | test | 10,859,171 | 47.21% | 0.4691 | -0.07% | -4.36% | -7.68% |
| mm_l1 | taker_heavy | train | 2,454,907 | 48.17% | 0.4783 | -0.47% | -4.64% | -7.80% |
| taker_heavy | mm_l3 | test | 82,353 | 61.42% | 0.6094 | 0.18% | -4.58% | -7.81% |
| mm_l1 | mm_l2 | train | 284,183 | 43.02% | 0.4186 | 1.78% | -3.82% | -7.87% |
| taker_heavy | mm_l3 | train | 8,482 | 58.74% | 0.5830 | 6.68% | -2.74% | -8.12% |
| taker_active | taker_active | train | 7,141 | 74.08% | 0.7348 | -2.11% | -5.64% | -8.16% |
| taker_heavy | mm_l2 | test | 93,723 | 58.71% | 0.5832 | -0.77% | -5.09% | -8.24% |
| taker_heavy | taker_active | test | 190,546 | 57.97% | 0.5743 | -0.70% | -5.18% | -8.49% |
| mm_l3 | light | test | 52,085 | 59.74% | 0.5778 | 4.90% | -3.75% | -8.55% |
| taker_heavy | mixed_mid | test | 94,855 | 62.68% | 0.6183 | -1.64% | -5.62% | -8.57% |
| taker_active | mm_l1 | test | 112,669 | 58.56% | 0.5986 | -2.50% | -6.04% | -8.62% |
| mm_l1 | mm_l2 | test | 2,136,725 | 45.68% | 0.4539 | -0.61% | -5.32% | -8.93% |
| mm_l1 | mm_l3 | train | 223,576 | 42.72% | 0.4151 | 2.62% | -4.34% | -8.99% |
| taker_active | mixed_mid | test | 44,852 | 69.88% | 0.6970 | -3.07% | -6.56% | -9.13% |
| mm_l2 | light | train | 43,439 | 43.15% | 0.4080 | 25.48% | 1.70% | -9.13% |
| taker_active | mm_l3 | test | 40,914 | 67.17% | 0.6701 | -2.26% | -6.43% | -9.25% |
| mm_l1 | taker_active | test | 4,009,307 | 44.39% | 0.4397 | 0.29% | -5.23% | -9.27% |
| taker_active | taker_active | test | 90,424 | 64.26% | 0.6430 | -2.07% | -6.34% | -9.34% |
| mm_l1 | mm_l3 | test | 1,713,756 | 44.89% | 0.4442 | -0.08% | -5.43% | -9.34% |
| mm_l3 | light | train | 22,465 | 52.63% | 0.5081 | 14.19% | -1.64% | -9.36% |
| mm_l2 | mm_l1 | test | 1,527,911 | 51.82% | 0.5267 | -2.60% | -6.91% | -9.92% |
| mm_l2 | mm_l1 | train | 230,056 | 53.80% | 0.5442 | -3.40% | -7.76% | -10.76% |
| mm_l1 | taker_active | train | 495,967 | 43.36% | 0.4238 | -0.05% | -6.50% | -10.87% |
| mm_l3 | mm_l1 | test | 892,229 | 54.24% | 0.5538 | -4.89% | -8.40% | -11.06% |
| mm_l3 | mm_l1 | train | 159,978 | 54.26% | 0.5534 | -5.05% | -8.48% | -11.20% |
| mm_l2 | taker_heavy | test | 4,605,887 | 50.68% | 0.5084 | -0.60% | -7.44% | -11.48% |
| mixed_mid | mm_l1 | test | 245,858 | 51.83% | 0.5336 | -5.29% | -8.87% | -11.61% |
| mm_l3 | taker_heavy | test | 3,135,136 | 55.63% | 0.5611 | -3.58% | -8.48% | -11.68% |
| mixed_mid | taker_heavy | test | 2,007,841 | 55.89% | 0.5646 | -4.63% | -8.94% | -11.90% |
| mixed_mid | light | test | 13,618 | 60.98% | 0.5968 | -2.35% | -8.25% | -11.97% |
| mm_l3 | taker_heavy | train | 491,037 | 56.97% | 0.5716 | -5.50% | -10.29% | -13.42% |
| taker_active | mm_l2 | train | 4,871 | 66.70% | 0.6858 | -8.47% | -11.49% | -13.60% |
| mixed_mid | taker_heavy | train | 506,764 | 56.17% | 0.5695 | -7.59% | -11.31% | -14.02% |
| mm_l3 | mixed_mid | train | 72,689 | 47.61% | 0.4652 | 12.85% | -5.63% | -14.18% |
| mixed_mid | light | train | 9,513 | 52.94% | 0.5160 | -0.66% | -9.30% | -14.25% |
| mixed_mid | mm_l1 | train | 74,313 | 47.95% | 0.5016 | -8.04% | -11.73% | -14.67% |
| mm_l2 | mixed_mid | test | 656,032 | 46.83% | 0.4588 | 2.46% | -9.24% | -15.16% |
| mm_l2 | taker_heavy | train | 773,496 | 51.26% | 0.5152 | -4.19% | -11.28% | -15.39% |
| mm_l3 | mixed_mid | test | 308,703 | 51.80% | 0.5117 | -1.30% | -10.90% | -15.99% |
| mixed_mid | mixed_mid | test | 79,568 | 54.67% | 0.5461 | -3.07% | -11.39% | -16.08% |
| mm_l2 | mm_l2 | test | 626,904 | 42.07% | 0.4177 | 0.21% | -11.02% | -16.85% |
| mm_l3 | mm_l2 | test | 331,420 | 46.90% | 0.4706 | -2.42% | -12.14% | -17.12% |
| mixed_mid | mixed_mid | train | 31,093 | 46.87% | 0.4685 | 2.64% | -10.34% | -17.12% |
| light | mm_l1 | train | 16,983 | 45.86% | 0.4954 | -10.72% | -14.46% | -17.26% |
| mm_l3 | mm_l3 | test | 279,204 | 47.86% | 0.4774 | -0.54% | -11.73% | -17.39% |
| mixed_mid | mm_l2 | test | 84,495 | 46.54% | 0.4755 | 0.55% | -11.70% | -17.62% |
| mm_l2 | taker_active | test | 1,395,587 | 39.29% | 0.3870 | 4.82% | -10.38% | -17.69% |
| mm_l2 | mixed_mid | train | 138,776 | 35.84% | 0.3438 | 18.88% | -6.86% | -17.88% |
| mm_l2 | mm_l3 | test | 544,387 | 40.64% | 0.4018 | 2.85% | -11.22% | -18.10% |
| mixed_mid | taker_active | test | 173,205 | 46.84% | 0.4731 | -1.75% | -12.53% | -18.15% |
| light | mm_l1 | test | 32,221 | 43.21% | 0.4689 | -12.96% | -16.06% | -18.61% |
| mm_l3 | taker_active | test | 688,793 | 44.39% | 0.4413 | -0.41% | -12.54% | -18.64% |
| mixed_mid | mm_l3 | test | 69,151 | 48.66% | 0.4890 | -5.40% | -14.03% | -18.82% |
| light | taker_heavy | train | 145,759 | 50.83% | 0.5311 | -13.33% | -17.08% | -19.73% |
| light | light | train | 2,687 | 47.97% | 0.4743 | -5.51% | -15.25% | -20.18% |
| light | taker_heavy | test | 339,494 | 47.55% | 0.4981 | -13.83% | -17.55% | -20.32% |
| light | mixed_mid | test | 8,915 | 47.73% | 0.4807 | -10.98% | -18.06% | -22.25% |
| mm_l3 | taker_active | train | 86,280 | 41.86% | 0.4135 | 4.33% | -14.44% | -22.71% |
| light | light | test | 1,689 | 54.77% | 0.5574 | -15.49% | -20.07% | -23.20% |
| mixed_mid | taker_active | train | 34,038 | 43.07% | 0.4366 | -7.35% | -18.87% | -24.70% |
| light | mixed_mid | train | 7,300 | 41.12% | 0.4156 | -7.94% | -20.22% | -26.04% |
| mixed_mid | mm_l2 | train | 22,034 | 41.41% | 0.4255 | -17.03% | -23.10% | -26.95% |
| light | taker_active | train | 7,538 | 38.87% | 0.4004 | -11.93% | -22.61% | -28.16% |
| light | mm_l3 | train | 4,178 | 38.70% | 0.4002 | -6.77% | -21.89% | -28.57% |
| mixed_mid | mm_l3 | train | 18,075 | 44.13% | 0.4481 | -15.50% | -24.61% | -29.29% |
| mm_l2 | taker_active | train | 172,040 | 27.19% | 0.2662 | 8.60% | -18.03% | -29.36% |
| mm_l3 | mm_l2 | train | 54,658 | 39.68% | 0.3979 | -12.93% | -24.12% | -29.56% |
| light | taker_active | test | 20,457 | 39.88% | 0.4184 | -19.51% | -26.02% | -29.86% |
| light | mm_l3 | test | 7,802 | 40.19% | 0.4257 | -20.36% | -26.52% | -30.28% |
| light | mm_l2 | test | 10,041 | 38.07% | 0.4094 | -21.43% | -27.30% | -31.00% |
| mm_l3 | mm_l3 | train | 46,259 | 41.28% | 0.4128 | -13.03% | -25.27% | -31.03% |
| mm_l2 | mm_l3 | train | 83,504 | 28.18% | 0.2762 | -1.78% | -23.00% | -32.42% |
| light | mm_l2 | train | 4,847 | 35.77% | 0.3826 | -22.67% | -28.87% | -32.86% |
| mm_l2 | mm_l2 | train | 93,922 | 28.63% | 0.2847 | -6.56% | -24.79% | -32.87% |

## Tier A #3 — multi-wallet taker cascade in 15s window (per condition+side)

| cascade | split | fills | win % | avg price | ROI 0c | ROI 1c | ROI 2c |
|---|---|---:|---:|---:|---:|---:|---:|
| cascade | test | 51,902,870 | 50.50% | 0.5042 | -0.73% | -5.84% | -9.34% |
| cascade | train | 6,481,040 | 48.08% | 0.4786 | -1.43% | -7.26% | -11.02% |
| isolated | test | 644,325 | 58.81% | 0.5842 | -1.02% | -9.48% | -13.25% |
| isolated | train | 861,350 | 57.77% | 0.5719 | 1.49% | -5.21% | -8.94% |
| pair | test | 757,807 | 66.61% | 0.6596 | -2.11% | -6.93% | -9.63% |
| pair | train | 1,027,560 | 56.68% | 0.5623 | -0.91% | -5.90% | -9.16% |
| small_group | test | 2,290,400 | 62.63% | 0.6221 | -2.14% | -6.75% | -9.58% |
| small_group | train | 2,114,135 | 53.80% | 0.5339 | -0.64% | -5.99% | -9.46% |

## Tier A #4 — time-of-day session (UTC hour) by split

| utc hr | split | fills | win % | avg price | ROI 2c |
|---:|---|---:|---:|---:|---:|
| 0 | test | 2,043,655 | 50.94% | 0.5097 | -7.10% |
| 0 | train | 357,758 | 50.45% | 0.5025 | -8.61% |
| 1 | test | 2,147,907 | 51.40% | 0.5117 | -8.73% |
| 1 | train | 362,354 | 50.63% | 0.5031 | -13.99% |
| 2 | test | 2,144,434 | 51.21% | 0.5119 | -10.29% |
| 2 | train | 365,356 | 50.70% | 0.5039 | -11.32% |
| 3 | test | 2,178,788 | 51.11% | 0.5102 | -11.53% |
| 3 | train | 379,486 | 50.09% | 0.4985 | -5.95% |
| 4 | test | 2,173,778 | 50.86% | 0.5084 | -5.13% |
| 4 | train | 373,598 | 50.36% | 0.4996 | -8.98% |
| 5 | test | 2,084,669 | 50.99% | 0.5102 | -7.59% |
| 5 | train | 368,489 | 50.69% | 0.5030 | -10.73% |
| 6 | test | 2,134,952 | 51.34% | 0.5122 | -9.67% |
| 6 | train | 428,223 | 51.35% | 0.5067 | -11.34% |
| 7 | test | 2,234,382 | 51.59% | 0.5140 | -10.35% |
| 7 | train | 433,212 | 51.22% | 0.5060 | -10.15% |
| 8 | test | 2,205,255 | 51.39% | 0.5140 | -8.11% |
| 8 | train | 467,808 | 51.17% | 0.5070 | -9.90% |
| 9 | test | 2,317,828 | 51.16% | 0.5116 | -14.22% |
| 9 | train | 452,696 | 50.24% | 0.5056 | -16.69% |
| 10 | test | 2,496,699 | 51.24% | 0.5109 | -8.93% |
| 10 | train | 481,723 | 50.56% | 0.5041 | -9.52% |
| 11 | test | 2,450,445 | 51.22% | 0.5123 | -9.07% |
| 11 | train | 463,604 | 51.23% | 0.5079 | -14.33% |
| 12 | test | 2,537,549 | 51.11% | 0.5120 | -10.79% |
| 12 | train | 489,287 | 50.96% | 0.5083 | -5.90% |
| 13 | test | 2,621,674 | 51.23% | 0.5133 | -8.21% |
| 13 | train | 513,749 | 50.70% | 0.5058 | -10.79% |
| 14 | test | 2,623,555 | 51.67% | 0.5130 | -7.69% |
| 14 | train | 515,445 | 50.78% | 0.5018 | 0.07% |
| 15 | test | 2,811,787 | 51.57% | 0.5132 | -9.57% |
| 15 | train | 481,423 | 51.10% | 0.5088 | -12.17% |
| 16 | test | 2,578,658 | 51.31% | 0.5126 | -8.27% |
| 16 | train | 540,864 | 50.67% | 0.5055 | -7.97% |
| 17 | test | 2,438,504 | 51.34% | 0.5126 | -10.63% |
| 17 | train | 484,024 | 51.60% | 0.5096 | -9.56% |
| 18 | test | 2,376,308 | 51.40% | 0.5133 | -12.79% |
| 18 | train | 476,078 | 50.78% | 0.5067 | -10.30% |
| 19 | test | 2,411,443 | 51.64% | 0.5135 | -15.77% |
| 19 | train | 444,806 | 51.22% | 0.5075 | -13.07% |
| 20 | test | 2,336,630 | 51.82% | 0.5133 | -14.01% |
| 20 | train | 449,038 | 50.96% | 0.5071 | -10.59% |
| 21 | test | 2,113,819 | 51.22% | 0.5108 | -9.12% |
| 21 | train | 412,946 | 50.96% | 0.5080 | -12.30% |
| 22 | test | 2,025,399 | 51.34% | 0.5144 | 3.78% |
| 22 | train | 377,985 | 51.03% | 0.5067 | -12.71% |
| 23 | test | 2,107,284 | 51.28% | 0.5103 | -9.57% |
| 23 | train | 364,133 | 51.24% | 0.5079 | -14.93% |

## Tier B #5 — ETH/SOL conditioned on BTC prior-minute return state

| symbol | split | btc state | fills | win % | avg price | ROI 2c |
|---|---|---|---:|---:|---:|---:|
| ETH | test | btc_down | 1,374,601 | 51.20% | 0.5096 | -11.38% |
| ETH | test | btc_flat | 10,057,532 | 51.03% | 0.5088 | -9.71% |
| ETH | test | btc_up | 1,379,891 | 51.05% | 0.5095 | -12.41% |
| ETH | train | btc_down | 529,783 | 50.79% | 0.5052 | -12.52% |
| ETH | train | btc_flat | 2,127,013 | 50.37% | 0.5018 | -11.23% |
| ETH | train | btc_up | 554,718 | 50.90% | 0.5070 | -8.92% |
| SOL | test | btc_down | 453,454 | 50.60% | 0.5056 | -11.11% |
| SOL | test | btc_flat | 3,406,036 | 50.63% | 0.5040 | -12.27% |
| SOL | test | btc_up | 452,479 | 50.93% | 0.5065 | -12.91% |
| SOL | train | btc_down | 118,739 | 48.29% | 0.4808 | -17.85% |
| SOL | train | btc_flat | 450,276 | 48.77% | 0.4862 | -15.60% |
| SOL | train | btc_up | 123,655 | 48.50% | 0.4828 | -11.28% |

## Tier B #6 — lead-band breakdown (final-15s vs others) by split

| lead | split | fills | win % | avg price | ROI 2c |
|---|---|---:|---:|---:|---:|
| 120_to_300s | test | 17,304,387 | 51.59% | 0.5149 | -10.13% |
| 120_to_300s | train | 3,527,388 | 51.23% | 0.5085 | -12.98% |
| 15_to_30s | test | 1,024,899 | 53.13% | 0.5306 | -13.35% |
| 15_to_30s | train | 220,173 | 52.13% | 0.5180 | -14.96% |
| 300_to_600s | test | 29,357,660 | 50.61% | 0.5053 | -7.82% |
| 300_to_600s | train | 4,990,783 | 50.14% | 0.4989 | -6.62% |
| 30_to_60s | test | 2,205,161 | 53.29% | 0.5309 | -12.30% |
| 30_to_60s | train | 513,329 | 52.04% | 0.5173 | -13.98% |
| 60_to_120s | test | 4,997,285 | 52.92% | 0.5274 | -13.18% |
| 60_to_120s | train | 1,070,462 | 52.16% | 0.5181 | -15.33% |
| final_5_to_15s | test | 706,010 | 53.68% | 0.5350 | -15.92% |
| final_5_to_15s | train | 161,950 | 51.79% | 0.5141 | -17.15% |

## Tier B #11 — price-level expansion (3.5-5.5c live band vs alternatives)

| price band | split | fills | win % | avg price | ROI 2c |
|---|---|---:|---:|---:|---:|
| 10-20c | test | 5,324,039 | 13.97% | 0.1444 | -15.42% |
| 10-20c | train | 938,491 | 13.20% | 0.1432 | -19.73% |
| 20c+ | test | 43,776,506 | 62.89% | 0.6265 | -3.78% |
| 20c+ | train | 8,154,946 | 63.29% | 0.6269 | -3.21% |
| 3.5-5.5c | test | 1,270,065 | 4.24% | 0.0452 | -35.07% |
| 3.5-5.5c | train | 263,427 | 3.77% | 0.0450 | -42.16% |
| 5.5-8c | test | 1,126,866 | 5.76% | 0.0649 | -32.27% |
| 5.5-8c | train | 207,034 | 5.39% | 0.0648 | -36.46% |
| 8-10c | test | 1,068,502 | 7.62% | 0.0850 | -27.48% |
| 8-10c | train | 184,642 | 7.46% | 0.0848 | -28.91% |
| <3.5c | test | 3,029,424 | 1.82% | 0.0182 | -54.41% |
| <3.5c | train | 735,545 | 1.81% | 0.0183 | -54.13% |

## Tier C #12 — realized 60m volatility decile (strictly prior bars)

Decile 1 = lowest volatility, decile 10 = highest. GLM proposed low-vol; DeepSeek R1 proposed high-vol. Read both ends.

| decile | split | fills | win % | avg vol | ROI 2c |
|---:|---|---:|---:|---:|---:|
| 1 | test | 6,352,141 | 51.37% | 0.0003 | -9.81% |
| 1 | train | 255,808 | 50.39% | 0.0004 | -12.52% |
| 2 | test | 6,182,703 | 51.35% | 0.0005 | -7.37% |
| 2 | train | 425,246 | 51.41% | 0.0006 | -9.18% |
| 3 | test | 5,974,850 | 51.34% | 0.0007 | -6.26% |
| 3 | train | 633,099 | 51.10% | 0.0007 | -9.26% |
| 4 | test | 5,817,221 | 51.36% | 0.0009 | -10.42% |
| 4 | train | 790,728 | 51.10% | 0.0009 | -9.31% |
| 5 | test | 5,656,062 | 51.34% | 0.0010 | -9.82% |
| 5 | train | 951,887 | 50.88% | 0.0010 | -8.23% |
| 6 | test | 5,492,722 | 51.12% | 0.0012 | -6.23% |
| 6 | train | 1,115,227 | 51.02% | 0.0012 | -10.78% |
| 7 | test | 5,352,536 | 51.23% | 0.0015 | -10.65% |
| 7 | train | 1,255,413 | 50.83% | 0.0015 | -10.73% |
| 8 | test | 5,090,019 | 51.21% | 0.0019 | -10.17% |
| 8 | train | 1,517,929 | 50.81% | 0.0019 | -10.67% |
| 9 | test | 5,000,804 | 51.43% | 0.0026 | -14.44% |
| 9 | train | 1,607,144 | 50.81% | 0.0026 | -11.68% |
| 10 | test | 4,676,344 | 51.39% | 0.0049 | -9.85% |
| 10 | train | 1,931,604 | 50.68% | 0.0050 | -10.30% |

## Tier D #14/#15 — post-fill 1m return (RESEARCH VALIDATOR ONLY, NOT AN ENTRY GATE)

**WARNING — RESEARCH VALIDATOR ONLY.** This uses post-fill 1m data (the bar containing the fill plus the next bar). It cannot be used as an entry rule because the bot does not know post-fill data at decision time. This table is provided to characterise *which* fills won, not to produce a tradeable filter.

**KNOWN BUG IN TABLE BELOW:** Fill counts are inflated due to a many-to-many join on `(condition_id, fill_ts)` when multiple fills share the same block timestamp. Win-rate and ROI columns are still ratios so their *ranking* is correct, but the absolute fill counts (`506,725,295` etc.) are wrong — true total in the lead 5-600s window is `66,079,487`. Fix is a 1-to-1 join via `(maker_addr, taker_addr, condition_id, fill_ts)`. Will be patched in a follow-up if Tier D becomes the focus.

| post state | split | fills | win % | avg price | ROI 2c |
|---|---|---:|---:|---:|---:|
| post_down | test | 506,725,295 | 50.64% | 0.5064 | -0.80% |
| post_down | train | 40,963,660 | 50.54% | 0.5011 | -2.76% |
| post_up | test | 506,878,181 | 50.72% | 0.5063 | -2.53% |
| post_up | train | 41,064,711 | 50.52% | 0.5007 | -3.50% |
| true_flat | test | 1,536,849,676 | 50.62% | 0.5060 | -10.02% |
| true_flat | train | 65,951,804 | 50.64% | 0.5029 | -13.26% |

## How to read these tables

1. A hypothesis is **supported** if a conditional cell beats baseline by `>5pp` win rate AND by `>10pp` net ROI 2c, AND the lift is present in BOTH `train` and `test`.
2. A hypothesis is **rejected** if train shows lift but test does not, or if test ROI is negative.
3. Sample sizes below `1,000` are flagged. Below `100` is unreliable.
4. Tier D post-fill rows must NEVER be used as entry rules — they only validate the existence of a winning subset post-hoc.

## Next steps

1. Operator review of which features pass the supported gate above.
2. For supported features, run Script 2 (recorder microstructure validation) on Bot G's own forward fills to confirm the lift translates from Becker conditions to Bot G's actual fill conditions.
3. Only then propose any ADR. No paper or live parameter change is authorized from this report alone.
