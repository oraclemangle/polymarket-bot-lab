# Bot C Thesis — Pyth-GBM Directional on Traditional-Asset Binary Markets

**Date created:** 2026-04-18 (Session 17m — Phase 1 P1.1).
**Status:** **DRAFT, pending backtest verdict at 2026-04-22 (Pyth Pro expiry).**
**Supersedes:** template version at this path dated 2026-04-17.

---

## 1. The mispricing claim

The CLOB price for binary Polymarket markets on traditional-asset strike-price events is systematically mis-calibrated relative to Black-Scholes-implied barrier or terminal probability derived from Pyth's real-time spot + short-window realised volatility, because Polymarket's retail participants do not price these markets using an options-pricing model.

Concretely: when AAPL trades at $182 and Polymarket shows "Will AAPL close above $185 by 2026-04-25?" at YES=$0.42, a GBM model using 30-minute realised vol of the Pyth AAPL feed and 7%/yr equity drift will produce a different P(YES) — say 0.28. If |edge| ≥ 10% exceeds round-trip fees, positive EV.

The **mechanism** is retail crowd mispricing at tails (same as Bot A/D). The **difference** is Bot C targets strike-priced events where a closed-form model (GBM) provides an explicit model advantage — not a tail-fade pattern.

---

## 2. Falsifiable claim (what kills the thesis)

The thesis is falsified if any of:

1. **Calibration failure.** On ≥ 30 resolved paper trades, `|realised_WR − mean_predicted_WR| > 0.05`.
2. **Negative net PnL.** Mean net PnL per trade < 0 after 1.5-1.8% round-trip fees.
3. **Sample insufficiency.** Fewer than 30 trades in 30 paper days on the target market set.

Not falsified by: Pyth Pro expiring (cost problem, not thesis problem — Hermes fallback exists).

---

## 3. Entry rules (current Bot C code, 2026-04-18)

- **Universe:** binary Polymarket markets parseable by `bots/bot_c_pyth/discovery.py::parse_question`. Symbols: GOLD, SILVER, WTI, AAPL, TSLA, NVDA, COIN, PLTR, SPY, QQQ, EWY, BTC, ETH, SOL. Question kinds: `terminal` or `barrier`.
- **Vol estimate:** 1-sec Pyth bars, 1,800-bar short window (30 min) + 18,000-bar fallback (5h). Annualised per category (252×6.5h equity, 365×24h crypto).
- **Drift:** +7%/yr equity+ETF, 0 for crypto/commodity. Conservative.
- **Model:** `gbm_prob_above/below/between/barrier_*` in `strategy.py`. BSM with drift; barrier uses reflection principle.
- **Edge threshold:** `BOT_C_MIN_EDGE_FOR_ORDER = 0.15` after parabolic-fee netting (U-15 fix 2026-04-18: per-share fee).
- **Size:** fixed `BOT_C_PER_TRADE_USD = 10`. Single position per `gamma_id`.
- **Concurrency cap:** ≤ 3 open positions.
- **Bankroll cap:** `BOT_C_BANKROLL_USD = 50` now. **Phase 1 bump to $500 if backtest validates.**
- **Horizon cap:** ≤ 7 days (GBM σ estimate noise compounds with √T).
- **Volume filter:** `BOT_C_MIN_VOLUME_24H_USD = 500`.
- **Limit style:** post at mid.

---

## 4. Exit rules

No explicit exit. Hold to resolution. GBM edge is terminal-probability miscalibration, not momentum. Winners auto-redeem, losers auto-decay. `Portfolio.on_redeem` handles UMA-disputed/cancelled markets.

Manual cut-loss at operator discretion if a position drifts 50%+ against entry within 24h. Not automated — add later as amendment if experience justifies.

---

## 5. Not a duplicate of Bot A/D

| | Bot A (archived) | Bot D | Bot C |
|---|---|---|---|
| Archetype | tail-fade | tail-fade | model-vs-crowd |
| Price model | none | Gaussian/skew-normal | GBM w/ rolling σ |
| Trigger | yes ≤ 0.05 | edge vs GFS ≥ 0.10 | edge vs GBM ≥ 0.15 |
| Signal input | PM only | PM + GFS/METAR/NWS | PM + Pyth spot/vol |
| Hold | 21–180 days | 1–2 days | hours–7 days |
| Archetype tag | short_surprise | short_surprise | **model_driven** (new) |

Bot C is the first non-fade bot if validated — directly addresses the meta-review M-1 concern (fleet all `short_surprise`).

---

## 6. Backtest requirements + 2026-04-18 data reality

**Pass criteria:** positive net EV after 1.5-1.8% fees on ≥ 30 simulated trades.

**Current data state on the bot LXC container:** 7,015 `PythBarPro` rows covering **only 25 minutes** (2026-04-15 17:11:57 → 17:36:27). **Insufficient for a 30-trade backtest.** The bar ingest stopped or was reset.

**Two paths:**

- **Path A — restart Pyth ingest, wait 2 weeks, re-run 2026-05-02.** Pyth Pro expires 2026-04-22 mid-wait → fall back to Hermes.
- **Path B — synthetic-spot backtest (1-day work).** Pull yfinance/Polygon 1-minute OHLCV for AAPL/TSLA/NVDA/BTC/ETH over 2026-01-01 → 2026-04-15; synthesise "spot at T"; join with Polymarket historical markets for the same underlyings; run backtest. Caveat: no 1-sec resolution so σ estimate noisier than live Pyth.

**Phase 1 choice: Path B now**, Path A as follow-up if B produces < 30 trades. Harness: `scripts/bot_c_backtest.py` (ships this session).

---

## 7. Archive path if backtest fails

ADR-033 pattern:

1. Write ADR-034 citing backtest result.
2. `BOT_C_ARCHIVED=true` env guard in `bots/bot_c_pyth/__main__.py` + early-exit.
3. Kill-dates.md Bot C → ARCHIVED.
4. Cancel Pyth Pro, keep Hermes free path.
5. Retain code for restoration.

---

## 8. Infra reality check — 2026-04-18 discovery

While writing this doc I checked production state on the bot LXC container. Two findings materially reframe the Phase 1 decision:

**Finding 1 — Pyth ingest silently broken since 2026-04-15 17:37.**
Journalctl for `polymarket-bot-c.service` shows `pro: connection error: server rejected WebSocket connection: HTTP 502; backoff=...` at 17:37:46. Reconnect loop never recovered cleanly — `HB pro=no-ticks hermes=disabled` has fired every 30 seconds for 3 days. Bot continues scanning Gamma + evaluating markets using **stale cached spot** (AAPL frozen at 264.90509 across 13+ minutes of scans before crash; presumably identical now 3 days later). Pyth Pro trial was due to expire 2026-04-22; may already be revoked server-side.

**Finding 2 — Market universe is structurally thin.**
Gamma scans at 2026-04-18 21:47 return **3 parseable candidates per scan**; pre-crash snapshots at 2026-04-15 returned 10. `bots/bot_c_pyth/discovery.py::parse_question` only matches a narrow question-phrasing template. Even on the most favourable day in the logs, 10 candidates/scan × 3–5 filtered by volume/edge = ~2–5 actionable markets at any moment. At 10 trades/week (best case — Pyth fixed, all filters clean) the 30-trade paper-gate criterion would take 3+ weeks, pushing any decision past Pyth Pro expiry.

## 9. Revised Phase 1 verdict — 2026-04-18

**Recommendation: archive Bot C using the ADR-033 pattern.**

**Evidence:**
- Thin market universe (3–10 candidates/scan) caps trade cadence below 15/week even if infra is fixed.
- Pyth Pro infrastructure broken for 72 hours; cost to fix is a full session, then 2+ weeks of data accumulation before a real backtest.
- Competing Phase 1 priorities (Bot E ML, Bot F cascades) have working data and are more likely to produce actionable signals in the same window.
- Per ADR-033 reversal contract: archive with env flag, retain code, restoration requires a new thesis AND evidence of sufficient market-universe depth (not just a Pyth fix).

**If operator disagrees:** acceptable alternative is a 1-week infra-fix sprint — diagnose Pyth auth / WSS reconnect, widen `parse_question` regex to capture more market phrasings, bump `BOT_C_BANKROLL_USD` to $500 for faster data, then re-run this decision at 2026-05-02.

Default action for this session: **archive Bot C now.**

---

## 10. Sign-off

- **Author:** Claude Code (Session 17m, 2026-04-18).
- **Operator approval:** _pending. Recommended action: archive per §9._
- **Paths A and B (§6) superseded by §8 infra finding.**
