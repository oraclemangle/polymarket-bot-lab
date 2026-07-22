# Maker Simulator Build Brief — Phase B2

**Date:** 2026-05-06
**Audience:** A future Claude/Codex session that builds this from cold.
**Status:** Spec only. No code, bot, service, paper parameter, live
parameter, cap, wallet, or order path may be modified by this build.
The output is one read-only Python script plus its report.
**Authority:** [docs/open-questions.md](open-questions.md) `OQ-083`
gates this work and blocks any runtime/service/dashboard/cap/wallet/
order-path change until the simulator clears.

---

## How to read this brief

You are a fresh session with full codebase access but no memory of
the prior research. This document tells you everything you need to
build the simulator without having to re-derive months of analysis.
File paths are repo-relative; grep or Read whatever you want for
deeper context.

Sections are ordered by what you need first. Read 1-4 before
starting. Sections 5-8 are the actual build. Sections 9-13 are
operational and quality-assurance.

---

## 1. One-paragraph context

Polymarket has 15-minute crypto Up/Down markets on BTC, ETH, and
SOL. Cheap-tail BUYING (the "Bot G" approach) has been exhaustively
falsified across `66M` Becker historical fills, multiple feature
filters, walk-forward splits, and a `19`-feature LightGBM model
(test AUC `0.86` but every conditional ROI bucket is essentially
zero or negative — the market is well-priced at the bucket level).
The only positive expected-value pocket surfaced anywhere in the
analysis is **maker-side cheap-tail SELLING**: posting an ask near
the cheap-tail price, collecting the premium upfront, paying out
only on the rare side-wins. Becker confirms `+1.21%` collateral ROI
on actual maker-sell rows in the `5.5-15c` band test split
(`766,459` fills); the strength concentrates on UP-side
(`+2.14%`) with DOWN-side near zero (`+0.28%`). Polymarket's
official docs confirm `0%` maker fees on crypto markets in May
2026, so the historical edge does not need a fee haircut. Your
job is to build a read-only **offline simulator** that models
realistic fillability with conservative lower-bound queue-ahead
fills, cancel-latency stress, and adverse-selection diagnostics —
and produces a clear yes/no answer on whether the historical edge
survives realistic execution.

## 2. Hard constraints (read these twice)

1. **Read-only.** No DB writes, no service restarts, no systemd
   edits, no config changes, no Bot G touches, no FV bot touches,
   no Bot D touches, no recorder touches, no dashboard touches.
2. **No runtime/service/package.** Output is one script
   `scripts/maker_simulator_paper.py` plus its Markdown+JSON report
   under `docs/reports/`. **Do not** create
   `bots/maker_paper/`, `systemd/polymarket-maker-paper.service`, or
   any equivalent runtime artifact in this build.
3. **OQ-083 gate.** Any service/wallet/cap/order-path change is
   explicitly blocked by `OQ-083` until the simulator report clears
   the acceptance criteria in section 8. Read it: lines 1289-1320 in
   [docs/open-questions.md](open-questions.md).
4. **Bot G stays as-is.** Operator instruction. Do not propose
   archive, do not edit any `bots/bot_g_longshot/` file, do not
   touch any `polymarket-bot-g-prime*` systemd unit. Bot G live
   continues at its current trajectory regardless of what this
   simulator finds.
5. **`$200` wallet cap mental model.** Solo UK operator. Do not
   build anything that implies institutional capital, multi-day
   margin, or external API integrations beyond what's already in
   the recorder.
6. **Audit rules apply (`OQ-081`).** Maker-side research lane
   acceptance still requires a forward paper trial after this
   simulator clears, plus a separate ADR before any live exposure.
   The simulator is one of three required gates, not the final
   answer.

## 3. The finding being validated

Source reports (read these in order before coding):

1. [docs/reports/maker-side-research-lane-validation-codex-2026-05-06.md](reports/maker-side-research-lane-validation-codex-2026-05-06.md)
   — **Codex's review is the spec.** This brief restates and
   amplifies it; if there's any conflict, Codex's spec wins.
2. [docs/reports/becker-maker-and-wallet-analysis-2026-05-06.md](reports/becker-maker-and-wallet-analysis-2026-05-06.md)
   — Phase A. Read the sections "ROI by price band" and "Maker-seller
   ROI by symbol × side × price band". Note that the headline
   tables are *counterfactual* (they compute seller economics for
   every fill, not actual maker-sell-only). Codex re-queried the
   parquet with `taker_buys=1` filter; those numbers are the truth.
3. [docs/reports/recorder-maker-side-validation-2026-05-06-the bot container.md](reports/recorder-maker-side-validation-2026-05-06-the bot container.md)
   — Phase B1. Small sample (`55` resolved markets, `9,884` trades)
   so this is supporting-only. The `>0.95/<0.05` resolution
   threshold has selection bias; you'll fix this with a sensitivity
   grid (see section 5.6).
4. [docs/reports/becker-lightgbm-taker-signal-2026-05-06.md](reports/becker-lightgbm-taker-signal-2026-05-06.md)
   — Phase D, the final taker rejection. Why we're not building
   another taker variant.

**The numbers you must beat (or fail to beat) in the simulator:**

| Cell | Becker test fills | Avg price | Collateral ROI |
|---|---:|---:|---:|
| Actual maker-sell `5.5-15c` all sides | `766,459` | `0.1006` | `+1.21%` |
| Actual maker-sell `5.5-15c` UP only | `381,976` | `0.1006` | **`+2.14%`** |
| Actual maker-sell `5.5-15c` DOWN only | `384,483` | `0.1006` | `+0.28%` |

Per-share E[P&L] formula at zero maker fees:
```
maker_sell_pnl_per_share = price - won
```
where `won` is `1` if the side resolved YES, `0` otherwise.

Collateral ROI = `maker_sell_pnl_per_share / (1 - price)`.

## 4. Codex-validated specifications (the authoritative spec)

Source: `docs/reports/maker-side-research-lane-validation-codex-2026-05-06.md`
sections "Required B2 Changes" (lines 242-259) and "Section 5 fillability
algorithm" (lines 146-169). The full Codex review is the source of truth;
this section restates it for ease of reference.

### 4.1 Quote ladders (three, side-by-side)

For each candidate market window, simulate three quote ladders
*independently*. Report results for each. Do not pick one — show
all three.

- **`join_best_ask`** — quote price = current best ask. Queue-ahead
  = current ask size at that price.
- **`improve_best_ask_by_1_tick`** — quote price = current best ask
  *minus one tick* (lower asking price; for a SELL, lower = more
  aggressive). Queue-ahead = `0` because the level is empty before
  we post.
- **`worse_than_best_ask_by_1_tick`** — quote price = current best
  ask *plus one tick*. Queue-ahead = sum of all ask depth at
  strictly cheaper prices, since they must trade through before we
  can fill.

Polymarket tick size is typically `0.001` (`0.1c`) for crypto Up/
Down markets. Confirm via the recorder's `tick_size_change` events
or from a `book` snapshot's level granularity.

### 4.2 Fee model

- Maker fee = `0` (confirmed against
  https://docs.polymarket.com/trading/fees, May 2026).
- Maker rebate = `0` in the base case. Track the program-dependent
  `~20%` rebate (per
  https://docs.polymarket.com/market-makers/maker-rebates) as
  *upside only*; do **not** include it in the gating ROI metric.
- Taker fees do not apply to your maker quote.

### 4.3 Targeting (in order)

1. **Primary:** UP-side `5.5-15c`, lead `300-600s` to start. This
   is where Phase A shows the strongest cell.
2. **Control:** DOWN-side same band/lead. Should show much weaker
   or negative ROI; serves as null-hypothesis check.
3. **Optional secondary** (only if primary clears): UP-side
   `5.5-15c`, lead `60-300s`; UP-side `15-30c` longer lead.

### 4.4 Outcome resolution priority

For each market, determine the winning token in this order:

1. **`market_resolved` event in `pm_events`** if present — use
   `winning_asset_id` from the payload.
2. **Price-threshold sensitivity grid:** report at three thresholds
   for transparency:
   - strict: winner `>=0.98`, loser `<=0.02`
   - baseline: winner `>=0.95`, loser `<=0.05`
   - inclusive: winner `>=0.90`, loser `<=0.10`
3. **Require both YES and NO consistency** when both tokens have
   late prints. Skip markets where YES and NO last-prints disagree.
4. Report counts of how many markets used each path.

### 4.5 Fillability — lower bound + upper bound

**Lower bound (the gating metric):** count only fills where:

1. The subsequent `last_trade_price` event prints at-or-through our
   ask price (i.e., for a SELL at price `P`, a buyer trade at
   price `>= P`).
2. Buyer-aggressive side (the trade represents an aggressive BUY).
3. After consuming queue-ahead volume from the same price level.

Cancellations do not create fills. Adverse cancellations of orders
ahead of us in queue *do* improve our position (we move up the
queue) but only count as a fill when a trade actually occurs.

**Upper bound:** allow `book`-event size depletion at our level to
count as possible fill. This is a capacity ceiling, not a
performance metric.

**Gate on the lower bound.** If the lower-bound report is not
positive, the strategy is not validated regardless of the upper
bound.

### 4.6 Cancel-latency stress

After a CEX-direction adverse signal (Binance moves toward our
short side by `>= X bps` in the last `Y seconds`, e.g. `3 bps`
in `30s`), simulate cancellation. Cancellation is not instant.
Run the simulator with three cancel-latency assumptions:

- `200ms`
- `500ms`
- `1000ms`

Any taker trade arriving during the cancel-latency window can fill
us. Report fill outcomes filtered by whether the cancellation was
in flight at trade time.

**Failure mode:** if cancel-latency `500ms` flips ROI negative,
that's a kill criterion (the gate is doing all the work, not the
strategy).

### 4.7 Adverse-selection diagnostic

For each filled vs unfilled quote in the same target cell (same
symbol × side × price band × lead bucket), compute:

- Win rate of the underlying side
- Collateral ROI

If filled quotes show systematically *worse* outcomes than the
unfilled population (i.e., we only fill on toxic flow), that's
the adverse-selection signal Bot G has been suffering. Report this
explicitly per cell.

### 4.8 ROI metrics — collateral dollar-minute is the headline

Per filled quote: `pnl = price - won` (per share, zero maker fee).

Per quote attempt:
- `attempted_collateral_dollar_minutes = (1 - price) × shares ×
  duration_resting_minutes`
- `quote_attempt_roi = total_pnl /
  total_attempted_collateral_dollar_minutes` (per quote attempt
  basis, including failed/cancelled attempts in denominator)

Also report:
- Per-fill collateral ROI (comparable to Phase A)
- Lower-bound and upper-bound fill rates as percentages of attempts
- Fill rate by ladder

The headline result is **collateral dollar-minute ROI under the
lower-bound fill model**. Everything else is supplementary.

### 4.9 Quarantine windows

Skip simulation during:

- `reconnect` events in `pm_events`
- Recorded `gaps` rows
- `tick_size_change` events (book reset)
- Stale-book windows: > `Y` seconds since last `book` or
  `price_change` event for the target token (use `Y = 30s` as
  default)

Report total minutes quarantined as a fraction of candidate-window
minutes. If quarantine exceeds `5%`, that's a kill criterion.

## 5. Build plan — phased

### 5.1 Phase 1 — Skeleton + market discovery

**Goal:** Connect to recorder DB, identify candidate markets,
verify they have outcome data.

Files: `scripts/maker_simulator_paper.py` (new).

Reuse patterns from
[scripts/recorder_maker_side_validation.py](../scripts/recorder_maker_side_validation.py)
for:
- `connect_ro(path)`
- `parse_iso_to_ms(iso)`
- `_wilson(wins, n)`
- Markets schema query

Add CLI args:
```
--recorder-db path  (default: /home/bot/polymarket-bot/data/bot_e_recorder.db)
--lookback-days 42
--target-band 5.5-15c
--target-lead-min-sec 300
--target-lead-max-sec 600
--cancel-latency-ms 200,500,1000
--cex-cancel-bps-threshold 3.0
--cex-cancel-window-sec 30
--out-md docs/reports/maker-simulator-paper-2026-05-06.md
--out-json docs/reports/maker-simulator-paper-2026-05-06.json
--label the bot container
```

Smoke-test: confirm `~50-200` resolved BTC/ETH/SOL 15m markets in
the lookback window (matches the prior B1 numbers).

### 5.2 Phase 2 — Book reconstruction

**Goal:** Rebuild a per-token L2 orderbook over time from `book`
snapshots and `price_change` deltas.

Recorder events you care about:
- `book` — full snapshot (treat as state reset)
- `price_change` — delta update
- `tick_size_change` — reset; book invalidated
- `reconnect` — reset; book invalidated

Algorithm:
```
state = empty book
for event in pm_events ordered by received_at_ms:
    if event_type == 'book':
        state = parse_book_snapshot(payload)
    elif event_type == 'price_change':
        state = apply_delta(state, payload)
    elif event_type in ('tick_size_change', 'reconnect'):
        state = empty book  # invalidated until next 'book'
    yield (timestamp, state)
```

Read the payloads to understand shape:
```sql
SELECT payload_json FROM pm_events
WHERE event_type IN ('book','price_change')
LIMIT 5;
```

Test: pick one market with known outcome. Reconstruct its book
over its 15-minute lifetime. Sanity-check that best ask + best bid
sum to `~1.00` at most timestamps (the no-arb constraint on paired
tokens).

### 5.3 Phase 3 — Quote-ladder simulator

**Goal:** For each candidate market, post three hypothetical
maker SELL quotes (join, improve, worse) at the entry of the
target window and track them.

Per-quote state:
- `posted_at_ms`
- `quote_price` (the price we asked for)
- `quote_size` (start at `5` shares — small fixed for simplicity)
- `queue_ahead_at_post` (computed from book state)
- `cumulative_queue_consumed`
- `status` (`open`, `filled`, `cancelled`, `expired`)

Quote-entry rules:
- Enter at `lead_sec = max_lead_sec` (e.g. `600s` before close)
- Quote sits until filled, cancelled, or market closes
- A market closes at `lead_sec = 0`

Cancellation triggers:
- CEX adverse signal (per 4.6)
- Lead time drops below `30s` and not yet filled

### 5.4 Phase 4 — Fillability counting

**Goal:** Determine whether each posted quote would have filled
under the lower-bound and upper-bound models.

For each quote, iterate `last_trade_price` events on the same token
in the time window from `posted_at_ms` to `(posted_at_ms +
duration_until_cancel_or_close)`.

**Lower-bound algorithm:**
```
queue_remaining = queue_ahead_at_post
for trade in token_trades_during_window:
    if trade.price < quote_price:
        continue  # didn't reach our ask
    # buyer-aggressive check: usually inferred from price > prior best ask
    if not is_buyer_aggressive(trade, prior_book_state):
        continue
    if queue_remaining > 0:
        queue_remaining -= trade.size
        if queue_remaining <= 0:
            # we got filled with the leftover
            quote.status = 'filled'
            quote.fill_size = -queue_remaining + ...  # leftover
            quote.fill_at_ms = trade.received_at_ms
            break
    else:
        quote.status = 'filled'
        ...
```

Also consume queue from cancellations of ahead-of-us orders, as
detected from `book`/`price_change` events that show ask size at
quote price decreasing without a corresponding trade.

**Upper-bound:** also count book-depletion (size at level → 0)
even without an explicit trade. Report separately.

### 5.5 Phase 5 — Cancel-latency stress

After your CEX-adverse-signal triggers a cancel intent at time
`T_cancel_intent`, the cancel actually lands at `T_cancel_intent +
latency`. Any trades during `[T_cancel_intent, T_cancel_intent +
latency]` that would have filled us *do* fill us.

Run the simulator three times with `latency_ms ∈ {200, 500, 1000}`
and tag each fill with which latency regime allowed it.

### 5.6 Phase 6 — Outcome resolution

Implement the priority order from section 4.4:

1. Search `pm_events` for `market_resolved` events with the
   condition_id. If found, use `winning_asset_id`.
2. If absent, sweep last `last_trade_price` for each token in the
   `[end_ms - 300s, end_ms + 300s]` window and apply the three
   thresholds.
3. Report a histogram of which path was used per market.

### 5.7 Phase 7 — Adverse-selection diagnostic

For each target cell (symbol × side × band × lead bucket × ladder),
compute:
- Win rate of fills (filled subset)
- Win rate of would-have-been-fills-but-didn't (unfilled candidate
  subset, e.g. quotes that never had a trade reach their level)

Compare. If filled-set win rate is materially below unfilled-set
win rate, you've measured adverse selection.

### 5.8 Phase 8 — Aggregation + report

Aggregate by:
- ladder (join / improve / worse)
- symbol × side
- price band × lead bucket
- cancel-latency regime
- resolution path

Output Markdown report with:
- Coverage section (markets, quote attempts, fills lower-bound,
  fills upper-bound)
- Fee assumption section (`0%` maker, rebate as upside only)
- Per-ladder summary (collateral dollar-minute ROI, fill rates,
  Wilson CIs)
- Per-cell tables matching the structure of
  `scripts/recorder_maker_side_validation.py` outputs
- Cancel-latency comparison table
- Adverse-selection diagnostic table
- Quarantine summary
- Resolution-path histogram
- Acceptance-gate check section (per section 8 of this brief)

Plus the JSON dump for downstream tooling.

## 6. Test plan

Before running the full simulator on the recorder:

### 6.1 Unit-level tests

Write `tests/test_maker_simulator_paper.py` (small) covering:
- `parse_book_snapshot` returns expected book given known payload
- `apply_delta` updates correctly
- `compute_queue_ahead` matches hand-calculated values for `join`,
  `improve`, `worse` ladders
- `lower_bound_fill_count` matches hand-calculated for synthetic
  trade sequences
- `cancel_latency_filter` includes/excludes correct trades

### 6.2 Smoke run on one market

Run the simulator against one specific resolved market with known
outcome. Print per-event book state. Manually verify quote behavior
matches expectation. Time-box `~5 minutes` of analyst time.

### 6.3 Sanity ranges

- Total quote attempts: roughly `n_markets × 3 ladders` (one quote
  per market per ladder)
- Lower-bound fill rate: probably `5-30%` per ladder at best-ask
  band; `0-10%` for the worse-by-one-tick ladder
- Upper-bound fill rate: 1.5-3× higher than lower bound
- Adverse selection: filled-set win rate likely *higher* than
  unfilled-set if our edge thesis is right (we collect premium more
  often than we pay out); if it's *lower*, that's the toxicity
  signal

If any of these are wildly outside the range, debug before running
the full lookback.

## 7. Run plan

### 7.1 Where it runs

**On the bot container.** The recorder DB is at
`/home/bot/polymarket-bot/data/bot_e_recorder.db` (`58 GB`).
Becker is on the the local workstation but Phase B2 doesn't need Becker — the
simulator runs against recorder data only.

Push the script via `pct exec`:
```
cat scripts/maker_simulator_paper.py |
  ssh hypervisor-host 'pct exec <ctid> -- bash -c "cat > /home/bot/polymarket-bot/scripts/maker_simulator_paper.py && chown bot:bot /home/bot/polymarket-bot/scripts/maker_simulator_paper.py"'

ssh hypervisor-host 'pct exec <ctid> -- sudo -u bot bash -c "cd /home/bot/polymarket-bot && .venv/bin/python -c \"import scripts.maker_simulator_paper\" && echo IMPORT_OK"'

ssh hypervisor-host 'pct exec <ctid> -- sudo -u bot bash -c "cd /home/bot/polymarket-bot && .venv/bin/python scripts/maker_simulator_paper.py --label the bot container --lookback-days 42 2>&1"'
```

Pull the report back:
```
ssh hypervisor-host 'pct exec <ctid> -- cat /home/bot/polymarket-bot/docs/reports/maker-simulator-paper-2026-05-06-the bot container.md' \
  > docs/reports/maker-simulator-paper-2026-05-06-the bot container.md
ssh hypervisor-host 'pct exec <ctid> -- cat /home/bot/polymarket-bot/docs/reports/maker-simulator-paper-2026-05-06-the bot container.json' \
  > docs/reports/maker-simulator-paper-2026-05-06-the bot container.json
```

### 7.2 Expected runtime

Estimate `30-90 minutes` on the bot container for `~50-200` resolved markets
× `3` ladders × `3` cancel-latency regimes × outcome resolution
sensitivity grid.

If runtime explodes, partition by symbol or by week and run in
chunks.

### 7.3 Safe to run multiple times

The script is read-only against the recorder. Re-runs are safe.
Idempotent on outputs (overwrites the report file).

## 8. Acceptance criteria

The simulator clears the gate **only if all of these hold on
the lower-bound fill model**:

| Criterion | Threshold |
|---|---|
| Total lower-bound fills (UP-side, `5.5-15c`, lead `300-600s`) | `>= 150` |
| Aggregate collateral dollar-minute ROI | `> 0%` |
| ROI under `500ms` cancel-latency stress | `> 0%` (does not flip negative) |
| Lower-bound / upper-bound fill ratio | `>= 0.33` |
| Quarantine fraction of candidate-window minutes | `< 5%` |
| Adverse-selection check: filled win rate vs unfilled | filled win rate `>= unfilled win rate − 5pp` |
| Per-cell minimum fills for any cell labelled `pass` | `>= 50` lower-bound fills |
| `improve_best_ask_by_1_tick` ladder ROI | not strictly required positive (depends on real maker behaviour) but report cleanly |
| DOWN-side as control | should be near zero or negative; if DOWN clearly beats UP, something is wrong with the simulator — debug |

If any single criterion fails, the simulator does not clear.
Report which criteria failed and why.

If the simulator clears, the next step is **a separate ADR**
proposing a paper-only research lane. That ADR is operator-decided;
not part of this build.

If the simulator does not clear, document the failure and update
`OQ-083` with the result. Maker direction is then closed.

## 9. Roll-out paths

### 9.1 If simulator clears (positive maker E[V] survives realistic execution)

1. Write a separate ADR proposing a maker-only paper research lane.
2. Build the paper bot itself (separate session/build) — this is
   not part of Phase B2.
3. Paper bot runs for `7-14` days on the recorder feed in dry-run
   mode.
4. Compare paper P&L to simulator-predicted P&L.
5. If forward paper still positive: write another ADR proposing
   live exposure with very small caps (`$50` initial, `$1`-per-quote
   size).
6. Operator approves or rejects each step explicitly.

### 9.2 If simulator does not clear

1. Update `OQ-083` with the failure diagnosis.
2. Maker direction is documented as closed (no positive-EV pocket
   identified anywhere on Polymarket cheap-tail markets at this
   granularity).
3. Operator decides what to do about Bot G live (currently `-73%`
   ROI; trajectory at-or-near archive trigger).
4. The historical analysis remains a reference for future research.

In either case, do not build a runtime, do not edit any service,
do not change any cap.

## 10. Files to read (priority order)

1. **This brief** in full.
2. [docs/reports/maker-side-research-lane-validation-codex-2026-05-06.md](reports/maker-side-research-lane-validation-codex-2026-05-06.md)
   — Codex's full validation. Section 5 (fillability) and the
   Required B2 Changes are the spec.
3. [docs/open-questions.md](open-questions.md) lines 1289-1320 (`OQ-083`)
   — the gate.
4. [docs/reports/becker-maker-and-wallet-analysis-2026-05-06.md](reports/becker-maker-and-wallet-analysis-2026-05-06.md)
   — Phase A findings.
5. [docs/reports/recorder-maker-side-validation-2026-05-06-the bot container.md](reports/recorder-maker-side-validation-2026-05-06-the bot container.md)
   — Phase B1 findings + the small-sample caveat.
6. [scripts/recorder_maker_side_validation.py](../scripts/recorder_maker_side_validation.py)
   — Reuse the connect-RO pattern, market query, outcome
   resolution, ROI helpers, table formatting.
7. [scripts/becker_maker_and_wallet_analysis.py](../scripts/becker_maker_and_wallet_analysis.py)
   — Reuse the maker-role classification SQL pattern (lines `~114-187`).
8. [bots/bot_e_recorder/schema.py](../bots/bot_e_recorder/schema.py)
   — Recorder schema details.
9. [bots/bot_e_recorder/capture.py](../bots/bot_e_recorder/capture.py)
   — How events are written; useful for understanding `payload_json`
   shapes.
10. [core/polymarket_ws.py](../core/polymarket_ws.py)
    — Public-channel events; payload structure for `book`,
    `price_change`, `last_trade_price`, etc.
11. Polymarket docs (open in browser, do not embed in code):
    - https://docs.polymarket.com/trading/fees
    - https://docs.polymarket.com/market-makers/maker-rebates
    - https://docs.polymarket.com/trading/orderbook
    - https://docs.polymarket.com/trading/orders/overview

## 11. Implementation gotchas (lessons from prior sessions)

### 11.1 DuckDB pitfalls

If you use DuckDB anywhere (likely for the resolution-grid
re-aggregation):

- **DECIMAL overflow.** When interpolating Python floats into SQL
  literals, DuckDB may treat them as `DECIMAL(18, n)`. Multiplying
  by an integer can overflow. Use explicit `CAST(... AS DOUBLE)`
  on both sides:
  ```sql
  CAST(prior_total AS DOUBLE) * 100.0 + CAST(50 AS DOUBLE) * CAST({pct:.6f} AS DOUBLE)
  ```
- **Window function in `GROUP BY`.** DuckDB rejects `NTILE(...) OVER
  (...)` directly in `GROUP BY`. Wrap in a CTE:
  ```sql
  WITH ranked AS (
      SELECT *, NTILE(5) OVER (ORDER BY x) AS quintile FROM t
  )
  SELECT quintile, ... FROM ranked GROUP BY quintile
  ```

### 11.2 SQLite recorder pitfalls

- The recorder DB is `~58 GB` on disk plus an `~18 GB` WAL.
  Read-only access is required:
  ```python
  con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
  ```
  Do not write. Do not run `VACUUM`. Do not run `ANALYZE`.
- `pm_events.payload_json` is a string. Parse with `json.loads`.
  Some payloads are nested objects, some are arrays; check the
  event type first.
- `received_at_ms` is integer milliseconds since UTC epoch. Treat
  consistently as `int`, not float.
- The recorder writes via best-effort queues
  ([bots/bot_e_recorder/capture.py](../bots/bot_e_recorder/capture.py)).
  Extreme load can drop events. The `gaps` table records detected
  drops; honor them in quarantine logic.

### 11.3 the bot container deployment

- the bot container is the homelab hypervisor container `105` named `longshot-bot`. SSH alias
  is `hypervisor-host` (the homelab hypervisor) plus `pct exec <ctid> -- ...`.
- Owner: user `bot`. Run scripts via `sudo -u bot`.
- Repo path on the bot container: `/home/bot/polymarket-bot/`. Venv at
  `/home/bot/polymarket-bot/.venv/`.
- After pushing a script, `chown bot:bot` so the `bot` user can
  read it.

### 11.4 Sample size sanity

- Recorder lookback `42` days yields `~150-200` candidate markets
  before resolution filtering, `~50-100` after. Be prepared for the
  sensitivity-grid to give different counts at different
  thresholds.
- `9,884` trades over `55` markets = `~180` trades per market on
  average (small market). Don't expect `1M`+ trade samples like
  Becker had.
- A handful of markets contain most of the trades; check the
  distribution.

### 11.5 Codex's caught Phase A bug to NOT replicate

`scripts/becker_maker_and_wallet_analysis.py` `_by_band_and_lead`
and `_by_band_symbol_side` (lines `306-308`, `346-348`) bucket all
`price < 0.055` as `'3.5-5.5c'` — this conflates `<3.5c` rows. Use
the correct split (separate `<3.5c` and `3.5-5.5c`) when reporting
your simulator's price-band breakdowns.

### 11.6 Wilson confidence intervals

For sample-size honesty in every reported win rate, include Wilson
95% CIs. Pattern from prior scripts:

```python
def wilson(wins, n, z=1.96):
    if n <= 0:
        return None, None
    p = wins / n
    denom = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denom
    margin = z * math.sqrt((p*(1-p) + z*z/(4*n))/n) / denom
    return centre - margin, centre + margin
```

A bucket "passes" only if the Wilson CI excludes the comparison
baseline (typically the unfilled-baseline win rate or the symbol-
neutral baseline).

## 12. What NOT to do

These would all violate the spec or the audit:

1. **Do not** create `bots/maker_paper/` package or any equivalent
   runtime directory. The script is the entire deliverable.
2. **Do not** create `systemd/polymarket-maker-*.service` or any
   service unit.
3. **Do not** edit any Bot G, Bot D, FV bot, recorder, watchdog,
   dashboard, or notify file. Those are outside scope.
4. **Do not** propose a paper bot, live bot, or wallet/cap change
   inside the simulator's report. The acceptance-gate output should
   be a yes/no verdict on the simulator alone.
5. **Do not** include maker rebates in the gating ROI. Track them
   as an upside note only.
6. **Do not** use the upper-bound fill model as the headline metric.
   It's a capacity ceiling, not validation.
7. **Do not** propose new taker-side hypotheses to test. The taker
   direction is closed. Phases 173, 177, 179, 182 cover the universe.
8. **Do not** propose Polymarket protocol changes, Kalshi
   arbitrage, copy-trading, or any strategy outside the cheap-tail
   maker thesis.
9. **Do not** reuse Phase A's headline counterfactual numbers as
   "actual maker-sell evidence". Use the corrected numbers from
   section 3 of this brief.
10. **Do not** write more code than necessary. One script + tests +
    one report. No infrastructure, no abstractions for hypothetical
    future variants.

## 13. Final checklist before declaring done

- [ ] `scripts/maker_simulator_paper.py` exists and imports cleanly
      on Mac local AND on the bot container
- [ ] `tests/test_maker_simulator_paper.py` exists, all unit tests
      pass
- [ ] `docs/reports/maker-simulator-paper-2026-05-06-the bot container.md` is
      generated against the real recorder DB on the bot container
- [ ] The corresponding `.json` is generated alongside
- [ ] Report has all sections from `4.x` and `5.8` filled
- [ ] All `8` acceptance-gate criteria have explicit pass/fail rows
- [ ] Wilson CIs reported on every win-rate cell
- [ ] Maker fee `=0`, maker rebate `=0` clearly stated as base-case
- [ ] `0` Bot G files touched
- [ ] `0` systemd files touched
- [ ] `0` service restarts
- [ ] `OQ-083` updated with the verdict and report link
- [ ] `MEMORY.md` and `CHANGELOG.md` have a session entry
- [ ] No `bots/maker_paper/` directory created

If any of these are unchecked, you are not done.

---

## 14. One-line success criterion

After this build, the user must be able to read the simulator
report and answer one yes/no question without ambiguity:

> **Does the maker-side cheap-tail edge survive realistic execution
> with conservative lower-bound fills, `500ms` cancel latency, and
> adverse-selection accounting?**

If yes → an ADR for paper research lane is the next step.
If no → maker direction is closed, document and move on.

That binary outcome is the entire deliverable.

---

## 15. Author's note

This brief was written by the Claude session that ran Phases A,
B1, and D, then handed Phase B2 design to Codex for review. The
spec above is Codex's GO-WITH-CHANGES verdict, restated for
operational clarity. If anything in this brief contradicts
[docs/reports/maker-side-research-lane-validation-codex-2026-05-06.md](reports/maker-side-research-lane-validation-codex-2026-05-06.md),
**Codex's review wins.**

The hardest part of this build is fillability modeling
(section 4.5). Everything downstream depends on it. If you find
yourself spending a lot of effort on the simulator report
formatting before the lower-bound fill counter is right, you are
optimizing the wrong thing. Build section 4.5 first, test it
against hand-calculated synthetic data, then build everything else
around it.
