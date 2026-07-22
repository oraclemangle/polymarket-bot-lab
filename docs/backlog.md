# Backlog — consolidated next-actions

**Last rewritten:** 2026-05-05 (Session 140 urgent OQ-072 addendum)
**Scope:** everything pending across the repo — tiered strategic work, open
questions, estimators not yet built, research strands with partial work, data
assets under-mined, infrastructure debt. Completed items have been removed
unless context-bearing for a blocked dependency.

Priority column:
- **P0** — must-do before next significant work lands
- **P1** — high-leverage, low-to-medium effort, meaningful impact
- **P2** — real but not urgent
- **P3** — parked / context-bearing / decision-required
- **P-dec** — needs operator decision, not researchable

---

## Cross-references

- `docs/decisions-log.md` — ADRs (latest: ADR-037 Bot E un-archive, 2026-04-22)
- `docs/open-questions.md` — open OQs with owner + unlock condition
- `docs/session-2026-04-17-edges-review.md` — 9-method edges analysis (canonical)
- `research/grok-methods-dump.md` — 11 trading methods, with crowding/edge notes
- `research/grok-winning-bots-dump.md` — wallet archetypes
- `docs/bot-f-ideas.md` — 5 Bot F strategy ideas
- `docs/oraclemangle-ensemble-proposal.md` — ensemble relocation proposal
- `docs/bot-b-scorer-rebuild-plan.md` — E1/E2/E3/E4 estimator plan

---

## Part 1 — Active per-bot monitoring (passive, check before doing new work)

| ID | Task | Priority | Notes |
|---|---|---|---|
| M1 | Bot G first-fill watch after `MAX_ENTRY_PRICE=0.05` relax | P1 | Deadline: 2026-04-23. If 0 fills in 24h, K2.6's 20% edge-survival estimate likely correct — shelve or relax further. |
| M2 | Bot F paper mirror first-fill watch | P1 | 4 validated sharps, $5/trade, 60s poll. First fills validate execution latency vs observed price. 2-week gate per ADR-037. |
| M3 | Bot E first-fills under new filters (min-entry 0.40, max-shares 15) | P1 | Validates the ADR-037 tuning on forward data. |
| M4 | Bot B calibration preset C rerun at 200 samples | P1 | Script fixed today (preset C, `--max-tokens 4000`, `--no-think`). Produces Brier + ECE for unhalt gate. |
| M5 | Bot D orphan-SELL reconciliation bug | P2 | 8 `portfolio.realised.orphan_sell` warnings still firing. Logged 2026-04-19, unresolved. |
| M6 | Bot C Pyth Crypto Base feed test (1 week) | P1 | Switched 2026-04-22 from Pyth Pro → Crypto Base (free). Verify `pyth_bars_pro`/`hermes` still populate, check update frequency matches 1s SLA, no API-shape breakage. Fallback: Hermes if Base fails. |

---

## Part 2 — Bot B (blocks unhalt)

Halted since Session 17r pending Phase 2 E2 estimator + ECE validation.
Scaffold shipped (`bots/bot_b/scorer_ensemble/` + 30 tests).

| ID | Task | Priority | Effort | Notes |
|---|---|---|---|---|
| B1 | **E2 — oraclemangle as Estimator** (wrap existing HTTP scorer in Estimator interface) | P1 | ~1 day | Unlocks ensemble. Gated on B3 decision. |
| B2 | **E3 — LocalSentimentEstimator** (local-qwen35 via the local workstation SSH) | P2 | 2-3 days | Independence from E2 TBD; only meaningful after E2 lands. |
| B3 | **Ensemble relocation decision** — move `bots/bot_b/scorer_ensemble/` to `the external scorer project (closed; see https://oraclemangle.com)`? | P-dec | — | `docs/oraclemangle-ensemble-proposal.md`. Blocks writing E2/E3 in the wrong place. |
| B4 | **E4 — WalletFlowEstimator** (reads Bot F Mirror aggregates as probability prior) | P1 | ~1 day | Now feasible — `mirror_signals` has 66k rows. |
| B5 | **Category-level dispute-rate shrinkage** (OQ-040) — populate empty `CATEGORY_DISPUTE_RATES` dict from external scorer's calibration data (closed) | P1 | ~2h | Cheapest real unlock. Sizer already accepts `category` arg; table empty. |
| B6 | **Calibration DEFAULT_PRESET swap** `b` → `c` after M4 confirms Brier ≤ 0.06 on 200 samples | P2 | 15 min | Follows from M4. |

**Unhalt gate:** B1 + B5 + B4 + M4 Brier ≤ 0.06 + ECE validation. 3-4 weeks of work.

---

## Part 3 — Bot F graduation (ADR-037 Steps 2 & 3)

| ID | Task | Priority | Gate | Notes |
|---|---|---|---|---|
| F1 | **Step 2 — ADR reversal to paper+live** (curated sharps) | P-dec | 2 weeks paper data, ≥25 fills, WR ≥55% on our own fills | Waiting on M2. |
| F2 | **Step 3 — full fleet graduation** | P-dec | Step 2 positive | Waiting on F1. |
| F3 | **Per-category wallet P&L refinement** — extend `scripts/bot_f_wallet_pnl.py` to group trades by market category per wallet | P1 | ~2h | Filters sharps list further. Data already local. |
| F4 | **Bot F Hunter N-threshold binding** (OQ-033) — N advisory, not authoritative, on top-N rankings | P2 | — | Small scoping fix. |
| F5 | **Co-movement analysis** — do the 4 sharps overlap on markets? Clustered signal ≠ 4 independent signals. | P2 | — | Affects sizing math. |
| F6 | **`crowd_signals` export wiring** — already scaffolded per `bots/bot_f/crowd_signals.py`; wire to Bot B E4 + Bot A/D filter consumers | P2 | — | Matches B4. |

---

## Part 4 — Bot E tuning (un-archived 2026-04-22 per ADR-037)

| ID | Task | Priority | Effort | Notes |
|---|---|---|---|---|
| E1 | **Backtest validation of today's ADR-037 tuning** (max-shares 15, min-entry 0.40) against recorder DB | P1 | ~2h | Verify the drill-down-derived guards improve historical ROI. |
| E2 | **T1.2** 75¢ profit-target exit for Bot E | P2 | 30 min | Partial exit at $0.75 to lock gains. |
| E3 | **T1.3** "Smart money 30–90s post-open" entry window test | P2 | 1h | Potential timing edge. |
| E4 | **T3.1** 5-min market mode | P3 | TBD | Deferred 4 weeks per ADR-022 paper gate. |
| E5 | **T3.3** Stop-loss exit at 35¢ | P3 | 15 min | Only meaningful alongside E2. |
| E6 | **T6.5** Document "live filter chain IS the edge" — naive OBI loses $188 in backtest, live filter chain nets positive | P3 | 30 min | Preserve in Bot E CLAUDE.md. |
| E7 | **Recorder DB deep-mine** — queue imbalance feature, signed CEX CVD, event study on the 7% longshot-fade wins | P2 | 1-2 days | 462MB tick data not fully leveraged. |

---

## Part 5 — Infrastructure / fleet

| ID | Task | Priority | Effort | Notes |
|---|---|---|---|---|
| I1 | **T4.1** Recorder silent-stall root cause | P0 | 3-4h uncertain | 9 overnight restarts; heartbeat fix deployed (17p) but root cause not found. **Fleet-wide operational risk.** |
| I2 | **T6.4** `model_call.py` → prefer `localhost:11434/api/chat` over OpenAI-compat endpoint | P1 | 30 min | Blocked Bot B calibration today; fixed with `--max-tokens`+`--no-think` but the cleaner fix is the endpoint. |
| I3 | **snapshot_daily daemon gap** — Bot E snapshot showed $0 realised today because nothing was firing `portfolio.snapshot_daily` for bot_e. New finding 2026-04-22. | P1 | 1h | Add cron or dedicated service to snapshot all bots daily. |
| I4 | **T4.3** Cross-bot P&L attribution on dashboard | P2 | 1-2h | Dashboard has partial per-bot data. |
| I5 | **T4.5** Wire `reconcile_paper_resolutions.py` into `bot_a_shadow` / `bot_b_shadow` | P2 | 30 min | Currently only bot_d / bot_e call it. |
| I6 | **T4.4** Recorder per-WSS instrumentation | P2 | pairs with I1 | Prerequisite for I1 root cause. |
| I7 | **T6.2** Fix Bot D 3 orphan positions (empty cid) | P2 | 30 min | Accounting cleanliness. |
| I8 | **V2 migration integration verification** — `core/clob_v2.py` + wrap/unwrap + liquidator merged to main 2026-04-22; needs end-to-end dry-run against a test wallet | P1 | 2-3h | No live path should use V2 until this passes. |

---

## Part 6 — New bots / strategy research

| ID | Task | Priority | Effort | Notes |
|---|---|---|---|---|
| S1 | **Bot H — Sharp-line lag** (Betfair Exchange vs Polymarket sports) | P2 | 2-3 wk | Real edge per edges-review Method 3.2. UK operator has licensed Betfair access. Park until Bot B ensemble lands. |
| S2 | **Negative-Risk multi-outcome arbitrage scan** | P3 | 1 day data-only | Method 1.1. Binary arb dead; NegRisk multi-outcome may have residual windows. Measurement only. |
| S3 | **T6.1 Bot I — "price-ceiling directional"** (K2.6's alternative: direction-matching side at t-60s, best_ask ≤ 0.78) | P3 | ~3h scoping | Plausible mid-single-digit ROI per K2.6. No backtest yet. |
| S4 | **Reward-cascade measurement** (OQ-039) — passive 14-day log of cancellation cascades + forward mid moves | P2 | 14 days passive + 1h script | `contrarian_edges.md` Method 2. Cheap. No trading. |
| S5 | **TA-herding fade reversion check** (OQ-038) | P3 | 1h | Data-only. Folded into Bot E POC originally. Re-verify negative result. |
| S6 | **TimesFM revival decision** — parked on Bot C which is being archived. Redeploy for 5-min crypto (Bot E-adjacent) or formally kill. | P-dec | — | `~/.claude/projects/-Users-operator-Code-next-build/memory/polymarket_bot_timesfm.md`. |
| S7 | **Long-tail sniping** (Grok Method 6) — thin pop-culture markets, 31k-position wallet example (+$117k from $300 seed) | P3 | 1 day scoping | Category-selection heuristic never built. |
| S8 | **Rebate-farming hybrid** (Grok Method 3) — V2 pays 20-25% maker rebates. Not standalone; as a subsidy layer to Bot G / Bot H. | P3 | — | Rejected standalone; revisit as subsidy. |
| S9 | **OQ-072 urgent 5m/15m crypto validation rerun** | P0 | 2-4h | 72h copied-recorder report now points to probability-gap and Brownian fair-value as paper-only candidates. Spin-off brief: `docs/crypto-fair-value-paper-bots-spin-off-2026-05-06.md`. Next: implement the two paper lanes, add settlement/Chainlink labels where possible, and calibrate fills. No live changes. |

---

## Part 7 — Data assets under-mined

| ID | Dataset | Next use | Notes |
|---|---|---|---|
| D1 | `data/scorer_calibration.db` (91,883 resolved UMA markets) | B5 | Category-level data not yet extracted. |
| D2 | `bot_f.db::mirror_signals` (66k rows, 45 wallets) | F3 / F5 | Today's per-wallet retrospective done; per-category / time-of-day / co-movement not yet. |
| D3 | `data/bot_e_recorder.db` (462 MB ticks) | E7 | Used for POC + longshot backtest; deeper feature mining pending. |
| D4 | `data/backtest.db` (526 MB) | P3 triage | Audit: valuable cache or stale junk? |
| D5 | Bot A phantom-fill + fee-adjusted backtest tooling | Reference for S1 | Archived Bot A — datasets and scripts still useful. |

---

## Part 8 — Open questions (Claude-researchable)

Summarised from `docs/open-questions.md`. Cross-referenced to priority IDs.

| OQ | Subject | Maps to | Priority |
|---|---|---|---|
| OQ-072 | Urgent 5m/15m crypto strategy validation on full recorder tape | S9 | P0 |
| OQ-040 | Category-level historical UMA dispute rates | B5 | P1 |
| OQ-039 | Reward-cascade 14-day passive measurement | S4 | P2 |
| OQ-033 | Bot F Hunter N-threshold binding | F4 | P2 |
| OQ-038 | TA-herding fade reversion | S5 | P3 |
| OQ-031 | `price_collector.py` schema flaw | — | P3 (moot if Bot C archived) |
| OQ-030 | Reconcile Bot A's missing BUY legs | — | P3 (archived bot) |
| OQ-029 | condition_id ID-space mismatch across bots | — | P3 |
| OQ-028 | Widen main ingest to weather markets | — | P3 |
| OQ-011 | WebSocket connection limits | — | P3 |

---

## Part 9 — Operator decisions pending (P-dec)

| ID | Question | Notes |
|---|---|---|
| OD1 | Bot C — Pyth Pro expired 2026-04-22; operator switched to **Pyth Crypto Base (free)**. Decision: continue on Base vs migrate to Hermes? | **Operator direction 2026-04-22: test Pyth Crypto Base first (1s updates, 99.99% SLA, free). Hermes migration only if Base fails to meet Bot C's thesis needs.** |
| OD2 | TimesFM revival — kill or reattach to a different bot? | **Decide later** (operator 2026-04-22). `memory/polymarket_bot_timesfm.md` has the plan. Was pegged to Bot C live data. |
| OD3 | Oraclemangle ensemble relocation (B3) | **Decide later** (operator 2026-04-22). Affects 3 weeks of E2/E3/E4 work location. |
| OD4 | Bot A code deletion vs retention | **Operator unsure 2026-04-22 — park pending forward use case.** Tests reference `bots/bot_a/` so deletion requires test cleanup too. |
| OD5 | Sports lag bot (S1 Bot H) — build plan or defer? | Assumes Betfair API access path; operator has licensed access. |

---

## Explicitly NOT on the backlog (rejected — see ADRs)

- Market-making / rebate farming standalone (ADR-020)
- Cross-venue arb Polymarket ↔ Kalshi (ADR-020)
- Delta-neutral crypto vol split (ADR-030 POC kill)
- Pure sentiment / news-latency
- Porting to another venue
- Mobile / webapp frontend
- Postgres migration (deferred until fleet grows)
- Hardware wallet signing path
- Weather directional standalone (now = Bot D)
- 5-min BTC scalping as new bot (now = Bot E retained infra)

---

## Recommended priority for next session

**If only 1 hour available:**
- **B5** (category dispute-rate shrinkage). Real unlock, existing data, no production risk, Bot B halted so safe.

**If 1 day available:**
- **B5** + **F3** (per-category wallet P&L refinement) + **check M1/M2/M3** forward results.
- Refines Bot F sharps list and completes today's tuning verification.

**If 1 week available:**
- **B5 + F3** then **B1** (E2 oraclemangle estimator, requires OD3 decision) then **I1** (recorder stability — operational risk).

**Strategic milestones:**
- **Bot B unhalt gate:** B1 + B5 + B4 + M4 (3-4 weeks).
- **Bot F graduation gate:** F1 (requires 2 weeks paper data from today).
- **Bot H sports-lag scoping:** after Bot B unhalts.
