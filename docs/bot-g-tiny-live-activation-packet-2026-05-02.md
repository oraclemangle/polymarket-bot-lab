# Bot G Tiny-Live Activation Packet

**Date:** 2026-05-02
**Status:** Approved for activation.
**Owner:** the operator approves; Claude maintains implementation/reporting.

## Decision Snapshot

This packet records the approved first live rung for Longshot Prime Live
(`bot_g_prime_live`) and the retained paper shadow (`bot_g_prime`).

| Item | Value |
|---|---:|
| Live wallet allocation | `$200` |
| Fixed entry size | `$5` |
| Entry size as wallet share | `2.5%` |
| Daily entry cap | `20` entries |
| Daily gross notional cap | `$100` |
| Daily gross as wallet share | `50%` |
| Max open positions | `10` |
| Max intended open stake | `$50` |
| Max open stake as wallet share | `25%` |

## Sizing Rule

The tiny-live probe uses fixed-notional sizing only. Do not switch Bot G to
bankroll-fraction or Kelly sizing for the first live rung. `$5` stays aligned
with the current paper stake so live-vs-paper execution and fill quality stay
comparable.

With `$5` entries and `20` entries/day, the entry-count cap and `$100` daily
gross cap bind together.

## Current Runtime Posture

As of the ADR-078 activation work, Bot G runs as two ledgers:

- `bot_g_prime_live`: `BOT_G_ENV=live`, `BOT_G_DRY_RUN=false`,
  `POLYMARKET_ENV=live`, `BOT_G_LIVE_APPROVED_AT=2026-05-02`, `4c-5c`.
- `bot_g_prime`: `BOT_G_ENV=paper`, `BOT_G_DRY_RUN=true`, `4c-8c` paper
  shadow.

Production has previously shown global `POLYMARKET_ENV=live`; this is not by
itself enough to make Bot G live because Bot G's own env and dry-run flags keep
`paper_override=true`.

## Activation Boundary

Do not broaden Bot G live beyond ADR-078 without a new decision. Jackpot and
scalp units remain disabled/archived during this live probe.

## Evidence Boundary

This first rung is a plumbing and edge-transfer probe. It is not evidence to
increase size until the post-live success criteria pass, including positive
ex-largest-two-wins ROI after `50` live fills.
