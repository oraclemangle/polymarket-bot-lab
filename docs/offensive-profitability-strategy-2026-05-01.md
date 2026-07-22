# Offensive Profitability Strategy

**Date:** 2026-05-01
**Status:** Active strategy, supersedes the defensive emphasis in
`docs/opus-profitability-edge-handoff-2026-05-01.md`.
**Owner:** Codex executes; the operator approves any live-capital step.

## 2026-05-01 Fast-ROI Update

Bot B remains the moat, but it is not the fast-ROI path because capital can
lock until resolution. Fast ROI priority is now:

1. **Bot E:** lead fast-turnover candidate.
2. **Bot G Prime:** fast challenger, high variance.
3. **Bot D:** first real-wallet candidate track, but daily/low-lock-up subset
   only until capacity is proven.
4. **Bot F:** shared crowd-sensor infrastructure, not a direct whale-copy bot.
5. **Bot B:** background moat sprint.

The active to-do list is
`docs/fast-roi-todo-2026-05-01.md`.

The current production evidence packet is
`docs/reports/fast-roi-production-2026-05-01.md`.

## One-Line Strategy

Move the project from defensive paper proof-outs to an offensive moat build:
**Bot B/oraclemangle becomes P0, fusion becomes the product, and D/E/G are
execution surfaces that must prove capacity and edge under hard time boxes.**

## What Changed After Opus Review

Opus was right on the strategic error: the previous handoff protected capital
but did not force fast ROI. It ranked Bot D first because Bot D is the closest
craft edge, but it demoted the only true moat, Bot B's UMA dispute-risk
calibration, to P1/P2. That is now corrected.

The revised hierarchy:

1. **Bot B P0:** local-owned scorer, base-rate estimator, disagreement/abstain
   gate, hard ECE/Brier thresholds.
2. **Fusion P0/P1:** Bot F crowd flow becomes a cross-bot feature, not a
   standalone copy trader.
3. **Bot D near-term cashflow candidate:** only if capacity, lock-up, and
   Bot-A-shaped tail-risk checks survive.
4. **Bot E/G paper probes:** useful only if maker-fill quality and adverse
   selection clear a quantified gate.

## Strategic Commitments

### Commitment 1: Bot B Is P0

The oraclemangle/UMA dispute-risk data is the only asset in the fleet that a
public bot operator cannot replicate in a two-week sprint. Public weather
station logic, wallet dashboards, and ensemble disagreement are good craft.
They are not durable moats by themselves.

**Deadline:** 2026-05-15.

**Deliverables:**

- Scorer-health state visible in DB/events.
- Halted Bot B skips scoring sweeps unless `BOT_B_SCORE_WHILE_HALTED=true`.
- Local scorer ownership decision recorded: this repo vs the external scorer product (https://oraclemangle.com).
- E1 historical base-rate estimator populated from the local calibration DB.
- E2 external-scorer estimator wrapped behind the ensemble interface.
- Explicit unhalt metrics:
  - held-out Brier <= `0.06`;
  - weighted ECE <= `0.05`;
  - every decile with `n >= 10` has calibration gap <= `0.05`;
  - stale scores fail closed at `MAX_SCORE_AGE_HOURS`;
  - no live order path until paper decisions pass.

**Kill/pause rule:** if local scorer ownership and calibration cannot be made
credible by 2026-06-01, Bot B pauses as a trading bot and remains only a
research asset.

### Commitment 2: Fusion Is The Product

The unique edge is not one bot. It is a private stack:

- **B:** calibrated resolution/dispute probability.
- **F:** wallet/crowd saturation and post-cascade drift.
- **D:** settlement-exact external truth where relevant.
- **E/G:** microstructure veto/confirm signals where relevant.

The first fusion implementation should be a **scoring layer**, not one opaque
fused auto-trader. Attribution stays visible: each estimator votes, abstains,
or vetoes. Execution remains bot-specific until the scoring layer proves it
improves outcomes.

**Deadline:** first fusion report by 2026-05-22.

**Deliverables:**

- Bot F cascade report with post-signal drift at 1m/5m/30m/6h.
- One table showing whether the F signal would improve Bot B/D/E/G decisions.
- Chosen first integration target: B estimator, D veto, E veto, or no-use.

### Commitment 3: No More Noise-Floor Live Tests

`$100` tiny-live is a plumbing test, not an ROI test. ROI evidence requires
meaningful order size. The ladder is now split:

- **Plumbing live:** up to `$100`, `$5-$10` orders, validates live fills,
  exits, fee accounting, reconciliation, and alerts. No ROI conclusions.
- **ROI live:** `$500-$1,000` allocated capital, `$25-$50` orders, only after
  paper + plumbing show execution reliability. Requires the operator's explicit
  approval.

No real-money action is authorized by this file.

### Commitment 4: Bayesian Promotion Beats Fixed N

Fixed `N=50` promotion gates are too blunt, especially for correlated weather
contracts. Each candidate must report:

- posterior `P(EV > threshold | data)` after every 25 closed trades;
- archive when posterior is below `0.2`;
- promote when posterior is above `0.8`;
- block-bootstrap or week/city/day clustering where trades are correlated;
- trimmed-mean ROI and largest-win contribution.

For Bot D specifically, effective sample size must be reported. Fifty same
forecast-cycle trades are not fifty independent observations.

### Commitment 5: Hard Time Boxes

- **2026-05-15:** Bot B P0 scorer-health/local-ownership packet complete.
- **2026-05-22:** first fusion/crowd-flow report complete.
- **2026-06-01:** exactly one of D/E/G has a credible live-capital packet, or
  D/E/G are archived/paused as live candidates.
- **2026-06-01:** Bot B is locally owned and producing calibrated paper
  decisions, or Bot B is paused as a trading bot.

No "one more iteration" without a new ADR.

## Bot-Specific Offensive Gates

### Bot B

**Purpose:** moat engine.

**Next action:** stop halted sweeps, then finish local ensemble ownership.

**Capacity:** highest ceiling because it can trade across UMA-resolved
categories, but cadence depends on eligible market flow and scorer freshness.

### Bot D

**Purpose:** near-term cashflow candidate if capacity holds.

**Required new analysis:**

- capital lock-up by contract duration;
- realistic monthly turnover under `$2k` hot-wallet cap;
- order-book depth and slippage at `$25/$50`;
- same-shape-as-Bot-A risk: if hit rate is high but tail losses erase EV,
  archive rather than tune;
- seasonality: test whether temperature-tail variance collapses in spring and
  autumn.

**Immediate archive trigger:** hit rate above `85%` and trimmed/ex-outlier ROI
negative after fees/slippage.

### Bot E

**Purpose:** maker-side microstructure and reward-subsidy candidate.

**Required new analysis:**

- adverse-selection ratio where maker rewards would break even;
- actual reward reconciliation, not assumed accrual;
- fill-quality by TTL/offset;
- order-book depth model instead of placeholder 1c/2c slippage.

Rewards are not banned. They are treated as a hedge/subsidy until reconciled.

### Bot F

**Purpose:** cross-bot crowd intelligence.

**Next action:** competitive-intel and cascade drift report. Direct mirror
expansion stays blocked until the crowd signal proves positive forward value.

### Bot G Prime

**Purpose:** narrow asymmetric tail probe.

**Required new analysis:** causal depletion/reload signal, no lookahead,
confirmed vs unconfirmed entries, ex-largest-win ROI. If the edge disappears
after trimming, pause.

## Competitive Intel Requirement

The project cannot claim "contrarian" without a map of visible bot behavior.
The first one-pager must identify public archetypes, not necessarily perfect
wallet labels:

| Archetype | Current public evidence | Why it matters |
|---|---|---|
| Copy-trading bots | QuickNode's 2026 guide shows wallet-monitor + mirror-buy bot construction; multiple public ads/tools exist. | Direct mirror is crowded; Bot F should measure crowd impact. |
| Market makers | Polymarket official docs describe continuous quoting, orderbook WSS, and liquidity rewards. | Maker rewards may matter, but adverse selection must be modeled. |
| Liquidity reward farmers | Official rewards docs score resting orders daily and emphasize two-sided tight quoting. | Break-even maker strategies may exist if rewards reconcile. |
| Short-horizon crypto scalpers | Public guides and repo history show crypto bots are common and fee-sensitive. | Bot E/G must avoid taker churn and prove maker/fill quality. |

Current public sources checked 2026-05-01:

- QuickNode, "Building a Polymarket Copy Trading Bot" updated 2026-02-20:
  <https://www.quicknode.com/guides/defi/polymarket-copy-trading-bot>
- Polymarket Market Maker overview:
  <https://docs.polymarket.com/market-makers/overview>
- Polymarket Liquidity Rewards:
  <https://docs.polymarket.com/market-makers/liquidity-rewards>

## What I Need From the operator

Not needed now. The next implementation steps are paper/local only.

Needed before any ROI-live test:

1. Approval for the ROI-live capital band: `$500-$1,000`.
2. Preferred first ROI-live candidate if two pass at once.
3. Whether a `$100` plumbing-live test is allowed once code says it is safe.
