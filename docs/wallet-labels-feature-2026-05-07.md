# Wallet Labels Feature — `core/wallet_labels.py`

**Created:** 2026-05-07
**Status:** ready, plumbed but no consumer yet
**Authority:** infrastructure-that-compounds work per state-of-the-fleet 2026-05-07

---

## What this is

A read-only Python module that exposes the PolyVerify wallet-bot-detection
data as a feature for any bot. Loads `data/polyverify_wallets.csv` once
per process (singleton via `lru_cache`) and provides O(1) lookups by
wallet address.

**Source data:** scraped 2026-05-06 from PolyVerify's undocumented JSON
API (`polyverify.com/api/leaderboard`). 999 unique wallets (1 duplicate
in source CSV — last-write-wins by design), 193-194 flagged
`likelyAutomated=True`.

## Why this exists

- The CSV has been on disk since Session 196 (2026-05-06) but never
  plumbed into any bot.
- It's referenced as #7 in `docs/reports/dormant-ideas-sweep-2026-05-07.md`
  ("PolyVerify wallet-tag features for any directional lane — 1000-wallet
  bot scores already cached at `data/polyverify_wallets.csv`; never
  plumbed into a feature pipeline. **Yes — data is on disk and free.**").
- This is **infrastructure that compounds**: any bot that wants to filter
  by counterparty bot-score, or log counterparty composition, gets it
  for free now.

## What this is NOT

- **NOT copy-trading.** Copy-trading verified sharps remains on the
  `CLAUDE.md` out-of-scope list. This module is a feature/telemetry
  primitive, used to FILTER OUT bot-flagged counterparties or LOG
  composition — not to mirror their trades.
- **NOT a replacement for `data/polyverify_wallets.csv`.** The CSV is
  the source of truth. This module reads it.

## API

```python
from core.wallet_labels import WalletLabels, load_default

# Singleton (recommended for hot paths)
labels = load_default()

# Direct lookup
record = labels.lookup("0xF00D000000000000000000000000000000000009")
# WalletLabel(wallet="0x56687...", user_name="Theo4", rank=1,
#             volume_usd=43_013_258.5, pnl_usd=22_053_933.7,
#             bot_score=36, bot_confidence="low",
#             likely_automated=False, tags="")

# Helpers (return False/None for unknown wallets)
labels.is_likely_automated(wallet)        # -> bool
labels.is_known(wallet)                   # -> bool
labels.bot_score(wallet)                  # -> int | None
labels.is_high_confidence_bot(wallet)     # -> bool (high confidence + flagged)
labels.is_top_100(wallet)                 # -> bool

# Filtering
top_profitable_humans = labels.filter(
    likely_automated=False,
    min_pnl_usd=100_000,
    max_rank=200,
)

# Telemetry / dashboard
labels.stats()
# {"total": 999, "likely_automated": 194, "automated_pct": 19.4,
#  "high_confidence_bots": 27, "positive_pnl_wallets": ~700}
```

## Use cases (in order of immediacy)

### 1. Counterparty composition logging (telemetry — zero risk)

Every bot's recorder/audit can log `is_likely_automated(taker_wallet)`
on every fill. This builds a baseline of "what fraction of our flow is
trading against known bots vs humans" — useful for adverse-selection
diagnosis on Bot G ("structurally weak" taker edge), Bot D NO-side
range-fade, and Strategy E.

**Implementation:** add to the `bot_d_spike` daily report or any
existing audit script:

```python
from core.wallet_labels import load_default

labels = load_default()
# In recorder/audit code:
counterparty_label = labels.lookup(fill.maker)
if counterparty_label:
    record["counterparty_bot_score"] = counterparty_label.bot_score
    record["counterparty_likely_automated"] = counterparty_label.likely_automated
    record["counterparty_user_name"] = counterparty_label.user_name
```

### 2. Adverse-selection filter (skip-entry logic)

Bots can refuse entries where the dominant counterparty is bot-flagged.
This is the "don't trade against known bots" defense.

**Implementation in any executor:**

```python
from core.wallet_labels import load_default

# In the entry-decision pipeline:
labels = load_default()
top_bid_taker = book.maker_at_top_bid()  # need to source from CLOB
if top_bid_taker and labels.is_high_confidence_bot(top_bid_taker):
    return EntryDecision(False, "counterparty_high_conf_bot")
```

**Caveat:** PolyVerify scores are static (snapshot 2026-05-06). They
reflect past behavior; a wallet that was human-discretionary may be
bot-quoting now. Treat as a heuristic, not ground truth.

### 3. Combined with WANGZJ retail-tier mining (when that lands)

The wallet mining query running on the bot container produces a list of
profitable retail-tier wallets (avg position $50-500, ≥30 trades, ≥30
days, sustained ROI). Cross-referencing with PolyVerify lets us:

- **Whitelist** retail-tier wallets that are positive-EV AND not bot-flagged
- **Blacklist** retail-tier wallets that are bot-flagged (don't fade
  bots; their flow is informationally weighted)
- **Feature column** for any future Bot D-Spike refinement: "boost
  confidence if ≥3 whitelisted retail wallets are entering same
  direction in last 1h"

This combination is what makes Variant B (wallet-tag features) more
defensible than Variant A (direct copy-trading) — we're not mirroring
trades, we're using counterparty composition as a feature.

## Tests

11 tests at `tests/test_wallet_labels.py`. Coverage:

- CSV parse correctness across all column types
- Case-insensitive wallet lookup
- Unknown-wallet null handling
- Helper methods (`is_likely_automated`, `is_high_confidence_bot`,
  `is_top_100`, `bot_score`)
- Filter API (multiple criteria)
- Stats aggregation
- File-not-found error
- Malformed-row skip behavior
- Singleton caching via `load_default()`
- Smoke test against actual checked-in CSV (verifies Theo4 record at
  rank 1)

All pass on VPS Python 3.12.

## Known limitations

1. **Static snapshot.** PolyVerify data is from 2026-05-06; bot
   behavior changes. Refresh cadence not yet defined.
2. **Top 1000 only.** Wallets outside top-1000 by volume × pnl are
   absent. Long-tail wallets aren't covered.
3. **Bot scores are not perfect.** PolyVerify's heuristics use trade
   timing, regularity, and net flow patterns. Some MM-style retail
   traders may be flagged as bots; some sophisticated bots may evade.
4. **No per-category data.** A wallet flagged "bot" may be highly
   skilled at sports betting and a noise-trader at politics. Module
   exposes a single global score.
5. **Source CSV has 1 known duplicate.** Module dedups by last-write
   (rank order). 999 unique entries from 1000 source rows.

## Refresh procedure

When PolyVerify data gets stale (3-6 months?), re-scrape:

```bash
# (Re-run the scraper from Session 196)
python scripts/scrape_polyverify.py --output data/polyverify_wallets.csv

# Tests will re-validate
pytest tests/test_wallet_labels.py
```

The module's `load_default()` is `lru_cache`-decorated; restart any
running bots after refresh to pick up new data.

## Files

- `core/wallet_labels.py` — module (181 lines)
- `tests/test_wallet_labels.py` — tests (11 tests)
- `data/polyverify_wallets.csv` — source data (999 unique wallets)
- `docs/wallet-labels-feature-2026-05-07.md` — this doc

## Files unchanged

- No bot service touched
- No order paths modified
- No new env vars
- Bot G stays as-is per standing instruction
- Strategy E paper deployment unchanged
