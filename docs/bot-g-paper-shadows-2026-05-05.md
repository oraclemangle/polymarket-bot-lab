# Bot G Paper Shadows

**Date:** 2026-05-05
**Status:** active plan
**Owner:** Claude implements; the operator reviews live changes.

## Purpose

Bot G Prime Live stays unchanged while paper lanes collect parameter
evidence. These services do not place real-money orders and do not alter the
live unit's wallet, size, band, symbols, caps, or halt logic.

## Services

| Unit | Bot id | Mode | Band | Window | Symbols | Purpose |
|---|---|---|---|---|---|---|
| `polymarket-bot-g-prime.service` | `bot_g_prime` | paper | `4c-8c` | `45s` | `BTC,ETH,SOL,XRP,DOGE` | Continuity baseline. |
| `polymarket-bot-g-prime-shadow.service` | `bot_g_prime_shadow` | paper | `3.5c-5.5c` | `60s` | `BTC,ETH,SOL` | Direct paper mirror of the current live lane. |
| `polymarket-bot-g-prime-late-cheap.service` | `bot_g_prime_late_cheap` | paper | `1c-3c` | `30s` with `5s` fresh-clock floor | `BTC,ETH,SOL` | Forward paper test of the replay-favoured late-cheap lane. |
| `polymarket-bot-g-prime-take-profit.service` | `bot_g_prime_take_profit` | paper | `3.5c-5.5c` entry | `60s` entry; synthetic exit only from `25s` to `8s` | `BTC,ETH,SOL` | Paper proof of the take-profit idea: buy the live-mirror tail, sell if best bid reaches `50c` before close per ADR-128. |

## Success Criteria

The live-mirror shadow is successful if it produces at least `50` closed paper
positions and gives a clean same-rule comparison against `bot_g_prime_live`.
It is a measurement lane, not a promotion argument by itself.

The late-cheap shadow is interesting only if it reaches at least `50` closed
paper positions and remains positive after excluding the largest win and the
largest two wins. It is not eligible for live consideration until replay and
forward paper agree directionally, and a separate ADR approves any live change.

The take-profit shadow is successful only if it improves realised paper P&L
versus the live-mirror shadow after at least `50` entries and preserves upside
after excluding the largest one and two exits. The exit is a paper-only
synthetic SELL at the recorder's observed best bid; it is not a live exit
router and does not submit real sell orders.

## Reporting

`scripts/bot_g_lead_bucket_roi_report.py` now groups Bot G orders by mode,
bot id, fresh lead bucket, submitted-limit bucket, symbol, and side. The daily
timer writes the latest JSON and Markdown under:

`/home/bot/polymarket-bot/data/reports/bot_g_lead_bucket/`

`scripts/bot_g_recorder_join_diagnostic.py` is a read-only manual diagnostic
for joining Bot G orders to the Crypto Recorder book tape around submit time.

## Guardrails

- Do not change `polymarket-bot-g-prime-live.service` as part of paper-shadow
  work.
- Do not promote the `1c-3c` late-cheap lane to live before OQ-068 has enough
  forward evidence.
- Do not promote the take-profit lane to live until latency, queue position,
  exit fill probability, and a real CLOB sell path have been separately
  reviewed and approved.
- Stop or disable either new paper unit if recorder load, dashboard health, or
  Bot G live reconciliation is degraded.
