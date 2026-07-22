# Risk And Sizing

## Current Live Probe Envelope

The current live probe is intentionally small. The point is to collect real
fill, slippage, resolution, and settlement evidence before scaling.

| Control | Value |
|---|---:|
| Wallet allocation posture | `$200` |
| Max single order | `$10` |
| Max daily gross notional | `$100` |
| Max open exposure | `$150` |
| Max concurrent positions | `20` |
| Minimum fallback size | `5` shares |
| Max dynamic size | `40` shares |

## Evidence-Gated Share Ladder

The sizing is not simply "cheaper means bigger". Cheap positions are only
scaled if the quality slice is strong.

| Entry price | Shares | Gate |
|---|---:|---|
| `<10c` | `30` | Tier B, NOAA NBM or multi-model, not Seattle/Denver |
| `10-20c` | `20` | Same gate |
| `20-50c` | `5` | Do not scale yet |
| `>=50c` | `10` | Same gate |
| Any weak slice | `5` | fallback |

Weak slices currently include:

- Tier C;
- Seattle;
- Denver;
- GribStream-primary entries;
- the `20-50c` band until more evidence exists.

## Sizing Pseudocode

```text
if live_sizing_mode != "evidence_gated":
    shares = fixed_shares
else:
    scaled = (
        setup_tier == "B"
        and forecast_source in {"noaa_nbm", "multi_model"}
        and city not in {"Seattle", "Denver"}
    )

    if not scaled:
        shares = 5
    elif entry_price < 0.10:
        shares = 30
    elif entry_price < 0.20:
        shares = 20
    elif entry_price < 0.50:
        shares = 5
    else:
        shares = 10

    shares = max(shares, exchange_minimum_shares)
    shares = min(shares, max_dynamic_shares)

notional = shares * entry_price
block if notional > max_order_usd
block if daily_gross + notional > daily_gross_cap
block if open_exposure + notional > open_exposure_cap
```

## Why This Shape

The evidence showed the fixed 5-share approach was profitable but under-sized
on some winning low-price and high-price entries. The same evidence also showed
that scaling every cheap entry would amplify weak cities and weak tiers. The
ladder therefore scales the proven slices while keeping the total daily risk
envelope unchanged.

