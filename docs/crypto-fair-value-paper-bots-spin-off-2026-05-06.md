# Crypto Fair-Value Paper Bots Spin-Off

**Date:** 2026-05-06
**Status:** next-session implementation brief.
**Owner:** Claude implements; the operator decides any later paper deployment and any
future live consideration.
**Scope:** paper-only research bots for Polymarket BTC/ETH/SOL 5-minute and
15-minute crypto Up/Down markets. The shared crypto recorder may capture
XRP/DOGE as record-only context, but these fair-value scoring lanes remain
BTC/ETH/SOL-only until a symbol-split report clears separate XRP/DOGE gates.

## Purpose

Create two new paper-only bots to forward-test the two strategy families that
screened positive in the 72-hour recorder validation:

1. `probability_gap`
2. `brownian_fair_value`

These are not live bots. They must not change Bot G Prime Live, Bot D, wallets,
caps, scored fair-value symbols beyond BTC/ETH/SOL, live order paths, or CLOB
live settings.

## Evidence Source

Latest validation report:

- `docs/reports/crypto-strategy-validation-72h-2026-05-06.md`
- Recorder snapshot: `2026-04-30 13:13:01 UTC` to
  `2026-05-03 13:32:53 UTC`
- Coverage: `689` markets, `17,895` decision points
- Outcome labels: CEX-proxy labels, not final Chainlink/Polymarket settlement
  labels
- Slippage stress: `0.5c`, `1c`, and `2c` per share

Headline at `1c/share` slippage:

| Strategy | Signals | Hit rate | Avg ROI | Ex-largest-2 ROI | Result |
|---|---:|---:|---:|---:|---|
| `probability_gap` | `5,045` | `73.6%` | `+34.4%` | `+33.5%` | Best candidate |
| `brownian_fair_value` | `5,815` | `71.1%` | `+25.3%` | `+24.7%` | Strong candidate |
| `cex_order_flow` | `3,897` | `46.3%` | `+5.3%` | `+4.1%` | Filter only |
| `closing_window_pin_fade` | `191` | `30.9%` | `-4.4%` | `-12.2%` | Reject for now |

## Critical Caveat

The validation currently labels outcomes using recorded Binance/CEX start/end
prices. Polymarket crypto Up/Down markets resolve from the specified oracle
source, not from our Binance proxy. The paper bots can be built now, but no
live decision is valid until actual settlement or Chainlink labels confirm the
same edge.

## Proposed Paper Bots

| Bot id | Proposed systemd unit | Strategy | Mode | Universe |
|---|---|---|---|---|
| `crypto_probability_gap_paper` | `polymarket-crypto-prob-gap-paper.service` | Broad model-vs-market probability gap | Paper only | BTC/ETH/SOL, 5m/15m |
| `crypto_brownian_fv_paper` | `polymarket-crypto-brownian-fv-paper.service` | Stricter Brownian fair-value gap | Paper only | BTC/ETH/SOL, 5m/15m |

Both bots should use separate `bot_id` values and separate order/report rows so
their results can be compared independently.

Naming note, 2026-05-09: do not label either lane as "Bot I". That alias is
retired because it was also used for a separate wallet-persistence idea. The
operator-facing names are **Crypto FV Probability Gap Paper** and
**Crypto FV Brownian Paper**.

## Shared Data Inputs

Required live inputs:

1. Crypto Recorder market discovery:
   - condition id
   - question
   - end time
   - YES/NO token ids
   - symbol
   - duration, when known
2. CEX trade feed:
   - BTCUSDT
   - ETHUSDT
   - SOLUSDT
   - local received timestamp
   - exchange timestamp when available
   - price
   - size
   - aggressor direction where available
3. Polymarket book or price state:
   - best ask for YES and NO
   - best bid for YES and NO
   - spread
   - top-level depth
   - book timestamp
4. Main DB paper-order storage:
   - paper order row
   - paper fill row if simulated fill succeeds
   - paper position row
   - later paper settlement row

Do not use live wallet state or real order placement.

## Common Market Filters

Apply these filters to both bots:

1. Scored symbols: BTC, ETH, SOL only. XRP/DOGE may be recorded by the shared
   crypto recorder, but are not eligible for these fair-value paper entries.
2. Durations: 5-minute and 15-minute crypto Up/Down markets only.
3. Remaining time:
   - 5m markets: `30s` to `300s` before close.
   - 15m markets: `30s` to `600s` before close.
4. Spread: skip if effective YES/NO spread is above `4c`.
5. Depth: skip if selected side has less than `$30` visible top-level depth.
6. Data freshness:
   - CEX data age must be `<= 2s`.
   - PM book/price age must be `<= 5s`.
7. Chaos filter:
   - skip if recent sampled volatility is above the 99th percentile once that
     percentile is available;
   - until percentile history exists, skip if the latest 60s absolute CEX move
     is greater than `1.5%`.
8. No duplicate entries:
   - at most one open paper position per bot per condition id.
   - if both bots signal the same side, record both paper ledgers separately,
     but tag the overlap for later analysis.

## Paper Fill Model

The first implementation must not use optimistic "offer existed equals fill"
paper logic.

Use three simultaneous fill tracks:

1. `paper_taker_top`:
   - assumes immediate taker fill at current best ask if the side has enough
     top-level depth.
2. `paper_taker_stressed_1c`:
   - same as above, but entry price is best ask plus `1c`.
3. `paper_taker_stressed_2c`:
   - same as above, but entry price is best ask plus `2c`.

The paper bot's main visible P&L should default to the `1c` stressed track.
Keep the `0c` and `2c` tracks in report output.

When proper fill calibration is added, replace or augment these with:

- latency-adjusted available ask after `200ms`
- actual observed consumption of the level in the recorder
- live paper/no-fill comparison by price bucket

## Bot 1: Probability Gap Paper

### Plain-English Rule

Estimate the probability that UP wins from current CEX price, start price,
remaining time, and recent volatility. Buy the side where our probability is
meaningfully higher than Polymarket's price.

### Model

For each market and decision time:

- `S0` = CEX price at market start
- `S` = latest CEX price at decision time
- `seconds_left` = market close minus decision time
- `sigma_remaining` = sampled realised volatility scaled to remaining time
- `p_up` = probability final price is greater than or equal to start price

Use the same formula as `scripts/crypto_strategy_validation.py`:

```text
p_up = normal_cdf(log(S / S0) / sigma_remaining)
```

Clamp probability to `[0.001, 0.999]`.

### Entry Rule

Buy UP if:

```text
p_up - up_ask >= 0.07
```

Buy DOWN if:

```text
(1 - p_up) - down_ask >= 0.07
```

Additional filters:

- selected side ask must be between `0.03` and `0.85`
- skip if PM spread is above `4c`
- skip if selected side top depth is below `$30`
- skip if data freshness filters fail

### Suggested Env Fields

```text
CRYPTO_PROB_GAP_BOT_ID=crypto_probability_gap_paper
CRYPTO_PROB_GAP_ENABLED=true
CRYPTO_PROB_GAP_DRY_RUN=true
CRYPTO_PROB_GAP_SYMBOLS=BTC,ETH,SOL
CRYPTO_PROB_GAP_DURATIONS=5,15
CRYPTO_PROB_GAP_MIN_SECONDS_TO_CLOSE=30
CRYPTO_PROB_GAP_MAX_SECONDS_TO_CLOSE_5M=300
CRYPTO_PROB_GAP_MAX_SECONDS_TO_CLOSE_15M=600
CRYPTO_PROB_GAP_MIN_EDGE=0.07
CRYPTO_PROB_GAP_MIN_PRICE=0.03
CRYPTO_PROB_GAP_MAX_PRICE=0.85
CRYPTO_PROB_GAP_MAX_SPREAD=0.04
CRYPTO_PROB_GAP_MIN_TOP_DEPTH_USD=30
CRYPTO_PROB_GAP_STAKE_USD=5
```

## Bot 2: Brownian Fair-Value Paper

### Plain-English Rule

Compute a stricter theoretical fair value for UP using the same price, time,
and volatility inputs. Trade only when the theoretical fair value and
Polymarket price disagree cleanly.

### Model

Use the same `p_up` calculation as the probability-gap bot, but require both:

1. the model-to-market gap is large; and
2. the selected ask is still cheap after crossing the spread.

### Entry Rule

Compute:

```text
pm_mid_up = average(up_ask, 1 - down_ask)
```

Buy UP if:

```text
abs(p_up - pm_mid_up) >= 0.04
and p_up - up_ask >= 0.03
```

Buy DOWN if:

```text
abs(p_up - pm_mid_up) >= 0.04
and (1 - p_up) - down_ask >= 0.03
```

Additional filters:

- avoid the first `30s` after market open
- avoid the final `30s` before close
- selected side ask must be between `0.03` and `0.85`
- skip if recent 60s CEX move is greater than `0.25%` in either direction;
  this keeps the bot closer to fair-value mispricing rather than momentum
- skip if PM spread is above `4c`
- skip if selected side top depth is below `$30`

### Suggested Env Fields

```text
CRYPTO_BROWNIAN_FV_BOT_ID=crypto_brownian_fv_paper
CRYPTO_BROWNIAN_FV_ENABLED=true
CRYPTO_BROWNIAN_FV_DRY_RUN=true
CRYPTO_BROWNIAN_FV_SYMBOLS=BTC,ETH,SOL
CRYPTO_BROWNIAN_FV_DURATIONS=5,15
CRYPTO_BROWNIAN_FV_MIN_SECONDS_TO_CLOSE=30
CRYPTO_BROWNIAN_FV_MAX_SECONDS_TO_CLOSE_5M=300
CRYPTO_BROWNIAN_FV_MAX_SECONDS_TO_CLOSE_15M=600
CRYPTO_BROWNIAN_FV_MIN_MODEL_MID_GAP=0.04
CRYPTO_BROWNIAN_FV_MIN_ENTRY_EDGE=0.03
CRYPTO_BROWNIAN_FV_MIN_PRICE=0.03
CRYPTO_BROWNIAN_FV_MAX_PRICE=0.85
CRYPTO_BROWNIAN_FV_MAX_SPREAD=0.04
CRYPTO_BROWNIAN_FV_MIN_TOP_DEPTH_USD=30
CRYPTO_BROWNIAN_FV_STAKE_USD=5
```

## Reporting Requirements

Add a daily report script, for example:

```text
scripts/crypto_fair_value_paper_report.py
```

The report must group results by:

- bot id
- strategy
- symbol
- duration: 5m vs 15m
- lead bucket: `<45s`, `45s-120s`, `120s-300s`, `300s+`
- side: UP vs DOWN
- model probability bucket
- entry ask bucket
- fill track: top, `1c` stressed, `2c` stressed

Metrics required:

- signals
- simulated fills
- no-fills
- fill rate
- closed positions
- wins
- hit rate
- gross P&L
- fee-stressed P&L
- raw ROI
- median ROI
- ex-largest-win ROI
- ex-largest-two ROI
- average model edge at entry
- average spread
- average top depth

Scan-level counts:

- missing-book count
- stale-data skip count

The dashboard and Telegram can be added later. First implementation can write
Markdown and JSON under:

```text
data/reports/crypto_fair_value_paper/latest.md
data/reports/crypto_fair_value_paper/latest.json
```

## Forward Paper Gates

Run both bots for at least `3` full days before reading anything. Prefer
`7` days before making a paper-lane verdict.

Minimum gates before keeping a bot:

| Gate | Threshold |
|---|---:|
| Signals | `>= 500` |
| Simulated filled entries under `1c` stress | `>= 150` |
| Closed positions | `>= 150` |
| Hit rate | `>= 55%` |
| Avg ROI under `1c` stress | `> 3%` |
| Ex-largest-two ROI under `1c` stress | `> 2%` |
| Avg ROI under `2c` stress | `> 0%` |
| Missing PM price at decision | `< 40%` of decisions |
| Data freshness violations | Reported, not hidden |

If a bot fails ex-largest-two ROI, do not promote it. A jackpot-shaped result
is not enough.

## Required Next Validation Before Live

Before any live discussion, complete all of these:

1. Actual settlement labels:
   - join paper positions to final Polymarket outcome where available; or
   - add Chainlink/Data Streams labels if historical access is available.
2. Fill calibration:
   - compare paper simulated fill/no-fill against actual exchange/live-mirror
     behavior where there is overlap.
3. Latency stress:
   - evaluate whether the selected ask still exists after `200ms`, `500ms`,
     and `1000ms`.
4. Capacity check:
   - estimate whether `$25` and `$50` entries would have been fillable under
     the same rules.
5. Separate ADR:
   - any live movement requires a new ADR and explicit the operator approval.

## Suggested Implementation Shape

Prefer a new small package rather than extending Bot G directly:

```text
bots/crypto_fair_value/
  __init__.py
  config.py
  model.py
  discovery.py
  paper_executor.py
  __main__.py
scripts/crypto_fair_value_paper_report.py
tests/crypto_fair_value/
```

Reusable pieces:

- `core/fees.py` for fee math
- `bots/bot_e_recorder` schema knowledge for recorder rows
- `scripts/crypto_strategy_validation.py` for model and bucket reference
- existing `core.db` order/trade/position/event models
- existing paper settlement patterns from Bot G where safe

Do not modify the external scorer (https://oraclemangle.com). Do not add a new live CLOB order path.

## Implementation Checklist

1. Add model helpers:
   - `normal_cdf`
   - `remaining_sigma`
   - `probability_up`
   - `probability_gap_signal`
   - `brownian_fair_value_signal`
2. Add config with paper-only guard:
   - hard fail if `POLYMARKET_ENV=live` and dry-run is false
   - hard fail if any live keystore setting is requested
3. Add discovery loop:
   - BTC/ETH/SOL 5m/15m only
   - collect start/end/token ids
4. Add CEX state:
   - latest price
   - start price lookup
   - sampled realized volatility
5. Add PM state:
   - ask/bid/spread/depth for both sides
   - timestamp freshness
6. Add paper executor:
   - record decision event for every signal
   - record paper order/fill/position for fillable signals
   - store model probability and edge in payload
7. Add report:
   - daily Markdown/JSON
   - include `1c` and `2c` stress tracks
8. Add tests:
   - no live order path
   - probability math
   - signal thresholds
   - stale data skip
   - spread/depth skip
   - no duplicate per condition
   - reporting ex-largest-one/two ROI
9. Add systemd units only after local tests pass:
   - `polymarket-crypto-prob-gap-paper.service`
   - `polymarket-crypto-brownian-fv-paper.service`

## Stop Conditions

Stop and ask the operator before:

- enabling any live mode
- using any private key or wallet path
- changing Bot G Prime Live
- changing Bot D live
- expanding symbols beyond BTC/ETH/SOL
- interpreting CEX-proxy outcome proof as final settlement proof
- deploying a service that writes unusually high DB volume

## Recommended Next Session Prompt

```text
Implement docs/crypto-fair-value-paper-bots-spin-off-2026-05-06.md.
Build the two paper-only crypto fair-value bots and the daily report.
Do not change any live services, wallets, caps, or Bot G Prime Live.
Use scripts/crypto_strategy_validation.py as the reference for signal math.
Run focused tests and leave the bots paper-only.
```
