# Bot G Tiny-Live Runbook

**Date:** 2026-05-02
**Status:** Authorized for ADR-078 tiny-live activation.
**Owner:** the operator approves; Claude maintains reporting.

## Scope

This runbook governs the first Longshot Prime (Bot G Prime) real-wallet probe
approved by the operator on 2026-05-02. ADR-085 superseded the original ADR-078
`4c-5c` band with a separate `bot_g_prime_live` unit at observed
`3.5c-5.5c`, one-tick transfer bidding capped at `5.5c`, `20` entries/day,
`$100` daily gross notional, and `10` max open positions. ADR-118 reduced the
active live entry size from `$5` to `$3` on 2026-05-07 because the Bot G edge
evidence weakened while the operator still wanted the live probe to continue. It does
not authorize any size increase, broader live entry band, jackpot or scalp live
unit, or Ledger treasury action.

The existing `bot_g_prime` service remains the `4c-8c` paper shadow. It must
stay paper/dry-run while the live probe runs.

Live activation has three separate runtime flags. All three must be understood
before any future switch:

| Flag | Paper value | Live-probe value |
|---|---|---|
| `BOT_G_ENV` | `paper` | `live` |
| `BOT_G_DRY_RUN` | `true` | `false` |
| `POLYMARKET_ENV` | `paper` | `live` |

`BOT_G_ENV=live` plus `BOT_G_DRY_RUN=false` is only Bot G's live intent.
Real CLOB orders also require global `POLYMARKET_ENV=live`; otherwise
`ClobWrapperV2` remains effective-paper.

## Current Posture

- Current live strategy: Longshot Prime Live (`bot_g_prime_live`).
- Current paper shadow: Longshot Prime Shadow (`bot_g_prime`).
- Current live band: observed `3.5c-5.5c`, submitted limit capped at `5.5c`.
- Current paper collection band: `4c-8c`.
- Current historical positive-signal band: `4c-5c`; live transfer proof is
  still incomplete.
- Current scale blocker: OQ-063 post-live proof is not complete.

## Approved Tiny-Live Probe

These are approved caps for the first plumbing/edge-transfer rung only:

| Item | Proposed value |
|---|---:|
| Live wallet allocation | `$200` |
| Starting trade size | `$3` (`1.5%` of wallet; reduced by ADR-118) |
| Daily entry cap | `20` entries |
| Daily gross notional cap | `$100` (`50%` of wallet turnover) |
| Max open positions | `10` |
| Max intended open stake | `$30` (`15%` of wallet at `$3` entries) |

This is a tiny-live probe, not ROI-live scaling. Its first job is to prove
live execution, order reconciliation, fills, slippage, and dashboard telemetry
match expectations at the smallest useful size.

Tiny-live sizing remains fixed-notional, not bankroll-fraction or Kelly
sizing. The current entry size is `$3`; the original `$5` entry size was
reduced by ADR-118 after the project notes and Becker/live-transfer evidence
made the Bot G edge less convincing. At the current `$3` entry size and `20`
entry/day cap, the entry-count cap normally binds before the `$100` daily gross
cap.

## Activation Gate

Activation is limited to ADR-078 and requires:

1. `polymarket-bot-g-prime-live.service` uses `bot_g_prime_live`, not
   `bot_g_prime`.
2. Live unit has `BOT_G_ENV=live`, `BOT_G_DRY_RUN=false`,
   `POLYMARKET_ENV=live`, and `BOT_G_LIVE_APPROVED_AT=2026-05-02`.
3. Live unit has `BOT_G_MIN_ENTRY_PRICE=0.035`,
   `BOT_G_MAX_ENTRY_PRICE=0.055`, and
   `BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS=1`.
4. Live caps are `20` entries/day, `$100` daily gross, and `10` max open.
5. `polymarket-bot-g-prime.service` remains paper/dry-run on `4c-8c`.
6. `polymarket-bot-g-jackpot` and `polymarket-bot-g-scalp` remain disabled.

## Code-Level Tiny-Live Safety

Session 73 added the live-path accounting fixes found by the Opus audit:

- live Bot G orders persist with live/open status instead of `PAPER_OPEN`;
- paper eager-fill remains paper-only;
- when the effective CLOB path is live, Bot G polls
  `Portfolio.reconcile_live_fills()` for live fills;
- live-only caps are code-visible separately from paper collection caps:
  `BOT_G_LIVE_MAX_DAILY_ENTRIES=20`,
  `BOT_G_LIVE_MAX_CONCURRENT_POSITIONS=10`, and
  `BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=100`;
- `BOT_G_LIVE_WALLET_USD=200` is code-visible for dashboard/reporting and
  config validation;
- the trader writes `bot_g.runtime_state` events with `BOT_G_ENV`,
  `BOT_G_DRY_RUN`, `POLYMARKET_ENV`, `paper_override`, and
  `effective_paper`, so the dashboard can read trader state rather than only
  dashboard-process environment defaults.

These fixes improve live accounting and visibility. They do not change the
paper entry band, CEX/depletion gates, or paper daily entry cap.

## Success Criteria

| Milestone | Pass condition |
|---|---|
| `10` live fills | No auth, sizing, reject-loop, duplicate-order, or unexpected-price errors. |
| `20` live fills | Median live entry slippage stays within one tick of paper expectation. |
| `50` live fills | Live fills remain comparable to the current `3.5c-5.5c` lane and the historical `4c-5c` cohort after outlier review. |
| `50` live fills | Ex-largest-two-wins ROI remains positive before any size increase. |

Profit alone is not proof. Jackpot-shaped wins must still survive
ex-largest-win and ex-largest-two analysis before any size increase.

## Halt Conditions

Immediately halt and return to paper if any of these occur:

- any real order appears outside the approved caps;
- any unexpected live open position appears;
- any order reconciliation mismatch appears between CLOB, local DB, and
  dashboard;
- any live fill records an unexpected price, side, token, or market;
- daily realised loss exceeds the operator-approved tiny-live loss cap;
- Bot G recorder/book telemetry is stale during an entry window;
- the dashboard cannot load `/api/bot-g`.

## Paper Rollback Procedure

These are manual steps if rollback is needed.

1. Stop and disable `polymarket-bot-g-prime-live.service`.
2. Reload systemd.
3. Confirm `polymarket-bot-g-prime.service` remains:
   - `BOT_G_ENV=paper`
   - `BOT_G_DRY_RUN=true`
   - `BOT_G_MIN_ENTRY_PRICE=0.04`
   - `BOT_G_MAX_ENTRY_PRICE=0.08`
4. Restart only `polymarket-bot-g-prime`.
5. Confirm `/api/bot-g` reports:
   - `Trader Mode = DRY_RUN`
   - tiny-live probe status `paper_observing`
   - `effective_paper=true`
   - `live_fills_count` unchanged after rollback
6. Run the focused Bot G/dashboard tests.
7. Record the rollback in `CHANGELOG.md` and `MEMORY.md`.

## Reporting Surfaces

The shared Bot G tiny-live probe plan now appears in:

- dashboard `/api/bot-g` under `live_probe`;
- the Bot G dashboard tab;
- hourly `scripts/fast_roi_report.py` output.
- daily `scripts/bot_g_lead_bucket_roi_report.py` output for lead/price
  bucket research.

All three surfaces must continue to distinguish `bot_g_prime_live` from the
`bot_g_prime` paper shadow.

See also:

- `docs/bot-g-tiny-live-activation-packet-2026-05-02.md`
- `docs/bot-g-paper-shadows-2026-05-05.md`
