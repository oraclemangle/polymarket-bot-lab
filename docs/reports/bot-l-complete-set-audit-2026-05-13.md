# Bot L Complete-Set Convergence Audit

**Date:** 2026-05-13
**Owner:** Codex executing `docs/opus-bot-l-complete-set-audit-prompt-2026-05-13.md`.
**Scope:** Local code + VPS read-only DB queries against
`bot_l_complete_set_paper.db` and the source recorder
`bot_e_recorder_vps_canary.db`.
**Posture:** Read-only. No service restarted. No order placed. No wallet,
keystore, passphrase, env, or CLOB auth touched. No Bot G live size,
band, lead window, or symbol change.

---

## 1. Verdict

**YELLOW.** Bot L is correctly isolated as a paper-only lane, the
24h backfill numbers reproduce exactly, the math is consistent
with Polygon CTF mechanics, and the simulator correctly de-dupes
events; but the headline `+$1.9665` executable P&L is not yet a
defensible edge. Three concrete blockers:

1. **Depth is silently unenforced.** 154 of 154 signals (100%) have
   `yes_size IS NULL OR no_size IS NULL`. The recorded
   `best_bid_ask` payloads do not carry size, so the simulator's
   `min_depth_shares` gate is dead code in production. Executable
   flag means "haircut-passing top-of-book," not "size-deliverable."
2. **Concentration is structural, not marginal.** One BTC 5-minute
   market is **24.3%** of executable P&L; the top three markets are
   **46.4%**. Ex-largest-10 leaves only **$0.49** across the
   remaining 35 rows (~$0.014/row, below the assumed slippage
   per-pair).
3. **Forward signal rate has collapsed.** 154 signals were written
   in a single 24h backfill run; the subsequent 90 incremental runs
   over the next 2+ hours have produced **zero** new signals while
   the cursor continues to advance through normal recorder traffic.

Bot L is plausible as a research surface but not yet trustworthy as
an edge candidate. The fixes are small and well-scoped — see
phased plan below.

---

## 2. Top Findings (severity order)

| # | Severity | Finding | Evidence |
|---:|---|---|---|
| 1 | High | Depth/size is captured as NULL in 154/154 signals; the `--min-depth-shares` gate is therefore dead in production | VPS query: `COUNT(*) WHERE yes_size IS NULL OR no_size IS NULL = 154`; systemd unit omits `--min-depth-shares` (defaults to `0`) → `depth_ok = True` whenever min is `<= 0` (`simulator.py:235-247`, `262-274`) |
| 2 | High | BUY and SELL executable P&L are aggregated in one number even though they price two distinct economic operations (BUY-MERGE arb vs SPLIT-SELL arb) | `_maybe_write_sell_signal.payload["note"] = "sell signal is inventory/split research only"` (`simulator.py:280`), but `build_summary` and `_bot_l_complete_set_summary` both add them into one `executable_pnl_usd` (`simulator.py:380-395`, `scripts/vps_node_status.py:1144-1148`) |
| 3 | High | Concentration: top market `0x2cf9ba89...` is **24.3%** of exec P&L; top-3 markets `46.4%` | Per-market rollup (audit run): top-1 `$0.4770`, top-2 `$0.2239`, top-3 `$0.2113`, executable total `$1.9665` |
| 4 | Medium | Forward signal rate is zero across 90 incremental runs (2h+); the headline is entirely a one-shot backfill | `run_log`: run 1 → 154 signals; runs 2..91 (cursor advances 39078507→39082970) → 0 signals total |
| 5 | Medium | Robustness battery: BUY ex-largest-10 = `$0.2554`; SELL ex-largest-10 = `$0.2800`; combined ex-largest-20 = `$0.5345` over the remaining 25 rows ≈ `$0.021/row`, below the assumed `$0.005 × 2-leg = $0.010` slippage haircut | Per-signal ex-largest computation (audit run) |
| 6 | Medium | Polygon SPLIT/MERGE mechanics (atomicity, gas, ProxyWallet path) are not modelled; the `+$X` ledger implicitly assumes free atomic split-merge | `simulator.py:206-211` (BUY: `return = shares = 1/adjusted_sum`); `simulator.py:271-279` (SELL: `return = notional × adjusted_sum`). No gas, no atomicity proof, no MERGE/SPLIT tx accounting |
| 7 | Medium | Test fixture `test_run_once_records_buy_complete_set_signal` uses a crossed book (`bid=0.51 > ask=0.48`) and the simulator records both BUY and SELL signals from it — there is no sanity check that `bid <= ask` | `tests/test_bot_l_complete_set.py:102-106`, `simulator.py:80-104` (`parse_quote` accepts any bid/ask values) |
| 8 | Low | `1c round-trip haircut` is implemented as `±slippage_per_leg × 2`, where `slippage_per_leg` is configurable (`0.005` in the deployed unit). That is **0.5c per leg**, not "1c round-trip" as written in the report — totals are 1c only at this specific config | systemd unit `--slippage-per-leg 0.005`; `simulator.py:202` (`adjusted_sum = raw_sum + 2 * slippage_per_leg`) |
| 9 | Low | The pair aging gate (`max_pair_age_ms=1000`) is one second — generous for low-tape periods but may admit stale top-of-book in fast moves. Worth slicing forward results by pair age | `simulator.py:339` (`abs(yes.received_at_ms - no.received_at_ms) > max_pair_age_ms`) |
| 10 | Low | Latest-quote `latest_by_asset` dict is keyed by `asset_id` and persists across the loop, so a single stale quote that hasn't been replaced can pair with a fresh quote of the other leg; this is conservative for one second but unbounded otherwise | `simulator.py:329-339` |

---

## 3. Evidence Check

| Metric | Claimed (analysis report) | Verified (VPS DB read-only) | Match |
|---|---:|---:|---:|
| Total signals | 154 | 154 | ✅ |
| Executable after 1c haircut | 45 | 45 | ✅ |
| BTC 5m markets touched | 30 | 30 | ✅ |
| BUY complete-set signals | 75 | 75 | ✅ |
| SELL complete-set signals | 79 | 79 | ✅ |
| Simulated raw P&L | +$2.3084 | +$2.3084 | ✅ |
| Simulated executable P&L | +$1.9665 | +$1.9665 | ✅ |
| Distinct `(event_id, signal_type)` pairs | implicit ≤ 154 | 154 (UNIQUE INDEX enforces) | ✅ |
| Distinct `event_id` | implicit | 154 (so each event yields BUY *or* SELL, never both) | n/a — informational |
| Backfill timestamp window | "first 24h" | 2026-05-12 20:35:42 UTC → 2026-05-13 17:40:00 UTC (21.07h) | ⚠️ Strictly 21h, not 24h, but close |
| Total runs since deploy | n/a | 91 (1 backfill + 90 incremental) | n/a |
| Forward signals after backfill | not stated | **0** new signals across 90 incremental runs spanning 18:11→20:22 UTC | ⚠️ Material |
| Source events seen forward | not stated | 736 events across the 90 incremental runs (cursor 39078507→39082970) | informational |
| Depth captured | implicit ("require both sides have book size above floor" per analysis recommendation) | **0/154 signals** have non-NULL `yes_size` AND `no_size` | 🔴 Mismatch — recommendation not realised in deployed config |

---

## 4. Accounting Review

### BUY complete-set (`simulator.py:_maybe_write_buy_signal`)

```
raw_sum      = yes.ask + no.ask
adjusted_sum = raw_sum + 2 * slippage_per_leg
shares       = gross_cost_usd / adjusted_sum
return       = shares                          # (1.0/share at resolution because YES+NO = 1.0)
cost         = gross_cost_usd
pnl          = return - cost
roi          = pnl / cost
```

- **Math is correct given the abstraction:** on Polygon CTF you can
  buy 1 YES at `yes.ask` plus 1 NO at `no.ask`, then call `MERGE`
  to convert the matched pair into 1.0 USDC.
- **Missing realism:** the simulated `return = shares` assumes the
  MERGE is free, atomic, and immediate. In practice `MERGE` on the
  CTF Exchange contract costs gas (~$0.001-$0.01 on Polygon) and is
  not atomic with the two BUYs — between the two fills and the
  MERGE call the book can move, asks can deplete, or the second leg
  can fail.
- **Threshold check:** raw_sum must be `<= raw_buy_threshold` (deployed
  at `0.995`), then `adjusted_sum <= adjusted_buy_threshold`
  (deployed at `0.985`) for `executable=1`. Logic is internally
  consistent.
- **Verified BUY exec rows:** 22 (of 75 BUY signals); exec pnl $1.1165.
- **BUY ex-largest robustness:**

| Trim | Remaining rows | Exec P&L | Drop |
|---|---:|---:|---:|
| raw | 22 | $1.1165 | — |
| ex-1 | 21 | $0.7651 | -31% |
| ex-5 | 17 | $0.4859 | -57% |
| ex-10 | 12 | $0.2554 | -77% |
| ex-20 | 2 | $0.0408 | -96% (only $0.02/row left) |

### SELL complete-set (`simulator.py:_maybe_write_sell_signal`)

```
raw_sum      = yes.bid + no.bid
adjusted_sum = raw_sum - 2 * slippage_per_leg
cost         = notional_usd                       # = gross_cost_usd, deployed at $1
return       = notional_usd * adjusted_sum
pnl          = return - cost
```

- **Math problem 1 — this is not a sell of existing inventory.** The
  P&L formula `return = notional × adjusted_sum` only makes sense
  if you have a way to *deliver* 1 YES and 1 NO at the bid for
  notional dollars worth of pairs. There are two real-world paths:
  - **SPLIT-and-sell:** pay $1.00 to SPLIT a complete set from
    collateral, sell each leg at bid. Net of the SPLIT cost the
    profit is `(yes.bid + no.bid) - 1.00 = raw_sum - 1.00`. The
    simulator's formula reduces to this for `notional_usd=1`:
    `return - cost = adjusted_sum - 1 = (raw_sum - 0.01) - 1`.
    Math is consistent **if** you assume SPLIT is free atomic and
    you have collateral idle.
  - **Sell from existing inventory:** requires the bot to already
    hold matched YES+NO, which Bot L cannot guarantee.
- **Math problem 2 — capital lockup.** Each $1 SPLIT locks $1 in
  USDC collateral while the two sales execute, then returns
  `raw_sum - 0.01` cash. At true SPLIT atomicity this is fine; at
  a real Polygon round trip it is multi-block (USDC approve → SPLIT
  → two SELL orders → settlement). The simulator is silent on this.
- **The simulator's own payload note acknowledges the limitation:**
  `payload["note"] = "sell signal is inventory/split research only"`
  (`simulator.py:280`).
- **Verified SELL exec rows:** 23 (of 79 SELL signals); exec pnl $0.85.
- **SELL ex-largest robustness:**

| Trim | Remaining rows | Exec P&L | Drop |
|---|---:|---:|---:|
| raw | 23 | $0.8500 | — |
| ex-1 | 22 | $0.7600 | -11% |
| ex-5 | 18 | $0.4800 | -44% |
| ex-10 | 13 | $0.2800 | -67% |
| ex-20 | 3 | $0.0600 | -93% ($0.02/row left) |

**Aggregation issue:** `build_summary.executable_pnl_usd` and
`vps_node_status._bot_l_complete_set_summary.executable_pnl_usd`
both sum BUY and SELL into one number. These two strategies
require fundamentally different operational paths (MERGE vs SPLIT)
and different gas/atomicity assumptions. The combined `$1.9665`
hides this.

### Haircut

`adjusted_sum = raw_sum ± 2 × slippage_per_leg` with
`slippage_per_leg=0.005` in production. That is a 0.5¢-per-leg
penalty (1¢ round trip), not a depth-aware haircut. The deployed
`adjusted_buy_threshold=0.985` and `adjusted_sell_threshold=1.015`
make the effective gate even tighter than the raw `0.995/1.005`.
Logic is sound; magnitude is a guess pending real fill data.

### Duplicate prevention

`UNIQUE INDEX ux_bot_l_signal_event_type ON
bot_l_complete_set_signals(recorder_event_id, signal_type)` plus
`INSERT OR IGNORE` correctly prevent the same recorder event from
firing the same signal type twice. Verified: 154 rows / 154 unique
`(event_id, signal_type)` pairs / 154 distinct `event_id`. The
distinct-event_id count tells us no event ever produced both a BUY
and a SELL signal — the simulator picks one per event according to
which threshold is crossed.

### `best_bid_ask` / `book` payload fallback

`parse_quote` (`simulator.py:60-107`) tries explicit
`best_bid` / `best_ask` first, then falls back to traversing
`bids`/`asks` arrays for the best price-and-size. This is correct;
however **none of the 154 rows captured a non-NULL size** which
indicates the deployed recorder payloads (book vs best_bid_ask)
do not carry size for these markets, or always include it as zero
and `_float` rejects zeros.

### `max_pair_age_ms` pairing

The simulator maintains `latest_by_asset[asset_id] = Quote` and
only fires a signal if `abs(yes_received_ms - no_received_ms) <=
max_pair_age_ms` (deployed: 1000ms). For one-second-stale top-of-
book on a tight market the pair is admitted; in fast moves this
can pair a slightly stale leg with a fresh one. Not a bug — a
research parameter — but worth slicing forward results by pair age.

---

## 5. Isolation Review

**Verdict: clean.**

| Risk | Verified |
|---|---|
| CLOB client imports | None. `grep -rn 'CLOB\|clob_v2' bots/bot_l_complete_set/` returns zero matches. |
| Wallet / passphrase / keystore | None. `grep -rn 'keystore\|passphrase\|wallet_key' bots/bot_l_complete_set/` returns zero matches. |
| Writes to live ledgers | None. `recorder = sqlite3.connect(f"file:{path}?mode=ro", uri=True, ...)` (`simulator.py:42`); writes only to `bot_l_complete_set_paper.db` via `init_db`. No `main.db` or `bot_g_vps_main.db` references. |
| Fleet cap inclusion | `BotMeta.include_in_cap=False` (`core/bot_registry.py:504`). |
| Service can mutate live trading state | `Type=oneshot`, `User=operator`, `ProtectSystem=strict`, `ProtectHome=read-only`, `ReadWritePaths=/home/operator/longshot-research/data /home/operator/longshot-research/logs`. No live unit dependency in `Wants=`/`After=`; only `network-online.target` and the recorder service. |
| Dashboard confusion with Bot G | `dashboard_visible=False` (no `dashboard_visible=True`) in registry; no `bot_l` references in `dashboard/runtime_queries.py`, `dashboard/server.py`, or `dashboard/static/app.js`. Only `scripts/vps_node_status.py:_bot_l_complete_set_summary` reads the paper DB read-only for the VPS status bridge. |

No isolation defects found.

---

## 6. Improvement Plan

| Phase | Change | Files likely touched | Why | Test / verification |
|---:|---|---|---|---|
| **1. Correctness fixes (high)** | Split `executable_pnl_usd` into `buy_exec_pnl_usd` and `sell_exec_pnl_usd` everywhere a summary is built (simulator, vps_node_status, any future dashboard). Keep a combined value but label it `combined_theoretical`. | `bots/bot_l_complete_set/simulator.py:build_summary`, `scripts/vps_node_status.py:_bot_l_complete_set_summary`, tests | BUY-MERGE and SPLIT-SELL price different mechanics; aggregation hides the asymmetric capital/atomicity assumptions | Add a test asserting both buckets are present and equal to per-type sums |
| 1 | Reject crossed-book signals at parse time (`if bid is not None and ask is not None and bid > ask: return None`) | `bots/bot_l_complete_set/simulator.py:parse_quote`, `tests/test_bot_l_complete_set.py` | A crossed book is either a stale tape artefact or a momentary inversion that should not be treated as a tradeable quote | Add a test inserting `bid=0.51, ask=0.48` and asserting zero signals |
| 1 | Verify depth source: probe whether the recorder's `book` events carry `bids`/`asks` arrays with sizes (currently only `best_bid_ask` rows are seen). If `book` events do carry size, prefer them. If neither does, document it in OQ-111 and propose a small recorder change. | `bots/bot_l_complete_set/simulator.py:parse_quote`, possibly recorder capture | Without size data the executable flag is just "raw plus a haircut" — depth gating is performative | One-shot probe script counting `best_bid_ask` vs `book` rows with non-null sizes; add a unit test for the `book` payload shape |
| **2. Reporting (high)** | Add a daily Bot L report (markdown + JSON) emitted via a sidecar systemd timer: signals/day, exec/day, top-N concentration, BUY/SELL split, ex-largest-{1,5,10,20}, distinct markets, pair-age distribution, source-recorder pm_events seen, signal rate per hour | `scripts/bot_l_complete_set_daily_report.py`, `systemd/polymarket-bot-l-complete-set-daily-report-vps.{service,timer}`, `core/bot_registry.py` description | Currently the only window into Bot L is `vps_node_status` which is summary-level. Daily reports surface concentration drift and forward-rate stall | Smoke test the script locally with the fixture DB; verify timer cadence (recommend 06:30 UTC daily) |
| 2 | Add a no-lookahead check: a "signal generated at `detected_at_ms`" should be compared to the market's `end_date_ts` to confirm it fired before resolution, not on stale tape after close. Emit `stale_after_end_date` reason | `bots/bot_l_complete_set/simulator.py` | If signals fire on quotes that arrive after market resolution, the executable flag is meaningless | Test with a market whose `end_date_iso` is before the event ts |
| **3. Forward-paper evidence (medium)** | Stop trusting the one-shot 24h backfill. Reset the cursor and run incremental-only for ≥7 forward days before any robustness verdict | manual / one-time script | The current `$1.9665` is one backfill batch; forward incremental rate is zero in 2h | After 7d: re-run the daily report and ex-largest-{1,5,10,20} checks |
| 3 | Add diagnostics for "why did the forward rate collapse?" — log the top reasons quotes fail to fire (one leg missing, pair-age too large, raw_sum within parity band, etc.). Adapter to `bot_l_complete_set_run_log` payload | `bots/bot_l_complete_set/simulator.py` | We currently can't tell whether the backfill was a regime-specific blip or whether the recorder isn't producing both legs in the live window | Inspect logs after 24h forward |
| **4. Replay robustness (medium)** | Run the simulator across multiple historical windows (week-on-week) and produce a per-window concentration + ex-largest report | `scripts/bot_l_complete_set_replay.py` | Concentration during the 21h backfill (24.3% in one market) might be regime-specific | Output table per week × signal_type |
| 4 | Sensitivity sweep over `(raw_thresh, adjusted_thresh, slippage_per_leg, max_pair_age_ms)` | same script | The deployed thresholds are first-pass guesses; we need to see whether the edge is robust to ±0.5c | Table or heatmap |
| **5. Dashboard surfacing (low)** | Add a hidden `/api/bot-l` route mirroring the structure of `/api/wallet-observer`, gated by `dashboard_visible=False` and surfaced only on a future "Research lanes" view | `dashboard/runtime_queries.py`, `dashboard/server.py` | Operator visibility into forward signal rate without SSH-ing the VPS | Existing dashboard regression suite |
| **6. Live-readiness work (future-only)** | None. Live promotion requires a new ADR + the operator approval + every gate in §7 explicitly met. | n/a | per ADR-159 §"Decision" | n/a |

---

## 7. Promotion / Kill Gates

A future live ADR for any complete-set lane must require **every** of:

| Gate | Threshold |
|---|---|
| Minimum forward-paper signals | ≥ **500 executable forward signals** (currently 45, ~91% short) |
| Minimum executable signals **after** depth check | ≥ **200**, with depth ≥ `gross_cost_usd / adjusted_sum` shares both legs |
| Minimum distinct markets contributing to executable P&L | ≥ **50** (currently 30 raw / ~14 executable) |
| Minimum days of observation including ≥ 1 weekend | ≥ **14 days** (currently 21 hours of backfill, then 2h of incremental zero) |
| Maximum concentration in top-1 market | < **10%** of executable P&L (currently **24.3%** → FAIL) |
| Maximum concentration in top-3 markets | < **25%** (currently **46.4%** → FAIL) |
| Minimum **BUY** executable P&L ex-largest-10 | > **+0.5%** of cost basis (currently `$0.2554` on `$22` cost = `+1.16%` — marginally passes BUT 12 rows is too small a sample for the gate) |
| Minimum **SELL** executable P&L ex-largest-10 | > **+0.5%** of cost basis under explicit SPLIT-and-sell modelling with gas | (currently `$0.28` on `$23` cost = `+1.22%` — same caveat) |
| Maximum drawdown over any 7-day rolling window | < **-5%** of cumulative exec P&L |
| Depth check | both legs ≥ `gross_cost_usd / adjusted_sum` shares **at quote time** (not "displayed" — must be observed in book event with size) |
| SPLIT/MERGE accounting | explicit Polygon CTF tx model: gas per leg, ProxyWallet/relayer path, atomicity proof or revert-protection envelope |
| Negative-control: same threshold logic on **non-BTC** 5m crypto markets (ETH, SOL) | should produce comparable signal rate; if it produces 10× more, the signal is symbol-specific or threshold-specific noise |
| Cells where edge requires either inventory or atomicity assumptions | explicit live-paper proof on a separate `bot_l_inventory_test_paper` lane that walks SPLIT/SELL round trips on the recorder tape with realistic gas + delay |

**Kill conditions** (auto-pause the paper lane):

- Two consecutive 7-day windows with negative executable P&L after fees.
- Top-1 market concentration > 30% on a ≥ 500-signal forward sample.
- Any "stale_after_end_date" signal ratio > 1%.
- Source recorder gap > 6h for the BTC 5m universe.

**Live promotion requires:** a new ADR explicitly citing this audit
report by date, the operator's written approval, and all gates above met
on a forward-paper sample taken **after** the depth-capture fix.

---

## 8. Codex Next Actions

In priority order. Each action is paper-only, read-only, or
research/reporting. No live restart, no live size, no wallet, no
order placement.

1. **Re-deploy with depth diagnostics** — patch `parse_quote` to log
   why size is NULL (missing payload field vs `_float` rejection of
   zero); push to VPS; let it run forward for 24h; check whether
   any signals capture non-NULL sizes.
2. **Split executable P&L into BUY/SELL buckets** —
   `bots/bot_l_complete_set/simulator.py:build_summary` + tests +
   `scripts/vps_node_status.py:_bot_l_complete_set_summary` + tests.
   This is a one-session change.
3. **Add crossed-book rejection** — `parse_quote` returns None when
   `bid > ask`; tests; redeploy.
4. **Daily report script + timer** — model after
   `scripts/bot_h_maker_v2_recorder_daily_report.py`. Outputs
   markdown + JSON sidecars with the gate-relevant slices.
5. **Reset cursor / force-refresh** — one-shot
   `python scripts/bot_l_complete_set_paper.py --full-refresh
   --lookback-hours 168` on VPS, then revert to incremental. This
   gets a richer baseline before forward-only mode takes over.
6. **OQ-111 update + ADR-159 cross-ref** — add this audit report as
   the named source for forward gates and update the OQ status
   blurb.
7. **Replay sensitivity sweep** — over `(raw_thresh ∈ {0.99, 0.995,
   0.998}, slippage_per_leg ∈ {0.0025, 0.005, 0.01})` for the
   21h backfill plus the next forward 7d.

---

## 9. Commands and Queries Used

```bash
# Read Bot L source (local)
cat bots/bot_l_complete_set/schema.py bots/bot_l_complete_set/simulator.py
cat scripts/bot_l_complete_set_paper.py
cat systemd/polymarket-bot-l-complete-set-paper-vps.{service,timer}
cat tests/test_bot_l_complete_set.py

# Foundational docs
grep -n -A 80 'OQ-111' docs/open-questions.md
grep -n -A 60 '^## ADR-159' docs/decisions-log.md
cat docs/reports/xuanxuan-btc-5m-strategy-analysis-2026-05-13.md

# Registry + dashboard wiring
grep -n 'bot_l\|bot_l_complete_set' core/bot_registry.py scripts/vps_node_status.py \
  dashboard/runtime_queries.py dashboard/server.py dashboard/static/app.js
grep -rn 'CLOB\|clob_v2\|wallet_key\|keystore\|passphrase\|main.db\|bot_g_vps_main' \
  bots/bot_l_complete_set/ scripts/bot_l_complete_set_paper.py

# VPS read-only inspection
ssh -i ~/.ssh/id_ed25519 operator@198.51.100.1 '/home/operator/longshot-research/.venv/bin/python3 /tmp/_a3.py'
# /tmp/_a3.py: see scripts/research/bot_l_audit_2026_05_13.py (proposed) for the same SQL.
# Queries:
# - SELECT COUNT(*) / SUM/COALESCE(...) FROM bot_l_complete_set_signals
# - Per-type / per-condition aggregates
# - run_log: source_events_seen, signals_written, cursor
# - Ex-largest-{1,5,10,20} per BUY and SELL
# - Depth captured: COUNT(*) WHERE yes_size IS NULL OR no_size IS NULL
# - Distinct (event_id, signal_type) pairs
```

## 10. Hard Boundaries Reaffirmed

This audit changed **no** runtime state. No bot service was started,
stopped, or restarted. No order was placed. No live size, cap, band,
lead window, symbol, or wallet was changed. No env, keystore, or
passphrase was read or written. The dashboard runtime was not
restarted. ADR-159's paper-only posture stands; OQ-111 stays open
pending the §6 improvements and §7 gates.
