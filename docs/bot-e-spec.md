# Bot E — 15-minute BTC OBI-directional trader

**Status:** Phase 0a+0b+0c+Phase 1 skeleton shipped 2026-04-16. Awaiting Phase 0d (calibration GO).
**Last updated:** 2026-04-16 (post-peer-review pivot).
**Role:** Order-book-imbalance (OBI) + directional trader on Polymarket's 15-min BTC/ETH/SOL Up/Down markets. Entry window t−10min to t−5min. Maker-only. Runs on existing homelab.

**Superseded sections below.** This spec was originally written for a CEX-lag arbitrage strategy targeting the last 60 seconds of each market. Two independent peer reviews (Grok, Codex — see `docs/bot-e-peer-review-responses/`) converged on: that strategy is not viable at our latency profile under 2026 dynamic fees. ADR-022 (accepted 2026-04-16) pivots Bot E to OBI-directional with a mandatory data-only recorder phase first.

**Read in this order:**
1. [ADR-022](decisions-log.md#adr-022-bot-e-pivot-to-obi-directional--mandatory-bot-e0-recorder-phase) — strategic decision
2. [Grok review](bot-e-peer-review-responses/grok-2026-04-16.md)
3. [Codex review](bot-e-peer-review-responses/codex-2026-04-16.md)
4. This spec (below) — original CEX-lag content now historical context

---

## Current plan summary (ADR-022)

| Phase | What | How long | Blocks |
|---|---|---|---|
| 0a | Governance + P0 verifications (fee curve, Chainlink tick units) | 1 hour | Everything |
| 0b | **Bot E0 recorder** (data-only, zero order placement) on homelab | 3–4 days wall time | Phase 0c calibration |
| 0c | Extended backtester (`core/backtest_bot_e.py`) consumes recorder output | Ships Day 1 (with Phase 0b), runs after capture | Phase 0d decision |
| 0d | Calibration: conditional expectancy by (min-to-expiry × OBI × regime); maker-only fee model | 1 day | Phase 1 activation |
| 1 | Trader activates (`bots/bot_e_btc_scalp/`) if Phase 0d = GO | Paper for ~1 month | Live bootstrap |

**Phase 0d decision criterion:** positive net EV after modelled 2026 fees + slippage + latency across at least two distinct market regimes. If negative, Bot E closes with zero capital at risk.

---

## Key constraints from Phase 0a verification

**1. Polymarket 2026 fees are dynamic.** Taker fee peaks at 1.80% for crypto at 50¢ prices (shrinks to ~0 at 1¢/99¢). Makers pay 0 and earn 20–25% rebate of counterparty fees. **Bot E is maker-only for entries.** Any taker round-trip at 50¢ crypto = 3.60% — erases realistic directional edge.

**2. Chainlink BTC/USD tick = 8 decimal places, integer representation.** The v96 article's `|dir_10m| > 30` threshold is dimensionally broken. Bot E's regime classifier normalises to basis points of current price (`dir_bps = (close_now - close_start) / close_now * 10_000`). Default trend-min threshold: 50 bps (~$42 at $85k BTC).

**3. No VPS required.** OBI runs from homelab — we only need Polymarket WSS + Binance WS, not sub-650ms CEX-to-Polygon colocation.

---

## v1 module layout (shipped 2026-04-16)

```
core/
├── fees.py                    # Polymarket 2026 dynamic fee curve + maker rebate
├── polymarket_ws.py           # Shared WSS client (CLOB + orders_matched + best_bid_ask)
├── cex_ws.py                  # Binance combined-stream WSS client
└── backtest_bot_e.py          # OBI calibration harness; consumes recorder DB

bots/bot_e_recorder/            # Phase 0b — DATA ONLY, no trading
├── config.py                   # capture parameters
├── schema.py                   # SQLite schema (pm_events, cex_trades, markets, heartbeats, gaps)
├── market_discovery.py         # Gamma scan for live 15-min crypto markets
├── capture.py                  # async capture loop (writer + subscribers + heartbeat + discovery)
├── audit.py                    # post-capture data-quality audit
└── __main__.py                 # CLI entry: python -m bots.bot_e_recorder

bots/bot_e_btc_scalp/           # Phase 1 — trader (inactive until Phase 0d GO)
├── config.py                   # env-overridable; 20+ validation checks
├── regime.py                   # binary choppiness hard-gate (bps-normalised trend)
├── signal.py                   # OBI engine (rolling window, threshold)
├── sizer.py                    # fixed $2/trade + crypto-bucket cap + aggregate cap
├── executor.py                 # maker-only; 5-question tagging; halts; dry-run
└── __main__.py                 # refuses to run --live until data/bot_e_calibration.json exists
```

---

## v1 scope (deliberately minimal)

Codex C-S7 and v96 anti-pattern rule: do NOT cargo-cult advanced features into v1. Ship the simplest thing that generates signals; let real losing trades drive v1.1+ feature priority.

**IN v1:**
- Pure OBI signal (right hemisphere of v96 only)
- Binary choppiness hard-gate (not tunable in v1)
- Fixed $2/trade (Kelly defaults to 0, reactivated after calibration)
- Maker-only entries
- Feed-freshness halt (500ms default)
- Consecutive-loss halt (5 in 10 min)
- Trailing-loss halt (12 of 20) — scaffolded, config-gated
- Primary+secondary+tertiary tagging (strategy_signal / reason_code / reason_detail)
- Telemetry: latency histograms per source, stale-feed auto-pause, heartbeat emission

**DEFERRED to v1.1+:**
- Two-hemisphere voting (technical on 30s OHLC + flow)
- PeriodTracker observe-then-trade window
- VETO system with consensus lifting
- Synergy bonuses (additive)
- Platt scaling calibration (D10 — build after 100+ paper trades)
- Signal memory / pattern match vs history
- SmartKelly quality multipliers
- Regime tuning surface (v1 uses hard-coded choppiness_max=0.65)
- Chainlink Data Streams primary feed (v1 uses Binance WS; CDS deferred unless needed)
- **Markov transition-matrix regime classifier (Entry 008, 2026-04-16).** Richer generalisation of v1's binary choppiness gate: discretise the last-N price-delta ticks into states, estimate P[i][j] online, require `p_(j*,j*) ≥ τ` simultaneously with the OBI gap. Only worth evaluating IF Phase 0d calibration demonstrates the binary choppiness gate is materially under-filtering choppy regimes. Do NOT include in v1 — Grok + Codex both flagged adding tunable regime parameters pre-calibration as anti-pattern. See `docs/bot-knowledge.md` Entry 008 D23.

---

## Paper gate (revised per Grok G5 / Codex Q6)

Original spec: 200 trades, ≥75% WR. **Infeasible** for a 60–65% WR directional strategy (binomial ~1–2%).

**New gate:**
- ≥300 trades
- Positive net EV after modelled fees + slippage + latency (from backtester)
- Sharpe ≥ 1.0
- Max drawdown ≤ 25%
- Survived ≥ 2 distinct regimes without kill-switch

---

## Capital phasing (unchanged)

| Phase | Capital | Gate |
|---|---|---|
| Phase 0d | $0 | Positive EV in backtest on recorded data |
| Paper sim | ~$1k sim | 300 trades, revised gate above |
| Live bootstrap | $100 real | 48h, positive P&L |
| Live scale-1 | $1,000 | 7 days, Calmar > 1.5 |
| Live scale-2 | $10,000 | 30 days, no kill events |
| Ceiling | $50,000 | Operator sign-off |

---

## Historical context — the ORIGINAL spec (CEX-lag)

This section is kept verbatim for context. It is NOT the current plan. See ADR-022 for why.



---

## Thesis

Polymarket's 15-minute BTC/ETH/SOL Up/Down markets resolve against Chainlink price feeds. In the final 5–60 seconds before resolution, the on-chain outcome is often already determined by CEX spot prices (Binance, Coinbase) that move faster than the Polymarket CLOB's limit book. A bot with direct CEX WebSocket access can buy the winning side at 96–99¢ before the book rebalances, capturing a 1–4¢ guaranteed profit per share.

**Edge persists because:**
- Polymarket resolution lags CEX by 5–15 seconds
- The book is populated by retail traders and market-makers who don't reprice on every CEX tick
- Execution requires sub-second decision + signing + Polygon confirmation — hard to beat without dedicated infra

**Edge does NOT persist for:**
- Anyone on the homelab hypervisor LXC going through the VPN provider (+30ms). Colocation in eu-west-1 is table stakes.
- Strategies using free public Polygon RPC. Need dedicated Alchemy/Infura.

---

## Mechanics

### Market selection

| Filter | Value |
|---|---|
| Category | 15-minute BTC/ETH/SOL Up/Down |
| Time-to-resolution | 10–60 seconds |
| Spread | ≤ 2¢ on either side (avoid adverse selection) |
| Target edge after fees/slippage | ≥ 5.5% (per @adiix_official production guidance) |

Expected opportunities: 100–1,440 windows/day (one per 15-min period per asset).

### Signal

Compare live Binance WS price to Polymarket CLOB book:

```
binance_now > strike_price + threshold_bps  →  "Up" will resolve YES
binance_now < strike_price - threshold_bps  →  "Down" will resolve YES

If implied_winner is trading < 0.96¢ on the book, BUY_YES on that side.
```

`threshold_bps` tuned empirically — start at 10 bps (0.10%), adjust based on Chainlink update cadence.

### Sizing — Half-Kelly

Per @adiix_official:

```
f* = (bp - q) / b
f_half = 0.5 × f*

where:
  b = net odds (0.99 entry → b = 0.01/0.99 ≈ 0.0101)
  p = estimated win probability (0.95+ near resolution)
  q = 1 - p
```

For p=0.95, b=0.01: f* ≈ 0.0505, f_half ≈ 0.0253 → 2.5% of bankroll per trade.
Scale down with volatility: multiply by σ_target/σ_current.

### Risk controls

| Control | Value | Trigger |
|---|---|---|
| Per-trade notional cap | 2.5% of bankroll | Hard cap |
| Aggregate open exposure | 30% of bankroll | Hard cap |
| **Daily loss kill** | **-18%** | Halt + Telegram |
| **Global drawdown kill** | **-35%** | Halt + require manual restart |
| Consecutive-loss halt | 5 losses in 10 min | 15-min cooldown |
| Stale CEX feed | >500ms | Halt entries |
| RPC failure | >3 consecutive | Halt + alert |

### Execution target

**End-to-end: <650ms**

Path:
1. Binance WS tick received (0ms)
2. Signal computation + book read (50–100ms)
3. Order sign + submit via py-clob-client (200–300ms)
4. Polygon confirmation (2–5s) — BUT order is "placed" as soon as CLOB accepts

The real race is CLOB acceptance, not Polygon confirmation. We sign the order, CLOB places it in the book within ~300ms, and it either fills against the existing book or sits there. Polygon confirmation happens in the background.

---

## Infrastructure

### NOT buildable on the homelab hypervisor LXC

- UK → Stockholm the VPN provider → eu-west-1 CLOB = +60–80ms round-trip. Too slow.
- Public Polygon RPC = unreliable. Need dedicated.
- **Minimum viable**: VPS in eu-west-1 with direct internet, no VPN hop.

### Recommended stack (from @adiix_official Articles 1, 6, 7)

- **Host**: Render.com / Fly.io / Vultr eu-west-1 ($10–30/mo)
- **Runtime**: Python 3.11+ async (aiohttp + websockets)
- **Data**:
  - Primary: Binance WS (`wss://stream.binance.com/ws/btcusdt@trade`)
  - Secondary: Pyth Lazer WS for Chainlink cross-check
  - Resolution: Chainlink price feed (via on-chain call or Polygon RPC)
- **Execution**: py-clob-client (shared with Bot A/B/D) — OR optimised fork if signing latency is critical
- **RPC**: Alchemy/Infura dedicated endpoint (free tier is fine for low request volume)
- **Signing**: Local keystore (reuse Bot A/B's age-encrypted pattern)
- **Monitoring**: Telegram + Prometheus + Grafana
- **CI/CD**: GitHub Actions with 200-trade simulated win-rate gate (>75% to deploy)

### Module layout

```
bots/bot_e_btc_scalp/
├── __init__.py
├── __main__.py           # Async daemon entry
├── config.py             # Thresholds, RPC URLs, asset list (BTC/ETH/SOL)
├── cex_feed.py           # Binance WS subscriber, lat-tracking
├── polymarket_book.py    # CLOB book subscriber (WSS user channel)
├── chainlink_oracle.py   # On-chain price feed reader
├── signal.py             # Edge detection: CEX vs Polymarket vs strike
├── sizer.py              # Half-Kelly with vol scaling
├── executor.py           # Sign + submit + confirm
├── lifecycle.py          # Order state machine (post → fill → resolve)
└── tests/
    ├── test_signal.py
    ├── test_sizer.py
    └── test_integration.py (backtest harness)
```

---

## Capital allocation

| Phase | Capital | Gate |
|---|---|---|
| Paper (simulated) | $1k sim | 200 trades, >75% WR |
| Live bootstrap | $100 real | 48 hours, positive P&L |
| Live scale-1 | $1,000 | 7 days, Calmar > 1.5 |
| Live scale-2 | $10,000 | 30 days, no kill events |
| Ceiling | $50,000 | Requires operator sign-off — slippage grows |

Starting at $100 is critical. The strategy MAY not have edge at our latency profile. Validate before scaling.

---

## Expected performance (from @adiix_official + X research)

| Metric | Estimate |
|---|---|
| Edge per trade | 0.3–2% after fees |
| Trade frequency | 50–200 per day (subset of 1,440 windows) |
| Hit rate | 85–95% (near-certain at resolution time) |
| Hold time | 10–60 seconds |
| Sharpe | 2–4 (annualised, high uncertainty) |
| Daily P&L | -18% floor, +3–5% median, +20% ceiling |

Crowding is **extreme** as of April 2026 — spreads 0.3–0.5¢. Only the fastest bots print. If Bot E is 50–100ms slower than the winners, edge is zero.

---

## Decision gates before live

1. **Backtest** against logged Binance + Polymarket book snapshots for 7+ days. Win rate must be >75% at our latency profile.
2. **Paper sim** on live feeds for 200+ trades. Same threshold.
3. **$100 live bootstrap** for 48 hours. Must be positive.
4. Only then scale.

Any gate failure = Bot E is not viable at our infra level. Do not tip real money without passing all four.

---

## Research sources

- `~/.claude/projects/-Users-operator-Code-little-rocky/memory/bot_e_btc_scalp.md` — initial notes from session 2026-04-15
- `docs/archive-little-rocky/feature-roadmap-ideas.md` — Grok dump on latency arb
- @adiix_official articles 1, 6, 7 (externally archived by user)
- Morph Polymarket x Pyth Pro article (Desktop)
- Benjamin Bigdev Medium article on 5-min crypto markets

---

## What NOT to do

- **Do not build this on the bot LXC container.** Latency path will fail.
- **Do not use shared Bot A/B wallet on day one.** Create a new hot wallet with $100 max balance so Bot E can't drain the treasury.
- **Do not skip the 200-trade paper gate.** The strategy MIGHT not work at our latency; find out before spending money.
- **Do not use marginal-polytope / Bregman projection in v1.** That's Article 3 and it's overengineered for single-contract scalping. Revisit only if Bot E expands to cross-contract plays.
- **Do not copy-trade the X-documented $300→$414k wallet.** That's unverified hype.

---

## References

- `specs/bot-a-spec.md`, `specs/bot-b-spec.md` — style guide for this doc
- `specs/shared-infra.md` — CLOB wrapper, keystore, portfolio reconciliation
- `specs/test-protocol.md` — paper-to-live graduation pattern Bot E will follow
- `core/clob.py` — reuse ClobWrapper with `paper_override` for paper-mode scoping
- `core/portfolio.py` — reuse Portfolio for fill reconciliation (the paper-fill fallback in simulate_paper_fills now works for arbitrary token IDs)

---

## Immediate next actions (for the Bot E build session)

1. Read this spec + `docs/archive-little-rocky/feature-roadmap-ideas.md`
2. Choose VPS provider (Render.com recommended per @adiix_official) and get latency baseline to eu-west-1 CLOB
3. Build `cex_feed.py` first — 1 day of Binance tick logging to measure real latency before writing a single trading line
4. Decide on dedicated hot wallet vs shared. Strong recommendation: **dedicated**, funded with $100 max
5. Build the backtest harness against logged data. Gate 1 must pass before any live work.
