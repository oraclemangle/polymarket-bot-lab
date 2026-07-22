# Architecture Decision — Polymarket Bot Dual-Track

**Date:** 2026-04-14
**Phase:** 3 (architecture lock)
**Status:** Decided, pending three user confirmations in §9

Implementation note (2026-04-15): the Bot B scorer path in this Phase 3 plan
was later superseded by ADR-015. Current code calls an externally calibrated
dispute-risk scorer (see https://oraclemangle.com) over HTTP and persists
derived `claude_pick` / `claude_implied_prob` locally instead of maintaining
a full in-repo scorer.

Supersession note (2026-05-02): this Phase 3 dual-track document is
historical for active operations. The current fleet model is
`docs/active-operating-model-2026-05-02.md` and ADR-071. Bot A and Bot F are
archived from active dashboard surfaces; Longshot Prime, Weather Fade,
Oraclemangle Kelly, Pyth Directional, and Maker Flow are the active
operator-facing fleet.

---

## Working assumptions (flagged up front)

The user's template for bankroll + drawdown + tax posture was left un-filled at the end of Phase 2.5. This doc proceeds under the following working assumptions. Any of these being wrong voids the corresponding plan below; ≤3 confirmations gate a start in §9.

- **Total bot bankroll**: £5,000 (~$6,250 at current rates). Ring-fenced. Written off in a black-swan.
- **Max drawdown before kill**: 15% of bankroll (£750 / ~$940) per bot, 20% aggregate (£1,000).
- **Time horizon**: 12 weeks from first paper-trade fill to "kill or scale" decision.
- **Tax posture**: gate (c) — CGT-on-ERC-1155-disposal working assumption, advisor opinion in flight in parallel. Log every trade in HMRC-ready format from day 1.
- **ToS posture**: gate (c) — capped-exposure compromise. Max $2,000 live exposure at any moment across both bots. VPN on the homelab hypervisor node (the VPN provider wireguard) for all CLOB traffic.
- **Rotation pattern**: assumed 4-weeks-home / 4-weeks-at-sea. Build tasks scheduled to fit a 4-week home window. **Verify in §9.**

All monetary figures below are GBP unless marked $.

---

## Section 1 — The decision

### Bot A — "Longshot Fade"
Mechanical longshot fader. Scan Polymarket's open books for UMA-resolved binary markets where `yes_price ≤ 0.05`, volume_24h > $5k, days-to-resolution between 30 and 180, and category ∈ {geopolitics, politics, finance, economics}. Buy the NO side at `(1 - yes_price)`, hold to resolution, redeem. Thesis is base-rate: most long-odds prediction-market binaries resolve NO, the crowd systematically over-prices tail outcomes, and the sub-0.05 tail is where the mispricing is largest and cheapest to harvest. No LLM in the loop. No external-scorer dependency. Grok's intel flagged one wallet doing this pattern at $300 → $117k over 31k predictions; the archetype exists and is thinly populated because the edge per trade is small and the holding period is long, which most bot-builders won't tolerate.

### Bot B — "Oraclemangle Kelly"
LLM-model directional bot fed by an externally calibrated dispute-risk scorer (see https://oraclemangle.com) — scraper re-activated, `claude_pick` populated, `claude_confidence` persisted — with scoring consumed in this bot's repo rather than depending on an external daemon's schedule. Markets selected where `dispute_risk ≤ 0.25`, `claude_confidence ≥ 0.7`, `|claude_implied_prob − yes_price| ≥ 0.08`, in {geopolitics, politics, economics, finance}. Sized by quarter-Kelly with a dispute-risk penalty multiplier. Held until resolution or until model-implied edge collapses below a re-check threshold. Differentiator vs Bot A is the scored signal; the strategy owns market selection, Kelly sizing, and risk controls here.

### Why these two, why not the others

The two differ on **every** meaningful dimension: edge source (base rate vs model), holding period (30–180 days vs days–weeks), signal generation (mechanical vs LLM-scored), external-scorer dependency (none vs total), failure modes (oracle tail risk only vs oracle + model-calibration risk), observability (deterministic rules vs LLM-black-box). That's a clean A/B. If they both make money, you've diversified edge. If only A makes money, you've validated the cheap baseline and learned the LLM didn't add enough alpha to justify its complexity. If only B, you've validated the model-scored edge. If neither, you've learned this game isn't for a solo UK operator and saved yourself from scaling into a losing thesis.

### Rejected alternatives (explicit)

| Alternative | Rejected because |
|---|---|
| **Market-making / rebate farming** (RN1/swisstony archetype) | Requires $50k–$500k inventory, sub-100ms requote loop, adverse-selection engineering. Wrong capital tier, wrong infra, wrong product. Would consume all build attention without advancing either bot's thesis. |
| **Near-resolution crypto scalping** (5/15-min BTC/ETH windows) | Spreads tightened to 0.3–0.5¢ per Grok intel; latency-bound; UK loses the queue-position game to Virginia-colocated bots; Fee V2 crypto category is 7.2% feeRate (worst). |
| **Delta-neutral volatility split** on crypto | Gas + one-leg-fill risk + timing pressure; 1–2% per cycle isn't enough margin to survive a single merge/split gas spike; still crypto-category. |
| **Cross-venue arb (Polymarket ↔ Kalshi)** | Kalshi is US-KYC dominated; UK access to both venues is fragile; cross-venue match quality is unreliable; the edge requires reliable simultaneous fills on both legs, which a single operator can't guarantee. |
| **Copy-trading verified sharps** (Theo4/Fredi9999) | Reactive, not an edge of our own. Their picks reach you slower than they move the book. Survivor bias on which wallets to copy. Can't unwind a losing copy without owning the original thesis. |
| **Pure sentiment / news-latency** | Headlines → market reaction window is a speed game; Grok specifically noted "less for reasoning" in this bucket. UK RTT kills it. |
| **Weather directional (GFS vs crowd)** | Genuinely tempting and I considered it hard. Rejected as a v1 pick because Polymarket weather-market volume is not yet verified (weather is Kalshi-dominant historically). Holding it as the v1.5 candidate for Bot C if Bot A or Bot B fails. |
| **TimesFM-based short-horizon crypto** | Good candidate but sits in the most-crowded + highest-fee category. Better as a v2 experiment once the shared infra is proven. Flagged in memory for future consideration. |

---

## Section 2 — Bot A — Longshot Fade

### Thesis
Polymarket's binary UMA-resolved markets systematically over-price tail outcomes in the sub-$0.05 region. Two forces create this: (1) retail "lottery ticket" buyers who pay above fair value for upside optionality, (2) thin liquidity at the far tail where an MM's small YES inventory sits wider than fair. A disciplined fader who buys NO at $0.95+, waits out resolution, and stays in zero-fee (geopolitics) or low-fee (politics/finance/economics) categories captures the over-round. Edge persists because the hold is 30–180 days, which bot-builders chasing short-horizon flash-strategies won't tolerate — the crowd of competitors self-selects out of this trade.

### Market selection
- **Category**: {geopolitics (fee=0), politics (fee=0.04), finance (fee=0.04), economics (fee=0.05)}. Never crypto or sports.
- **Structure**: binary (YES/NO) only. No multi-outcome / neg-risk markets in v1 (different contract, different fill math, adds complexity for no gain).
- **Filters**:
  - `yes_price ≤ 0.05`
  - `volume_24h ≥ $5,000` (ensures exit optionality if thesis breaks)
  - `days_to_resolution ∈ [30, 180]` (short enough to compound, long enough to avoid event-driven variance)
  - `book_depth_at_nobid ≥ $500` notional within 2¢ of mid
  - `question` not on a manual blacklist (sanctions, assassination markets, anything that makes HMRC reporting awkward)
- **Expected universe**: ~40–120 active candidate markets at any time. Estimate from a rough scan of open books — verify on fresh data.

### Signal generation
**There is no signal model.** The rule IS the signal:
```
if (market matches filter) and (no existing position) and (capital_available):
    place NO buy at (1 - best_yes_ask), size = position_size_rule()
```
Deliberately mechanical. This is the baseline that doesn't "trust the LLM".

### Execution
- **Order type**: GTC limit at `(1 - best_yes_ask)`. No market orders. No crossing the spread except on kill-switch unwinds.
- **Sizing rule** (fixed-fraction, not Kelly): `position_size = min($30, 1% of bankroll, 2% of book_depth)`. Starting at $30 (£24) per market. Deliberately small to diversify across the 40–120 candidate universe.
- **Entry**: one order per qualifying market. No pyramiding.
- **Exit** (normal): hold to resolution, redeem winning NO shares for USDC.e.
- **Exit** (abnormal): if `yes_price` rises above $0.25 (market swung against us 5x), cut at market. Reason: the thesis was base-rate at a specific pricing regime; a 5x move invalidates the regime assumption.
- **Exit** (dispute): if the market enters UMA dispute, hold — don't panic-sell into low liquidity. Re-assess after DVM resolution.

### Risk controls
- **Per-market cap**: $30 notional.
- **Aggregate cap**: $1,000 across all open Bot A positions.
- **Drawdown kill**: if unrealised + realised PnL hits −£150 (15% of Bot A's £1,000 allocation), cancel all open orders, halt new entries, alert via Telegram. Human-in-loop to resume.
- **Staleness halt**: if market data feed lags >5 min, halt new orders.
- **Dispute-streak halt**: if 3 consecutive closed positions resolved via dispute (regardless of outcome), halt until human review.

### Capital allocation
- **Starting**: £1,000 allocated to Bot A (paper for first 30 days; live with £250 after graduation).
- **Scaling**: if realised PnL after 30 live days is positive AND max drawdown <10%, scale to £500. If positive at 60 days AND drawdown <12%, scale to £1,000. No further scaling without re-decision.

### Expected performance (estimates, not promises)
- **Edge per trade**: I estimate 4–8% of notional on expected value (i.e., buying NO at $0.95 when fair value is $0.97–0.99). Flag: this is inferred from base-rate analysis of resolved UMA markets, not empirically measured on this filter. Verify in paper.
- **Trade frequency**: 15–40 entries/week (one per qualifying new market, turnover limited by resolution cadence).
- **Hold**: 30–180 days mean, ~90 days.
- **Hit rate**: estimate 88–96% win rate (mechanical consequence of buying at 95¢ when the fair value is 96–98¢). Losses are full-notional on the rare YES resolution.
- **Sharpe-equivalent**: estimate 1.2–1.8 annualised, high uncertainty. The returns distribution is heavily skewed: many small wins, rare large losses. Sharpe understates this risk shape; Calmar (return ÷ max drawdown) is the better KPI.
- **Max drawdown (theoretical)**: 5–15% over any 90-day window, dominated by concurrent YES-resolution events.

### Failure modes
- **Base-rate regime shift**: prediction-market crowd gets more sophisticated, tail prices tighten from $0.05 fair value to $0.02 fair value, edge evaporates. Observable: hit rate stays high but edge per trade compresses.
- **Correlated tail event**: an unexpected geopolitical shock causes a basket of "longshot" markets to resolve YES simultaneously (e.g., a single election night with many upsets). Observable: 5–10% drawdown in a single day.
- **Liquidity drought at exit**: can't unwind a panic cut because the YES side that mispriced is gone and the NO side has also thinned. Observable: a cut-loss order sits at the touch for hours.
- **Oracle dispute on a won position**: UMA DVM votes P4 ("unknown") on a market we were about to redeem; we get refunded but lose the $30 opportunity cost. Observable: `disputes` count in the tape.
- **Death pattern**: hit rate drops below 80% for 2 consecutive weeks, or average edge per trade falls below 2%.

### Tech stack
- **Language**: Python 3.11
- **Libraries**: `py-clob-client` (order placement), `httpx` (Gamma API for market metadata), `sqlalchemy` + **SQLite** (local state — Postgres migration deferred), `tenacity` (retry), `cryptography` (keystore), `python-telegram-bot` (alerts)
- **Data sources**: Polymarket Gamma API for market list; CLOB REST for books + orders; CLOB WSS `user` channel for fills
- **Storage**: SQLite local + daily snapshot to encrypted S3-compatible blob (Backblaze B2, ~$0.01/month) for disaster recovery
- **Monitoring**: Telegram bot for alerts; Uptime Kuma on the homelab hypervisor for daemon liveness; systemd journal for everything

### MVP scope
- **Week 1**: shared infra (§6). Bot A does nothing yet.
- **Week 2**: Bot A paper-trading mode. Fetches live book, generates paper fills at the touch, logs to `bot_a_trades` table, alerts to Telegram on each simulated entry/exit. No real money.

### What Bot A does NOT do
- Does not score markets with an LLM. Ever.
- Does not read external scorer tables.
- Does not attempt to predict the outcome — only to harvest the over-round.
- Does not cross the spread on entry.
- Does not scale a position. One entry per market, period.
- Does not trade crypto or sports categories.
- Does not trade multi-outcome / neg-risk markets.

---

## Section 3 — Bot B — Oraclemangle Kelly

### Thesis
An externally calibrated dispute-risk scorer (see https://oraclemangle.com) supplies model-vs-crowd signal on ambiguous-resolution markets. The crowd under-prices resolution ambiguity (they trade as if binary outcomes are binary); the scorer prices it explicitly. When the scorer's implied probability diverges meaningfully from the crowd's price AND dispute_risk is low (so the tail isn't a DVM coin flip), there's an edge worth sizing. Persistence of edge, if any, is an empirical question for paper and live runs; the strategy is low-frequency enough that a 10-minute decision latency does not kill it.

### Market selection
- **Category**: {geopolitics (fee=0), politics (fee=0.04), economics (fee=0.05), finance (fee=0.04)}
- **Structure**: binary UMA-resolved only
- **Filters**:
  - `dispute_risk ≤ 0.25` (avoid the DVM-coin-flip zone)
  - `claude_confidence ≥ 0.7` (only act when the model says it knows)
  - `|claude_implied_prob − yes_price| ≥ 0.08` (minimum 8 percentage points of edge before fees/slippage)
  - `volume_24h ≥ $10,000`
  - `book_depth_at_pick_side ≥ $1,000` notional within 3¢
  - `days_to_resolution ∈ [7, 365]`
- **Expected universe**: ~5–30 active candidate markets at any time. Estimate — verify on fresh scored data.

### Signal generation
Pipeline:
1. **Scraper** (cron, every 15 min): fetch Polymarket open markets via Gamma API → `open_markets` table. Bot B owns its own scraper in the bot repo; it does not depend on an external daemon.
2. **Scorer** (cron, every 30 min): for each unscored market, call an externally calibrated dispute-risk scorer (see https://oraclemangle.com) → populate `dispute_risk`, `resolution_prediction`, `claude_confidence`, `claude_implied_prob`, `claude_pick`.
3. **Filterer** (on every scoring batch): apply §3 filters → emit candidate list
4. **Sizer** (on each candidate): `kelly = 0.25 × ((p_model − p_market) / (1 − p_market))`, capped at 4% of bot bankroll per position. Dispute-risk penalty: multiply by `(1 − dispute_risk / 0.25)` so DR=0.25 → 0 size, DR=0 → full Kelly.
5. **Executor**: place GTC order at the model-inside price.

### Execution
- **Order type**: GTC limit at `market_mid ± 0.005` (inside the spread). Rationale: maker rebates + lower fill cost; we're not latency-sensitive, and missing a fill is cheaper than crossing.
- **Re-post**: if not filled in 2 hours, cancel, re-fetch book, re-post at current mid ± 0.005.
- **Exit (normal)**: hold to resolution.
- **Exit (edge-collapse)**: if the model re-scores the market and `|p_model − yes_price| < 0.03`, cancel open orders and close the position at market. The edge has been absorbed.
- **Exit (dispute)**: if market enters DVM dispute, hold and wait — the position is either settled by UMA or refunded.
- **Exit (kill-switch)**: on any risk-control trigger (§3.5), cancel all orders, close positions at market.

### Risk controls
- **Per-market cap**: 4% of Bot B bankroll = £40 at £1,000 allocation. Hard cap regardless of Kelly recommendation.
- **Aggregate cap**: £800 across all open Bot B positions.
- **Drawdown kill**: −15% of Bot B bankroll halts entries, cancels unfilled orders, alerts.
- **Stale-score halt**: if any market's score is >12 hours old, it drops from the candidate pool automatically.
- **Stale-data halt**: if scraper hasn't run in >45 min, halt entries.
- **Dispute tail-risk cap**: no more than 3 open positions in `dispute_risk ∈ [0.15, 0.25]` at once. Limits the number of tail-risk eggs in one basket.
- **Calibration halt**: if 10 consecutive resolved Bot B positions show mean `model_prob − realised_outcome > 0.15`, halt for re-calibration. The model has drifted.

### Capital allocation
- **Starting**: £1,000 allocated (paper for 30 days; live with £250 after graduation)
- **Scaling**: same schedule as Bot A — £250 → £500 → £1,000 contingent on realised PnL + drawdown bounds

### Expected performance (estimates, not promises)
- **Edge per trade**: 8–18% of notional when the filter triggers. Based on prior calibration-oriented backtests of the external scorer, not a trading-rule P&L simulation. **Flag: actual trading edge is unmeasured.**
- **Trade frequency**: 3–12 entries/week, with seasonal variance (more during election cycles, less in quiet periods)
- **Hold**: 7–365 days, mean ~45 days
- **Hit rate**: estimate 60–70% — the model is making directional calls against the crowd and the crowd isn't always wrong
- **Calmar (return ÷ max drawdown)**: estimate 1.0–2.5, very high uncertainty
- **Max drawdown (theoretical)**: 8–18% over any 90-day window, dominated by oracle dispute losses and model mis-calls on geopolitical tail events

### Failure modes
- **Model drift**: the external scorer's calibration shifts (provider change, data aging, dispute_risk distribution changes). Observable: calibration-halt trigger fires.
- **Oracle tail hit**: a high-volume position we sized at full DR-penalised Kelly still catches a DVM P4 ("unknown") vote. Observable: single-position loss >5% of bankroll.
- **Model echo**: the LLM's probability tracks the market price with a small lag, producing apparent edge that's actually just "the crowd from 2 hours ago." Observable: edge per trade drops sharply when we shorten the re-scoring interval.
- **Scraper breakage**: staleness halt fires regularly. Observable: >20% of days have stale-halt events.
- **Death pattern**: calibration halt fires, OR 4 consecutive weeks of negative PnL with drawdown approaching 15%, OR model_echo test (§5) fails.

### Tech stack
- **Language**: Python 3.11 (reusing shared infra)
- **Libraries**: all of Bot A's + HTTP client for the external scorer API; optional local helpers for caching scores
- **Data sources**: Polymarket Gamma (markets), UMA subgraph via The Graph (resolved history + disputes), externally scored outputs persisted locally
- **Storage**: SQLite for bot state; both local on the homelab hypervisor
- **Scorer**: externally calibrated dispute-risk scorer (see https://oraclemangle.com)

### MVP scope
- **Week 1**: shared infra (shared with Bot A)
- **Week 2**: Bot B scraper + scorer client (fixing `claude_pick` + `claude_confidence` persistence); fills `open_markets` with fresh data + complete scoring
- **Week 3**: Bot B paper-trading mode. Consumes filled pipeline; generates paper fills on live book data; logs to `bot_b_trades`.

### What Bot B does NOT do
- Does not re-implement the external scorer — consumes scored outputs via API
- Does not depend on an external daemon schedule — owns scraper + score consumption in-repo
- Does not trade markets the model hasn't scored in the last 12 hours
- Does not use a pre-populated `kelly_fraction` from the scorer — computes Kelly fresh in-bot
- Does not trade multi-outcome / neg-risk markets in v1

---

## Section 4 — Differentiation matrix

| Dimension | Bot A — Longshot Fade | Bot B — Oraclemangle Kelly |
|---|---|---|
| **Edge source** | Base-rate over-round on tail outcomes | LLM-scored resolution-risk + directional model |
| **Market category** | Geopolitics / politics / finance / economics (same) | Geopolitics / politics / finance / economics (same) |
| **Market sub-filter** | `yes_price ≤ 0.05` tail | `|p_model − p_market| ≥ 0.08` mid-book |
| **Holding period** | 30–180 days | 7–365 days, mean ~45 |
| **Trade frequency** | 15–40 entries/week | 3–12 entries/week |
| **Signal generation** | Deterministic rule | External scorer + Kelly |
| **External-scorer dependency** | None | Consumes scored outputs; owns filter/size/execute |
| **Required bankroll** | $250 viable, $1,000 comfortable | $250 viable, $1,000 comfortable |
| **Capital intensity** | Low — $30/position | Low — $40/position cap |
| **Observability** | High — rule-based, auditable | Medium — LLM is a partial black box |
| **Compute cost** | Negligible | $20–50/month external scorer API |
| **Primary failure mode** | Correlated tail event, base-rate regime shift | Model drift, oracle tail hit, model echo |
| **Primary tech risk** | Scraper reliability | External-scorer availability + scraper reliability |
| **Graduation bar** | Higher (lower expected edge per trade, needs longer paper period to confirm) | Lower (larger per-trade edge, confirms or fails faster) |
| **Infra needs** | systemd + SQLite + Telegram | systemd + SQLite + external scorer API access |
| **Build time estimate** | ~3 days after shared infra | ~8 days after shared infra (scorer client + scraper fix) |

---

## Section 5 — Test protocol

### Paper trading phase

**Duration**: 30 calendar days per bot from first paper-fill. 30 days picked because (a) a typical Bot A entry takes ~90 days to resolve, so even 30 days is a small sample of actual PnL; we're testing the *machinery* and *theoretical edge*, not realised PnL. Bot B can accumulate 15–50 theoretical resolutions in 30 days because its holding period is shorter.

**What counts as enough data**:
- Bot A: 60+ paper entries placed (filter is firing) AND 5+ simulated resolutions
- Bot B: 20+ paper entries placed AND 10+ simulated resolutions

If either bot fails to hit entry-count minimums in 30 days, the filters are too tight (fine — loosen once) or the thesis doesn't have enough candidate markets (bad — re-evaluate).

**Metrics tracked daily**:
- **Primary**: Calmar-equivalent on simulated PnL (realised + mark-to-market)
- **Secondary**: entries/day, fill rate (for paper, always 100% at touch; for live, real fill rate), avg edge captured vs theoretical, simulated slippage, oracle-dispute-hit count
- **Failure tripwires**: any single simulated position >10% loss, max simulated drawdown >12%, any "unexplained" behaviour (log-detectable anomaly the developer can't account for)

### Live graduation criteria

**Before any real money**:
1. 30 paper days completed on the bot in question
2. Entry-count minimums met
3. Simulated Calmar ≥ 0.8 (relaxed from ideal 1.2+ because paper Calmar can't capture real slippage; the relaxation is the "trust discount" on paper)
4. No unexplained log events in the last 14 days
5. Manual code review by the user of the filter + sizer + executor
6. One live dry-run that places a $5 order, cancels it before fill, and verifies the whole auth + signing + cancel path

**Live capital graduation**:
- £250 per bot on graduation (total £500 across both)
- If after 30 live days: realised PnL ≥ 0 AND drawdown < 10%, scale to £500
- If after 60 live days: realised PnL > 0 AND drawdown < 12%, scale to £1,000
- Never scale beyond £1,000 per bot without a full re-decision session

### Decision rules (concrete thresholds)

**Kill a bot when**:
- Live drawdown hits 15% of bot bankroll
- 4 consecutive weeks of negative realised PnL
- Bot-specific death pattern fires (Bot A: hit rate <80% for 2 weeks OR avg edge <2%; Bot B: calibration halt fires OR model-echo test fails)
- Any single unexplained log event that reveals a bug capable of unbounded loss (kill regardless of PnL state)

**Double down on a bot when**:
- 60 live days complete
- Realised Calmar > 1.5
- Drawdown never exceeded 10%
- At least one full "bad month" survived with <5% drawdown

**Stalemate (keep running but don't scale)**:
- Realised PnL positive but below risk-free rate
- Calmar in [0.5, 1.5] range
- No clear signal either way

### Model-echo test (Bot B only)

Weekly, run a diagnostic: compute `edge_at_score_time − edge_at_score_time_minus_2h`. If the mean absolute difference is small (<0.01), the "edge" is really just the crowd from 2 hours ago reflected back through the scorer. Flag and review.

### Timeline & decision points

Expressed in calendar weeks from Week 1 of the build. Dates in §7.

- **Week 4 end**: Bot A paper launch
- **Week 5 end**: Bot B paper launch
- **Week 8 end**: Bot A paper review → live graduation decision
- **Week 9 end**: Bot B paper review → live graduation decision
- **Week 12 end**: Live A/B checkpoint → kill/stalemate/scale decision per bot
- **Week 16**: hard decision — if neither bot is live-profitable by this point, terminate both and return to discovery

---

## Section 6 — Shared infrastructure

Built once, used by both bots. Estimated build time: **6 working days** over ~10 calendar days in one rotation window.

### Components

**1. CLOB client wrapper** (`core/clob.py`) — 1 day
- Thin wrapper around `py-clob-client` exposing: `get_book`, `get_tick_size`, `place_limit_order`, `cancel_order`, `cancel_all`, `get_user_trades`, `subscribe_user_channel`
- `tenacity` retry on `(PolyApiException, httpx.ConnectTimeout, httpx.ReadTimeout)` — `wait_exponential(0.5–8s)`, max 5 attempts
- Rate-limit awareness: local token bucket at 80% of published limits to stay well under cap
- HMAC canonical string verified against `py_clob_client/signing/hmac.py` before first use (Phase 2.5 gap)
- **No private key handling** inside this module — keys are injected by `core/keystore.py`

**2. Key management** (`core/keystore.py`) — 1 day
- Encrypted keystore at `~/.config/polymarket-bot/keystore.age`, age-encrypted (preferred over gpg for simplicity)
- Passphrase prompted on daemon start (systemd `ExecStartPre` reads from a `PassphraseFile=` pointing at an in-memory tmpfs location populated via SSH on boot)
- Decrypted key held in a `SecureBytes` wrapper that zeroes on scope exit where Python allows
- **No hardware wallet path in v1**. Rationale: `py-clob-client` has no HW-wallet integration, building one is a 2-week project in itself, and a dedicated hot wallet capped at $2k exposure is the risk-appropriate substitute
- **Treasury**: Ledger-held wallet, separate from hot wallet. Manual top-ups only. Never trades.

**3. Market data ingestion** (`core/ingest.py`) — 1.5 days
- Scraper: Gamma API for market list; pagination; backoff; upsert to `markets` table
- Book snapshotter: REST `/book` every 5 min for each market in the active set; stores to `books` table
- Trade stream: WSS `user` channel subscribed once per daemon; writes to `trades` table on fill
- Settlement watcher: polls UMA subgraph for resolution events on markets we hold; triggers redeem flow

**4. Storage** (`core/db.py` + `migrations/`) — 0.5 days
- SQLite with `sqlalchemy` + Alembic migrations
- Tables: `markets`, `books` (snapshot), `trades`, `positions`, `orders`, `scores` (Bot B), `events`, `pnl_snapshots`
- Daily encrypted backup to Backblaze B2 (`restic` or `rclone crypt`)
- Postgres migration deferred — SQLite handles this volume fine; migrating is a week's work for zero current benefit

**5. Position tracker + PnL** (`core/portfolio.py`) — 1 day
- Reconciles on every fill: updates `positions`, writes `pnl_snapshots` row
- Unrealised PnL uses current best-bid as mark (conservative)
- Exposes `get_bot_bankroll(bot_id)`, `get_open_exposure(bot_id)`, `get_realised_pnl(bot_id, since)` — each bot consumes these, doesn't track on its own
- HMRC-friendly trade log: every buy/sell/redeem with timestamp, market id, side, size, price, fee paid, USD↔GBP rate at trade time

**6. Kill-switch + monitoring** (`core/watchdog.py`) — 0.5 days
- Runs every 60s
- Checks: drawdown limits per bot, aggregate exposure, scraper liveness, scorer liveness, oracle-dispute hits
- On trigger: cancel all orders via CLOB `cancel-all`, halt entries (flag in SQLite), send Telegram alert with reason
- Manual unhalt via Telegram command (authenticated by chat-id allowlist)

**7. Telegram alerting** (`core/notify.py`) — 0.25 days
- Entry, fill, exit, resolution, kill-switch trigger, daily PnL summary
- Chat-id allowlist; no public bot

**8. Backtest harness** (`core/backtest.py`) — 0.75 days
- Replay mode: feeds historical `books` snapshots to a bot's decision function, simulates fills at book price, computes theoretical PnL
- For Bot A: deterministic — replay + rule = exact paper trades
- For Bot B: feeds historical `scores` snapshots to the sizer + executor; re-scoring via the external API is expensive if not cached (order-of-magnitude ~$2 per 30 simulated days). Cache scores.
- Not a fancy vectorbt-style harness. Just enough to sanity-check the filters aren't garbage.

**9. VPN + network posture** (`infra/vpn/`) — 0.25 days
- WireGuard VPN on the homelab hypervisor node, split-tunnelled: only CLOB + Gamma + UMA subgraph go through VPN, everything else direct
- Kill-switch: if VPN drops, `iptables` rules block CLOB egress until VPN reconnects
- Exit node: Europe (Stockholm or Amsterdam), NOT UK

**Total shared infra**: 6 working days + 0.25 for VPN = **~6.25 days**.

---

## Section 7 — Build order

Assumes 4-week rotation home window, starting rotation week 1 = calendar week 1 below. **Verify rotation schedule in §9.**

### Week 1 — Shared infrastructure (rotation home)
- Mon-Tue: keystore + CLOB wrapper. Test against Amoy testnet (chainId 80002).
- Wed: Ingestion scraper + book snapshotter.
- Thu: Storage + migrations + position tracker.
- Fri: Kill-switch + Telegram + VPN setup.
- Weekend: Backtest harness skeleton; shared infra shakedown with a live dry-run order ($5, cancelled).

**End-of-week gate**: one successful $5 Amoy testnet order placed and cancelled; one successful $5 mainnet limit order placed at a deliberately unfillable price and cancelled; encrypted keystore unlocks cleanly on boot; Telegram alert fires end-to-end on drawdown simulation; VPN kill-switch verified.

### Week 2 — Bot A MVP (rotation home)
- Mon: Bot A filter + candidate universe. Test against real Gamma data.
- Tue: Bot A sizer + order builder. No live orders yet.
- Wed: Bot A paper-trading mode. Entry logic against live book snapshots; simulated fills at touch.
- Thu: Bot A exit + resolution redemption logic (paper).
- Fri: End-to-end paper trade cycle. Start the 30-day paper clock.
- Weekend: Observability dashboard (basic Streamlit template).

**End-of-week gate**: Bot A paper-trading, logging fills, alerting on entries.

### Week 3 — Bot B MVP (rotation home)
- Mon: Scraper in-repo (with the `claude_pick` persistence fix).
- Tue: External scorer client wiring. Smoke-test score fields against known fixtures.
- Wed: Bot B filter + Kelly sizer + DR-penalty.
- Thu: Bot B paper-trading mode end-to-end.
- Fri: 30-day paper clock starts. Manual code review of A and B.
- Weekend: Rotation packing.

**End-of-week gate**: Bot B paper-trading with a re-scored, fresh `open_markets` table.

### Weeks 4–7 — At-sea paper-trade observation window
- Bots run unattended on the homelab hypervisor.
- Telegram digest twice daily (08:00 / 20:00 UTC) even without events, so silence ≠ failure.
- User reviews digests when satellite internet permits.
- If either bot crashes hard: auto-restart via systemd; if it crashes 3× in a rolling 24h, halt + alert.
- If either bot hits a drawdown kill: halt + alert; resumes require human unhalt.

**Week 7 end gate**: 30-day paper window complete for Bot A; review data.

### Week 8 — Rotation home, Bot A live graduation
- Mon: Review Bot A paper data against §5 graduation criteria.
- Tue: Manual dry-run ($5 mainnet, place + cancel).
- Wed: Bot A live with £250.
- Thu–Sun: Observe. Ready to kill immediately on any unexplained event.

**End-of-week gate**: Bot A live or explicitly killed.

### Week 9 — Rotation home, Bot B live graduation
- Mon: Review Bot B paper data.
- Tue: Manual dry-run.
- Wed: Bot B live with £250 (subject to Bot A not already being in drawdown).
- Thu–Sun: Observe.

**End-of-week gate**: Bot B live or explicitly killed.

### Weeks 10–11 — At-sea live observation
- Both bots live with £250 each.
- Same digest + auto-restart pattern as weeks 4–7.
- Watchdog tightened: any single-day drawdown >5% halts the offending bot.

### Week 12 — Rotation home, A/B checkpoint
- Review both bots against kill/scale/stalemate rules.
- Scale survivors to £500 if earned.
- Kill non-performers.

### Weeks 13–15 — At-sea
- Survivors run at £500.

### Week 16 — Hard decision
- Scale to £1,000 any bot that meets double-down criteria.
- Return any bot in stalemate to reconsideration.
- Terminate project if neither bot is net-profitable.

**Total elapsed time**: 16 weeks (4 rotations). Real at-keyboard time: ~3 weeks across rotation weeks 1, 2, 3, 8, 9, 12, 16.

---

## Section 8 — Risks I'm accepting

Explicit list of risks **this plan does not mitigate** and why that's the right call right now:

1. **UMA oracle tail risk on Bot B.** A DVM P4 or adversarial vote can zero a position. Mitigated by `dispute_risk ≤ 0.25` filter and position caps, not eliminated. Accepted because the risk is bounded (max 4% of Bot B bankroll per hit = £40 at £1,000 allocation). Unacceptable if: a single market accumulates more than 4% exposure via re-scoring after entry — add a hard per-market notional cap independent of re-sizing.

2. **Polymarket ToS/policy change risk.** UK is already blocked; if Polymarket adds on-chain geo-checking, wallet-level KYC, or cancels open positions from flagged geos, the bot halts with positions stranded. Accepted because no technical mitigation exists short of running via a non-UK proxy entity, which is a full separate legal project. Mitigation via §6 VPN makes the network-level posture consistent; legal posture is via tax+ToS gates in §9.

3. **USDC.e depeg.** Polymarket collateral is USDC.e (bridged); a depeg would reduce notional bankroll. Unmitigated because diversifying collateral isn't an option on Polymarket. Accepted because USDC.e has been stable through two Polygon bridge stress events and the risk is low-probability. Unacceptable if: USDC.e deviates >1% from USD for >2 hours. Kill-switch condition added to watchdog.

4. **Polygon outage.** Block production halts; orders can't settle; positions stuck. Mitigated only by the short-horizon nature of outages (typically <4 hours historically). Accepted — no viable mitigation for a solo operator.

5. **Single-wallet custody.** Hot wallet holds up to $2k. If key is compromised, up to $2k is lost. Mitigated by: encrypted keystore, treasury separation, cap on hot-wallet exposure. Accepted because the alternative (multi-sig + signing relayer) is a 3-week infra project for a diminishing return on this scale.

6. **External scorer availability / cost / drift.** Bot B depends on an externally calibrated dispute-risk scorer (see https://oraclemangle.com) that can be rate-limited, changed, or price-hiked. Mitigation: cache scores, stale-score halt, and a documented fallback path if the service is unavailable. Accepted because scoring cost ($20–50/month order of magnitude) is small vs expected PnL. Unacceptable if: the scorer becomes unavailable with no equivalent replacement.

7. **offshore-rotation operational risk.** 4 weeks where the user cannot intervene in <24h if something goes wrong. Mitigated by: kill-switches fail-closed, drawdown halts, scraper-liveness halts, systemd auto-restart limits (3 crashes halts the bot), Telegram digests twice daily. Accepted because the alternative — only running the bot home-rotation — cuts live time by 50% and destroys the thesis's statistical power.

8. **External scorer drift or service breakage.** Bot B consumes an external scorer rather than owning the model. Calibration drift or outages pass through to entries. Mitigated by: stale-score halt, calibration halt (§3), and smoke fixtures on the score-field contract before going live. Accepted because re-implementing a calibrated scorer is out of scope for this bot.

9. **HMRC late-opinion.** Advisor opinion returns after live money is deployed and says the tax treatment is worse than CGT-on-disposal (e.g., trade income + NI). Mitigated by: logging every trade HMRC-ready from day 1. Accepted because the opinion is in flight; if it comes back adverse, we pause, re-sizer, or shutter — not destroy the opportunity waiting for it.

Risks NOT listed: front-running (no public mempool exposure for signed CLOB orders), MEV (CLOB is off-chain match), sandwich attacks (N/A for prediction markets).

---

## Section 9 — What I need from you before I build

Three items. Reply "ack, 1/2/3 as specified or corrected" and I start the Week-1 build.

1. **Confirm or correct bankroll**: working assumption is £5,000 total / £1,000 per bot at full scaling / £250 per bot at live graduation / £2,000 max aggregate live exposure. Max drawdown kill at 15% per bot, 20% aggregate.
2. **Confirm tax + ToS posture**: working assumption is (c)/(c) — build + advise in parallel; capped-exposure compromise; VPN via the homelab hypervisor; HMRC-ready logging from day 1. If you want (a)/(a) or (b)/(b), say so and timeline shifts accordingly.
3. **Confirm rotation pattern and week-1 start date**: working assumption is 4-on/4-off, Week 1 starting the next home rotation. Give me a start date or correct the pattern.

That's it. Everything else is decided in §1–§8.

---

*End of architecture decision. Changes to any of §1–§8 require a new decision session, not in-line edits.*
