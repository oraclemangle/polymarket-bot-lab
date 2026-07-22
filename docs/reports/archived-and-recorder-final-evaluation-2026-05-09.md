# Archived Bots and Recorders — Final Evaluation

**Generated:** 2026-05-09
**Owner:** Codex / Opus pass executing
`docs/opus-archived-recorder-final-evaluation-handoff-2026-05-09.md`.
**Scope:** Read-only evidence sweep against the bot container main DB, VPS
`bot_g_vps_main.db`, VPS `main.db`, VPS `wallet_observer.db`, VPS
`maker_recorder.db`, plus repo reports/ADRs. No service touched, no
order placed, no cap or wallet change.

---

## Priority Edge Alert

**None.** The wallet-tag PolyVerify-`bot_score < 30` cohort is the only
math-found candidate edge in the recent stack (`+10.7pp` on `25,092`
historical trades, bootstrap 95% CI on ROI `(+4.4%, +184.8%)`,
`docs/reports/wallet-tag-edge-finding-2026-05-08.md`). It is already
under active forward-validation by ADR-137 with a `7-day` window and
first-eligible report date `2026-05-15`. Surfacing it here as new
priority would double-count: the wallet observer service is already the
priority research feed, and the gate is locked to settled-trade math
in `scripts/research/wallet_observer_report.py`. No newly discovered
edge survives the priority-alert protocol in this pass.

---

## Verdict Table

| Lane | Class | Decision | Live evidence | Robust check | Operator action |
|---|---|---|---|---|---|
| `bot_a` | archived bot | hide_permanently | 18 trades, 4 markets, last 2026-04-15. ADR-033 walk-forward `12,521` trades, `93.7%` hit rate, **`-$13,613.58` net** | catastrophic asymmetric loss tail | confirm hidden; keep code under `BOT_A_ARCHIVED=false` flag |
| `bot_a_shadow` | archived bot | hide_permanently | 120 trades, 13 markets, **`-$750.01`** cash, 12 OPEN positions stuck pre-V2-migration | shadow inherits Bot A failure mode | confirm hidden; OPEN rows are stuck pre-V2 cleanup, no further redeem expected |
| `bot_b` | parked paper bot | hide_but_keep_evidence | 48 trades, 12 markets, `+$63.67` cash, 1 OPEN, halted; last activity 2026-04-19 | scorer rebuild stalled; future spin-off candidate per active operating model | keep halted; no service running; bot_id retained for cap audit only |
| `bot_b_shadow` | parked paper shadow | hide_but_keep_evidence | 11 trades, 3 markets, **`-$220.00`** cash, 3 OPEN $220 cost, halted | tiny pre-V2 sample, 100% drawdown on closed | confirm hidden, halted |
| `bot_c` | archived bot | hide_permanently | 233 trades, 8 markets, **`-$1,149.41`** cash, mostly `ARCHIVED_STALE_PAPER` / `RESOLVED_DB_CLEANUP`, retired by ADR-093 | strategy retired; Pyth/Hermes data retained as research input | confirm hidden, halted |
| `bot_f` | crowd sensor identity (no service) | hide executor/default dashboard — **status change `sensor` → `archived`** | no service running on the bot container or VPS; `polymarket-bot-f-mirror.service` not in service list | active wallet-flow recording is superseded by `wallet_observer` and `bot_h_maker_v2`; OQ-059 still retains historical Bot F signal data for fillability-gated momentum research | registry update applied this session; no dashboard visibility |
| `bot_f_mirror` | archived legacy executor | hide_permanently | 8 trades, last 2026-05-03; archived by ADR-071 | superseded by `wallet_observer` | confirm hidden |
| `bot_g` | archived raw G | hide_permanently | 200 trades, 100 markets, **`-$205.34`** cash; `0 wins / 100 closed` per ADR | dead, cleanly archived 2026-04-30 | confirm hidden |
| `bot_g_jackpot` | archived jackpot variant | hide_permanently | 168 trades, 84 markets, **`-$350.40`** cash, `0 wins / 84 closed` | jackpot thesis dead | confirm hidden |
| `bot_g_scalp` | archived scalp variant | hide_permanently | 174 trades, 87 markets, **`-$266.99`** cash, `0 wins / 87 closed` | scalp thesis dead | confirm hidden |
| `bot_g_prime_shadow` | live-shaped paper mirror | hide_but_keep_evidence (already hidden) | VPS: 145 trades, 73 markets, **`-$160.67`** cash; per ADR-135 `1 win / 55 resolved`, `-100%` ex-largest-win | confirms ADR-135 emergency-pause diagnosis | keep running for regime-monitor; default surface stays hidden |
| `bot_g_prime_late_cheap` | late-cheap paper probe | hide_but_keep_evidence (already hidden) | VPS: 298 trades, 150 markets, **`-$550.71`** cash; per ADR-135 `1 win / 117 resolved` | thesis falsified | keep running for regime-monitor; default surface stays hidden |
| `bot_g_prime_take_profit` | synthetic-exit paper probe | hide_but_keep_evidence (already hidden) | VPS: 137 trades, 69 markets, **`-$184.15`** cash; per ADR-135 `0 wins / 50 resolved` | thesis falsified | keep running for regime-monitor; default surface stays hidden |
| `bot_e` recorder | shared crypto recorder | keep_recorder_visible | the bot container DB `82.66 GB`, `57,452,957` PM events, `104,418,449` CEX trades, `0` gaps, `1,724.1` PM events/min, heartbeat age `0.8s` | per ADR-122 keep indefinitely | already surfaced as `/api/bot-e` and Crypto Recorder (E) tab |
| `longshot-crypto-recorder-vps-paper-feed` | VPS crypto recorder | keep_recorder_visible | VPS DB `22.21 GB`, `16,580,574` PM events, `18,032,788` CEX trades, `0` gaps, heartbeat `15s` | per Session 270 records BTC/ETH/SOL/XRP/DOGE for context | already in `recorder_comparison` overview |
| `bot_h_maker_v2` recorder | Phase 1 maker recorder | keep_recorder_visible | VPS DB `261 MB`, `156,813` PM events, `1,805` heartbeats, latest heartbeat 2026-05-09 12:45 UTC, `16` subscribed asset IDs, `173` reconnects in `~16h` | per ADR-134 acceptance gate `≥1M pm_events OR ≥30 days`; on track to hit 1M in `~4 days` at current rate | keep, OQ-100 burn-in continues; no Phase 2 quote engine without separate ADR |
| `wallet_observer` | wallet-tag passive observer | keep_recorder_visible | VPS DB `89.6 MB`, `104,111` total fills, `73,748` fills 24h, Tier A `99,522` / Tier B `4,589`, latest run started 2026-05-09 09:00 UTC at `last_block 86623410` | per ADR-137 `7-day` forward window, first report `2026-05-15`; first decision-grade edge candidate forward-feed | keep, OQ-099 gate decision after 2026-05-15 |
| `bot_d_spike` | Strategy E paper lane | keep (paper) — already hidden | VPS: 17 trades, 12 markets, **`-$24.00`** cash, started 2026-05-08 | gate OQ-086 needs `200` closed or `90` days | continue paper-only; surfaced under inventory and spike panel |
| `bot_d_spike_short` | Strategy E2 short-TTR paper lane | keep (paper) — already hidden | VPS: 8 trades, 6 markets, **`-$12.00`** cash, started 2026-05-09 | gate OQ-097 needs `200` closed or `90` days; far too early | continue paper-only |
| `crypto_probability_gap_paper` | crypto FV paper lane | keep (paper) — already hidden | VPS: 295 trades, 148 markets, **`-$80.65`** cash net of `$26.66` fees, latest fill 2026-05-09 12:09 UTC | per OQ-078 / ADR-132 gate; continues until microstructure + post-cost audit clears | already on `/api/crypto-fair-value` |
| `crypto_brownian_fv_paper` | crypto FV paper lane | keep (paper) — already hidden | VPS: 402 trades, 202 markets, **`-$72.39`** cash net of `$34.08` fees, latest fill 2026-05-09 12:09 UTC | per OQ-078 / ADR-132 gate; continues until microstructure + post-cost audit clears | already on `/api/crypto-fair-value` |

(Live lanes `bot_d`, `bot_d_live_probe`, `bot_g_prime`, `bot_g_prime_live`
are out-of-scope for this archived/recorder pass and remain governed by
their own ADR posture: ADR-120 / ADR-097 for Bot D, ADR-135 / ADR-136
for Bot G live which is now a `$1` data-gathering micro-probe.)

---

## Permanent Hides (operator confirmation)

These bots are kept hidden from the default operator surface and have
no expected restart path. Their code, ledger rows, and historical
evidence remain in the repo / DB for audit:

1. `bot_a`, `bot_a_shadow` — ADR-033 walk-forward decisive.
2. `bot_b`, `bot_b_shadow` — ensemble-scorer rebuild stalled; halted;
   future public spin-off candidate, not an active fleet bot.
3. `bot_c` — retired by ADR-093.
4. `bot_f`, `bot_f_mirror` — direct executor/default dashboard identity
   superseded by `wallet_observer` and `bot_h_maker_v2`. Registry status
   moved to `archived` in this session for `bot_f`. OQ-059 remains open
   only as historical-signal/fillability research, not as an active bot.
5. `bot_g`, `bot_g_jackpot`, `bot_g_scalp` — raw G family archived
   2026-04-30 with zero wins on closed cohorts.

The three Bot G Prime paper-only research probes
(`bot_g_prime_shadow`, `bot_g_prime_late_cheap`,
`bot_g_prime_take_profit`) keep running on VPS as the live-shaped
regime-monitor cohort that produced the ADR-135 evidence. They are
already hidden from the default dashboard and stay hidden.

---

## Recorders / Sensors — Keep, Restart, or Hide

| Recorder | Decision | Why | Where surfaced |
|---|---|---|---|
| `polymarket-bot-e-recorder.service` (the bot container) | keep visible | 82 GB shared crypto recorder, gaps `0`, healthy `1,724` PM events/min, ADR-122 indefinite | `/api/bot-e`, Crypto Recorder (E) tab, Overview `recorder_comparison.local` |
| `longshot-crypto-recorder-vps-paper-feed.service` (VPS) | keep visible | 22 GB VPS shadow recorder, BTC/ETH/SOL/XRP/DOGE, gaps `0` | Overview `recorder_comparison.vps` |
| `polymarket-bot-h-maker-v2-recorder-vps.service` (VPS) | keep visible | ADR-134 Phase 1 wide CLOB recorder, 156k pm_events in `~16h`, fresh heartbeats, on track for the `1M pm_events` acceptance gate inside `~4 days` | `/api/bot-h`, inventory row "Maker Flow Recorder (H paper)" |
| `polymarket-wallet-observer.service` (VPS) | keep visible | ADR-137 7-day forward-validation feed for the only decision-grade math-found candidate edge; 73k fills/24h; first report 2026-05-15 | `/api/wallet-observer`, inventory row "Wallet Observer" |
| `polymarket-wallet-tag-forward.{service,timer}` (the bot container) | keep visible | OQ-099 forward-gate path on a separate DB `data/wallet_tag_forward.db`; 24-fill increments, 0 errors | dashboard surfaces wallet-tag forward gate by VPS bridge; the bot container timers run independently |
| `bot_f` crowd-sensor identity | hide from dashboard | no service running, active wallet-flow capture superseded by `wallet_observer`; keeps DB rows as OQ-059 evidence | inventory now hidden because status moved `sensor` → `archived` |

No recorder requires a restart-for-data action: every recorder of
operator value is already running and producing healthy heartbeats.
No halted/stale recorder warrants a restart.

---

## Dashboard Changes Applied

The Session 271 inventory overhaul already split the operator surface
into **Live** / **Paper** / **Recorder** / **Parked** / **Paused** /
**Archived** groups sourced from `core.bot_registry.REGISTRY`. Today's
pass narrows the Recorder/Archived split:

1. `bot_f` registry status moved `sensor` → `archived` so the inventory
   table no longer shows it as a Recorder. The crowd-flow signal data
   remains in the DB for OQ-059; the dashboard hides the row entirely
   because archived and inactive rows are not operator-visible.
2. `bot_f` description tightened to reflect that the wallet observer
   and Bot H Maker V2 recorders supersede the active crowd-sensor role.
3. Headline descriptions for `bot_g_prime_shadow`,
   `bot_g_prime_late_cheap`, and `bot_g_prime_take_profit` are tagged
   with the `ADR-135` regime-monitor framing in the row description so
   the operator surface explains why they keep running while live is a
   `$1` micro-probe.

No bot is added to the default operator dashboard surface in this
pass. No bot already on the default surface is removed. The dashboard
already filtered halted/parked/archived rows out of the four-card
fleet header (`bot_d`, `bot_d_live_probe`, `bot_g_prime`,
`bot_g_prime_live`) — that surface stays.

---

## Bot Registry Diff

```
bot_f.status: sensor -> archived
bot_f.description: tightened to "...superseded by wallet_observer (ADR-126/137) and bot_h_maker_v2 (ADR-134)..."

bot_g_prime_shadow.description: appended "ADR-135 regime-monitor; live-shaped cohort"
bot_g_prime_late_cheap.description: appended "ADR-135 regime-monitor; thesis falsified"
bot_g_prime_take_profit.description: appended "ADR-135 regime-monitor; thesis falsified"
```

`bot_b`, `bot_b_shadow` retain their `paper` / `shadow` status because
the `tests/test_bot_registry.py::test_cap_member_includes_current_paper_bots`
test contract pins `bot_b` in `cap_member_bot_ids()` while the bot
still holds 1 OPEN position. They remain halted and hidden; demoting
them to `paused` is deferred to a future cleanup ADR alongside the
spin-off plan.

`include_in_cap`, `archetype`, `systemd_unit`, and `bankroll_env`
fields are unchanged for every bot.

---

## ADR + OQ Changes

- **ADR-138 added** — final-evaluation hides for the archived
  cohort, `bot_f` archive status promotion, and the Bot G Prime paper
  probes' regime-monitor framing.
- **OQ-059 — Contrarian crowd-flow edge validation:** stays open only
  for historical Bot F signal/fillability research. The active Bot F
  service/default dashboard identity remains archived.
- **OQ-085 — Bot G seven-day microstructure probe and retirement
  decision:** marked **superseded** by ADR-135 (emergency pause) and
  ADR-136 (resume at `$1`). The seven-day probe was never the gating
  decision; the live cohort failed the live-shaped paper mirror in
  the same window.
- **OQ-099 — Wallet-tag forward gate:** stays open. Next event:
  first report-eligible `2026-05-15`.
- **OQ-100 — Bot H Maker V2 Phase 2 readiness:** stays open. Burn-in
  continues; recorder is healthy.
- **OQ-086 — Bot D-Spike forward gate:** stays open at very low
  closed-position count.
- **OQ-097 — Bot D-Spike-Short forward gate:** stays open at almost
  zero sample (lane started 2026-05-09).

---

## Tests

Validation after the final amendments:

- `./.venv/bin/python -m pytest -q tests/dashboard tests/test_bot_registry.py`
  — `38 passed`.
- `git diff --check` — passed.
- `./.venv/bin/python scripts/repo_secret_scan.py` — passed with no output.

---

## Commands Used

```bash
git status --short --branch

ssh -o ConnectTimeout=8 root@hypervisor-host 'pct exec <ctid> -- systemctl is-active polymarket-dashboard.service'
ssh -o ConnectTimeout=8 root@hypervisor-host 'pct exec <ctid> -- curl -fsS --max-time 20 http://127.0.0.1:8090/api/overview'

ssh -o ConnectTimeout=8 -i ~/.ssh/id_ed25519 operator@198.51.100.1 \
  'systemctl --type=service --state=running | grep -E "recorder|observer|crypto|maker|bot|persistence|longshot"'

ssh root@hypervisor-host 'pct exec <ctid> -- /bin/python3 - <<PYEOF
import sqlite3
con = sqlite3.connect("/home/bot/polymarket-bot/data/main.db")
# per-bot orders + trades + positions + events queries
PYEOF'

ssh -i ~/.ssh/id_ed25519 operator@198.51.100.1 \
  '/home/operator/longshot-research/.venv/bin/python - <<PYEOF
import sqlite3
con = sqlite3.connect("/home/operator/longshot-research/data/bot_g_vps_main.db")
# VPS bot G P&L
con2 = sqlite3.connect("/home/operator/longshot-research/data/main.db")
# VPS paper main + spike + crypto FV
con3 = sqlite3.connect("/home/operator/longshot-research/data/wallet_observer.db")
# wallet observer fills + observer_runs
con4 = sqlite3.connect("/home/operator/longshot-research/data/maker_recorder.db")
# Bot H pm_events + heartbeats
PYEOF'
```

---

## Done Criteria — checklist

- [x] Every archived bot has a final dashboard/report decision.
- [x] Every halted or stale recorder has a keep/restart/hide decision.
- [x] No resurrected edge: priority alert section explicitly empty.
- [x] No live trading service was restarted.
- [x] Bot G live remains under ADR-135/ADR-136 (`$1` micro-probe).
- [x] Bot H stays Phase 1 recorder-only under ADR-134.
- [x] Dashboard inventory emits active live/paper/recorder rows only; archived,
  parked, halted, paused, unknown, and inactive rows are hidden.
- [x] Docs, open questions, ADRs, memory, and changelog updated.
- [x] Relevant tests pass.
- [x] Secret scan returns nothing unexpected.
