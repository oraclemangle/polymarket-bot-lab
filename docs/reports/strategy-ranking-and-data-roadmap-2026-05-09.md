# Strategy Ranking and Data Roadmap

**Date:** 2026-05-09
**Status:** Current numbers-first resource allocation verdict after Sessions 283-296.
**Scope:** Active bots, paper lanes, recorders, datasets, archived strategy reports,
wallet-tag/copy-trade edges, maker-flow reports, Bot F crowd-flow reports, WC/neg-risk
monitoring, and current ADR/OQ gates.
**Runtime:** Read-only report update. No service touched, no order placed, no wallet,
cap, band, city, threshold, or strategy parameter changed.

## Resource Verdict

Spend the next resources in this order:

1. **Bot D live probe evidence loop.** Current realised live result is `31` closed
   groups / `23` wins / `+$12.73`; first source/tier split is positive in B-tier
   and NOAA/multi-model, but the sample is still small. The fastest profitable
   answer is another `20-30` closed live groups plus source/tier/outlier review.
2. **Persistence Paper (I).** Already paper-active and close to its first cell
   gate: `69` entries / `59` wins / `+15.85%` post-fee ROI, Cell A `32/50`,
   Cell B `37/50`. Do not promote beyond paper until outlier, fee/slippage, and
   negative-control checks clear after the first gate.
3. **Bot F same-side momentum paper.** Historical 1800s PASS cells are now
   promoted to a BUY-only paper ledger. It needs executable forward proof:
   `100` closed entries, positive post-fee ROI, and ex-largest-two positive.
4. **Wallet-tag forward gate.** The P0 settlement fix is deployed. Current forward
   report is still `INSUFFICIENT`: `104` proxy-settled trades, hit `46.2%` vs implied
   `49.4%`, edge `-3.3pp`, 95% CI ROI `(-63.2%, +1.5%)`. Keep it running to
   `2026-05-15`; do not build a wallet feature unless the gate flips positive.
5. **Bot H Maker V2 recorder.** Do not use `1M pm_events` alone. Phase 2 waits for
   `100` replayable trips and replay robustness. The recorder is healthy; the quote
   engine is not authorised.

Everything else is either watch-only, label-blocked, or dead.

## Master Strategy Ranking Table

Evidence grades: `A` = live or forward settled data with robust checks; `B` = useful
forward/live sample but still underpowered; `C` = promising data but blocked by joins,
fillability, or sample; `D` = contradicted by robustness; `F` = dead/archived.

| Rank | Strategy / edge | Lane / report | Current P&L | Projected P&L / ROI | Sample size | Evidence | Time to decisive proof | Time to live / scale | Blocker | Data modification needed | Next action | Final decision |
|---:|---|---|---:|---|---:|---|---|---|---|---|---|---|
| 1 | Weather Fade range-fade | `bot_d_live_probe` | `+$12.73` realised live; `31` closed / `23` wins; earlier ex-top-two ROI `+7.44%` | No scale projection yet | `31` closed groups, `6` open, `87` source labels | B | `20-30` more closes, likely `3-10d` | Already live tiny; scale only after `50-60` closed + source split | Small sample; source-lag still null; sub-$1 CLOB rejects | Add min-notional guard; continue source-resolution labels; add final-source lag poller | Keep `5` shares, rerun source/tier/outlier report at `50-60` closed | `push_evidence_now` |
| 2 | Persistence Paper (I) | `bot_i_persistence` | `+$8.05` after fees; `69` entries / `59` wins / `+15.85%` ROI | No scale projection; first gate not complete | Cell A `32/50`, Cell B `37/50` | B/C | First cell gate likely `1-2wk` at daily cadence | Paper already active; live prohibited | Cell B ROI is friction-sensitive; needs ex-largest/ex-largest-two and negative controls | Canonical repo unit added; keep daily run | Let run to `50/cell`, then robustness review | `paper_promoted_existing` |
| 3 | Bot F same-side crowd momentum | `bot_f_momentum_paper` / OQ-059 | New forward paper ledger; no closed forward sample yet | Historical edge per trade only: `+4.16c` to `+10.92c` in 1800s PASS cells | Historical PASS cells `n=117-380`; `42` market-days | C | `100` closed paper entries, likely `2-3wk` | Paper-only; live prohibited | Fillability, BUY-only executable subset, spread/queue, public-print mark quality | Added 5-min BUY-only paper ledger | Run unchanged to first `100` closes | `paper_promoted` |
| 4 | PolyVerify low-bot-score wallet tag | OQ-099 / ADR-137 forward gate | Research only; current forward edge `-3.3pp` | Not projection-ready; historical `+10.7pp` is not live forecast | `104` proxy-settled scored trades; `123` BUY rows joinable; `39` proxy-settled markets | C | First gate date `2026-05-15`; needs `>=200` settled/scored BUYs | Live prohibited; feature input only after ADR | Forward sample still insufficient and currently negative | the bot container proxy-settlement fix deployed; VPS join draft needs review before deploy | Let timers run; review report on `2026-05-15`; do not plumb into bots yet | `gate_only` |
| 5 | Maker-flow top cells | `bot_h_maker_v2` / OQ-100 | n/a recorder only | Not projection-ready; historical maker sim not enough for build | `191k+` pm_events at last audit, `98.6%` condition_id-filled, `0` resolved then | C | Wait for `100` replayable trips, not raw `1M` events | Paper Phase 2 only after OQ-100 + the operator approval | Need replayable settled trips and AS proxy validation | None now; resolution timer/daily replay already built | Keep recorder; run replay when `100` trips exist | `keep_recorder` |
| 6 | Weather Fade paper / EMOS path | `bot_d` paper + OQ-093/OQ-096 | Raw positive all-time, but ex-largest-one `-21.77%`, ex-largest-two `-30.28%`; earlier raw `+$686.11` becomes `-$1,255.05` ex-top-two | No projection; raw P&L is outlier-dominated | `75-80` closed/matched weather groups; `87` labels | D | After forecast payload fix + EMOS/NGR benchmark | Live scale blocked; live probe already separate | Paper sizing not live-shaped; payload schema missing fields | Fix OQ-096 forecast-entry payload and source-lag fields | Keep as shadow; do not cite paper P&L for scaling | `modify_dataset` |
| 7 | Bot G Prime live | `bot_g_prime_live` / ADR-136 | `-$82.84`, `51` closed / `1` win, `-80.6%` ROI; ex-largest `-$101.98`; `35%` EXCHANGE_CLOSED miss rate | No projection; no scale path | `51` live closed | D/F | Already decisive for no-scale | Already live `$1`; scale blocked | BTC/ETH all -100%; one SOL NO win props ledger | None | the operator decides keep `$1` data probe or halt | `watch_or_halt_no_scale` |
| 8 | Bot G Prime paper 4-8c | `bot_g_prime` | `+$327.42`, `143` closed / `13` wins; ex-largest-two `+$87.42` | Not live-projectable; jackpot-shaped | `143` closed | D | Already shows regime-monitor value only | Live prohibited by live/shadow failure | Positive headline concentrated in 6.5c-8c; live band fails | None | Keep hidden paper monitor | `watch_only` |
| 9 | Bot D-Spike Strategy E | `bot_d_spike` | `-$10.00` realised on `5` closed; `0` wins; `7` open | Not projection-ready | `5/200` closes | C/D | `200` closes or `90d` | Live prohibited until OQ-086 + ADR | Sample tiny; high-variance longshot YES | None | Continue unchanged paper-only | `watch_only` |
| 10 | Bot D-Spike-Short Strategy E2 | `bot_d_spike_short` | `-$8.00` realised on `4` closed; `0` wins; `2` open | Not projection-ready | `4/200` closes | C/D | `200` closes or `90d` | Live prohibited until OQ-097 + ADR | Sample tiny; lane just started | None | Continue unchanged paper-only | `watch_only` |
| 11 | Non-whale 5m/15m copy-trade | OQ-101 report | n/a; `0` settled local crypto copy trades | No projection; settlement/book joins fail | Cohort C `730` trades / `7` wallets, `0` settled, `0` book overlap | D | Already answered | Live/build prohibited | 100% settlement and book-join loss locally; production wallet-tag forward leaning negative | None until wallet-tag gate passes | Do not build copy-trade bot | `no_build` |
| 12 | WC 2026 / negRisk observation | WC + negRisk reports | n/a monitor | No P&L projection; Group A ask-sum `0.999` raw arb is fee-gated | `12` WC group baskets; `1,983` negRisk events in scanner | C | Tournament window `2026-06-11` to `2026-07-19` | No bot authorised | Observation only; fee/slippage kills raw arb | Optional timer deployment only | Optional 5-min monitor during tournament | `keep_observer_optional` |
| 13 | Crypto FV Probability Gap | ADR-139 archive report | `-$104.00`, `144` closed, `-14.4%`; ex-largest `-17.1%`, ex-largest-two `-19.7%` | n/a dead | `145` signals / `144` closed | F | Decisive | Live prohibited | Failed fees, 1c stress, trim | None | Keep recorder data only | `dead` |
| 14 | Crypto FV Brownian | ADR-139 archive report | `-$100.80`, `196` closed, `-10.3%`; ex-largest `-12.5%`, ex-largest-two `-13.9%` | n/a dead | `198` signals / `196` closed | F | Decisive | Live prohibited | Failed fees, 1c stress, trim | None | Keep recorder data only | `dead` |
| 15 | Bot G live mirror | `bot_g_prime_shadow` | `-$161.81`, `74` closed / `2` wins, `-57.4%` ROI | n/a | `74` closed | F | Decisive | Live prohibited | Live-shaped cohort fails | None | Hidden regime monitor only | `watch_only_hidden` |
| 16 | Bot G late-cheap | ADR-140 | `-$560.71`, `152` closed / `1` win, `-86.4%` ROI | n/a | `152` closed | F | Decisive | Live prohibited | Thesis falsified | None | Archived; service stopped/disabled | `dead` |
| 17 | Bot G take-profit | ADR-140 | `-$184.15`, `65` closed / `1` win; TP replay `0/26` hit 50c | n/a | `65` closed | F | Decisive | Live prohibited | Exit threshold unreachable | None | Archived; service stopped/disabled | `dead` |
| 18 | Bot B Oraclemangle Kelly | parked spin-off | `+$63.67`, `48` trades, `1` open; shadow `-$220` | Not projection-ready | tiny stale sample | F | n/a | Live prohibited | Scorer rebuild/spin-off boundary | None now | Keep parked/hidden | `hide` |
| 19 | Bot C Pyth Directional | ADR-093 | `-$1,149.41`, `233` trades | n/a | `233` trades | F | Decisive | Live prohibited | Retired | None | Preserve Pyth/Hermes research assets only | `dead` |
| 20 | Bot A Longshot Fade | ADR-033 | Walk-forward `-$13,613.58`, `12,521` trades, `93.7%` hit rate | n/a | `12,521` walk-forward trades | F | Decisive | Live prohibited | Catastrophic asymmetric tail | None | Hidden permanently | `dead` |
| 21 | Bot F mirror identity | ADR-138 | `-$8` legacy mirror; no active service | n/a | `8` trades | F | Decisive | Live prohibited | Superseded by wallet observer/Bot H | None | Historical data only | `dead` |
| 22 | Bot G raw / jackpot / scalp | archived raw G | `-$205` / `-$350` / `-$267`, all `0` wins | n/a | `100` / `84` / `87` closed | F | Decisive | Live prohibited | Zero-win cohorts | None | Hidden permanently | `dead` |

## Data Roadmap Table

| Priority | Recorder / dataset | Used by | Health | Coverage | Missing labels / joins | Modification needed | Why it matters | Time to benefit | Decision |
|---:|---|---|---|---|---|---|---|---|---|
| P0 | the bot container `wallet_tag_forward.db` | OQ-099 wallet-tag gate | Active 5m observer + 2h resolver; proxy fix deployed | `18,653+` trades, `378` markets, `39` proxy-settled, `104` scored trades in latest report | Strict settlements still `0`; sample below `200` scored trades | No new schema now; monitor timers and compare strict vs proxy labels | Fastest empirical gate for wallet-tag feature; currently negative/insufficient | `2026-05-15` first gate | `run_gate` |
| P0 | Bot D source/entry telemetry | Bot D live scaling, OQ-067/OQ-073/OQ-075/OQ-077 | Active; `87` paper + `87` live forecast-resolution labels after backfill | `44` live forecast-entry conditions in first source/tier split; `31` closed groups | Source-visible lag null; EMOS fields missing; sub-$1 reject noise | Add min-notional guard; add final-source/Wunderground lag poller; fix OQ-096 payload | Decides whether live Bot D can scale beyond 5 shares | `3-10d` for next source/tier review; `1-3` sessions for lag/payload work | `modify_dataset` |
| P1 | VPS `wallet_observer.db` | 245-wallet Polygon CTF observer, secondary wallet gate | Active; latest audit `116,345` fills, `67` wallets, `62` active 24h | Tier A `111,690`, Tier B `4,655`; run 4 captured `25,628` fills | No settlement-resolution join | Review/deploy `scripts/wallet_observer_settlement_join.py` and helper tables | Richer forward wallet evidence if the bot container gate remains underpowered | `2-3d` after review | `join_next` |
| P1 | VPS `maker_recorder.db` | Bot H Maker V2 OQ-100 | Active; `191k+` pm_events, `98.6%` condition_id-filled, fresh heartbeat | 68 markets at audit; politics/sports/awards/crypto scope | Needs resolved/replayable trips; not raw event count | None now; resolution timer + daily replay already in place | Only high-upside maker-flow path; build waits for real replay | Unknown; return at `100` replayable trips | `keep_recorder` |
| P1 | `bot_f_momentum_paper.db` | OQ-059 same-side momentum | New paper ledger | Starts from Bot F `mirror_signals`; BUY-only PASS-cell entries, 1800s public-trade exits | No forward closed sample yet | Let 5-min timer accumulate `100` closed entries | Tests whether historical 30m same-side edge survives executable BUY-only paper | `2-3wk` | `paper_promoted` |
| P2 | Bot F historical signal data | OQ-059 same-side momentum | Static but usable | 500 signals, 64 markets, 1340 observations; 8 PASS same-side cells | No fillability/queue replay | Preserve as source for `bot_f_momentum_paper` and post-run robustness | Could become a filter if PASS cells survive execution stress | `2-3wk` | `source_dataset` |
| P2 | the bot container `persistence_paper.db` | Persistence Paper (I) | Active daily paper/replay | `69` entries, `59` wins, Cell A `32/50`, Cell B `37/50` | Negative controls and outlier trims pending | Keep daily timer; review at `50/cell` | Fastest near-gate paper lane outside Bot D | `1-2wk` | `paper_promoted_existing` |
| P2 | the bot container main DB | Bot D/B/C/A legacy ledger, dashboard truth | Healthy enough for dashboard; legacy rows preserved | Bot D paper/live, archived bot ledgers | Bot D stale paper orders; OQ-096 payload fields | Payload backfill + stale paper cleanup | Cleans Bot D decision math and operator surface | `1-3` sessions | `modify_dataset` |
| P2 | VPS `main.db` | Bot D-Spike, Spike-Short, archived Crypto FV ledgers | Healthy at last VPS bridge check | Spike `5` closes; Spike-Short `4`; Crypto FV archive ledgers | Crypto FV external Becker/settlement join still absent but strategy archived | Only preserve; optional Becker join for research | Useful for audit, not active strategy spend | low urgency | `preserve` |
| P2 | `backtest.db` / Becker crypto resolved markets | Crypto research, OQ-079 | Local `526 MB` DB present | `16,042` resolved crypto Up/Down rows in non-whale audit | `0/289` overlap with local observer crypto Up/Down condition_ids | No immediate work unless crypto research reopens | Current crypto/copy-trade decisions do not depend on it | deferred | `defer` |
| P3 | the bot container Bot E recorder | Bot G replay, crypto context, future research | Healthy; `77.30 GB`, `57.7M` pm_events, `104.7M` CEX trades, `0` gaps | BTC/ETH/SOL full tape; shared ADR-122 infra | None urgent | Daily integrity check only | Keeps future replay optionality | same day if scripted | `keep_recorder` |
| P3 | VPS crypto recorder feed | Bot G, crypto context, XRP/DOGE record-only | Healthy; `21.03 GB`, `16.85M` pm_events, `18.30M` CEX trades, `0` gaps | BTC/ETH/SOL/XRP/DOGE | None urgent | Snapshot/rollover only if storage pressure | Active data plane after Crypto FV archive | n/a | `keep_recorder` |
| P3 | VPS `bot_g_vps_main.db` + daily probe reports | Bot G live/paper truth | Healthy enough for daily report | Bot G live/paper/shadow ledgers | None | Keep daily report | Confirms no-scale/no-halt decision quality | continuous | `watch_only` |
| P3 | WC negRisk monitor snapshot | WC 2026 observation | Script/report exists; not deployed as timer | 12 group baskets; scanner found `1,983` negRisk events | None for observation | Optional 5-min VPS timer during tournament | Captures fee-gated arb frequency; not a live bot | before `2026-06-11` | `optional` |
| P3 | PolyVerify / retail wallet CSVs | Wallet-tag cohorts, non-whale audit | Static inputs | 106 low-bot-score wallets; 245 Tier A/B retail wallets | Static labels can stale | Refresh only before a new wallet gate | Cohort hygiene | after OQ-099 | `defer_refresh` |
| P3 | Non-whale copy-trade audit artifact | OQ-101 | Complete | Cohort C `730` trades / `7` wallets; `0` settled; `0` book overlap | None; report already answers no-build | None | Prevents resurrecting direct copy-trade without new evidence | n/a | `closed_no_build` |

## Evidence Rules Applied

- Fees and 1c/2c stress are binding for Crypto FV and copy-trade decisions.
- Ex-largest and ex-largest-two are binding for Bot D paper, Bot G paper,
  Crypto FV, and Bot G live.
- No-lookahead and settlement-side scoring are binding for wallet-tag and
  copy-trade work; YES/NO token side must be scored by bought token, not by
  assuming every BUY is YES.
- Fillability is binding for Bot G live (`35%` EXCHANGE_CLOSED miss rate),
  Bot F same-side momentum, and non-whale copy-trade.
- No projected P&L is provided for lanes without settled forward evidence.

## Source Reports

- `docs/reports/bot-d-full-review-audit-2026-05-09.md`
- `docs/reports/bot-g-final-review-2026-05-09.md`
- `docs/reports/crypto-fv-final-review-before-archive-2026-05-09.md`
- `docs/reports/non-whale-copytrade-5m15m-analysis-2026-05-09.md`
- `docs/reports/archived-and-recorder-final-evaluation-2026-05-09.md`
- `docs/reports/wallet-tag-edge-finding-2026-05-08.md`
- `docs/reports/bot-f-crowd-momentum-ev-2026-05-08.md`
- `docs/reports/bot-f-anti-crowd-join-diagnostic-2026-05-08.md`
- `docs/reports/wc-2026-edge-research-2026-05-09.md`
- `docs/reports/polymarket-negrisk-scanner-2026-05-09.md`
- `docs/active-operating-model-2026-05-02.md`
- `docs/open-questions.md`
- `docs/decisions-log.md`
