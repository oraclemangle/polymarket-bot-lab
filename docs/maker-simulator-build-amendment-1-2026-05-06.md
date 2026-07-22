# Maker Simulator Build — Amendment 1: Manipulation Defense

**Date:** 2026-05-06
**Status:** AMENDMENT to
[docs/maker-simulator-build-brief-2026-05-06.md](maker-simulator-build-brief-2026-05-06.md).
Apply to the in-progress Phase B2 build.
**Audience:** The session currently building
`scripts/maker_simulator_paper.py`.
**Authority:** Per `OQ-083` and the original brief, no service/runtime/
cap/wallet/order-path change is permitted. This amendment adds defensive
features only; nothing in it relaxes the existing constraints.

## Why this amendment exists

A trader source publicly stated that Polymarket short-term crypto markets
(BTC `5min` especially, but the same mechanism applies to BTC/ETH/SOL
`15min`) are being systematically manipulated:

1. Manipulators build large positions on cheap tails.
2. They push the underlying on Binance in the final seconds.
3. Polymarket's Chainlink oracle (heavily Binance-weighted) follows.
4. Cheap tails flip from `~3-5c` to `$1`, manipulators cash out.
5. **The makers selling those cheap tails are the prey** — extracted
   by claim above $50k/day on BTC `5min` alone.
6. Sophisticated MMs reportedly turn off near settlement, leaving
   naive makers as the residual liquidity providers.

This is the **literal failure mode** of the strategy our simulator is
testing. Our existing spec partially defends against it (cancel-latency
stress, CEX-direction cancel signal) but does not include:

- **Weekend / low-liquidity quarantine.** The most common manipulation
  windows.
- **Final-`60s` no-new-quote rule.** Our current spec only cancels
  *existing* quotes on adverse signal; new quotes can still post into the
  final-30s manipulation window.
- **Manipulator-cluster wallet detection.** Wallets/clusters running
  this play are trackable on-chain via repeat patterns; our existing
  adverse-selection diagnostic groups by cell, not by counterparty.
- **Cancel-latency gating threshold of `300ms` instead of `500ms`.** If
  manipulation prints land in the final `5-10 seconds`, a `500ms`
  cancel is too slow.

If we do not include these, the simulator will measure what naive
historical makers earned — the population that was being farmed —
rather than what a careful maker could earn forward. The reported ROI
would be optimistic by an unknown but potentially large margin.

## Spec changes

Apply each change to the indicated section of the original build brief.

### Change 1 — Quarantine extension (modifies §4.9)

Original: skip simulation during `reconnect`, `gaps`, `tick_size_change`,
stale-book windows.

**Add to the quarantine list:**

1. **Weekends.** Skip markets where `end_date_iso` falls on Saturday or
   Sunday in UTC. Tweet explicitly identifies weekends and low-liquidity
   periods as "borderline untradeable."
2. **Last `60s` quote-posting freeze.** Do not POST any new quote in the
   final `60` seconds of a market regardless of book state or CEX
   signal. Quotes already resting can remain (subject to the existing
   cancel rules). This is the period where manipulation prints land
   most aggressively.
3. **Low-trade-density periods.** Skip markets with fewer than `5`
   `last_trade_price` events on the *same token* in the prior `5
   minutes`. The tweet flags low-liquidity periods as
   manipulator-friendly.

Report quarantine breakdown by reason in the output. Add to the
`>5%` quarantine kill criterion: it now includes these new categories.

### Change 2 — Cancel-latency gate (modifies §4.6 and §8)

Original: kill criterion is "ROI flips negative under `500ms` cancel
delay."

**Replace with:**

> Acceptance gate: aggregate collateral dollar-minute ROI must remain
> `>0%` under `300ms` cancel-latency. Stress at `200ms`, `300ms`,
> `500ms`, `1000ms` (now four regimes; was three).
>
> Failure mode: if `300ms` cancel-latency flips ROI negative, the
> strategy is not viable in adversarial regimes regardless of average
> conditions. Report each regime separately in the output table.

Rationale: manipulation prints reportedly land in the final `5-10
seconds`. A `500ms` cancel is too slow when the manipulator is timing
the print to within `~1s` of close.

### Change 3 — Manipulator-cluster wallet detection (NEW §4.10)

Add a new subsection between `§4.9` (quarantine) and `§4.10` (the
existing collateral-dollar-minute metric, which becomes `§4.11`).

#### §4.10 — Manipulator-cluster wallet detection

For each `taker` wallet that filled at least once in the lookback,
compute over the **train half only** (Sep 2025 - Nov 2025):

```
last_60s_fills            = count of fills where lead_sec <= 60
last_60s_win_rate         = fraction of last_60s fills where
                            taker's side won
last_60s_pnl_usd          = sum of taker's per-fill PnL in last_60s
total_lookback_volume_usd = sum of fill sizes
```

Mark a wallet **toxic** if all of:
- `last_60s_fills >= 30` (sample threshold)
- `last_60s_win_rate >= 0.65` (well above the natural cheap-tail
  base rate of `~5%`; high WR concentrated in last `60s` is the
  manipulator signature)
- `last_60s_pnl_usd >= 1000` (filters tiny accidents)

Then on the **test half** (Dec 2025 - Jan 2026):

For each simulated quote, check if the actual filling taker (per the
Becker `taker` field on the historical print our simulator joined to)
is in the toxic set. If yes, treat that quote as **filled-but-toxic**.

Report two ROI numbers in the headline:

- `roi_all_fills` — including toxic-marked fills
- `roi_excluding_toxic` — excluding toxic-marked fills

The delta between them measures how much of the historical edge
disappears when we cleanly avoid the manipulator clusters.

**Important interpretation:** in the live setting, we cannot
*identify* a toxic wallet at fill time before the cancel decision —
we can only identify after the fact. So `roi_excluding_toxic` is an
upper bound on what a "perfect cluster avoidance" strategy would
earn. The simulator does not assume we can avoid them in real time.
The point is to measure the magnitude of the manipulation tax on the
historical numbers.

#### Optional extension (do this only if the basic version surfaces a
material delta)

Cluster wallets by:
- **Shared funding source.** Wallets that received their first USDC
  deposit from the same tx hash, within `48h`. Becker has `block_number`
  and `transaction_hash` on every fill; trace the funding chain via
  Polygon explorer if needed (out of scope for this script — note as a
  follow-up).
- **Coordinated timing.** Multiple wallets entering the same
  `condition_id` within `1s` on the same side.
- **Repeat appearance.** A wallet entering `>20` markets on the same
  side at the same approximate lead time.

For this build, the simple per-wallet detector is sufficient. Cluster
analysis is a follow-up if needed.

### Change 4 — Per-counterparty diagnostic (modifies §4.7)

Original adverse-selection diagnostic compares filled vs unfilled win
rates per cell.

**Add a third comparison:** within filled fills, group by counterparty
(`taker`) wallet. Report the win-rate distribution across the top `100`
fillers.

If a small number of wallets account for a disproportionate share of
fills AND have above-average win rate, that's the manipulation
signature. Report explicitly:

```
top_10_taker_wallets_share_of_fills      = X%
top_10_taker_wallets_avg_win_rate         = Y%
top_10_taker_wallets_avg_collateral_roi   = Z%
remaining_taker_wallets_avg_win_rate      = W%
remaining_taker_wallets_avg_collateral_roi = V%
```

If `X > 30%` and `Y - W > 10pp`, the strategy is fishing in a
manipulator-dominated pool. Document this in the verdict.

### Change 5 — Acceptance criteria (modifies §8)

Original `8` criteria. **Add three:**

| New criterion | Threshold |
|---|---|
| ROI excluding toxic-marked counterparty fills | `>0%` (otherwise the historical edge is purely manipulator-fed) |
| `300ms` cancel-latency ROI | `>0%` (raised from `500ms`) |
| Top-10 taker wallet concentration | `<30%` of fills, OR top-10 win rate gap from rest `<10pp` |

If `roi_all_fills` is positive but `roi_excluding_toxic` is negative or
flat, the strategy is **not viable** — the historical positive number
is the manipulator's contribution, not real edge.

### Change 6 — Output report sections (modifies §5.8)

Add to the output Markdown report:

- **Manipulation-defense section** with:
  - Quarantine breakdown by reason
  - Toxic-wallet-detection summary (count of toxic wallets, fills
    against them, share of total fills)
  - `roi_all_fills` vs `roi_excluding_toxic` table per cell
  - Per-counterparty top-10 distribution
  - Cancel-latency table at `200/300/500/1000ms`
  - Weekend exclusion stats (markets skipped, % of total)
- **Verdict-section update**: explicit yes/no to "does this strategy
  earn positive ROI excluding toxic-marked fills under `300ms`
  cancel-latency on weekday markets only?" That's the real question.

### Change 7 — Targeting (clarifies §4.3)

Original: UP-side `5.5-15c`, lead `300-600s` first.

**Reaffirm and tighten:**

- Lead `300-600s`. Do not post new quotes inside `60s` of close
  (per Change 1).
- The original spec's "secondary" UP-side `5.5-15c` lead `60-300s` is
  **demoted to research-only** for this amendment. Do not include it
  in primary acceptance criteria — that lead band is too close to the
  manipulation window to be the first cell tested.
- DOWN-side remains as control. If manipulation is a real driver,
  DOWN-side may show inverse ROI (manipulators may push DOWN sometimes
  too); a strong DOWN positive is suspicious.

## Implementation notes

### Wallet PnL computation for toxic detection

Becker fills give us `(taker_addr, condition_id, price, size, won)`. For a
taker buying a token at price `P`, taker PnL per share = `won - P`. So
for the toxic detector:

```python
# Train half only.
WITH train_takers AS (
  SELECT
    taker_addr,
    SUM(CASE WHEN lead_sec <= 60 THEN 1 ELSE 0 END) AS last_60s_fills,
    SUM(CASE WHEN lead_sec <= 60 AND won THEN 1 ELSE 0 END) AS last_60s_wins,
    SUM(CASE WHEN lead_sec <= 60 THEN
      shares * (CAST(won AS DOUBLE) - price) ELSE 0 END) AS last_60s_pnl_usd,
    SUM(notional_usd) AS total_volume_usd
  FROM fill_events
  WHERE fill_ts < TIMESTAMP '2025-12-01'
    AND taker_addr IS NOT NULL
  GROUP BY taker_addr
)
SELECT taker_addr
FROM train_takers
WHERE last_60s_fills >= 30
  AND CAST(last_60s_wins AS DOUBLE) / NULLIF(last_60s_fills, 0) >= 0.65
  AND last_60s_pnl_usd >= 1000;
```

This list is fixed at simulator-start. On the test half, mark each
fill where `taker_addr IN (toxic_set)`.

### Weekend filter

```python
# UTC weekend exclusion.
end_dow = EXTRACT(dow FROM end_date_iso AT TIME ZONE 'UTC')
# 0 = Sunday, 6 = Saturday in DuckDB DOW (verify in your duckdb version)
exclude_market = end_dow IN (0, 6)
```

Verify the DOW convention in your DuckDB version with a quick test.

### Final-60s no-new-quote rule

In the existing quote-posting logic in `§5.3`:

```python
# Don't post a new quote if remaining lead is below the floor.
if lead_sec_at_post < NEW_QUOTE_LEAD_FLOOR_SEC:
    continue  # quarantine: in manipulation window
```

Set `NEW_QUOTE_LEAD_FLOOR_SEC = 60` initially.

### Low-trade-density check

For each candidate quote at time `T_post` on token `K`:

```python
prior_5m_trade_count = count of last_trade_price events
                       on token K in [T_post - 300s, T_post]
if prior_5m_trade_count < 5:
    continue  # quarantine: low liquidity
```

### Cancel latency `300ms` regime

Add `300ms` to the `cancel-latency-ms` CLI default:

```python
parser.add_argument("--cancel-latency-ms", default="200,300,500,1000")
```

The `300ms` regime becomes the gating regime in acceptance criteria.

## Test additions

Add to `tests/test_maker_simulator_paper.py`:

1. **`test_weekend_exclusion`** — markets with `end_date_iso` on Sat/Sun
   are skipped; report fields show non-zero `weekend_exclusions`.
2. **`test_final_60s_no_new_quote`** — given a market where `lead_sec` at
   posting time is `30`, no quote is posted; quote count for that
   market is `0`.
3. **`test_low_trade_density_quarantine`** — given a synthetic token
   with `<5` trades in prior `5min`, the quote attempt is skipped.
4. **`test_toxic_wallet_detection`** — given a synthetic train set with
   one wallet meeting all three thresholds (`fills >= 30`, `WR >= 0.65`,
   `PnL >= $1000`), the wallet is in the toxic set; another wallet
   below the thresholds is not.
5. **`test_roi_excluding_toxic`** — given a test set where `30%` of
   fills are against a toxic wallet, `roi_all_fills` ≠
   `roi_excluding_toxic`, and the delta matches expected math.
6. **`test_300ms_cancel_latency_regime_present`** — the output JSON
   includes a `cancel_latency_300ms` entry alongside the `500ms` and
   `1000ms` regimes.

## Updated final checklist (replaces §13 of the original brief)

In addition to the original `14` checklist items, add:

- [ ] Weekend quarantine implemented and tested
- [ ] Final-`60s` no-new-quote rule implemented and tested
- [ ] Low-trade-density quarantine (`<5` trades in `prior 5min`)
      implemented and tested
- [ ] Toxic-wallet detector implemented (`>= 30` last-60s fills,
      `>= 65%` WR, `>= $1000` PnL)
- [ ] Test split tags fills as toxic-or-not based on train-derived set
- [ ] Cancel-latency stress at `200ms`, `300ms`, `500ms`, `1000ms`
      (four regimes, not three)
- [ ] Output report has new "Manipulation defense" section
- [ ] Output JSON includes `roi_all_fills` AND `roi_excluding_toxic`
      per cell
- [ ] Acceptance gate now requires:
  - `>0%` collateral dollar-minute ROI under `300ms` cancel-latency
  - `>0%` collateral dollar-minute ROI excluding toxic fills
  - Top-10 taker wallet concentration below `30%` OR win-rate gap
    below `10pp`

## Anti-instructions (additions to original §12)

In addition to the original `10` anti-instructions:

11. **Do not** assume manipulator-cluster avoidance is feasible in
    real time. The toxic detector measures historical magnitude
    only; in live, we'd need a different (faster) signal to
    identify toxicity at fill time.
12. **Do not** report `roi_all_fills` as the headline. The
    headline is `roi_excluding_toxic` with `300ms` cancel-latency.
13. **Do not** widen the quarantine list beyond what's specified
    here. Adding more aggressive filters reduces the strategy's
    addressable market and may push it below viable scale even
    though it earns positive ROI per fill.
14. **Do not** optimize for the `improve_best_ask_by_1_tick` ladder
    against this manipulation backdrop. Improving by `1` tick takes
    you below the manipulation-attractive prices and reduces fills
    against toxic counterparties — but it also reduces fills against
    everyone else proportionally. Report it as informational; the
    primary ladder remains `join_best_ask`.

## How to apply this amendment to the in-progress build

The amendment is additive. If you've already built:

1. **Skeleton + book reconstruction** — keep, no changes.
2. **Quote-ladder simulator** — add the final-`60s` floor before
   posting. Add weekend-DOW check at market enumeration.
3. **Fillability counting** — keep the lower-bound algorithm. Add a
   `taker_addr_filled` field on each fill so we can later mark toxic.
4. **Cancel-latency stress** — add the `300ms` regime to the existing
   `200/500/1000` set.
5. **Outcome resolution** — keep, no changes.
6. **Adverse-selection diagnostic** — extend with per-counterparty
   top-10 distribution.
7. **Aggregation + report** — add the manipulation-defense section,
   `roi_excluding_toxic` columns, weekend stats.

If you haven't built much yet: just incorporate this amendment into
the build from the start. The original brief plus this amendment is
the complete spec.

## What this amendment does NOT change

- The script is still `scripts/maker_simulator_paper.py` only — no
  runtime, no service, no `bots/maker_paper/` package.
- The script is still read-only against the recorder.
- `OQ-083` still gates any operating change until the simulator
  clears.
- Bot G stays as-is.
- Targeting remains UP-side `5.5-15c` lead `300-600s` primary.
- The fee model (`0%` maker, `0%` rebate base case) is unchanged.

## One-line summary

If the simulator clears with `roi_all_fills > 0%` under `500ms` cancel
but `roi_excluding_toxic ≤ 0%` under `300ms` cancel, **the historical
edge was the manipulator's tax on naive makers, not a real opportunity
for us.** This amendment makes the simulator capable of detecting that
case.
