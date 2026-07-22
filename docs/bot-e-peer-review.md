# Bot E Peer-Review Package

**Reviewers:** External LLMs (Grok, Codex, etc.)
**Prepared by:** Claude session 2026-04-16, polymarket-bot repo
**Review scope:** Bot E strategy direction, v1 scope, and supporting infra decisions
**What I want from you:** Contrarian analysis, missed edges, blind spots, red flags. See "Specific review questions" at the bottom.

---

## Redaction note

This package has been redacted for external review. Real wallet addresses, homelab IPs, container identifiers, and keystore paths have been generalised to `<hot-wallet>`, `<lxc>`, `<path>`, etc. The technical substance is intact. If you need detail that's been redacted to answer a question, flag it and the operator will decide whether to share.

---

## 0. TL;DR

Solo retail operator building four live Polymarket bots (A/B/C/D) plus Bot E (specified, unbuilt) on a private homelab + VPN. Six weeks of intensive work have landed A+B live, C+D paper-trading, and extensive research for E. Five recent X articles have shifted the Bot E strategy picture: the current spec targets a **CEX-vs-Polymarket lag arbitrage in the last 60 seconds of 15-minute BTC markets**, which requires sub-650ms end-to-end latency and a eu-west-1 VPS. Recent evidence strongly suggests that strategy is crowded by HFT competitors and that a second, distinct strategy — **order-book imbalance (OBI) + technicals at t−10min to t−5min** — is viable from the existing homelab with no VPS, based on a working v96 implementation by @Gustafssonkotte (architectural writeup, no P&L claims) and a 223× ROI wallet (@vague-sourdough, public Polymarket profile, $1.8k deposits → $410k) at our capital tier.

Seeking review on: (a) whether that pivot is justified, (b) whether the proposed minimal v1 scope is right, (c) what we've missed.

---

## 1. Project context

### Operator

UK-based solo retail operator. Live capital cap **$2,000 USD (USDC on Polygon)**. Strict risk posture: paper-first, 4-gate graduation to live, per-trade and daily kill-switches non-negotiable but **tunable as defaults, not hard-coded blocks** (captured explicit operator preference — safety controls must never stand between evidence and profit).

### Infra today

- Private the homelab hypervisor homelab. Primary trading container runs behind a VPN with split-tunnel policy routing and fail-closed firewalling. Secondary container for the upstream scorer service (used by Bot B).
- Python 3.11+ async. SQLite via SQLAlchemy 2.x (WAL mode, Postgres-compatible types). Alembic migrations. pytest.
- `py-clob-client` 0.34.6 (pre-V2). Polymarket V2 migration deferred until paper-gate passes (ADR-017).
- Keystore: age-encrypted, tmpfs-delivered passphrase, never env vars. L1 derives CLOB API creds from the private key once; L2 uses HMAC-SHA256 on a cached secret.

### Existing bots (brief)

| Bot | Strategy | Status | Notes |
|---|---|---|---|
| **A — Longshot Fade** | Mechanical NO-side fader; enters YES at ≤5¢ (implies market says <5% prob); abnormal-exit at 25¢ (5× entry ceiling). Volume + book-depth filters. | **LIVE paper** on homelab | 18 trades on prod DB; small notional; 100% win-rate so far but average trade $0.39 |
| **B — Oraclemangle Kelly** | LLM+RAG scorer, directional Kelly-sized trades on UMA-dispute-risk politics/geopolitics markets | **LIVE paper** on homelab | 1 order, scorer is a separate HTTP service |
| **C — Pyth ingest** | Pre-trading data hoover for crypto price feeds | **Paper, data-only** | No orders yet; Pyth Pro trial expires 2026-04-22 |
| **D — Weather** | Temperature buckets; GFS multi-model ensemble + METAR + NWS three-layer pipeline; Gaussian CDF vs market; one-bet-per-event (city+date) | **LIVE paper** on homelab | 15 orders, 14 fills, 3 closed (all losses, low-price YES long-shots), 11 open |
| **E — BTC 15-min scalp** | **Under review here.** Current spec: CEX-vs-Polymarket lag arb. Emerging alternative: OBI + technicals | Specified, unbuilt | |

### Shared infra (reused by Bot E)

- `core/clob.py` — ClobWrapper, GTC limit orders by default, FOK/IOC in enum, paper_override mode
- `core/portfolio.py` — realised/unrealised P&L, paper-fill fallback for arbitrary token IDs
- `core/backtest.py` — deterministic replay, take-the-touch fill model
- `core/db.py` — 10 SQLAlchemy tables
- `core/notify.py` — Telegram private channel (executed trades + daily summary only; no spam)
- `bots/watchdog_daemon.py` — kill-switch watchdog, silences known liveness-noise channels

### Recent Bot D analytics gap (just fixed, ADR-021)

While quantifying a time-to-resolution question for Bot D against the prod DB, discovered that Bot D's 15 orders reference 15 distinct `condition_id` values and **zero** of them exist in the `markets` table. The main ingest pipeline doesn't capture the Gamma pages containing weather markets. Fix: Bot D's executor now dual-writes a minimal `markets` row inside the same transaction as Order/Position, best-effort (try/except, logs but never blocks the trade). Longer-term fix (widen main ingest) logged as OQ-028. Condition_id ID-space mismatch (Bot D uses Gamma numeric id; Bot A uses hex) logged as OQ-029.

---

## 2. Operator constraints (non-negotiable)

1. **Privacy-first.** Nothing from the repo leaves the machine to external LLMs without redaction. Code, wallet addresses, keystore — never. Oraclemangle scorer data — local only.
2. **Paper-trading mandatory before live.** 4-gate graduation: backtest ≥75% WR on ≥7 days logged data → 200-trade paper sim ≥75% WR → $100 live for 48h → scale.
3. **Daily loss kill −18%, global drawdown kill −35%.** Per-trade cap 2.5%, aggregate open exposure 30%. All env-overridable defaults, not hard-coded blocks.
4. **No cross-venue arbitrage, no market-making, no HFT scalping beyond Bot E's 15-min window, no sentiment/news-latency strategies, no cloud provider beyond what's already used.** Scope-creep kill-list in CLAUDE.md.
5. **Bot D is LIVE. Any change goes through an ADR.**

---

## 3. Bot E — current spec (the thing being reviewed)

Full spec lives at `docs/bot-e-spec.md`. Key points:

### Current thesis: CEX-vs-Polymarket lag arbitrage

Polymarket's 15-minute BTC/ETH/SOL Up/Down markets resolve against Chainlink price feeds. In the final 5–60 seconds before resolution, the on-chain outcome is often already determined by CEX spot prices (Binance, Coinbase) that move faster than the Polymarket CLOB's limit book. A bot with direct CEX WebSocket access buys the winning side at 96–99¢ before the book rebalances, capturing 1–4¢ per share.

### Key parameters

- Entry window: **10–60 seconds before resolution**
- Target edge after fees+slippage: **≥5.5%** (per @adiix_official)
- Sizing: half-Kelly (k=0.5), per-trade cap 2.5% of bankroll
- Risk controls: daily −18% / global −35% / consecutive-loss halt (5 in 10min → 15min cooldown) / stale-feed halt (>500ms)
- Target end-to-end latency: **<650ms**
- Infra: **eu-west-1 VPS** (LXC is +60–80ms via VPN — too slow)
- Hit rate target: 85–95%
- Target trade frequency: 50–200/day

### Infra stack

- Binance WSS primary, Pyth Lazer secondary, Chainlink on-chain fallback
- Dedicated Alchemy/Infura RPC (free tier)
- Reuse `py-clob-client` + `ClobWrapper`
- Separate $100-capped hot wallet (not shared with Bot A/B)

### Module layout (planned, not built)

```
bots/bot_e_btc_scalp/
├── config.py             # thresholds, RPC URLs
├── cex_feed.py           # Binance WSS, latency-tracking
├── polymarket_book.py    # CLOB book WSS
├── chainlink_oracle.py   # on-chain price
├── signal.py             # CEX vs Polymarket vs strike
├── sizer.py              # half-Kelly
├── executor.py           # sign + submit
├── lifecycle.py          # order state machine
└── tests/
```

### Phase/gate plan

| Phase | Capital | Gate |
|---|---|---|
| Paper (simulated) | $1k sim | 200 trades, >75% WR |
| Live bootstrap | $100 real | 48h, positive P&L |
| Live scale-1 | $1,000 | 7 days, Calmar > 1.5 |
| Live scale-2 | $10,000 | 30 days, no kill events |
| Ceiling | $50,000 | Operator sign-off |

---

## 4. Evidence base — 7 article distillations

Summarised from `docs/bot-knowledge.md`. Each entry graded for credibility and actionability.

### Entry 001 — Kelly Criterion (unknown author, operator-shared)

**Credibility: high.** Core maths correct.

- `f* = (bp − q) / b`; Edge = p − m
- Most Polymarket pros gate at edge ≥ 5–6%
- Full Kelly → 40–50% drawdown on 8–10 losses in a row at 60% edge
- Fractional Kelly at **k ∈ [0.25, 0.50]** is standard practice
- p must have a cited source; "why do I know something the market doesn't?" as hard gate

**What we took:** Start Bot E at k=0.25 for paper phase (more conservative than spec's 0.50). Mandatory `p_source` + `reason_code` on every trade. Use `edge_net = p − m − fees − expected_slippage` for the gate, not raw edge.

### Entry 002 — @RetroValix "9 types of Polymarket trading bots" (2026-04-06)

**Credibility: moderate-to-high.** Dataset of top-1000 profitable wallets, described strategies ring true, wallet examples are public. No proprietary signal formulations disclosed.

| # | Strategy | Example wallet | Deposits → PnL | ROI |
|---|---|---|---|---|
| 1 | Arbitrage (sum <$1) | googoogaga23 | $6.6k → $133k | 20× |
| 2 | **Order-book imbalance** | **vague-sourdough** | **$1.8k → $410k** | **223×** |
| 3 | Hybrid (arb + directional) | BoshBashBish | $3.2k → $364k | 114× |
| 4 | Near-resolution at 99c | anon-fake | $7.5k → $214k | 28× |
| 5 | Cross-market arb | swisstony | $2.85M → $5.56M | 2× |
| 6 | Repricing on state change | gatorr | $200k → $1.9M | 9.5× |
| 7 | Directional hedge | tradecraft | $17k → $213k | 12× |
| 8 | Ladder (elimination) | hondacivic | $43k → $50k | 1.15× |
| 9 | Probability model + hedge | kch123 | $13.2M → $11.3M | 0.85× |

**The 5 universal patterns:** limit orders only; small edges, high frequency; structural risk management (split entries, skewed hedges); exploit lag; trade market structure, not opinions.

**The 5 "precise questions" (operator-flagged as KEY):** Where is the price wrong? Where is liquidity weak? Which linked market hasn't moved? How should this be priced now? How can I build this with better EV? — saved as the canonical `reason_code` enum: `{price_wrong, liquidity_weak, linked_lag, repricing, ev_structure}`.

**What we took:** Strategy #2 (OBI) is the highest-ROI-per-dollar at our capital tier. Strategy #4 (pure near-resolution 99c) is a simpler version of our current Bot E spec. Both might be LXC-runnable without VPS — flagged for architecture decision.

### Entry 003 — @bl888m "$67k in 9 weeks" (2026-04-12) — Kreo.app marketing piece

**Credibility: low on claims, moderate on microstructure.** Hero numbers ($300 → $5,812 linearly compounding), FOMO framing, affiliate structure. BUT buried microstructure observations are independently legitimate:

- **Copy-trading edge compresses fast** (well-known dynamic; validates need for recent-edge filter on whale copy)
- **Priority execution = 1 Polygon block (~2s)** — if you're 15s behind the whale, you eat slippage
- **Volume spike as exit signal** — 3× baseline in 10min → exit (testable threshold)
- **Liquidity timing window — enter 4–8h after initial volume spike** (unverified but coherent)
- **Category rotation** — attention cycles through election → sports → crypto (real phenomenon, hard to operationalise)

**What we took:** Sharpened Bot F idea 001 (whale copy) with a recent-edge filter (trailing-30d ≥ 80% of trailing-6m median) and a crowd-edge-adjusted category filter. Rejected the SaaS and the linked wallet addresses.

### Entry 004 — Three-file copy-trading bot (anonymous X post, 2026-04)

**Credibility: low on P&L claims (9 days, $300 → $5,812), moderate on architecture. Linked repos are three unrelated projects by three different authors.**

Architecture that maps cleanly onto our existing `discovery/signal/executor` pattern:

| Article | Role | Our equivalent |
|---|---|---|
| **Hunter** | Offline ranker over historical trades | `bots/bot_f/discovery.py` |
| **Mirror** | Online WSS subscriber, fires deduped signals | `bots/bot_f/signal.py` |
| **Trigger** | Risk-filtered executor | `bots/bot_f/executor.py` |

Concrete filter thresholds (starting points for backtest):
- Hunter: min_trades ≥ 100 (90d), win_rate > 62%, profit_factor > 1.8, rank by Sharpe, top 40
- Mirror: dedupe within 60s, exponential-backoff reconnects
- **Trigger: skip if signal age > 90s, per-trade ≤ 3%, per-market ≤ 2 positions, spread ≤ 4¢, TTR > 6h, size ≤ 25% of whale's size, ±0.002 slippage buffer**

**What we took:** Adopted Hunter/Mirror/Trigger decomposition for Bot F idea 001. Replaced Redis with Python `asyncio.Queue` (no new infra dependency). Concrete thresholds as backtest starting values, NOT live defaults. Flagged code bugs in the article's snippets (token_id vs market_id mix-up, simplified `create_and_post_order` signature) — not copying verbatim.

### Entry 005 — @Gustafssonkotte v96 Bot (2026-04-13)

**Credibility: highest in series.** Dated iteration history (v96), detailed architectural writeup, code snippets are idiomatic without the structural bugs of Entry 004, **no P&L claims and no CTA** (strong trust signal — not selling). Targets the same 15-min BTC Polymarket market as our Bot E.

**Strategy description:** two-hemisphere design.
- **Left hemisphere:** technical analysis on 30s OHLC candles built from Chainlink Data Streams ticks. SuperTrend, EMA, volume oscillators.
- **Right hemisphere:** live order book + orders_matched WSS. Computes live trade imbalance every 5 seconds.

**Both hemispheres vote; trade fires only at intersection. No hemisphere outranks the other.**

Entry window: **minutes 5–10 of each 15-min period** (i.e., t−10min to t−5min before resolution). This is **different from our current Bot E spec** (t−60s to t−5s) — it's an **order-flow-directional strategy, not a CEX-lag arbitrage.**

Seven concrete architectural patterns from the v96 article:
1. **Two-hemisphere voting** (technical × flow)
2. **Market-regime classifier** — 6 regimes (TREND_UP, TREND_DOWN, VOLATILE_TREND, VOLATILE_CHOPPY, SIDEWAYS, UNKNOWN). Choppiness ratio = `reversals / (candles-1)`. `<0.45 AND |dir_10m|>30` = VOLATILE_TREND (trade). `>0.60` = VOLATILE_CHOPPY (skip).
3. **PeriodTracker** — observe for first 5min, enter mins 5–10. Confidence ≥0.60 agreeing with candidate → drop BTC-move threshold by 20%.
4. **VETO system** — any signal can block; consensus lifts vetoes unless absolute. Volume VETO is absolute.
5. **Synergy bonuses (additive, not multiplicative)** — clusters of agreeing signals add to `synergy_score`.
6. **Platt scaling confidence calibration** — every N trades, weighted linear regression of predicted vs actual hit rate per bucket. Bounded corrections: slope `a ∈ [0.5, 2.0]`, intercept `b ∈ [−0.15, 0.15]`. Applied as `fair = a*fair + b`. **Exact implementation of the edge-decay meta-feature we'd flagged after Entry 003.**
7. **SmartKelly** — base Kelly × multiplier ∈ [0.5, 1.5] driven by confidence tier / vote_score / market_quality / synergy_count / fast-slow conflict / memory_adj.

Infra:
- **Chainlink Data Streams** as primary BTC feed (institutional-grade WSS with HMAC auth, sub-second latency). **This is the same source Polymarket uses for resolution → zero lag ambiguity.**
- Fallback chain: CDS → Chainlink on-chain → CEX APIs
- Pre-warm 35 candles via 37 REST at startup — indicators live from iteration 1
- Config validation of 27+ params at startup; bot refuses to start if invalid
- Auto-claim via `Safe.execTransaction` calling `redeemPositions` on CTF Exchange (V2-aware)

**What we took:** This article reframes the whole Bot E question. Either the author is wrong about the 15-min BTC strategy or our current spec is targeting the wrong sub-strategy of a multi-strategy market. The architectural patterns listed would take months to cargo-cult. **Explicit anti-pattern warning: do not build v96 in one shot.** Start minimal (OBI only + choppiness regime + basic Kelly + config validation), let real losing trades drive feature priority.

### Entry 006 — @theparuchh "Little Rocky" weather-bot guide (2026-04-14)

**Credibility: low on P&L ("$313 → $414k in one month"), mostly beginner how-to (Mac Mini setup, Homebrew, install Claude Code, etc.). Re-covers Bot D territory.**

Three takeaways worth keeping:
1. **FOK-with-GTC-fallback execution pattern** — FOK first, GTC as graceful degradation with configured slippage tolerance. Our ClobWrapper already supports both but defaults to GTC. Low-risk `prefer_fok` flag would benefit Bot E and Bot F.
2. **12-of-20 trailing-loss circuit breaker** — hard count over fixed window. Different from rolling-WR (our current Bot D approach). Faster-reacting to acute streaks. Worth running alongside consecutive-loss halt in Bot E.
3. **Analyst Bot concept** — reads trade log, identifies profitable cells (city × hour × edge-bucket × market), rewrites config. Different from Platt calibration (which corrects fair_prob) — this corrects operating parameters. Parked as Bot F-adjacent idea.

### Entry 007 — @maqxbt "5 strategies + 3 golden rules" (2026-04-08)

**Credibility: lowest in series. Beginner-oriented overview. No sample sizes, no dates, no wallet examples.** Strategies overlap Entry 002 at lower resolution.

Two bits with actual novelty:
1. **Niche-edge category-selection heuristic** — don't validate strategies in US-presidential / major-crypto (most-crowded, least-forgiving of latency). Pick niche categories operator has domain knowledge in. Matches Entry 003's crowd-edge-adjusted filter — composes as: "prefer specialists in uncrowded categories."
2. **Cross-PLATFORM arb (Polymarket ↔ Kalshi ↔ PredictIt)** — already on CLAUDE.md out-of-scope kill-list. Not reopening.

Three golden rules (operator wisdom, kept):
1. **Always read resolution criteria** → every strategy config must have a one-line `resolution_source` field.
2. **Check liquidity** → min volume + book depth filter (already enforced per-bot; shared `core/liquidity.py` is a follow-up).
3. **Don't chase 50x returns** → Kelly-compound thesis; gate for new strategy proposals.

---

## 5. The strategic question

**Two distinct viable strategies exist for 15-min BTC Polymarket markets:**

| Dimension | Option A: current Bot E spec | Option B: v96 / OBI+flow |
|---|---|---|
| **Entry window** | Last 60 seconds | Minutes 5–10 (t−10min to t−5min) |
| **Signal source** | CEX price vs Polymarket strike | OBI on orders_matched + technical vote + regime classification |
| **Infra requirement** | eu-west-1 VPS colocation (<650ms E2E) | LXC-friendly (no sub-second CEX race) |
| **Edge type** | Arbitrage (near-certain resolution) | Directional prediction (5–10min before resolution) |
| **Hit rate target** | 85–95% (close to certain) | ~60–65% (Kelly math implication) |
| **Entry window duration** | ~55 seconds | ~5 minutes |
| **Shots per day** | 50–200 (subset of 1,440 windows) | Potentially higher (5x entry window) |
| **Evidence at our capital tier** | @adiix_official's guidance, unverified | @vague-sourdough $1.8k→$410k public profile (strategy #2 in Entry 002); @Gustafssonkotte v96 detailed architecture |
| **CEX-lag competition** | Extreme (HFT colocation) | Lower (different skill set) |

**Strong case for Option B:**
- No evidence anywhere in the article series that retail CEX-lag arb at our latency profile is profitable
- Highest-ROI-per-dollar wallet in the dataset at our capital tier (vague-sourdough) did OBI
- v96 author runs order-flow on LXC-equivalent infra with no P&L-pitch (trust signal)
- Ships weeks sooner (no VPS provisioning)
- Saves ~$30/mo hosting
- Option A becomes a phase-3 module iff we ever co-locate

**Case against Option B:**
- Directional hit rate (60–65%) is much lower than arb hit rate (85–95%) → more variance, more psychological load
- OBI signals are noisy; takes longer to calibrate what "imbalance > 0.20" means in our market conditions
- We'd be competing with v96-class implementations that have 95 iterations of edge-case handling
- Option A is at least clearly definable (CEX > strike → YES wins); Option B requires real signal calibration

**My recommendation:** **Option B (pivot), with explicit v1 minimum-viable scope.**

---

## 6. Pending decisions (D1–D14)

Full list with my recommendation + reasoning.

### Bot E strategy bundle (must decide together)

| # | Question | Rec | Why |
|---|---|---|---|
| **D9** | Pivot Bot E strategy to OBI+flow (t−10min to t−5min)? | **YES** | Evidence (Entries 002, 003, 005) consistently points here. No evidence retail CEX-lag is profitable. |
| **D1** | Bot E on LXC, defer VPS indefinitely? | **YES** (follows D9) | OBI doesn't need <650ms. Saves hosting + accelerates paper gate. |
| **D12** | v1 scope = OBI signal + choppiness regime + basic Kelly + config validation only; defer two-hemisphere / PeriodTracker / synergy / signal memory / VETO to phase 2+? | **YES** | v96 took 96 iterations to build. We don't have that corpus. Ship minimal, let real losing trades drive features. |

### Shared infra (independent, pull-through JIT)

| # | Question | Rec | Why |
|---|---|---|---|
| **D2** | Five-question `reason_code` enum across all bots (`{price_wrong, liquidity_weak, linked_lag, repricing, ev_structure}`) + `strategy_name` secondary column? | **YES eventually** | Schema migration, touches all bots. Land after Bot E v1 is running. |
| **D10** | Shared `core/calibration.py` with Platt scaling, applied across all bots? | **YES eventually** | Build when Bot E has >100 paper trades. Article gives working reference code. |
| **D13** | FOK-with-GTC-fallback flag on ClobWrapper? | **YES if Bot E v1 uses it** | Small addition; benefits Bot E + Bot F; zero risk to A/B/C/D. |

### Bot F (wait until Bot E paper gate passes)

| # | Question | Rec | Why |
|---|---|---|---|
| **D6** | Hunter/Mirror/Trigger decomposition for Bot F idea 001? | **YES** (noted in ideas file) | Matches existing pattern. |
| **D7** | First Bot F build = extend backfill + discovery.py for 2-week read-only tracker? | **DEFER** | One bot at a time. Keep Bot E debug surface small. |

### Low-priority / parked

| # | Question | Status |
|---|---|---|
| **D3** | Bot D ladder v2 enhancement (elimination logic on dead ranges) | Parked — Bot D is live, scope-creep rule |
| **D4** | Bot F idea 001 filter additions (recent-edge, crowd-edge) | Already in ideas file |
| **D5** | Edge-decay monitor meta-feature first, before Bot F build? | Rolled into D10 |
| **D8** | Add the VPS provider CX11 Frankfurt to Bot E VPS decision matrix | Low-risk doc tweak; fold into Bot E commit if D9=YES makes it moot |
| **D11** | Investigate Chainlink Data Streams access/pricing | Deferred until CEX fallback proves insufficient |
| **D14** | Park Analyst / Scout bot concepts to Bot F ideas file | Low-risk doc tweak |

---

## 7. Proposed v1 build (if D9+D1+D12 = YES)

### Module layout

```
bots/bot_e_btc_scalp/
├── __init__.py
├── __main__.py          # async main loop, signal handling
├── config.py            # env-overridable params; 10-param startup validation
├── polymarket_ws.py     # CLOB + orders_matched subscribers; auto-reconnect w/ backoff
├── signal.py            # OBI: rolling 2-min imbalance, threshold 0.20, optional regime filter
├── regime.py            # choppiness ratio; skip VOLATILE_CHOPPY
├── sizer.py             # Kelly × config-driven fraction (default 0.25)
├── executor.py          # dry-run first; GTC limit orders via existing ClobWrapper
└── tests/
    ├── test_signal.py         # OBI math unit tests
    ├── test_regime.py         # regime detection unit tests
    ├── test_config.py         # startup validation
    └── test_integration.py    # dry-run end-to-end against mock WSS
```

### Config (all env-overridable)

```python
# Risk caps
BOT_E_BANKROLL_USD = 100.0  # live bootstrap; env for scale
KELLY_FRACTION = 0.25
EDGE_NET_THRESHOLD = 0.055
PER_TRADE_CAP_FRAC = 0.025
AGGREGATE_EXPOSURE_CAP_FRAC = 0.30
DAILY_LOSS_KILL_FRAC = -0.18
GLOBAL_DRAWDOWN_KILL_FRAC = -0.35
CONSECUTIVE_LOSS_HALT_N = 5
CONSECUTIVE_LOSS_HALT_WINDOW_SEC = 600
CONSECUTIVE_LOSS_HALT_COOLDOWN_SEC = 900
TRAILING_LOSS_HALT_N = 12   # halt if 12 of last 20 lost (Entry 006)
TRAILING_LOSS_HALT_WINDOW = 20

# OBI signal
OBI_ROLLING_WINDOW_SEC = 120.0       # 2 min (v96)
OBI_THRESHOLD = 0.20                  # abs(imbalance) > 0.20
OBI_MIN_TRADES = 2
OBI_MIN_VOLUME_USD = 1.0

# Regime
REGIME_CHOPPINESS_MAX = 0.60   # skip if > 0.60
REGIME_TREND_CHOPPINESS_MAX = 0.45
REGIME_TREND_DIR_10M_MIN = 30.0

# Execution
PREFER_FOK = True
ENTRY_WINDOW_SEC_MIN = 300    # t−10min
ENTRY_WINDOW_SEC_MAX = 600    # t−5min
SLIPPAGE_BUFFER = 0.002

# Misc
STALE_FEED_MS = 500
REASON_CODE_REQUIRED = True
```

### Signal math (OBI core, from v96)

```python
def compute_obi(trades, cutoff_sec: float = 120.0) -> float | None:
    cutoff = now() - cutoff_sec
    recent = [t for t in trades if t.ts >= cutoff]
    up_vol = sum(t.size for t in recent if t.outcome == "Up")
    down_vol = sum(t.size for t in recent if t.outcome == "Down")
    if len(recent) < 2 or (up_vol + down_vol) < 1.0:
        return None
    return (up_vol - down_vol) / (up_vol + down_vol)
```

### Regime classifier

```python
def classify_regime(closes: list[float]) -> str:
    if len(closes) < 3:
        return "UNKNOWN"
    signs = [1 if closes[i] > closes[i-1] else -1 for i in range(1, len(closes))]
    reversals = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
    choppiness = reversals / max(1, len(signs) - 1)
    dir_10m = closes[-1] - closes[0]
    if choppiness < 0.45 and abs(dir_10m) > 30:
        return "VOLATILE_TREND"
    elif choppiness > 0.60:
        return "VOLATILE_CHOPPY"
    else:
        return "VOLATILE"
```

### Gate plan (unchanged from spec)

| Phase | Capital | Gate |
|---|---|---|
| Paper (simulated) | $1k sim | 200 trades, >75% WR |
| Live bootstrap | $100 real | 48h, positive P&L |
| Live scale-1 | $1,000 | 7 days, Calmar > 1.5 |
| Live scale-2 | $10,000 | 30 days, no kill events |
| Ceiling | $50,000 | Operator sign-off |

### What's explicitly NOT in v1

- Two-hemisphere voting (just the right hemisphere / OBI)
- PeriodTracker observe-window
- Synergy bonuses
- VETO system
- Signal memory
- SmartKelly quality multipliers
- Platt scaling calibration (scaffold only, disabled until 100+ trades exist)
- Chainlink Data Streams integration (use CEX WS + Chainlink on-chain as v1 price stack)
- Auto-claim via `Safe.execTransaction` (build stub, test manually first)

---

## 8. Specific review questions

Please attack these. Contrarian is better than polite.

### Strategy

1. **Is the OBI pivot justified?** We're inferring from one ROI example (@vague-sourdough, public but small sample) and one architectural writeup (@Gustafssonkotte v96, no P&L claims). Are we over-weighting these? Is the CEX-lag strategy defensible with different infra choices we haven't considered?
2. **Is there a third strategy we're missing?** The article series clusters around arbitrage, near-resolution, OBI, copy-trading, and probability-model. Is there a 2026-current edge we haven't surfaced?
3. **Directional at 60–65% WR vs arbitrage at 85–95% WR** — for a $2k bankroll with 2.5% per-trade cap, which strategy's variance profile is more psychologically survivable for a solo operator?

### Scope

4. **Is v1 too minimal?** Real bots ship with more. Are we underestimating the cost of incremental feature additions to a live bot vs shipping a fuller v1?
5. **Is v1 too broad?** Alternatively — is OBI + regime too much? Could we ship pure OBI with no regime filter and learn faster?
6. **Paper gate at 200 trades, >75% WR** — for a 60–65% directional strategy this gate may be mis-specified. What should the gate look like for Option B?

### Signal

7. **OBI threshold of 0.20 over a 2-min rolling window** — the v96 article's starting point. What's the right way to calibrate this against our specific market/latency conditions before live?
8. **Choppiness ratio < 0.45 with |dir_10m| > 30** — dimensional units of `dir_10m` and threshold `30` are unclear (is this dollar-price or index-points?). How should we interpret this for BTC markets specifically?
9. **Correlation across simultaneous positions** — if Bot E holds BTC-up + ETH-up + SOL-up at the same 15-min resolution, aggregate Kelly ≠ sum of individual Kelly. How should we cap aggregate exposure on correlated outcomes?

### Infra

10. **LXC vs VPS** — the current spec insists VPS is required. Is there a signal latency profile we can measure on LXC today that would definitively rule in or rule out OBI from that infra?
11. **WSS reliability** — the Polymarket public WSS has user and market channels. How robust is it for real-time trade-flow data over hours/days? Known failure modes we should plan for?
12. **CTF Exchange V2 auto-claim** — we're deferring `Safe.execTransaction` + `redeemPositions`. How risky is manual claim in a paper phase running for weeks?

### Risk

13. **Kelly at k=0.25 starting fraction** — conservative vs spec's 0.50. Is 0.25 too conservative for the paper phase (learning too slowly)? Is 0.50 too aggressive given our smaller sample size than a whale with thousands of trades?
14. **Consecutive-loss halt + trailing-loss halt running together** — are both needed, or is one sufficient? What failure modes are we missing?

### Schema / process

15. **Five-question `reason_code` enum** — `{price_wrong, liquidity_weak, linked_lag, repricing, ev_structure}`. Does this taxonomy cleanly map every strategy you can think of, or are we forcing a square peg?
16. **Bot D dual-write to `markets` table (ADR-021)** — is the best-effort try/except the right pattern, or should a failed upsert be a soft-block on trading to avoid creating silent data gaps?

### Things I'm likely wrong about

17. What's the #1 thing in this plan that you'd flag as wrong, naive, or dangerous?
18. What's the biggest missing feature that we'd regret skipping in v1 specifically?

---

## 9. What's already been decided and shipped

For context so reviewers don't retread:

- **ADR-017:** Stay on `py-clob-client` 0.34.6 through paper phase; defer V2 migration until paper-gate passes.
- **ADR-018:** Reject zero-touch passphrase restore from disk (keystore requires human-delivered passphrase per boot).
- **ADR-021 (today):** Bot D dual-writes a minimal `markets` row on every order to unblock analytics. Best-effort, try/except, cannot block a trade. `core/db.py` helper `upsert_market_minimal` + `WeatherMarket.end_date` + executor call site. 297 tests pass.
- **Operator memory:** Risk controls must be tunable/overridable, not hard walls. Default-safe is fine; default-blocking is not.
- **Framing memory:** Every strategy articulable as one of the five precise questions (canonical `reason_code` enum).
- **Scope-creep kill-list:** no cross-venue arb, no market-making, no HFT beyond Bot E, no sentiment/news-latency, no copy-trading verified sharps, no cloud provider beyond what's already used.

---

## 10. File manifest (in-repo, reviewers can ask for any of these verbatim)

- `docs/bot-e-spec.md` — full current Bot E spec (216 lines)
- `docs/bot-knowledge.md` — all 7 article distillations in detail
- `docs/bot-f-ideas.md` — Bot F ideas bucket with Hunter/Mirror/Trigger architecture
- `docs/decisions-log.md` — ADRs 1–21
- `docs/open-questions.md` — 29 OQs (including OQ-028/029 added today)
- `docs/archive-little-rocky/*.md` — 8 docs of prior research
- `core/clob.py`, `core/db.py`, `core/portfolio.py`, `core/backtest.py` — shared infra
- `bots/bot_{a,b,c_pyth,d_weather}/` — live/paper bot implementations
- `CLAUDE.md` — repo operating rules
- `STATE.md` — deployment state (redact before sharing)

---

**End of review package. Please flag any assumption you disagree with.**
