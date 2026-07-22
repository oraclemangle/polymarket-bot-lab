# State of the Fleet — 2026-05-07 EOD

**Generated end of a heavy day:** NegRisk closure (ADR-119), Bot D paper longshot-fade archive (ADR-120), Bot D-Spike build + audit (ADR-123/125), Strategy A intraday-exit rejected, cross-event NegRisk arb killed, Bot H bear case ran (WOUNDED).

**Operator emotional check:** "back to the drawing board, no edge anywhere." This document exists to push back honestly on that framing using only what's in the data.

---

## Lanes currently producing positive signal

| lane | status | sample | edge | comment |
|---|---|---|---|---|
| **Strategy E (bot_d_spike)** | paper-deployed today on VPS | 0 entries yet (TTR window structurally empty at deploy moment); 14,697 historical trades on WANGZJ show +30.6% net ROI, Wilson 95% CI excludes null | +30.6% historical | First live entries expected 00:00-06:00 UTC May 8 |
| **Bot D live_probe (range-fade NO)** | running live on the bot container at $3/entry | 12 closes, 91.7% hit rate, +28.4% net edge | +28.4% | Different from archived Bot D paper longshot-fade (ADR-120) |
| **Bot G live probe** | running live at $3/entry | 15 closes, 12 wins (80%), +$6.62 realized | +small | Operator's own analysis says "structurally weak" but it's still positive |

**3 lanes positive. Total live realized PnL: ~$18 cumulative.** Tiny but the right sign.

## Lanes definitively closed (today)

| lane | killshot |
|---|---|
| Bot D paper longshot-fade | 84-position +27% headline edge driven 100% by Lagos +$1,735 outlier; ex-top-1: -20.9% |
| Strategy A (cheap-YES intraday exit) | Bot D's own tape: 1/16 cheap-YES BUYs had any profitable bid window; bid liquidity doesn't exist |
| NegRisk basket arb (within-event) | 0 of 1,425 events have real arb after exhaustiveness gates; 252 have illiquid field markets |
| Cross-event NegRisk arb | semantic matching is the alpha and is already won at sub-second cadence by entrenched MMs |
| Settlement sweep | Opus killed it: fees ~11% of premium, single-wallet dominance 77% from one wallet, correlated tail |
| Paired-token within-market arb | 0/1.05M paired BBO snapshots show arb; spread structurally prevents it |
| Crypto 5m/15m corner | 10 strategy variants exhausted, no edge regardless of size |
| Bot A high-hit-rate fade | 12,521 trades, 93.7% hit rate, -$13,614 from asymmetric loss math |

**8 closures.** That's not "no edge" — that's normal strategy-research mortality (~95% kill rate at hedge funds).

## Lanes worth revalidating (per earlier in session)

| lane | trigger event | next test |
|---|---|---|
| **Maker-flow / builder-code rebate** | $5k cap raised; ADR-048 plumbing already in place | Operator must lift CLAUDE.md kill-list line |
| **Bot H Betfair sharp-line lag** | VPS Helsinki latency improvement | 14-day passive recorder before any code (per strategy-adversary today) |
| **Wallet-tag features (Variant B)** | WANGZJ + PolyVerify on disk | Mining running (the bot container PID 31878 as of 2026-05-07) |
| **Slow-burn news arb** | Helsinki latency + Grok-with-X | 2-3 sessions paper validation |
| **Longer-horizon crypto with maker rebates** | Mar 6 2026 rebate extension | 2-3 sessions, combine with maker-flow |

## What the data says about realistic ceiling at $5k retail

Per Strategy E historical edge (14,697 trades, +30.6% gross of slippage):
- Forward-validated half-edge realistic: ~+15% ROI on $200 deployed = $30/quarter
- Compounded to $50k cap with multiple lanes: **~$5–15k/year net realistic**
- This is BEFORE any forward strategy survives validation

Polymarket retail trading at $5k–50k scale is an "okay side income" venue, not a get-rich-quick venue. The discipline that's been built (kill-list, ADRs, calibration tests, strategy-adversary subagent) is itself the alpha. Most retail traders don't have it and lose.

## Not "no edge anywhere" — "edge in calibration, not execution"

Today's pattern across all 5 closures: every **execution-based** strategy died (intraday exits, basket arb, cross-venue arb, settlement sweep, paired arb). The **calibration-based** strategies survived (Strategy E TTR-windowed cheap-YES, Bot D NO-side range-fade).

**Retail at $5k cannot win execution races.** Solo operator vs PolyBetbot vs Wintermute infra is unwinnable on speed. Where retail CAN win is finding the slice of the market that's mis-calibrated and the entrenched MMs don't bother with (long tail, niche cities, narrow time windows).

## Recommended posture for the next 30 days

1. **Don't build another bot.** The "operator-state risk" the strategy-adversary flagged on Bot H today is real. Three major builds in one day is bad cadence.
2. **Let Strategy E run.** Target: 30-100 closed paper positions by mid-June. Calibration check at 200 closes or 90 days per ADR-123.
3. **Let Bot D live_probe + Bot G accumulate sample.** Both are positive but n<30; need more closes to confirm.
4. **Shore up infrastructure** that compounds across all future bots:
   - Wallet-tag features (mining running)
   - Builder-code rebate accounting (lift ADR-121 kill-list entry, then plumb)
   - PolyVerify integration as feature column
5. **Survey adjacent markets** (Betfair Bot H passive recorder, the meta-prompt for "what else can bots be used for")

## Anti-pattern: "I've found nothing, build something else"

This is what creates Bot A. The discipline is:
- Find historical signal ✓ (Strategy E did this)
- Wait for forward validation
- Don't pre-commit to "more bots" as a reaction to anxiety about empty quarters

The hedge fund version of this is: most quant teams have ONE strategy actually making money at any given time. They don't have ten. They have one calibration edge that they protect, scale carefully, and pivot away from when it decays.

---

## State checkpoint for tomorrow's session

When picking this up tomorrow:

1. Check wallet mining results (`/tmp/retail_wallets_pnl.csv` on the bot container if mining completed; otherwise re-run)
2. Check Bot D-Spike first-day entries (`journalctl -u polymarket-bot-d-spike.service --since '06:00 UTC May 8' --until '07:00 UTC May 8'`)
3. Run the adjacent-markets meta-prompt (drafted in chat earlier) → produces survey of bot-tradable venues beyond Polymarket
4. **Don't propose another Polymarket bot.** Strategy E + Bot D NO + Bot G are the live lanes; let them validate.

Reference docs to re-read:
- `docs/decisions-log.md` ADR-119, 120, 123, 125 (today's ADRs)
- `docs/reports/wangzj-cheap-yes-weather-calibration-2026-05-07.md` (the empirical evidence)
- `docs/reports/dormant-ideas-sweep-2026-05-07.md` (frontier ranking)
- `docs/reports/bot-d-spike-deployment-audit-2026-05-07.md` (today's audit)
