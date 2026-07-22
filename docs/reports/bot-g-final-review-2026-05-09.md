# Bot G Final Review

**Generated:** 2026-05-09
**Owner:** Codex executing
`docs/codex-bot-g-final-review-handoff-2026-05-09.md`.
**Scope:** Final numbers-first review of `bot_g_prime_live`,
`bot_g_prime`, `bot_g_prime_shadow`, `bot_g_prime_late_cheap`,
`bot_g_prime_take_profit`, plus shared crypto recorder and Bot G
dashboard surfaces.
**Read-only.** No service restarted, no order placed, no live size
/ cap / symbol / price band / lead window changed, no wallet touched.

---

## Executive verdict

| Lane | Recommended decision | Rationale |
|---|---|---|
| `bot_g_prime_live` ($1 micro-probe) | **keep `$1` data probe OR halt** — do **not** scale | 51 closed, 1 win, **-$82.84 / -80.6% ROI all-time** (VPS); ex-largest -$101.98 (single SOL NO is propping up the entire ledger); 18/51 orders fail to fill before market close (35% miss rate); BTC and ETH cells all -100%. No defensible scale path under ADR-135/136. Operator chooses keep $1 (continue collecting fillability + live-mirror evidence) or halt. |
| `bot_g_prime` (paper 4-8c) | **keep paper, hidden default surface, regime monitor only** | 143 closed, 13 wins, +$327.42 / +62.1% ROI; **ex-largest-2 +$87.42** (still positive). Top-3 wins are $95, $120, $120 (multiple ~$120 wins, not single jackpot). But the 6.5c-8c bucket dominates the headline (per ADR-135 evidence: 6 wins/25 closed at +205% ROI). Live-mirror (3.5c-5.5c) contradicts the headline. Do **not** treat as live-readiness signal. |
| `bot_g_prime_shadow` (3.5-5.5c paper mirror) | **keep regime monitor, hidden** | 74 closed, 2 wins (2.7%), -$161.81 / -57.4% ROI; ex-largest -$246.96 (worse). Confirms ADR-135 emergency-pause diagnosis. Required for live-shaped paper benchmark. |
| `bot_g_prime_late_cheap` (1-3c paper) | **propose retirement** (operator approval required) | 152 closed, 1 win (0.7%), **-$560.71 / -86.4% ROI**; ex-largest -$646.02 (worse). Thesis falsified at decisive sample. ADR-128 -100% rolling ROI floor has been violated. Already hidden from dashboard; recommend stop service + status `paper_tuning` → `archived`. |
| `bot_g_prime_take_profit` (synthetic 50c TP) | **propose retirement** (operator approval required) | 65 closed, 1 win (1.5%), -$184.15 / -67.5% ROI; ex-largest -$269.30 (worse). **Take-profit replay shows 0/26 positions ever hit even the 50c threshold; 0 actual TP events fired.** Synthetic 50c TP cannot exit because positions never reach 50c in the final-window proxy. Thesis falsified. Already hidden; recommend stop service + status `paper_tuning` → `archived`. |
| Shared crypto recorder (the bot container + VPS) | **keep, no change** | the bot container 77.30 GB / 0 gaps / 1,724 ev/min; VPS 21.03 GB / 0 gaps / 2,425 ev/min. ADR-122 indefinite. Supports Bot G replay grids + future strategy work. |
| Dashboard Bot G tab | **keep current shape, no change** | `/api/bot-g` and `/api/overview` truthful match to DB. Live + `bot_g_prime` paper visible; shadow/late_cheap/take_profit already hidden from default surface (Session 274 ADR-138). |

### Did any edge survive robust checks?

**No edge survives the full robustness battery for any live or
live-shaped lane.** Specifically:

- `bot_g_prime` paper (4-8c): survives ex-largest-2 trimming
  (+$87.42), but the headline is concentrated in the 6.5c-8c bucket
  which is jackpot-shape per ADR-135. The 4c-5c sub-band (the live
  band) is decisively negative. **The lane is not live-promotable.**
- `bot_g_prime_live` (3.5c-5.5c, BTC/ETH/SOL): only positive cell is
  SOL NO (1/7 wins, +$8.95). Single-win sample is not predictive.
  ex-largest = -$101.98 confirms one SOL NO win is propping up the
  entire ledger. No survival.
- `bot_g_prime_shadow`: same band as live, same negative result
  on a larger sample. No survival.
- `bot_g_prime_late_cheap`: 1 win / 152 closed. No slice survives.
- `bot_g_prime_take_profit`: 1 win / 65 closed. TP threshold was
  never reachable. No survival.

**No live restart at any band, symbol, lead window, or take-profit
threshold is justified by current evidence.**

### Recorder/data retention decision

**Keep the bot container Bot E recorder + VPS crypto recorder running unchanged.**
Both are healthy (0 gaps, sub-second heartbeats) and serve Bot G
replay + Bot H Maker V2 + future strategies. ADR-122 keeps recorders
indefinite; this review does not alter that.

The Bot G family lanes (`bot_g_prime_late_cheap`,
`bot_g_prime_take_profit`) consume recorder data but do not modify
it. Retiring those lanes would NOT affect recorder operation.

### Dashboard changes made this pass

**None.** The dashboard already correctly:

- shows live `$1` probe under "Longshot Prime Live (G)" with VPS
  service `vps:active`, P&L `-$181.50` cumulative, 89 trades, 103
  fills, 88 settlement fills, 2 open positions / $3.88 cost;
- shows paper `bot_g_prime` under "Longshot Prime (G)" with VPS
  service `vps:active`, P&L `+$356.99` cumulative;
- hides `bot_g_prime_shadow`, `bot_g_prime_late_cheap`, and
  `bot_g_prime_take_profit` from the four-card fleet header;
- inventory table shows them under "Active recorders/probes"
  group with ADR-135 regime-monitor framing per Session 274.

If operator approves the proposed retirement of `late_cheap` and
`take_profit`, follow-up dashboard work is:

1. Status `paper_tuning` → `archived` in `core/bot_registry.py`.
2. Drop them from inventory under archived rows (already filtered out
   by Session 275 active-only contract).
3. Stop and disable the two services on the VPS.
4. Add an ADR superseding ADR-128.

### Tests run

```
./.venv/bin/python -m pytest -q tests/dashboard tests/test_bot_registry.py tests/test_bot_g_longshot.py
node --check dashboard/static/app.js
./.venv/bin/python scripts/repo_secret_scan.py
git diff --check
```

Test results recorded in CHANGELOG entry alongside this report.

### Unresolved risks

1. The single SOL NO live win obscures the catastrophic BTC/ETH live
   evidence. Operator needs to act on the negative live evidence
   regardless of one positive cell.
2. Retiring `late_cheap` and `take_profit` requires explicit operator
   approval (per CLAUDE.md "Strategy changes — User decides"); this
   report only proposes the retirement.
3. Dashboard label "Longshot Prime Live (G) paper epoch" for the
   live row is technically a copy quirk (the epoch label suffix
   "paper epoch" is misleading when applied to a live probe). Low
   priority cosmetic fix.

---

## 1. Lane Status Table

Cumulative state per lane as of 2026-05-09 ~14:58 UTC.

| Lane | Service | Status | Mode | Current cash P&L (cumulative, all-time) | Orders | Fills | Closed | Wins | Open pos | Latest fill | Verdict |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `bot_g_prime_live` | `polymarket-bot-g-prime-live.service` | **active (live)** on VPS | live `$1` micro-probe (ADR-136) | **-$82.84** (VPS only); `-$181.50` (the bot container lifetime, includes pre-VPS-migration) | 51 | 33 (+18 EXCHANGE_CLOSED, 35% miss) | 51 | 1 | 2 ($3.88) | 2026-05-09 12:59 UTC | watch_only / halt — no scale |
| `bot_g_prime` | `polymarket-bot-g-prime.service` | **active (paper)** on VPS | paper, 4-8c, BTC/ETH/SOL | +$327.42 (VPS); `+$356.99` (the bot container) | 143 | 143 | 143 | 13 | 0 | 2026-05-09 13:57 UTC | keep (regime/hidden) |
| `bot_g_prime_shadow` | `polymarket-bot-g-prime-shadow.service` | **active (paper)** on VPS | paper, 3.5-5.5c live mirror | -$161.81 (VPS) | 74 | 74 | 74 | 2 | 0 | 2026-05-09 13:56 UTC | keep regime monitor (hidden) |
| `bot_g_prime_late_cheap` | `polymarket-bot-g-prime-late-cheap.service` | **active (paper)** on VPS | paper, 1-3c, 30s window | -$560.71 (VPS) | 152 | 152 | 152 | 1 | 1 | 2026-05-09 14:56 UTC | propose archive |
| `bot_g_prime_take_profit` | `polymarket-bot-g-prime-take-profit.service` | **active (paper)** on VPS | paper, 3.5-5.5c, synthetic 50c TP | -$184.15 (VPS) | 69 | 69 | 69 | 1 | 0 | 2026-05-09 12:56 UTC | propose archive |

**Notes on numbers:**

- VPS P&L is computed from `bot_g_vps_main.db` `trades`: `SUM(CASE
  WHEN side='BUY' THEN -price*size - fee_usd ELSE price*size -
  fee_usd END)` per condition_id, then summed.
- the bot container P&L (lifetime) is the dashboard `/api/bot-g` headline,
  includes pre-VPS-migration entries.
- "Closed" = positions resolved with SELL/redemption. For
  `bot_g_prime_live`, 51 conditions are closed; 1 of the 51 had a
  win (SOL NO at 4c).
- "EXCHANGE_CLOSED" orders are `bot_g_prime_live` orders that were
  placed but the market closed before fill — fillability proxy for
  live, not for paper (paper fills synthetically from recorder).

---

## 2. Edge Survival Table

Each row = a candidate slice. "Decision" reflects whether it is
edge-positive after fees, 1c stress, ex-largest, top-k/concentration,
fillability, no-lookahead.

| Slice | Lane | Sample | Net P&L / ROI | ex-largest | ex-largest-2 | Fillability | Data quality | Decision |
|---|---|---:|---:|---:|---:|---|---|---|
| All-band live (3.5-5.5c, BTC/ETH/SOL) | `bot_g_prime_live` | 51 closed, 1 win | -$82.84 / -80.6% | -$101.98 | -$101.55 | 35% miss (EXCHANGE_CLOSED) | OK | dead |
| 4c-5c live | `bot_g_prime_live` | 28 closed, 1 win | -$28.90 / -59.1% | not computed (only 1 win) | not computed | OK | OK | dead |
| 5c-6c live | `bot_g_prime_live` | 19 closed, 0 wins | -$45.20 / -100% | n/a | n/a | OK | OK | dead |
| <30s lead live | `bot_g_prime_live` | 18 closed, 0 wins | -$37.48 / -100% | n/a | n/a | OK | OK | dead |
| 30s-45s lead live | `bot_g_prime_live` | 9 closed, 0 wins | -$14.81 / -100% | n/a | n/a | OK | OK | dead |
| 45s-60s lead live | `bot_g_prime_live` | 20 closed, 1 win | -$21.81 / -52% | -$40.95 | n/a | OK | OK | dead (1 win not predictive) |
| Asia overnight live | `bot_g_prime_live` | 17 closed, 0 wins | -$30.26 / -100% | n/a | n/a | OK | OK | dead |
| Europe morning live | `bot_g_prime_live` | 12 closed, 1 win | -$5.39 / -21.2% | -$25.00 | n/a | OK | OK | dead (1 win not predictive) |
| US overlap live | `bot_g_prime_live` | 11 closed, 0 wins | -$22.02 / -100% | n/a | n/a | OK | OK | dead |
| Late US live | `bot_g_prime_live` | 7 closed, 0 wins | -$16.43 / -100% | n/a | n/a | OK | OK | dead |
| Volatility low | `bot_g_prime_live` | 21 closed, 1 win | -$19.07 / -48.8% | -$38.14 | n/a | OK | OK | dead (1 win not predictive) |
| Volatility medium/high | `bot_g_prime_live` | 26 closed, 0 wins | -$55.03 / -100% | n/a | n/a | OK | OK | dead |
| BTC YES live | `bot_g_prime_live` | 13 closed, 0 wins | -$39.04 / -100% | n/a | n/a | OK | OK | dead |
| BTC NO live | `bot_g_prime_live` | 10 closed, 0 wins | -$19.42 / -100% | n/a | n/a | OK | OK | dead |
| ETH YES live | `bot_g_prime_live` | 8 closed, 0 wins | -$12.37 / -100% | n/a | n/a | OK | OK | dead |
| ETH NO live | `bot_g_prime_live` | 5 closed, 0 wins | -$7.04 / -100% | n/a | n/a | OK | OK | dead |
| **SOL NO live (4c-5c, 45-60s lead, low vol, Europe morning UTC 09)** | `bot_g_prime_live` | **7 closed, 1 win** | +$8.95 / +81% | -$10.19 | n/a | OK | OK | **single-win not predictive; sample too small** |
| SOL YES live | `bot_g_prime_live` | 4 closed, 0 wins | -$5.19 / -100% | n/a | n/a | OK | OK | dead |
| All-time paper 4-8c | `bot_g_prime` | 143 closed, 13 wins | +$327.42 / +62.1% | +$207.42 | **+$87.42** | OK (paper synthetic) | OK | survives ex-2 but jackpot-shape; live-prohibited |
| 6.5c-8c paper bucket | `bot_g_prime` | 25 closed, 6 wins | +$192.54 / +205% (per ADR-135) | not computed | not computed | OK (paper synthetic) | OK | jackpot-driven; do not promote |
| 3.5-5.5c paper mirror (live-shape) | `bot_g_prime_shadow` | 74 closed, 2 wins | -$161.81 / -57.4% | -$246.96 | -$276.91 | OK (paper synthetic) | OK | dead (live-shape) |
| 1-3c paper near-close | `bot_g_prime_late_cheap` | 152 closed, 1 win | -$560.71 / -86.4% | -$646.02 | -$645.01 | OK (paper synthetic) | OK | dead |
| 3.5-5.5c + synthetic 50c TP | `bot_g_prime_take_profit` | 65 closed, 1 win | -$184.15 / -67.5% | -$269.30 | -$268.10 | OK (paper synthetic) | OK | dead; **TP threshold never hit (0/26 in replay)** |

**Survival summary:** Only `bot_g_prime` paper at 4-8c survives
ex-largest-2 trimming. The same lane's 4c-5c sub-band is the live
band; the live evidence on that band is decisively negative.
Promotion of any other slice to live is blocked by ADR-135.

---

## 3. Next Action Table

Sorted by priority. Operator approval flagged where applicable.

| Priority | Action | Lane / slice | Why | Expected benefit | Time to resolve | Risk | Approval needed? |
|---:|---|---|---|---|---|---|---|
| 1 | **Operator decision: keep `$1` live probe, or halt it** | `bot_g_prime_live` | -78.75% on 47 closed (168h); -80.6% all-time on 51 closed; ex-largest -$101.98. No defensible scale path under ADR-135/136 | Frees the $1/day live capital usage, simplifies live posture | same day (operator decision) | low (probe is `$1` cap) | **YES** |
| 2 | **Propose retirement: `bot_g_prime_late_cheap`** | `bot_g_prime_late_cheap` | 1 win / 152 closed; -86.4% ROI; ADR-128 floor violated; thesis falsified | Frees recorder/CPU; declutters service inventory | 1 day after approval | low | **YES** |
| 3 | **Propose retirement: `bot_g_prime_take_profit`** | `bot_g_prime_take_profit` | TP threshold never hit (0/26 positions in replay); 1 win / 65 closed; -67.5% ROI; thesis falsified | Frees recorder/CPU; declutters | 1 day after approval | low | **YES** |
| 4 | **Keep `bot_g_prime_shadow` running** | `bot_g_prime_shadow` | Required as live-shaped paper benchmark (ADR-135 regime monitor). 74 closed -57.4% confirms diagnosis | Detects regime change before any future live restart | continuous | low | none |
| 5 | **Keep `bot_g_prime` paper running, hidden from default surface** | `bot_g_prime` | Generates baseline data; +$87.42 ex-largest-2 keeps the optionality of a future ADR if the 6.5c-8c bucket reproduces in a forward sample | Optionality; cheap to run | continuous | low | none |
| 6 | **Recorder no-change** | shared crypto recorder | ADR-122 indefinite | n/a | n/a | low | none |
| 7 | **Cosmetic dashboard fix: live row epoch label says "paper epoch"** | dashboard `/api/bot-g` simple/fleet | Misleading copy on live row | none | low | low | none |

**No real-money order will be placed by this report.** All "propose"
actions require operator approval before any service is stopped or
registry status changes.

---

## 4. Archive / Keep Decision Table

| Component | Decision options | Recommended decision | Rationale |
|---|---|---|---|
| `bot_g_prime_live` | keep `$1` / halt / archive live path | **operator-decision pending — keep $1 OR halt** | Live evidence is decisively negative across BTC/ETH/SOL except for one SOL NO win (1/7) that is not statistically predictive. Per ADR-136 the lane was approved for data collection at $1; current 47-closed sample answers the data question. **Operator chooses: continue collecting fillability evidence OR halt; do NOT scale.** |
| `bot_g_prime` | keep paper / hide / archive | **keep paper, hidden** | Survives ex-largest-2 (+$87.42) but is jackpot-driven by 6.5c-8c. Optionality for future research without scale risk. Already hidden from default fleet header per Session 274 ADR-138 (note: `dashboard_visible=True` in registry but the "main four" cards still show it; the inventory table is what changed). |
| `bot_g_prime_shadow` | keep regime monitor / hide / archive | **keep regime monitor, hidden** | 74 closed -57.4% confirms ADR-135 emergency-pause diagnosis. Required if a future live restart is ever proposed. |
| `bot_g_prime_late_cheap` | keep / hide / archive | **propose archive** (operator approval needed) | 152 closed / 1 win / -86.4% ROI; ADR-128 -100% floor violated; thesis dead. Already hidden from dashboard. |
| `bot_g_prime_take_profit` | keep / hide / archive | **propose archive** (operator approval needed) | TP replay shows 0/26 positions hit threshold; thesis falsified. Already hidden from dashboard. |
| Shared crypto recorder | keep / narrow / expand / stop | **keep unchanged** | ADR-122 indefinite; serves Bot G + Bot H + replay grids. |
| Dashboard Bot G tab | keep / simplify / remove slices | **keep current shape** | Truthful match to DB; archived/hidden lanes already filtered. Cosmetic "paper epoch" label fix on live row is low-priority. |

---

## Data / Recorder Notes

- **the bot container Bot E recorder** — 77.30 GB, 57.7M pm_events, 104.7M
  cex_trades, 0 gaps, 1.5M heartbeats, ADR-122 indefinite. Healthy.
- **VPS crypto recorder paper-feed** — 21.03 GB, 16.85M pm_events,
  18.30M cex_trades, 0 gaps, hb 15.1s, 2,425 ev/min. Symbols:
  ETHUSDT 8.48M / BTCUSDT 7.15M / SOLUSDT 2.57M / DOGEUSDT 73,917 /
  XRPUSDT 32,670. Per Session 270 records BTC/ETH/SOL/XRP/DOGE for
  context; live trades remain BTC/ETH/SOL.
- **Bot G replay grid (`scripts/bot_g_crypto_replay_grid.py`)** —
  unchanged; can run against either recorder DB if operator wants
  parameter probing while live is paused/halted. **Recommendation:**
  do not run new replay grids until the live probe direction is
  resolved; current evidence dominates.
- **Take-profit replay** — `docs/reports/bot-g-take-profit-replay-2026-05-08.json`
  shows 0/26 positions hit even the 50c threshold across 26 closed
  positions inspected. The synthetic 50c TP cannot exit because
  positions never reach 50c in the final-window proxy. Threshold
  ladder (0.50, 0.70) produces identical -100% outcomes. **TP is
  decisively falsified.**
- **Daily probe report (`scripts/bot_g_daily_probe_report.py`)** —
  active 06:11 UTC daily timer on VPS. Latest report
  `data/reports/bot_g_daily_probe/latest.json` 2026-05-09 10:36
  UTC. Slice tables consumed for this review.
- **Bot G symbol/time/liquidity slice (`docs/reports/bot-g-symbol-time-liquidity-slice-2026-05-09.md`)**
  — unchanged from Session 268; this review reaffirms its
  conclusions.

---

## Dashboard Truth Notes

`/api/bot-g` and `/api/overview` were both queried fresh at 14:58
UTC. Truth check:

- ✅ Live row P&L (`-$181.50` lifetime) matches the bot container main DB +
  VPS positions reconciliation.
- ✅ `bot_g_prime` paper (`+$356.99`) matches the bot container main DB.
- ✅ Service states show `polymarket-bot-g-prime-live` and
  `polymarket-bot-g-prime` as `vps:active`.
- ✅ 89 live trades / 103 fills / 88 settlement fills / 2 open / $3.88
  cost matches DB.
- ✅ Inventory table for live shows VPS-only counts (51 orders,
  -$82.84) which matches `bot_g_vps_main.db` (post-migration only).
- ⚠️ Cosmetic: live row epoch label is `"Longshot Prime Live (G)
  paper epoch"` even though the lane is live. Low-priority copy fix.
- ✅ `bot_g_prime_shadow`, `bot_g_prime_late_cheap`,
  `bot_g_prime_take_profit` are not in the four-card fleet header
  (consistent with Session 274 ADR-138).

No priority alert fires. No edge in this review crosses the
priority-edge protocol bar.

---

## Open Questions update

- **OQ-051 — Bot G split-cohort EV proof before any tuning or live
  argument:** ANSWERED. Cohort-level evidence is decisive: no live
  slice survives the robustness battery. ex-largest, top-k,
  fillability, lookahead checks all consistent with ADR-135. **Mark
  RESOLVED with reference to this report and ADR-135.**
- **OQ-063 — Bot G post-live tiny-probe proof and scale decision:**
  ANSWERED. 47-closed sample with -78.75% ROI provides the proof.
  Scale decision: **no scale** under current evidence. **Mark
  RESOLVED.**
- **OQ-066 — Bot G XRP/DOGE live-universe proof:** DEFERRED. XRP/DOGE
  are not in the live universe, only the recorder. No new evidence to
  resolve. Keep open with note that the question is moot until the
  live universe ever expands beyond BTC/ETH/SOL.
- **OQ-068 — Bot G crypto recorder replay grid for parameter
  tuning:** Keep open. Recorder data continues to accumulate;
  replays remain useful if live restart is ever proposed.
- **OQ-070 — Bot G live on-chain redemption automation:** Keep open.
  Active for the `$1` probe lifecycle if the operator keeps it.
- **OQ-094 — Bot G discrete hazard, score decomposition, tail
  concentration audit:** ANSWERED by 2026-05-08 reports
  (`docs/reports/bot-g-hazard-score-audit-2026-05-08.md`,
  `docs/reports/fleet-probability-score-decomposition-2026-05-08.md`,
  `docs/reports/bot-g-take-profit-replay-2026-05-08.md`). Resolution
  near zero confirms entry rule has no discrimination power. **Mark
  RESOLVED.**
- OQ-085 already SUPERSEDED in Session 274 — no change.
- OQ-043, OQ-044 — Bot G fill-path investigation: Bot G live fills
  via CLOB (33 FILLED out of 51 orders attempts; 18 EXCHANGE_CLOSED).
  Keep open — fill-path investigation may remain relevant for the
  $1 probe.

---

## ADR proposal (NOT added to decisions-log.md without operator approval)

**Proposed ADR-139: Retire bot_g_prime_late_cheap and
bot_g_prime_take_profit paper lanes**

**Status:** **proposed; operator approval required.** Not added to
`docs/decisions-log.md` in this read-only pass.

**Context:**
- `bot_g_prime_late_cheap`: 152 closed / 1 win / -$560.71 / -86.4%
  ROI. ADR-128 set a -100% rolling ROI floor; floor violated.
- `bot_g_prime_take_profit`: 65 closed / 1 win / -$184.15 / -67.5%
  ROI. Take-profit replay proves the 50c threshold is never reached
  (0/26 positions in the final-window proxy).

**Decision:** Retire both lanes. Specifically:

1. Stop and disable on VPS:
   - `polymarket-bot-g-prime-late-cheap.service`
   - `polymarket-bot-g-prime-take-profit.service`
2. `core/bot_registry.py`: `paper_tuning` → `archived` for both;
   description tightened to record the falsification.
3. Update `docs/active-operating-model-2026-05-02.md` to remove the
   two lanes from "Shared Data Infrastructure" and add to "Archived
   Active Surfaces".
4. Supersede ADR-128 (which had explicit "keep collecting" intent).

**Consequences:**
- Frees a small VPS CPU/memory footprint and two service slots.
- Simplifies dashboard inventory.
- Does not affect Bot G live $1 probe, paper Prime (4-8c), or
  paper shadow regime monitor.
- Does not affect recorders.

**Rollback:** Re-enable services if a future ADR proposes a fresh
thesis with concrete forward evidence.

**Operator action:** approve or decline the proposal. If approved,
this report writer (or a future Codex pass) will execute the four
items above and append ADR-139 to `docs/decisions-log.md`.

---

## Commands and queries used

```bash
# the bot container dashboard truth
ssh -o ConnectTimeout=8 root@hypervisor-host 'pct exec <ctid> -- curl -fsS --max-time 20 http://127.0.0.1:8090/api/bot-g'
ssh -o ConnectTimeout=8 root@hypervisor-host 'pct exec <ctid> -- curl -fsS --max-time 20 http://127.0.0.1:8090/api/overview'

# VPS systemd inventory
ssh -i ~/.ssh/id_ed25519 operator@198.51.100.1 \
  'systemctl --type=service --state=running | grep -iE "bot-g|crypto-recorder"'

# VPS bot_g_vps_main.db queries
ssh ... '/home/operator/longshot-research/.venv/bin/python3 /tmp/_bg_paper.py'
# trades + per-condition net + ex-largest/ex-largest-2 per lane
ssh ... '/home/operator/longshot-research/.venv/bin/python3 /tmp/_bg_fill.py'
# orders status distribution; latest fill per lane; live BUY price/size dist
ssh ... '/home/operator/longshot-research/.venv/bin/python3 /tmp/_bg_slice.py'
# daily probe latest.json: by_live_price_point, by_live_lead, by_live_session,
# by_live_volatility, by_live_watch_bucket, by_live_macro_window, by_live_utc_hour
ssh ... '/home/operator/longshot-research/.venv/bin/python3 /tmp/_bg_tp2.py'
# take-profit replay summaries (0/26 hit threshold)

# Reports + ADRs read
docs/reports/bot-g-symbol-time-liquidity-slice-2026-05-09.md
docs/reports/bot-g-tp50-expanded-clustered-validation-2026-05-08.md
docs/reports/bot-g-hazard-score-audit-2026-05-08.md
docs/reports/bot-g-take-profit-replay-2026-05-08.json
docs/reports/bot-g-multi-model-deep-analysis-2026-05-07.md
docs/reports/bot-g-paper-vs-live-divergence-2026-05-06-the bot container.md
docs/decisions-log.md (ADR-085, ADR-098, ADR-101, ADR-118, ADR-128,
                       ADR-135, ADR-136, ADR-138)
docs/open-questions.md (OQ-043, OQ-044, OQ-051, OQ-063, OQ-066,
                        OQ-068, OQ-070, OQ-085, OQ-094)
core/bot_registry.py
bots/bot_g_longshot/{config.py, __main__.py}
```
