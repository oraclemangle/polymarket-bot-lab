"""Bot F — sensor + curated paper-mirror (un-archived for paper 2026-04-22, ADR-037).

**Current scope:**

- **Hunter** (`bots/bot_f/discovery.py`): offline nightly ranker. Scores
  Polymarket wallets against quantitative filters and outputs a ranked
  top-N list. Read-only.
- **Mirror** (`bots/bot_f/signal.py`): polls `data-api.polymarket.com/trades`
  per ranked wallet and logs every detected signal to
  `bot_f.db::mirror_signals`, including a hypothetical "would_have_traded"
  label. No orders from this module, ever.
- **Paper Mirror** (`bots/bot_f/paper_mirror.py` — ADR-037 Step 1, added
  2026-04-22): paper-only executor for a curated 4-wallet allowlist. Three
  safety layers lock it to paper mode (env gate + `paper_override=True` +
  per-tick attribute check). `bot_id="bot_f_mirror"` keeps it distinct
  from sensor rows.

**History:** Phase 2 Trigger was cancelled Session 17g (2026-04-17) on the
grounds that (1) 100% of local Mirror signals exceeded the 90s age cutoff
and (2) the copy-trading ecosystem was crowded. Both findings were
revisited 2026-04-22 with newer data: 24,473 of 66,236 signals (37%) now
have `would_have_traded=1`, and a per-wallet data-api P&L retrospective
identified 4 wallets with defensible edge. ADR-037 authorised the
paper-only mirror as Step 1 of a new graduation path.

The original plan was: after 2 weeks of Mirror measurement data, a Phase 2
"Trigger" executor would use ranked wallets + hypothetical-trigger filters
to place live copy-trade orders. Two findings made that path structurally
uneconomic:

  1. Local Mirror data shows 100% of signals hitting the 90s age cutoff
     (0 of 200 local mirror_signals had would_have_traded=1). The homelab
     latency profile cannot win the copy-trade race against on-chain
     Polygon block indexers.
  2. The copy-trading ecosystem is crowded by 2026: PolyProbs, WhaleTrail,
     PolyCopyTrade, @bl888m's "Priority Mode" tooling. Codex peer review
     flagged 2/5 confidence for this strategy path.

Bot F's value is reframed as INTELLIGENCE / SENSOR infrastructure:

  - Hunter's 45-wallet ranked dataset is useful for understanding where
    smart money is going.
  - Mirror's signal stream + "would_have_traded" labels are measurement
    data, not trade candidates.
  - Future F-2 work may add a `crowd_signals` table as an opt-in
    down-weighter for Bot A/B candidate filters ("don't enter markets
    where 6+ known copy-bots just entered").

**Scope boundary:** the paper mirror is Step 1 of three. Steps 2 (paper +
curated-sharps live) and 3 (full-fleet graduation) require an ADR reversal
and 2 weeks of successful paper data. Adding new executor surface beyond
`paper_mirror.py` still needs a fresh ADR.

See `docs/bot-f-demotion-plan.md` for Phase 2 cancellation history and
`bots/bot_f/CLAUDE.md` for operating rules.
"""
