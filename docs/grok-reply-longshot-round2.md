# Round 2 — reply to Grok's critique

Copy-paste the block below into Grok. This responds to the "strategy is stupid" teardown with concrete data + methodology so Grok can refute or update.

**Strategy:** share the methodology (fee formula, depth model, outcome oracle) and let Grok independently sanity-check. Let Grok see the backtest numbers but frame them as "here's what our tick-level replay produced — tear this apart."

---

```
Thanks for the tear-apart. Real objections, so let me share what the
actual 766-market tick-level backtest produced, with the methodology
exposed so you can verify each claim.

**Dataset:** Bot Longshot Fade (G) backtest on 766 resolved crypto
Up/Down markets (5-min and 15-min, BTC/ETH/SOL), 2026-04-13 through
2026-04-20, from 2.02M Polymarket WSS events + 22M Binance tick-level
CEX trades captured in our own recorder DB (3.87 GB).

**What the backtest does (verbatim logic from scripts/backtest_strategies.py):**

1. For each resolved market, parse question to get (symbol, start_ts, end_ts).
   Example: "Solana Up or Down - April 19, 2:55PM-3:00PM ET" → SOL / 18:55Z / 19:00Z.
2. Determine YES/NO outcome from Binance trade price nearest to start_ts
   vs end_ts (oracle proxy; expected ~0.5% noise vs Polymarket's actual
   Chainlink snapshot).
3. Replay pm_events in order, reconstructing top-5 book levels per side
   from `book` events and updating best_bid/best_ask from `price_change`
   and `best_bid_ask` events.
4. At each 1-Hz tick with `t_to_res in [0, 60s]`, if min(yes_ask, no_ask)
   ≤ 0.02 with ≥20 shares at best, simulate a $5 BUY.
5. Fill simulator walks the book levels best→worst, consuming up to
   order size or until limit exhausted. Partial fills continue on next
   tick. NO unlimited-depth assumption.
6. At resolution, settle against the oracle outcome (YES wins → $1 per
   share; NO wins → $0 per share; strategy owns the opposite).

**Result (fees=$0, no slippage beyond book-walk):**
  fills=54, closed=52, wins=4, losses=48, win_rate=7.7%
  avg_win=$752.72, avg_loss=$2.85
  total_cost_basis=$143.22, total_pnl=+$2,874.14, ROI=+2007%

**Now — let's run your objections against the data:**

**1. Fees.** You cite `fee = C × 0.072 × p × (1-p)`. At p=0.02 this is
0.072 × 0.0196 × $5 = **$0.007 per order**, ~0.14% of notional.
Your "5-7%" figure assumes the fee applies per-share of a ~1¢ ticket,
but per-order on ~$5 notional it's under a cent. Over 54 fills total
fees would be ~$0.40. Even 10× that at $4 total fees, the +$2,874 P&L
doesn't flinch. Am I applying the formula wrong? Does it scale with
notional or with *shares*? If it's ~$0.35/ticket ($0.072 × share count
× fill price × (1-fill_price)), over 54 fills that's ~$19 — still
rounding error against a $2,874 win pool.

**2. Depth / adverse selection.** We DID model depth via the top-5
book levels per side snapshot, walking best→worse. Mean fill size was
~125 shares (not the original 5000-share lunchshot from the first run
that assumed unbounded depth — we caught and fixed that). If LPs pull
quotes pre-res we'd see it as "no qualifying fill" in the replay; 54
fills out of 766 markets means ~7% of markets had a qualifying
≤2¢+≥20-share quote in the final 60s. That's consistent with "bots
already took most of the quotes but some persist."

Adverse-selection is real but not killer: avg_loss=$2.85 (not $5)
means we partial-filled and lost less than max on 48/48 losers. If
MMs were actively dumping on us we'd see fills at limit-price-
exactly + then collapse to $0 — we see that, but the 4 jackpots
nonetheless swamp the losses on THIS dataset. Maybe our window is
too benign; would welcome a regime-breakdown.

**3. Conditional reversal probability (your best point).** You argue
q = P(reversal ≥ required gap | gap_bps, seconds_remaining, vol) is
priced into 1-2¢ quotes correctly. The empirical q on our 52 closed
trades is 7.7%. Market price implied q = avg_entry_price ≈ $0.011
(most trades entered at 1-2¢). If market was correctly pricing,
empirical q should match ~1-2%. Observed 7.7% is 4-7× higher. 

**Is our 7.7% a statistical fluke on n=52?** 95% CI is roughly [2%, 18%].
Market-implied q of ~1% would be at the bottom edge but not ruled out.
Your intuition could be right that as n grows the WR drops toward 1-2%.
We'll have live-paper data in ~30 days at current volume to narrow.

**4. X/Twitter.** Interesting that @polybacktest, @0xTengen_, @xmayeth
run the *inverse* strategies (buying 95-99¢ sides for maker rebate).
That's consistent with the edge existing on the tail side but being
less attractive per-trade. Or it's consistent with Hanlon's razor —
simpler strategies get more attention.

**What would update me negatively:**
- Fee formula applied correctly produces materially more drag than my
  calc (your view on the correct way to compute fee on a 250-share
  fill at 0.02?).
- Regime breakdown: does the edge disappear in the 60-70% of markets
  with small (<15bps) gaps, and only persist in wide-gap markets
  where the "cheap" side is actually a structural reversal bet?
- Chainlink oracle vs Binance spot: how much of the 7.7% WR is our
  oracle being wrong vs Polymarket's actual oracle?

**What would update me positively:**
- Specific historical periods where known manipulation incidents (the
  XRP example you cited) should have produced wins; did the strategy
  capture those?
- A tighter `t-N-seconds` sweep: you guessed t-20s to t-40s; does the
  P&L curve confirm?

**Ask:**
- Can you compute a pessimistic-case scenario with your fee model,
  your adverse-selection premium, and a 3× WR haircut, applied to our
  54 fills? That gives us a "does it survive realistic costs?" answer.
- Is there any known arbitrageur or LP who has publicly reported
  defending this specific edge? If nobody claims to front-run this,
  where's the price-discovery mechanism?

Not trying to win the argument. Real data: 52 closed trades, not 52,000.
Ready to be wrong if the fee math or adverse selection really does flip
the sign when modeled properly.
```

---

## Supplementary — if Grok asks for the raw numbers

Share this table:

```
Phase                         Closed  W/L      WR    Total P&L    Total Cost   ROI
Backtest (no fees, full data)    52    4/48   7.7%   +$2,874.14   $143.22    +2007%

Breakdown by entry price bucket:
  <=0.005                          3    1/2   33.3%  +$4,990        $5.01   +99,600%  (THE big winner)
  0.005 < p <= 0.010              8    0/8    0.0%  -$80           $80      -100%
  0.010 < p <= 0.015             10    1/9   10.0%  +$50           $125     +40%
  0.015 < p <= 0.020             31    2/29   6.5%  -$86           $138     -62%
```

## Decision before sending

Consider: does sharing the raw numbers give Grok enough to produce a genuinely-new counter that materially updates our priors? Or does it just invite confirmation bias?

**Risk of sharing:** Grok anchors on "+2007% ROI" and becomes less critical. We lose the ability to test the opposite edge (Grok pure first-principles analysis).

**Benefit of sharing:** Specific fee-math correction, specific regime-filter suggestions, specific historical validation points — all improve our follow-up backtests.

Send the numbers in a follow-up turn, NOT the first reply. First reply: methodology + direct challenge to the fee formula claim. Second reply (after Grok clarifies fees): the numbers.
