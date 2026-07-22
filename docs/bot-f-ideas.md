# Bot F — Longer-Hold Strategy Ideas

**Status:** Ideas bucket. No code. Not yet approved.
**Last updated:** 2026-04-16
**Owner:** operator (scope) / Claude (evaluation + distillation)

Bot F is the parallel vehicle to Bot E. Where Bot E targets seconds-to-minutes scalps on mechanically-resolvable markets (crypto price feeds), Bot F targets hours-to-weeks holds on fundamentally-driven markets where the edge compounds slowly and the operator tolerates longer capital lock-up.

This file accumulates candidate strategies as they surface during article review. Entries here are **not approved features**. They are research-backed opportunities to evaluate, backtest, and then pitch for inclusion.

---

## Scope guardrails

Bot F MAY:
- Hold positions for hours, days, or weeks
- Use news/sentiment/on-chain signals to size into political, sports, macro, or event markets
- Copy-trade whale wallets with quality filters (see idea 001)
- Combine multiple signal families per trade (e.g., whale entry + news confirmation + stale CLOB price)

Bot F MUST NOT (without explicit operator approval):
- Trade on markets Bot A/B/C/D already cover without a conflict-resolution rule
- Share a hot wallet with Bot E (separate risk profile)
- Skip the same 4-gate graduation pattern Bot E uses (backtest → paper → $100 live → scale)

---

## Ideas

### 001 — Whale watching + filtered copy-trading

**Source seed:** operator, 2026-04-16 (Bot E branch init)
**Status:** Phase 0 (Hunter) approved for build — 2026-04-16 after Grok + Codex peer review.

**CRITICAL FRAMING (post peer-review, 2026-04-16):** Bot F is a MEASUREMENT-FIRST system, not an execution bot. The 2-week paper phase is a data-purchase decision, not a delay before live trading. If the collected data shows edge is already dead, we never build Trigger and save 2-4 weeks of execution code. Codex pushed confidence to 2/5 citing the crowded 2026 copy-trading ecosystem (PolyProbs, WhaleTrail, PolyCopyTrade all live).

**Core idea.** Identify wallets with sustained, verifiable outperformance on Polymarket. When they open a position, enter the same side with size scaled to Kelly + confidence in the whale's track record.

**Why it might work.**
- Polymarket is public. Every wallet's history is readable via Gamma + on-chain Polygon events.
- Some whales have genuine edges (insider info on political/sports markets, superior models on crypto, faster news ingestion). Copying them with lag still captures most of the edge if you're quick enough.
- Markets with low liquidity let a whale move price — following adds slippage but you're often still in the money if you gate on their track record.

**Why it might not.**
- Survivor bias: the wallets you notice are the ones that won. Their next trade may be random.
- Copy-lag: if you're 3 minutes behind the whale and the market is thin, you eat their footprint.
- Whale splits orders across wallets; you may miss half the position.
- Some public "$300 → $414k" style wallets are fabricated or single-lucky-break. Bot E spec already flags: do not copy-trade unverified wallets.

**Filters to consider before any copy trade.**
1. Minimum verifiable track record (e.g., ≥100 trades, ≥6 months, Calmar ≥ 1.0) **AND recent-edge check**: trailing 30d P&L ≥ 80% of trailing 6-month median monthly P&L. Kills wallets whose edge is already compressing out (see [bot-knowledge.md Entry 003](bot-knowledge.md))
2. Category-specific edge (a whale good at politics may be terrible at sports) **AND crowd-edge-adjusted**: if the category's top-50-wallet rolling-30d ROI has dropped >40% vs 6-month median, deprioritize the category — copy-trading saturation has likely killed the edge there
3. Position size sanity (skip if their position is >5% of market depth — they ARE the market)
4. Opposite-side sharp check: is any known-smart counterparty taking the other side?
5. Time-to-resolution (copy only if ≥4 hours remain — gives you catch-up room)

**Exit rules beyond resolution (optional, backtest first).**
- **Volume-spike exit:** after entering, monitor 10-min rolling volume. If it exceeds 3× the 1-hour baseline AND we are in profit, close. Rationale: whales exit into liquidity rushes rather than holding to resolution; capital-redeployment beats the small remaining yield. Specific 3× / 10-min thresholds are placeholders until backtested (see [bot-knowledge.md Entry 003](bot-knowledge.md)).

**Infrastructure cost of doing this right.**
- Copy-trading latency budget is ~2 seconds (one Polygon block). Detecting a whale order after the block lands and getting our order into the NEXT block is the minimum bar. Behind that, we eat slippage — this is why @bl888m's article sells "Priority Mode" as a feature. Our equivalent: dedicated Alchemy/Infura RPC (free tier) + Polymarket WSS subscription + pre-signed order templates with only the whale-derived params filled at submit time. May need an ADR on infra before any code.

**Open questions.**
- Is the on-chain wallet → trader identity graph queryable at scale, or do we have to build an indexer?
- Can we subscribe to a wallet's CLOB activity in real time, or only via periodic polling?
- What's the latency distribution of whale trade → our detection → our entry?

**Next step if pursued.** Build a read-only wallet-tracking module that logs top-500-by-P&L wallet trades for 2 weeks with zero execution. Measure detection-to-entry latency and a synthetic "if we'd copied" P&L curve, gated by the filters above. Then pitch for formal approval.

**Reference architecture (from [bot-knowledge.md Entry 004](bot-knowledge.md)).** Three decoupled modules:

| Module | Role | Maps to |
|---|---|---|
| Hunter | Offline ranker; scores wallets on win_rate, profit_factor, Sharpe, recency; outputs ranked table | `bots/bot_f/discovery.py` |
| Mirror | Online WSS subscriber; fires deduped signals when a ranked wallet opens a new position | `bots/bot_f/signal.py` |
| Trigger | Online consumer; applies risk/time filters, sizes, places limit orders via existing ClobWrapper | `bots/bot_f/executor.py` |

Use Python `asyncio.Queue` between Mirror and Trigger (no Redis dependency).

**Starting thresholds for backtest (NOT live defaults — live values come from the 2-week tracker + backtest calibration).**

Hunter:
- `min_trades >= 100` over 90-day lookback
- `win_rate > 0.62`
- `profit_factor > 1.8`
- Rank by per-trade Sharpe; take top 40
- Plus the recent-edge + crowd-edge filters above

Mirror:
- Dedupe within 60s window (same market, any ranked wallet)
- Log every signal; never drop silently
- Exponential backoff on WSS reconnects

Trigger:
- ≤3% of bankroll per trade
- ≤2 open positions per market
- Skip if spread > 4¢
- Skip if signal age > 90s (concrete "priority execution" target, achievable on the bot LXC container)
- Skip if time-to-resolution < 6h
- Cap size at 25% of hunter's own position size
- Slippage buffer: +0.002 on YES buys, −0.002 on NO buys

---

### 002 — Cross-market arbitrage on sports (totals / spreads / BTTS)

**Source seed:** [bot-knowledge.md Entry 002](bot-knowledge.md), @RetroValix dataset, wallet example: swisstony ($2.85M → $5.56M)
**Status:** Ideas-only. Significant research exists — see [docs/archive-little-rocky/structural-arb-research.md](archive-little-rocky/structural-arb-research.md) and [arxiv-structural-arb-comparison.md](archive-little-rocky/arxiv-structural-arb-comparison.md).

**2026-04-16 update:** Polymarket shipped an official sports WebSocket (`docs.polymarket.com/market-data/websocket/sports`) with live scores/periods/status, no auth required. This LOWERS the data-plumbing burden for this idea substantially — prior "paid Sportradar feed" concern is partially resolved. Atomicity + thin-book risks remain.

**Core idea.** Related sports markets (totals vs spreads vs both-teams-to-score) are logically constrained. When one moves and the other lags, buy the lagger on the side that must move to restore consistency.

**Why it might work.** Sports markets on Polymarket are fragmented by market type even though the underlying distribution is shared. Bookmaker-style structural constraints are well-understood; a small edge in repeated trades compounds fast.

**Why it might not.** Cross-market execution is atomicity-critical — if one leg fills and the other doesn't, you're left with unhedged directional exposure. The swisstony ROI (2×) is modest because of slippage at their scale; at our scale the edge might be higher OR might not clear fees.

**Next step if pursued.** Port the arxiv constraint math into a research module, backtest on 3+ months of logged sports market snapshots. Do NOT execute until backtest confirms positive EV after realistic fill models.

---

### 003 — Sports repricing on state change

**Source seed:** [bot-knowledge.md Entry 002](bot-knowledge.md), wallet: gatorr ($200k → $1.9M)
**Status:** Ideas-only. Requires sports data subscription.

**Core idea.** When the score/possession/time-remaining changes, the fair probability of each market outcome shifts. If the Polymarket book hasn't repriced yet (lag of seconds to minutes), buy the side with the freshly-created edge.

**Why it might work.** Entry zone 48–52c (roughly coinflip markets) has the most sensitivity to state changes — small probability moves translate to big price moves. Sports data is cheaper than crypto/political real-time data.

**Why it might not.** Requires a live game-state feed (ESPN/Sportradar API). That feed has its own latency and cost. Model error in the fair-value calculator = direct P&L hit.

**Next step if pursued.** Evaluate sports data provider latency/cost. Build a fair-value calculator for one specific market type (e.g., NBA totals) with >100 historical games of training data before any paper trading.

---

### 004 — Directional hedge (skewed 82/18 pattern)

**Source seed:** [bot-knowledge.md Entry 002](bot-knowledge.md), wallet: tradecraft ($17k → $213k, tennis)
**Status:** Ideas-only. Architecturally close to Bot B.

**Core idea.** When you have a directional opinion and real edge, don't go 100% — go ~82% on the dominant side and ~18% on the opposite as a hedge. Reduces variance at a modest cost to EV. Over many trades, the Sharpe improvement is significant.

**Why it might work.** Tennis example: median dominant share 82.8%. Tennis has many discrete events (match, set, break-point markets) where skewed hedging provides clean risk control. Same logic extends to MMA, boxing, individual events.

**Why it might not.** If Bot B already does directional trading with its own sizing rules, we don't want to duplicate. Unless Bot F targets a *different* market category (sports vs Bot B's geopolitics/politics) this is a re-invention.

**Next step if pursued.** First confirm Bot F's target category differs from Bot B's. Then specify the hedge-construction rule mathematically (is the hedge sized to neutralize X% of downside? Or to target a fixed Sharpe?).

---

### 005 — Probability model with arbitrage hedge

**Source seed:** [bot-knowledge.md Entry 002](bot-knowledge.md), wallet: kch123 ($13.2M → $11.3M, NBA/NHL)
**Status:** Ideas-only. **Very high build cost.** Significant overlap with Bot B.

**Core idea.** Build your own fair-value probability model for a specific sport or event category. When the model disagrees with the Polymarket price, trade the gap. Hedge the directional exposure with related-market arbitrage to reduce variance.

**Why it might work.** This is the cleanest form of "superior pricing" edge. kch123 has scaled this to $13M+ deposits.

**Why it might not.** Building a useful NBA/NHL probability model is a full research project (months of work, sports data subscriptions, ML infrastructure). At our scale/bandwidth, Bot B already occupies this niche for geopolitics/politics; duplicating the work for sports is a major commitment.

**Next step if pursued.** Do not pursue until Bot B is profitable at scale and has surplus operator bandwidth. Revisit end of 2026.

---

## Other candidates to park here as they surface

- News-latency on political/event markets (Reuters wire → Polymarket lag)
- Sports sharp-side follow (post-result scout for sharp entry patterns, pre-next-game entry)
- UMA dispute-risk trades (oraclemangle's core edge — already belongs to Bot B, do not duplicate)
- Structural arbitrage across related markets (see `docs/archive-little-rocky/structural-arb-research.md`) — now formally idea 002
- Longer-horizon weather forecast disagreement (Bot D is short-horizon; multi-week climate bets are different)

---

## References

- [docs/bot-e-spec.md](bot-e-spec.md) — sibling bot, short-horizon scalping
- [docs/archive-little-rocky/feature-roadmap-ideas.md](archive-little-rocky/feature-roadmap-ideas.md) — structural arb + depth-aware sizing research
- [docs/archive-little-rocky/structural-arb-research.md](archive-little-rocky/structural-arb-research.md) — cross-market constraint math
- [docs/bot-knowledge.md](bot-knowledge.md) — distilled insights from external articles, tagged by applicable bot
