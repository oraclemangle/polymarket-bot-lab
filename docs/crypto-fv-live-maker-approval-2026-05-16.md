# Crypto FV Maker Tiny-Live Approval Packet

**Date:** 2026-05-16
**Scope:** `crypto_probability_gap_live_maker` and `crypto_brownian_fv_live_maker`
**Status:** prepared only; not deployed or activated

## Current Evidence

| Lane | Paper maker bot | Runtime observed | Closed markets | Realised P&L | ROI | Decision |
|---|---:|---:|---:|---:|---:|---|
| Probability-gap maker | `crypto_probability_gap_paper_maker` | ~20h | ~216 | +$155.41 | +14.4% | Prepare tiny-live probe |
| Brownian FV maker | `crypto_brownian_fv_paper_maker` | ~20h | ~264 | +$173.15 | +13.1% | Prepare tiny-live probe |

These figures came from the 2026-05-16 the bot container morning snapshot. They justify a
capped live probe, not a full-size live promotion.

## Prepared Live Controls

| Control | Probability-gap | Brownian FV |
|---|---:|---:|
| Max order notional | `$5` | `$5` |
| Daily gross cap | `$250` | `$300` |
| Open exposure cap | `$100` | `$120` |
| Max concurrent positions | `20` | `24` |
| Stale quote cancel age | `90s` | `90s` |
| Minimum maker edge after quote discount | `2.5c` | `2.5c` |
| Order posting | Exchange-enforced `post_only=True` | Exchange-enforced `post_only=True` |
| Existing paper runner | Remains paper-only | Remains paper-only |

The live path is separate: `python -m bots.crypto_fair_value.live_maker`.

The caps are based on the observed the bot container paper-maker distribution at
2026-05-16 11:26 UTC:

| Lane | Paper fills | Paper gross | Peak hourly fills | Peak open exposure | Prepared cap logic |
|---|---:|---:|---:|---:|---|
| Probability-gap | `260` | `$1,300` | `18` fills / `$90` | `20` fills / `$100` | Daily cap about `2.8x` peak hour; open cap equals observed peak |
| Brownian FV | `320` | `$1,600` | `23` fills / `$115` | `24` fills / `$120` | Daily cap about `2.6x` peak hour; open cap equals observed peak |

## Files Added

| File | Purpose |
|---|---|
| `bots/crypto_fair_value/live_maker.py` | Approval-gated live maker executor |
| `systemd/polymarket-crypto-prob-gap-live-maker.service` | Blocked-by-default probability-gap live unit |
| `systemd/polymarket-crypto-brownian-fv-live-maker.service` | Blocked-by-default Brownian live unit |
| `tests/crypto_fair_value/test_live_maker.py` | Unit tests for approval gates and order accounting |

## Approval Gates

The services are intentionally blocked unless all of these are true:

```text
POLYMARKET_ENV=live
CRYPTO_PROB_GAP_LIVE_ENV=live
CRYPTO_PROB_GAP_LIVE_AUTHORIZED=true
CRYPTO_PROB_GAP_LIVE_APPROVED_AT=2026-05-16

POLYMARKET_ENV=live
CRYPTO_BROWNIAN_FV_LIVE_ENV=live
CRYPTO_BROWNIAN_FV_LIVE_AUTHORIZED=true
CRYPTO_BROWNIAN_FV_LIVE_APPROVED_AT=2026-05-16
```

If any flag is missing, the process exits before loading live wallet/client
paths.

## Exact Operator Approval Wording

Use this only if approving activation:

```text
I approve activating the crypto FV probability-gap and Brownian maker tiny-live
probes on the bot container with $5 max order. Probability-gap caps are $250 daily gross,
$100 open exposure, and 20 max concurrent positions. Brownian caps are $300
daily gross, $120 open exposure, and 24 max concurrent positions. Both lanes
use 90-second stale quote cancellation and exchange-enforced post-only orders.
Do not change any other live bot caps.
```

## Activation Steps After Approval

1. Deploy the new code and unit files to the bot container.
2. Add the lane-specific live env overrides with the approved cap values.
3. Reload systemd.
4. Start one lane first, preferably `crypto_probability_gap_live_maker`.
5. Verify the first scan emits either `blocked_*`, `quote_skip_*`, or at most
   one known `crypto_fv_live_maker.quote_placed` event.
6. Confirm the order appears in `orders` under the live bot id.
7. Only then start the second lane.

## Kill Switch

Stop one lane:

```text
sudo systemctl stop polymarket-crypto-prob-gap-live-maker.service
sudo systemctl stop polymarket-crypto-brownian-fv-live-maker.service
```

Emergency cleanup must use the existing approved live-order cancellation path,
then verify no `OPEN`, `PARTIAL`, `MATCHED`, or `live` orders remain for:

```text
crypto_probability_gap_live_maker
crypto_brownian_fv_live_maker
```

## Still Not Proven

- Live maker fill quality against real queue position.
- Whether the 20h paper window survives a full 24-72h regime shift.
- Whether positive P&L concentrates in one symbol, duration, or lead bucket.
- Whether live fills match paper fills closely enough after queue delay.

The first live phase is therefore a plumbing and slippage probe, not a scale-up.
