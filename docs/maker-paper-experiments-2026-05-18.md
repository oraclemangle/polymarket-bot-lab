# Maker-Paper Experiments — 2026-05-18 (from full codebase audit)

**Status:** Paper-only proposals derived from live evidence (the bot container dashboard + DB + Data API patterns) and maker-vs-taker daily comparator (2026-05-16). No live promotion. All require new ADR + explicit operator approval before any live-probe packet.

**Source data (verified live 2026-05-18 from the bot container dashboard /api/overview + DB queries):**
- Bot D live_probe: +31.06 realised / 11.07% ROI, 178 fills, 95 closed, last_fill 2026-05-17, exposure 0.
- Bot D maker_live_probe: +0.12, 17 fills, 0 closed, exposure 21.5.
- Bot G prime live: -189.13 / -78.71% ROI, 140 fills, 123 closed, exposure 0.8 (vps, last_fill 2026-05-10 — stale).
- Crypto Brownian FV live_maker (paused): -104.05 / -31.4%, 109 fills, 105 closed, exposure 0.
- Crypto Prob-gap FV live_maker (paused): -63.25 / -21.55%, 108 fills, 102 closed + 3 open, exposure 10.65.
- Paper lanes (G makers, D, I persistence, J/K): mixed, with FV paper shadows showing +10-14% lifetime and +13pp maker lift vs taker in 05-16 comparator.
- All numbers cross-checked against live the bot container systemctl, curl /api/overview (26 rows), and sqlite position/trade aggregates.

## Profitability Ranking (live verified 2026-05-18, using dashboard inventory + DB)

**Profitable now (positive realised, recent resolved activity, low risk concentration)**:
- Bot D live_probe: +31.06 / 11.07% ROI on 280+ cost basis, 178 fills / 95 closed, recent fills — highest quality live evidence. Gate: continue collecting resolved to clear OQ-067/116 for modest scaling proposal.

**Promising under-sampled (positive direction or maker lift, below full gates, needs more data)**:
- G high-tail maker shadow: +54% ROI on small n (~20-48 closed in reports), near 50 gate — push existing paper service.
- FV maker paper (both cells): lifetime +10-14% on 200+ resolved, documented +13pp lift vs taker baselines in daily comparator — best revival candidate.
- I persistence maker (A/B cells): +10% on 40/40/40 — run to 50/cell per current timers.

**Accounting-blocked (P0 — do not scale or trust ROI until OQ-123 report reviewed)**:
- FV live makers (paused per ADR-181): large negative realised + residual exposure on prob-gap; separate persistence_live.db for Bot I; unowned wallet activity confirmed in prior Data API matches.
- Bot G prime live: -189 legacy with stale last_fill (May 10) while registry still "live".
- Bot I live: 0 in main.db, true wallet P&L negative per previous Data API.

**Recorder data validation (May 2026, read-only on the bot container production DBs)**:
- Maker V2 recorder: 12M+ pm_events, Phase 2 tables live (73 maker_quotes, 49 maker_paper_fills). Replay on the live DB returned **INSUFFICIENT_DATA** for the target politics 0-10c and sports 10-20c cells (0 markets/trades in the sensitivity combos). The raw feed is correct and rich; coverage in the specific cells the H maker paper and maker revival experiments were built around is still too low for the OQ-100 gate.
- Bot E crypto recorder: 220M+ pm_events + 166M+ cex_trades — excellent volume for G paper and Longshot research.
- VPS: active paper feed service + snapshots; main production recorders are on the bot container.

## New Research Lane: X / Low-Viewership Account Sourcing for Uncrowded Edges (Added 2026-05-18)

**Rationale (profitability focus)**: High-follower Polymarket content is already arbitraged. Low-viewership / pseudonymous accounts on X frequently post or demonstrate real edges in weather, high-tail temperature outcomes, resolution source latency (especially Weather Underground), and maker execution in low-volume/niche cells before the crowd copies them. These are exactly the "niche data advantages" that survive in a bot-dominated market.

**Goal**: Systematically monitor a shortlist of low-follower accounts and terms to generate new filters, models, or market universes for existing paper lanes (primarily Bot D weather and G high-tail maker paper) without increasing live risk.

**Target accounts / signals to monitor (low viewership / high signal)**:
- Cold Math / ColdMath style: grinding high-confidence near-certs (95–99¢) with ensemble consensus + micro-mispricing on specific cities.
- meropi / 1pixel style: automated real-time monitoring of ensembles vs prices for micro + ladder bets on NYC/London and other high-volume weather markets.
- Hans323 style: asymmetric tail bets on extreme temperature outcomes where models show convexity the market underprices.
- Resolution source latency: posts or on-chain analysis highlighting speed advantages on Weather Underground / specific station feeds (the forensic paper with ~179 reads explicitly calls this the real edge for elite wallets).
- Maker / microstructure in obscure cells: low-profile accounts discussing spread capture + rebates in thin political or event markets.

**Proposed experiments (paper-only, read-only data first)**:

**Experiment A — Bot D Weather "Resolution Latency + Ensemble Consensus" Filter (highest priority for current live edge)**
- bot_id variants: bot_d_live_probe, bot_d_maker_live_probe, bot_d_source_shadow, bot_d_ensemble_ladder
- Universe: Daily city temperature buckets (focus on high-volume cities like NYC, London, Chicago, Seoul first).
- Entry rule: Model ensemble (GFS 31-member + ECMWF + local station) probability > market price by >5–8% **and** signal that a low-view account or on-chain latency pattern suggests the resolution source will update before the market reprices.
- Data sources: Public ensembles + targeted X monitoring of the accounts above + historical resolution timing from the recorder DB.
- Metrics / gates: Same as existing D gates + new "latency edge capture rate" and "edge after resolution source timing".
- Kill gate: If the added filter does not improve ex-largest ROI on the next 50 resolved trades, drop it.

**Experiment B — G High-Tail Maker Paper "Extreme Temperature Tails"**
- bot_id: bot_g_prime_high_tail_maker (and shadow variants)
- Universe: High-tail temperature outcomes (top 5–10% probability bins) in the same crypto-linked or event-driven weather markets where low-view accounts have shown asymmetric payoffs.
- Maker entry: Post-only in cells where the recorder already has good depth coverage (from the Maker V2 replay data) + model shows tail probability materially higher than market.
- Fill realism: Use the existing recorder book + trade prints (we already validated the data is correct).
- Reward eligibility: Track maker rebates in these cells.
- Gates: Reach n=50 resolved in the tail bins with positive ex-largest ROI before any live micro-probe discussion.

**Experiment C — Maker Paper in "Obscure Low-Volume Cells" (longer term)**
- Use the low-view maker/microstructure accounts to identify thin political or event markets where spread + rebate + low competition still exists.
- Only in cells where the Maker V2 recorder already shows sufficient event volume (avoid the INSUFFICIENT_DATA cells identified in the 2026-05-18 replay).

**Implementation (safe, local first)**:
- Maintain a private watchlist of the accounts and terms listed above.
- Use (or extend) the local monitoring helper `scripts/research/x_low_view_polymarket_edge_monitor.py` (generates ready-to-paste advanced search URLs for the watchlist + key terms). Run it periodically (e.g., weekly) and review the output manually.
- Promising signals (new station quirks, model improvements, resolution latency patterns, obscure maker cells) are logged and fed into the existing paper bot backtesting / model improvement pipeline.
- Nothing moves to production paper code or live without manual review + backtest on the recorder DB + the usual gates (n, ex-largest ROI, concentration, OQ-123 clean).

**Success metric for this lane**: At least one new filter or universe that improves ex-largest ROI on the next 50–100 resolved paper trades in Bot D or G high-tail without increasing concentration risk.

This lane is deliberately designed as a low-cost, high-upside research track that feeds the existing profitable (or near-gate) paper services rather than creating new live risk. It directly exploits the "low viewership = uncopied edge" dynamic the operator highlighted.

**Archive / low priority**:
- Bot A, C, E trading (retired/archived per ADRs).
- G late-cheap / take-profit (falsified on signal per ADR-140).
- Old F mirror (superseded).

**Recommended order (fastest path to verified positive ROI with clean accounting)**: 
1. OQ-123 dry-run report (new wallet_reconcile_dryrun.py) — unblock trust in any future numbers.
2. Grow resolved sample + edge validation in the only currently approved live family (Bot D live/maker probes) — already showing +31 realised / 11% ROI with recent fills.
3. Push G high-tail maker paper to the full gate (n, ex-largest, concentration) — was closest in prior small samples.
4. Continue D maker live probe resolved data (compare maker vs taker live fills).
5. Only after the above + OQ-123 clean: revisit Maker paper experiments in cells where the recorder now has sufficient coverage (the current target cells were INSUFFICIENT per the live replay).

All paper-only or tiny-live only inside existing approvals until the above are met. No new tiny-live proposals without the gates + new ADR + explicit operator sign-off.

## Experiment 1: Crypto FV Maker Paper Continuation + Gate Push (probability-gap + Brownian)

- **bot_id variants**: crypto_probability_gap_paper_maker, crypto_brownian_fv_paper_maker (existing shadows + recorder)
- **Market universe**: 5m/15m BTC/ETH/SOL 95-99c high-side cells (same as current shadows)
- **Maker entry rule**: non-crossing post-only quotes, min notional per cell from recorder book depth, 120-300s lead, avoid top-of-book adverse selection using H maker v2 depth.
- **Fill realism assumption**: Use bot_h_maker_v2_recorder prints for queue/priority simulation + actual CLOB fill probability from recent live maker fills (even though paused).
- **Reward eligibility**: Yes — maker fills in fee-enabled markets; reconcile public rebates via /rebates/current + authenticated rewards (already in reward-credit-reconcile script).
- **Metrics / gates (paper only)**:
  - Resolved fills >= 200 per cell (current ~200-250 lifetime, push to 300+ for ex-largest stability).
  - Realised ROI > +5% after fees/rebates.
  - Ex-largest-win ROI still > +2%.
  - Concentration < 35% in any single symbol/duration bucket.
  - Fill rate bias vs taker baseline documented.
- **Kill gate**: If any cell drops below +1% ex-largest ROI on next 50 closes, archive the shadow and document adverse selection.
- **Service shape**: Keep existing polymarket-crypto-*-maker-paper.service + daily maker-vs-taker report timer. No new live units.
- **Tests**: Extend tests/test_maker_vs_taker_daily_report.py with new cell filters; add replay test using maker_recorder.db for fill simulation.
- **Next**: Run after wallet_reconcile_dryrun report classifies any unowned FV activity. Target: 2026-05-25 review.

## Experiment 2: Bot G High-Tail Maker Shadow to Gate (6.5c-8c ETH/SOL)

- **bot_id**: bot_g_prime_high_tail_maker (existing paper shadow)
- **Market universe**: 6.5c-8c, 45s entry window, ETH/SOL only (matches the $1 live micro-probe but paper).
- **Maker entry rule**: Post-only, non-crossing, fresh clock guard 5s, depth filter from crypto recorder.
- **Fill realism**: bot_e_recorder + bot_h_maker_v2 depth; actual fill probability from G live micro fills (even if stale).
- **Reward eligibility**: Low (small notional), but track any maker rebates.
- **Metrics / gates**:
  - Resolved >= 50 (current ~48 in 05-16 report, +54% ROI on 20 closed).
  - Ex-largest ROI > 0% after removing top 2 winners.
  - Drawdown < 15% of deployed paper bankroll for the shadow.
  - Symbol balance (ETH vs SOL) documented.
- **Kill gate**: If ex-largest ROI < -5% or concentration > 60% in one symbol, retire the high-tail maker shadow (consistent with ADR-140 precedent for late-cheap/take-profit).
- **Service shape**: polymarket-bot-g-prime-high-tail-maker-paper.service (already active).
- **Tests**: Add to existing G maker shadow tests + new ex-largest calculation test.
- **Next**: After 50 closes, produce report and decide on merge into prime maker or archive.

## Experiment 3: Bot I Persistence Maker to 50/cell (Cell A/B)

- **bot_id**: bot_i_persistence_maker (paper)
- **Market universe**: Cell A (5m+15m, 50-55c borderline), Cell B (15m, 85-95c tail) on BTC/ETH/SOL.
- **Maker entry rule**: Same as current persistence maker paper (daily replay from recorder).
- **Fill realism**: Synthetic from historical fills in persistence DBs; compare to live maker fills if any residual.
- **Reward eligibility**: N/A (persistence is directional, not pure maker quote).
- **Metrics / gates**:
  - n >= 50 closed per cell (current ~40 for A/B).
  - ROI > +5% post-fee on full 50, ex-largest still positive.
  - Negative control (random entry) ROI documented for contrast.
- **Kill gate**: If cumulative ROI < +2% on 50/cell or Cell C borderline stays -1% to +1%, archive per ADR-176 precedent.
- **Service shape**: Existing daily persistence_paper_run.py timers (now guarded for live variants).
- **Tests**: Extend persistence_paper_run tests with cell-specific ex-largest and negative-control assertions.
- **Next**: Run daily until 50/cell, then OQ-118 style review for any $1 live probe (exchange min notional blocker remains).

**Cross-refs**: ADR-139 (FV maker paper), ADR-149 (G high-tail), ADR-176 (Cell C blocker), OQ-117, OQ-122, OQ-123 (accounting prerequisite).

All experiments are read-only paper data collection. No live order path changes.

**Approval required**: New ADR + operator sign-off before promoting any to "live-probe" status. The wallet_data_api_backfill.py (or wallet_reconcile_dryrun) dry-run report must be clean for any bot that had live exposure (OQ-123).
