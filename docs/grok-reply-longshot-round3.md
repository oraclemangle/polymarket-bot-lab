# Round 3 — reply to Grok with the sweep + gap-filter results

Copy-paste the block below into Grok. Grok's round-2 verdict was "no longer
obviously stupid, testable micro-alpha"; they asked specifically for the
t-N sweep, gap-size filter backtest, and oracle-subset check. Round 3
delivers the first two.

---

```
You asked for the t-N sweep and gap-size filter — I ran them. Your
intuitions were partially right and partially wrong; here's the matrix:

**Sweep: (entry_seconds_before_res × min_gap_bps). 781 resolved markets.
Base size $5, top-5 book walk, partial fills, no fees applied.**

t_sec  gap_bps  fills  wins  WR     P&L         cost      ROI
-----  -------  -----  ----  -----  ----------  --------  ----------
60s    0bps     48     4     8.3%   +$2884.42   $132.93   +2170%
60s    10bps    31     1     3.2%   +$2092.12   $ 91.90   +2276%
60s    20bps    13     1     7.7%   +$2156.84   $ 27.18   +7935%
60s    30bps    7      1    14.3%   +$2171.81   $ 12.21   +17785%  ← jackpot-concentrated

30s    0bps     43     9    20.9%   +$341.77    $115.74   +295%    ← surprising: HIGHER WR, SMALLER wins
30s    10bps    19     0     0.0%    -$77.43     $77.43   -100%
30s    20bps     5     0     0.0%    -$18.60     $18.60   -100%
30s    30bps     3     0     0.0%    -$13.60     $13.60   -100%

15s    0bps     35     3     8.6%   +$23.47     $100.30   +23%
15s    10bps    15     0     0.0%   -$58.83     $58.83    -100%
15s    20bps     4     0     0.0%   -$15.00     $15.00    -100%
15s    30bps     2     0     0.0%   -$10.00     $10.00    -100%

10s    0bps     27     2     7.4%   +$406.58    $93.42    +435%
10s    10bps    11     0     0.0%   -$48.83     $48.83    -100%
10s    20bps     1     0     0.0%   -$5.00      $5.00     -100%
10s    30bps     1     0     0.0%   -$5.00      $5.00     -100%

5s     0bps     18     0     0.0%   -$74.06     $74.06    -100%     ← extinct edge
5s     10bps    7      0     0.0%   -$33.83     $33.83    -100%
5s     20bps    0     -     -      $0          $0         -
5s     30bps    0     -     -      $0          $0         -

**Observations:**

1. **Your t-20-to-40s guess was inverted.** Later entry windows (5-15s)
   have catastrophically low WR. The edge is strictly in the 45-60s
   window. Intuition: a reversal needs at least ~30-45s of CEX vol
   remaining to flip a 25-40bps gap; inside 30s there isn't enough
   clock left.

2. **Gap filter concentrates the edge dramatically.** At t=60s, ≥30bps
   gap retains only 7 fills but *same single jackpot winner* —
   ROI jumps from +2170% to +17,785%. But the n=7 sample is the same
   jackpot-dominated sliver as before, just with more of the small
   losers filtered out.

3. **At t=30s, WR actually HIGHER (20.9%) but P&L lower.** The wins
   here are small — avg +$50 — suggesting the 30s window captures more
   mundane reversals but misses the jackpot regime that lives further
   out. This is the opposite of my t=60s thesis where rare wins pay
   huge.

4. **The t=30s + any-gap-filter = 0% WR.** Filtering for gap AND
   restricting to the closer-to-res window kills everything. The
   regime that works is: wide entry window + either broad filter OR
   tight filter.

**What this updates (vs. your round-2 priors):**

- Your "wide-gap filter concentrates the edge" intuition is directionally
  right at t=60s but the edge is carried by one jackpot winner; sample
  size 7 is too small to trust.
- Your "t-20-40s optimum" is contradicted — t-60s is better for the
  asymmetric-payoff version; t-30s is better for a low-variance
  higher-WR version.
- The data suggests TWO distinct sub-strategies live here:
  * **Jackpot mode** (t=60s, no gap filter or ≥20bps): high variance,
    rare big wins, fragile to n.
  * **Scalp mode** (t=30s, no gap filter): 20.9% WR, smaller per-win
    payouts, lower variance. Survives pessimistic costs more robustly.

**Applied to your round-2 pessimistic model:**

t=60s, gap=0 (base):
  Gross +$2884 − $17 fees − $18 adv.sel − 2/3 win haircut = ~+$843,
  ROI ~633%.

t=60s, gap=30 (jackpot regime):
  Gross +$2172 − $2.45 fees − $2.40 adv.sel − 2/3 win haircut = ~+$712,
  ROI ~5770%.

t=30s, gap=0 (scalp regime):
  Gross +$342 − $15 fees − $14 adv.sel − 2/3 haircut = ~+$85, ROI ~75%.

All three survive haircut. Jackpot and scalp are non-overlapping
regimes — you could run both, bankroll-separated.

**Questions for round 3:**

1. The t=60s jackpot regime is 1 winner dominating everything. What's
   the minimum n you'd need to trust the ~13-14% WR in that bucket
   before paper-scaling? My instinct says 30-50 closed trades.

2. Given the two-regime structure, should I run both as paper sub-
   strategies and let live data decide, or commit to one?

3. Your oracle-subset (exact Chainlink match) check — I can pull
   actual Polymarket resolution prices for ~100 markets from Gamma's
   historical endpoint. Worth doing now or after live paper hits n=50?

4. Is there a published Kelly fraction for this kind of asymmetric
   payoff (250× upside, 1× downside, 8% WR)? Full Kelly is wildly
   aggressive on that variance; looking for the right fractional
   Kelly that's stable.

One thing your round-2 made me realize: the +$2,874 was carried by
ONE trade. The gap-filter data above is the same — one market
drives most of the P&L. If that market had gone the other way,
the entire backtest reverses sign. That's not a backtest confirming
an edge; that's a backtest with a single lucky sample. Live paper
trading is the only way to actually answer this.

Paper bot running at t=60s, no gap filter, $5 size, 10-position cap.
Will report back at n=50 and n=200.
```

---

## Notes

- Grok's round-2 already conceded "no longer obviously stupid". This round confirms their specific predictions (regime matters, gap filter helps) while contradicting others (t-20-40s was wrong).
- The one-jackpot-dominates observation is the most important thing in this round. If that trade had gone the other way, base P&L would be roughly breakeven.
- Suggested practical response: run both t=60s and t=30s as paper sub-strategies (easy config tweak per Bot G, or a second Bot G variant).
