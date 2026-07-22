# polymarket-bot-lab

A lab of **11 candidate Polymarket trading bots** plus a full research framework: CLOB clients, fee models, backtest tooling, tests, and a fleet dashboard. Sanitized export of a 2026 multi-bot research project. Built for people to **use, fork, and extend** — not as a productized live-trading system.

Two strategies showed **positive expectancy in testing** and are the headline candidates below. The rest are documented, runnable starting points with real backtest or paper/live-probe data and clear notes on what still needs refinement before any edge is claimed. Past results are not future results. Confidence intervals, sample sizes, and promotion criteria are part of the record on purpose; they are the credibility.

---

## Headline candidates (positive expectancy in testing)

### 1. Playbook — sports mid-band NO-fade (primary research path)

**Thesis:** Buy NO when sports YES is priced roughly **55–75c**, typically **6–78h** before close — mid-band favorite overpricing, not the toxic sub-5c tails that left other longshot lanes unprofitable as-tested.

**Tested result (local `backtest.db` re-check, April tape):** n=573 regex-matched sports in the 55–75c band; hit rate **57.4%** vs **63.5c** mean implied; post-fee NO-fade ROI **+5.32%**. Trade-bootstrap 95% CI **[-4.73%, +15.64%]** — **crosses zero**. Treat as a research candidate, not a proven edge. Related code lives under `bots/bot_k_sports_taker/` and sports-related research scripts/reports.

### 2. Nimbus — weather range-fade (runner-up)

**Thesis:** Fade mispriced temperature range / station-linked weather markets with disciplined filters and shared risk gates.

**Tested result (tiny live probe):** **+$31.06 / +11.07% ROI / 95 closed groups** — the only positive live P&L sample in the fleet record. Restart or scale was gated on accounting and operator open questions (see ADRs / OQs in `docs/`). Implementation: `bots/bot_d_weather/`.

Neither headline claims guaranteed profit. Both are starting points with numbers you can re-run and stress — promising, unproven.

---

## Research framework

Shared infrastructure for building and evaluating bots:

| Area | Path | Role |
|---|---|---|
| CLOB clients | `core/clob.py`, `core/clob_v2.py`, `core/polymarket_v2.py` | Polymarket order/book/auth surface (V1 + V2 era) |
| Fees | `core/fees.py` | Fee math for realistic P&L (taker/maker-aware) |
| Backtest engine | `core/backtest*.py`, `core/backtest_db.py` | Offline replay and bot-specific backtest helpers |
| Portfolio / risk | `core/portfolio.py`, `core/exec_policy.py`, `core/emergency_halt.py` | Exposure, policy, halt patterns |
| Fleet registry | `core/bot_registry.py`, `core/fleet.py` | Canonical bot metadata and aggregate caps |
| Tests | `tests/` | Unit and integration coverage as exported |
| Dashboard | `dashboard/` | Local fleet overview UI and runtime queries |
| Specs / ADRs | `specs/`, `docs/decisions-log.md`, `docs/` | Strategy specs, architecture decisions, refinement notes |

Other useful entry points: `research/` (CLOB notes), `scripts/` (one-off research and audits), `bots/` (per-strategy packages).

---

## Bot roster

Eleven candidate strategies ship as code and docs. **Oracle** (`bot_b`) is reference-only (implementation excluded; integration path open for anyone with scorer access — see external scorer note). Each row is one-line status plus a **refinement direction** — honest, not promotional.

Directory paths and id strings (e.g. `bot_k`, `bots/bot_k_sports_taker/`, `BOT_K_*`) are internal codenames; human display names map in this table.

| # | Bot | Package | Status and refinement direction |
|---|---|---|---|
| 1 | **Playbook** `bot_k` | `bots/bot_k_sports_taker/` | **Headline.** Sports mid-band NO-fade; positive post-fee sample ROI with CI that still crosses zero. Refinement: larger sample, regime splits, fee/fill stress before any live scale claim. |
| 2 | **Nimbus** `bot_d` | `bots/bot_d_weather/` (+ `bot_d_spike*`) | **Headline.** Weather range-fade; only positive tiny-live P&L sample in the record. Spike variants need filter and promotion-gate work before reuse. Scale gated on accounting reconciliation. |
| 3 | **Longshot** `bot_a` | `bots/bot_a/` | General binary NO tail-fade; unprofitable as-tested on walk-forward (jackpot losses ate the grind despite high hit rate). Refinement: cap or reprice extreme tails; see ADR-033 and reports. |
| 4 | **Pythia** `bot_c` | `bots/bot_c_pyth/` | Pyth/GBM directional on crypto and indices; set aside pending model and data-feed refinement. Data/model pieces retained for reuse. |
| 5 | **Scribe** `bot_e` | `bots/bot_e_btc_scalp/` | Near-resolution / OBI-style crypto scalp research code; paused pending fill-realism and latency work before any edge claim. Companion dataset authored via the retained recorder path (`bots/bot_e_recorder/`). |
| 6 | **Sonar** `bot_f` | `bots/bot_f/` | Crowd / whale-sensor experiments; historical sensor path. Refinement: reframe as cascade detector inputs rather than direct copy-trade. |
| 7 | **Dash** `bot_g` | `bots/bot_g_longshot/` | Crypto near-resolution longshot family (Prime and variants); unprofitable as-tested on paper/live probes. Refinement: tail exposure and fee-aware sizing. |
| 8 | **Quill** `bot_h` | `bots/bot_h_maker_v2/` | Maker / rebate research and recorder path; live maker probes stayed behind fill-conditioned replay gates. Refinement: prove fill realism before maker capital. |
| 9 | **Relay** `bot_j` | `bots/bot_j_nr_wallet/` | Neg-risk / wallet-linked paper starting point; needs wallet-signal quality and risk gates before a live money path. |
| 10 | **Compass** `bot_l` | `bots/bot_l_complete_set/` | Complete-set style probe; documented starting point with real test trail. Refinement: inventory and arb economics under fees. |
| 11 | **Meridian** `crypto_fair_value` | `bots/crypto_fair_value/` | Crypto fair-value / probability-gap maker-style probes; unprofitable as-tested in live/paper samples. Refinement: quote staleness and adverse selection. |
| — | **Oracle** `bot_b` | *(code excluded)* | LLM + external-scorer Kelly path; reference entry — integration open for anyone with scorer access via https://oraclemangle.com. See `docs/bot-b-reference.md`. |

Infrastructure (not counted in the 11): Scribe's recorder package `bots/bot_e_recorder/`, `bots/wallet_observer/`, notify/watchdog daemons. Decision spine: `docs/decisions-log.md`. Promotion criteria, pause dates, and fleet reviews live under `docs/`.

---

## Companion dataset

Market and tape data used in research are released separately:

**→ see [DATASET.md](DATASET.md)** (polymarket-canary-tape; hosting links TBD on Zenodo / Hugging Face).

Code in this repository is Apache-2.0. The companion dataset is **CC-BY-4.0**.

---

## Licensing

| Artifact | License |
|---|---|
| Code and documentation in this repository | [Apache License 2.0](LICENSE) |
| Companion dataset (polymarket-canary-tape) | CC-BY-4.0 (see [DATASET.md](DATASET.md)) |

Third-party notices: [NOTICE](NOTICE). Citation metadata: [CITATION.cff](CITATION.cff).

Copyright 2026 the longshot-research authors.

---

## Research only — not financial advice

This is **research and engineering material**, not financial advice. Nothing here is a guarantee of profit. Strategies may look positive in a sample and still need refinement under fees, adverse selection, regime shift, or operational load. Paper and tiny-live results do not imply scalable live performance. Do not trade with capital you cannot afford to lose. You are responsible for venue terms of service, local law, tax, and risk.

---

## External scorer (Oracle / `bot_b` code not in this repo)

One strategy path (**Oracle** / Kelly-with-external-scores) consumed scores from a **closed commercial product**:

**[Oraclemangle](https://oraclemangle.com)**

This repository may cite that product and the bot architecture at a reference level. It does **not** ship the scorer, model weights, calibration data, scored-output datasets, or the integration client tightly coupled to that boundary. Anyone with scorer access can rebuild the integration path; see `docs/bot-b-reference.md`.
