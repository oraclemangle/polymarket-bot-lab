# Repo-integration roadmap — 2026-04-23

**Session 23 artifact.** Evaluates 33 external GitHub repos for transplant value
into our Polymarket bot fleet, with counter-edge opportunities parked for later
exploration.

**Source material:**
- Batch 1 (5 weather-bot repos) — deep-read complete via sonnet agent (2026-04-23
  afternoon). Findings integrated below.
- Batch 2 (28 "information-overload" repos) — 3 sonnet agents running in
  background at time of writing, covering 8 priority repos. This doc will be
  extended when those agents report.
- Batch 2 non-priority repos (~20) — classified via shelf memory + CLAUDE.md
  out-of-scope list + this file's triage.

**Guiding constraints** (enforced on every entry below):
- Nothing OOS per CLAUDE.md (no Kalshi arb, no mobile/webapp, no cloud providers
  outside our homelab, no oraclemangle upstream mods, no HFT latency race).
- Every STEAL port declares: LOC, licence, clean-room vs copy, prerequisites.
- Every CROWD-PROXY entry describes: crowd behavior + proposed fade +
  empirical work needed.
- No dead links in entries. No "TBD" without an OQ.

---

## Tier 0 — Already shipped this session (reference)

Preceding Session 23 work that this roadmap builds on:

- **OQ-043** — Bot G `_latest_best_bid_ask` event-type fallback (commit `920f055`).
  First paper fill 6 min after deploy.
- **OQ-044** — Bot G eager paper-fill at entry (commit `f719466`). Closes the
  `PAPER_OPEN`-forever gap (Book table missing). Post-fix tuning deploy active
  on the bot LXC container since 17:14 UTC.
- **Bot G telemetry** — candidate-distribution summary emitter (commit `c0eeb99`).
  Every 5 min logs percentile distribution of `min(yes_ask, no_ask)` + would-
  qualify-at-ceiling counts for {0.03, 0.05, 0.08, 0.10, 0.15}. Feeds Tier 1
  ceiling-tune decision.
- **LXC `.env` tuning bumps** — `BOT_G_MAX_ENTRY_PRICE=0.05→0.08`,
  `BOT_E_OBI_THRESHOLD=0.10→0.07`, `BOT_E_CEX_CVD_MIN_USD=50000→25000`.
  Expected ~2× entry rate each.
- **MEMORY.md fix** — `polymarket_agents_reference.md` "V2-migration bellwether"
  framing corrected; that repo is V1-only, stale Nov 2024, not useful for
  OQ-034.

---

## Tier 1 — Immediate (this week; validated)

### T1-A. DEB (Dynamic Error Balancing) port to Bot D — OQ-046

**Source:** yangyuan-zhen/PolyWeather `src/analysis/deb_algorithm.py`.

**What it is (ground truth from agent deep-read):** inverse-MAE weighting
across per-city 7-day forecast error history. Formula:

```
inverse_errors[model] = 1.0 / (mae_7d[model] + 0.1)
weights[model]        = inverse_errors[model] / sum(inverse_errors)
blended_forecast      = Σ current_forecast[m] * weights[m]
```

Cold-start (<2 days of history) → unweighted mean fallback. ~80 LOC.

**Why it matters:** Bot D currently uses NWS primarily. Today's post-hoc
analysis showed Bot D's +$1170 realised P&L is dominated by 1 jackpot trade;
without it, Bot D has been losing ~$14/trade across 40 closed positions.
Forecast-source diversity weighted by accuracy is a defensible way to tighten
mispricing detection.

**Prerequisite (T1-A.0):** Bot D needs ≥2 forecast sources ingested — DEB is a
blender, not a forecaster. Current state: NWS. Candidates for second source:
Open-Meteo ensemble (free, REST), METAR observations (free, aviationweather.gov).
Scope first, then port DEB.

**Licence:** AGPL-3.0 — **do NOT copy-paste**. Clean-room reimplement from
the algorithm description above (the math is trivially simple; AGPL attaches
to the code, not the idea).

**LOC:** ~80 (DEB itself) + ~50 (Open-Meteo fetcher) + ~30 (METAR fetcher) +
~100 (per-source MAE ledger in SQLite).

**Owner:** Operator-approved before starting. Claude can scope + PR.

### T1-B. Bot G ceiling-tune decision (data-driven)

**Source:** Tier 0 Bot G telemetry (commit `c0eeb99`).

**Action:** After 48h of data on the bot LXC container (i.e. by ~2026-04-25 18:00 UTC), review
`bot_g.candidate_summary` events and pick the BOT_G_MAX_ENTRY_PRICE that yields
the best expected (fill-rate × per-trade-EV) curve. Likely 0.05 → 0.07 or back
to 0.05 if 0.08 dilutes returns too much. **No code change**, just an `.env`
edit + restart.

**Owner:** Claude (data review), operator-approved before changing `.env`.

### T1-C. Bot G OQ-044 verification

**Status:** Scheduled wake-up at 19:22 UTC (today). Verify fresh entries
produce Positions post eager-fill fix. If they do → OQ-044 resolved.

### T1-D. Bot B bull/bear/risk-veto pre-entry gate (NEW from Batch 2)

**Source:** Pattern only — the named repo #5 msitarzewski/agency-agents was
misidentified (it's a collection of markdown prompt templates, 85.9k stars,
no trading logic). Agent B confirmed the bull/bear/risk pattern does NOT
exist as a reusable framework under that name. Virattt/ai-hedge-fund has
adjacent ideas (14 investor personas + Risk Manager) but is "educational
only" and differently architected.

**Why we're doing it anyway:** The pattern is sound and trivially
implementable. Bot B currently has a single-LLM entry call; a
bull-case-agent + bear-case-agent + risk-veto-on-disagreement adds a
sanity check that catches low-conviction entries. Especially useful on
ensemble-scorer rebuild.

**Concrete shape (~80 LOC, raw Anthropic SDK, no LangChain):**
```python
bull = llm_call(system=BULL_PROMPT, market_context=ctx)
bear = llm_call(system=BEAR_PROMPT, market_context=ctx)
if abs(bull.confidence - bear.confidence) > VETO_THRESHOLD:
    return NO_TRADE  # disagreement = veto
kelly_fraction = kelly(bull.p, bear.p, edge_estimate)
```

Wire into Bot B's existing entry path. Scope: 0.5-1 day.

**Dependency:** None. Build whenever Bot B comes off halt for the
ensemble-scorer rebuild.

---

## Tier 2 — Short-term (2-4 weeks)

### T2-A. METAR nowcast ingestion for Bot D — OQ-047 (proposed)

**Source:** alteregoeth-ai/weatherbot lines 305–318 (METAR fetcher from
`aviationweather.gov/api/data/metar`).

**Why:** METAR is observed (not forecast), free, per-airport, updated hourly.
For D+0 temperature markets it's a much tighter anchor than any forecast.
Currently unused by Bot D.

**LOC:** ~15 in a new `core/weather/metar.py` + 10 LOC to wire into Bot D's
snapshot.

**Licence:** alteregoeth-ai/weatherbot is MIT — clean to copy attributes, not
prose.

**Owner:** Claude can scope.

### T2-B. Open-Meteo ensemble ingestion for Bot D

**Source:** suislanchez/polymarket-kalshi-weather-bot `backend/data/weather.py`
(Open-Meteo `ensemble-api.open-meteo.com/v1/ensemble` endpoint parse).

**Why:** Provides ~30 GFS ensemble perturbations free. Would give DEB a second
source distinct from NWS.

**LOC:** ~50 (fetch + parse + cache).

**Licence caveat:** **No LICENSE file on suislanchez repo → legal ambiguity.**
DO NOT copy code verbatim. The Open-Meteo API is public and free for non-
commercial use; the ~50 LOC to hit it is trivially re-implementable.
Clean-room rewrite based on Open-Meteo's public API docs only.

**Owner:** Claude can scope (if T1-A prereq green-lit).

### T2-C. [MOVED TO T1-D]

Bot B bull/bear/risk-veto moved to Tier 1 because it's a 0.5-1 day build
with no repo dependency (pattern is implementable from scratch; named
repo was misidentified, see Batch 2 findings).

### T2-D. Backtest rigor upgrade — ExecutionModelConfig latency

**Source:** evan-kolberg/prediction-market-backtesting (Agent A STEAL).

**Why:** Our `scripts/backtest_strategies.py` fill model is simple —
crosses at best_ask, no queue position, no latency. #25 uses
NautilusTrader's `ExecutionModelConfig` with configurable `latency_base`,
`latency_insert`, `latency_update`, `latency_cancel` (all ms), plus
queue-position modelling. This is exactly what Bot G's ceiling-tune
decision (T1-B) needs for calibration — at ≤5¢ prices, any modelling
error in the fill assumption dwarfs the strategy edge.

**Two paths:**
1. **Minimal (recommended):** Port the ExecutionModelConfig latency model
   pattern (~60 LOC) directly into `scripts/backtest_strategies.py`. No
   new deps. Upgrade Bot G backtest rigor without adopting the full
   NautilusTrader stack.
2. **Full:** Write a PMXT-schema normaliser (~80-120 LOC) exporting our
   `pm_events` DB → hourly Parquet files, then run Bot G via #25's
   NautilusTrader harness directly. Requires Rust 1.93 + NautilusTrader
   1.225 install (1-2 hours env setup). Worth it if we find Bot G
   backtest fidelity is the bottleneck to real-money graduation.

**Licence:** #25 is MIT + LGPL-3.0 mixed. LGPL on some components — read
each file's header before copying. Clean-room preferred on anything
LGPL-tagged.

**Owner:** Claude can scope Path 1 in a session.

### T2-E. Bot F trailing-stop exit + staleness filter (NEW from Batch 2)

**Source:** G3-DEV-AGENCY/polymarket-copy-trading-bot (Agent C — the real
repo closest to the claimed-but-deleted dylanpersonguy repo).

**Gap identified:** Bot F has no trailing-stop exit. Every position rides
to resolution or halt. G3-DEV-AGENCY implements a clean trailing-stop
tracked against `maxPrice` per position — when price falls N% below max,
exit. Also has `entry_trade_sec` (staleness gate — don't copy trades older
than X seconds) and `trade_sec_from_resolve` (proximity-to-resolution
gate — don't enter within N seconds of resolution). Both cleaner than
Bot F's current path.

**LOC:** ~50 for trailing-stop exit loop + ~20 for the two staleness
filters = ~70 total. TypeScript original; clean-room reimplement in
Python.

**Licence:** G3-DEV-AGENCY repo has **no LICENSE file** — legal
ambiguity. Reimplement from the described behaviour only; do not copy
code verbatim.

**Why it matters:** One of the wallets in Bot F's allowlist having a
drawdown turns into real paper losses that trailing-stop would bound.
Cheap defence.

**Owner:** Claude can scope.

### T2-F. fredapi equivalent — 40-LOC FRED client for Bot B

**Source:** mortada/fredapi (Agent B REFERENCE, write our own).

**Why:** Fed macroeconomic data (CPI, unemployment, 10Y yield) in Bot B's
LLM context for any macro-sensitive Polymarket market (Fed decision
markets, recession calls, inflation prints). The dep itself has zero
caching, zero rate-limit handling, zero schema typing — not worth the
pandas overhead.

**Concrete:** `core/data/fred.py` with 3-4 `requests.get` calls
(`/fred/series/observations` for CPIAUCSL, UNRATE, DGS10) + 24h cache
layer. ~40 LOC. No external dep.

**Licence:** Apache-2.0 on fredapi itself (could be ported directly),
but so trivial to write we gain by doing our own (no pandas coupling).

**Owner:** Claude can scope in <1d when Bot B returns from halt.

---

## Tier 3 — Medium-term (1-3 months)

### T3-A. OQ-045 — .env permanent relocation outside project tree

Already scoped. Logged in `docs/open-questions.md`. Moves `.env` from
`/home/bot/polymarket-bot/.env` → `/home/bot/polymarket-bot.env` + updates
all 12 systemd unit files. Needs operator approval (fleet-wide blast radius).

### T3-B. Larger ports from Batch 2 agent results

Placeholder — any STEAL items from Agents B/C/D that require >200 LOC or
touch cross-bot infrastructure (e.g. if Agent A finds a fair-value model in
mlmodelpoly worth resurrecting for Bot E) get planned here.

### T3-C. Bot F whale-wallet expansion research

Currently 4-wallet allowlist. If Batch 2 Agent C confirms a large crowd of
copy-bots follow the same 4-10 top wallets, our signal decays. Research:
identify profitable wallets that are NOT yet mirrored by retail bots (rank
by realised P&L, filter by follower-count heuristics). No clear scope yet.

---

## Tier 4 — Counter-edge (parked; revisit when data supports)

**Thesis:** Widely-adopted public trading tools flatten retail behavior into
predictable patterns. Our edge lies in being orthogonal to or explicitly
fading those patterns. Each entry below is a research candidate, not a
committed strategy — each needs empirical validation before any capital
touches it.

### T4-α. Whale-cascade fade (now with concrete timing from Batch 2)

**Crowd behavior (ground-truth, not speculation):** G3-DEV-AGENCY's
`polymarket-copy-trading-bot` (153 stars, 107 forks) ships a curated
default whale list of 14 wallet addresses in `trade.toml`. Retail deploys
this with default config → FOK market orders within 1–30s of leader's
trade appearing in the activity stream. NO slippage guard on FOK orders
(confirmed in agent deep-read — the `SLIPPAGE_TOLERANCE` config exists but
isn't applied to order params). Result: **price overshoots 2–8% on
illiquid markets post-leader entry, t+5s to t+90s window**.

The 14-wallet default list is the coordination mechanism. Any of those 14
wallets buying triggers the same FOK pile-in from every bot fork.

**Asymmetry:** bots ignore sell signals by default (`revertTrade: false`
is the default). When leader exits, retail does NOT follow → trapped
retail longs unwind slowly through normal market channels. This creates a
predictable *absence* of coordinated exit pressure — not tradeable on its
own but worth measuring.

**Proposed fade:**
- Monitor the same 14 wallets as G3-DEV-AGENCY's default list (URL
  retrievable from the repo's `trade.toml`).
- When a leader buys on an illiquid market, wait the t+5–90s overshoot
  window, measure price vs pre-trade fair value.
- If overshoot > 2 standard deviations, short the overshoot for the
  mean-reversion that typically completes within 2-5 min.

**Empirical work needed before deploying:**
- Pull G3-DEV-AGENCY default wallet list (14 addresses) into Bot F's
  monitor scope, tagged as "public-crowd-leader".
- For every public-crowd-leader buy, log (leader_px, t+30s_px, t+90s_px,
  t+5min_px) into a new `event_type='crowd_cascade'` Event row.
- Collect 50+ events over 3-4 weeks. Measure overshoot magnitude and
  reversion half-life.
- If median overshoot > 3% and reversion < 5min on markets with
  liquidity < $50k, thesis is tradeable.

**Implementation path:** sibling "Bot F-inv" service, paper mode, ADR when
empirical work completes. Wallet-overlap diligence first — some of the 14
may already be on Bot F's allowlist, in which case "mirror" vs
"mirror-then-fade" is per-wallet configurable.

### T4-β. Backtest-strategy decay fading

**Crowd behavior:** Public backtest results (#25, #22's 7 strategies:
arbitrage, momentum, market-making, AI forecast, whale copy-trade,
convergence, +1) cause retail deployment → edge decays.

**Our current posture:** Bot G (deep tail, t-60s longshot fade) is already
orthogonal to all 7 strategies in #22. Good by accident.

**Proposed enhancement:** Audit the on-chain footprint of the 7 public
strategies. If we can detect the collective retail behavior (e.g.
market-maker quote withdrawals at consistent times, momentum chasers
piling into top gainers), we can fade the crowded trade. Requires:

- Agent C deep-read of #22 to enumerate the 7 strategies precisely.
- Historical pattern detection (60d).

**Risk:** the "fade the crowd" trade is itself a strategy; at scale it
becomes the new crowded trade. Discipline: only deploy if effect size >3%
net.

### T4-γ. LLM-consensus fading

**Crowd behavior:** Many bots (Claude #1, TradingAgents #8, Dexter #15,
Polymarket/agents #17) query similar LLMs with similar prompts → similar
conclusions on news-driven markets. Markets converge to LLM consensus.

**Proposed fade:** Where LLM consensus strongly agrees with current market
price, there's no edge (market has already absorbed LLM view). Where LLM
disagrees with market on INFORMATION-THIN markets, LLM is usually wrong —
fade the LLM view.

**Status:** Already partially captured in our `~/.claude/models.yaml`
triangulation approach (3-way: Grok + thinking + Kimi). The explicit
"fade LLM consensus when info-thin" signal isn't yet operationalised in
any bot.

**Empirical work:** Tag 100+ past Polymarket resolutions by (LLM
consensus, market consensus, outcome). Measure LLM-vs-market edge by
market-depth bucket. If LLMs lose in info-thin markets, build a filter.

### T4-δ. Speed-race cleanup (partial overlap with Bot G)

**Crowd behavior:** HyperBuildX and MEV bots at sub-100ms place orders we
cannot match. They displace the order book.

**Our position:** Bot G's t-60s entry window is already after the
speed-traders have done their work in most cases. If Bot G's fill data
shows a pattern of book displacement (e.g. our fills consistently sit
against one side of the order book that looks like a just-fled MEV
resting order), we have signal.

**No explicit action needed now** — folds into Bot G's normal operation.

### T4-ζ. Dual-limit retail-bot footprint fade (NEW from Batch 2)

**Crowd behavior (ground-truth, not speculation):** ConteurShadow's
`Polymarket-Trading-Bot-Rust` (240 stars, 104 forks) runs a pure
heuristic dual-limit strategy on Polymarket's own 15-min BTC/ETH/SOL/XRP
Up/Down markets (exactly Bot E / Bot G's territory). Retail running this
exhibits very specific, measurable patterns (timing confirmed from the
code):

1. **$0.45 dual-bid at period open.** Simultaneous limit buys at $0.45 on
   both Up and Down tokens at each 15-min window start. Expect a visible
   resting-bid cluster at $0.45 on both sides in the first 60 seconds of
   each 15-min crypto market.
2. **Forced hedge market-buys at t+2min, t+4min, t+10min.** When one side
   fills, the bot cancels the other side and re-buys at market within
   those fixed time windows. Predictable demand spikes at those three
   timestamps.
3. **Sell walls at $0.93 and $0.98.** After a hedge executes, 5 limit
   sells are placed at those prices. Known resistance levels that are
   *mechanical* not *directional* — the bot will sit there regardless of
   whether the market is actually heading to 1.0.

**Proposed fade (3 specific trades):**
- **(a) Hedge-trigger scalp.** If $0.45 dual bids exist at period start
  and one side gets lifted, the other side faces predictable
  market-order demand at t+2min or t+4min. Short-window buy on the
  unfilled side just before trigger time, exit at trigger + 30s.
- **(b) Sell-wall piercing.** When approaching $0.93/$0.98 into
  resolution and the market is genuinely running toward 1.0, the sell
  wall is noise — buy through it knowing retail placed it mechanically.
- **(c) Period-reset exploit.** The binary resets cleanly per 15-min
  window — any dislocation caused by bot activity at t+14min unwinds by
  t+0 of the next period. Dislocations are scalpable.

**Empirical work needed:**
- Instrument Bot E's recorder to tag $0.45 dual-bid clusters at period
  opens and log presence/absence.
- For 100+ observed clusters, measure correlation between cluster
  presence and overshoot at t+2min / t+4min hedge triggers.
- If correlation > 0.3 and overshoot > 2%, thesis is tradeable.

**Relationship to Bot G:** Bot G operates in the FINAL 60s (t+14min
window). ConteurShadow-driven sell walls at $0.98 may be affecting our
winning-side exits. Worth checking whether Bot G's realised fills show a
$0.98 "stuck" pattern.

### T4-ε. Under-followed wallet alpha

**Crowd behavior:** All whale-trackers use the same top-P&L wallet lists
(polymarketanalytics.com #23, etc.). A wallet with large follower count
has diluted signal.

**Our current posture:** Bot F's 4-sharp allowlist is small and somewhat
curated; as long as we don't chase the most-public top-100 lists, we
retain signal. But we haven't quantified this.

**Proposed research:** Build a "mirror count" estimator (how many public
wallet-trackers include wallet X). Rank candidate wallets by
(realised P&L ÷ estimated_mirror_count). Expand Bot F allowlist only with
high-ratio candidates.

---

## Tier 5 — Shelf / Decline

Full list of repos explicitly NOT being acted on, with reason per entry.
Kept here so future sessions don't re-evaluate blindly.

### Batch 1 (5 repos — agent ground-truth in section "Findings" below)

| # | Repo | Decision | Reason |
|---|---|---|---|
| 1 | alteregoeth-ai/weatherbot | REFERENCE (partial port T2-A) | "Ensemble" is just hierarchical pick. Only METAR fetcher worth taking. |
| 2 | suislanchez/polymarket-kalshi-weather-bot | REFERENCE (partial port T2-B) | Real Open-Meteo fetch but NO LICENSE, rest of stack is Kalshi-arb OOS. |
| 3 | hcharper/polyBot-Weather | SKIP | Copy-trade is TODO placeholders. BS pricer trivial + no long-dated bot planned. |
| 4 | yangyuan-zhen/PolyWeather | STEAL (clean-room T1-A) | DEB real, AGPL-fenced, ~80 LOC clean-room port. |
| 5 | Polymarket/agents | REFERENCE | V1-only, stale 18 months. Prompts file skim only. |

### Batch 2 non-priority (20 repos, triaged from descriptions + shelf memory)

| # | Repo | Decision | Reason |
|---|---|---|---|
| 1 | Claude (Anthropic) | ALREADY USE | Primary strategist, this session. |
| 2 | Qwen3-Coder | ALREADY USE | In our multi-LLM stack per `~/.claude/models.yaml`. |
| 3 | Claude Squad | SKIP | Parallel Claude instances = what systemd already does for us. |
| 4 | G0DM0D3 | HARD SKIP — SECURITY | "Uncensored AI" is a jailbreak tool. Operational risk, no trading alpha. Per CLAUDE.md §Security, out. |
| 6 | MiroThinker | SKIP | Mandatory CoT adds latency; Bot E scalp intolerant, no Bot B benefit beyond existing audit trail. |
| 7 | ClaudeAgentOneClick | SKIP | One-click deploy — we have systemd. |
| 8 | TradingAgents | ALREADY SHELVED | Shelf memory `github_repos_shelf_2026_04_19.md` rejected for now. |
| 9 | Superpowers | SKIP | Generic agent tooling; we have tools. |
| 10 | OpenBB | ALREADY SHELVED | Shelf memory rejected. |
| 14 | Polymarket Assistant Tool | LOW PRIORITY | Too vague to evaluate without a read; not worth a dedicated agent unless operator flags. |
| 16 | lightweight-charts | SKIP | UI only, OOS (no webapp frontend). |
| 17 | Polymarket/agents | DUPLICATE of Batch 1 #5 | Already assessed. |
| 18 | polyterm | LOW PRIORITY | Terminal dashboard — crowd-proxy but no novel logic. Note in T4-α context. |
| 19 | Polyscope | CROWD-PROXY (T4-α) | Whale alerts → retail cascade → fade target. |
| 20 | Polywhaler | CROWD-PROXY (T4-α) | Same as #19. |
| 23 | polymarketanalytics.com | SKIP | Website, not code; useful for T4-ε research as a "who's public" signal. |
| 24 | polybot | SKIP | Kafka + ClickHouse + Grafana = institutional infra. Overkill for solo-operator homelab. |
| 26 | MCP Server (financial-datasets) | SKIP | Interesting protocol, no trading logic. T3 reference if we adopt MCP for data feeds. |
| 27 | Crucix | SKIP | Polygon-specific on-chain aggregator. Bot F already does on-chain reads. |
| 28 | WHALES tracker (Apify) | LOW PRIORITY | Aggregator across Gamma/Data/CLOB. If we need consensus/conviction scoring, reconsider. |

### Batch 2 priority (8 repos) — DONE

| # | Repo | Decision | Action (tier) |
|---|---|---|---|
| 5 | msitarzewski/agency-agents | **CLAIM-MISIDENTIFIED** | Build from scratch (T1-D) — no repo dep |
| 11 | txbabaxyz/mlmodelpoly | REFERENCE | `fair_model.py` GBM z-score benchmark (60 LOC optional for Bot E) |
| 12 | txbabaxyz/polyrec | REFERENCE | Feature-ideas only (70-col CSV logging schema) |
| 13 | mortada/fredapi | REFERENCE (write our own) | 40-LOC FRED client for Bot B (T2-F) |
| 15 | virattt/dexter | SKIP | TS/Bun + paid Financial Datasets API; near-zero Polymarket relevance |
| 21 | HyperBuildX/Polymarket-Trading-Bot | **URL FABRICATED (404)** | Real proxy analysed: ConteurShadow/Polymarket-Trading-Bot-Rust → CROWD-PROXY (T4-ζ) |
| 22 | dylanpersonguy/Polymarket-Trading-Bot | **URL FABRICATED (404)** | Real proxy analysed: G3-DEV-AGENCY/polymarket-copy-trading-bot → REFERENCE (T2-E, T4-α concrete) |
| 25 | evan-kolberg/prediction-market-backtesting | **STEAL** | ExecutionModelConfig latency model port to backtest_strategies.py (T2-D, 60 LOC minimum path) |

---

## Findings: Batch 1 ground-truth (2026-04-23 afternoon)

Preserving all key detail so we don't lose context.

### #1 alteregoeth-ai/weatherbot — REFERENCE

- **Real?** Partial. Weather pulls are live HTTP (Open-Meteo for ECMWF/HRRR,
  aviationweather.gov for METAR, Visual Crossing for post-resolution actuals).
  "Ensemble" is hierarchical pick, NOT fusion: US D+0/D+1 uses HRRR, else
  ECMWF. METAR stored only. No averaging, no weighting.
- **Stack:** Python, Gamma REST (no py-clob-client). Two files: `bot_v1.py`
  (17KB) + `bot_v2.py` (44KB) ≈ ~1400 LOC. Paper-only, `state.json` on disk.
  MIT licence. 211 stars, last push 2026-03-22.
- **Salvage:** `calc_kelly(p, price)` at lines 145–151 is clean (fractional,
  clamped, capped by MAX_BET). We have equivalents. METAR fetcher (lines
  305–318) is ~15 LOC of useful free-nowcast source we don't currently use →
  T2-A.
- **Gotchas:** Paper-only, stale since March. MIT = clean to port.

### #2 suislanchez/polymarket-kalshi-weather-bot — REFERENCE (caveat)

- **Real?** Partial. Does hit `ensemble-api.open-meteo.com/v1/ensemble` and
  parses `temperature_2m_max_member01..member30`, so ~30-31 real GFS
  perturbations. "31-member" isn't asserted in the request; it's whatever
  Open-Meteo returns. No ECMWF ensemble alongside.
- **Probability derivation:** Raw frequency:
  `above_count = sum(1 for m in members if m > threshold);
   agreement_frac = max(above, len-above)/len(members)`. Clipped to [0.05, 0.95].
  NO calibration (no isotonic, no Platt). Edge gate `abs(edge) >= WEATHER_MIN_EDGE_THRESHOLD`
  (config-driven, not hard-coded 8%).
- **Stack:** Python (FastAPI), SQLite, React, Claude + Groq plumbing. ~36
  backend files, ~150KB Python. Production-scale structure. Active, 146 stars,
  last push 2026-03-02.
- **Salvage:** Open-Meteo ensemble fetcher + member-parse in `backend/data/weather.py`
  ~50 LOC portable → T2-B.
- **Gotchas:** **NO LICENSE file** — legal ambiguity. Heavy FastAPI/React
  baggage. Must re-implement from Open-Meteo public API docs, NOT copy.

### #3 hcharper/polyBot-Weather — SKIP

- **Real?** Partial/no. NOAA + Pyth + copy-trading structurally present but
  **copy-trade is placeholder-only**: `execute_pending_copies` logs
  "EXECUTING COPY" with TODO. `discover_top_traders()` explicitly "would
  query Dune/subgraph in production" — hardcoded `DEFAULT_TOP_TRADERS`.
- **Copy-trade data path (real):** `detect_new_trades()` polls via
  `eth_getLogs` filtered on CTF contract address on Polygon, fallback
  Polygonscan API. No WebSocket. Fractional scaling (default 10%) capped
  at $100.
- **Black-Scholes (`strategies/crypto.py`)** actually implemented:
  `d2 = ln(S/K)/(σ*sqrt(T))` with `N(d2) = 0.5*(1+erf(d2/sqrt(2)))`.
  Zero-drift assumption, hardcoded realised vol BTC 0.55 / ETH 0.70. No Pyth
  IV, no regime model. Targets 0.5–30 day price-above-X markets.
  Mathematically clean, inputs weak.
- **Stack:** Python (pyproject.toml), Streamlit dashboard. ~900KB Python,
  ~30 files. **NO LICENSE.** Last push 2026-02-03 — stale. 17 stars.
- **Decision:** BS pricer (~40 LOC) salvageable IF we ever do long-dated
  bots — we don't, so skip.

### #4 yangyuan-zhen/PolyWeather — STEAL (DEB, clean-room)

- **Real?** Yes. DEB is genuinely implemented in `src/analysis/deb_algorithm.py`
  (43KB, ~1000 LOC). Also LightGBM models (`src/models/lgbm_daily_high.py`),
  isotonic-style calibration layer, probability-rollout layer. Serious
  production bot (134MB repo, 42KB `market_alert_engine.py`, 121KB
  `polymarket_readonly.py`).
- **DEB formula (ground truth):** Inverse-MAE weighting, NOT Bayesian model
  averaging:
  ```
  inverse_errors = {m: 1.0 / (mae + 0.1) for m, mae in maes.items()}
  weights        = {m: inv / total_inv for m, inv in inverse_errors.items()}
  blended_high   = sum(current_forecasts[m] * weights[m] for m in weights)
  ```
  Per-model MAE over past 7 days of actuals vs forecasts, per city. Cold-start
  (<2 days) falls back to unweighted mean. Models weighted from whatever keys
  appear in `current_forecasts` (ECMWF, GFS, JMA, MGM, NWS, HKO, ICON, GEM,
  AIFS — explicitly excludes meteoblue by name). No calibration on top of
  DEB; calibration is a separate layer in `probability_calibration.py` (linear
  regression on DEB output, 5 coefficients each, min 3 samples).
- **Stack:** Python, SQLite (`db_manager.py` 65KB), Polygon on-chain wallet
  watcher, Telegram bot, Supabase entitlement. Active (pushed 2026-04-23),
  25 stars.
- **Transplant value:** HIGH. Port `calculate_dynamic_weights` to Bot D as
  ~80-LOC drop-in blender when ≥2 forecast sources exist. Reusable per-source
  MAE ledger portable across Bot B/C/D/E.
- **Licence:** **AGPL-3.0 — COPYLEFT.** Copy-paste would infect. Solo-operator
  private deploy is fine but any SaaS move (unlikely but) breaks. **Clean-room
  reimplement from the algorithm description** — math trivial, defensible
  clean-room rewrite.
- **Top file:** `src/analysis/deb_algorithm.py` lines ~990–1050.

### #5 Polymarket/agents — REFERENCE

- **Real?** Yes. Genuine framework, 3246 stars, MIT. Class-based tools
  (`get_all_markets`, `get_orderbook`, `execute_order`, `execute_market_order`,
  `build_order`, `get_usdc_balance`) — not LangChain/CrewAI decorators. Chroma
  + news connectors for RAG. Places real mainnet orders via
  `self.client.post_order(signed_order, orderType=OrderType.FOK)`.
- **Stack:** Python, `py_clob_client.client.ClobClient` (unpinned — likely V1),
  chroma, Dockerfile. 2239 LOC in `application/trade.py` + 34KB in
  `polymarket/polymarket.py`. **Last push 2024-11-05 — 18 months stale.**
- **V2 status:** NO V2 SUPPORT. Zero references to V2, USDC.e migration, CTF
  Exchange V2, or `py-clob-client-v2`. Uses `ClobClient.create_or_derive_api_creds()`
  (L2 HMAC). **NOT a V2 bellwether** — memory corrected.
- **Salvage:** `application/prompts.py` (10KB) worth skimming for Bot B
  prompt ideas.
- **Licence:** MIT.

---

## Findings: Batch 2 ground-truth (2026-04-23 evening)

Preserving all key detail from 3 parallel sonnet agents.

### #11 txbabaxyz/mlmodelpoly — REFERENCE

- **Real?** Partial. Collector, fair-value model, edge engine are genuine
  Python. The "ML model" claim is misleading — `fair_model.py` is a
  Black-Scholes variant: `z = ln(S_now/ref_px) / (σ√τ); fair_up = Φ(z)`.
  No regression, no trained model. Edge engine (`edge_engine.py`) layers
  AVWAP mispricing + RVOL/impulse/absorption on top. NO backtest in repo;
  `scripts/` has calibration tools and a TUI dashboard but no P&L output.
- **Stack:** Python 3.10+, FastAPI, TAAPI.io (external paid API for
  regime indicators), Prometheus, Binance WSS + Polymarket WSS. ~35
  files, 2–4k LOC.
- **Licence:** MIT. Recent, ≤3 months old. 2 commits on main.
- **Data sources:** Binance Futures/Spot WSS (aggTrade, bookTicker,
  markPrice), Polymarket orderbook WSS. No Pyth.
- **Would it beat last-trade-price?** Unknown — no backtest exists. GBM
  fair-value is theoretically sound but ignores Polymarket's fee wedge,
  liquidity, bid/ask spread (which dominate 15-min pricing). TAAPI adds
  cost/latency with no proven lift.
- **Salvage:** `fair_model.py` GBM z-score (~60 LOC) as benchmark
  probability for Bot E. Not a signal on its own. Skip TAAPI dep.

### #12 txbabaxyz/polyrec — REFERENCE

- **Real?** Partial. `dash.py` is a live terminal monitor. Two backtest
  scripts (`fade_impulse_backtest.py`, `replicate_balance.py`) read real
  CSV logs captured from the live dashboard — so they backtest on
  self-collected data, not a pre-existing archive. No published results.
- **Stack:** Python 100%, Chainlink via Node.js subprocess, Binance WSS
  + Polymarket WSS + Polymarket REST. 70+ logged columns per bar.
  Small — 6 Python files.
- **Licence:** MIT. 3 commits on main, same author/era as #11.
- **Overlap with #11:** COMPLEMENTARY HALVES. polyrec is the
  data-collection layer; mlmodelpoly is the modelling layer. They are
  one system, not independent projects.
- **Backtester:** reads `./logs/*.csv` (self-collected). 2-second fill
  window. No orderbook replay — CSV snapshots with bid/ask only. Schema
  mismatch with our `pm_events` recorder DB.
- **Salvage:** 70-column CSV logging schema — feature-ideas reference for
  what microstructure features to log. Backtester fill model too naive
  vs. our pm_events replay.

### #25 evan-kolberg/prediction-market-backtesting — STEAL

- **Real?** Yes. Most substantive of the three. Built on **NautilusTrader
  1.225.0** with custom Polymarket and Kalshi adapters. Supports
  trade-tick and quote-tick modalities. PMXT is a relay/mirror service
  that captures real Polymarket L2 orderbook data as hourly Parquet
  files (`polymarket_orderbook_YYYY-MM-DDTHH.parquet`). Schema carries
  bid/ask arrays, price_change events, book_snapshots — actual WSS
  stream capture.
- **Stack:** Python 3.12+, Rust 1.93.1, NautilusTrader 1.225.0, uv,
  Ruff. Jupyter notebooks (~75%), Python (~25%). 730 stars, 103 forks.
- **Licence:** Mixed MIT + LGPL-3.0. Check per-file headers before
  copying.
- **Data:** real historical Polymarket L2 orderbook via PMXT Parquet
  archive OR self-hosted PMXT relay. BYOD path: normalize external data
  to `{market_id, update_type, data}` Parquet schema — our `pm_events`
  recorder DB is transplantable if we write the normaliser.
- **Backtests:** `backtests/` has Polymarket strategies using quote-tick
  and trade-tick variants. **Execution modelling includes configurable
  latency (base, insert, update, cancel in ms), queue positioning, fee
  + slippage**. This is what our backtest is missing.
- **Transplant:** two options in T2-D above.

### #13 mortada/fredapi — REFERENCE (write our own)

- **Real?** Partial. Real, maintained (last release 2024-05, v0.5.2,
  Apache-2.0). 1.5k stars, 67 commits. "Every macroeconomic dataset"
  overstates it — it wraps FRED specifically.
- **Stack:** Pure Python, single dep pandas. ~550 LOC total (~350
  logic). Uses `urllib.urlopen` + XML parsing + pandas wrap. **No
  caching, no schema validation, no retry, no rate-limit handling.** URL
  construction + XML parse + DataFrame.
- **Rate limits:** FRED API is free, requires API key, generous.
- **Verdict:** The 7 endpoints we'd use for Bot B (CPI=CPIAUCSL,
  UNRATE, DGS10, etc.) are 3–4 `requests.get` calls + simple XML parse.
  Our own `fred_client.py` in ~40 LOC avoids pandas coupling and gives
  us caching. Dep not worth it.

### #15 virattt/dexter — SKIP for Bot B

- **Real?** Yes. 21.4k stars, active (last release 2026-04-08), MIT.
  TypeScript/Bun.
- **Stack:** LLM-driven orchestration (Claude/OpenAI/Gemini/xAI via
  OpenRouter). Data via **Financial Datasets API (paid, third-party)** +
  Exa/Tavily for web search. Output is NDJSON scratchpad logs.
- **What "deep research" is:** task decomposition → LLM picks tool
  calls → hits Financial Datasets API for filings/statements → LLM
  synthesises → self-validation loop. "SEC filings" path calls
  `financialdatasets.ai/filings/` (paid wrapper around EDGAR). No direct
  EDGAR scraping.
- **Polymarket relevance:** near zero. Markets where SEC filings matter
  (earnings surprises, M&A, public-company-specific resolution) are a
  small slice and typically resolve on price moves, not filing text.
  Paid API + TypeScript stack alien to our Python fleet.
- **Salvage:** read `src/agent/` directory as a **design pattern
  reference** for Bot B's ensemble orchestration (plan → tool calls →
  validate). Do not port the TypeScript. Do not add the paid API.

### #5 msitarzewski/agency-agents — MISIDENTIFIED

- **Real?** The repo is real, but the trading-agent claim is **fabricated**.
  `msitarzewski/agency-agents` is a collection of 144 markdown prompt
  templates for Claude Code/Copilot/Cursor — 85.9k stars, MIT, 96.8%
  Shell (install scripts). Zero trading logic. Finance division has 5
  agents for bookkeeping/FP&A, not algo trading.
- **The bull/bear/risk-veto pattern does NOT exist there.** Closest real
  adjacent work: `virattt/ai-hedge-fund` (57.2k stars, Python + TS, 14
  investor personas, Risk Manager, Portfolio Manager). Explicitly
  educational-only, different architecture.
- **Decision:** **build from scratch** in ~80 LOC raw Anthropic SDK (see
  T1-D). No framework needed; the pattern is trivial.

### #21 HyperBuildX/Polymarket-Trading-Bot — URL FABRICATED

- **Repo returns 404.** GitHub API confirms it doesn't exist. No web-
  search mirrors. Claims ("Rust sub-100ms, AI ranks copy-trade signals")
  unverifiable — the code never existed publicly.
- **Closest real proxy:** ConteurShadow/Polymarket-Trading-Bot-Rust (240
  stars, 104 forks, last push 2026-04-22). Below.

#### ConteurShadow/Polymarket-Trading-Bot-Rust — CROWD-PROXY

- **Real?** Partial. Genuine Rust, compiles, hits CLOB. Strategy is NOT
  "whale copy-trade with AI" (that was the fabricated #21 description).
  It's pure **price-momentum on Polymarket's own BTC/ETH/SOL/XRP 15-min
  Up/Down markets**.
- **Stack:** Rust, Tokio, `tokio-tungstenite`, `reqwest`, `libloading`
  (CLOB SDK via `.so`). ~12 source `.rs` files + 12 strategy binaries.
  4–6k LOC. **No LICENSE file.**
- **"Sub-100ms"?** Plausible but **irrelevant** — `check_interval_ms:
  500` (configurable). Market data via REST (`gamma-api.polymarket.com`),
  not WSS. One WSS connection feeds Chainlink BTC/USD for reference
  only. Realistic polling latency 500ms–2s.
- **"AI ranks signals"?** Zero. No ML, no model. Hardcoded floats +
  time-window guards (2/4/10 min). "Intelligence" is a heuristic.
- **Whale wallets tracked:** none.
- **Strategy binaries:**
  1. `main_dual_limit_045_same_size`: dual $0.45 limit buys on both
     tokens at period start. One side fills → cancel other → re-buy at
     market within 2/4/10-min windows.
  2. `main_dual_limit_045_5m_btc`: same on 5-min BTC markets.
  3. `main_trailing`: waits for token <$0.45 near mid, trails the low,
     buys dip, hedges via time-gated opposing buys.
  4. Backtest binary replays `history/*.toml`.
- **Crowd profile:** Requires Rust toolchain + CLOB SDK `.so` +
  Ubuntu 22/24 + funded wallet. Barrier moderate-high. **<5% of
  starrers realistically deploy** (paid advanced version exists via
  Telegram @soladity — public code may be lead-gen).
- **Transplant value:** only the Rust Chainlink feed subscription logic
  (`rtds.rs` → `wss://ws-live-data.polymarket.com` with
  `crypto_prices_chainlink`) is worth reading for Bot E's price-source
  options. Strategy logic is heuristic, we have better.
- **Crowd fade:** see T4-ζ above.

### #22 dylanpersonguy/Polymarket-Trading-Bot — URL FABRICATED

- **Repo returns 404.** "53k LOC TypeScript, 7 strategies" unverifiable.
- **Closest real proxy:** G3-DEV-AGENCY/polymarket-copy-trading-bot.

#### G3-DEV-AGENCY/polymarket-copy-trading-bot — REFERENCE

- **Real?** Yes. Working TypeScript copy-trade code. 153 stars, 107
  forks, built Feb 2026, last push 2026-04-20.
- **Stack:** TypeScript, Node 18+, `@polymarket/real-time-data-client`,
  `@polymarket/clob-client`, `ts-big-lib`. ~15 files, ~700–1k LOC TOTAL
  (not 53k — that claim was fabricated). Lean, functional.
- **Licence:** **No LICENSE file** — legal ambiguity.
- **Strategies:** **ONE**, not 7. Copy-trade a target wallet. Sub-modes:
  1. **WebSocket mode** (single target): subscribes to
     `activity/trades` topic, filters by `proxyWallet`.
  2. **Polling mode** (multiple targets): polls positions API every N
     sec, diffs against previous snapshot.
  3. **Simulation/dry-run mode.**
  4. **Exit management:** take-profit %, stop-loss %, trailing-stop %
     on a polling loop.
- **Crowd profile:** LOW barrier — `npm install && npm run dev`,
  configure `trade.toml`. README ships **curated default list of 14
  whale wallet addresses** (e.g. `@gabagool22`, `@risk-manager`,
  `@7thStaircase`) with PnL screenshots. Estimated **10–20% of 107
  forkers realistically deploy** — the config is turnkey.
- **Behavior on trigger:** FOK market orders within 1–3s (WSS path) or
  `poll_interval_sec` (default 10s) of leader's trade appearing. **No
  slippage guard applied to order params** (the `SLIPPAGE_TOLERANCE`
  config exists in settings but isn't passed through — confirmed in
  agent deep-read).
- **Buy-only default:** `revertTrade: false` → copies BUYS only. When
  leader exits, bots don't follow → trapped retail longs unwind slowly
  through normal channels.
- **Size multiplier default `0.01`** — small positions, but aggregated
  across 107 forkers it matters.
- **Transplant value (T2-E):** `shouldCopyTrade` filter with
  `entry_trade_sec` staleness gate and `trade_sec_from_resolve`
  proximity gate are both **cleaner than Bot F's current path**. Port
  both filters (~20 LOC). **Trailing-stop exit tracked against
  `maxPrice` is a real Bot F gap** — port pattern (~50 LOC). Total ~70
  LOC clean-room Python.
- **Crowd fade (T4-α):** the 14-wallet default list is the
  coordination mechanism. Any of those 14 buys → 107 forks' worth of
  FOK-no-slippage-guard pile-in within 1–30s → 2–8% overshoot on
  illiquid markets → mean-reversion scalp window t+5s to t+90s.

---

## Session 23 addendum — data integrity note on repo claims

Of the 8 priority repos in Batch 2, **two URLs were fabricated** (#21
HyperBuildX, #22 dylanpersonguy) and **one had a misidentified claim**
(#5 Agency Agents bull/bear/risk pattern doesn't exist in that repo).
Source material for Batch 2 came from a social-media marketing list,
which contained these errors. Going forward: any repo the operator cites
from social-media sources should be fetched before I give a verdict.
Batch 1 source material was operator-curated and all 5 repos were real.

---

## Ground rules for adding to this doc

When new repo evaluations happen (or for any future repo eval):

1. Place each repo in Tier 1/2/3/4/5 with the same structure used above.
2. For STEAL items: always state LOC + licence + clean-room requirement.
3. For CROWD-PROXY items: always state (crowd behavior, proposed fade,
   empirical work needed, no deployment before empirical validation).
4. If an item moves between tiers later, log the rationale in
   `docs/decisions-log.md` with a new ADR.
5. Fetch the actual repo before classifying. Do not classify from
   description alone.
