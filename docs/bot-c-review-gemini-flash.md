[Gemini 2.5 Flash (Vertex AI)] Instructions:
Same capabilities as standard Gemini 2.5 Flash. Billed to GCP credits.

Alright, let's critically review your Polymarket trading bot strategy. This is an excellent request, and I appreciate the detail you've provided. I'll approach this by ranking findings by blast radius (real-money risk first, then correctness, then hygiene), followed by answers to your specific questions, and finally a prioritized remediation list.

**Overall Impression:**

This strategy, in its current form, is **fundamentally flawed and should not trade live with real money.** The core issue is that your edge model is ill-suited for the markets you're trading, and your risk controls, while present, don't adequately address the catastrophic potential of this mismatch. You've identified many of these issues yourself, which is a great start.

---

### **Blast Radius Ranking (Real-Money Risk First)**

#### **Category 1: Catastrophic Real-Money Risk (Immediate Stop)**

1.  **Zero-Drift GBM for Equities/Crypto (Fundamental Model Mismatch)**
    *   **Finding:** Your core model, a zero-drift Geometric Brownian Motion (GBM), assumes assets have no expected return. This is a *catastrophic assumption* for equities (AAPL, TSLA, NVDA, SPY, QQQ, PLTR, COIN) and even for crypto (BTC, ETH, SOL), especially for weekly and monthly horizons. Equities have a well-documented positive drift (expected return), and crypto can have even more pronounced trends.
    *   **Impact:** If the underlying asset is trending upwards (which is common for these assets, particularly in bull markets or strong individual stocks), your "above K" probabilities will be systematically underestimated, and "below K" probabilities systematically overestimated. This means you will consistently bet against the prevailing trend and likely take large, repeated losses. Conversely, if there's a strong downtrend, you'll be betting on "above K" too often. The `|edge| >= 0.15` filter is good, but it won't save you from a systematically wrong model. Your model will constantly signal "buy NO" on an upward-trending asset or "buy YES" on a downward-trending asset when the market prices in the drift.
    *   **Example:** Imagine an AAPL market "Will AAPL finish above $200 next week?". If AAPL is at $195 and typically drifts up 0.1% a day, your zero-drift model might say P(above $200) = 0.3. The market, incorporating drift, might say P(above $200) = 0.6. Your model will generate a -0.3 edge and tell you to "BUY_NO", which is likely the wrong trade if the market's drift assumption is more accurate.
    *   **Remediation:** **DO NOT TRADE LIVE.** This is the single biggest flaw. You need to incorporate drift into your model. Even a simple historical drift estimate or a risk-neutral drift (e.g., using interest rates for risk-free assets) is better than zero. For equities, estimating forward drift is complex (earnings, economic outlook), but assuming zero is a guaranteed way to lose money against participants who *do* account for it.

2.  **No Exit Logic, No Stop Losses (Unlimited Downside)**
    *   **Finding:** You explicitly state "NO exit logic", "NO stop losses", and "NO take profit". Positions hold to resolution.
    *   **Impact:** This is extremely dangerous.
        *   **Model Failure:** If your model is wrong (which it will be due to the zero-drift assumption, noisy vol, etc.), you have no mechanism to cut losses. A trade that quickly moves against you will ride all the way to resolution, guaranteeing a 100% loss on that notional if you were wrong.
        *   **Market Events:** Black swans, unexpected news, flash crashes, or even simply a market realizing your position is "wrong" (adverse selection) can quickly invalidate your initial edge. Without stops, your $10 notional can easily become $0.
        *   **Opportunity Cost:** Capital is tied up until resolution, even if the trade is clearly lost.
    *   **Remediation:** **DO NOT TRADE LIVE.** Implement some form of exit logic. While prediction markets are different from spot trading, if your edge disappears or reverses, you should consider unwinding the position. This is especially true if you are systematically mispricing something. A simple approach could be: if your model's edge *reverses* (e.g., you bought YES, now model says BUY_NO with a large edge), consider selling. Even simple stop-loss conditions (e.g., if market price moves X% against you) could provide some protection.

3.  **Adverse Selection (Price Taker Vulnerability)**
    *   **Finding:** You acknowledge being a price-taker and correctly note that if your GTC limit fills, "it's because someone better-informed wanted to sell at that price." Your `Limit price = market_mid_for_side + 0.01`.
    *   **Impact:** This `+ 0.01` offset exacerbates adverse selection. You are *offering a slightly better price* than the market mid to get filled. This means you're almost guaranteeing that if someone takes your offer, they believe the true fair value is lower (if buying YES) or higher (if buying NO) than your offer price. You are essentially paying extra to be potentially picked off by more informed traders or faster bots. This will systematically erode your profitability, especially with a model that already has fundamental flaws.
    *   **Remediation:** **DO NOT TRADE LIVE with `+0.01` offset.** If you must be a price-taker, you should be trying to get filled at the market mid, or even slightly *worse* than mid if you believe your edge is strong enough to justify it. Or, ideally, you should be a price-maker (placing limit orders at the current best bid/ask) rather than trying to get filled *aggressively* against the flow. For a small bot, this is a major vulnerability.

4.  **No Fee-Adjusted Edge Calculation (Systematic Overestimation of Profitability)**
    *   **Finding:** Your `Edge = model_p_yes - market_yes_price` does not factor in Polymarket's fees, which "peaks ~3% at 50% prob".
    *   **Impact:** Your calculated `|edge| >= 0.15` is a *gross* edge. If fees are 3%, your *net* edge is closer to `0.15 - 0.03 = 0.12`. For markets near 0.50, this is a significant haircut. Many trades that you deem profitable will actually be unprofitable after fees. This leads to systematically losing money on trades that your model incorrectly classifies as having positive expected value.
    *   **Remediation:** **DO NOT TRADE LIVE.** Your edge calculation *must* be net of fees. For Polymarket, this means calculating the expected return including the 2-3% taker fee (or maker fee if you manage to place an order that gets taken). This is a critical adjustment for profitability.

#### **Category 2: Significant Real-Money Risk & Correctness Issues (High Priority)**

5.  **Volatility Calculation (Noise, Incorrect Annualization, No Term Structure)**
    *   **Finding:**
        *   "σ from 30 minutes of 1-second log returns, annualised by sqrt(252 * 6.5h * 3600s)"
        *   "σ annualised using equity hours (overstates for 24/7 crypto)"
        *   "30-min σ is noisy, ignores volatility term structure"
    *   **Impact:**
        *   **Noisy 30-min σ:** 1800 1-second bars is a decent sample size, but 30 minutes of *realized* volatility can be extremely noisy and unrepresentative of future volatility, especially for longer horizons (weekly/monthly). A sudden spike or dip in that 30 minutes will massively skew your σ.
        *   **Incorrect Annualization:** You correctly identify that `bars_per_year` is wrong for crypto. Using equity trading hours for 24/7 crypto will *understate* crypto volatility (not overstate as you suggest, as it assumes fewer bars per year for the same level of actual volatility). If `sigma_per_bar` is per second, then `sqrt(365 * 24 * 3600)` would be closer for crypto, which is a much larger multiplier than your equity-based one. This will lead to mispricing crypto markets.
        *   **No Volatility Term Structure:** You're using a single σ for all maturities. Real-world options (and by extension, prediction markets that resemble options) exhibit a volatility term structure, meaning implied vol varies with time to expiry. Using short-term realized vol for 90-day markets is a major simplification that will lead to mispricings.
    *   **Remediation:**
        *   **For Noise:** Consider longer lookback periods for volatility (e.g., 1-day, 5-day, 20-day annualized realized vol), or an exponentially weighted moving average (EWMA). You'll trade off responsiveness for stability.
        *   **For Crypto Annualization:** Correct the `bars_per_year` for crypto assets to `365 * 24 * 3600`.
        *   **Term Structure:** This is advanced. For now, prioritize accurate *base* volatility. If you want to address term structure, you'd need to fetch implied volatilities (e.g., from options markets for equities) or build a more sophisticated realized volatility model that adjusts for time to expiry.

6.  **"Between L and H" Probability (Incorrect for End-of-Period Resolution)**
    *   **Finding:** You state "`between L and H` uses terminal probability (correct for end-of-period resolution, wrong for `at any point`)"
    *   **Impact:** Your `gbm_prob_between` function is correct *if* the market resolves based on the price being within the range *at resolution time*. However, if Polymarket means "will it *ever* trade between L and H at any point before resolution", your calculation is wrong.
    *   **Remediation:** Clarify Polymarket's resolution criteria for "between" markets. If it's "at any point", you'll need a different model (e.g., barrier option pricing for two barriers), which is significantly more complex. Assume your current interpretation is correct unless proven otherwise, but be aware of this potential misinterpretation. The current code assumes *terminal* probability of being within bounds, which is standard for vanilla options.

7.  **Max Horizon: 90 Days & Max Concurrent Positions: 3 (Capital Inefficiency, Slow Feedback)**
    *   **Finding:** Max horizon 90 days. Max 3 concurrent positions. $50 aggregate bankroll cap.
    *   **Impact:**
        *   **Long Horizons:** The longer the horizon, the more dominant the drift term becomes (which your model ignores), the less reliable short-term realized vol becomes, and the longer your capital is tied up without a clear exit strategy. Your *edge* for a 90-day market will be much harder to predict accurately than for a 1-day market.
        *   **Limited Learning:** With only 3 concurrent positions and long horizons, you'll get very slow feedback on your strategy's performance. It will take a long time to gather enough resolved trades to assess profitability.
        *   **Capital Efficiency:** Tying up $10 for 90 days for a $50 bankroll is 20% of your capital, limiting how many edges you can pursue.
    *   **Remediation:** **Reduce max horizon significantly for initial paper trading.** Start with daily/weekly markets (e.g., max 7 days). This will give you faster feedback and reduce the impact of your drift error. Once you have a more robust model, you can gradually increase the horizon. Also, consider the capital allocation relative to max positions. If your goal is to learn quickly, you want more, shorter-duration trades.

8.  **Question Regex Parsing - Ambiguous Date Formats (Incorrect Resolution Date)**
    *   **Finding:** "Ambiguous date formats default to current year."
    *   **Impact:** This is a correctness issue. If a market resolves in an upcoming year (e.g., "Jan 15" for a market created in Dec 2024, resolving Jan 2025), your parser will incorrectly set the resolution date to Jan 2024, leading to wrong `t_years` and therefore wrong probabilities.
    *   **Remediation:** **Improve date parsing.** Always infer the *next* plausible year if a year isn't specified, or explicitly list all ambiguous cases and flag them for manual review/skip until precise. Example: if `month day` is in the past, assume `current_year + 1`.

#### **Category 3: Medium Risk / Correctness (Important to address)**

9.  **No Market/Contract Size Check (Potential Liquidity Issues)**
    *   **Finding:** You have `Min 24h market volume: $100` and `GTC limit, min 5 shares`.
    *   **Impact:** $100 volume is extremely low for a "traditional asset" market. You're trying to trade a $10 notional. If you're trading into a market with $100 daily volume, you're a significant chunk of that volume. If Polymarket charges fees based on total market size (which it usually does via a market making fee), then trading in low-volume markets might lead to higher effective fees or significantly worse fills than anticipated due to lack of liquidity.
    *   **Remediation:** Increase `BOT_C_MIN_VOLUME_24H_USD` to a more realistic level (e.g., $1000 - $5000) for paper trading to simulate slightly more liquid conditions. Also, consider your trade size relative to the *order book depth*, not just 24h volume. You can query Polymarket's order book (if available) to see actual liquidity at various price levels.

10. **Hardcoded Equity Annualization Constant for `bars_per_year` (Incorrect for non-equity assets)**
    *   **Finding:** `bars_per_year = 5_896_800 # 252d * 6.5h * 3600s — approximate for equities`
    *   **Impact:** This is used for GOLD, SILVER, WTI, BTC, ETH, SOL. These are not 252 * 6.5-hour assets. GOLD/SILVER/WTI have different trading hours (though often near 24/5), and crypto is 24/7. This will incorrectly scale their 1-second volatility, leading to mispricings.
    *   **Remediation:** Parameterize `bars_per_year` by `feed_id` or asset type. For 24/7 assets, use `365 * 24 * 3600`. For commodities, investigate their actual trading hours.

11. **GTC Limit Order Behavior (Stale Prices, Missed Opportunities)**
    *   **Finding:** You're placing GTC limit orders.
    *   **Impact:** GTC orders can stay on the book indefinitely. If your model's edge disappears or reverses due to new information (price movement, vol change), your old GTC order might still be active and get filled at a stale, unprofitable price.
    *   **Remediation:** Consider OCO (one-cancels-other) or IOC (immediate-or-cancel) orders, or at least a time-in-force (TIF) of something like "good-for-hour" (GFH) or "good-for-day" (GFD). More importantly, you need to implement **order management**:
        *   **Cancel outstanding orders** if the market price moves significantly, or your model no longer shows an edge.
        *   **Monitor filled orders** to ensure they match your expected price.

12. **Model Assumption: Normal Distribution (GBM implies log-normal, which is fine, but often misses fat tails/skew)**
    *   **Finding:** You use `_norm_cdf`. GBM assumes log-normal prices, which means log-returns are normal. This is a standard assumption but is known to be imperfect for financial assets, which exhibit fat tails and skew.
    *   **Impact:** Your model might underestimate the probability of extreme events (large price moves) and might misprice options with very high or very low strikes (out-of-the-money options).
    *   **Remediation:** This is an advanced modeling topic. For now, acknowledge this limitation. If you were to improve it, you might look into jump-diffusion models or stochastic volatility models, or using implied volatility surfaces if available.

#### **Category 4: Hygiene and Minor Correctness Issues (Good to address, but not critical for initial paper trading)**

13. **`_get_spot_and_vol` minimum rows check:**
    *   **Finding:** `if not rows or len(rows) < 30: return None, None` and `if len(rets) < 10: return spot, None`.
    *   **Impact:** You're using `lookback_bars = 1800` (30 mins). Requiring 30 bars (0.5% of lookback) or 10 returns is extremely low. If you're missing this many bars, your 30-minute window isn't complete, and the realized volatility might be skewed.
    *   **Remediation:** Increase the minimum number of bars or returns required to compute vol (e.g., 90% of `lookback_bars`). If you don't have enough data for the full lookback, perhaps skip the market or use a longer lookback to ensure sufficient data points.

14. **`_money` function for strike prices:**
    *   **Finding:** `_money(s: str) -> Decimal: return Decimal(s.replace(",", "").strip())`
    *   **Impact:** This seems generally fine but assume Polymarket's strike prices always come as numbers or string representations of numbers. If they ever use other characters, this could break.
    *   **Remediation:** Robustness check for various strike formats.

15. **`extract_yes_price` fallback to `lastTradePrice`:**
    *   **Finding:** Your `_extract_yes_price` falls back to `lastTradePrice`.
    *   **Impact:** `lastTradePrice` can be very stale or not representative of current liquidity. The `outcomePrices` (which I assume are current bid/ask midpoints or last traded prices from the Polymarket's own feed) should be preferred.
    *   **Remediation:** Be cautious with `lastTradePrice`. If `outcomePrices` is usually present, then relying on `lastTradePrice` should only be for discovery and perhaps not for active trading decisions, or with a clear timestamp check on its freshness.

---

### **Answers to Your Specific Questions**

1.  **Position sizing: $10 fixed for 10-25% edges with binary-loss shape ($0.80 pay, $0.80 loss if wrong). Should I use half/quarter-Kelly?**
    *   **Answer:** **No, absolutely not, in the current state.** Kelly Criterion (full, half, or quarter) assumes you have an *accurate* estimate of your win probability and payout. Your model's `model_p_yes` is fundamentally flawed due to the zero-drift assumption and noisy volatility. Using Kelly with a systematically biased probability estimate will lead to overbetting on losing trades and potentially blowing up your bankroll rapidly.
    *   **Recommendation:** Stick with fixed notional for paper trading, or even lower it. Only *consider* Kelly (or fractional Kelly) once you have a demonstrably profitable and robust model with accurate probability estimates over a significant sample size of trades. Even then, Kelly is aggressive.

2.  **Stop losses: do binary prediction-market positions need them? When to exit early if edge disappears?**
    *   **Answer:** **YES, they are critical, especially without take profit.** While prediction markets resolve to 0 or 1, and you can't "stop out" in the traditional sense like a stock, you absolutely need a strategy for managing your *position's exposure*. If your edge disappears or, worse, *reverses*, you are holding a decaying liability.
    *   **Recommendation:**
        *   **Conditional Exit:** If your model *re-evaluates* and now shows a significant *opposite* edge (e.g., you bought YES because of a +0.20 edge, and now your model shows a -0.10 edge, meaning BUY_NO), you should absolutely consider selling your YES position, even at a loss.
        *   **Time-Based Exit:** If a position is open for too long and the edge has vanished, or the market has become illiquid, you might want to exit to free up capital.
        *   **Market Price Based:** If the market price moves significantly against your position, and your initial thesis is invalidated, consider exiting. This is harder in prediction markets due to spread, but important.

3.  **Adverse selection: I'm a price-taker. If my GTC limit fills, it's because someone better-informed wanted to sell at that price. Sizer adjustment?**
    *   **Answer:** Your analysis is correct. You are vulnerable.
    *   **Recommendation:**
        *   **Eliminate `+0.01` offset:** Stop aggressively taking price. Place orders at the *current best bid/ask* (i.e., `market_mid_for_side` with no offset, or even slightly *worse* than mid) if you want to be a price-maker.
        *   **Monitor Fills:** If you get filled too quickly or frequently on a particular market/direction, that's a red flag. Track your profitability per market and per fill type.
        *   **Consider Market Making:** If you truly believe you have an edge and the market is inefficient, you might consider attempting to *make* a market (placing both a buy and sell order, capturing the spread), but this is vastly more complex and requires very accurate models and sophisticated order management. For now, focus on being a *smart* price taker, or a patient price maker (at the bid/ask).

4.  **Volatility: 30-min realised from 1s bars — failure modes?**
    *   **Answer:**
        *   **Noise:** As discussed, 30 minutes is a very short window for estimating future volatility, especially for weekly/monthly horizons. A few extreme 1-second bars can massively skew the `sigma_ann`.
        *   **Intraday Patterns:** Volatility exhibits intraday patterns (e.g., higher at open/close). A fixed 30-minute window might capture different "states" of volatility depending on *when* it's sampled.
        *   **Regime Shifts:** If the market enters a new volatility regime (e.g., suddenly becomes very volatile after news), your 30-minute window will react quickly, which can be good, but it might overreact to temporary spikes.
        *   **Non-Stationarity:** Volatility is not constant. A 30-min window assumes it is, for that snapshot.
    *   **Recommendation:** Experiment with different lookback periods (e.g., 1-hour, 4-hour, 1-day) and weighting schemes (e.g., EWMA) during paper trading. Compare the stability and predictive power of different `sigma` estimates.

5.  **Drift assumption: zero-drift GBM for weekly/monthly equity bets — how bad at |edge| ≥ 0.15?**
    *   **Answer:** **Extremely bad.** As the largest real-money risk, this is a fatal flaw for these assets and horizons. An edge of 0.15, while seemingly large, can be completely wiped out (and then some) by a systematic error in your underlying probability calculation due to missing drift. A 15% edge quickly becomes a -5% edge if your model is off by 20% on the probability due to unmodeled drift.
    *   **Recommendation:** **This MUST be addressed before live trading.** Implement some form of drift.

6.  **Trade frequency / crowding: traditional asset markets are 2 weeks old. Expected lifetime of edge?**
    *   **Answer:**
        *   **Frequency:** With 3 concurrent positions, $10 notional, and potentially long holding periods, your trade frequency will be low.
        *   **Crowding / Edge Lifetime:** Prediction markets are highly competitive. If Polymarket launched "traditional asset" markets, it likely attracted sophisticated traders. Edges, especially those based on common models like GBM, can disappear quickly as market participants arbitrage them away. A two-week-old market suggests any simple edges would already be gone. The "lifetime" of an edge can be minutes, hours, or days, but rarely weeks or months if it's based on a publicly known model.
    *   **Recommendation:** Assume short edge lifetimes. Your slow execution and GTC orders mean you're susceptible to these edges disappearing before you get filled.

7.  **Fee-adjusted edge: 0.15 gross → ~0.12 net at mid-book. Profitable after slippage + variance?**
    *   **Answer:** **Unlikely, especially with the other flaws.**
        *   **Fees:** 0.12 net is better, but your gross calculation is still misleading.
        *   **Slippage:** Your `+0.01` limit offset *is* slippage against the true mid. If the true mid is 0.50, you're paying 0.51. That's another 0.01 immediately against you.
        *   **Adverse Selection:** The cost of adverse selection is difficult to quantify but will be significant.
        *   **Model Error (Drift, Vol):** This is the biggest killer. If your underlying probabilities are systematically wrong, no amount of fee/slippage adjustment will save you.
    *   **Recommendation:** You need a **positive net edge *after* all transaction costs (fees, slippage, adverse selection costs) and *after* accounting for model errors.** Your current setup is unlikely to achieve this.

8.  **Failure modes I haven't listed?**
    *   **Polymarket API/CLOB Downtime:** What happens if the Polymarket API or CLOB goes down? Your bot won't be able to query prices, place orders, or cancel.
    *   **Pyth Data Stale/Down:** What if the Pyth feed for a specific asset becomes stale or stops updating? Your bot will be using old `spot` and `sigma`, leading to incorrect decisions.
    *   **Database Failure:** Your `sqlalchemy` setup needs to be robust. What if the DB goes down or gets corrupted?
    *   **Network Latency/Timing Issues:** Your `_get_spot_and_vol` is querying the DB, then `evaluate_market` runs, then `try_enter` places the order. There's a time lag. Market prices (and your edge) can change during this.
    *   **Market Manipulation:** Especially for lower-volume markets, "wash trading" or other forms of manipulation could occur, skewing your volume filter or market prices.
    *   **Arbitrageurs/Front-runners:** Faster bots or those with co-location could potentially front-run your orders, especially with your `+0.01` aggressive limit price.
    *   **Resolution Date Inaccuracies:** The `resolution_date` might be ambiguous or change, leading to incorrect `t_years`.
    *   **Weekend/Holiday Effects:** For equities, market hours are key. How do you handle weekend/holiday gaps in Pyth data or resolution dates that fall on non-trading days?
    *   **Extreme Market Conditions:** During periods of extreme volatility or illiquidity, your model (especially 30-min vol) and execution might break down.

9.  **Systematic mispricings? (skew, jumps, dividends, earnings, gaps, weekend effects)**
    *   **Answer:** Yes, all of these are potential systematic mispricings that your current GBM model *does not account for*:
        *   **Skew:** GBM assumes symmetric log-normal returns. Real equity options exhibit volatility skew (implied vol is different for out-of-the-money puts vs. calls). Your single `sigma` cannot capture this.
        *   **Jumps:** GBM assumes continuous price movements. Real markets have price jumps (e.g., earnings announcements, geopolitical news). These can lead to rapid price changes that invalidate your model.
        *   **Dividends:** For "above/below K" markets on equities, dividends can affect the probability of hitting a strike by slightly reducing the expected future spot price (for ex-dividend dates). Your model ignores this.
        *   **Earnings:** Major earnings announcements cause predictable volatility spikes and potential jumps. Your 30-min realized vol might pick up *post-earnings* volatility, but not the *pre-earnings* uncertainty that drives option pricing.
        *   **Gaps:** Market openings/closings for equities can create price gaps that are not captured by continuous GBM.
        *   **Weekend Effects:** Equity markets are closed on weekends. Your `t_years` calculation needs to account for *trading days*, not just calendar days, for equity-like assets. Your current `dt` calculation uses total seconds, which includes weekends, thus potentially *overstating* `t_years` for equity-based markets and distorting probabilities.

10. **Priority-ordered remediation list for live $2,000 bankroll. What MUST change first?**

    **STOP. DO NOT GO LIVE. The current strategy *will* lose money.**

    Here's a prioritized remediation list for **paper trading first**, before even thinking about $2,000 live:

    ---

    ### **Priority 1: Fundamental Model & Risk Control Fixes (Absolute Must-Haves before *any* live trading)**

    1.  **Integrate Drift into GBM:**
        *   **Action:** Add a drift term (`μ`) to your GBM probability calculations.
        *   **Implementation:** `P = Φ((ln(S/K) - (μ - 0.5σ²)T) / (σ√T))`.
        *   **Source for μ:**
            *   For equities, start with a simple historical average daily drift, annualized (e.g., 10% per year for SPY, adjust for individual stocks).
            *   For crypto, consider a higher historical drift.
            *   Later: Explore risk-neutral drift using risk-free rates (though harder for equities without full options data).
        *   **Code Impact:** Modify `gbm_prob_above`, `gbm_prob_below`.

    2.  **Implement Fee-Adjusted Edge:**
        *   **Action:** Modify `evaluate_market` to calculate edge *net* of Polymarket's taker fees.
        *   **Implementation:** Research Polymarket's fee structure precisely (e.g., 2% on positive EV payout, or direct taker fee). Adjust `market_p_yes` or your edge calculation accordingly. Example: `net_edge = (p_yes * (1 - taker_fee_percent)) - market_p`.
        *   **Code Impact:** Modify `evaluate_market`.

    3.  **Implement Exit Logic (Stop Loss / Take Profit / Edge Reversal):**
        *   **Action:** Add a mechanism to sell existing positions.
        *   **Implementation:**
            *   **Edge Reversal:** If `evaluate_market` for an OPEN position now shows a strong *opposite* edge, place a sell order for that position.
            *   **Time-Based:** After X days, if no edge exists, consider selling.
            *   **Market Price Deviation:** If the market price moves beyond a certain threshold (e.g., 20% against your entry price), attempt to sell.
        *   **Code Impact:** New `try_exit` function in `executor.py`, integrate into main loop.

    4.  **Correct Adverse Selection (Limit Price Strategy):**
        *   **Action:** Remove the `+0.01` offset for limit orders.
        *   **Implementation:** `BOT_C_LIMIT_OFFSET = Decimal("0")`. Consider placing orders at the current best bid/ask, rather than actively trying to cross the spread.
        *   **Code Impact:** Modify `_choose_token_and_limit` in `executor.py`.

    5.  **Refine Volatility Calculation (Lookback, Annualization, Gaps):**
        *   **Action:**
            *   Increase `lookback_bars` (e.g., to 4 hours or 1 day of 1-second bars) for more stable `sigma`.
            *   Parameterize `bars_per_year` by asset class.
            *   For equity markets, adjust `t_years` to account for *trading days* not calendar days (e.g., skip weekends/holidays in `dt` calculation).
        *   **Code Impact:** Modify `_get_spot_and_vol` and `evaluate_market`.

    ---

    ### **Priority 2: Critical Correctness & Robustness (Required for Reliable Paper Trading)**

    6.  **Improve Date Parsing:**
        *   **Action:** Make `_parse_dmy` more robust to ambiguous year cases (e.g., assume next year if month/day is past for current year).
        *   **Code Impact:** Modify `_parse_dmy` in `discovery.py`.

    7.  **Order Management & GTC Cancellation:**
        *   **Action:** Implement a mechanism to cancel stale GTC orders.
        *   **Implementation:** Regularly query your open orders. If an order has been open for too long (e.g., 1 hour) and your model no longer shows an edge for that market, cancel it.
        *   **Code Impact:** New `cancel_stale_orders` function, integrate into main loop.

    8.  **Increase Minimum Market Volume:**
        *   **Action:** Raise `BOT_C_MIN_VOLUME_24H_USD` to at least $1000 - $5000.
        *   **Code Impact:** Modify `executor.py` constant.

    9.  **Reduce Max Horizon for Paper Trading:**
        *   **Action:** Temporarily set `BOT_C_MAX_HOURS_TO_RESOLUTION` to a much lower value (e.g., 24-72 hours, max 7 days).
        *   **Code Impact:** Modify `executor.py` constant.

    ---

    ### **Priority 3: Enhancements & Hygiene (For Optimized Paper Trading and Future Live)**

    10. **Monitoring for Pyth/Polymarket Data Stale/Downtime:**
        *   **Action:** Add checks for data freshness before making decisions.
        *   **Implementation:** Check timestamps on Pyth bars and Polymarket market data. Skip if stale.
        *   **Code Impact:** Integrate checks into `_get_spot_and_vol` and `fetch_candidate_markets`.

    11. **Comprehensive Logging & Alerting:**
        *   **Action:** Ensure all critical actions (order placement, fill, cancellation, errors, halt) are logged clearly.
        *   **Implementation:** Consider integration with an alerting system (e.g., Discord, PagerDuty) for critical failures.

    12. **Consider Weekend/Holiday Handling for `t_years`:**
        *   **Action:** For equity-based markets, refine `t_years` to count trading days, not just calendar days, to match how options are often priced.
        *   **Code Impact:** Modify `evaluate_market`.

    ---

    **Conclusion:**

    Your self-awareness of the known limitations is commendable and accurate. The strategy as described, while well-structured from a code perspective, contains fundamental modeling errors (zero-drift GBM, unadjusted fees, noisy vol, adverse selection) that will almost certainly lead to rapid capital loss in a live environment. **Do not flip the switch to live.**

    Focus on rigorously paper trading with the suggested remediations. Prove profitability and robustness in paper mode over a statistically significant number of trades before even considering real money. Good luck!
