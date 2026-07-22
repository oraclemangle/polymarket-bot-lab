# Polymarket Bot Knowledge — Distilled from External Sources

**Status:** Rolling knowledge file. Growing per article.
**Last updated:** 2026-04-16
**Purpose:** Curate actionable insights from X threads, articles, research, and operator-shared material. Each entry is tagged by which bot(s) it applies to and flags what's already in the codebase vs what's new.

Format per entry:
- **Source** (date, author/handle if known, link if available)
- **Applies to** (Bot A/B/C/D/E/F/all)
- **Core claims** (what the source actually asserts)
- **Already in our codebase** (cross-ref to files/lines)
- **Actionable** (concrete items, bot-tagged)
- **Caveats** (what the source gets wrong or glosses over)

---

## Entry 001 — Kelly Criterion for Polymarket (2026-04-16)

**Source:** X article on Kelly sizing, shared by operator 2026-04-16
**Applies to:** all bots (sizing framework); primary focus Bot E, Bot F

### Core claims

1. **Kelly formula** (John Kelly, Bell Labs, 1956): `f* = (bp − q) / b` where `b` = net odds, `p` = win prob, `q` = 1 − p
2. **Edge** is simply `Edge = p − m` where `m` is the market price you're buying at
3. **Entry gate.** Most Polymarket pros only trade when edge ≥ 5–6%. Below that, fees and variance eat the profit
4. **Full Kelly drawdown reality.** 8–10 losing trades in a row at a 60% edge is statistically normal. Full Kelly takes a 40–50% bankroll hit in that stretch
5. **Fractional Kelly.** Standard practice: multiply `f*` by `k ∈ [0.25, 0.50]`. Slower growth, much better psychological survival
6. **p must have a real source.** Technical analysis, volume anomalies, RSI/MACD for short-price markets. Source quality + historical analogs for event markets. "Why do I know something the market doesn't?" is the hard gate — no answer, no trade
7. **Log every trade.** Record `p`, `p_source`, `m`, `edge`, `f*`, `f_applied`, outcome. After ~a month you can see where your edge is real vs flattering

### Already in our codebase

- **Bot E spec** ([docs/bot-e-spec.md](bot-e-spec.md)): half-Kelly (`k = 0.5`), edge threshold `≥ 5.5%` after fees, consecutive-loss halt (5 in 10 min → 15-min cooldown). Consistent with the article.
- **Bot D** ([bots/bot_d_weather/strategy.py](../bots/bot_d_weather/strategy.py)): already uses Kelly sizing with bankroll cap. Verified in the memory index at 2015 and in `feedback_risk_vs_profit.md`.
- **Bot B**: uses LLM-derived `p` with oraclemangle RAG. `p_source` is implicitly "scorer ensemble" — but the explicit `reason_code` discipline from the article is NOT enforced.

### Actionable

- **[Bot E]** Start fractional Kelly at `k = 0.25` for the 200-trade paper gate. Only escalate to `k = 0.50` after calibration data shows predicted hit rate within ±5% of realized. Rationale: operator is right — kills shouldn't block profit, but k=0.25 is a *parameter*, not a block. Move it up or down based on data, not dogma. Stored in `config.py` as `KELLY_FRACTION` env-overridable
- **[Bot E, Bot F]** Every trade-insert row MUST carry: `p_value`, `p_source` (enum: `cex_lag`, `whale_copy`, `news_latency`, `scorer_ensemble`, `weather_ensemble`, `manual_override`, ...), `m_value`, `edge`, `f_star`, `f_applied`, `bankroll_at_entry`. Enables post-hoc calibration
- **[all bots]** Add a **calibration report** scheduled nightly: for each 5-percentage-point `p` bucket, compare predicted hit rate vs realized. If p=0.70 bets historically win 0.55, we're over-confident and the module auto-suggests dropping `KELLY_FRACTION`. The suggestion surfaces via Telegram — operator decides whether to apply
- **[Bot E, Bot F]** Enforce a `reason_code` string per trade. If empty, block with a loud warning (not silent). Prevents vibes-trading

### Caveats

- Article's `Edge = p − m` ignores fees and slippage. Use `edge_net = p − m − fee_rate − expected_slippage_bps/10_000`. Gate on `edge_net` ≥ threshold, not raw edge
- Article talks about single trades in isolation. In production, Bot E might have 3–5 simultaneous positions on correlated outcomes (e.g., BTC-up and ETH-up at the same 15-min resolution). Aggregate Kelly ≠ sum of individual Kelly — add a **correlation-adjusted position cap** to the aggregate-exposure rule
- Fractional Kelly only pays off over hundreds of trades. At Bot E's $100 bootstrap with ~100 trades, variance dominates. Don't over-interpret the first 48h
- Article doesn't mention the **edge-decay-near-resolution** effect on 15-min BTC markets: your `p` estimate gets sharper as time-to-resolution shrinks, but so does everyone else's. The window where Bot E has asymmetric info is roughly t−60s to t−5s. Gate entries accordingly

### Operator decisions logged from this article

- Accepted: 0.25 fractional Kelly as starting point for Bot E paper phase
- Accepted: `reason_code` required on every trade (Bot E + Bot F)
- Deferred: nightly calibration report — noted, build after paper gate passes

---

## Entry 002 — 9 Main Types of Polymarket Trading Bots (2026-04-16)

**Source:** @RetroValix ("VALIX") on X, 2026-04-06. Dataset: top 1,000 most profitable Polymarket bots.
**Applies to:** Bot E (strategies 1–4), Bot F (strategies 5–7, 9), Bot D (strategy 8 — review only), all bots (common patterns)

### The 9 strategies (summary table)

| # | Strategy | Wallet example | Deposits → PnL | ROI | Maps to |
|---|---|---|---|---|---|
| 1 | Arbitrage (sum <$1) | googoogaga23 | $6.6k → $133k | 20× | Bot E (new module) |
| 2 | **Order-book imbalance** | **vague-sourdough** | **$1.8k → $410k** | **223×** | **Bot E (primary candidate)** |
| 3 | Hybrid (arb + directional) | BoshBashBish | $3.2k → $364k | 114× | Bot E (phase 2) |
| 4 | Near-resolution at 99c | anon-fake | $7.5k → $214k | 28× | Bot E (current spec) |
| 5 | Cross-market arbitrage | swisstony | $2.85M → $5.56M | 2× | Bot F (priority) |
| 6 | Repricing on state change | gatorr | $200k → $1.9M | 9.5× | Bot F |
| 7 | Directional hedge | tradecraft | $17k → $213k | 12× | Bot F |
| 8 | Ladder (elimination) | hondacivic | $43k → $50k | 1.15× | Bot D (review only) |
| 9 | Probability model + hedge | kch123 | $13.2M → $11.3M | 0.85× | Bot F (overlaps Bot B) |

Scale warning: swisstony ($2.85M) and kch123 ($13M) are HFT-scale professional operators. Their absolute ROIs are lower because they eat more slippage at size. Our tier (sub-$10k deposits) is represented by googoogaga23, vague-sourdough, BoshBashBish, anon-fake, and tradecraft — these are the relevant examples.

### The five "precise questions" (operator-flagged as KEY)

Every trade across every strategy reduces to one of these five framings. Treat them as a mandatory pre-trade checklist and as the enum for `reason_code` from Entry 001:

1. **Where is the price wrong?** → repricing, probability-model
2. **Where is liquidity weak?** → order-book imbalance
3. **Which linked market has not moved yet?** → cross-market arbitrage
4. **How should this outcome be priced right now?** → probability-model, near-resolution
5. **How can this position be built with better EV?** → hybrid, directional hedge

Code implication: `reason_code` enum becomes `{price_wrong, liquidity_weak, linked_lag, repricing, ev_structure}` with a secondary `strategy_name` column for the specific tactic (e.g., `strategy_name=obi`, `reason_code=liquidity_weak`). This makes post-hoc attribution across all bots use the same five buckets.

### The five universal patterns (all 9 strategies share)

1. **Limit orders only.** Already baked into our stack — [core/clob.py](../core/clob.py) defaults to `OrderType.GTC` and no bot issues market orders. **Verified 2026-04-16.** Keep it that way. Any new Bot E/F module that uses market orders gets a code-review block.
2. **Small edges, high frequency.** Our 5.5% net-edge floor is conservative vs BoshBashBish's stated 7.27% average arb edge — consistent with "many small edges over hundreds of trades."
3. **Structural risk management.** Not just position sizing — split entries, skewed hedges (82.8% dominant / 17.2% hedge), linked-market hedges.
4. **Exploit lag.** Reality changes first, price updates second. Every strategy above is a specific form of lag arbitrage.
5. **Trade market structure, not just opinions.** The five questions above operationalize this.

### Strategy-by-strategy mapping

**[Bot E] Strategy 1 — Arbitrage (combined cost <$1)**
googoogaga23 runs this on 5-min BTC markets, 60% arb entries, refines position afterwards. Detection is mechanical: scan book, find YES_ask + NO_ask < $1 − fees. Execution is limit orders so you don't get picked off. Worth a dedicated `bot_e_btc_scalp/arb_scanner.py` module. Only needs Polymarket WSS, no CEX feed, no VPS.

**[Bot E] Strategy 2 — Order-book imbalance (vague-sourdough, 223× ROI)**
This is the highest ROI per dollar deposited in the dataset. 5-min crypto, $8 median trade size. Mechanism: one side of the book becomes thin, enter into that imbalance, wait for book to rebalance, close or keep the stronger side. **Critical observation: this strategy may NOT need a eu-west-1 VPS.** It trades Polymarket-internal microstructure, not CEX-vs-Polymarket lag. If true, Bot E could run on the bot LXC container for this strategy, bypassing the VPS requirement in the current spec. **Flagged for operator decision** — could be a significant architectural simplification.

**[Bot E] Strategy 3 — Hybrid (arb + directional)**
BoshBashBish: 5-min arb + 15-min directional on OBI. Validates the current spec's 15-min BTC focus AND suggests adding 5-min arb as the base layer. Natural phase-2 after OBI/arb individually validated.

**[Bot E] Strategy 4 — Near-resolution 99c**
anon-fake: buys at 99c with limit orders, waits for redemption. Current Bot E spec is a more sophisticated version of this (using CEX feed to predict the winner earlier). The pure 99c version is simpler and doesn't need a CEX feed. Worth considering as the v0 of Bot E — ship the simplest-possible version, validate the plumbing, then layer in the CEX-lag edge.

**[Bot F] Strategy 5 — Cross-market arbitrage**
swisstony on sports: totals vs spreads vs BTTS. 0.45–0.55 entry zone. This is the classic structural-arb play — see [docs/archive-little-rocky/structural-arb-research.md](archive-little-rocky/structural-arb-research.md) and [arxiv-structural-arb-comparison.md](archive-little-rocky/arxiv-structural-arb-comparison.md). Priority candidate for Bot F because the math is already researched.

**[Bot F] Strategy 6 — Repricing on state change**
gatorr on sports spreads/totals, 48–52c range. Requires live game-state feed (score, possession, time remaining) + a fair-value calculator. Bot F, but needs a sports data subscription.

**[Bot F] Strategy 7 — Directional hedge**
tradecraft on tennis, 82.8% dominant / 17.2% hedge. This is Bot B's architecture applied to sports. Could be a Bot F category variant of Bot B.

**[Bot D — REVIEW ONLY, do not modify] Strategy 8 — Ladder**
hondacivic on weather: temperature ladder, buys NO on impossible ranges as distribution collapses. Our Bot D strategy is Gaussian CDF per-range with one-bet-per-event enforcement — it does NOT currently do elimination logic (buy NO on dead ranges). Flagging as a potential Bot D enhancement but per CLAUDE.md scope-creep rules, Bot D is live and working; any change goes through an ADR. Not proposing a change, just noting the gap.

**[Bot F] Strategy 9 — Probability model + hedge**
kch123 on NBA/NHL, own model + arb hedge on directional exposure. This is architecturally similar to our Bot B but applied to sports. Bot F candidate — would need a sports probability model, which is a significant undertaking (another oraclemangle-scale project).

### Actionable — immediate

- **[Bot E]** Flag the OBI strategy (#2) and pure near-resolution (#4) as potentially-VPS-free alternatives to the current CEX-lag spec. **Needs operator decision** before committing to eu-west-1 VPS. If either works from the bot LXC container, Bot E ships faster and cheaper.
- **[all bots]** Refactor `reason_code` to use the five-question enum: `{price_wrong, liquidity_weak, linked_lag, repricing, ev_structure}`. Update [core/db.py](../core/db.py) trade schema to require it. Secondary `strategy_name` column for the specific tactic.
- **[Bot E]** Module layout: `arb_scanner.py` (strategy 1), `obi.py` (strategy 2), `near_resolution.py` (strategy 4). Start with OBI — highest ROI in the dataset at our capital tier. CEX-lag arb from the current spec becomes `cex_lag.py` as a phase-2 module that requires the VPS.
- **[Bot F]** Add entries to [docs/bot-f-ideas.md](bot-f-ideas.md) for cross-market arb (002), sports repricing (003), directional hedge (004), and probability-model-+-hedge (005).

### Caveats

- **Survivor bias.** These are the top 1,000 out of thousands of bots. Most of the long tail lost money. The strategies listed work, but only with good implementation — the article's dataset excludes the long-tail losers.
- **No data on latency budgets.** Article doesn't say how fast vague-sourdough's OBI reactions are. Our the bot LXC container may or may not be fast enough. Needs empirical test (log ticks + simulated entries for 24h, measure latency distribution).
- **No hold-time data for strategies 1–4.** Assumed minutes-to-seconds based on market type, but not stated.
- **Scale effect on swisstony/kch123.** Their absolute PnL is huge but their ROI is low because slippage at their size is crushing. At our size ($1–2k tier) the same strategy could have a much higher ROI — OR a much lower one, because small positions don't move a market and don't attract adverse selection the same way. Needs independent backtest.
- **Near-resolution bots carry tail risk.** Article acknowledges it. Our Bot E kill-switch (-18% daily) is the mitigation.

### Operator decisions pending from this article

- **Decision 1:** Should Bot E pivot to start with OBI (strategy 2) from the bot LXC container, deferring the VPS requirement until we know the simpler strategy works? **[PENDING — awaiting operator input]**
- **Decision 2:** Adopt the five-question enum for `reason_code` across all bots? **[PENDING]**
- **Decision 3:** Approve adding strategies 5, 6, 7, 9 to [docs/bot-f-ideas.md](bot-f-ideas.md) as formal candidates? **[PENDING — I'll add them to the ideas file now since "ideas" status doesn't require approval, but flagging any that look like approved-feature lists need explicit sign-off]**

---

## Entry 003 — Copy-trading compression + Kreo.app pitch (2026-04-16)

**Source:** @bl888m on X, 2026-04-12 ("How I Made $67K on Polymarket in 9 Weeks")
**Applies to:** Bot F (whale copy-trading, idea 001 — sharpens existing thinking)
**Framing:** This article is primarily a marketing piece for Kreo.app with a personal-narrative wrapper. Treat the hero numbers (+$2.1k / +$18.9k / +$44.8k) and the specific wallet addresses as unverified. Extract only the microstructure observations, which are independently testable.

### What's real in the article

1. **Copy-trading edge compresses as adoption grows.** Author claims "$400 trade in January → $120 same trade in April" on the same wallet. Specific numbers unverifiable, dynamic is correct. Directly validates our Bot F idea 001 filter: "minimum verifiable track record ≥6 months" isn't enough — we also need a *recent* edge signal (e.g., trailing 30-day P&L above trailing 6-month median).
2. **Priority execution is required for copy-trading.** If you're 15s behind the whale, you eat slippage. Polymarket blocks on Polygon at ~2s cadence. Realistic requirement: detect whale order within one block and submit inside the next block. That means dedicated WSS + dedicated RPC + pre-signed order templates.
3. **Volume spike as exit signal.** Article claims "3x normal volume in 10 min = whale exit trigger." The pattern (exit into volume rather than hold to resolution) is microstructurally legitimate — liquidity is cheapest to consume when there's a counterparty rush. Specific threshold (3x / 10 min) is testable and should NOT be adopted without backtesting.
4. **Liquidity timing window — "enter 4–8h after initial volume spike."** Rationale (vol drops after initial reaction, price hasn't fully corrected) is coherent. Specific window unverified. Worth testing against logged market snapshots.
5. **Category rotation.** Attention cycles through election → sports → crypto → politics. When a category is crowded, edge collapses there and appears elsewhere. Real phenomenon. Hard to operationalize mechanically; needs a concrete signal (e.g., rolling-30-day-edge per category, rotate when current-category edge < other-category-edge − threshold).

### What's marketing/fluff (do NOT act on)

- **Specific wallet addresses posted** (`0xd84c...`, `0xeebd...`, `0xf2f6...`, etc.). Seven addresses, all presented as "copy these." Could be: real whales pulled from the Polymarket UI (legitimately public), the author's own sock-puppet accounts, or random. **No endorsement.** If Bot F idea 001 gets approved, our wallet discovery builds its OWN ranked list from on-chain data using our own filters — we don't inherit someone else's list.
- **"Claude analyzed 14,000 wallets and flagged these edges."** Fabricated appeal to AI authority. Ignore.
- **Kreo.app endorsement.** Third-party paid copy-trading SaaS with "Priority Mode", custom exit rules, etc. Not vetted. Almost certainly takes a fee or cut. Not integrating. If we build copy-trading, we build our own execution layer using the existing ClobWrapper.
- **FOMO framing** ("window is closing", "start tonight", "October might be gone"). Classic copywriter pressure tactic. Our build follows the 4-gate graduation regardless of urgency.
- **Hero numbers in a linearly-escalating pattern** ($3.2k → $18.9k → $44.8k over 3/3/3 weeks). Too clean. Not evidence.

### Already in our codebase / ideas

- **Bot F idea 001 (whale copy-trading)** already has the right skeleton. This article sharpens three of the five entry filters:
  - Filter 1 was "≥100 trades / ≥6 months / Calmar ≥1.0." Add: **recent-edge check — trailing 30d P&L must be ≥80% of trailing 6m median monthly P&L.** This kills wallets whose edge is compressing out.
  - Filter 2 was "category-specific edge." Add: **attention-adjusted** — if the category's crowd-edge (average top-50-wallet ROI over 30d) has dropped >40% vs the 6m median, deprioritize that category entirely.
  - Filter 3 (position-size sanity) unchanged.
- **Volume-spike exit rule** is a new candidate exit trigger for Bot F idea 001. Add as a sub-feature: after entering a whale-copied position, monitor 10-min rolling volume; if it exceeds 3× the 1h baseline while we're in profit, close. Backtest before enabling.

### Actionable

- **[Bot F idea 001]** Extend the filter list per above (recent-edge check + crowd-edge-adjusted category filter). Update [docs/bot-f-ideas.md](bot-f-ideas.md).
- **[Bot F idea 001]** Add "volume-spike exit" as an optional exit rule. Backtest against 3 months of logged market data before enabling live.
- **[Infra]** If Bot F idea 001 is approved: the copy-trading latency budget is ~2 seconds (one Polygon block). That changes the infra story — may push us toward a dedicated Alchemy RPC or running a Polygon full node. Flag for ADR before any code.
- **[All bots]** Treat the ROI-compression dynamic as a durable fact. Every strategy we ship must have a mechanism to detect its own edge decay (rolling realized-edge vs baseline, alert when realized drops below threshold). This is a meta-feature worth adding to the shared portfolio module.

### Caveats

- Marketing articles are selected by survival — the author made money in the specific window they describe (or claims to). This tells us nothing about forward returns.
- The specific numbers (4–8h, 3× volume, 10 min) are author-chosen and may not be optimal or even correct. Treat them as a starting guess for backtest parameterization, not truth.
- Kreo.app and similar SaaS tools optimize the *marketing* of copy-trading, not the *edge*. A tool that lowers the barrier to copy-trading accelerates edge compression — using such a tool is itself a reason the edge decays. Building our own gives us a durable advantage: we see the decay in our own metrics and adapt, instead of being locked into someone else's abstraction.

### Operator decisions pending

- **D4:** Approve the two Bot F idea 001 filter additions (recent-edge, crowd-edge-adjusted category)? **[Ideas-level, low risk — adding to file now]**
- **D5:** Keep Bot F idea 001 zero-execution milestone (read-only wallet tracking for 2 weeks) as the only next step, OR add a backtest-harness milestone after 2 weeks? **[PENDING]**

---

## Entry 004 — Three-file copy-trading bot (Hunter / Mirror / Trigger) (2026-04-16)

**Source:** X post — anonymous "9 days, $300 → $5,812" copy-trading bot, written largely by Gemini CLI. Three linked GitHub repos (different authors): `echandsome/Polymarket-betting-bot`, `ent0n29/polybot`, `warproxxx/poly-maker`.
**Applies to:** Bot F (idea 001 — architecture + concrete thresholds)
**Framing:** The hero numbers ($300 → $5,812 in 9 days = 19.4× return, 66.7% WR on 216 trades) are not credible evidence. The *architecture* and *filter thresholds* are a clean specification of what Bot F idea 001 should look like, and they're what we actually want to take from this. Treat the linked repos as read-only references — if patterns are useful, we write them fresh rather than forking third-party code with unknown audit status.

### Architecture worth adopting: three decoupled modules

The article decomposes copy-trading into three roles connected by a Redis queue. This maps cleanly onto our existing `discovery.py / strategy.py / executor.py` pattern:

| Article name | Role | Online/offline | Our equivalent |
|---|---|---|---|
| Hunter | Ranks wallets on historical P&L, produces a ranked list | Offline batch (runs hourly or daily) | `bots/bot_f/discovery.py` |
| Mirror | Watches CLOB events for ranked wallets, fires signals on new positions | Online async, WSS subscriber | `bots/bot_f/signal.py` |
| Trigger | Consumes signals, applies risk/time filters, places orders | Online async | `bots/bot_f/executor.py` |

**Why decouple.** Hunter is expensive (scans historical trades) and doesn't need to be fast. Mirror is fast but stateless. Trigger is where the money actually moves and should be the smallest, most audited piece. Swapping Redis for a Python `asyncio.Queue` keeps Bot F self-contained on the bot LXC container without adding infra.

### Concrete filter thresholds (starting points for backtest)

**Hunter (wallet selection):**
- `min_trades >= 100` over 90-day lookback
- `win_rate > 0.62`
- `profit_factor > 1.8` (gross profit / gross loss)
- Rank by Sharpe (per-trade, not annualised); take top 40
- **Our additions (from Entry 003):** recent-edge check — trailing 30d P&L ≥ 80% of trailing 6m median monthly P&L. Attention-adjusted category filter: if category's top-50 rolling-30d ROI dropped >40% vs 6m median, demote

**Mirror (signal creation):**
- Dedupe signals within 60s window (prevents two hunters entering the same market from firing twice)
- Log every signal to a local file; never drop one silently
- On WSS drop: reconnect with exponential backoff

**Trigger (execution):**
- Per-trade cap: 3% of bankroll
- Per-market cap: 2 open positions max
- Spread filter: skip if bid-ask > 4¢
- **Signal staleness: skip if hunter's entry was > 90 seconds ago** — this is the most concrete operationalisation of "priority execution" in any source so far. Better than "within 1 Polygon block" as a practical target because it tolerates the bot LXC container latency
- Time-to-resolution: skip if <6 hours remaining
- **Position cap at 25% of hunter's own size** — prevents us from moving the book against ourselves and eating our own slippage
- Slippage buffer: +0.002 (20 bps) on the entry price for YES buys, −0.002 for NO buys (article only shows the YES side; the symmetric case matters)

### Code-quality issues in the article's snippets (do NOT copy verbatim)

- `client.create_and_post_order({...})` — simplified signature; the real py-clob-client API is `ClobClient.create_and_post_order(order_args, options)` and `token_id` is not the same as `market`. A market has two tokens (YES and NO) and the executor must resolve which token_id the hunter actually traded. Our existing [core/clob.py](../core/clob.py) ClobWrapper already handles this distinction correctly.
- `pl.col("pnl").mean() / pl.col("pnl").std()` labelled "sharpe" — this is a per-trade Sharpe with no annualisation. Fine for ranking across the same period; not a comparable Sharpe across timeframes. Relabel in our port.
- "Subscribe to the Polymarket WSS for fills on every address" oversimplifies. The public WSS exposes market-channel data; per-address fill events likely need either (a) subscribing to all markets and filtering client-side, (b) polling the graph, or (c) the Polymarket subgraph with websocket support. Needs verification against the py-clob-client docs before build.
- "Pull every trade from the public subgraph for the last 90 days" — at ~50k markets/7d (confirmed from our own backfill work), 90 days of trades is potentially many millions of rows. Subgraph pagination limits apply. Don't trust the 3-minute claim.

### What the article actually gets right beyond architecture

1. **"The bankroll rules are the whole game. Without them I'd have been rugged by a single bad hunter inside 24 hours."** This is the honest line in the article. A single whale with a blown-up edge can torch a naive copy-trader. Our Trigger risk filters are non-negotiable.
2. **Signal staleness as a hard filter.** 90 seconds old → skip. Prevents chasing whale footprints after the book has already adjusted.
3. **Self-sizing relative to the whale.** 25% of their size is a defensible ceiling. Scales naturally — if the whale is small, we're smaller; if the whale is huge, we cap at 3% of bankroll.
4. **the VPS provider CX11 Frankfurt at €3.49/mo** is a legitimately cheap EU-adjacent VPS option. Worth noting in the Bot E VPS decision alongside Render/Fly/Vultr. Frankfurt is a reasonable proxy for eu-west-1 latency-wise; actual ping needs measurement.
5. **Log every action to SQLite.** We already do this via [core/db.py](../core/db.py); article reinforces the pattern.

### Already in our codebase

- **ClobWrapper** ([core/clob.py](../core/clob.py)): defaults to GTC limit orders, handles token_id correctly, supports paper_override. All the primitives Trigger needs already exist.
- **Portfolio** ([core/portfolio.py](../core/portfolio.py)): realised/unrealised P&L, paper-fill fallback. What Trigger writes to.
- **Backtest harness** ([core/backtest.py](../core/backtest.py)): deterministic replay — can test Hunter filter thresholds and Trigger risk rules against logged data.
- **Backfill script** (previously-built): already collecting Polymarket markets. Needs extension to backfill per-wallet trades (not just markets) for Hunter to have training data.

### Actionable

- **[Bot F idea 001]** Adopt the three-module architecture. Update [docs/bot-f-ideas.md](bot-f-ideas.md) to reference Hunter/Mirror/Trigger alongside the discovery/signal/executor naming so both vocabularies are searchable
- **[Bot F idea 001]** Record the concrete thresholds (62% WR, 1.8 PF, 100 trades, 3% bankroll, 4¢ spread, 90s staleness, 6h TTR, 25% size cap) as **starting values for backtest**, not live defaults. Live defaults are set only after the 2-week read-only tracker + backtest harness produce calibrated numbers
- **[Bot F idea 001]** First concrete build: extend the existing backfill to pull per-wallet trade events, then write our own Hunter as `bots/bot_f/discovery.py`. Zero-execution for 2 weeks, output a ranked `hunters.json` equivalent as a DB table. Compare our list against any wallet addresses that surface in external sources — divergence is useful signal
- **[Bot E]** Add the VPS provider CX11 Frankfurt €3.49/mo to the VPS provider decision matrix in [docs/bot-e-spec.md](bot-e-spec.md) alongside Render/Fly/Vultr. Needs latency measurement before commitment
- **[Infra]** Replace the article's Redis dependency with Python `asyncio.Queue` for our Bot F port — keeps the bot self-contained, one fewer moving part to deploy/monitor, no performance cost at our volume

### Caveats

- **The 9-day $300 → $5,812 return is not credible evidence.** 19.4× compounding with a 66.7% WR on 216 trades would require extreme profit factor and aggressive compounding into a narrow window. Even if the numbers are technically accurate, they're cherry-picked and not a basis for sizing expectations
- **The three linked GitHub repos are by three different authors.** The article frames them as "the bot" but they're three separate projects the author is linking out to. Read them as references; don't assume they work together as described
- **"Gemini wrote it in one shot, I didn't touch a character"** is marketing. The code snippets shown have real bugs (token_id vs market mix-up, API signature drift). A real port requires a human who knows the CLOB API
- **Copy-trading's fundamental issue is edge compression** (Entry 003). This article doesn't address it. Our recent-edge + crowd-edge filters (added in idea 001) are what keeps the strategy working past the first month

### Operator decisions pending from this article

- **D6:** Adopt the Hunter/Mirror/Trigger decomposition as the canonical Bot F idea 001 architecture? **[Recommending YES — matches our existing bot pattern, decouples cleanly. Would update bot-f-ideas.md on approval]**
- **D7:** First concrete Bot F build step: extend backfill to per-wallet trades + write `discovery.py` (Hunter). Zero-execution, 2-week tracking window. Approve? **[PENDING — was already idea-001's plan, this article sharpens the specification]**
- **D8:** Add the VPS provider CX11 Frankfurt to the Bot E VPS decision matrix? **[Low-risk, adding to the spec now unless you object]**

---

## Entry 005 — Two-hemisphere 15-min BTC Polymarket bot (v96) (2026-04-16)

**Source:** @Gustafssonkotte on X, 2026-04-13. Claimed v96, iterated against specific losing trades with dated fixes. No paid CTA, no hero P&L, no affiliate links — highest-credibility article in this series so far.
**Applies to:** Bot E directly (this is a working implementation targeting the same 15-min BTC market). Some cross-applicable infra (confidence calibration, Chainlink Data Streams) applies to all bots.
**Framing:** A detailed architectural writeup of a bot competing in Bot E's exact target market. Code snippets are idiomatic and don't show the structural bugs of Entry 004's samples. No P&L numbers means the author isn't selling us anything — that's actually a trust signal. Treat the architecture as directly competitive evidence: if this is the standard, that's the bar Bot E has to clear.

### This article is evidence for a Bot E strategy pivot

The current Bot E spec ([docs/bot-e-spec.md](bot-e-spec.md)) targets a **t−60s to t−5s entry window** using CEX-Polymarket lag arb. This article describes a bot targeting the **t−10min to t−5min entry window** using order flow + technicals. These are **different strategies** on the same market:

| Dimension | Current Bot E spec | Article's bot |
|---|---|---|
| Entry window | Last 60 seconds | Minutes 5–10 of the 15-min period (i.e., t−10min to t−5min) |
| Signal source | CEX price vs Polymarket strike | Order flow imbalance + technical vote + regime classification |
| Infra requirement | eu-west-1 VPS colocation (<650ms E2E) | LXC-friendly (no sub-second CEX race) |
| Edge type | Arbitrage (near-certain resolution) | Directional prediction (5–10min before resolution) |
| Hit rate target | 85–95% | Not stated but Kelly math implies ~60–65% |

The article's bot runs a different strategy entirely. Neither strategy is wrong. But the article's strategy:
- Runs fine from our existing infra (the bot LXC container, no VPS)
- Is consistent with the OBI-first pivot already flagged in D1
- Has a much larger entry window (~5 min vs ~55s) giving more shots per day
- Doesn't require CEX colocation

**This reinforces D1 very strongly.** The market has (at least) two distinct strategies, and the non-colocation-dependent one is empirically real at v96 level maturity.

### Architectural patterns worth adopting

**Pattern 1: Two-hemisphere signal engine**

Split signals into two independent voters:
- **Left hemisphere** — pure technical analysis on 30s OHLC candles built from Chainlink ticks. SuperTrend, EMA, volume oscillators. Looks at what already happened.
- **Right hemisphere** — live market-state: CLOB book + orders_matched flow from Polymarket WSS. Looks at what is happening right now.

Neither outranks the other. A trade fires only at the intersection. This cleanly separates "price said X" from "book said Y" — so when they diverge, we skip rather than picking one. This is how to avoid overfitting to either feed alone.

**Pattern 2: Market-regime classifier with regime-dependent thresholds**

Six regimes: TREND_UP, TREND_DOWN, VOLATILE_TREND, VOLATILE_CHOPPY, SIDEWAYS, UNKNOWN. Each has different entry thresholds and indicator weights. The choppiness metric is clean:

```python
signs = [1 if closes[i] > closes[i-1] else -1 for i in range(1, len(closes))]
reversals = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
choppiness = reversals / max(1, len(signs) - 1)  # 0 = pure trend, 1 = pure chaos
dir_10m = closes[-1] - closes[0]
```

Rules: `choppiness < 0.45 AND |dir_10m| > 30` → VOLATILE_TREND (trade). `choppiness > 0.60` → VOLATILE_CHOPPY (skip). **Adopting this in Bot E blocks the "trade the churn" failure mode before it happens.**

**Pattern 3: PeriodTracker — observe before trade**

First 5 minutes of each 15-min period: bot observes, no entries. Records BTC direction every 10s, CVD trend, OFI, speed/acceleration. At entry window (mins 5–10), PeriodTracker outputs a 0.0–1.0 confidence verdict. If ≥ 0.60 AND agrees with candidate entry direction, the minimum BTC-move threshold drops by 20%. This is the concrete implementation of the "warm up before trading" pattern and solves cold-start at each interval boundary.

**Pattern 4: VETO system**

Some signals can hard-block an entry under extreme conditions. Consensus can *lift* an individual VETO if it's strong enough. But the **VOLUME VETO is absolute**: if all four volume signals simultaneously oppose direction, no trade is placed regardless of other consensus. This is how you build a multi-signal system without one noisy signal killing the book.

**Pattern 5: Synergy bonuses (additive, not multiplicative)**

When related signals agree simultaneously, add a fixed bonus to `synergy_score`. Three market-pressure signals agreeing → +X. ST + EMA agreeing → +Y. Six or more signals → MEGA bonus. All additive, not multiplicative (prevents runaway amplification when many weak signals align). Final `synergy_score` becomes one multiplier on confidence.

**Pattern 6: Confidence calibration via Platt scaling** ← implements Entry 003's edge-decay meta-feature

Every N trades, weighted linear regression of predicted vs actual hit rate per probability bucket. Bounded corrections: slope `a ∈ [0.5, 2.0]`, intercept `b ∈ [−0.15, 0.15]`. Applied to every new trade: `fair = a * fair + b`. **This is the exact mechanism we flagged as needed after Entry 003.** The article gives us a working implementation to port.

**Pattern 7: SmartKelly — Kelly with quality adjustments**

Base Kelly × multiplier where multiplier ∈ [0.5, 1.5]. Multiplier driven by:
- confidence tier (≥0.80 → +0.20, ≥0.72 → +0.12, etc.)
- vote_score (≥0.60 → +0.10, <0.10 → −0.10)
- market_quality × 0.20
- synergy_count × 0.03 (capped at +0.15)
- conflict penalty: −0.20 if fast/slow signals conflict
- memory_adj × 2.0 (pattern-match against past trade outcomes)

**This is how half-Kelly should actually work in Bot E.** Not `f_applied = 0.5 × f*` flat, but `f_applied = 0.5 × f* × quality_multiplier`. Operator-visible, each trade log shows which factors contributed.

### Infra details worth taking

- **Chainlink Data Streams** as primary BTC price source (institutional-grade WSS with HMAC auth, sub-second latency). Article claims sub-second latency. **Crucial advantage over CEX WS: Chainlink is the same source used for resolution.** Eliminates CEX-vs-Chainlink lag ambiguity. Bot E spec currently plans Binance WS primary + Pyth Lazer secondary — worth investigating Chainlink Data Streams access/pricing before we lock that in.
- **Fallback chain**: Chainlink Data Streams → Chainlink on-chain (Polygon RPC) → CEX APIs (Coinbase/Binance/Kraken). Multi-layer with strict priorities. We should adopt this structure regardless of primary choice.
- **Pre-warm at startup**: 35 candles loaded via 37 REST requests so indicators are live from iteration 1. Eliminates cold-start blind period. Adopt directly.
- **Config validation on startup**: 27+ parameters checked; bot refuses to start if invalid. Adopt directly — prevents "silently trading with wrong weights" failure mode.
- **Auto-claim via Safe.execTransaction calling redeemPositions on CTF Exchange**. V2-aware. Winning positions on Polymarket don't self-claim; this is the on-chain call pattern we'll need. Aligns with our V2 migration (OQ-008).
- **Two parallel Telegram channels**: private (full detail — edge, fair_prob, size, signal logs) and public (direction + confidence only). We already have the notify_daemon; this is the pattern for a public channel if we ever want one.

### Signals listed but not detailed (proprietary to the author)

The article names these without full implementation:
- Market-pressure signals (three of them; exact formulation not given)
- Vote score, fair_probability, market_quality
- SuperTrend + EMA confluence rule
- Four "volume signals" that collectively drive the volume VETO
- Signal memory pattern-matching scoring

Implication: the *architecture* is public, the *signal formulations* are the author's edge. We'd need our own signal set. Start minimal for Bot E v1 — OBI, SuperTrend, EMA, CVD, one volume oscillator. Add more only when real trades teach us what's missing.

### Already in our codebase

- **[core/clob.py](../core/clob.py)** — GTC limit orders, token_id handling. Covers pattern 11 (execution) except the on-chain claim.
- **[core/portfolio.py](../core/portfolio.py)** — realised/unrealised PnL. What the Platt-scaling calibrator reads from.
- **[bots/watchdog_daemon.py](../bots/watchdog_daemon.py)** — already silences wss.liveness per 1105f44. Pattern in place for adding Bot E liveness channel.
- **[bots/notify_daemon.py](../bots/notify_daemon.py)** — Telegram private channel exists. Public channel would be additive, not replacement.

### Do NOT cargo-cult v96 into Bot E v1

v96 is 96 versions of iteration against specific losing trades. We do not have that corpus. Starting v1 with all features from v96 means:
- Most features aren't validated against our data
- Tuning parameters without data is guessing
- Debugging surface area is huge from day 1
- Adding features later is easy; removing them is painful

**Bot E v1 starting scope (Claude recommendation):**
- One hemisphere at first: right-hemisphere OBI (pattern from Entry 002 strategy #2, code snippet from this article). Ship the simplest version that generates signals
- Single regime detector (choppiness ratio) — skip VOLATILE_CHOPPY hard
- Simple Kelly with `KELLY_FRACTION = 0.25` config-driven (no quality multipliers yet)
- Config validation on startup
- Chainlink Data Streams integration deferred — use CEX WSS + Chainlink on-chain as v1 price stack
- Calibrator scaffolding in place but off by default (needs 100+ trades before it's even useful)
- Two-hemisphere, PeriodTracker, synergy bonuses, signal memory, VETO system → **phase 2+**

Ship v1 fast, let real losing trades drive the feature list.

### Actionable

- **[Bot E]** Strongly reinforce D1: pivot Bot E v0/v1 to the order-flow-directional strategy described here (and Entry 002 strategy #2), NOT the CEX-lag arb from the current spec. Concrete entry window: mins 5–10 of each period (t−10min to t−5min before resolution). CEX-lag becomes phase-3 module iff we ever colocate
- **[Bot E]** Port the `ws_orderbook_imbalance()` pattern directly. It's 15 lines and it's the core signal. Threshold `abs(imbalance) > 0.20` is a starting point; calibrate against our own logged data
- **[Bot E]** Adopt the choppiness-ratio regime detector as the only v1 filter. Skip VOLATILE_CHOPPY, trade everything else. Add more regimes in phase 2
- **[All bots]** Adopt the Platt scaling calibration pattern as the shared edge-decay monitor (flagged as meta-feature in Entry 003). Lives in a new `core/calibration.py`. Every bot's executor reads its coefficients and applies them to fair_prob before sizing
- **[Bot E]** Replace flat half-Kelly with SmartKelly-style quality multiplier. Start with just two factors (confidence tier + vote_score) to match v1 feature set; add more as real trades justify
- **[Bot E]** Config validation on startup: 27+ params is a lot, but even a 10-param sanity-check in `config.py` prevents shipping with wrong values. Include all risk caps, edge thresholds, and Kelly params
- **[Bot E]** On-chain claim via Safe.execTransaction → redeemPositions on CTF Exchange is a required V2 implementation detail. Build stub early, test against Amoy (once restored) or forked Polygon state
- **[Infra]** Investigate Chainlink Data Streams access/pricing. If affordable and accessible, it beats Binance WS for this use case because it's literally the source used for resolution — zero lag ambiguity. Deferred until operator decision

### Caveats

- The article's bot is direct competition. Reading it gives us architectural parity but not signal parity — the author's specific signal formulations aren't disclosed. We'd still need to derive our own.
- v96 implies the author has iterated against 95 prior versions' losing trades. Our v1 will lose money in ways their v1 did. Plan for that — the Bot E paper gate (200 trades) is where we learn what WE specifically break on
- No P&L numbers disclosed. We can't independently verify the strategy is profitable at the described architecture; we can only verify the architecture is internally coherent and matches the academic patterns for order-flow-directional trading
- Chainlink Data Streams may require an approved application. Confirm access before committing to it as the primary feed
- The PeriodTracker window (5–10 min entry) assumes the market is live and liquid from minute 0. Very new 15-min markets may have thin books in the first 5 min even with our observation-only logic running — no signals until the book fills
- "VOLUME VETO is absolute" is attractive but requires that our four volume signals are independent. If they're all derived from the same underlying feed, the VETO is just one signal in disguise

### Operator decisions pending from this article

- **D9:** Pivot Bot E v1 entry window from t−60s to t−5min–t−10min, and pivot strategy from CEX-lag arb to order-flow-directional (OBI + technical vote)? **[Strong recommendation: YES. Reinforces D1. This is the most durable Bot E decision from the full article series]**
- **D10:** Adopt Platt scaling calibration as a shared `core/calibration.py` module applied across all bots? **[Recommendation: YES. This is the edge-decay defense we flagged as a meta-feature in Entry 003. The article gives us working reference code]**
- **D11:** Investigate Chainlink Data Streams as primary BTC feed (may have access/cost requirements we don't know yet)? **[PENDING — needs operator to confirm willingness to pay for a data feed if there's a subscription]**
- **D12:** Accept the v1 scope restriction (OBI-only signal, choppiness regime, config-validation, basic SmartKelly-lite) and defer two-hemisphere / PeriodTracker / synergy / signal memory / VETO system to phase 2+? **[Recommendation: YES. Ship a minimal v1 that reaches the backtest gate; let real data drive feature priority]**

---

## Entry 006 — "Little Rocky" weather-bot guide (2026-04-16)

**Source:** @theparuchh on X, 2026-04-14 ("The $100 Polymarket Bot That Could Make $100K+")
**Applies to:** Bot D (review only — already live, do not modify without ADR), conceptual spin-offs (Analyst Bot / Scout Bot)
**Framing:** 90% of this article is a beginner's how-to (Mac Mini setup, Homebrew, Claude Code install, Telegram bot, basic weather-forecast-vs-market math). All of that is irrelevant to us — our infrastructure is the homelab hypervisor/LXC and we already have Bot D in production. Skimming to extract only the handful of items not already in our stack.

### Already in our Bot D — confirmed, nothing to do

- GFS ensemble as primary weather source, fallback API chain
- One-bet-per-event enforcement (city + date) — memory confirms Bot D has this as the most critical rule
- Edge threshold on each trade, Kelly sizing, bankroll caps
- Circuit breaker on daily loss / loss streak
- Telegram alerts scoped to real events only (post-1105f44 we actively silenced liveness-noise channels)
- GTC limit orders via py-clob-client
- SQLite trade log

### Three bits worth noting

**1. FOK-with-GTC-fallback execution pattern.** Article's prompt specifies "FOK orders via py-clob-client (GTC fallback 2% slippage)." Fill-or-Kill as the preferred mode — order fills at the quoted price or not at all — with GTC as the graceful degradation when FOK can't find a counterparty. [core/clob.py](../core/clob.py) currently defaults to `OrderType.GTC`; the FOK mode is also supported in the enum (line 77). Adding FOK-first-with-GTC-fallback as an option on the ClobWrapper is a clean, cross-bot improvement — better execution quality on thin markets where GTC sits and gets picked off. Applicable to Bot E primarily (short-hold scalping) and Bot F (copy-trading). **Not proposing to touch Bot D** since it's live, but this is a candidate for the shared wrapper.

**2. 12-of-20 trailing-loss circuit breaker.** Article's risk_manager uses "stop if 12/20 lost" as a concrete trailing-window rule, alongside the daily-loss rule. Different mental model from our rolling-WR approach — a hard count over a fixed window rather than a moving-average threshold. Simpler to reason about, faster-reacting to a bad streak. Worth considering for Bot E v1 alongside the consecutive-loss halt already in the spec.

**3. Two conceptual follow-on bots worth parking as ideas (not building now)**

- **Analyst Bot.** Reads completed-trade history, identifies which cities / hours / edge-buckets / markets are most profitable, and after every N trades rewrites the calling bot's config. Different from Platt calibration (Entry 005, which corrects `fair_prob`) — this corrects *operating parameters*: edge_threshold, KELLY_FRACTION, per-market caps, etc. Natural next step after we have a shared `core/calibration.py`. **Parking as a feature idea** (append to a new section in [docs/bot-f-ideas.md](bot-f-ideas.md) or a new `docs/analyst-bot-ideas.md` — TBD).
- **Scout Bot.** Scans X and GitHub every N hours for new strategies, open-source bot updates, and profitable trader wallets. Article claims it found a new ensemble model that went live overnight and improved WR by 6%. This is a **research-assistant pipeline**, not a trading bot — conceptually what Claude is doing manually right now while reading these articles. Not obviously worth automating until we have a clear signal that manual review misses things.

### Not worth taking

- The 5-hour/$100/zero-coding framing — marketing.
- Hero numbers ("$313 → $414k in one month"). Hero.
- "The bot doesn't sleep. Doesn't hesitate." — filler.
- Telegram bot creation, Mac Mini setup, Homebrew, Python install — all the homelab hypervisor-irrelevant.
- The full prompt the author used with Claude Code — we already have Bot D; we don't need to rebuild from scratch.

### Caveats

- Author explicitly says Bot D is v1 and he has never run at scale long enough to know if edge persists. "Edge on weather markets has been consistent for months" is his personal anecdote, not evidence.
- "$1,000 → $24,000 on London temperatures alone" — unverified; likely a single winning streak cherry-picked.
- The "Scout Bot found a new ensemble at 4am, integrated by morning" claim is not credible as described (no bot has a demonstrated capability to identify, evaluate, integrate, and backtest a new weather model unattended) — treat as narrative.

### Actionable

- **[Shared infra]** Add a `prefer_fok` flag on [core/clob.py](../core/clob.py) ClobWrapper — pass FOK to py-clob-client, on rejection retry as GTC with a configured slippage tolerance. Enables Bot E/F to use better-quality execution without touching Bot D. **Low-risk shared-infra addition; worth doing regardless of D-series decisions**
- **[Bot E v1]** Add a trailing-window loss rule (e.g. "halt if ≥12 of last 20 closed trades are losers") to the Bot E risk manager alongside the consecutive-loss halt already in the spec. Keep both; they fire on different failure modes
- **[Ideas file]** Append "Analyst Bot" concept to a new section in [docs/bot-f-ideas.md](bot-f-ideas.md) or a sibling `docs/meta-bots-ideas.md`. Defer actual build until after shared calibration module (D10) is decided

### Operator decisions pending from this article

- **D13:** Add `prefer_fok` flag to [core/clob.py](../core/clob.py) ClobWrapper as a shared-infra improvement? **[Recommendation: YES, low-risk, benefits Bot E and Bot F without changing Bot D behavior]**
- **D14:** Append Analyst Bot and Scout Bot concepts to a Bot F-style ideas file? Park only, not build. **[Low-risk doc change, adding on approval]**

---

## Entry 007 — 5 strategies + 3 golden rules (2026-04-16)

**Source:** @maqxbt on X, 2026-04-08 ("5 Strategies for Stable Earnings on Polymarket")
**Applies to:** conceptual overview; most content overlaps earlier entries. Primary new value is the three "golden rules" at the bottom.
**Framing:** Beginner-oriented overview article. Lists 5 strategies that are all already better-documented in Entry 002 (VALIX's 9-type taxonomy) and 3 operator rules. Low novelty on strategies, real signal on the rules. Short entry.

### Strategies — overlap with prior entries

| Article's strategy | Maps to (prior entry) | Genuinely new? |
|---|---|---|
| 1. Niche edge (specialised knowledge) | (no direct prior) | **Yes — see below** |
| 2. Fading the chaos (emotional overreaction) | Entry 002 strategy #1 (arb), and generally Bot A's longshot fade on NO | Partial — "fade news panic" is a timing overlay on existing strategies |
| 3. "98% sure" near-resolution | Entry 002 strategy #4 (near-resolution 99c), Entry 005 | No — already covered |
| 4. Cross-platform arbitrage | Entry 002 strategy #5 — but this article says cross-PLATFORM, not cross-market within Polymarket | **Yes — new angle** |
| 5. Following the smart money (whale watching) | Entry 003, Entry 004; Bot F idea 001 | No — already covered in detail |

### Two bits with genuine novelty vs prior entries

**1. Niche edge — monetise specialised personal knowledge.**
The beginner mistake is trading the loudest / most-tracked markets (US presidential, major crypto). Edge hides in lower-attention categories: regional sports, local politics, niche entertainment, domain-specific tech. Retail traders don't bother; market-makers don't have specialist expertise. If you know a domain deeply, the market may be mispriced before the crowd updates. This is implicit in Entry 002 strategy #9 (probability model) but not called out as a *category-selection* heuristic.

**For Bot F:** adds a filter to idea 001 (whale copy) and to future prob-model bots — **prefer lower-attention categories** for strategy validation first. Specifically: avoid US presidential + major-crypto markets for the initial paper run because they're the most-crowded and least-forgiving of our latency. Pick two niche categories the operator has domain knowledge in, validate there, then consider broadening. Worth a sub-filter in the Hunter ranker: weight wallets by the *category concentration* of their winning trades — a wallet consistently printing in one niche beats a generalist.

**2. Cross-PLATFORM arbitrage (Polymarket ↔ competitor venues).**
Article claims "82c YES on one platform vs 12c NO on another → $0.94 total cost for guaranteed $1 payout, 6% risk-free." This is **different from Entry 002 strategy #5** (which was cross-market *within* Polymarket, e.g., totals vs spreads on the same game). Here the arb is across competing prediction venues (Polymarket ↔ Kalshi ↔ PredictIt etc).

**Already on our scope-creep kill list** per [CLAUDE.md](../CLAUDE.md) §"Out-of-scope": *"Cross-venue arbitrage (Polymarket ↔ Kalshi)"*. Not reopening. Flagging only because the article raises it and we should have a single source of truth — the kill-list entry stands. Reasons unchanged: added KYC surface on a second venue, second wallet, second auth stack, second latency profile, not worth the infra for a 6% arb that closes in seconds against HFT competitors.

### Three golden rules (operationally useful)

1. **Always read the market resolution criteria.** Article example: "Will AI sue a human?" — the market resolved on "lawsuit filed in court," even though legally meaningless. **Translation for us:** every new market category Bot F considers must have its *resolution source* logged explicitly in the strategy config. Weather → Chainlink/NOAA (Bot D uses METAR + NWS per memory). Crypto price → Chainlink Data Streams (relevant to Bot E, see Entry 005). Political → UMA dispute process (Bot B's wheelhouse). If a strategy's resolution source can't be stated in one sentence, don't trade it.

2. **Check liquidity.** Article: "$50 volume markets trap you in the position because there's no buyer on exit." This is **already in Bot D** (volume filter) and **already in Bot A** (book-depth filter per memory). Worth codifying as a *shared* `core/liquidity.py` check: minimum 24h volume + minimum book depth within N cents of mid. Entry 002 strategy #2 (OBI, Bot E v1 target) genuinely cares about this too — a thin book is where OBI signals print, but also where we can't exit.

3. **Don't chase 50x returns.** Article: "2c → $1 is lottery. Real money: 1-5% repeated edges with compound interest." This is the Kelly-compound thesis from Entry 001 restated. **Tension with Bot A**: Bot A is explicitly a longshot fader (buys NO at ≥95%; equivalent to buying YES at ≤5% and holding short). The current Bot A strategy is arguably the opposite of this rule at the trade level, but the PORTFOLIO-level thesis holds because Bot A takes many small bets relying on base-rate resolution. The rule doesn't apply bot-to-bot; it applies trade-to-trade. Keep the rule as a gate for new strategy proposals, not an indictment of Bot A.

### Actionable

- **[Bot F idea 001]** Add a "category concentration" factor to the Hunter ranker — bonus points for wallets whose profitable trades cluster in one or two niche categories. Deprioritize generalists in the same top-40. Matches Entry 003's crowd-edge-adjusted category filter (they compose: prefer wallets who are *specialists in uncrowded categories*).
- **[Bot F first paper run]** Pick 1–2 niche categories for initial validation (e.g., sports sub-niches the operator watches, regional politics) rather than US-presidential or major-crypto. Concrete list defer to operator.
- **[Shared infra]** Consider lifting the liquidity filter out of per-bot executors into a shared `core/liquidity.py` check. Low priority — not broken, just duplicated. OK to park.
- **[Strategy config discipline]** Require every strategy config (Bot D, Bot E v1, Bot F idea 001, future bots) to carry a one-line `resolution_source` field. Cheap, catches misaligned markets at config-review time.

### Caveats

- The 98%-sure strategy's "never more than 10% per event" rule is much looser than our 2.5% / 3% per-trade caps. Not a contradiction — the article is writing for a general audience with no kill-switch infra. Our tighter caps still apply.
- Cross-platform arb at 6% is an attractive-sounding number but the article glosses over withdraw fees, funding moves between venues, and the window (seconds) during which both legs stay mispriced. Empirically the net is far lower than the advertised spread. CLAUDE.md kill-list decision stands.
- Article gives no sample sizes, no dates, no wallet examples. Lowest-evidence article in the series. The three golden rules transcend the article's weakness because they're operator wisdom, not claimed results.

### Operator decisions pending from this article

None. Article confirms things we already do; the actionable items are small and advisory.

---

## Entry 008 — "The Math That Made $1M+ for Quant Traders" / Markov-Chain Framing (2026-04-16)

**Source:** @0xRicker on X, 2026-04-16 (article link; text + 4 embedded equation screenshots). Post ID `2044722741706678282`.
**Applies to:** Bot E (modest, v2+ only), Bot F (single wallet-callback datapoint), Bot C (moderate — alternative to GBM modeling, but deferred), all bots (cautionary tale on Kelly fraction)
**Framing:** Well-dressed Markov-chain formalisation of what is ultimately the same tail-prob fade + near-resolution edge we've already captured in Entries 002, 004, 005. Math is real, application is selective, P&L numbers are survivorship-biased, **Polymarket profile links carry `?via=track` affiliate-attribution tracking** (so the author earns engagement attribution on every click). Includes a cross-article wallet callback (`0xeebde7a0…` = same wallet @bl888m pushed in Entry 003).

### Core claims and their math

1. **Markov transition matrix P** — 4×4 matrix where `P[i][j]` = P(next state = j | current state = i). Rows sum to 1. Real math; been in the literature since 1906 (Markov).
2. **Arbitrage gap entry trigger** — `Δ^(w) = p̂^(w) − q^(w) ≥ ε` where q is market-implied, p̂ is model estimate for window w. Enter when gap ≥ ε. **Same concept as Entry 001 Kelly (edge = p − m).**
3. **State persistence filter** — `p_(j*,j*) ≥ τ = 0.87` where `j* = argmax P[i][j]` is the most-likely next state. Must hold *simultaneously* with #2. Intended to suppress noise-driven signals.
4. **Compounding under reinvestment** — `V_T = V₀ × e^(N(T) × r̄)` where `r̄` = mean log-return per trade. Standard math.
5. **Claimed per-trade returns:** Bonereaper 0.038%, 0xe1D6b514 0.031%, 0xB27BC932 0.033% — all well under 0.04%. `N(T) ∈ [12,866, 18,915]` trades over 30 days.
6. **Kelly criterion at f* ≈ 0.71** — claimed as "the exact point where growth is maximised without risking ruin."
7. **Multi-asset variance reduction** — bot 0xB27BC932 trades 5 assets (BTC+ETH+SOL+BNB+XRP) on 5-min windows, claimed σ reduction of 55%.
8. **"Markets priced by humans; humans aren't online at 3AM watching 5-min BTC"** — same thesis as our Bot E OBI pivot (Entry 005, ADR-022).

### Credibility grade: LOW-TO-MEDIUM

Breaks down into:

- **Math is real** (Markov chains, Kelly, compounding, variance reduction).
- **Application is selectively sloppy.** The transition matrix shown in the image has max diagonal 0.62, which would NEVER satisfy the claimed entry threshold of `p_(j*,j*) ≥ 0.87`. The article is showing an illustrative matrix that is internally inconsistent with its own entry trigger. Either cherry-picked as "not the live case" or narrative convenience.
- **P&L numbers are survivorship-biased hero framing.** Claimed $1.33M / 30 days across three unverified wallet addresses. Same pattern as Entries 003 (@bl888m / Kreo.app) and 004 (three-repos-framed-as-one-bot). No dated iteration history, no loss transparency.
- **Kelly `f* = 0.71` is reckless.** Half-Kelly (0.50) is already aggressive. Peer review for Bot E (Grok, Codex) explicitly calibrated to 0.10–0.50 range; 0.71 is where the quant-blowup post-mortems live. A stranger on X telling you 0.71 is "the exact point where growth is maximised without risk of ruin" is not a source you copy.
- **`0.034% per trade net of fees` claim requires maker-only execution.** Polymarket 2026 dynamic fees (ADR-022 verification) peak at 1.80% for crypto takers at 50¢. At 83–97¢ entry prices, taker fee is 0.22–1.22% — so 0.038% *net* per trade requires maker rebate on every fill. Article doesn't say maker-only anywhere.
- **Affiliate-tracked Polymarket profile links** (`?via=track` suffix). Author earns engagement attribution on every click. Doesn't invalidate the math, but contextualises intent: CTA-driven, not analytical.
- **Cross-article wallet callback.** `0xeebde7a0…` appears in BOTH this article AND Entry 003 (@bl888m / Kreo.app). Two different authors, different framings, same wallet. Either a genuinely successful wallet multiple observers noticed, or a coordinated promotional network.

### Independent verification against our own Bot F Hunter (2026-04-16)

**`0xeebde7a0…` is NOT present in our Hunter rankings.** Fails the filter (win_rate > 62% / profit_factor > 1.8 / ≥100 trades). Under our independent scoring, the wallet the article recommends is not classifiable as alpha. **Do not whitelist from this article.**

### What reduces to edges we already know

- "High-persistence state + gap trigger" → **trade near-resolution 99¢ markets** (terminal state is self-persistent) where model says true p → 1.00. That's Entry 002 strategy #4 (anon-fake near-resolution bot) dressed up in Markov notation.
- "Humans not watching 3AM 5-min BTC windows" → Entry 005 (v96 / @Gustafssonkotte), ADR-022 Bot E OBI pivot thesis.
- Multi-asset variance reduction → BTC→BTC+ETH+SOL expansion already in Bot E roadmap.

### Actionable by bot

| Bot | Relevance | Action |
|---|---|---|
| A — Longshot Fade | none — `YES ≤ 5¢` filter already captures Markov's "high-persistence tails" without matrix overhead | ignore |
| B — Oraclemangle Kelly | negligible, except 0.71 Kelly as a "what not to do" | ignore; keep fractional Kelly small |
| C — Pyth ingest | moderate — Markov is a legitimate alternative to current GBM modeling for short crypto windows; BUT `price_collector.py` schema flaw (OQ-031) is a prerequisite; AND Pyth decision is the more urgent gate | log as candidate Bot C v2 direction; do not act until OQ-031 + free-pyth test resolve |
| D — Weather | none — article is crypto-specific | ignore |
| E — BTC OBI | modest, v2+ only — Markov transition-matrix regime classifier is a richer generalisation of Bot E v1's binary choppiness gate; park for post-Phase-0d ONLY if calibration shows binary is insufficient | Bot E v2+ backlog |
| F — Whale Copy | single datapoint: cross-article wallet callback; Hunter already tested + rejected `0xeebde7a0…` | none — Hunter's verdict is the verdict |

### Caveats

- The 0.87 persistence threshold is plausible in principle (near-terminal states), but the article's own illustrative matrix fails to reach it, so the number is unverified.
- Multi-asset variance-reduction math assumes asset-return independence. BTC/ETH/SOL are highly correlated; claimed 55% σ reduction is optimistic unless the joint distribution is explicitly modeled.
- 18,915 trades in 30 days = 26/hr non-stop. Feasible with 5-min windows × 5 assets × rapid-fire entries, but every one needs independent Markov re-estimation or the matrix staleness creates latent drift.
- `Theorem 2.1` at the bottom (structurally self-sustaining edge) is marketing, not a theorem. No arbitrage persists in perpetuity without new entrants being priced out.

### Operator decisions pending from this article

- **D23**: When Bot E v2+ evaluates regime-classifier upgrades (post-Phase-0d, only if binary gate insufficient), compare Markov transition matrix against alternatives (HMM, regime-switching GARCH). **[PENDING — do not act until Phase 0d completes]**
- **D24**: Bot C modeling approach — keep current GBM or pivot to Markov transition matrix? **[PENDING — blocked on OQ-031 schema fix + free-pyth decision at 2026-04-22]**

---

<!-- Append new entries here as articles arrive. Keep each entry self-contained so a single grep finds everything the source contributed. -->
