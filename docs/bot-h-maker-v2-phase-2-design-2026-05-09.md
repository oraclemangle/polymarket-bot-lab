# Bot H Maker V2 — Phase 2 Quote Engine Design

**Created:** 2026-05-09 (Session 260)
**Status:** spec only — no code, no commitments. Build is gated on
OQ-100 acceptance per ADR-134. This doc exists so that when the gate
fires positive, building takes 3-4 sessions instead of 5-6.

---

## What Phase 2 is

A paper-only quote engine that:

1. Maintains standing maker quotes on the bid side of `politics 0-10c`
   and `sports 10-20c` markets surfaced by the Phase 1 recorder.
2. Logs paper-fills when an actual taker BUY trade in the recorder's
   `pm_events` stream hits our quoted price.
3. Tracks per-fill adverse-selection (AS) at multiple horizons (5/15/60
   min, at-resolution).
4. Holds paper positions to resolution; recognises PnL using the
   resolution backfill output (yes_won + outcome_yes_price).
5. Emits a daily report with per-cell ROI, AS-loss, fill-rate, and
   builder-rebate accounting.

Quotes never hit the live CLOB. The "paper-fill" is purely a DB write
when a real taker BUY in the recorder's WSS stream had a price ≤ our
quoted bid at that moment.

## What Phase 2 is NOT

- Not live order placement. Live promotion remains gated on a separate
  ADR after Phase 2 completes 200 closed paper positions per cell.
- Not a market-maker that re-quotes intraday on price moves. Phase 2
  uses a static-bid model (one quote per market for the duration of
  the inclusion window) — same shape as the WANGZJ historical
  simulation, so the empirical numbers stay comparable.
- Not a generalised maker. Strictly the two cells from ADR-134
  (politics 0-10c, sports 10-20c). Other cells are recorder-only data
  for counterfactual analysis.

## Module layout

```
bots/bot_h_maker_v2/
  __init__.py                  # existing
  __main__.py                  # add --mode {recorder,quote-engine,both}
  config.py                    # extend with QUOTE_* parameters
  schema.py                    # already migrated for resolution
  capture.py                   # existing recorder
  discovery.py                 # existing
  resolution_backfill.py       # already shipped Session 260
  quote_engine.py              # NEW: maintains active quotes
  paper_filler.py              # NEW: matches taker BUYs to our quotes
  as_tracker.py                # NEW: per-fill AS labels at 5/15/60m/resolution
  pnl.py                       # NEW: realised PnL from resolution backfill
```

## New tables in `data/maker_recorder.db`

The schema-migration helper already scaffolds the markets resolution
columns. Phase 2 adds three more tables (idempotent ALTER + CREATE
patterns to avoid disrupting the running recorder):

```sql
CREATE TABLE IF NOT EXISTS maker_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    posted_at_ms INTEGER NOT NULL,
    cancelled_at_ms INTEGER,                -- NULL until cancelled / market resolves
    condition_id TEXT NOT NULL,
    yes_token_id TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'BUY_YES',
    quoted_price REAL NOT NULL,             -- the bid we're holding (e.g. 0.05)
    quoted_size_shares REAL NOT NULL,
    quoted_size_usd REAL NOT NULL,
    cell_label TEXT NOT NULL,               -- 'politics_0_10c' | 'sports_10_20c'
    cancelled_reason TEXT                   -- 'market_resolved' | 'price_drift' | 'fill' | 'shutdown'
);
CREATE INDEX IF NOT EXISTS ix_maker_quotes_token_time
    ON maker_quotes(yes_token_id, posted_at_ms);
CREATE INDEX IF NOT EXISTS ix_maker_quotes_cell ON maker_quotes(cell_label);

CREATE TABLE IF NOT EXISTS maker_paper_fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filled_at_ms INTEGER NOT NULL,
    quote_id INTEGER NOT NULL REFERENCES maker_quotes(id),
    triggering_pm_event_id INTEGER NOT NULL REFERENCES pm_events(id),
    fill_price REAL NOT NULL,
    fill_size_shares REAL NOT NULL,
    fill_size_usd REAL NOT NULL,
    -- These are populated lazily after resolution; NULL until then.
    yes_won INTEGER,                        -- 1=YES win, 0=NO win
    realised_pnl_usd REAL,
    builder_rebate_usd REAL,
    net_pnl_usd REAL
);
CREATE INDEX IF NOT EXISTS ix_paper_fills_quote ON maker_paper_fills(quote_id);
CREATE INDEX IF NOT EXISTS ix_paper_fills_time ON maker_paper_fills(filled_at_ms);

CREATE TABLE IF NOT EXISTS maker_as_labels (
    fill_id INTEGER PRIMARY KEY REFERENCES maker_paper_fills(id),
    -- Average mid-price at each horizon AFTER the fill.
    -- Toxic if next-window avg > entry_price + 2c (matches historical
    -- simulator's heuristic in /tmp/track1_maker_sim.py on the bot container).
    mid_at_fill REAL NOT NULL,
    mid_5min REAL,
    mid_15min REAL,
    mid_60min REAL,
    mid_at_resolution REAL,
    is_toxic_5min INTEGER,
    is_toxic_15min INTEGER,
    is_toxic_60min INTEGER,
    backfilled_at_ms INTEGER NOT NULL
);
```

## Quote engine logic

### Sizing rules (from ADR-134 §2 + WANGZJ historical capacity)

- Per-quote size: $5 USD (matches `PER_FILL_CAP_USD` in the historical
  simulator, models realistic top-of-book depth at retail).
- Per-cell concurrent quote cap: 50 markets (politics 0-10c) + 25
  markets (sports 10-20c).
- Total deployed cap: $375 = (50 × $5) + (25 × $5). Matches the order
  of magnitude of the existing `bot_d_spike` paper lanes ($200) so the
  fleet isn't dominated by Bot H.
- Daily new-quote cap: 100 (resets at 00:00 UTC).

### Quoting cadence

- On every `book` or `best_bid_ask` event for a subscribed token where
  no active quote exists, evaluate the cell rules:
  1. Does the market match an active cell (politics 0-10c or sports
     10-20c)?
  2. Is the current best ask within the cell's price band?
  3. Are there free quote slots in the cell?
  4. Is the daily cap below limit?
- If all yes: post a quote at `best_bid` (one tick below current
  best ask if best_bid is empty), size $5.
- An active quote stays put until: a paper-fill matches it, the
  market resolves, the price drifts >5c outside the cell, or the
  recorder shuts down.

### Quote drift / cancel rules

- **Drift cancel**: if the YES price moves >5c above the cell's upper
  bound, cancel the quote (the historical edge collapses outside the
  cell — sports 30-40c was killed in the robustness probe).
- **Resolution cancel**: when resolution_backfill flips status to
  RESOLVED, mark all active quotes for that condition_id cancelled
  with reason `market_resolved`.
- **No re-quote on cancel**: each market gets at most one paper-quote
  in its lifetime within Phase 2. This avoids over-fitting and
  matches the WANGZJ simulator's "one bid per market" assumption.

## Paper-fill rules

The fill engine reads `pm_events` continuously. For every
`last_trade_price` event with `side="BUY"` (a taker BUY) on a token
where we have an active quote at price ≤ trade.price:

1. Create a `maker_paper_fills` row referencing the quote and the
   triggering event.
2. Mark the quote as cancelled with reason `fill`.
3. Compute fill_size as `min(trade.size, our_quoted_size)`.
4. Trigger AS-tracker to schedule label-backfill jobs at 5/15/60 min
   horizons (or at-resolution if sooner).

This models a **conservative** fill rate: real makers may fill only a
fraction of the trades that touch their bid (due to queue position),
so we may overstate fills. The `AS_FILL_FRACTION` tunable lets us
sensitivity-test this — Phase 2 ships at 1.0 (count every match) and
the report runs sweeps at 0.25, 0.5, 0.75 to bracket.

## AS tracker

For each fill, schedule an asyncio task that wakes at fill_time + N
minutes (N = 5, 15, 60) and at-resolution. At each wake:

1. Query `pm_events` between [fill_time, fill_time + N] for `book` or
   `best_bid_ask` events on the same yes_token_id.
2. Compute the average midpoint over that window.
3. Write the mid + toxic flag (`mid > fill_price + 0.02`) to
   `maker_as_labels`.
4. At resolution, also record the final settlement price.

The 60-min and at-resolution labels live across recorder restarts —
the at-startup boot sequence enumerates `maker_paper_fills` rows
without complete labels and queues the missing backfills.

## PnL accounting

Drives off the resolution backfill columns. For each fill where
`markets.yes_won IS NOT NULL`:

```
gross_pnl_per_share = -1 + fill_price  if yes_won == 1
                    = fill_price       if yes_won == 0
realised_pnl_usd    = gross_pnl_per_share * fill_size_shares
builder_rebate_usd  = 0.030 * fill_price * (1 - fill_price)
                      * 0.25 * fill_size_shares    # politics+sports rate
net_pnl_usd         = realised_pnl_usd + builder_rebate_usd
```

These columns are written by a `pnl_settlement_loop` that polls every
hour for newly-resolved markets and updates the corresponding fills.

## Daily report extension

`scripts/bot_h_maker_v2_recorder_daily_report.py` adds a Phase 2
section:

- **Quotes:** active count, posted-since-yesterday, cancelled-since-yesterday
  (by reason).
- **Fills:** total fills, fills today, total $ filled.
- **PnL:** realised $ and ROI (net/cost), per cell.
- **AS profile:** toxic-fill % at each horizon, average AS-loss $.
- **Forward-vs-historical drift:** the daily report flags if forward
  ROI deviates >20pp from the WANGZJ historical baseline (politics
  0-10c +43%, sports 10-20c +55%).

## Kill triggers (mirroring ADR-134 §6)

- Realised ROI < +20% on closed positions after 30 closes.
- AS-loss as fraction of cost > 10% sustained for 200 closes.
- Top-5-robust ROI on closed positions ≤ 0% at 200-close audit gate.
- Quote engine errors (placement failure rate > 5% per day).

## Build effort estimate

| component | est. session count |
|---|---:|
| `quote_engine.py` (subscribe to recorder events, post/cancel quotes, drift logic) | 1.0 |
| `paper_filler.py` (match-against-recorder-events) | 0.5 |
| `as_tracker.py` (multi-horizon backfill) | 0.5 |
| `pnl.py` (resolution → realised PnL) | 0.5 |
| Schema migration + tests | 0.5 |
| Daily-report extension | 0.5 |
| Systemd unit + deploy + smoke-test | 0.5 |
| **TOTAL** | **~4.0 sessions** |

Versus the original ADR-134 estimate of 4-6 sessions, this design
shaves ~1-2 sessions because:

1. The Phase 1 recorder already handles WSS subscription, market
   discovery, and event persistence.
2. The resolution backfill already produces yes_won labels.
3. The replay simulator's kernel (rebate formula, gross PnL,
   toxicity) is already in
   `scripts/research/maker_flow_recorder_replay.py` and can be
   imported directly into `pnl.py` and `as_tracker.py`.

## Trigger condition (when to start building)

ADR-134's gate: **30 days of recorder data OR 1M pm_events**, then the
daily replay must show:

1. Both target cells (politics 0-10c + sports 10-20c) PASS the
   robustness check (excl-top-5 ROI > +20% in all 5 sensitivity
   combos).
2. No counterfactual cell (politics 30-40c, awards 0-10c, etc.) flips
   to PASS — if any does, an ADR amendment to expand the active scope
   must precede Phase 2 build.

At observed event rate (~210K events/day), 1M events fires in **~5
days** (around 2026-05-14). Resolution data needs both event capture
AND markets actually closing in our 1c-50c price band — that's slower.
Realistic earliest gate evaluation: **2026-06-08** (30 days).

## Why not start building NOW

ADR-134 explicitly defers Phase 2 to post-burn-in. Three concrete
reasons:

1. The historical robustness probe was on WANGZJ V2 data; forward
   real-market data may differ. If forward fails, Phase 2 code is
   wasted effort.
2. The toxicity-proxy (15-min mid drift) is a guess; forward data may
   reveal a better horizon (5-min or 60-min) before we commit to the
   AS-tracker schema.
3. Phase 2 module touches the recorder process; building before the
   recorder has stable burn-in adds risk to the data we're collecting.

This document captures the design so when the trigger fires, we
build in 4 sessions instead of 5-6.

## Files referenced

- `docs/decisions-log.md` ADR-134 — authority for the build
- `docs/open-questions.md` OQ-100 — gate for the build
- `docs/reports/track1-maker-flow-robustness-probe-2026-05-08.md` —
  empirical foundation
- `bots/bot_h_maker_v2/` — Phase 1 module (recorder running)
- `scripts/research/maker_flow_recorder_replay.py` — kernel that
  Phase 2 imports
- `/tmp/track1_maker_sim.py` (the bot LXC container) — original WANGZJ simulator
