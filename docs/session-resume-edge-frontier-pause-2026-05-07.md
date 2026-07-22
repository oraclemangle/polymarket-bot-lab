# Session Resume — Edge-Frontier Work Paused

**Paused:** 2026-05-07
**Reason:** Operator pivoted to test a new strategy. Resume when that work concludes.
**Picks up from:** Sessions 197 (NegRisk closure), 198 (Bot D post-mortem + dormant-ideas sweep), 199 (builder-code audit + Grok edge-hunt + cross-event NegRisk DEAD).

---

## Critical new constraint (operator clarification, 2026-05-07)

**Wallet ceiling is $5,000, not $200.** $200 is current scale; operator can scale up to $5k once a real edge is found. This re-opens several frontiers that were declared "out-of-scope at $200" but does NOT revive corners closed for capital-independent reasons.

### What capital scaling DOES change

| frontier | old verdict | new verdict |
|---|---|---|
| Builder-code rebate harvest via maker-flow bot | BLOCKED-by-scope (ADR-121) | **DECISION POINT** — at $5k, Grok-cited $16-30/day rebate yields ($480-900/month) become material. But maker-flow bot is on `CLAUDE.md` out-of-scope list. Operator must explicitly lift that entry to unlock. |
| Bot H Betfair sharp-line lag | "biggest scope" | **TRACTABLE** — UK-eligible, Polymarket sports WSS public no-auth since Apr 2026, $5k makes per-trade edge × N stop being noise. Now the leading "find a real edge" candidate. |
| Hardware wallet path (OQ-014) | "only matters above $5k" | **TRIGGER CONDITION MET** — Ledger treasury + hot trading wallet pattern is now appropriate. ~1 session setup. |
| Longer-horizon crypto + Mar-6-2026 maker rebates | needs operator scope | **WORTH PAPER-TESTING** — at $5k, paper samples could validate edge. Operator to choose horizon (1H/4H/daily/weekly). |

### What capital scaling does NOT change

- **Cross-event NegRisk-vs-binary arb** stays DEAD. Strategy-adversary's killshot was "leg risk eats spread"; at $5k that becomes 0.5% per bad fill instead of 2-5%, BUT the real alpha is semantic matching at sub-second latency, already won by PolyBetbot/Wintermute affiliate. Capital doesn't fix speed.
- **Crypto 5m/15m corner** stays closed (10 strategy variants exhausted; no edge regardless of scale).
- **Paired-token within-market arb** stays killed (real BBO data showed 0 arbs across 1.05M snapshots; capital doesn't make a non-existent edge appear).
- **NegRisk basket arb (within-event)** stays closed (252 events have illiquid field markets with `vol=0, liquidity=0`; capital can't buy what isn't being sold).
- **Settlement sweep** stays killed by Opus review (fees + concentration + correlated-tail; bigger capital makes the correlated tail worse, not better).
- **Bot A high-hit-rate fade** stays archived (variance, not capital, was the issue).
- **Bot B oraclemangle Kelly** stays parked (operator: "too slow, months per trade").
- **Bot D paper longshot fade** stays archived (outlier-dominance variance is structural).
- **Hard out-of-scope per `CLAUDE.md`:** cross-venue arb (Kalshi US KYC), mobile/webapp, port to other venues.

---

## Three decisions pending operator input

When edge-frontier work resumes, these are the questions to answer:

### Decision 1: Lift "market-making / rebate farming bot" from CLAUDE.md out-of-scope?

**Why it matters now:** Builder-code infra is fully plumbed (ADR-048). Rebate yields cited by Grok-verified X handles (`@appledog_xyz`, `@0xsolvix`) are $16-30/day on modest capital. At $5k, that's $480-900/month — material edge.

**The bear case:** maker fills give adverse selection (you're the maker on trades where the counterparty has information). Against MM whales already running this strategy, the directional loss could exceed rebate income. Need `strategy-adversary` adversarial review on a specific bot spec before greenlighting.

**Required for greenlight:**
1. Operator explicit approval to lift the out-of-scope entry
2. `strategy-adversary` review of a concrete maker-flow spec (deep-book limits in sports / politics, exit-on-resolution, $20-50 entries)
3. Paper-first run for 30 days minimum to confirm rebate-vs-adverse-selection net is positive

### Decision 2: Hardware wallet path now or after edge found?

**Trigger:** OQ-014 was parked because $200 didn't justify the friction. $5k crosses that threshold.

**Standard pattern:** Ledger holds the treasury, separate hot wallet trades. Two manual transfers per top-up cycle. the VPN provider VPN unchanged.

**Effort:** ~1 session — set up Ledger + Safe-on-Polygon, transfer pattern, document the operator manual steps.

**Recommendation:** Do this BEFORE scaling actual capital exposure, not after. Doing it after is a forced project at the worst possible moment.

### Decision 3: Bot H Betfair priority

**Thesis:** Polymarket reacts slower to Betfair Exchange odds moves on the same UK/EU sports event. Betfair is price-discovery venue (sharp lines); Polymarket is betting-narrative venue. Latency-arb between two markets pricing the same outcome.

**Pre-conditions met:**
- UK-eligible (operator has Betfair access)
- Polymarket sports WSS public no-auth since Apr 2026 (was the historical blocker)
- $5k makes per-trade edge × N trades stop being noise

**Pre-conditions NOT yet evaluated:**
- Sport-by-sport liquidity (some sports have thin Polymarket books)
- Semantic matching of Betfair markets to Polymarket markets (similar to cross-event NegRisk problem but venue-different rather than within-venue)
- Polymarket V2 fee schedule across sport categories
- Latency budget (Betfair tick → Polymarket order placement under what wall-clock?)

**Required workflow before any code:**
1. `trading-research` agent: descriptive briefing on Bot H mechanics + data sources + execution model
2. `strategy-adversary` agent: bear case on the specific spec
3. Operator decision based on both

**Estimated scope:** 2-3 sessions to scaffold a paper-first version. 1-2 weeks of paper data before live consideration.

---

## Recommended resume order (when this work picks up)

1. **First action:** ask the three decisions above. Don't guess.
2. **If Decision 2 = yes:** hardware wallet setup (1 session, foundational, do before scaling).
3. **If Decision 3 = priority:** Bot H Betfair scaffolding via `trading-research` + `strategy-adversary` parallel review. Most plausible "find a real edge" frontier.
4. **If Decision 1 = yes:** maker-flow bot spec + `strategy-adversary` adversarial review.
5. **In parallel (any decision combo):** reward-cascade 14-day passive log (zero-risk, free-roll, instruments OQ-039's "$50-150/day" claim that's never been validated).
6. **Cheap plumbing whenever:** PolyVerify wallet-tag features as a feature column for any directional lane (data already on disk at `data/polyverify_wallets.csv`, just never plumbed).

---

## Active session reference

- `MEMORY.md` Session 197 / 198 / 199 entries
- `CHANGELOG.md` 2026-05-07 entries (3 sessions)
- `docs/decisions-log.md` ADR-119 (NegRisk closure), ADR-120 (Bot D split), ADR-121 (builder-code BLOCKED)
- `docs/reports/polymarket-negrisk-closure-2026-05-07.md`
- `docs/reports/bot-d-post-mortem-2026-05-07.md`
- `docs/reports/dormant-ideas-sweep-2026-05-07.md`
- `docs/reports/builder-code-rebate-audit-2026-05-07.md`
- `docs/external-watch-list.md` — handles + wallets to monitor (does not require active engagement)
- `.claude/agents/strategy-adversary.md` — adversarial review subagent
- `.claude/agents/trading-research.md` — descriptive research subagent

## Resume-trigger check

When this work resumes, verify:
- [ ] Operator answers the 3 decisions
- [ ] No new closures landed in interim (check Sessions 200+)
- [ ] Bot D live_probe sample reached `30` closes (per ADR-120 trigger)
- [ ] Polymarket V2 fee schedule unchanged (re-check builder-code mechanics if changed)
- [ ] No new Polymarket V3 deploy (would invalidate plumbing assumptions)
