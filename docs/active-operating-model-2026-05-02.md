# Active Operating Model

**Date:** 2026-05-26
**Status:** Current active fleet model.
**Decision source:** ADR-071, ADR-072, ADR-078, ADR-084, ADR-085, ADR-087, ADR-088, ADR-089, ADR-090, ADR-091, ADR-092, ADR-093, ADR-096, ADR-097, ADR-098, ADR-123, ADR-125, ADR-127, ADR-128, ADR-133, ADR-134, ADR-135, ADR-136, ADR-139, ADR-142, ADR-143, ADR-147, ADR-148, ADR-149, ADR-160, ADR-161, ADR-162, ADR-163, ADR-164, ADR-165, ADR-166, ADR-167, ADR-168, ADR-169, ADR-170, ADR-171, ADR-172, ADR-173, ADR-174, ADR-176, ADR-179, ADR-180, ADR-181, ADR-182, ADR-183, ADR-186, and ADR-187 in `docs/decisions-log.md`.
**Code source:** `core/bot_registry.py`.
**2026-05-19 live halt note:** ADR-183 stops and disables all live services on
the bot container and the VPS. Paper traders and recorders remain active for data
collection. Any live restart needs a new explicit the operator approval and ADR.

## Active Fleet

| Name | Bot ID | Status | Current role |
|---|---|---|---|
| Longshot Prime Live | `bot_g_prime_live` | Paused live probe | Stopped/disabled by ADR-183 on 2026-05-19. Previous ADR-149 settings were `6.5c-8c`, 45s, ETH/SOL only, `$1` fixed entries. No restart without a new ADR. |
| Longshot Prime Shadow | `bot_g_prime` | Paper operational | Keep collecting `4c-8c`; judge mainly `4c-5c`, do not mix live rows into this ledger. |
| Weather Fade | `bot_d` | Paper operational | First weather wallet candidate if daily-only, station-exact edge clears depth and trimmed ROI. |
| Weather Fade Live Probe | `bot_d_live_probe` | Paused live probe | Stopped/disabled by ADR-183 on 2026-05-19. Residual exposure remains accounting-visible. No restart without OQ-123/OQ-124 review and a new ADR. |
| Weather Maker Live Probe | `bot_d_maker_live_probe` | Paused live probe | Stopped/disabled by ADR-183 on 2026-05-19. Residual exposure remains accounting-visible. No restart without OQ-123/OQ-124 review and a new ADR. |
| Weather Spike Live Probe | `bot_d_spike` | Paused live probe | VPS live-probe service stopped/disabled by ADR-183 on 2026-05-19. Paper `bot_d_spike_short` remains active. |
| Weather Station Lock Live Probe | `bot_d_station_lock` | Paused live probe | the bot container live-probe service stopped/disabled by ADR-183 on 2026-05-19. Scaling remains blocked by OQ-112 and restart now also requires a new ADR. |
| BTC Complete-Set Live Probe | `bot_l_complete_set` | Paused live probe | VPS live-probe service/timer stopped/disabled by ADR-183 on 2026-05-19. Paper timer remains active for data collection. |
| Weather Source Shadow | `bot_d_source_shadow` | Paper tuning | Promoted 2026-05-09 by ADR-142. Separate paper-only Bot D lane using live-shaped weather settings under its own `bot_id` for source/tier/city proof. |
| Weather Ensemble Ladder | `bot_d_ensemble_ladder` | Paper tuning | Added 2026-05-16 by ADR-179. Paper-only adjacent YES-bucket basket lane using station-exact ICON/GFS/ECMWF deterministic forecasts, 18-30h entry window, and event-level ladder filters. Writes Event rows only; no CLOB client, orders, fills, or positions. |
| Persistence Live | `bot_i_persistence_live` | Paused live probe | Stopped and disabled on the bot container by ADR-181. Its separate `persistence_live.db` ledger misclassified redeemed winners, so it cannot restart until OQ-123 fixes wallet-level ownership and Bot I accounting. |

## Shared Data Infrastructure

| Name | Bot ID | Status | Current role |
|---|---|---|---|
| Crypto Recorder | `bot_e` / recorder | Retired Bot E trading strategy; shared crypto data infrastructure | ADR-092 retires active Bot E trading/tuning. ADR-096 reframes the old Bot E0 recorder as shared crypto telemetry for Bot G replay/parameter research. ADR-122 keeps recorder tape, bounded replay, outcome labels, and offline features running indefinitely as reusable infrastructure, subject to storage/health monitoring. No Bot E live graduation path remains open without a new ADR. |
| Bot G live-mirror paper shadow | `bot_g_prime_shadow` | Archived | Stopped/disabled by ADR-187 after the 2026-05-26 audit. Historical rows remain for comparison; do not restart without a new thesis and ADR. |
| Bot G high-tail paper shadow | `bot_g_prime_high_tail` | Archived | Stopped/disabled by ADR-187 after the 2026-05-26 audit found the high-tail paper and maker-shadow family below live-candidate quality. Historical rows remain for audit only. |
| Bot D-Spike-Short | `bot_d_spike_short` | Archived | Stopped/disabled by ADR-187 after negative paper evidence and no live-transfer case. Historical rows remain for audit only. |
| Bot F same-side momentum | `bot_f_momentum_paper` | Archived | Stopped/disabled by ADR-187 after the 2026-05-26 audit confirmed 0 entries after a large run sample. |
| Bot H Maker V2 Recorder | `bot_h_maker_v2` | Read-only recorder | ADR-134 Phase 1 wide CLOB recorder only. Captures politics/sports/awards/crypto 1c-50c data into `data/maker_recorder.db`. No quote engine, no paper fills, no order placement. Phase 2 requires OQ-100 and a separate approval/ADR. |
| Bot H Maker V2 Quote Paper | `bot_h_maker_v2_quote_paper` | Paper research lane | ADR-143 early paper quote simulator on the ADR-134 target cells. Writes paper quote/fill tables into `data/maker_recorder.db`, uses only recorder prints, and does not place CLOB orders. OQ-100 remains binding before any live or feature claim. |
| Wallet-Tag Feature Shadow | `wallet_tag_feature_shadow` | Paper research lane | ADR-143 paper ledger over low-bot-score wallet BUY rows from `data/wallet_tag_forward.db`. This is feature evidence only, not copy-trading. OQ-099 remains binding before any bot feature plumbing. |
| Wallet-Tag Elite Cap Paper | `wallet_tag_elite_cap_paper` | Paper research lane | ADR-186 capped paper-only lane over the four recent profitable wallet suffixes from the 2026-05-26 audit. Uses `$1` max entry cost, `$15` open exposure cap, one entry per wallet/market, a separate ledger, and no CLOB client or order placement. |
| WC negRisk Basket Paper | `wc_negrisk_basket_paper` | Archived | Stopped/disabled by ADR-187 after the lane was judged fee-gated/illiquid at solo-operator scale. |
| Persistence Paper | `bot_i_persistence` | Paper research lane | Daily the bot container paper/replay lane for the two persistence cells. Current first gate is `50` entries per cell, then outlier, fee, and negative-control review. |
| Cell C Maker Shadow | `bot_i_cell_c_maker` | Paper research lane | Maker-conversion S7 shadow for BTC/ETH/SOL 5m+15m 95-99c high-side persistence. ADR-176 records the 2026-05-16 borderline `69/69/69`, `-0.90%` ROI result but blocks the `$1/trade` live probe on exchange 5-share minimum mechanics until OQ-118 is resolved. |
| Pyth/Hermes market-data lane | `bot_c` / data | Retired trading strategy; research infrastructure | ADR-093 retires Bot C active trading. Keep Pyth/Hermes bars, feed registry, parser, GBM/probability math, and historical decisions as read-only research and shared modeling inputs. |

## Parked Productization Track

| Name | Bot ID | Status | Current role |
|---|---|---|---|
| Oraclemangle Kelly | `bot_b` / `bot_b_shadow` | Parked / maintained | Hidden from active dashboard and reboot-readiness surfaces; candidate for future public Bot B spin-off after redaction. |

## Archived Active Surfaces

| Legacy name | Bot ID | Archive rule |
|---|---|---|
| Longshot Fade | `bot_a`, `bot_a_shadow` | Code and historical docs stay in archive/spec form. No active dashboard tab or active fleet tile. |
| Pyth Directional | `bot_c` | Active/paper trading surface archived by ADR-093. No active dashboard tab, reboot-readiness requirement, or enabled paper service. Pyth/Hermes data and modeling pieces stay available as shared research infrastructure. |
| Whale Mirror / Whale Sensor | `bot_f_mirror`, `bot_f_paper_mirror`, `bot_f` | Standalone bot identity is archived. Crowd, cascade, and mirror-signal data stay as shared sensor infrastructure. |
| Crypto FV paper lanes | `crypto_probability_gap_paper`, `crypto_brownian_fv_paper` | Original taker-like paper strategy surfaces archived by ADR-139 after forward paper failed OQ-078 robustness gates. Maker paper shadows continue as research controls; the two FV live-maker probes are paused by ADR-181 after live drawdown and accounting gaps. |
| Bot G late-cheap paper | `bot_g_prime_late_cheap` | Paper-only late-cheap probe (`1c-3c`, `30s`, BTC/ETH/SOL) archived 2026-05-09 by ADR-140 after `152` closed / `1` win / `-86.4%` ROI; ADR-128 -100% rolling-ROI floor violated; thesis falsified. Service stopped and disabled on VPS; ledger rows preserved for audit. |
| Bot G take-profit paper | `bot_g_prime_take_profit` | Paper-only synthetic 50c take-profit probe (`3.5c-5.5c`, BTC/ETH/SOL) archived 2026-05-09 by ADR-140 after `65` closed / `1` win / `-67.5%` ROI; replay shows `0/26` positions ever hit the 50c threshold; thesis decisively falsified. Service stopped and disabled on VPS; ledger rows preserved for audit. |

## Live-Money Discipline

- Current live posture after ADR-181: only Bot D live lanes remain active on
  the bot container. Bot I live, crypto FV probability-gap live maker, and crypto FV
  Brownian live maker are stopped/disabled and must not restart until OQ-123 is
  resolved (dry-run backfill + dashboard truth surface delivered 2026-05-18, gated deploy + report review + new ADR still required).
- Longshot Prime live is active only as the ADR-149 `$1` high-tail
  data-gathering micro-probe. ADR-135/ADR-149 block scaling, promotion, or a
  band/symbol change without a new ADR.
- Longshot Prime live previously ran the ADR-136 `3.5c-5.5c` `$1` probe.
  ADR-149 supersedes only that live parameter set; it does not assert durable
  Bot G edge.
- ADR-149 keeps the Bot G Prime Live fresh-clock guard at `5s` while using a
  `45s` entry window and `2s` scan.
- The broader `4c-8c` Longshot Prime range stays open for data collection because the operator chose more sample, but only `4c-5c` has the strongest positive evidence so far.
- ADR-098 adds two Bot G paper-only research lanes for parameter learning; do
  not interpret them as live authorization.
- Weather Fade paper remains operational in parallel with the active
  `bot_d_live_probe` tiny-live unit.
- Weather Fade live probe exists to measure fill transfer, slippage,
  reconciliation, and exit handling at minimum practical size; it is not a
  declaration that Bot D has cleared full ROI-live-readiness.
- Weather Maker Live Probe exists to measure whether maker quotes improve fill
  economics and trade count versus Bot D's taker lane. It has separate ledger,
  caps, watchdog routing, and OQ-116; it is not a broad Bot D scale approval.
- `bot_d_live_probe` has enough transfer proof for selective quality-slice
  sizing proposals, but OQ-067 still blocks broad scaling, durable edge
  claims, or any runtime cap change without a new ADR and explicit the operator
  approval.
- Bot D-Spike is active as the ADR-172 tiny live probe on the VPS. Its hit
  rate is diagnostic versus the `3.6%` historical baseline; `90` days /
  `200` closes now block scaling and durable edge claims, not the already
  capped tiny live-probe packet.
- ADR-091 slightly loosens only the Bot D live NWS veto floor to `3.0F` and
  adds shadow counters; Bot D live size/caps stay unchanged.
- ADR-092 retires Bot E as an active trading strategy. ADR-096 keeps the old
  Bot E recorder path as the shared Crypto Recorder for Bot G research, but
  Bot E should not receive threshold, model, execution, sizing, or
  live-posture tuning without a new ADR.
- ADR-122 keeps recorders and data-only lanes running indefinitely as research
  infrastructure, subject to storage, backup, and health monitoring. Recorder
  continuity is not trading authorization.
- ADR-093 retires Bot C as an active trading strategy. Bot C should not
  receive parser, endpoint, threshold, sizing, execution, or live-posture
  investment unless a new ADR presents fresh walk-forward evidence that clears
  the reversal gate.
- Any live wallet setting change, bankroll change, or real-money order requires explicit operator approval.
- ADR-163 adopts a faster tiny-live probe doctrine: incomplete paper evidence
  may no longer block a tightly capped live-probe packet, but fund-safety,
  wallet/key handling, caps, watchdogs, reconciliation, rollback, and explicit
  the operator approval remain mandatory.
- ADR-168 makes mounted storage the canonical home for bulky the bot container live DBs,
  backups, and snapshots; root disk should stay code/config/runtime-only.
- ADR-170 lowers old paper sample gates only for tiny live-probe proposals;
  scale, durable edge claims, and any real-money runtime change still require
  explicit approval.
- ADR-171 makes external DB symlink targets part of the bot container unit sandboxing and
  treats accidental `data/data/external` DB forks as storage-health faults.
- ADR-172 activates the approved D-Spike and Station Lock live-probe runtimes
  and deploys a Bot L live-probe timer that refuses orders below the exchange
  minimum-share rule.
- ADR-173 raises Bot L's live-probe bundle cap to `$5`, keeps daily gross at
  `$10`, and preserves the BUY-only scope so the timer can satisfy the
  exchange minimum without widening fund-safety exposure.
- ADR-174 adds the separate Bot D maker live probe under a `$200` wallet
  posture, `$10` max order, `$100` daily gross, and `$100` open exposure.
- ADR-180 adds automatic residual USDC.e -> pUSD wrapping as wallet
  maintenance only; it is not a strategy edge and does not solve over-allocation.
- ADR-181 pauses all non-Bot-D live probes that recently created accounting or
  ROI concern: Bot I Persistence Live and both crypto FV live makers.

## Current Risk Levels

| Level | Lanes | Current rule |
|---|---|---|
| R0 — data only | Recorders, wallet observers, archived research assets | Keep running if healthy; no order paths. |
| R1 — paper/replay | Bot G maker shadows, Bot I maker shadows, Bot H quote paper, Bot F momentum, FV maker paper shadows, Bot D Ensemble Ladder | Evidence collection only; no live promotion without an ADR and ROI gates. |
| R2 — tiny live, allowed | Bot D live probe, Bot D maker live probe, Bot D station-lock live probe | Keep active at current caps; scaling requires OQ evidence, dashboard truth, and a new ADR. |
| R3 — paused live, no restart | Bot I Persistence Live, crypto probability-gap live maker, crypto Brownian FV live maker | Stopped/disabled. Restart is blocked by ADR-181 and OQ-123. |
| R4 — prohibited without new explicit approval | Ledger treasury, wallet transfers beyond approved pUSD wrapping, any new live service, any cap lift | Stop and ask the operator before action. |

## Dashboard Rule

The operator dashboard shows active fleet tabs plus explicitly approved
read-only recorder/sensor tabs:

- Overview
- Longshot Prime Live (G)
- Longshot Prime Shadow (G)
- Weather Fade (D)
- Weather Fade Live Probe (D)
- Maker Recorder (H)
- Wallet Observer
- Orders and Positions
- Events and Health

Parked Bot B, retired Bot C/E trading rows, and archived Bot A/F rows can
remain in the database for audit and tests, but aggregate dashboard queries
should filter them out by default.
