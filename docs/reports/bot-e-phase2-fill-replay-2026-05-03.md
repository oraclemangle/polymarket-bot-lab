# Bot E Phase 2 Fill Replay Report — 2026-05-03

**Status:** Complete for the first 24h copied-snapshot run.  
**Scope:** Read-only analysis. No Bot E runtime settings, thresholds, sizing,
services, or live-money posture changed.

## Snapshot

Window:

- Replay window: `2026-05-02T13:11:03.188Z` to
  `2026-05-03T13:11:03.188Z`.
- Recorder slice warmup starts at `2026-05-02T12:51:03.188Z`.

Copied-snapshot inputs:

- Remote recorder slice:
  `data/phase2_snapshots/bot_e_phase2_recorder_24h_20260503T131103Z.db`
- Remote main slice:
  `data/phase2_snapshots/bot_e_phase2_main_24h_20260503T131103Z.db`

Local report artifacts:

- `data/phase2_snapshots/bot_e_phase2_replay_24h_20260503T131103Z.json`
- `data/phase2_snapshots/bot_e_phase2_replay_24h_20260503T131103Z.csv`
- `data/phase2_snapshots/bot_e_phase2_manifest_24h_20260503T131103Z.json`

Slice contents:

| Table | Rows |
|---|---:|
| recorder `pm_events` | 180,611 |
| recorder `cex_trades` | 2,342,761 |
| recorder `markets` | 2,624 |
| main `orders` | 29 |
| main `trades` | 31 |
| main `books` | 2,060 |

The full production DBs were not copied. The first full-copy route was
rejected because production `bot_e_recorder.db` is about 31.9 GB and
`main.db` is about 8.4 GB. The final run used bounded copied slices only.

## Headline Results

| Row set | Rows | Filled | Fill rate | 30s adverse | 60s adverse | 300s adverse |
|---|---:|---:|---:|---:|---:|---:|
| Actual Bot E paper orders (`main_order`) | 29 | 15 | 51.7% | 9/14 = 64.3% | 7/13 = 53.8% | n/a |
| Optimistic replay signals (`replay_signal`) | 241 | 137 | 56.8% | 52/120 = 43.3% | 45/114 = 39.5% | 9/24 = 37.5% |

Interpretation:

- The actual paper-order path breaches the existing 60% 30s adverse-selection
  stop line on this slice: `64.3%`.
- The optimistic replay ceiling looks less toxic, but it is not the live-like
  execution path. It fills on recorder last-trade evidence and does not prove
  queue position.
- Actual fill rate is acceptable on this slice (`51.7%`), so the immediate
  failure mode is fill quality, not just absence of fills.

## Actual Paper Orders

Actual `main_order` rows:

| Slice | Orders | Filled | 30s adverse |
|---|---:|---:|---:|
| BUY_YES | 25 | 11 | 5/10 = 50.0% |
| BUY_NO | 4 | 4 | 4/4 = 100.0% |

By maker-limit bucket:

| Maker limit | Orders | Filled | 30s adverse |
|---|---:|---:|---:|
| 25-50c | 7 | 6 | 6/6 = 100.0% |
| 50-75c | 11 | 5 | 3/5 = 60.0% |
| 75c+ | 11 | 4 | 0/3 = 0.0% |

Depth/capacity on actual orders:

- Depth samples: `24`.
- Median depth notional: `$4.63`.
- At least `$25` depth: `7/24`.
- At least `$50` depth: `6/24`.
- Filled-order median depth: `$23.22`.
- Filled-order median fill delay: `22.1s`.

Actual-order read:

- BUY_NO fills are the most concerning part of this slice: `4/4` filled and
  `4/4` moved against Bot E within 30s.
- Low/mid-priced fills are toxic. 25-50c filled often but every measured fill
  moved against Bot E at 30s.
- High-priced orders are less toxic in the measured 30s window, but their
  payoff asymmetry and thin depth still need EV treatment before they can be
  considered useful.

## Optimistic Replay Signals

Replay signal rows:

| Slice | Signals | Filled | 30s adverse | Labelled WR | Filled labelled WR |
|---|---:|---:|---:|---:|---:|
| All replay signals | 241 | 137 | 52/120 = 43.3% | 116/181 = 64.1% | 60/104 = 57.7% |
| BUY_YES | 109 | 68 | 22/57 = 38.6% | 58/86 = 67.4% | n/a |
| BUY_NO | 132 | 69 | 30/63 = 47.6% | 58/95 = 61.1% | n/a |

By maker-limit bucket:

| Maker limit | Signals | Filled | 30s adverse | Labelled WR |
|---|---:|---:|---:|---:|
| <25c | 25 | 20 | 12/16 = 75.0% | 2/9 = 22.2% |
| 25-50c | 54 | 37 | 18/33 = 54.5% | 8/45 = 17.8% |
| 50-75c | 78 | 38 | 15/32 = 46.9% | 51/67 = 76.1% |
| 75c+ | 84 | 42 | 7/39 = 17.9% | 55/60 = 91.7% |

Replay-signal read:

- Signal-only labels look strong in higher-price buckets, but that can be
  mostly market price/base-rate rather than a Bot E edge.
- Low-price buckets are bad in both directions: poor labelled WR and high
  adverse movement.
- The optimistic replay path understates the toxicity seen in actual paper
  orders.

## Verdict

Phase 2 does not produce a Bot E edge claim.

The current evidence says:

1. Bot E can still get fills.
2. Actual fills are too toxic on this 24h slice.
3. The optimistic replay ceiling looks materially better than actual order
   flow, so it cannot be used alone for tuning.
4. A possible narrow edge, if any, is more likely in high-probability/high-price
   buckets, but EV must account for payoff asymmetry, fees, no-fills, cancels,
   and thin depth before that bucket is investable.

This keeps Bot E in paper-only research mode. The next useful work is Phase 3:
compute EV and missed-winner/missed-loser accounting on the actual-order and
replay-signal rows.

## Next Action

Phase 3 should consume
`data/phase2_snapshots/bot_e_phase2_replay_24h_20260503T131103Z.json` and add:

- realised/labelled EV by row type, side, maker-limit bucket, and depth bucket;
- filled-vs-unfilled outcome split;
- missed-winner and avoided-loser counts;
- fee/slippage sensitivity;
- conservative queue haircut against the optimistic replay fills.
