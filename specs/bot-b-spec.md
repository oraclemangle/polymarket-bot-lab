# Bot B (Oracle) — LLM directional Kelly trader

**Status:** Built for paper mode; scorer path changed after the original spec
**Last updated:** 2026-04-15
**Role:** LLM directional trader that consumes an external calibrated dispute-risk
scorer (Oraclemangle, a separate closed product — https://oraclemangle.com) over
HTTP, deriving and persisting `claude_pick` and `claude_implied_prob` in this repo.

Implementation note: ADR-015 superseded the original "full in-repo scorer port" plan. This spec describes the live implementation path where relevant. The repo does not consume the external service's DB or daemon state directly, and does not contain its model or internals.

---

## Thesis

The strategy relies on an external, calibrated dispute-risk + resolution-prediction
scorer (Oraclemangle — https://oraclemangle.com) as a model-vs-crowd signal on
ambiguous-resolution markets. Its model, calibration dataset, and internals are
proprietary to that closed product and are **not** part of this repo; see the
website for what it is.

- The crowd under-prices resolution ambiguity — they trade binary outcomes as if they were binary
- The scorer prices ambiguity explicitly via `dispute_risk`
- When the scorer's implied probability diverges from the crowd's AND `dispute_risk` is low (so the tail isn't a DVM coin flip), there's an edge worth sizing

**Edge persists because:**
- The scorer is a proprietary external product
- Its calibration dataset is costly to assemble
- Strategy is low-frequency enough that 10-minute decision latency doesn't matter

Bot A is the baseline; Bot B's differentiation is the external scorer signal.

---

## Relationship to the external scorer

Bot B **consumes the external scoring API only** — not its DB or internals. Specifically:

| External capability | This repo's integration | Modification |
|---|---|---|
| `GET /v1/score` | `bots/bot_b/http_scorer.py` | Add local derivation + persistence of `claude_pick` / `claude_implied_prob` |
| The LLM+RAG pipeline behind `/v1/score` | Treated as an external dependency | No local copy; this repo does not contain it |
| Shared state / DB | Not consumed | This repo stores its own `scores`, orders, positions, books, and markets |

The external scorer (Oraclemangle, https://oraclemangle.com) is a separate closed product; this repo never contains or modifies its code or data.

---

## Mechanics

### Pipeline (cron-driven)

| Stage | Frequency | Writes to |
|---|---|---|
| 1. Scraper | every 15 min | `open_markets` (upserts) |
| 2. Scorer (HTTP to the external scorer) | every tick, budget-capped | `scores` (one row per (market, scored_at)) |
| 3. Filterer | on each scoring batch | emits candidate list in memory |
| 4. Sizer | per candidate | computes Kelly fraction, applies DR penalty |
| 5. Executor | per sized candidate | CLOB order via `core/clob.py` |

Scraper and scorer must **not** depend on the external service's own scheduling. They run in Bot B's own process (or its own systemd unit).

### Market selection filters

| Filter | Value |
|---|---|
| Category | ∈ {geopolitics, politics, finance, economics} |
| Structure | binary YES/NO (no neg-risk in v1) |
| `dispute_risk` | ≤ 0.25 |
| `claude_confidence` | ≥ 0.7 |
| `|claude_implied_prob − yes_price|` | ≥ 0.08 |
| `volume_24h` | ≥ $10,000 |
| `book_depth_at_pick_side` | ≥ $1,000 within 3¢ of mid |
| `days_to_resolution` | ∈ [7, 365] |
| `score_age` | ≤ 12 hours |

Expected candidate universe: **5–30 active markets** at any time.

### Sizing

```python
# Quarter-Kelly over crowd price
kelly_raw = (p_model - p_market) / (1 - p_market)
kelly_fraction = 0.25 * kelly_raw

# Dispute-risk penalty: linear decay, zero at DR=0.25
dr_multiplier = max(0, 1 - dispute_risk / 0.25)

# Final sizing, hard-capped
position_size_usd = min(
    bot_bankroll * kelly_fraction * dr_multiplier,
    bot_bankroll * 0.04,      # 4% per-position hard cap
    book_depth_at_pick * 0.5, # don't be more than half the depth
)
```

### Execution

- **Order type:** GTC limit at `market_mid ± 0.005` (inside the spread)
- **Re-post cadence:** if not filled in 2 hours, cancel, re-fetch book, re-post at fresh `mid ± 0.005`
- **Exit (normal):** hold to resolution
- **Exit (edge-collapse):** if re-scoring reduces `|p_model − yes_price|` below 0.03, cancel open orders, close position at market
- **Exit (dispute):** hold; UMA DVM resolves or refunds
- **Exit (kill-switch):** cancel all, close at market, alert

### Risk controls

| Control | Value |
|---|---|
| Per-market notional cap | 4% of Bot B bankroll = £40 at £1,000 |
| Aggregate open exposure cap | £800 |
| Drawdown kill | −15% of Bot B bankroll |
| Stale-score halt | scores >12 hours old drop from candidate pool |
| Stale-data halt | scraper hasn't run in >45 min → halt entries |
| Dispute tail-risk cap | ≤3 open positions with `dispute_risk ∈ [0.15, 0.25]` at once |
| Calibration halt | 10 consecutive resolutions where mean `|p_model − realised| > 0.15` → halt for re-calibration |

### Capital allocation

Identical tier schedule to Bot A: paper £1k sim → live £250 → £500 → £1,000 ceiling.

---

## Expected performance (estimates, not promises)

- **Edge per trade:** 8–18% of notional when filter triggers (estimated from backtest; **actual trading-rule P&L is unmeasured**)
- **Trade frequency:** 3–12 entries/week (seasonally variable)
- **Mean hold:** ~45 days (range 7–365)
- **Hit rate:** 60–70% (directional calls against the crowd — crowd isn't always wrong)
- **Calmar target:** 1.0–2.5 (high uncertainty)
- **Max drawdown (theoretical):** 8–18% over any 90-day window, dominated by oracle dispute losses + model mis-calls on geopolitical tail events

---

## Failure modes

| Mode | What it looks like | Response |
|---|---|---|
| Model drift | Gemini upgraded/degraded; dispute_risk distribution shifts | Calibration-halt fires; re-score sample + compare |
| Oracle tail hit | DR-penalised position still catches a P4 vote; single loss >5% | Expected ~annually; size caps bound the pain |
| Model echo | Edge drops sharply at short re-score intervals | Weekly model-echo diagnostic; see test-protocol.md |
| Scraper breakage | Stale-halts fire regularly | Auto-restart 3× then halt; alert |
| Gemini unavailable | 429s or deprecation | Groq-Kimi fallback in scorer |
| **Death pattern** | Calibration-halt fires, OR 4 consecutive negative weeks + drawdown approaching 15%, OR model-echo test fails | Kill |

---

## Tech stack

- **Language:** Python 3.11
- **Key libraries:** Bot A's libraries + `google-generativeai` (Gemini primary), `chromadb` (RAG), `rank_bm25` (BM25), `sentence-transformers` (embeddings fallback)
- **Data sources:**
  - Polymarket Gamma API (markets)
  - External scorer `/v1/score` HTTP API (Oraclemangle, https://oraclemangle.com)
- **Storage:** SQLite for bot state
- **Models:** the scoring model runs inside the external service; Bot B holds no
  model or embeddings of its own on the HTTP-scorer path.

### Module layout

```
bots/bot_b/
├── __init__.py
├── http_scorer.py      # HTTP client for upstream /v1/score + local persistence fix
├── scoring_sweep.py    # Refreshes stale/missing scores before each tick
├── scorer.py           # DB-backed scorer protocol + StoredScorer test stub
├── filters.py          # Candidate predicates
├── sizer.py            # Kelly + DR penalty
├── executor.py         # Order placement
├── lifecycle.py        # Entry, hold, exit state machine
├── config.py           # Thresholds, Gemini model id, etc.
└── tests/
    ├── test_bot_b_http_scorer.py
    ├── test_filters.py
    ├── test_sizer.py
    └── test_lifecycle.py
```

---

## MVP scope

### Implemented in repo
- `http_scorer.py`, `scoring_sweep.py`, `filters.py`, `sizer.py`, `executor.py`, and `lifecycle.py` are built.
- Bot B daemon now runs market ingest, book snapshots, score refresh, and decision ticks in one loop.
- Paper-mode end-to-end smoke exists via `scripts/seed_dev_fixture.py`.

---

## What Bot B does NOT do (explicit non-goals)

- Does not re-implement the external scorer
- Does not read the external service's DB or depend on its scheduling
- Does not contain or modify the external service's code
- Does not trade markets scored >12 hours ago
- Does not trade multi-outcome / neg-risk markets in v1
- Computes its own Kelly fraction rather than relying on any field from the scorer

---

## Open items specific to Bot B

- **External API availability**: the scorer service must be running and reachable from the bot host.
- **API key provisioning**: set `ORACLEMANGLE_API_KEY`. Do not commit.
- **Scorer fallback**: there is no local scorer fallback yet if the external API is down. That is a real operational dependency.
- **Scorer-echo risk**: see `docs/open-questions.md`. Diagnostic is part of weekly review during paper phase.

---

## References

- `docs/architecture-decision.md` §3 — original decision context
- `docs/decisions-log.md` ADR-003, ADR-004 — why this thesis
- `specs/shared-infra.md` — dependencies
- `specs/test-protocol.md` — how Bot B is judged (including model-echo test)
- The external scorer is documented at https://oraclemangle.com
- Claude Code local memory note on TimesFM (machine-local) — TimesFM deferred-integration note
