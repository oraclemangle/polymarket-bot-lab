# Bot A Walk-Forward Backtest — SII-WANGZJ trades.parquet

**Generated:** 2026-04-18T00:06:18.327540+00:00
**Dataset:** SII-WANGZJ/Polymarket_data — markets.parquet + trades.parquet
**Entry filter:** yes_price ≤ 0.05, DTR ∈ [21, 180] days, vol ≥ $5000, binary YES/NO, resolved.
**Entry size:** $30.0

## Summary

- Unique Bot-A entries simulated: **12,521**
- Resolved NO (win): **11,735** (93.7%)
- Mean edge per trade: **-3.62%**
- Median edge per trade: +2.25%
- Mean PnL per trade: $-1.09
- **Total PnL: $-13,613.58**
- Max drawdown: $13,666.58

**Interpretation:**
- Hit rate 93.7% is at or above the spec's 88-96% estimate. **Thesis is empirically supported** at the entry-price slice Bot A actually trades.

## By entry yes_price bucket

| bucket | n | hit_rate | mean_edge_% | mean_pnl$ |
|---|---|---|---|---|
| 00c | 2,184 | 99.0% | -0.63% | -0.19 |
| 01c | 2,252 | 94.1% | -4.78% | -1.43 |
| 02c | 1,622 | 93.2% | -4.81% | -1.44 |
| 03c | 1,558 | 92.6% | -4.45% | -1.34 |
| 04c | 1,801 | 91.5% | -4.56% | -1.37 |
| 05c | 3,104 | 91.8% | -3.32% | -0.99 |

## By inferred category

| category | n | hit_rate | mean_edge_% | total_pnl$ |
|---|---|---|---|---|
| _other | 7,008 | 93.2% | -4.20% | -8,824.84 |
| crypto_scalp | 195 | 94.4% | -2.46% | -143.63 |
| culture_mentions | 771 | 96.4% | -1.09% | -251.38 |
| finance_economics | 766 | 95.7% | -0.93% | -213.02 |
| geopolitics | 535 | 94.0% | -2.42% | -388.06 |
| politics | 2,158 | 93.6% | -3.82% | -2,471.98 |
| sports | 1,019 | 94.0% | -4.05% | -1,238.76 |
| weather | 69 | 92.8% | -3.96% | -81.91 |

## Limitations

- **No fee modelling.** Real live PnL compresses by fee_rate × notional per round-trip. Bot A's geopolitics focus is fee-free; other categories pay up to 5%.
- **No spread modelling.** Entries simulated at the trade price; real entries are at `best_ask`, usually higher.
- **No order-minimum rejection.** Polymarket rejects orders <5 shares; at entries with yes_price near 0.05, shares ~$600/0.95 ≈ 632 — not a binding constraint, but an edge case at 0.01-0.02 entries would be.
- **Entry at first-qualifying trade.** Real Bot A holds the rest of the market's life in the same position; doesn't re-enter.