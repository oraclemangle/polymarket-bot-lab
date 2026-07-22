# Strategy E2 — Short-TTR Weather Variant Spec

**Created:** 2026-05-08
**Status:** spec only; deployment requires operator OK + ADR to lift CLAUDE.md "near-resolution scalping" entry for weather specifically.

---

## What this is

Extension of Strategy E (Bot D-Spike) to the **<6h time-to-resolution window**, in addition to the existing 6-12h window.

## Why it's separate

- Strategy E is paper-deployed at 6-12h TTR per ADR-123/-125
- WANGZJ re-validation (Test C, 2026-05-08) found `<6h × weather` ALSO survives outlier-robustness check:
  - n=40,496 trades, +36% as-is ROI, **+11% after top-5 outlier removal**
  - Same shape as 6-12h × weather (Strategy E baseline: +40% as-is, +16% top-5 removed)
- This is the only OTHER cheap-YES slice that survives the same robustness test in any category

## Why it's NOT just a config tweak

- CLAUDE.md `Out-of-scope` list contains: `Near-resolution scalping / HFT strategies`
- `<6h` is by any definition near-resolution
- Bot G already operates in <30min crypto markets — but that's grandfathered, not a precedent
- **Lifting near-resolution scalping for weather specifically requires a new ADR**

## Empirical evidence (from Test C, 2026-05-08)

| TTR | category | n | as-is ROI | top-5 robust | top-25 robust | verdict |
|---|---|---:|---:|---:|---:|---|
| 6-12h | weather | 35,931 | +40.1% | +16.2% | -30.4% | ROBUST (Strategy E baseline) |
| **<6h** | **weather** | **40,496** | **+36.1%** | **+11.1%** | **-29.7%** | **ROBUST** |
| 12-24h | weather | 54,731 | +5.8% | -14.4% | -46.0% | fragile |

Both robust slices have ≥35K trades and survive top-5 outlier removal. Top-25 removal is negative for both — same outlier-tail dependence as Bot D paper longshot-fade, but the body of the distribution is positive.

## Spec — minimum diff from Strategy E

If approved, smallest possible deviation from existing `bot_d_spike`:

**Option A: Single bot with widened TTR window**
- Change `cfg.TTR_MIN_HOURS = 0` (was 6)
- Keep `cfg.TTR_MAX_HOURS = 12`
- Keep all other gates identical (3-10c price, city whitelist, hold to resolution)
- Pros: minimal code, minimal new state to monitor
- Cons: combines two slices into one PnL; harder to attribute later

**Option B: Separate paper bot lane**
- New module `bots/bot_d_spike_short/` (mostly symlinks/inheritance from `bot_d_spike`)
- New `bot_id = bot_d_spike_short`
- TTR window: `[0, 6)` hours
- Same city whitelist, price band, hold-to-resolution
- New systemd unit `polymarket-bot-d-spike-short.service`
- Pros: clean attribution; can kill independently
- Cons: more config and surface

**Recommended:** Option B. Cleaner, lets us measure both slices in isolation and kill one without touching the other.

## Sizing & limits

Same as Strategy E (per ADR-123):
- $1-3 per position (paper-only initially)
- 50 concurrent positions cap
- $200 total deployed cap
- 20 daily entries cap
- Hold to resolution

Note: <6h TTR means positions resolve fast → daily entry cap may need to bump to 30-40 for <6h variant since each position closes within hours and slot turns over faster.

## Kill conditions

Same as Strategy E:
- 200 closed positions OR 90 days, whichever first
- Archive if realized ROI < +5%
- Archive if hit rate < 4%

Robustness check at kill point: top-5 ROI must remain positive (matches the threshold that triggered the build).

## What this would unlock

**If <6h × weather forward-validates:**
- Doubles the addressable cheap-YES weather opportunity (40K + 35K = 75K trades/year of historical sample equivalent)
- Twice the daily entry rate → faster forward-validation than Strategy E alone
- If both slices forward-validate, the combined Strategy E2 lane could legitimately scale to $5-15K/year at $5k cap

**If <6h × weather forward-FAILS but 6-12h × weather succeeds:**
- Confirms Strategy E's TTR boundary is meaningful (the operator's empirical edge is specifically "last few hours" not generally "near-resolution")
- Useful diagnostic; refines theory

## Required ADR amendment

**Proposed ADR-133 (or next available number):**

> Lift CLAUDE.md "Near-resolution scalping / HFT strategies" entry **for weather temperature-bucket markets only**, paper-only, conditional on:
>
> 1. Strategy E (existing 6-12h variant) shows positive forward-edge on first 30+ closes
> 2. Build follows Option B above (separate `bot_d_spike_short` lane)
> 3. No live promotion without separate ADR after 200-close validation
>
> The general "near-resolution scalping" prohibition stays for crypto, sports, politics, and all other categories. Bot G's existing 5/15-min crypto operation is unchanged.

## Estimated effort

- Spec + ADR drafting: done (this doc)
- Module clone + config diff: 1 hour
- Tests: 30 min
- Systemd unit: 15 min
- Deploy + verify: 30 min
- **Total: ~3 hours when approved**

## Decision required

Operator must:
1. Read the empirical evidence (Test C results, this spec)
2. Decide: lift "near-resolution scalping" kill-list entry for weather specifically?
3. If yes, approve ADR-133 (or next available) and authorize build

If no, this spec stays as a reference but no code is written.

## Files referenced

- `docs/reports/findings-revalidation-all-tests-2026-05-08.md` — empirical evidence
- `docs/decisions-log.md` ADR-123, ADR-125 — Strategy E foundations
- `bots/bot_d_spike/` — module to clone for short-TTR variant
- `CLAUDE.md` "Out-of-scope" section — what's being amended
