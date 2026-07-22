# Bot D Maker Live Probe — 2026-05-15

**Status:** built locally; deploy/start only after focused tests and host
preflight pass.

## Purpose

Bot D's existing live weather lane is taker-first: it crosses when the edge is
large enough. The maker probe tests a narrower question: can Bot D collect
more live weather evidence, better entry prices, and lower execution cost by
posting short-lived non-crossing BUY quotes instead of crossing the spread?

## Approved packet

| Control | Value |
|---|---:|
| Bot id | `bot_d_maker_live_probe` |
| Wallet posture | `$200` |
| Minimum quote notional | `$5` |
| Maximum order notional | `$10` |
| Daily gross cap | `$100` |
| Open exposure cap | `$100` |
| Max concurrent positions/orders | `20` |
| Quote max age | `180s` |
| Forecast max age | `1800s` |
| Cities | existing verified Bot D settlement cities only |
| Order style | BUY maker quotes only |
| Deployment unit | `polymarket-bot-d-maker-live.service` |

The dollar caps are the hard risk unit. The share target is normally `5-10`
shares depending on quote price, but very cheap quotes can exceed `10` shares
only when required to reach the `$5` minimum and still stay below the `$10`
order cap.

## Phases

1. **Build isolated maker lane.** Separate module, bot id, registry entry,
   systemd unit, dashboard block, and tests.
2. **Preserve live safety.** Enforce live authorization, separate bot id,
   emergency/per-bot halt, fleet cap, verified settlement, known end date,
   stale forecast block, NWS-fallback block, and non-crossing quote guard.
3. **Deploy with no manual orders.** Install the service on the bot container, run focused
   tests, reload systemd, then start only the dedicated maker service.
4. **First evidence gate.** Review after `10` maker fills, `25` maker quotes,
   or `48h` of runtime, whichever comes first.
5. **Decision gate.** Keep, pause, or tune based on fill rate, cancel rate,
   realised P&L, adverse selection, quote age, and comparison to the taker
   `bot_d_live_probe` lane.

## Kill switches

- Stop service: `polymarket-bot-d-maker-live.service`.
- Per-bot halt id: `bot_d_maker_live_probe`.
- Fleet-wide emergency halt still applies.
- Watchdog cancel routing uses `BOT_D_MAKER_ENV`.

## Review metrics

- Quotes placed, cancelled, expired, and filled.
- Fill rate by quote price bucket.
- Average quote edge at placement.
- Average fill slippage versus best ask at quote time.
- Realised P&L and ROI.
- Open exposure versus `$100` cap.
- Daily gross versus `$100` cap.
- Any duplicate quote or stale quote older than `180s`.

## Non-goals

- No taker order path.
- No city expansion.
- No cap/size increase.
- No changes to `bot_d_live_probe`.
- No treasury or wallet key changes.
