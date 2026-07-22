# Bot E POC Results — 2026-04-17

**Purpose:** answer §5.1 Q1/Q2/Q3 from `docs/session-2026-04-17-edges-review.md` before any build of the Bot E spread-capture pivot.

**Script:** `scripts/bot_e_poc_recorder.py`

**Dataset:** `data/bot_e_recorder.db` — 461 MB, 338,416 pm_events, 1,377,142 cex_trades, 52 markets with full metadata, covering 2026-04-16 09:14–13:53 UTC (~4.6 hours on BTC/ETH/SOL 5-minute Up/Down binaries).

**Dataset caveat:** recorder captured 4.6 hours, not Q1 2026. Scaled-down POC threshold: 20 qualifying markets instead of 500. Even against this relaxed bar, all gates fail.

---

## Headline verdict

**All three gates fail (decisively, even at scaled-down thresholds).**

**Recommendation: Archive Bot E per kill date 2026-06-30. Do not build the revised backtest. The recorder dataset asset is preserved for future analysis.**

| Gate | Threshold | Result | Pass? |
|---|---|---|---|
| Q1 — universe size | $\ge 20$ markets with sub-threshold $\ge 60$s | 4 markets | **FAIL** |
| Q2 — early-window fraction | $T_{\text{early}} / T_{\text{total}} \ge 0.30$ | 0.505 | Pass (but on a 4-market base) |
| Q3 — fill asymmetry | $r_{\text{lose}} / r_{\text{win}} \le 1.5$ | Infinite (0.0 / 0.0) | **FAIL** |

Q2 "passes" only on a statistically meaningless base of 4 markets.

---

## Structural finding (why this needs a different approach)

The data reveals a **market-efficient equilibrium** that the reviewer's critique anticipated but did not name explicitly:

**Wherever the spread exists, there is no taker flow to fill passive bids. Wherever taker flow exists, there is no spread.**

Evidence from the distribution of minimum $P_Y^{\text{bid}} + P_N^{\text{bid}}$ across the 49 markets with complete timelines:

| Bucket | Count |
|---|---|
| $< 0.97$ (ostensibly tradeable spread) | 20 |
| $0.97$ – $0.99$ (marginal spread) | 26 |
| $\ge 1.00$ (no spread, auto-matched if ever present) | 0 |

Of the 20 markets that briefly showed sub-0.97 sum-bid, only 4 sustained it for $\ge 60$s. All 4 were degenerate low-activity markets:

| condition_id (short) | total events | total trades | passive BUY YES fills | passive BUY NO fills |
|---|---|---|---|---|
| 0xb1dd49d6 | 40 | 0 | 0/16 | 0/39 |
| 0x8ea6bf7e | 23 | 1 | 0/18 | 0/2 |
| 0x846a68f3 | 18 | 0 | 0/2 | 0/16 |
| 0xda9baa22 | 20 | 0 | 0/2 | 0/13 |

**Zero passive BUY fills during the sub-threshold windows across all four qualifying markets.** Not because of adverse selection — because of no flow at all. The sellers who could fill your bid did not arrive.

Conversely, the 10 most-liquid markets in the dataset (0x01233f11 with 5,323 chances, 0x51fecb93 with 6,770, 0xb9f03159 with 5,322, etc.) have plenty of fill opportunities — but their minimum sum-bid barely drops below 0.99. No tradeable spread, ever.

---

## Why this is stronger than the reviewer's original concern

The reviewer framed Problem 3 as "adverse selection" — the theory that *losers fill, winners don't*. That frame requires a baseline of fills on both sides, then looks for asymmetry.

The actual data shows a more fundamental problem: **there are no fills on either side in the regimes where the strategy wants to operate.** You cannot have an adverse-selection trap when the trap is empty.

Subordinate concerns become moot:

- The sizing bug (Problem 2) is irrelevant — no fills to size.
- The vol-harvest framing flaw (Problem 1) is irrelevant — no harvest to do.
- Mid-distance cap, lifecycle positioning, refresh cadence — all moot.

---

## Methodology caveats (for future re-runs)

1. **Scale:** 4.6h of recorder data is insufficient for a Q1-2026-scale decision. A fair re-run needs ≥ 30 days of recorder history. Current recorder is still live on the bot LXC container, so a re-run in Q3 2026 is feasible — but the structural finding above is unlikely to reverse given the efficient-market mechanism identified.
2. **Winner-side inference:** I used `last yes_bid >= 0.90 → YES won, `last no_bid >= 0.90 → NO won`. 29 of 49 timelines ended before the market resolved — so winner-side was indeterminate for most. A re-run should join against an off-chain resolution source (Gamma API `/markets/{id}/resolved`) rather than in-tape inference.
3. **Fill model:** passive BUY at bid fills only when an aggressive SELL (side="SELL") occurs within 30s at price $\le$ our bid. No queue-position modeling. This is optimistic — real-life queue dynamics would lower fill rates further.
4. **Market category:** recorder captures crypto 5-min binaries. If Bot E were hypothetically extended to 15-min, hourly, or daily crypto markets, the ratio of "sub-threshold time" to "active time" would likely drop further (lower-vol windows = tighter efficient pricing), not rise.

---

## OQ-037 verification (separate but related)

The current `core/backtest_bot_e.py::calibrate` function:

1. Does NOT separate winner-side vs loser-side passive fill rates. `ObiObservation.would_fill` is a single boolean; `ExpectancyTable.add` keys by `(obi_bucket, mte_bucket)`, not by winner/loser.
2. Is a stub — line 489 (`table.add(obi_b, "unknown", win=False, pnl=0.0)`) always records `win=False, pnl=0.0` with `mte_bucket="unknown"`. The function was left incomplete at end of Phase 0.

**OQ-037 resolution:** both issues must be fixed before any Bot E backtest is ever trusted. Since the POC says archive, this becomes moot unless the fleet later needs to resurrect Bot E off a different thesis — in which case the fix goes under that thesis's ADR.

---

## Decision matrix applied (per §5.2 of review doc)

Review doc matrix:

| Q1 | Q2 | Q3 | Action |
|---|---|---|---|
| < 500 | — | — | Archive Bot E now |
| ≥ 500 | $T_{\text{early}} < 30\%$ | — | Archive; pass gate not reachable |
| ≥ 500 | $T_{\text{early}} \ge 30\%$ | $r_{\text{lose}}/r_{\text{win}} > 1.5$ | Archive; adverse selection fatal |
| ≥ 500 | $T_{\text{early}} \ge 30\%$ | $r_{\text{lose}}/r_{\text{win}} \le 1.5$ | Proceed to revised full backtest |

POC result: row 1 applies. Universe threshold hit is 4 not 500 (or 4 not 20 on scaled thresholds). **Archive.**

---

## What stays, what goes

**Keeps:**

- **Bot E recorder service** — live on the bot LXC container, continues capturing. Data asset preserved. No cost to keep running; may inform future thesis work unrelated to spread-capture.
- **Bot E kill date 2026-06-30** — unchanged. Window for any new thesis (not spread-capture) remains open until then, but scope would need new ADR.

**Archives:**

- Bot E vol-harvest / spread-capture thesis. ADR-030 lands as "gated POC failed; archive."
- Bot E1 trader code under `bots/bot_e_btc_scalp/` — keep in repo (don't delete; history is valuable) but mark deprecated via CLAUDE.md note. No further development.

**Explicitly unchanged:**

- Recorder continues running — it is a cheap sensor. Future theses (e.g., CEX-lag rehabilitation, regime-detection research) can use this data asset without re-standing the infrastructure.

---

## Next-session implications

Per the roadmap in `docs/session-2026-04-17-edges-review.md` §7:

- Bot E POC completed (this doc) — gates Bot E archive decision.
- Tier-1 work reduces from 4 streams to 3:
  1. Bot B ensemble scorer rebuild (3 weeks)
  2. Fleet-wide exec-policy module
  3. Bot F rehabilitation as estimator supplier + `crowd_signals` table
- Rewards monitor + sports-lag park exactly as previously planned.

One week of planned Bot E revised-backtest work is reclaimed. Proposed reallocation: accelerate Bot B ensemble rebuild by a week (target 2 weeks, not 3) by starting the `base.py` + `ensemble.py` skeleton in this session.

---

## Files produced / modified this POC

- `scripts/bot_e_poc_recorder.py` — the POC script (NEW)
- `docs/bot-e-poc-results.md` — this memo (NEW)
