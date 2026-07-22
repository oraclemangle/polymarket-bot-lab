[reasoning only — increase max_tokens]
Let me carefully analyze this trading bot strategy for Polymarket. I need to be critical, find mistakes, and rank by blast radius (real-money risk first, then correctness, then hygiene).

Let me go through systematically.

## BIGGEST BLAST RADIUS ISSUES (Real-money risk)

### 1. Edge calculation is systematically wrong for "hit" markets vs "finish above" markets

This is the single most critical flaw. The GBM model computes P(S_T > K) — the probability of being above K at time T (terminal price). But many of the question patterns are "hit" patterns:

- "weekly_hit" pattern: "Will X hit (HIGH/LOW) $K Week of [date]"
- "eom_hit" pattern: "Will X hit (HIGH/LOW) $K by end of [month]"

The GBM terminal probability P(S_T > K) is the probability the price is above K at maturity. But "hit" means "touches at some point during the period." For upward barrier, P(hit above K by time T) ≥ P(S_T > K) — it's strictly greater because the price could touch K and then go back below.

For a barrier at K above, the probability of hitting at some point is approximately:
P(hit K by T) ≈ 2 * P(S_T > K) for ATM-ish barriers (reflection principle under GBM with zero drift)

More precisely: P(max_{0≤t≤T} S_t ≥ K | S_0) = P(S_T ≥ K) + (K/S_0)^{2μ/σ²} * P(S_T ≥ K) (for drift μ)

For zero drift: P(max_{0≤t≤T} S_t ≥ K) = 2 * P(S_T ≥ K) when K > S_0

This is a MASSIVE systematic mispricing. If the market is pricing "will hit $200" and you're computing "will be above $200 at T", you'll systematically underestimate the probability for "above" hit markets and overestimate for "below" hit markets.

For strike above spot: model gives P(above at T), but market is pricing P(touch above K by T). The model UNDERESTIMATES the true probability. So the bot will often see "model < market" → BUY_NO on "hit above" markets, which is the WRONG direction.

For "hit (LOW)" markets: P(min S_t ≤ K) = 2 * P(S_T ≤ K) for zero drift. So the model UNDERESTIMATES the probability of hitting below. The bot sees "model < market" for "below" markets → BUY_NO, which is WRONG.

Wait, let me re-check the direction mapping. Looking at the code:
- "weekly_hit" with HIGH side → direction = "above"
- "weekly_hit" with LOW side → direction = "below"

Then in evaluate_market:
- direction "above" → gbm_prob_above (terminal P(S_T > K))
- direction "below" → gbm_prob_below (terminal P(S_T < K))

So for "Will AAPL hit (HIGH) $200 by end of week":
- Market is pricing: P(touch $200 at some point during week)
- Model computes: P(S_T > $200) = terminal probability ≈ 0.5 * P(touch $200)
- Model says probability is way lower than market → edge is negative → BUY_NO
- But the market is CORRECT that the touch probability is higher! The model is wrong!
- So the bot will systematically BUY_NO on "hit above" markets and BUY_NO on "hit below" markets

Actually wait. Let me think more carefully.

For "hit (HIGH) $200" with AAPL spot at $195:
- Touch probability: P(max S_t ≥ 200 by T) ≈ 2 * P(S_T ≥ 200) [for zero drift, strike > spot]
- Terminal probability: P(S_T ≥ 200) 
- Touch prob >> terminal prob
- Market price ~ touch prob
- Model computes terminal prob
- Model prob << market price for YES
- Edge = model_p_yes - market_p_yes < 0 (model thinks prob is much lower)
- Side = BUY_NO

But the market is pricing the TOUCH probability, which is CORRECT. The model is underpricing. So the bot buys NO when it should probably buy YES (or at least not trade). This is systematic — every "hit" trade will be on the wrong side.

This is a FUNDAMENTAL flaw that guarantees losses on "hit" markets.

Actually, let me reconsider. Is the market correct? The market is pricing the touch probability. The model computes terminal probability. If the model says 0.30 and the market says 0.55, and the true probability is 0.55... then:
- edge = 0.30 - 0.55 = -0.25
- Bot buys NO at 0.45 (since NO price = 1 - 0.55)
- True NO probability = 1 - 0.55 = 0.45
- Bot pays 0.45 for something worth 0.45 → zero expected value... minus fees

Actually no. If the true touch probability is 0.55:
- YES is worth 0.55, market price is 0.55
- NO is worth 0.45, market price is 0.45
- Bot buys NO at 0.45 + 0.01 = 0.46
- Expected value = 0.45 - 0.46 = -0.01 → losing money

But wait, the bot buys NO at mid + 0.01. If mid for NO = 0.45, limit = 0.46. Plus 3% fee on the pay side. So it's definitely losing.

More precisely: the bot systemically takes the wrong side on hit markets because its model underestimates the probability. This isn't a small error — for near-the-money options, the touch probability can be roughly 2x the terminal probability. The bot will consistently buy NO on "hit above" markets where spot is near the strike, thinking it's a 25% chance when it's really 50%.

This is a terminal bug. The strategy as coded CANNOT be profitable on hit markets.

### 2. "Between L and H" markets — terminal vs. barrier

The code already acknowledges this in known limitations, but it's worth emphasizing. If the question is "will the price be between $100 and $120" and it means "at any point" (which is how many such markets work), then the model using terminal probability P(L < S_T < H) is wrong. The "between" barrier probability (stays in a range for entire period) is much less than terminal probability of being in range.

Actually, "between" on Polymarket typically means the resolution price is between L and H, i.e., terminal. Let me reconsider — for Polymarket, "between" markets usually resolve based on the final price. So terminal probability IS correct. But the "hit" vs "finish" distinction is critical and the code conflates them.

### 3. Limit price computation is problematic

Looking at `_choose_token_and_limit`:
- For BUY_YES: mid = Decimal(str(decision.market_p_yes)), limit = mid + 0.01
- For BUY_NO: mid = 1 - Decimal(str(decision.market_p_yes)), limit = mid + 0.01

The `market_p_yes` comes from the Gamma API's `outcomePrices` or `lastTradePrice`. This is NOT the order book mid. It's the last trade price or the displayed price, which could be stale (polled every 60 seconds), and doesn't reflect the actual bid-ask spread.

If the bot computes a 0.15 edge based on the API price, but the actual order book has moved, the real edge could be much smaller or even negative. The bot has no way to get the actual order book depth before placing.

Also, posting at mid + 0.01 means the bot is crossing the spread to take liquidity. As a price-taker with stale data, this means fills happen when the market has moved against the bot.

### 4. No exit logic

Holding to resolution with binary outcomes is actually OK IF the model is correct. But given that the model has systematic errors (hit vs. finish), no exit means there's no way to cut losses on bad entries.

More importantly: no exit means no capital recycling. If the bot enters a 90-day position (even though it caps at 7 days in code — wait, let me check: `BOT_C_MAX_HOURS_TO_RESOLUTION` = 24*7 = 168 hours = 1 week), capital is locked with no way to free it even if the thesis is clearly wrong.

For binary markets, if you buy YES at 0.60 thinking it's worth 0.80, and the market moves to 0.95... your position is worth 0.95 but you can't realize that gain. Or if it moves to 0.20, you've lost 0.40 of your 0.60 invested with no stop.

### 5. Fee model is not in the edge calculation

The edge threshold is 0.15 gross. Polymarket's fee structure (the bot mentions ~3% at 50% prob) means:
- Buying YES at 0.60: pay 0.60 + 0.03*1.0 = 0.63? Actually, Polymarket fee is typically on the payout side. Let me recall: Polymarket charges a taker fee of about 1-2% on the payoff. For a $1 payoff, the fee can be ~2-3 cents.

Actually, Polymarket fees work like: when you buy YES shares at price p, you pay p per share, and if it resolves YES, you get $1 per share minus the fee. The fee is on the winnings.

So for BUY_YES at price p:
- Cost per share = p
- Payoff if YES = 1 - fee ≈ 0.98
- Expected payoff if model probability is q: q * 0.98
- Expected P&L: q * 0.98 - p
- Edge after fees: q * 0.98 - p = (q - p) - 0.02*q ≈ (q - p) - 0.02*q

For BUY_NO at price (1-p):
- Cost per share = 1-p
- Payoff if NO = 1 - fee ≈ 0.98
- Expected payoff if model probability of NO is (1-q): (1-q) * 0.98
- Expected P&L: (1-q) * 0.98 - (1-p) = (p - q) - 0.02*(1-q)

With edge = q - p = 0.15 and q ≈ 0.75:
- Net edge for YES: 0.15 - 0.02*0.75 = 0.15 - 0.015 = 0.135
- Still positive but tighter

With edge = 0.15 and q ≈ 0.85:
- Net edge for YES: 0.15 - 0.02*0.85 ≈ 0.133

Hmm, actually let me check the exact Polymarket fee structure. The latest is a dynamic fee based on the order book at time of fill. The simple model: fee_rate ~ 2% on the payout. Some sources say it can be up to 3%.

The bigger issue is the fee is NOT subtracted from the edge calculation. With 0.15 threshold, the actual net edge might be 0.12-0.13. Still positive but less comfortable.

### 6. Annualisation factor is wrong for mixed asset classes

`bars_per_year = 252 * 6.5 * 3600 = 5,896,800`

This is correct for equity-only markets (AAPL, TSLA, etc.) that trade 6.5h/day, 252 days/year. But crypto trades 24/7/365. For crypto:
- bars_per_year = 365.25 * 24 * 3600 = 31,557,600 (coincidentally equal to seconds/year)

Using 5,896,800 for crypto inflates sigma_ann by sqrt(31,557,600 / 5,896,800) ≈ sqrt(5.34) ≈ 2.31x.

So the annualized volatility for BTC/ETH/SOL will be overestimated by ~2.3x. This massively distorts the probability calculations:

For gbm_prob_above with an inflated sigma:
- d = [ln(S/K) - 0.5*σ²*T] / (σ*√T)
- If σ is 2.3x too high, σ² is 5.3x too high
- The -0.5*σ²*T term dominates, making d much more negative
- This makes P(S_T > K) MUCH lower than it should be
- So the bot will consistently underestimate upward-move probabilities for crypto
- And consistently underestimate downward-move probabilities too (since P(below) also uses inflated σ)

Wait, let me reconsider. Higher σ makes the distribution wider, so:
- P(S_T > K) for K > S_0: higher σ increases probability (because of fatter tails)
- But the -0.5*σ²*T term is a drag that DECREASES probability

For short time horizons (T small), the ln(S/K) / (σ√T) term dominates and higher σ → higher P > K.
For longer time horizons, the -0.5*σ²*T drag term dominates and higher σ → lower P > K.

The crossover depends on how far the strike is from spot and the time horizon.

For weekly markets: T = 7/365 ≈ 0.019 years
For BTC at σ_ann = 60% real vs 138% inflated:
- 0.5 * 0.6² * 0.019 = 0.5 * 0.36 * 0.019 = 0.0034
- 0.5 * 1.38² * 0.019 = 0.5 * 1.90 * 0.019 = 0.018

So with inflated σ, the probability drag is ~5x larger. For a strike 5% above spot:
- σ√T real = 0.6 * √0.019 = 0.083
- σ√T inflated = 1.38 * √0.019 = 0.190
- d_real = [ln(1.05) - 0.0034] / 0.083 = [0.0488 - 0.0034] / 0.083 = 0.546 → P = 0.71
- d_inf = [0.0488 - 0.018] / 0.190 = 0.163 → P = 0.56

So inflated σ understates the probability of being above. But this is directionally biased: the bot will buy NO on "above" crypto markets and buy YES on "below" crypto markets too often.

Actually for "below" with inflated σ:
- P(below K) where K < S_0: with inflated σ, P(S_T < K) is higher (fatter left tail)
  - d = [ln(S/K) - 0.5*σ²*T] / (σ√T)
  - With S > K, ln(S/K) > 0, but -0.5*σ²*T reduces it
  - For below: we compute Φ(-d), and with smaller d, Φ(-d) is larger

So for BTC:
- "Above" markets: model understates probability → BUY_NO too often
- "Below" markets: model potentially OVERSTATES probability → BUY_YES too often

The net effect depends on which markets present opportunities, but the direction is consistently wrong for crypto. This is another systematic money-loser.

### 7. Pyth feed_id mapping — I don't see it in the code

The strategy code takes a `feed_id` parameter but there's no mapping from the parsed market symbol (e.g., "AAPL") to the Pyth feed_id. The discovery module outputs a `symbol` string, and somewhere the mapping to Pyth feed IDs must happen. If that mapping is wrong or missing, you get the wrong spot/vol for the wrong asset. This is a correctness issue that could lead to catastrophically wrong trades.

### 8. GTC limit orders with stale data

Bot polls Gamma API every 60 seconds. Pyth data is 1-second bars. But the order is placed at a price derived from the Gamma poll, which could be 60 seconds stale. In a fast market, the actual order book could have moved significantly. A GTC order sitting there can get filled at a bad price when the market moves through it.

Worse: the bot calculates edge based on the current state, places a GTC order, and that order can sit indefinitely. If the edge disappears (spot moves, vol changes), the order remains active with no cancellation logic. Someone can pick off the stale order.

### 9. No dedup on symbol + direction + strike

The dedup is on `gamma_id` (condition_id). But what about similar markets? If there are two markets for "AAPL above $200 by end of week" with different gamma_ids but the same economic thesis, the bot could double up. More importantly, if there's a "AAPL above $200" weekly and an "AAPL above $200" monthly, the bot might enter both, doubling risk on essentially the same thesis.

### 10. The `evaluate_market` uses `edge_threshold` = 0.10 but executor uses 0.15

There's a disconnect. The strategy function has a default threshold of 0.10 but the executor checks 0.15. Some SKIP decisions at 0.10 would be actionable... actually no, the executor further filters by 0.15, so anything with edge 0.10-0.14 is skipped by BOTH. The issue is that edge_threshold in evaluate_market serves to determine the `side` field. If |edge| < 0.10, side is SKIP. But the executor checks 0.15 separately. So edges between 0.10 and 0.15 would have side="BUY_YES"/"BUY_NO" from evaluate_market but would be rejected by the executor. This is fine logically but it means the strategy function's edge_threshold is misleading. It's a hygiene issue, not a real-money risk.

### 11. Resolution date vs expiration — critical mismatch

The code uses `market.resolution_date` which is constructed from the parsed question text (e.g., "Week of April 14" → April 14 23:59:59 UTC). But the actual Polymarket resolution for equity markets is based on the closing price on a specific day. For "Week of April 14" hit markets, the resolution might be any time during that week, not at end of the week.

Moreover, the code computes `hours_to_resolution` as the time until the parsed resolution date. If the resolution is for "end of April" and the relevant price is the closing price on the last trading day, the bot might be computing edge using too much or too little time. For equities, the resolution should use trading days, not calendar days.

Actually, a bigger issue: computing `t_years` as total_seconds / 31,557,600 (seconds per year) gives CALENDAR time. But GBM annualized σ is in TRADING time (252 days, 6.5h). So if the market resolves in 7 calendar days but only 5 are trading days:
- t_years_calendar = 7/365 = 0.0192
- t_years_trading = 5/252 = 0.0198

Close enough for a week, but over 90 days with holidays... the discrepancy grows.

Actually the bigger issue is: the GBM model should use TRADING time for equities, but the bot uses calendar time (time until resolution date, in calendar years). During weekends and overnight, equity prices don't move (in GBM terms), but the bot's time variable keeps ticking. This means the bot OVERESTIMATES the time to expiration for equity markets by the fraction of time the market is closed.

For a weekly market resolving on Friday, the actual trading time might be 5 days out of 7, so the bot overestimates T by 40%. This matters for the probability:
- Higher T → lower impact of the -0.5*σ²*T term (since σ is annualized to trading time, using more calendar T understates the drag)

Wait, let me think more carefully. If σ_ann is computed as σ_per_bar * √(bars_per_year) where bars_per_year = 252*6.5*3600, then σ is annualized in "trading time." But T is computed in calendar time. This is inconsistent.

Correct approach: either use trading-time T (where T = trading_days / 252), or convert σ to calendar-time annualization.

Currently:
- σ_ann is in "252 trading days of 6.5 hours" annualization
- T is in calendar years (365.25 days * 24h)
- The σ√T computation uses a time variable that's too large (includes non-trading hours)
- This effectively overstates σ√T, making d smaller
- For above-the-money strikes, this means the model UNDERESTIMATES P(S_T > K)

This is another systematic source of mispricing for equity markets. The crypto σ inflation and the equity time inconsistency are BOTH pointing in the same direction for certain market types, compounding the error.

### Now let me organize all findings by blast radius:

**CRITICAL (Money-losing even in theory):**

1. **Hit vs. Finish probability confusion** — The most devastating error. "Hit" markets have ~2x the probability of "finish above" markets at the same strike. The GBM terminal probability model is wrong for all "hit" markets. The bot will systematically BUY_NO on "hit above" and systematically BUY_YES on "hit below" (or buy NO)... actually let me reconsider.

For "hit (HIGH) $200":
- direction in code = "above"
- Model computes P(S_T > 200) = terminal prob
- True prob = P(max S_t ≥ 200 by T) ≈ 2 * terminal prob (for near-ATM)
- If terminal prob = 0.30, true prob = 0.60
- Market price ≈ 0.60
- edge = 0.30 - 0.60 = -0.30
- Bot buys NO

But market price should be ~0.60, and NO trades at ~0.40.
Bot buys NO at ~0.41 (mid 0.40 + 0.01).
True NO prob ≈ 0.40.
Bot pays 0.41 for something worth 0.40 → expected loss of 0.01 + fee

For "hit (LOW) $200":
- direction = "below"
- Model computes P(S_T < 200) = terminal prob
- True prob = P(min S_t ≤ 200 by T) ≈ 2 * terminal prob (for strike near spot)
- If terminal prob = 0.30, true prob = 0.60
- Market price YES ≈ 0.60
- edge = 0.30 - 0.60 = -0.30
- Bot buys NO... wait, that's wrong. The bot would buy NO when model price is below market.

Hmm, but actually, "hit (LOW)" means the price hits a LOW level. So the strike is probably below the current price (it's a downside target). Let me reconsider:

If AAPL is at $200 and the market is "Will AAPL hit (LOW) $180?":
- True prob = P(min S_t ≤ 180 by T) 
- Terminal P(S_T ≤ 180) could be, say, 0.20
- Touch P ≈ 2 * 0.20 = 0.40
- Market price ≈ 0.40
- Model computes 0.20
- edge = -0.20 → BUY_NO

Bot buys NO at 0.60+0.01 = 0.61, true NO value is 0.60. Slight loss.

Actually wait, I keep getting small losses. Let me think about a case where the hit/finish difference creates a BIG loss.

AAPL at $198, "Will AAPL hit (HIGH) $200 by end of week":
- Terminal P(S_Friday > 200) with 5 days left, σ_ann = 30%:
  - ln(198/200) = -0.01005
  - σ√T = 0.30 * √(5/252) = 0.30 * 0.1409 = 0.04227
  - d = (-0.01005 - 0.5 * 0.09 * 5/252) / 0.04227 = (-0.01005 - 0.000893) / 0.04227 = -0.259
  - P(above) = Φ(-0.259) = 0.398

- Touch P(max ≥ 200 by T) with zero drift: P_touch = 2 * P(S_T > 200) = 2 * 0.398 = 0.796

Wait no, the reflection principle says P(max ≥ K) = P(S_T ≥ K) + (K/S_0)^{2r/σ²} * P(S_T ≥ K) for GBM with drift r. With zero drift (r=0):
P(max ≥ K | S_0) = P(S_T ≥ K) + P(S_T ≥ K) = 2 * P(S_T ≥ K)

Hmm, but this only applies when K ≥ S_0. For K ≤ S_0, P(max ≥ K) = 1.

Actually, since AAPL is at $198 and K = $200, K > S_0, so:
P_touch = 2 * P(S_T > K) = 2 * 0.398 = 0.796 (hmm, this seems too high)

Let me double check. Actually the formula is:
P(M_T ≥ K) = P(S_T ≥ K) + (K/S_0)^{2μ/σ²-1} * Φ(d') where d' is some expression.

For zero drift (μ = 0), the simpler formula is:
P(M_T ≥ K) = 2 * P(S_T ≥ K) when K > S_0

This IS correct for standard Brownian motion, but for GBM with drift μ = 0, it's:
P(max S_t ≥ K by T) = 2 * N(d1) where d1 = [ln(S_0/K)] / [σ√T]

Wait, I need to be more careful. Under zero-drift GBM:
ln(S_T/S_0) ~ N(-0.5σ²T, σ²T)

P(S_T ≥ K) = N([ln(S_0/K) + 0.5σ²T] / [σ√T])

Hmm, that doesn't look right either. Let me re-derive.

Under GBM with μ = 0:
dS/S = σdW
ln(S_T) = ln(S_0) - 0.5σ²T + σW_T
ln(S_T/S_0) = -0.5σ²T + σW_T

So ln(S_T/S_0) ~ N(-0.5σ²T, σ²T)

P(S_T ≥ K) = P(ln(S_T/S_0) ≥ ln(K/S_0))
= P(-0.5σ²T + σW_T ≥ ln(K/S_0))
= P(σW_T ≥ ln(K/S_0) + 0.5σ²T)
= P(W_T ≥ [ln(K/S_0) + 0.5σ²T] / σ)
= P(Z ≥ [ln(K/S_0) + 0.5σ²T] / [σ√T])  [where Z = W_T/√T ~ N(0,1)]
= N(-[ln(K/S_0) + 0.5σ²T] / [σ√T])
= N([ln(S_0/K) - 0.5σ²T] / [σ√T])

This matches the code's d = (ln(S_0/K) - 0.5σ²T)/(σ√T) and Φ(d).

For the reflection principle with zero drift:
P(max_{0≤t≤T} S_t ≥ K | S_0) = P(S_T ≥ K) + (K/S_0) * P(S_T ≥ K²/S_0) 

Hmm, I'm getting confused with exact GBM barrier formulas. Let me use a simpler approach.

Under zero-drift GBM, the first-passage time to a barrier K > S_0 has a known distribution. The probability that the barrier is hit before time T is:

P(τ_K ≤ T) = N(-d1) + (K/S_0) * N(-d2)

where d1 = [ln(S_0/K) + 0.5σ²T]/(σ√T) and d2 = [ln(S_0/K) - 0.5σ²T]/(σ√T)

Actually let me just use the standard result. For GBM with drift r, the probability of hitting level K (K > S_0) before time T is:
P(M_T ≥ K) = N(-d+) + (K/S_0)^{2r/σ²-1} * N(-d-)

where:
d+ = [ln(S_0/K) + (r + 0.5σ²)T] / (σ√T)
d- = [ln(S_0/K) + (r - 0.5σ²)T] / (σ√T)

Wait, these formulas are getting complicated and I don't want to get them wrong. Let me just use the key insight:

**For zero-drift GBM, the probability of touching an out-of-the-money barrier before expiration is approximately 2x the terminal probability of being beyond that barrier at expiration.**

This is a well-known result (reflection principle for Brownian motion). The exact factor depends on how far the barrier is from spot and the drift, but 2x is the zero-order approximation for a zero-drift process.

With our example:
- Terminal P(S_T > $200) ≈ 0.4
- Touch probability ≈ 0.8
- But the code computes 0.4

If the market is efficiently pricing the touch probability at ~0.8:
- edge = 0.4 - 0.8 = -0.4
- Bot buys NO at ~0.20 + 0.01 = 0.21
- True NO prob (touch doesn't happen) = 0.2
- Bot pays 0.21 for something worth 0.20 → slight loss + fee

Hmm, or with fees the loss is:
- Expected payout = 0.2 * (1 - fee) = 0.2 * 0.98 = 0.196
- Cost = 0.21
- Expected P&L = -0.014 per share

But what if the market is NOT perfectly efficient? What if market price is 0.7 for the YES (between our 0.4 and the true 0.8)?
- edge = 0.4 - 0.7 = -0.3
- Bot buys NO at 0.31 (mid 0.30 + 0.01)
- True prob of NO = 0.2
- Expected payout = 0.2 * 0.98 = 0.196
- Loss = 0.196 - 0.31 = -0.114 per share

That's a significant loss. The bot is systematically on the wrong side.

What about "finish above" (like "weekly_finish" or "month_settle")? Those DO use terminal probability, which IS what the model computes. So those might be OK... except all the other errors still apply.

**Summary of the hit/finish issue:** The bot conflates "hit" (barrier touch at any time) with "finish above" (terminal price above at resolution). For "hit" markets, the model systematically underestimates YES probability, causing the bot to take the NO side when it should take YES or skip. This is a guaranteed systematic loss maker.

### 2. Annualization mismatch for crypto

Using equity hours (252 * 6.5 * 3600 = 5,896,800) for crypto that trades 24/7 overstates σ_ann by factor ~2.3x. This corrupts all crypto probability estimates.

### 3. Trading time vs calendar time

T is computed in calendar time but σ is annualized in trading time for equities. This overstates σ√T and systematically biases probabilities.

### 4. Zero drift assumption for equities with known drift

For weekly/monthly equity bets, the equity risk premium (say 5-10% annual drift) is significant. With the model assuming zero drift:
- For "above" equity markets: model UNDERESTIMATES probability (because it ignores positive drift)
- This compounds with the hit/finish error for hit-above equity markets
- For "below" equity markets: model OVERESTIMATES probability of going below

The drag from -0.5σ²T in the d calculation already captures some of this (it's the risk-neutral drift), but in reality equities have a POSITIVE actual drift. Using zero drift instead of risk-neutral drift (which for equities is approximately the risk-free rate) might actually be closer to reality for physical probability... but the GBM formula with -0.5σ²T corresponds to risk-neutral drift = 0, which is less than the actual drift.

Hmm, let me think about what the bot is computing:
d = [ln(S/K) - 0.5σ²T] / (σ√T)

Under GBM with drift μ = r (risk-neutral):
d = [ln(S/K) + (r - 0.5σ²)T] / (σ√T)

With μ = 0 (bot's assumption):
d = [ln(S/K) - 0.5σ²T] / (σ√T)

The difference: bot uses drift of -0.5σ² (which comes from the Ito correction), but real-world equities have drift μ ≈ 0.08 (8% per year). So the bot's drift is:
μ_bot = 0 (under the physical measure, the expected return of the stock should be > 0)

Wait, let me reconsider what the "right" drift is. In prediction markets, we want to compute the PHYSICAL probability (real-world probability that the event occurs). NOT the risk-neutral probability. Risk-neutral pricing is for derivatives pricing; prediction market pricing should use physical probabilities.

Under physical measure with drift μ:
P(S_T > K) = N([ln(S/K) + (μ - 0.5σ²)T] / (σ√T))

The bot uses μ = 0:
P(S_T > K) = N([ln(S/K) - 0.5σ²T] / (σ√T))

For equities with μ ≈ 8%/year and σ = 30%/year:
The effect on "above" markets with T = 1 month:
- μ*T = 0.08/12 = 0.0067
- σ²T/2 = 0.045/12 = 0.00375
- Effect on d: (μ*T) / (σ√T) = 0.0067 / (0.3 * √(1/12)) = 0.0067 / 0.0867 = 0.077

This shifts the probability by about 3% (cumulative normal at d=0 is 0.5, at d=0.077 is 0.53). So for one-month equity "above" markets, the zero-drift assumption understates probability by ~3%.

Over longer horizons, the effect grows. For 3-month: μ*T = 0.02, shift in d = 0.02 / 0.15 = 0.13, about 5% probability shift.

This is significant but not as devastating as the hit/finish confusion.

### Now let me compile findings systematically:

## CRITICAL (Guaranteed money loss)

**F1. Hit vs. Finish: GBM terminal probability used for barrier-touch markets**
- "weekly_hit" and "eom_hit" patterns ask whether a barrier is touched at ANY point during the period
- Model computes P(S_T > K) (terminal) instead of P(max S_t ≥ K by T) (barrier)
- For zero-drift GBM, barrier touch probability ≈ 2x terminal probability for OTM strikes
- This causes systematic mispricing: bot buys NO when YES is correct
- Blast radius: EVERY "hit" market trade will be on the wrong side or at a worse price
- Fix: Implement first-passage probability formula, or only trade "finish"/"settle" markets

**F2. Crypto annualization uses equity trading hours**
- bars_per_year = 5,896,800 (equity) applied to 24/7 crypto assets
- Overstates crypto σ_ann by ~2.3x
