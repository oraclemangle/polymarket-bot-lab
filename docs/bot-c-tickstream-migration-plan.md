# Bot C Tick-Stream Migration Plan — OQ-031 (REVISED 2026-04-17 PM)

**Date:** 2026-04-17 (Session 17g execution). **REVISED** after reading the actual ingest code.
**Owner:** Claude proposes; operator reviews Alembic migration before apply on LXC.
**Objective:** decide whether OQ-031's remaining gap (2-hour tick retention) needs extending, or whether the existing 1-second OHLCV bars are sufficient for Bot C's thesis.

---

## Correction — the premise in `memory/` was wrong

The memory claim "`price_collector.py` persists only one price point per market per ingest cycle" was **incorrect**. Actual state as read from the repo on 2026-04-17:

- **`core/pyth_ingest.py`** is the real ingestor (there is no `bots/bot_c_pyth/price_collector.py`).
- **`core/pyth_models.py`**:
  - `PythTickRecent` stores **every tick** with `(endpoint, ts_ms, feed_id, price, bid, ask)`.
  - `PythBarPro` / `PythBarHermes` store **1-second OHLCV bars** indefinitely (`ts`, `feed_id`, `open`, `high`, `low`, `close`, `bid`, `ask`, `confidence`, `publisher_count`, `market_session`, `tick_count`).
- **`PythIngestor.handle_tick`** writes BOTH the tick and the bar update per tick.

What IS true:
- **`PythTickRecent` has 2-hour retention** (`TICK_RETENTION_S = 7200` at `core/pyth_ingest.py:42`). Ticks older than 2h get pruned.
- 1-second bars are NOT pruned; long-term history at second-resolution is available.
- `bots/bot_c_pyth/analyst.py` / `strategy.py` read from the **bars**, not the ticks. So the analyst is already on historical time-series.

So OQ-031's stated problem is mostly already solved: price history exists at 1-second resolution. What remains is a scoping question — does Bot C need sub-second ticks with >2h retention, or are 1-second bars sufficient?

---

## Decision logic (do this first, not the migration)

The answer depends on Bot C's thesis (OQ-031 is conditional on C-3). Cases:

1. **If thesis is "directional over hours/days horizon"** (most likely given market DTR limits at `BOT_C_MAX_HOURS_TO_RESOLUTION = 168`):
   - 1-second bars are already sufficient for vol estimation, GBM drift, Markov transitions.
   - No tick-stream migration needed.
   - OQ-031 closes as "resolved by existing schema"; this plan doc is archived.

2. **If thesis requires sub-second microstructure** (unlikely for a traditional-asset directional bot):
   - Extend `TICK_RETENTION_S` to 7-14 days.
   - Add disk-budget guard (10 feeds × 2 ticks/sec × 1.2M sec/14d × ~80 bytes = ~270 MB; feasible).
   - No schema change needed — just a constant bump + disk headroom verification.

3. **If thesis requires millisecond-resolution vol or order-flow** (very unlikely):
   - Write a new higher-resolution table (already proposed in this doc's original version).
   - Add sub-second bars (100ms or 250ms) on top of ticks.

**Default expectation:** case 1. OQ-031 closes as resolved.

---

## Remaining schema concern (still real)

Even with bars resolving history, SECURITY_AUDIT.md H-3 flagged `get_spot_and_vol` as O(N) per market (fetches 18,000 rows per market). That's a performance issue, not a data issue. Fix: window the query by timestamp.

```python
# core/pyth_ingest.py or bots/bot_c_pyth/strategy.py::get_spot_and_vol
# Before: SELECT FROM pyth_bars_pro WHERE symbol = ? ORDER BY ts DESC LIMIT 18000
# After:
#   lookback_seconds = 3600  # 1 hour of 1-sec bars = 3600 rows
#   cutoff = now - timedelta(seconds=lookback_seconds)
#   SELECT FROM pyth_bars_pro WHERE symbol = ? AND ts >= ? ORDER BY ts DESC
```

Cost: one `(symbol, ts)` compound index (already in schema as `(ts, feed_id)` primary key — need a second index on `(feed_id, ts)` if not present).

This is the only remaining schema fix; it's a pref issue not a correctness issue.

---

## Target schema

**New table:** `prices`.

```sql
CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,           -- 'pyth_pro' | 'pyth_hermes' | 'cex_binance' | ...
    symbol TEXT NOT NULL,           -- 'BTC/USD', 'ETH/USD', ...
    price NUMERIC(20, 8) NOT NULL,
    local_ts_ms INTEGER NOT NULL,   -- local UTC ms at receipt
    source_ts_ms INTEGER,           -- publisher timestamp if available
    conf_interval NUMERIC(20, 8),   -- Pyth confidence band, if applicable
    received_at DATETIME NOT NULL   -- SQLite convenience, derived from local_ts_ms
);
CREATE INDEX ix_prices_symbol_local_ts ON prices(symbol, local_ts_ms);
CREATE INDEX ix_prices_source_local_ts ON prices(source, local_ts_ms);
```

Design notes:
- Every tick persisted; no dedup by symbol. If two ticks land with identical `(symbol, local_ts_ms)`, both persist (rare; worth auditing).
- `local_ts_ms` is the authority for ordering. `source_ts_ms` is informational (clock drift between Pyth and receiver is a known source of confusion).
- `conf_interval` supports Pyth's confidence-weighted models downstream.
- `source` enum is open-ended string for flexibility (easier than migrations when we add feeds).

### Alembic migration stub

File: `migrations/<next-rev>_bot_c_price_tickstream.py`

```python
"""Bot C tick-stream schema (OQ-031)."""

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "prices",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("local_ts_ms", sa.Integer, nullable=False),
        sa.Column("source_ts_ms", sa.Integer, nullable=True),
        sa.Column("conf_interval", sa.Numeric(20, 8), nullable=True),
        sa.Column("received_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_prices_symbol_local_ts", "prices", ["symbol", "local_ts_ms"])
    op.create_index("ix_prices_source_local_ts", "prices", ["source", "local_ts_ms"])

def downgrade():
    op.drop_index("ix_prices_source_local_ts")
    op.drop_index("ix_prices_symbol_local_ts")
    op.drop_table("prices")
```

### SQLAlchemy model

Add to `core/db.py`:

```python
class PriceTick(Base):
    __tablename__ = "prices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    local_ts_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    source_ts_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conf_interval: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

---

## Collector rewrite

`bots/bot_c_pyth/price_collector.py` — replace the upsert-in-place logic with pure append.

Key changes:
- Drop all UPDATE / upsert paths.
- Every tick from the feed = one INSERT into `prices`.
- Batching: accumulate 50-100 ticks in memory, commit in one INSERT (SQLite perf; `executemany`).
- Retention: initial policy is "keep everything". Add a TTL script later if disk pressure manifests (unlikely — 1 tick/sec/symbol × 10 symbols × 30 days × ~100 bytes = ~26 MB).
- Respect `BOT_C_PRICE_SOURCE` env (`pyth_pro` / `pyth_hermes` — matches OQ-017 pending decision).

---

## Analyst migration

`bots/bot_c_pyth/strategy.py::get_spot_and_vol` — currently queries `PythBarPro` table with ~18,000 rows per market (per SECURITY_AUDIT.md H-3). Change:

```python
# Before: SELECT FROM pyth_bar_pro WHERE symbol = ? ORDER BY snapshot_at DESC LIMIT 18000
# After: SELECT FROM prices WHERE symbol = ? AND local_ts_ms >= ? ORDER BY local_ts_ms DESC
#        (parameterize the lookback window in ms, e.g. 60_000 for last minute)
```

This fixes the H-3 perf issue (O(N) per market) as a side effect: `(symbol, local_ts_ms)` index makes the query O(log N + W) for a window W.

---

## Migration sequence (safe, zero-data-loss)

1. **Land the new table alongside the old one.** Both schemas co-exist for one week.
2. **Dual-write from collector.** Insert into both `pyth_bar_pro` (legacy) and `prices` (new).
3. **Analyst reads from new table.** Switch `get_spot_and_vol` to `prices`. Run tests. Sanity-check live Bot C behavior for 48h.
4. **Stop writing to legacy.** Keep table for 14 days as fallback.
5. **Drop legacy table.** After 14 days of analyst-on-new confirmed healthy.

Each step is a separate commit. Do NOT skip step 3's sanity check — Bot C is paper but the ghost-position bug (Session 17f cleanup) shows silent data issues propagate.

---

## Files touched

**New:**
- `migrations/<next-rev>_bot_c_price_tickstream.py`

**Modified:**
- `core/db.py` (add `PriceTick` model).
- `bots/bot_c_pyth/price_collector.py` (append-only path).
- `bots/bot_c_pyth/strategy.py` (analyst reads `prices`).
- `tests/test_bot_c_*.py` (new tests for collector append + analyst window).

**Deleted (after step 5):**
- `PythBarPro` model (or leave as read-only legacy stub).

---

## Disk budget

Estimate: 10 symbols × 1 tick/sec × 86,400 sec/day × ~120 bytes/row = ~103 MB/day. Acceptable up to 90 days (~9 GB) on the bot LXC container's current disk (8 GB original, resized TBD). If disk pressure appears, implement a cold-tier rollup (daily summary rows) at week 6.

---

## Kill criteria

If after migration Bot C still cannot express a falsifiable thesis with paper-validated positive EV by 2026-05-31, Bot C archives per `docs/kill-dates.md`. Schema fix does not save the bot by itself; it unblocks the thesis work.
