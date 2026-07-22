# Profitability and ROI Goal Handoff - 2026-05-16

**Start this in a new Codex session.**

## Goal

Reframe the active work from "convert promising maker-paper lanes when samples clear" to:

> Make per-bot profitability and ROI the controlling decision surface, fix live-dashboard P&L visibility first, and only tune or promote parameters after realised/live-accounting truth is visible and ADR-gated.

Additional research workstream:

> Re-audit previously rejected or parked strategy theories through a maker-first lens, because many historical tests were taker-like and may have failed on spread/fee/execution rather than predictive signal. This workstream is subordinate to profitability/ROI truth: it is report-only until dashboard live accounting is fixed and any revived lane clears ROI gates.

## Hard boundaries

- Do not place live orders.
- Do not start, stop, restart, reset, or redeploy live trading services without explicit in-session approval.
- Do not change wallet, keystore, VPN, treasury, bankroll, or CLOB auth paths.
- Do not quietly convert paper/shadow executors into live executors.
- Do not tune live parameters until the dashboard distinguishes realised P&L from open exposure for every live bot.
- Paper/shadow parameter sweeps are allowed if they are report-only and do not change live runtime behavior.
- Do not reinstate an archived strategy as a live or enabled runtime just
  because maker execution looks interesting. Old theories may only be revived
  as read-only replay, offline report, or explicitly paper-only maker shadow
  lanes after an ADR/open-question review.

## Current evidence snapshot

Source: the bot container read-only `data/main.db`, local dashboard source inspection, and
FV live redemption/accounting checks on 2026-05-16.

### Live accounting

| Bot | Current read | Interpretation |
|---|---:|---|
| `bot_d_live_probe` | `176` live fills, `74` closed trades, `+$31.16` realised P&L, `3` open positions, about `$16.50` open cost | Positive live lane, but still tiny-probe scale. Continue evidence collection; do not scale from dashboard headline alone. |
| `bot_d_maker_live_probe` | `15` live BUY fills, `0` closed trades, `$0.00` realised P&L, about `$20.53` open exposure | The Polymarket account shows live positions, but this is open exposure, not realised P&L yet. |
| `bot_g_prime_live` | `140` live fills, `123` closed trades, about `-$189.08` realised P&L, `1` open position | Do not scale. Treat as negative live evidence unless a later scoped ADR says otherwise. |
| `bot_l_complete_set` | `0` fills in the bot container `main.db` | No realised live P&L yet. Prior Bot L work fixed cap/mechanics and left it idling cleanly at `no_executable_signal`. |
| `crypto_probability_gap_live_maker` | After FV live redemption/accounting closeout: `10` redeemed positions, `$34.8077` redeemed cost, about `+$12.76` realised P&L after fees/rebates, ROI about `+36.66%`; still has open live exposure | Best current live FV signal. Keep tiny-live running at current caps; do not scale until more redeemed rows and dashboard truth are visible. |
| `crypto_brownian_fv_live_maker` | After FV live redemption/accounting closeout: `14` redeemed positions, `$51.4219` redeemed cost, about `-$5.94` realised P&L after fees/rebates, ROI about `-11.56%`; still has open live exposure | Paper looks good but live is weak. Keep tiny only or pause if the next redeemed batch is negative. Do not scale. |

### Maker / paper evidence

Latest 07:35 UTC maker-vs-taker report:

| Lane | State |
|---|---|
| Bot G live-maker paper | `27/31/20`, ROI `+54.07%`, below `n>=50`; wait. |
| Bot G Prime maker | `38/52/25`, ROI `-87.04%`; wait/reject leaning. |
| Bot G shadow maker | `37/41/24`, ROI `-83.48%`; wait/reject leaning. |
| Bot G high-tail maker | `68/84/48`, ROI `-3.56%`, closed count near gate but negative. |
| Bot I Persistence maker | `40/40/40`, ROI `+10.00%`, below `n>=50`; wait. |
| Cell C maker | `69/69/69`, ROI `-0.90%`; ADR-176/OQ-118 blocks the `$1/trade` borderline probe because 95-99c markets need about `$4.75-$4.95` to satisfy the exchange 5-share minimum. |
| FV probability-gap maker | `210/210/203`, ROI `+10.39%`; review-only under ADR-139/OQ-117. |
| FV Brownian maker | `249/249/246`, ROI `+14.45%`; review-only under ADR-139/OQ-117. |

FV still fails concentration/fillability: probability-gap remains concentrated in BTC, 5m, and 120s-300s lead buckets; Brownian has the same problem after the latest close refresh. These are not live-executor approvals.

### FV live-vs-paper update

The first FV maker live batch changed the interpretation:

| Lane | Mode | Closed/redeemed | Cost | P&L | ROI | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| Probability-gap | Live maker | `10` redeemed | `$34.8077` | about `+$12.76` after fees/rebates | about `+36.66%` | Strong first live transfer signal, still tiny sample. |
| Probability-gap | Paper maker same-window | `20` resolved | `$100.00` | `+$15.7594` | `+15.76%` | Positive and directionally confirms live. |
| Brownian | Live maker | `14` redeemed | `$51.4219` | about `-$5.94` after fees/rebates | about `-11.56%` | Live underperforms paper; pause candidate if next batch is negative. |
| Brownian | Paper maker same-window | `22` resolved | `$110.00` | `+$22.5208` | `+20.47%` | Paper positive, but live fill selection is not transferring yet. |

Lifetime FV maker paper remains positive: probability-gap `298` resolved,
`+$179.1565`, ROI `+12.02%`; Brownian `359` resolved, `+$205.6611`, ROI
`+11.46%`.

### Other active paper/maker evidence

| Lane | Current read | Interpretation |
|---|---:|---|
| Bot G live-maker shadow | about `+$10.03` realised on `20` closed | Potentially interesting, but still below gate. |
| Bot G high-tail maker | about `-$1.51` on `48` closed | Flat/weak; near sample gate but not attractive. |
| Bot G prime maker | about `-$67.14` on `25` closed | Poor; do not promote. |
| Bot G shadow maker | about `-$50.52` on `24` closed | Poor; do not promote. |
| Bot J near-resolution wallet paper | Active service, no useful P&L rows yet | Continue collecting only. |
| Bot K sports taker paper | Active service, no useful P&L rows yet | Continue collecting only. |

## Dashboard problem to fix first

The operator can see live trades in the Polymarket account but not a reliable per-bot live P&L surface in the dashboard.

Read-only diagnosis:

- Local source expects `/api/overview` to include `bot_inventory`; `dashboard/static/app.js` uses that to render active live/paper rows with realised P&L and exposure.
- the bot container deployed `dashboard.runtime_queries.query_overview()` returned no `bot_inventory` key at 2026-05-16 07:44 UTC.
- the bot container still returns older `fleet_bots` rows where some rows mix cost/exposure with P&L semantics.
- Example: `bot_d_maker_live_probe` showed roughly `-$20.42` in older overview rows, but `_trade_metrics("bot_d_maker_live_probe")` correctly reports `$0.00` realised P&L and `15` BUY fills. The negative number is open cost/exposure, not closed P&L.

## New decision gate

Before any live parameter tuning, the dashboard must show a live accounting table with:

- bot id and display name;
- realised P&L from FIFO/closed trades;
- open exposure/cost basis;
- open order reserved notional;
- open positions;
- fills and closed count;
- last fill timestamp;
- source label: the bot container DB, VPS bridge, synthetic shadow, or paper DB.

The table must label `realised P&L` separately from `open exposure`; no open BUY cost should be displayed as realised loss unless the position is closed/resolved.

## Maker-revival audit

New hypothesis:

Some historical strategies may have been rejected under taker-like execution
assumptions even though their signal could be viable as maker quotes. The
correct response is not to unarchive old bots blindly; it is to classify each
old theory by why it failed.

### Audit classification

For each retired, parked, or weak paper/live method, classify the historical
failure reason:

| Class | Meaning | Maker-revival priority |
|---|---|---|
| Execution-cost failure | Signal looked directionally useful, but taker fees/spread/slippage killed P&L | High |
| Fillability uncertainty | Paper looked good, but realistic fill transfer was unproven | Medium; maker paper/replay first |
| Signal failure | Labels, prediction quality, or edge were poor before execution costs | Low |
| Data/infra failure | Recorder, labels, joins, or parsing were not good enough to judge | Data repair first |
| Live-transfer failure | Paper positive but live fills select into bad outcomes | Treat cautiously; Brownian currently fits here |

### Candidate revival list

Start with these, in order:

1. Bot G selected maker variants, especially the live-maker shadow. Taker/live was bad, but one maker shadow has positive early evidence.
2. Bot I persistence maker and Cell C maker. Already have maker-specific rows; Cell C remains blocked by exchange minimum mechanics.
3. Bot D maker/live weather. Wait for resolved maker positions before judging; compare against Bot D taker/live and source-shadow.
4. Bot H Maker V2. This was designed as maker-native infrastructure and should be judged by recorder replay, not taker assumptions.
5. Archived crypto/FV variants. Probability-gap is already live-positive; Brownian needs live-transfer diagnosis.
6. Bot A/B/C/E/F historical methods only after an ADR/open-question scan shows they failed mainly on execution cost rather than signal quality.

### Maker-revival output

Create a report:

`docs/reports/maker-revival-audit-2026-05-16.md`

The report should include:

- every historical strategy/lane reviewed;
- original rejection or parked reason with ADR/OQ links;
- whether the original validation was taker, maker, synthetic maker, or unclear;
- available data source for maker replay;
- cheapest maker-proof path;
- whether a paper-maker lane already exists;
- recommended action: `keep archived`, `replay only`, `paper-maker candidate`, `continue existing paper`, or `live-review later`.

No live services are started from this audit.

## Recommended next-session steps

1. Read `AGENTS.md`, `MEMORY.md`, `CHANGELOG.md`, this handoff, `docs/open-questions.md`, and `docs/decisions-log.md`.
2. Confirm current worktree status.
3. Read the dashboard source:
   - `dashboard/runtime_queries.py`
   - `dashboard/static/app.js`
   - `tests/dashboard/test_dashboard.py`
   - `core/bot_registry.py`
4. Query the bot container read-only live accounting again:
   - orders grouped by `bot_id,status`;
   - trades grouped by `bot_id,side`;
   - positions grouped by `bot_id,status`;
   - `_trade_metrics()` for active live bots.
5. Patch dashboard overview so the bot container `/api/overview` exposes `bot_inventory` and a live-accounting row for each active live bot.
6. Add focused dashboard tests proving `bot_d_maker_live_probe` displays `$0.00` realised P&L while separately showing open exposure.
7. Deploy dashboard code to the bot container only after explicit approval to restart `polymarket-dashboard.service`.
8. In parallel, produce `docs/reports/maker-revival-audit-2026-05-16.md` as a report-only review of old theories under maker execution.
9. After dashboard truth is fixed, revisit paper/shadow parameter changes using ROI gates.

## ROI gates for future parameter changes

Paper/shadow parameter changes can be tested now, but live parameter changes need an ADR and should require:

- at least `n>=50` closed rows for the scoped lane;
- positive post-fee ROI;
- positive ROI after ex-largest-one and ex-largest-two stress;
- positive ROI after 1c and 2c per-share cost stress where relevant;
- no single symbol, duration, market family, city, or lead bucket carrying the result;
- real fillability or live-maker transfer evidence, not only synthetic fill assumptions;
- dashboard-visible live accounting before and after any live change;
- named kill switch, cap, rollback, and review date.

For maker-revival candidates, add these extra gates:

- original strategy failed mainly on execution cost or fillability uncertainty,
  not on pre-cost signal failure;
- replay can model maker queue/fill selection, not just assume every quote fills;
- maker result remains positive after adverse-selection stress;
- live-transfer risk is explicitly compared against the Brownian FV mismatch;
- any revived lane starts as report-only or paper-only, never as live.

## Current conclusion

Changing the goal is appropriate. Changing live parameters now is premature.

The immediate next objective is dashboard truth: make live realised P&L and open exposure visible per bot, then use that surface to decide which paper/shadow parameters deserve more evidence and which live probes should be paused, kept, or capped.

The additional objective is maker-revival triage: identify which old taker-era
ideas deserve maker-paper/replay because maker execution may be the missing
edge layer. Profitability and ROI remain the controlling priority.

## Useful commands

Read-only the bot container DB snapshot query pattern:

```bash
ssh hypervisor-host 'pct exec <ctid> -- bash -lc "cd /home/bot/polymarket-bot && ./.venv/bin/python -"' <<'PY'
from dashboard.runtime_queries import _trade_metrics, query_overview

payload = query_overview()
print(sorted(payload.keys()))
for bot_id in [
    "bot_d_live_probe",
    "bot_d_maker_live_probe",
    "bot_d_spike",
    "bot_d_station_lock",
    "bot_g_prime_live",
    "bot_l_complete_set",
]:
    print(bot_id, _trade_metrics(bot_id))
PY
```

Local verification targets after patching:

```bash
./.venv/bin/python -m pytest -q tests/dashboard/test_dashboard.py
node --check dashboard/static/app.js
python3 scripts/repo_secret_scan.py
git diff --check
```

## Related files

- `docs/codex-maker-goal-status-2026-05-16.md`
- `docs/reports/maker-vs-taker-daily-2026-05-16.md`
- `docs/open-questions.md` OQ-117, OQ-118, OQ-119
- `docs/decisions-log.md` ADR-139, ADR-174, ADR-176
- `docs/active-operating-model-2026-05-02.md`
- `docs/reports/crypto-bots-maker-vs-taker-sweep-2026-05-15.md`
- `dashboard/runtime_queries.py`
- `dashboard/static/app.js`
- `tests/dashboard/test_dashboard.py`
- `core/bot_registry.py`
