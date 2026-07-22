# Test Protocol

**Status:** Specified
**Last updated:** 2026-04-14
**Role:** How we judge each bot. Concrete thresholds. No vibes.

This spec is self-contained.

---

## Phases

```
Paper (30 days) → Live graduation gate → Live £250 → +30 days → £500 → +30 days → £1,000 → +4 weeks → Decision point
```

16 calendar weeks end-to-end from paper start to kill-or-scale decision.

---

## Paper phase (30 days per bot)

### Why 30 days
- Bot A's typical hold is ~90 days; 30 days is a small sample of actual resolutions. We're testing **machinery + theoretical edge**, not realised PnL.
- Bot B's typical hold is ~45 days; 30 days yields 15–50 theoretical resolutions — useful.

### Minimum entry counts
- **Bot A:** ≥60 paper entries placed over 30 days
- **Bot B:** ≥20 paper entries placed over 30 days

If either fails to hit entry minimums:
- **First occurrence:** relax the filter by one notch (e.g., raise `volume_24h` floor, broaden `|edge|` threshold). Restart the 30-day clock.
- **Second occurrence:** thesis doesn't have enough candidate universe. Kill the bot and reconsider at the architecture level.

### Minimum resolution counts
- **Bot A:** ≥5 simulated resolutions (low because hold is long)
- **Bot B:** ≥10 simulated resolutions

### Metrics tracked daily

**Primary**
- `calmar_simulated = annualised_return / max_drawdown` (using mark-to-market + resolved P&L)

**Secondary**
- Entries per day
- Fill rate (paper: 100% at touch; live: real)
- `edge_captured = realised_edge / theoretical_edge_at_entry`
- `slippage_simulated` (mid vs touch at entry)
- Oracle-dispute hit count
- Mean + max hold time

**Failure tripwires (fire during paper, cause re-evaluation)**
- Any simulated single-position loss >10%
- Max simulated drawdown >12%
- Any unexplained log event (tool developer cannot account for an entry / cancel / halt)

---

## Live graduation gate

A bot graduates to £250 live capital only when ALL the following pass:

- [ ] 30 paper days completed
- [ ] Entry-count minimum met (Bot A ≥60, Bot B ≥20)
- [ ] Simulated Calmar ≥ 0.8 — **note**: relaxed from the ideal 1.2+ because paper Calmar can't capture real slippage; the relaxation is a trust discount on simulated fills
- [ ] No unexplained log events in the last 14 days
- [ ] Manual code review by the operator of: `filters.py`, `sizer.py`, `executor.py`, `lifecycle.py`
- [ ] One live dry-run: `scripts/dry_run_order.py` places a $5 order at deliberately unfillable price and cancels it. Verifies auth + signing + cancel + WSS fill receipt path end-to-end.

All boxes ticked → graduate.
Any box fails → return to paper, document the fail reason, fix, restart the 30-day clock.

---

## Live scale-up ladder

| Tier | Capital | Promotion criteria |
|---|---|---|
| Graduated | £250 | All graduation-gate boxes ticked |
| Tier 2 | £500 | +30 live days; realised PnL ≥ 0; max drawdown < 10% |
| Tier 3 | £1,000 | +60 live days (cumulative); realised PnL > 0; max drawdown < 12% |
| Scaling ceiling | £1,000 | No further scale without a full re-decision session |

Scaling happens only during rotation-home weeks. Never at sea.

---

## Kill rules

A bot is killed **immediately** if ANY:

1. Live drawdown hits 15% of that bot's bankroll
2. 4 consecutive weeks of negative realised PnL
3. Bot-specific death pattern fires:
   - **Bot A:** hit rate <80% for 2 consecutive weeks OR avg edge per trade <2%
   - **Bot B:** calibration halt fires (10 resolutions with mean `|p_model − realised| > 0.15`) OR model-echo test fails
4. Any single unexplained log event that reveals a bug capable of unbounded loss (regardless of PnL)
5. Aggregate cross-bot drawdown hits 20%

Kill = cancel all orders, close open positions at market, disable systemd unit, alert.

Revival from kill requires a full post-mortem + new ADR in `docs/decisions-log.md`.

---

## Double-down rules

A bot is considered for scaling beyond the £1,000 ceiling ONLY when ALL:

- [ ] 60 consecutive live days of positive realised PnL
- [ ] Realised Calmar > 1.5
- [ ] Drawdown never exceeded 10% in the live period
- [ ] At least one "bad month" survived with <5% drawdown (demonstrates real tail handling, not just a good streak)

A "bad month" = a month where the candidate universe shrinks >25% OR avg daily volatility (VIX-equivalent on the basket) rises >50% over baseline.

Double-down decisions are user-only. ADR required before any cap change.

---

## Stalemate

A bot is "stalemate" (keep running, don't scale) when:

- Realised PnL positive but below UK risk-free rate (gilt yield ~4.5% annualised as of 2026-04-14)
- Calmar in [0.5, 1.5]
- Drawdown <12%

Stalemate persists 4 weeks, then re-evaluate. Do not kill a stalemate bot unless it crosses into kill territory.

---

## Diagnostics

### Model-echo test (Bot B only — weekly)

**Hypothesis being tested:** Is Gemini's "edge" really just reading the crowd's current price back through RAG?

**Procedure:**
1. Pick 20 markets recently scored at `t0`
2. Re-score the same 20 markets at `t0 − 2h` using only data available at that earlier timestamp
3. Compute `edge_at_t0 - edge_at_t0_minus_2h` per market
4. Take mean absolute difference

**Pass:** mean absolute difference > 0.02 (model is doing something independent of short-term crowd price)
**Fail:** mean absolute difference < 0.01 (model is echoing the crowd)
**Review:** between 0.01 and 0.02 — investigate, don't auto-kill

### Calibration check (Bot B only — rolling)

Track mean of `|p_model − realised_outcome|` over last 10 resolved positions. If >0.15, calibration halt fires.

### Slippage audit (both bots — monthly)

Compare `price_at_entry` (the book mid at decision time) with `filled_price` (actual). Large systemic divergence suggests latency or queue-position issues.

---

## Decision timeline (concrete weeks)

Referenced from Week 1 of build (= first home rotation).

| Week | Event |
|---|---|
| 1 | Shared infra build |
| 2 | Bot A MVP → paper start |
| 3 | Bot B MVP → paper start |
| 4–7 | At-sea paper observation (auto-digest twice daily) |
| 8 | Rotation home: Bot A paper review → live graduation decision |
| 9 | Rotation home: Bot B paper review → live graduation decision |
| 10–11 | At-sea live (£250 per bot if graduated) |
| 12 | Rotation home: A/B checkpoint — kill / stalemate / scale |
| 13–15 | At-sea live (scaled survivors) |
| 16 | **Hard decision point**: kill, scale to £1,000, or terminate project |

If Week 16 arrives with neither bot net-profitable: terminate. Return to discovery or retire the project.

---

## Success criteria (project-level)

The project succeeds if, at Week 16:
- At least one bot has realised Calmar > 1.2
- Max observed drawdown < 15% per bot
- No silent bugs discovered during live
- Total realised PnL exceeds development cost (Gemini API, the VPN provider, Backblaze, RPC = ~£150 over 16 weeks)

The project fails if Week 16 shows neither bot clearing stalemate. This is acceptable — discovery and ruling-out is valuable; the alternative is scaling into a losing thesis.

---

## References

- `docs/architecture-decision.md` §5 — original protocol
- `docs/decisions-log.md` ADR-008 — thresholds rationale
- `specs/bot-a-spec.md` — Bot A specific failure modes
- `specs/bot-b-spec.md` — Bot B specific failure modes (model-echo, calibration halt)
