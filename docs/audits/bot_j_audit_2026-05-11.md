# Bot J Audit — 2026-05-11

**Auditor:** Claude Code (Session, 2026-05-11)
**Scope:** `bots/bot_j_nr_wallet/` code, systemd units, strict-settlement monitor,
wallet cohort P&L on proxy-settled sports markets, parameter calibration speed.

---

## 1. Strategic: Is the 30-70c band capturing +EV or noise?

**Finding: Borderline +EV, not statistically significant at 95% confidence.**

On 83 proxy-settled sports markets (first trade per condition, 7-wallet cohort,
30-70c BUY-only):

| Metric | Value |
|--------|-------|
| Unique conditions | 83 |
| Wins | 46 |
| Losses | 37 |
| Win rate | 55.4% |
| Mean return per $1 staked | +$0.232 |
| Std dev of returns | 1.20 |
| **t-statistic** | **1.76** (p ≈ 0.08 one-tailed) |
| Total return on $66 staked | +$19.26 |

A t-stat of 1.76 is significant at 90% confidence, not 95%. The effect size is
economically meaningful (+23.2% per trade) but n=83 is too small for a reliable
read. Target n > 200 for a t-stat that clears the 95% bar.

**Concentration risk (critical):** One wallet (`0x397e4f…`) accounts for 42 of
66 entries (64%) and +17.21 of the +19.26 total edge. Two wallets (`0x31864f…`,
`0xc97485…`) are net negative (-5.48 and -1.74 respectively). The "7-wallet
smart cohort" story is misleading — in practice this is a single-wallet signal
with six other wallets diluting it.

Per-wallet breakdown (proxy-settled sports, first trade per condition):

| Wallet | N | Total return |
|--------|---|-------------|
| `0x397e4f…` | 42 | +17.21 |
| `0x19e27e…` | 5 | +4.38 |
| `0xa2b5b…` | 3 | +2.39 |
| `0xdaef2…` | 1 | +2.23 |
| `0x2d395…` | 2 | +1.23 |
| `0xc9748…` | 6 | -1.74 |
| `0x31864f…` | 7 | -5.48 |

All-category comparison (no sports filter, same cohort): 88 conditions, +25.1%
ROI, t-stat = 1.98. The 5 non-sports trades add marginal alpha but the sports
filter doesn't harm performance.

The 30-70c band captures the majority of the cohort's trade volume (1,151 of
~1,973 total cohort BUYs). Sub-band analysis within 30-70c was inconclusive due
to small per-band sample sizes.

### Recommendations

1. **Track per-wallet signal quality** in the Bot J executor. Log wallet-level
   P&L so you can detect if `0x397e4f…` degrades or stops trading.
2. **Continue paper calibration** until n ≥ 200 proxy-settled trades before
   drawing firm conclusions about edge existence.
3. **Consider weighting entries** by wallet historical quality rather than equal
   weighting all 7.
4. **Verify the 66% NULL-question gap**: 762 of 1,158 qualifying trades have
   NULL `observed_markets.question`. These are invisible to the sports keyword
   filter. Investigate whether the wallet-tag-forward observer is failing to
   backfill market metadata.

---

## 2. Operational: Strict settlement monitor threshold and cadence

**Finding: The threshold of 50 is unreachable. The gate will never open with
current data.**

Observer DB state (2026-05-11):
- 0 strict settlements (`observed_markets.settled = 1`)
- 1,619 proxy settlements (`proxy_settled = 1`, `settled = 0`)
- Settlement methods: 477 NULL, 404 `proxy_near_final_after_end`

The monitor SQL queries `WHERE m.settled = 1 AND …`. Polymarket's Gamma API
sets `proxy_settled = 1` for near-final-price resolutions and almost never sets
`s settled = 1` directly. The query is checking for a settlement pathway that
doesn't occur in practice.

The monitor script itself (`scripts/research/wallet_tag_strict_settlement_monitor.py`)
is well-structured: read-only DB connection, clear exit codes (0=waiting, 1=gate
open, 2=error), good logging format. The issue is the filter predicate, not the
code quality.

Cadence (2x daily at 08:00 and 20:00, Persistent=true) is reasonable for
low-priority monitoring. Timer syntax is correct.

### Recommendations

1. **Change the settlement query** to count `proxy_settled = 1` trades instead
   of `settled = 1`, OR add `proxy_settled` as a parallel metric with its own
   threshold.
2. **Recalibrate the threshold** against proxy data. At 1,619 and growing, a
   threshold of 50 would have been crossed long ago. Consider: what number of
   proxy-settled trades gives sufficient confidence in the settlement pipeline?
3. **If strict settlement is genuinely required** (regulatory or custody
   concern), document why and accept that the gate may remain closed
   indefinitely. The current design is dead code if that's the case.

---

## 3. Parameter: Should the daily entry cap be raised?

**Finding: Yes. The cap of 10/day is the binding constraint on calibration speed.**

Daily qualifying volume from the observer (unique sports conditions per day):
- 2026-05-09: 77 conditions, 178 raw trades
- 2026-05-10: 63 conditions, 151 raw trades
- 2026-05-08: 17 conditions, 50 raw trades

At 10/day, Bot J samples ~15% of available signal. With the 300s cooldown and
open-position cap already providing guardrails, the daily cap is the least
sophisticated and most binding of the three.

Calibration timeline projection:
- At 10/day: ~3 weeks to reach 200 recorded trades
- At 20/day: ~10 days to reach 200 recorded trades
- At 30/day: ~7 days to reach 200 recorded trades

The cooldown (300s) and open position cap (currently 20) prevent runaway
entries. The daily cap's original purpose (safety valve during initial deploy)
has been served.

### Recommendations

1. **Raise `MAX_DAILY_ENTRIES` to 20** immediately.
2. **Monitor for 3 days**: if the 300s cooldown and position cap keep daily
   entries naturally bounded below 20, raise further to 30.
3. **Revisit when approaching live**: paper-mode caps should be calibrated for
   data collection speed; live-mode caps should be calibrated for risk.

---

## 4. Code audit: bugs and issues

### Bug 1 (HIGH) — Dead `after` variable forces full-table scan every poll

**File:** `bots/bot_j_nr_wallet/executor.py`, lines 247-248

```python
after = _latest_ingested_at(con)        # fetched, never used
trades = _qualifying_trades(con, after_ingested_at=None)  # scans ALL rows
```

Every 60s poll re-scans all 20,501 rows (and growing). The `after` variable is
dead code. Fix:

```python
after = _latest_ingested_at(con)
trades = _qualifying_trades(con, after_ingested_at=after)
```

This would reduce each poll from scanning 20k+ rows to scanning only new rows
since the last poll.

### Bug 2 (MEDIUM) — Over-broad sports keywords

**File:** `bots/bot_j_nr_wallet/config.py`, lines 38-68

The keywords `"game"`, `"map"`, and `"vs."` match non-sports content:
- `"game"` appears in crypto, politics, and generic betting markets
- `"map"` has nothing to do with sports on its own
- `"vs."` matches political markets ("Trump vs. Biden")

Empirically the false-positive rate is low (17 non-sports trades out of 396 with
questions, or 4.3%), but the keywords are fragile against new market types.

**Fix:** Either require `"game"` and `"map"` to co-occur with an esports keyword
(`"esports"`, `"bo3"`, `"bo5"`, `"lol"`, `"cs:"`, `"counter-strike"`, `"league
of legends"`), or remove them as standalone keywords.

### Bug 3 (MEDIUM) — Silent YES default on unknown token side

**File:** `bots/bot_j_nr_wallet/executor.py`, lines 143-151

```python
def _token_side(outcome: str | None, outcome_index: int | None) -> str:
    …
    return "YES"  # default — reached when both are unparseable
```

If the observer records a trade with `outcome_index = NULL` and an unrecognized
`outcome` string, the function silently returns YES. If the whale bought NO,
this produces an incorrect paper position.

**Fix:** Log a warning and return `None` (caller can skip) or raise. Don't
default to YES.

### Bug 4 (LOW) — Hardcoded taker fee assumption

**File:** `bots/bot_j_nr_wallet/executor.py`, line 171

```python
fee = fee_for_fill(price, size, "sports", is_maker=False).gross_fee
```

Some whale trades were likely maker orders (resting limit orders with lower
fees). Overestimating fees is conservative and acceptable for paper mode, but
this will skew calibration P&L slightly negative vs reality.

### Bug 5 (LOW) — Hardcoded USD/GBP rate

**File:** `bots/bot_j_nr_wallet/executor.py`, line 212

```python
usd_gbp_rate=Decimal("0.79"),
```

This will drift over weeks. Move to config or fetch live.

### Issue 6 (LOW) — `ReadOnlyPaths` race on boot

**File:** `systemd/polymarket-bot-j-nr-wallet-paper.service`, line 25

```
ReadOnlyPaths=/home/bot/polymarket-bot/data/wallet_tag_forward.db
```

If the observer hasn't created the DB file by the time this unit starts (despite
`After=` ordering), systemd will fail the unit. Consider an `ExecStartPre` check
or using a directory-level path.

---

## 5. Settlement pipeline: empirical state

As of the observer DB snapshot on this machine (may be stale vs the bot container):
- 20,501 observed trades across 881 markets
- 477 markets unsettled, 404 proxy-settled
- 0 strict settlements
- The 7-wallet cohort has 1,158 trades at 30-70c BUY, 462 unique condition_ids
- 299 of those condition_ids (762 trades) have NULL questions — 65% data gap

---

## Summary of actions required

| Priority | Action | File(s) |
|----------|--------|---------|
| **P0** | Fix dead `after` variable | `executor.py:248` |
| **P0** | Redesign strict-settlement gate | `strict_settlement_monitor.py` + ADR |
| **P1** | Raise `MAX_DAILY_ENTRIES` to 20 | `config.py:75` |
| **P1** | Add per-wallet signal quality logging | `executor.py` |
| **P2** | Tighten sports keywords | `config.py:38-68` |
| **P2** | Log warning on unknown token side | `executor.py:151` |
| **P3** | Make USD/GBP rate configurable | `config.py` + `executor.py:212` |
| **P3** | Add `ExecStartPre` DB existence check | systemd service file |
| **Investigate** | Why 65% of cohort trades have NULL questions | wallet-tag-forward observer |
