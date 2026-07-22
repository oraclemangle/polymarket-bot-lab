# Project History

**Scope:** condensed narrative of the research project behind polymarket-bot-lab
(2026-03 through 2026-07). The full decision trail survives in
[decisions-log.md](decisions-log.md) (ADR-001 onward) and
[open-questions.md](open-questions.md); this file is the readable arc.

## Phase 1 — Dual-track origin (2026-03 to 2026-04)

The project began as a two-bot A/B test: **Bot A (Longshot)** (longshot fade — mechanically
fade sub-5c YES tails) against **Bot B (Oracle)** (LLM directional — size Kelly bets where
an externally calibrated dispute-risk scorer, see https://oraclemangle.com,
diverged from the crowd). The design bet was that the two shared nothing: edge
source, holding period, signal generation, and stress modes were all different,
so live results would identify which class of edge was real.

Longshot was set aside after a walk-forward replay showed the tail-fade unprofitable
as-tested at scale despite a 93%+ hit rate — the jackpot losses ate the grind
(refinement target: extreme-tail exposure; see ADR-033 and the Bot A reports).
Oracle was paused pending a scorer-ensemble rebuild that never cleared its
calibration gate before project retirement (see
[bot-b-reference.md](bot-b-reference.md)); its implementation code is not part
of this export. Integration remains open for anyone with scorer access via
https://oraclemangle.com.

## Phase 2 — Fleet expansion (2026-04 to 2026-05)

The lab widened into a fleet: **Bot C (Pythia)** (Pyth-fed directional on traditional
assets), **Bot D (Nimbus)** (weather — fade mispriced temperature-tail and range markets),
**Bot E (Scribe)** (15-minute crypto Up/Down scalping, which became primarily a market
*recorder*), **Bot F (Sonar)** (whale mirror, later reframed toward cascade detection),
**Bot G (Dash)** (longshot variants on short-horizon crypto), **Bot H (Quill)** (paper maker),
and later paper lanes (**Relay**/J, **Playbook**/K, **Compass**/L, **Meridian**/crypto
fair-value, wallet-tag filters). Every
lane ran paper-first with explicit promotion and pause criteria; several took
tiny live probes.

This phase produced the infrastructure that is the lasting value of the repo:
the shared CLOB client and fee model in `core/`, the backtest and replay tooling
in `scripts/`, the recorder schema (see the companion dataset), the paper-trading
dashboard, and the test suite.

## Phase 3 — Recorder era and empirical discipline (2026-05 to 2026-06)

The project's center of gravity moved from strategy tuning to data collection:
an always-on recorder (Scribe) captured CEX trades and Polymarket market-channel
WebSocket events continuously (first locally, then on a small VPS "canary"
node). Strategy claims were increasingly settled by fill-conditioned replays
against this tape rather than by quote-presence backtests — a distinction that
set aside several lanes that looked profitable under quote-presence only
(stale-quote mirage; see the related ADRs). Most paper lanes were paused with
documented refinement needs (fees, fill realism, sample size) rather than
promoted.

## Phase 4 — Full reassessment (2026-07)

A structured reassessment (see `reports/full-reassessment-2026-07.md`)
ranked every surviving candidate. Verdict: **sports mid-band NO-fade (Playbook)** was the
primary research path (positive point estimate, confidence interval crossing
zero — promising, unproven) with **weather range-fade (Nimbus)** as runner-up
(small live-probe profit, gated on accounting reconciliation). Everything else
was set aside with documented refinement needs, or required high-frequency
infrastructure unsuitable for a small account.

## Phase 5 — Retirement and open-sourcing (2026-07)

The operator retired the project and open-sourced it as this repo plus the
companion dataset (`polymarket-canary-tape`). The export is sanitized: private
infrastructure, personal identifiers, third-party wallet cohorts, and the
closed external scorer product are excluded by design. The honest numbers —
including the negative ones — are retained on purpose: they are what makes the
two surviving candidates worth someone's time, and they show every other bot
as a starting point that needs refinement before it has an edge.
