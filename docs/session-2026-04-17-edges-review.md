# Session 2026-04-17 Evening — Polymarket Edges Deep Review + Bot B / Bot E Plans

**Status:** Discussion captured. Action gates defined. No code shipped.
**Purpose:** Persistent record so a cold-start session can re-enter at the Bot E POC gate without re-deriving context.
**Entry point for next session:** §5 (Revised Bot E POC gate).

---

## Table of contents

1. Fleet baseline at session start
2. External input — `polymarket_edges.md` method-by-method analysis
3. Implementation plans drafted (Bot B ensemble, Bot E vol-harvest, exec-policy, crowd hybrids)
4. Critical review of the Bot E proposal — three blocking issues
5. Revised Bot E gate — 1-day POC on recorder data before any build
6. ADRs to draft and open questions added
7. Updated 30-day roadmap

---

## 1. Fleet baseline at session start (2026-04-17, post-Session 17g)

All deployments on the bot LXC container. Paper-only fleet pivot Session 17f.

| Bot | Thesis | Status | Kill date |
|---|---|---|---|
| A | Tail-fade NO ≤ 5¢ on UMA geopolitics/politics/econ/finance | Paper active; $30/trade fixed | — |
| B | Directional Kelly on external dispute-risk scorer dislocation (Oraclemangle — https://oraclemangle.com) | HALTED pending scorer rebuild (P0) | — |
| C | Pyth directional; thesis undefined | Paper; $10/trade; OQ-031 open | 2026-05-31 |
| D | Weather tail-fade (ECMWF + METAR) | Paper; entries halted; $5k bankroll for headroom | 2026-05-31 |
| E | OBI micro-scalp on 15-min crypto binaries (FAILED — WR 0.500 vs predicted) | Trader gated; Recorder active and capturing (462 MB) | 2026-06-30 |
| F | Wallet-flow sensor (Hunter + Mirror) | Live; Phase 2 Trigger cancelled 2026-04-17 (ecosystem crowded, 90s freshness cutoff) | — |

**Shared infra present:** Polymarket WSS (`core/polymarket_ws.py`), Binance CEX WSS (`core/cex_ws.py`), atomic fleet cap (`core/fleet.py`), keystore (`core/keystore.py` + age-encrypted file), watchdog (`core/watchdog.py`), notify daemon (`core/notify.py`), dashboard (`dashboard/`), backtest harness (`core/backtest.py` + per-bot variants — Bot E variant hardened for crossing-the-spread simulation).

**Shared infra absent:** no arbitrage module, no market-making module, no cross-venue feed (Vegas / Pinnacle / Betfair / Kalshi).

---

## 2. External input — `polymarket_edges.md` method-by-method analysis

Curated list of 9 trading-edge methods with math and implementation notes was analyzed against the fleet. Summary table of verdicts below; full per-method notes captured in the session transcript and recaptured here only where action-bearing.

| # | Method (source title) | Net verdict | Incremental fleet alpha | Effort | Notes |
|---|---|---|---|---|---|
| 1.1 | Negative-Risk / YES+NO<$1 arbitrage | Data-only scan; **do not build execution** | Low (gates future decisions) | 1 day | Binary arb dead at retail latency. NegRisk multi-outcome has residual windows; measure first |
| 1.2 | Pair-cost "Gabagool-style" rebalancing on short-expiry crypto | Candidate Bot E pivot → **now gated on POC per §5** | Medium-high IF viable; unknown until POC | 2–3 wk post-POC | Reviewer critique collapsed the thesis; see §4 |
| 2.1 | Passive limit-order execution | **Already done; upgrade to dynamic ladder + toxicity filter** | Medium (fleet-wide compounding) | 1 wk | Polymarket has NO maker rebate under V2 fee structure — source doc wrong on this |
| 3.1 | Probability dislocation + EV + Kelly sizing | **= Bot B design; not a new method** | Zero new — Bot B scorer rebuild is the work | 3 wk (= §3.1 below) | Quarter-Kelly + p-clip + depth cap already in `bots/bot_b/sizer.py` |
| 3.2 | Sharp-line lag (Vegas / Pinnacle / Betfair vs Polymarket) | Real edge; new bot (G); park until post-B reactivation | Medium if pursued | 2–3 wk after B unhalted | UK operator has Betfair Exchange licensed access; Pinnacle TOS-grey |
| 3.3 | Short-term TA indicators on 5/15-min binaries | **Skip.** Bot E's OBI failure is prior evidence TA won't clear fees | Likely negative | 0 | Commodified, overfitting-prone |
| 4.1 | Adaptive multi-strategy bot | **= current fleet architecture** | Zero — already there | N/A | Formalize monthly cap-reallocation review only |
| 4.2 | Liquidity provision / market-making | **Skip.** Polymarket has no rebate; adverse-selection eats retail | Negative | N/A | Pro MMs with sub-10ms infra dominate |
| 5.1 | Multi-estimator probability averaging (ensemble) | **HIGHEST incremental alpha — reframes Bot B scorer rebuild as ensemble, rehabilitates Bot F as estimator supplier** | High | 3 wk | See §3.1 below |

**Top 3 highest-leverage combinations identified:**

1. Bot B ensemble scorer + Bot F estimator rehabilitation (method 5.1 + §4.1 below).
2. Bot E pivot to spread-capture (method 1.2, reframed after review — see §5).
3. Dynamic limit-ladder + toxicity filter (method 2.1 upgrade) fleet-wide.

**Redundant with existing fleet:** methods 3.1, 4.1, and passive-limit baseline of 2.1.
**Declined:** methods 3.3, 4.2, and 1.1-execution (NegRisk scan data-only is OK).

---

## 3. Implementation plans drafted

### 3.1 Bot B — ensemble scorer rebuild (method 5.1)

**Scope:** replaces the single HTTP call to an externally calibrated dispute-risk scorer (Oraclemangle — https://oraclemangle.com; currently in `bots/bot_b/http_scorer.py`) with a multi-estimator ensemble. Kelly sizer, depth caps, filters, unhalt doc all preserved. The external product's model, corpus, and performance figures are proprietary and not restated here.

**File structure (`bots/bot_b/scorer/`):**

```
scorer/
├── base.py                       # Estimator Protocol + dataclasses + EstimatorAbstainError
├── ensemble.py                   # EnsembleScorer orchestrator
├── weights.py                    # WeightTracker — rolling 30-day Brier → normalized weights (floor 0.05)
├── calibration.py                # IdentityCalibrator | PlattCalibrator | IsotonicCalibrator
├── validation.py                 # no-lookahead held-out harness
└── estimators/
    ├── historical_baserate.py    # E1 — non-LLM base-rate by (category × price-bucket × DTR)
    ├── external_scorer_prior.py  # E2 — existing http_scorer refactored to Estimator interface (cites https://oraclemangle.com)
    ├── sentiment_local.py        # E3 — local-qwen35 news scan (privacy-safe)
    └── wallet_flow.py            # E4 — Bot F Mirror data as probability estimator (not timing signal)
```

**Key design decisions (captured inline so the file is self-describing):**

- `Estimator` is a `Protocol`, not an ABC. Supports mocking and matches Bot B's existing patterns.
- `EstimatorAbstainError` is first-class — estimators without a view raise rather than returning 0.5 with low confidence. 0.5 is a real prediction.
- Variance gate on the ensemble: if weighted std across estimators exceeds $\sqrt{0.03} \approx 0.17$, ensemble abstains from that market — independent estimator disagreement is a red flag.
- Calibration applied **once at the ensemble output**, not per-estimator. Platt residual monitored; switch to isotonic only if Platt MAE > 0.02 on holdout.
- Weight floor at 0.05 — one temporarily-poor estimator cannot be zeroed out (it can recover).
- Exception isolation — one estimator crash must not halt Bot B (previous single-scorer was the crash point).

**Math — weight update:**

$$w_i = \frac{1/\text{Brier}_i^2}{\sum_j 1/\text{Brier}_j^2}, \quad w_i \leftarrow \max(w_i, 0.05), \text{ then renormalize.}$$

**Config keys (add to `bots/bot_b/config.py`):**

```
BOT_B_ENSEMBLE_ENABLED (default True)
BOT_B_ENSEMBLE_MIN_ACTIVE (default 2)
BOT_B_ENSEMBLE_MAX_VARIANCE (default 0.03)
BOT_B_ENSEMBLE_MIN_CONFIDENCE (default 0.5)
BOT_B_ENSEMBLE_CALIBRATOR ("identity" | "platt" | "isotonic"; default "identity" until 50+ resolutions)
BOT_B_ENSEMBLE_WEIGHT_WINDOW_DAYS (default 30)
BOT_B_ENSEMBLE_WEIGHT_FLOOR (default 0.05)
BOT_B_EST_HISTORICAL_ENABLED (default True)
BOT_B_EST_EXTERNAL_SCORER_ENABLED (default True)  # E2: external dispute-risk scorer (https://oraclemangle.com)
BOT_B_EST_SENTIMENT_ENABLED (default False — bootstrap off)
BOT_B_EST_WALLETFLOW_ENABLED (default False — bootstrap off)
```

**Risk guardrails:**

1. Per-estimator kill-switch via env — operator yanks a bad estimator without redeploy.
2. Minimum 2 active estimators for any Kelly bet.
3. Variance gate abstains on disagreement.
4. Weight floor prevents single-estimator dominance.
5. Watchdog check: `ensemble_abstain_rate_24h > 95%` triggers halt (all estimators broken).
6. Daily prediction logging to `scorer_predictions` table; weekly Brier batch job reconciles against resolutions.
7. Quarter-Kelly unchanged. Ensemble improves probability input; does not license raising fraction.
8. Cold-start: until 50 resolved ensemble predictions, `IdentityCalibrator` + `MIN_ACTIVE = 3`.

**Unhalt gates (additive to existing doc at `docs/bot-b-scorer-rebuild-plan.md`):**

- Brier ≤ 0.12 on held-out **2026** UMA resolutions (out-of-training-distribution).
- Per-estimator Brier ≤ 0.18 on same holdout OR deweighted to ≤ 0.05.
- Variance gate rejects ≥ 15% of candidates (sanity — 0% means gate is broken).
- Platt calibrator residual MAE < 0.02.

**3-week delivery plan:**

| Week | Deliverables |
|---|---|
| 1 | `base.py`, `ensemble.py`, `weights.py`, `calibration.py`; E1 (historical base-rate); tests green |
| 2 | E2 refactor (external scorer prior); E4 (wallet-flow); validation harness; first holdout run |
| 3 | E3 (local-qwen35 sentiment); Platt calibrator fit; watchdog integration; ADR-029 |

---

### 3.2 Bot E pivot to spread-capture (method 1.2)

**Status: superseded by §5 after critical review. See §4 for why and §5 for the revised gate.**

Original (pre-review) spec had three blocking flaws:

1. Vol-harvest framing mathematically incoherent (Bernoulli variance ≠ diffusion vol).
2. Sizing formula created a directional NO bet, not a direction-free pair.
3. Fill-rate asymmetry on binaries (losers fill, winners don't) structurally favours pro MMs with sub-10ms infra — likely under-modeled in backtest.

Do not implement pre-review spec. Go via §5 POC.

---

### 3.3 Dynamic limit-ladder + toxicity filter (method 2.1 upgrade)

**Scope:** fleet-wide execution wrapper. Every bot placing limits benefits. Strategy logic unchanged.

**Module:** `core/exec_policy.py` with two primitives:

**Toxicity filter** — "is top-of-book informed right now?":

$$\text{toxicity}(\text{side}) = \frac{\text{aggressive flow against our side}_{\Delta t}}{\text{total aggressive flow}_{\Delta t} + \epsilon}$$

Thresholds (priors to tune): `toxicity_place_block = 0.80` (skip placement), `toxicity_freeze = 0.70` (hold existing limit, don't step).

**Limit ladder state machine:**

```
PLACED ── age > T1 ── STEP_1 ── age > T2 ── STEP_2 ── age > T3 ── CANCEL
  ├── book moved against us (|delta| > k·ATR) ─→ CANCEL
  └── toxicity flipped high ─→ FREEZE
```

**Per-bot tuning priors:**

| Bot | T1 (step 1) | T2 (step 2) | T3 (cancel) | Rationale |
|---|---|---|---|---|
| A | 300 s | 900 s | 3600 s | Tail markets move slowly |
| B (post-unhalt) | 300 s | 900 s | 1800 s | Directional signal stales |
| C | 120 s | 360 s | 600 s | Short-window signal ephemeral |
| D | 600 s | 1800 s | 7200 s | Weather signal ages over hours |
| E (if revived) | 30 s | 120 s | 300 s | 15-min windows require tight refresh |

**Risk guardrails:**

1. Max 2 ladder steps before cancel — prevents runaway chasing.
2. Cancel-storm breaker: > 30 cancels in 5 min per bot triggers watchdog halt.
3. Toxicity-freeze audit: > 50% frozen over 1h → operator notify; market is hostile.
4. Default off (`EXEC_POLICY_ENABLED=false`); enable per-bot one at a time.

**Rollout sequence:**

1. Module + tests with all flags false.
2. Enable on Bot A paper for 7 days; measure fill-rate delta and cost-basis delta.
3. If cost-basis ≥ +20 bps, roll to B (post-unhalt), C, D, E.
4. ADR-031: fleet-wide adoption.

**Tests (`tests/core/test_exec_policy.py`):** toxicity blocks placement, freeze overrides stepping, book-move cancels, ladder progression, cancel-storm breaker, per-bot config respect.

---

### 3.4 Contrarian bot-flood hybrids

#### 3.4.1 Short-term herding fade (Bot F resurrection as **estimator**, not trader)

Bot F Phase 2 Trigger was cancelled because local signals exceeded 90s freshness cutoff for *execution timing*. But for **probability priors** (not timing), 90s-stale data is fine.

**New table:** `crowd_signals` (daily cron via `bots/bot_f/crowd_signals.py::detect_cascades`):

Columns: `market_id`, `cascade_start_ts`, `n_wallets`, `dominant_side`, `gross_usd`, `price_move_bps`.

**Consumers:**

1. Bot B estimator E4 (`wallet_flow.py`) — maps cascade net ratio to probability prior in $[0.2, 0.8]$.
2. Bot A/D entry filter — if same-direction cascade within 6 h, halve size or skip (avoid front-run-fade trap).
3. (Optional mini bot "G-fade") — counter-trade bot-dominated overshoots, 60–180 min hold, $20/position cap. Deferred.

**Risk guardrails:** cascade wallets must pass Bot F Hunter classifier (bots only, not humans). Per-bot cap at 10% daily deployed capital on cascade-driven trades. G-fade kill-switch at WR < 45% over 30 trades.

#### 3.4.2 Reward-pool cascade detection (execution-layer edge)

Polymarket liquidity-rewards epochs drive predictable LP rush-in (spread compression) / rush-out (spread widening) dynamics.

**New module:** `core/rewards_monitor.py`, polls Polymarket rewards endpoint every 10 min. TOS-grey — see OQ-036.

**Consumers:**

1. Bot A filter — reject if market in active rewards (Bot A edge is in *unsubsidized* tails).
2. `core/exec_policy.py` — when `seconds_to_epoch_end < 600`, switch to faster-step ladder (LPs pulling, cheaper passive fills incoming).
3. Bot E (if revived post-POC) — exclude in-rewards markets from vol-harvest (LP noise contaminates realized-vol proxy).

**Deliberate non-use:** we do not become an LP ourselves. Method 4.2 declined.

---

## 4. Critical review of Bot E proposal — three blocking issues

Reviewer critique landed after the §3.2 draft. I agree with all three major items plus the smaller concerns. Documented here so a future session sees the full argument, not just the revision.

### 4.1 Problem 1 — Vol-harvest framing mathematically incoherent

**Reviewer claim:** the proxy `iv_bps = 2·sqrt(P(1-P)) * 1e4 / sqrt(T)` has no valid option-theoretic derivation. `sqrt(P(1-P))` is the SD of the Bernoulli *terminal outcome*, not the diffusion vol of the binary price path.

**My audit after the critique:** correct on two counts.
- Factor of 2 is spurious — Bernoulli SD peaks at 0.5, not 1.0.
- The option-theoretic path vol of a binary on $S_T > K$ is $\sigma_P \propto \varphi(d_2)/\sqrt{T-t}$, which requires knowing $\sigma_{\text{BTC}}$ — the very input we'd be comparing against. The ratio collapses to self-reference.

**Fix:** strip vol-harvest framing entirely. Call the strategy *passive pair-accumulation against spread-capture opportunities*. Replace RV/IV ratio gate with a direct threshold: skip if $P_Y^{\text{bid}} + P_N^{\text{bid}} \ge 0.97$. Tune threshold on recorder data without vol-ratio pretense.

### 4.2 Problem 2 — Sizing formula created directional exposure

**Reviewer trace:** with $P_Y = 0.70$, $P_N = 0.30$, budget $\$2$, my pseudocode produced `size_yes = $0.60` (0.857 shares) and `size_no = $1.40` (4.67 shares) — net P&L $-\$1.14$ if YES wins, $+\$2.67$ if NO wins. That's a directional NO bet, not a hedge.

**My audit:** direct bug. For a hedged equal-share pair:

$$n_Y = n_N = s = \frac{\text{budget}}{P_Y + P_N}, \quad \text{cost}_Y = s \cdot P_Y, \quad \text{cost}_N = s \cdot P_N$$

So `size_yes / budget = yes_px / (yes_px + no_px)` — exactly inverted from what I wrote. The `Inventory.pair_cost` property in the spec hinted I had the model correct in my head; the rebalance controller didn't match. Survives synthetic symmetric unit tests at $P_Y = P_N = 0.50$, breaks at asymmetric prices. Classic latent-bug pattern.

**Fix:** rewrite sizing to equal-share allocation:

```python
shares = budget / (yes_px + no_px)
size_yes = shares * yes_px
size_no = shares * no_px
```

### 4.3 Problem 3 — Fill-rate asymmetry fatal on binary markets

**Reviewer claim:** passive bids fill against taker flow. Taker flow on binaries is asymmetric — losers exit (sell aggression), winners hold (no sell flow). So BUY_YES at bid fills when YES is losing, doesn't fill when YES is winning. Result: long-the-loser inventory → directional loss. Pro MMs with sub-10ms infra compete for the thin winning-side fills; the bot LXC container via WireGuard (~500 ms) cannot.

**Reviewer's critical question:** does `core/backtest_bot_e.py` separate winner-side from loser-side passive fill rates? If it uses a uniform fill-rate calibrated from the full tape, the backtest will systematically overstate net P&L because the tape averages the asymmetry out.

**My audit:** I do not know whether the simulator separates them. The prior sitrep surfaced a single-number fill rate ("53.2% → 50.0% after crossing-the-spread"). Needs verification. Logged as **OQ-037**.

**Nuance I'd add (my push-back on the "fatal" framing):** asymmetry worsens monotonically through the window. Mins 0–5 with $P \approx 0.50$, outcome is genuinely uncertain and fills are roughly symmetric. Mins 10–15 with $P \approx 0.95$, asymmetry is extreme. A strategy that activates only in the **first 5 minutes** of each window and hard-exits at min 5 may preserve edge. Narrower universe, not necessarily dead.

### 4.4 Smaller concerns (all agreed)

- `mid_distance_cap = 0.20` narrows universe; combined with mins-0–5-only constraint, need to count viable windows empirically.
- 50 bps/window target is optimistic. Realistic net after fills + fees + adverse selection is 5–15 bps. Lower pass threshold to 5 bps.
- Bot F coupling ("cascades depress vol") is a weak prior; premature optimization. Strip from v1; prove core first.
- Cancel / refresh cadence was a material omission. Need explicit policy: cancel-and-replace on mid move ≥ 1 tick, heartbeat refresh every 10s, max 30 replacements per window.

### 4.5 My net assessment

Reviewer is substantively correct on all three major points plus the smaller items. The critique saves either two weeks of building on a shaky foundation or a full 2026-06-30 cycle on a broken strategy.

Bot E pivot is NOT dead — but the gate is no longer "write the backtest harness." The gate is a 1-day POC on the recorder data answering three questions before any new code lands under `bots/bot_e_btc_scalp/`.

---

## 5. Revised Bot E gate — 1-day POC on recorder data

### 5.1 POC question tree

Run against `data/bot_e_recorder.db`, Q1 2026 window. 1 day of work, no new code in `bots/bot_e_btc_scalp/`.

**Q1 (universe size):** count 15-min BTC/ETH/SOL Up/Down windows where $P_Y^{\text{bid}} + P_N^{\text{bid}} < 0.97$ held for at least 60 consecutive seconds.

**Q2 (lifecycle positioning):** for qualifying windows, split sub-threshold time into:
- $T_{\text{early}}$ = seconds in minutes 0–5 of the window
- $T_{\text{late}}$ = seconds in minutes 10–15

**Q3 (fill asymmetry):** from the recorder tape, compute:
- $r_{\text{win}}$ = P(our hypothetical passive BUY at bid fills | our side ultimately wins that window)
- $r_{\text{lose}}$ = P(our hypothetical passive BUY at bid fills | our side ultimately loses)

Measured by replaying every bid-level event against subsequent trade tape. Separate by window third (mins 0–5, 5–10, 10–15).

### 5.2 Decision matrix

| Q1 | Q2 | Q3 | Action |
|---|---|---|---|
| < 500 windows | — | — | **Archive Bot E now.** No addressable universe |
| ≥ 500 | $T_{\text{early}} < 30\%$ of $T_{\text{total}}$ | — | **Archive.** Strategy mostly in adverse-selection zone |
| ≥ 500 | $T_{\text{early}} \ge 30\%$ | $r_{\text{lose}}/r_{\text{win}} > 1.5$ (monotonic) | **Archive.** Fill asymmetry fatal |
| ≥ 500 | $T_{\text{early}} \ge 30\%$ | $r_{\text{lose}}/r_{\text{win}} \le 1.5$ | **Proceed to revised full backtest** (§5.3) |

POC deliverable: `docs/bot-e-poc-results.md` — 2 pages, three numbers, go/no-go.

### 5.3 Revised full backtest spec (only if POC passes)

1. **Rename:** "passive pair-accumulation on binary-market spread-capture." Delete vol-harvest references.
2. **Sizing:** equal-share pair. `shares = budget / (yes_px + no_px); cost_yes = shares * yes_px; cost_no = shares * no_px`.
3. **Lifecycle window:** mins 0–5 only. Hard cancel-all at $t = 5$ min. Freeze inventory until market close.
4. **Entry gate:** `yes_bid + no_bid < 0.97` (tune on train, validate on holdout, do NOT sweep ratio thresholds on tiny samples).
5. **Refresh policy:** cancel-and-replace on any mid move ≥ 1 tick; heartbeat refresh every 10 s; cap 30 replacements per window.
6. **Backtest reporting (critical per reviewer):**
   - Pair P&L (both legs filled)
   - Orphan-leg P&L (one side only) — this IS the real test
   - Winner-side passive fill rate (per window third)
   - Loser-side passive fill rate (per window third)
   - P&L by asset (BTC / ETH / SOL) — detect concentration
7. **Pass thresholds (revised, lower):**
   - $n \ge 500$ windows with at least one fill
   - Mean net P&L $\ge +5$ bps per window (was +50)
   - Sharpe $\ge 0.7$ (was 1.0)
   - Orphan-leg P&L / pair P&L $\le 25\%$
   - Max drawdown $\le 25\%$ of deployed per-window capital
   - No single asset $\ge 70\%$ of total P&L
8. **Drop Bot F coupling.** Add only if core passes holdout.
9. **OQ-037 must be resolved before backtest trusted:** verify `core/backtest_bot_e.py` models winner-vs-loser fill rate separately, not as a single scalar. If it doesn't, fix first.

### 5.4 Train / holdout / kill alignment

- Train: earliest 60% of recorder windows.
- Holdout: most recent 40%, untouched during tuning.
- Kill alignment: if POC fails, archive by kill date 2026-06-30. If POC passes but full backtest fails holdout, archive. No second pivot.

---

## 6. ADRs to draft and open questions added

### ADRs (to land in `docs/decisions-log.md`)

- **ADR-029** — Bot B Ensemble Scorer Rebuild. Supersedes implicit single-scorer design. Per §3.1.
- **ADR-030** — Bot E Pivot — gated on POC (REVISED from pre-review spec). Supersedes ADR-022 thesis. Per §5.
- **ADR-031** — Fleet-Wide Exec-Policy (limit ladder + toxicity filter). Per §3.3.
- **ADR-032** — Bot F Rehabilitation as Estimator Supplier + Crowd Signal Table. Supersedes Phase 2 Trigger cancellation. Per §3.4.1.

### Open questions added (to `docs/open-questions.md`)

- **OQ-033** — Does E3 (local-qwen35 sentiment) share enough bias with E2 (external dispute-risk scorer prior; https://oraclemangle.com) to violate ensemble independence? Check pairwise correlation on holdout before enabling E3.
- **OQ-034** — `bot_e_recorder.db` timestamp alignment precision: is Binance WSS lag captured accurately enough to trust realized-vol calculations? Confirm before vol-harvest backtest.
- **OQ-035** — Exec-policy toxicity thresholds (0.70 freeze, 0.80 block) are priors from sports-betting literature. Tune on Bot A paper for 2 weeks before fleet rollout.
- **OQ-036** — Polymarket rewards-endpoint scraping TOS status. Is there a public API, or does this require a partnership / accept TOS-grey scraping?
- **OQ-037** — Does `core/backtest_bot_e.py` separate winner-side from loser-side passive fill rates? **Blocking for Bot E revised backtest** per §5.3 item 9.

### Cross-links

- `docs/bot-b-scorer-rebuild-plan.md` — add §2.1 Ensemble Design
- `docs/bot-e-poc-results.md` — NEW, produced by the POC (see §5.1)
- `docs/exec-policy-design.md` — NEW (optional, can live entirely in this doc + ADR-031)
- `docs/crowd-signals-design.md` — NEW (optional)
- `docs/kill-dates.md` — no changes; dates already align

---

## 7. Updated 30-day roadmap

| Day | Deliverable | Owner | Depends on |
|---|---|---|---|
| 1 | Bot E POC query on recorder data (§5.1 Q1–Q3) | Claude | — |
| 1 | POC results memo: `docs/bot-e-poc-results.md` | Claude | POC query |
| 2 | OQ-037 verification in `core/backtest_bot_e.py` | Claude | — (parallel to POC) |
| 2–3 | Exec-policy module `core/exec_policy.py` + tests | Claude | — (parallel) |
| 3–5 | Bot A paper: exec-policy enabled, start 7-day fill-rate measurement | Claude | exec-policy module |
| 3–21 | Bot B ensemble rebuild main track (§3.1 3-week plan) | Claude | — |
| 6–10 | If POC passed: Bot E revised backtest build (§5.3) | Claude | POC pass, OQ-037 fix |
| 10–20 | Bot E revised backtest run + holdout | Claude | backtest build |
| 20–24 | Bot F crowd_signals table + Bot A/D filter integration | Claude | Bot B ensemble E4 (shares data model) |
| 24–26 | Rewards monitor `core/rewards_monitor.py` | Claude | OQ-036 TOS decision |
| 26–28 | ADR-029, 024, 025, 026 drafted in `docs/decisions-log.md` | Claude | all of the above |
| 28–30 | Validation runs; fleet cap reallocation monthly review | the operator + Claude | — |

**Explicitly deferred:**

- Bot G (sports-line lag, method 3.2) — park until B reactivated.
- Bot G-fade mini (method 3.4.1 item 3) — park until crowd_signals table has 30 days of data.
- Full NegRisk-arb execution (method 1.1) — scanner only. Execution requires co-location, which conflicts with UK VPN posture.

**Explicitly declined:**

- Method 3.3 (TA indicators) — Bot E OBI failure is prior evidence.
- Method 4.2 (true market-making) — no rebates on Polymarket V2; adverse selection fatal for retail.

---

## Appendix A — Key math used in this session

### Kelly fraction (quarter-Kelly, Bot B unchanged)

$$f^* = \frac{p_{\text{model}} - P_{\text{market}}}{1 - P_{\text{market}}}, \quad f = 0.25 \cdot f^*$$

### Ensemble weighting (Bot B §3.1)

$$w_i = \frac{1/\text{Brier}_i^2}{\sum_j 1/\text{Brier}_j^2}, \quad w_i \leftarrow \max(w_i, 0.05), \text{ renormalize}$$

### Bernoulli variance vs binary option path vol (Bot E §4.1)

*Bernoulli variance of outcome:* $\text{Var}(X) = P(1-P)$, SD $= \sqrt{P(1-P)}$, peaks at 0.5.

*Diffusion vol of binary option price:* $\sigma_P = \varphi(d_2) / \sqrt{T - t}$ in $P$-units, where $d_2 = [\ln(S/K) + (r - \sigma^2/2)(T-t)] / (\sigma \sqrt{T - t})$.

**These are NOT the same object.** The first is terminal-state dispersion; the second is the instantaneous volatility of the price process. My original proxy conflated them.

### Equal-share pair sizing (Bot E §4.2 fix)

$$\text{shares} = \frac{\text{budget}}{P_Y + P_N}, \quad \text{cost}_Y = \text{shares} \cdot P_Y, \quad \text{cost}_N = \text{shares} \cdot P_N$$

### Toxicity filter (exec-policy §3.3)

$$\text{toxicity}(\text{side}) = \frac{\text{aggressive flow against us}_{\Delta t}}{\text{total aggressive flow}_{\Delta t} + \epsilon}$$

---

## Appendix B — Files NOT to touch without review

Per the CLAUDE.md decision-authority matrix, do not modify without explicit operator approval:

- The external scorer product (Oraclemangle — https://oraclemangle.com) — closed product, out of scope; cite only, never ship or describe its internals.
- `core/keystore.py` + keystore age file — security critical.
- `core/fleet.py` atomic cap semantics — Session 17f fix.
- Any production `.env` on the bot LXC container — env secrets.

---

## Appendix C — How to re-enter this context in a new session

1. Read this file top-to-bottom (30 min).
2. Read `docs/bot-e-peer-review.md` (prior reviewer context).
3. Check `data/bot_e_calibration.json` `ready` status.
4. Check whether `docs/bot-e-poc-results.md` exists — if yes, POC already run.
5. Check `docs/bot-b-scorer-rebuild-plan.md` for latest ensemble design state.
6. Confirm Bot B halt status via `core/watchdog.py` status query.
7. Pick the earliest unblocked item from §7 roadmap and proceed.

---

## 2026-04-17 late addendum — cross-check against `contrarian_edges.md`

Added after a separate `contrarian_edges.md` review (5-method contrarian playbook) was cross-referenced against this session doc. ~80% overlap; the 5 contrarian methods map 1-to-1 onto items already specified above. Three genuinely additive items landed; documented here so the day-1 roadmap does not drift.

### A.1 Method-to-session mapping

| `contrarian_edges.md` method | Session-doc equivalent | Action |
|---|---|---|
| 1 — TA-herding fade | 3.3 (TA indicators) | **Skip as standalone.** Fold a 1-query reversion check into Bot E POC (OQ-038) |
| 2 — Reward-pool cascade fade | §3.4.2 `rewards_monitor.py` | **Insert 14-day passive measurement gate** before code (OQ-039) |
| 3 — Long-horizon fundamental | 3.1 = Bot B | Already planned — session §3.1 ensemble rebuild |
| 4 — Bot-flow meta-copy fade | §3.4.1 Bot F rehabilitation | Already planned — estimator-supplier role |
| 5 — Cross-horizon lag | — (session covers cross-venue 3.2, not cross-horizon) | **Deferred research spike** 1 day, gated on Bot C survival past 2026-05-31 |

### A.2 Code shipped in this addendum

**Bot B sizer — optional `category` argument + `CATEGORY_DISPUTE_RATES` config map.** Layered on top of the existing `dr_multiplier` per-market penalty, this is a category-level historical UMA dispute-rate shrinkage:

$$\text{kelly\_size} = B \cdot f_K \cdot \text{Kelly}_{\text{raw}} \cdot m_{\text{dr}}(\text{dr}_{\text{mkt}}) \cdot (1 - r_{\text{cat}})$$

where $r_{\text{cat}} = $ `CATEGORY_DISPUTE_RATES.get(category, 0)`.

- `bots/bot_b/config.py` — `CATEGORY_DISPUTE_RATES: dict[str, Decimal] = {}` (empty default, backward-compatible)
- `bots/bot_b/sizer.py` — new `category_shrinkage()` helper; `size_position(..., category=None)` optional arg
- `bots/bot_b/executor.py` + `shadow_main.py` — pass `candidate.category` through to sizer
- `tests/test_bot_b_sizer.py` — 7 new tests covering None, unknown, populated, clamp, regression equality, empty-map no-op, populated shrinkage (all 20 sizer tests pass; 54 Bot B caller tests pass; 9 security-audit regressions pass)

The map stays empty until the OQ-040 data pipeline populates it from external category-level dispute-rate aggregates (see the externally calibrated dispute-risk scorer at https://oraclemangle.com). Until then behaviour is identical to pre-addendum.

### A.3 Open questions added

- **OQ-038** — Method 1 reversion check folded into Bot E POC (kill-memo target, no new build)
- **OQ-039** — 14-day passive reward-cascade measurement window before `rewards_monitor.py` build
- **OQ-040** — Category-level historical UMA dispute-rate data pipeline (sizer scaffold shipped; data not yet)

### A.4 Roadmap delta

One insertion into §7, no other changes:

| Day | Deliverable | Source |
|---|---|---|
| 1 | Bot E POC — **add Method 1 reversion check sub-query** per OQ-038 | addendum A.1 |
| (after OQ-036 resolves) | 14-day reward-cascade passive measurement — OQ-039 | addendum A.1 |
| 24–26 | `core/rewards_monitor.py` — **gate on OQ-039 measurement passing** in addition to OQ-036 TOS clearance | addendum A.1 |

Nothing in the addendum changes §7's P0 path (Bot B ensemble rebuild, `exec_policy.py`, Bot E POC, OQ-037). It narrows the reward-cascade build gate and buys back a permanent kill-memo for the two contrarian methods that are already redundant with the fleet.
