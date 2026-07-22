# Fleet Capacity First Pass

**Date:** 2026-05-01
**Status:** First pass, now supplemented by the 2026-05-01 production
snapshot in `docs/reports/fast-roi-production-2026-05-01.md`.
**Purpose:** Make ROI capacity visible before choosing which bot gets the next
engineering dollar.

## Key Correction

Trade count is not capacity. Capacity is:

```
capital deployed per order * concurrent positions * turnover per month
```

For longer-hold bots, bankroll lock-up dominates. For short-horizon bots,
fees, slippage, fill quality, and adverse selection dominate.

## Fast-ROI Priority Update

Fast ROI is now ranked separately from strategic moat:

1. **Bot E** gets the first fast-ROI sprint because 15-minute markets can turn
   capital quickly if maker fills are not toxic.
2. **Bot G Prime** runs as the fast challenger because turnover is fast but
   outlier risk is high.
3. **Bot D** is constrained to the daily/low-lock-up subset until weekly
   capital lock-up and depth are quantified. Bot D still remains the preferred
   first real-wallet candidate track once those gates clear.
4. **Bot F** contributes crowd-sensor functions only.
5. **Bot B** continues as background moat work, not fast ROI.

## Bot D: Weather

**Likely bottleneck:** capital lock-up and thin weather books.

Working assumptions to verify:

- `$2,000` hot-wallet cap.
- `$25-$50` meaningful ROI-live order size.
- Daily weather contracts resolve in 1-2 days; weekly contracts can lock
  capital 5-7 days.
- If practical depth permits only 10-20 concurrent `$50` positions, deployed
  notional is `$500-$1,000`, not the full hot wallet.

Rough monthly turnover examples:

| Hold time | Concurrent capital | Monthly turnover |
|---:|---:|---:|
| 1 day | `$1,000` | about `$30,000` |
| 3 days | `$1,000` | about `$10,000` |
| 5 days | `$1,000` | about `$6,000` |
| 7 days | `$1,000` | about `$4,300` |

At `10%` ROI on deployed turnover, the difference between 1-day and 7-day
hold time is the difference between `$3,000/month` theoretical gross and
`$430/month` theoretical gross before slippage, losses, and idle capital.

**Capacity gate:** Bot D cannot be the primary ROI path unless it can deploy at
least `$500-$1,000` concurrently without destroying edge through slippage.

**Production read 2026-05-01:** Bot D had zero fills in the 24h fast-ROI
report, `5` fresh paper-open orders, and `937` NWS veto events. The follow-up
wallet-readiness report found `15` open paper orders worth `$321.33`: `13`
daily/low-lock-up orders worth `$271.34` and `2` weekly-lock-up orders worth
`$50.00`. It also found `8` stale orders and `3` stale open positions. The
real-wallet path is therefore daily/weekly split plus stale-open
reconciliation, not generic loosening.

## Bot E: 15-Minute Microstructure

**Likely bottleneck:** adverse selection, not bankroll.

Bot E can generate many decisions per day, but profitable capacity requires:

- maker fill rate high enough to matter;
- adverse movement after fill below the edge threshold;
- reward subsidy reconciled separately;
- no reliance on taker orders in crypto fee conditions.

**Capacity gate:** show net EV after maker fills, cancels, post-fill adverse
move, and reward/no-reward scenarios at `$25` and `$50` order sizes.

**Production read 2026-05-01:** Bot E generated `40` fills and `$185.88`
notional in the 24h fast-ROI report, but the cancel autopsy showed `61-65%`
30s adverse movement in fill scenarios. The next tuning target is fill quality,
not more aggressive TTL/offset.

## Bot G Prime: Final-Window Tails

**Likely bottleneck:** jackpot/outlier dependence and oracle noise.

The current 4c-8c Prime cohort has better flow than archived G variants, but
capacity is probably small. Price bands this low magnify every slippage and
oracle mismatch error.

**Capacity gate:** no live-capital packet unless Prime remains positive after
excluding the largest one and largest two wins, with at least 100 closed Prime
positions or a Bayesian posterior that justifies promotion earlier.

**Production read 2026-05-01:** Bot G Prime matched `14` closed round trips
with `+98.7%` headline ROI, but ex-largest-win ROI is `-100.0%`. Keep running
for data; do not promote.

## Bot B: Oraclemangle / UMA Dispute-Risk

**Likely bottleneck:** scorer ownership and market cadence, not public
replicability.

Bot B has the highest ceiling because it can trade across many UMA-resolved
categories and uses the only genuinely private moat in the fleet. Capacity
depends on how many markets pass:

- dispute-risk gate;
- model-vs-market edge gate;
- confidence/calibration gate;
- depth and volume gates.

**Capacity gate:** once local scoring is restored, report eligible markets per
day, average depth at intended order size, and expected monthly turnover at
`$25/$50/$100` order sizes.

## Bot F: Crowd Sensor

**Likely bottleneck:** not capital, but signal truth.

Bot F does not need live capital to add value. Its capacity is measured by how
often its signal improves another bot's decision:

- avoided losing trades;
- confirmed winning trades;
- fade/crowd reversal opportunities;
- reduction in adverse selection.

**Capacity gate:** show cross-bot EV uplift, not standalone mirror P&L.
