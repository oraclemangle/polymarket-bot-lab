# Grok Intel — Winning Polymarket Bots & Wallet Archetypes

**Source:** Grok (X platform assistant), delivered verbatim by user
**Date received:** 2026-04-14
**Model version:** Not specified by source
**Preservation rule:** This file is a verbatim paste of the delivered intel. Do NOT summarise or rewrite. If superseded, add a new dated dump alongside; don't overwrite.

---

**Polymarket microstructure update as of April 14, 2026 (critical reframing):** On March 30, 2026, Polymarket rolled out **Fee Structure V2**: dynamic taker fees now apply to most categories (peaking near 50% probability outcomes; crypto ~0.072–1.8%, sports ~0.03–0.75%, politics/finance/economics 0.04–0.05). Makers pay zero and earn **daily USDC rebates** (20% crypto / 25% most others) funded by those taker fees. Geopolitical/world-events markets remain fee-free. This materially favors **market-making / liquidity provision** and rebate-farming bots while increasing drag on pure taker-heavy directional, arb, or scalping strategies. No major changes to CLOB API access, Polygon settlement, or UMA Optimistic Oracle (still 2-hour dispute window + bonds). Past oracle risk example (2025 Ukraine minerals market, ~$7M allegedly manipulated via UMA voting power) remains the benchmark; no equivalent 2026 public blowups surfaced in X or analytics.

**X/Twitter mining summary (aggressive thread-dive priority):** Recent posts (since Oct 2025) are dominated by **Claude/AI-generated bot hype** (5/15-min BTC/ETH/SOL scalping, volatility splits, copy-trading sharps via TG bots like Ares, KreoPolyBot, Ratio, PolyApex). Screenshots show claimed $1k–$900/day on micro-arb or copy-trade, but skepticism is high ("engagement farming," fake dashboards, malware in cloned GitHub repos). Real top wallets rarely disclose; complaints focus on slippage in copy-trading or "Claude bots that lose money." High-volume wallets (RN1, swisstony) are repeatedly labeled bots doing bid-side scalping, rebate farming at 0.01–0.06 spreads, Dutching/hedging vs books, or synthetic YES/NO ladders. No full live dashboards from verified top bots; strategy leaks are rare and high-level. Quote-tweet chains under Polymarket posts and leaderboard screenshots surface wallet addresses and "insider" calls (e.g., majorexploiter 3-trade $2.4M monthly win).

**On-chain/leaderboard reality (polymarketanalytics.com + native leaderboard):** Top PnL dominated by low-position sharps (likely human/hybrid with info edge) vs. ultra-high-frequency wallets (92k–139k+ positions, ~53–56% win rates, micro-profits) that are clearly bot-driven. Position sizing, frequency, and off-hours volume (inferred from patterns) separate them. Data updated every 5 mins; all-time as of Apr 14 2026.

### Per-Actor Breakdown

**Verified** = direct from polymarketanalytics.com / leaderboard / on-chain. **Reported** = X claims/screenshots. **Inferred** = trade-count + PnL-per-trade patterns (flag explicitly). Only notable actors with public signals; no filler.

#### Sharp Directional / Likely Manual or Hybrid (Low Positions, High Conviction/WR)
| Identity | Verified PnL (source) | Strategy Classification | Markets | Position Sizing/Frequency | Tech/Infra Clues | Known Losses/Blowups | Notes & Sources |
|----------|-----------------------|--------------------------|---------|---------------------------|------------------|----------------------|---------------|
| **Theo4** (0xF00D000000000000000000000000000000000009) | +$22,053,934 all-time (22 positions, 88.9% WR) | Manual sharp trader / possible info edge | Politics (historical heavy); now broader | Large concentrated bets; very infrequent | Wallet cluster patterns historically; likely UI + manual | Minimal public drawdowns | Classic French-whale-style sharp; not bot. Verified. |
| **Fredi9999** (0xF00D00000000000000000000000000000000000a) | +$16,619,507 all-time (66 positions, 73.3% WR) | Manual sharp trader / possible info edge | Politics primarily | Large single bets; low frequency | Same cluster as Theo4 | None major reported | Verified; part of historical network. |
| **PrincessCaro** (0xF00D00000000000000000000000000000000000b) | +$6,083,643 all-time (21 positions, 100% WR) | Manual sharp trader | Politics/sports? | Large bets; infrequent | Linked historically | None | Verified. |
| **kch123** (0xF00D00000000000000000000000000000000000c) | +$12,059,612 all-time (3,840 positions, 54.1% WR) | Manual sharp trader (sports EV) | Sports dominant (football, NBA/NFL spreads) | Rare but massive bets; selective | X threads call "pure human" heavy bets | Prior drawdowns reported in analyses | Higher frequency than pure sharps but still conviction-based; not pure bot. Verified + reported. |
| **beachboy4** | +$2,667,527 all-time (monthly leader) | Manual sharp trader | Sports (European/US leagues) | $300k–$3M+ single bets; 40-win streaks reported | Manual conviction plays | Jan 2026 massive drawdown (recovered) | Verified on leaderboard; X/Reddit sharp-human label. |
| **majorexploiter** | +$2,416,975 monthly (3 trades) | Insider/information edge (flagged) | Sports (e.g., basketball/tennis) | 3 massive wins; then stopped | UI likely; joined Feb 2026 | None yet | X calls "pure insider play." Reported + verified monthly. |

#### High-Frequency / Clearly Bot-Driven (Microstructure, MM, Arb)
| Identity | Verified PnL (source) | Strategy Classification | Markets | Position Sizing/Frequency | Tech/Infra Clues | Known Losses/Blowups | Notes & Sources |
|----------|-----------------------|--------------------------|---------|---------------------------|------------------|----------------------|---------------|
| **RN1** (0xF00D00000000000000000000000000000000000d) | +$7,310,807 all-time (92,649 positions, 55.7% WR) | Market-making / liquidity provision + micro-spread arb / hedging | Sports + crypto short-term | Micro (cents) repeated 100s×/day; 49k+ trades/month examples | Bid-side only scalping, rebate farming, Dutching vs books; off-hours implied | Some months net loss on hedging fails | Textbook bot (high vol, low edge per trade). Verified + X-reported. |
| **swisstony** (0xF00D00000000000000000000000000000000000e) | +$5,783,900 all-time (139,575 positions, 53.3% WR) | Market-making / liquidity provision + spread clipping | Broad (sports/crypto) | Micro-profits repeated at scale | Ultra-high frequency; "model worker" label on X | Drawdowns in volatile periods | Clear bot pattern. Verified + reported. |
| **gmanas** (0xF00D00000000000000000000000000000000000f) | +$4,955,881 all-time (6,670 positions, 50.9% WR) | Automated HFT / microstructure | Mixed | High frequency, small edges | Called "automated execution" in X analyses | Minor | Bot-like. Verified. |
| **GamblingIsAllYouNeed** (0xF00D000000000000000000000000000000000010) | +$4,816,501 all-time (83,642 positions, 54.0% WR) | Market-making / arb | Mixed | Micro repeated at volume | High trade count | Not specified | Bot signal. Verified. |

**Other reported/inferred bots (X hype, lower verified PnL):**
- **gabagool22** (profile linked in X): Reported volatility-split bot on 15m crypto (buy cheap side + opposite on overreaction; sum <1.00). 86% WR claimed, $165k–$246k/month examples. Inferred automated. Reported only.
- **Black-Scholes quant bot** (X profile linked): Reported 12k predictions, $21k/day avg using options pricing model on crypto up/down. $411k PnL in 3 weeks claimed. Reported.
- **Claude-built 5/15-min crypto bots** (multiple X promoters, e.g., @cryptosymbiiote, @AleiahLock students): Claimed $1.4k → $238k–$730k in days/weeks via arb/scalping/copy-trade. Many lose money per counter-posts. Reported + inferred (promotional).

**GitHub catalogue (production vs toys):**
- **Official Polymarket**: py-clob-client / ts-clob-client / agents repo (AI trading examples); poly-market-maker keeper (276*+). Production reference.
- **amadeusprotocol/polymarket-trading-bot** (TS, 218*): Copy-trading + CLOB client.
- **Poly-Tutor/polymarket-5min-15min-1hour-arbitrage-trading-bot-tools** (Python, 216*): Production-style short-horizon crypto arb/scalping. Recent commits.
- Many others (<100* or hype): momentum/arb/copy-trade combos; warnings of malicious key-stealing repos (e.g., dev-protocol hijacks). Most toys/reference; real edges private/custom. No public repo claims consistent top-leaderboard PnL.

**Discord/Telegram:** Public servers heavy on copy-trading bots (Ares, PolyApex, KreoPolyBot, Ratio). Leaked chatter is mostly promo; no deep production strategy dumps.

**Long-form/Polymarket content/adjacent:** X is the real signal source. Substack/Medium echo fee changes and Black-Scholes/quant edges. Kalshi/Manifold strategies (sports vs books) port but Polymarket CLOB + rebates favor faster infra.

### Strategy Meta-Analysis (2026 Reality)

1. **What's Actually Working in 2026 vs 2023–2024**
   2023–2024: Naive YES/NO sum<1 arb, simple news latency, directional politics — largely arbed away or fee-killed.
   **2026 winners (X + on-chain):** Rebate/MM + micro-spread farming (0.01–0.06 clips repeated at scale in sports/crypto); volatility splits / synthetic hedging on 5/15-min BTC/ETH/SOL; Black-Scholes / quant models on short-horizon crypto; copy-trading verified sharps + AI overlay; bid-side Dutching / rebate farming to avoid taker drag. High-volume bots (RN1/swisstony) still print via sheer frequency + rebates.

2. **Edge Decay**
   Crowded: Basic arb, naive Claude copy-trading (slippage + fees kill).
   Room left: Sophisticated rebate-aware MM (custom spreads/risk), private quant models (Black-Scholes, weather metrics), multi-wallet hedging. Rebates make MM less crowded for capitalized players.

3. **Capital Requirements**
   Micro-arb/scalping/copy: $1K–$10K viable (but fees eat).
   MM/rebate farming: $50K–$500K+ for inventory + scale.
   Sharp directional: $100K+ per conviction bet.
   Minimum viable production bot: $10K–$50K bankroll + monitoring.

4. **Infra Requirements**
   Laptop only: Claude prototyping / simple copy-trading / monitoring.
   Production: VPS/EC2 (low-latency WebSocket), dedicated RPC for Polygon, env secrets, auto-recovery, Google Sheets/TG dashboards. Rust/Go for sub-second; Python/TS common. No colocation needed (centralized CLOB). Monitoring/alerts essential.

5. **The Oracle Risk Picture**
   UMA disputes rare but expensive (bond loss). 2025 Ukraine minerals (~$7M) remains the cited case (alleged whale manipulation via voting power). No major 2026 equivalents in public X/leaderboard data. The external scorer product (https://oraclemangle.com) directly relevant — focus on clear-wording markets or dispute-window monitoring. Verified historical.

6. **Geo/Regulatory Reality**
   Anonymous Polygon wallets + VPNs standard. Top actors pseudonymous (French network precedent persists). US restricted (CFTC); many EU/elsewhere or non-US entities. KYC-lite historically. No public doxxing of active bots.

7. **Unknowns / Dark Matter**
   Private HFT firms / multi-agent AI swarms (beyond public Claude hype). Coordinated wallet clusters. Sudden micro-order floods in low-liquidity markets (testing/spoofing?). Insider sports models that look manual but run automated. Tape signals not publicly claimed. Survivor bias extreme — losing bots silent; only copy-trading promoters loud.

**Bottom line for your bot:** Prioritize **rebate-aware MM or 5/15-min crypto volatility/arb** with dynamic spreads, position merging, and auto-hedging. Public GitHub = starting point only. On-chain transparency helps reverse-engineering, but speed + capital + risk separate winners. Microstructure evolves weekly — re-verify daily. Data current to April 14 2026; filter hype aggressively. Good luck.
