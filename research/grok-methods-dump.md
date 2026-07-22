# Grok Intel — Polymarket Trading Methods (11 Categories)

**Source:** Grok (X platform assistant), delivered verbatim by user
**Date received:** 2026-04-14
**Model version:** Not specified by source
**Preservation rule:** This file is a verbatim paste of the delivered intel. Do NOT summarise or rewrite. If superseded, add a new dated dump alongside; don't overwrite.

---

**Polymarket microstructure note (April 14, 2026):** Fee Structure V2 (live since ~March 30) charges dynamic taker fees (peaking near 50% probability) while paying **daily USDC maker rebates** (20% on crypto, 25% elsewhere, funded by takers). This tilts the game heavily toward limit-order liquidity provision and rebate farming; pure taker strategies face extra drag. No oracle mechanics changes (UMA Optimistic Oracle, 2-hour dispute window). All data below is current as of today's X activity and on-chain patterns.

X is the primary signal source (aggressive keyword + semantic searches + thread dives on high-engagement posts since Jan 2025). Real operators leak mechanics via screenshots, videos, PnL curves, and complaints. Hype posts (Claude bots turning $1k → $730k) are flagged as **Reported** with skepticism; backtested or wallet-verified edges are **Verified** where possible. No public data = "no specifics found."

### 1. Near-Resolution Scalping — Crypto Short-Term (5/15-min BTC/ETH/SOL Up/Down)
**Mechanic:** Monitor live BTC/ETH/SOL spot price vs. Polymarket 5-min or 15-min "Will BTC be above X at HH:MM?" windows. In final 5–60 seconds, when outcome is decided on CEX but PM order book lags (winning side still trades 24–99¢), place limit/market buy on the certain side. Hold to resolution ($1.00 payout). Repeat across 1,440+ daily windows.

**Example market:** Any active 5-min BTC Up/Down (e.g., "BTC 5-min 74,500–75,000" windows).
**Entry/exit prices:** Buy winning side at 98–99.7¢ (or as low as 24–62¢ on momentum-mispriced opens); resolve at $1.00.
**Edge per trade:** 0.3–2¢ per share (~0.3–2% gross). $10 position = $0.03–$0.20 net after gas/fee drag.
**Frequency:** 100–1,440 opportunities/day (every 5/15 min across assets).
**Capital required:** Minimum $100–$1k viable (scale to $10k+ per window for $100–$1k daily). Optimal $50k+ for size without slippage.
**Infra required:** API + fast WebSocket + low-latency VPS (eu-west-1/4 ~22ms ping). Basic laptop for monitoring only.
**Automation level:** Fully botable (Claude-generated Python/TS/Rust; FIFO queue sniping).
**Risks:** Last-second flash reversal, liquidity dry-up (no fill at 99¢), gas spike, CLOB queue position.
**Current crowding:** Extremely crowded; spreads tightened to 0.3–0.5¢ in 2026. Still prints for fastest bots.
**Known practitioners:** High-volume wallets (e.g., 255 trades/hour bot turning $4,485 → $230k in 6 weeks, 78% BTC/84% 5-min); anonymous Claude bots claiming $300–$900/day. Wallet examples in threads show 6k–12k shares/position.
**Sources:** Verified backtests (56/56 wins last-15s strategy); X videos/PnL screenshots.

**Verified:** Backtested 100% WR samples + public wallet PnL curves.
**Reported:** Claude hype threads (engagement farming common).
**Inferred:** Top HFT wallets (RN1/swisstony patterns) run variants.

### 2. Delta-Neutral / Volatility-Split on Short-Term Crypto (YES+NO Sum < $1.00)
**Mechanic:** When Up + Down prices sum < $1.00 (e.g., 49¢ + 49¢ = 98¢), split USDC and buy equal shares of both via split/merge. Hold until volatility resolves: sell losing leg cheap (1–2¢) near resolution or let winner pay $1.00. Net: original collateral + 1–2% per cycle. Skip unclear windows.

**Example market:** Any 15-min BTC Up/Down during consolidation.
**Entry/exit prices:** Enter both sides at combined < $1.00; sell loser at 1–2¢, winner resolves $1.00.
**Edge per trade:** 1–2% per cycle (risk-free if filled both legs).
**Frequency:** 25–50 viable windows per high-vol session.
**Capital required:** Minimum $1k–$5k (scale with position merging). Optimal $50k+ for inventory.
**Infra required:** API + split/merge functions + monitoring dashboard. Laptop viable for semi-auto.
**Automation level:** Fully botable (Python/TS with position merging for gas efficiency).
**Risks:** One leg doesn't fill (imbalance exposure), extreme volatility, merge/split gas during congestion.
**Current crowding:** Still open but requires speed; retail leaves gaps during spreads blow-out.
**Known practitioners:** Wallet "gangwarharshit" ($329k, 23/25 green days, avg hold 8–12 min); Gabagool22-style reverse-engineered algos.
**Sources:** Wallet screenshots + explanatory threads.

**Verified:** Public wallet PnL + on-chain split/merge patterns.
**Reported:** Gabagool22 leaks (Python/TS from laptop claims debunked for latency).
**Inferred:** Many high-volume bots use this as hedging layer.

### 3. Market-Making / Liquidity Provision with Rebate Farming
**Mechanic:** Place tight limit orders (±3–27¢ around fair value or ±4¢ from entry in reward pools). Capture spread when takers hit you + daily USDC maker rebates (20–25% of taker fees). Manage inventory via hedging or delta-neutral exits. Focus liquid categories.

**Example market:** 15-min crypto or sports with LP rewards.
**Entry/exit prices:** Bid/ask 5¢ wide → capture 1–2¢ flips repeatedly; rebates add 20–25% on volume.
**Edge per trade:** Spread clip (1–6¢) + rebate (covers losses). Example: $20k capital → $500/day LP + rebates after $400 spread loss.
**Frequency:** Hundreds of fills/day in liquid books.
**Capital required:** Minimum $5k–$20k. Optimal $50k–$500k for scale/inventory.
**Infra required:** API/WebSocket + VPS + Google Sheets/Python dashboard. No colo needed.
**Automation level:** Fully botable (Rust/Go for speed; Python common).
**Risks:** Adverse selection (toxic flow), inventory blow-up in volatile periods, rebate changes.
**Current crowding:** Growing but rebate-aware bots still profitable; less crowded than pure arb.
**Known practitioners:** EVPoly bot ($500/day LP + rebates on $20k); RN1/swisstony (92k–139k positions, micro-spread).
**Sources:** Daily rebate screenshots + bot videos.

**Verified:** Rebate payout screenshots + wallet volume.
**Reported:** Top bots $5k+/day rebates.
**Inferred:** Microstructure "ant-moving" from high-position wallets.

### 4. Weather Directional with Model Edge (GFS Supercomputer vs. Crowd)
**Mechanic:** Scan 154 daily temp-range markets (5 US cities). Compare NOAA GFS model forecast (90% historical accuracy) vs. PM crowd price. Bet small when edge >8% (e.g., buy NO at 94–98¢ on overpriced crowd fear).

**Example market:** San Francisco/Boston low-temp daily ranges (Kalshi/PM cross hints).
**Entry/exit prices:** Buy NO at 94–98¢; resolve $1.00 or hold.
**Edge per trade:** 2–6% per position (compounds via repetition).
**Frequency:** Multiple per city daily (hundreds weekly).
**Capital required:** Minimum $100–$1k (small $2–$1.2k bets).
**Infra required:** API + GFS data scrape + Claude/Python script. Laptop sufficient.
**Automation level:** Fully botable (Claude-built agents).
**Risks:** Black-swan weather event, model error, low liquidity.
**Current crowding:** Low; niche and repeatable.
**Known practitioners:** Anonymous weather bots ($25 → $12.4k single trade, $41k/month cumulative).
**Sources:** PnL videos + strategy breakdowns.

**Verified:** Public bot PnL curves.
**Reported:** Claude weather scanner claims.
**Inferred:** Model vs. crowd is classic oracle-adjacent edge.

### 5. Intra-Polymarket Arbitrage (Complementary Markets Sum ≠ $1)
**Mechanic:** Scan multi-outcome or conditional sets where YES+NO < $1.00 or correlated markets misalign (e.g., candidate win vs. party control). Buy cheap leg(s), hedge or resolve.

**Example market:** Any Up/Down or multi-candidate where sum drifts.
**Entry/exit prices:** Combined < $1.00 → arbitrage to $1.00 effective.
**Edge per trade:** Risk-free 1–3% if filled.
**Frequency:** Dozens daily in active sessions.
**Capital required:** $1k+.
**Infra required:** API scanner + fast execution.
**Automation level:** Fully botable.
**Risks:** Fill failure, resolution disputes.
**Current crowding:** Rare real arb (0.12% hit rate in scans); mostly fleeting.
**Known practitioners:** Gabagool22-style bots.
**Sources:** Arb alert threads.

**Verified:** Price-check scans.
**Reported:** Occasional screenshots.
**Inferred:** HFT bots snipe these instantly.

### 6–11: Other Categories (Limited Public Specifics)
- **News/Latency:** Last-seconds CEX lag on crypto/sports (overlaps near-resolution). No new 2026 examples beyond 5/15-min.
- **Resolution/Oracle Edge:** No fresh UMA exploits or ambiguous wording leaks in recent X. Historical cases stale.
- **Sentiment/LLM-Driven:** Claude agents for 5/15-min (prompts scan momentum); claimed but mostly hype. No verified prompt + PnL pairs.
- **Long-Tail Sniping:** Thin pop-culture markets at obvious discounts (buy 7–30¢ "No" on hype events). One wallet: 31k predictions, $117k from $300.
- **Event/Calendar:** Pre-FOMC/debate overreactions — no repeatable numbers in X.
- **Insider/Info Edge:** Suspected 3-trade $2.4M wallet (majorexploiter); tape shows massive single bets.
- **Oddball:** Nothing new (no glitches/airdrops in 2026 data).

**No public specifics found** for pure cross-venue (Kalshi/PM weather alerts exist but no executable spreads), sports in-play final minutes (beyond crypto overlap), or political post-call scalping.

### Ranking of Methods
1. **Solo-operator accessibility** (lowest barrier first): Weather model edge (laptop + Claude), delta-neutral split, rebate MM (VPS but low capital), near-resolution scalping (needs speed).
2. **Current edge remaining** (most open first): Weather directional (niche), rebate/MM (rebates subsidize), delta-neutral (timing gaps persist). Near-resolution and intra-arb heavily arbed.
3. **Automation fit for LLM-edged bot**: High — near-resolution (LLM + momentum signals), weather (GFS scrape + probability), rebate/MM (rule-based + risk params). Low for pure latency (speed > reasoning).

**Bottom line:** 2026 winners grind micro-edges at scale (rebates + timing + models) rather than big directional calls. Public GitHub toys (e.g., NautilusTrader 15-min) are starting points; production = custom execution + monitoring. X leaks mechanics faster than any blog—monitor high-volume wallets daily. Data current to April 14 2026.
