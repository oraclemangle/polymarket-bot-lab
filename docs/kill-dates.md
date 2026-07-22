# Kill Dates and Success Criteria per Bot

**Created:** 2026-04-17 (Session 17g execution).
**Purpose:** dated judgement per bot. Without explicit kill dates, research bets become zombies. This file is the operator's contract with themselves: on the review date, the bot is either scaled, continued with new criteria, or archived. No open-ended "let's see" extensions.

**Convention:**
- **Review date** = scheduled decision point. Outcome is one of: SCALE / CONTINUE-with-revised-criteria / ARCHIVE.
- **Kill date** = hard deadline. If success criteria not met by then, archive to `research/`. No exceptions without a new ADR.
- "Archive" = move code + tests + config to `research/bot_X_archive/`, remove systemd unit, remove dashboard row, keep data.

---

## Bot A — Longshot Fade — **ARCHIVED 2026-04-18 per ADR-033**

**Status:** ARCHIVED. `BOT_A_ARCHIVED=true` is the default; both `polymarket-bot-a.service` and `polymarket-bot-a-shadow.service` early-exit. Watchdog skips `cancel_all` for `bot_a`. Code preserved at `bots/bot_a/` for restoration.

**Archival evidence:** [`docs/bot-a-walkforward-wangzj-2026-04-18.md`](bot-a-walkforward-wangzj-2026-04-18.md) — 12,521 simulated entries against SII-WANGZJ/Polymarket_data, 93.7% hit rate, **-$13,614 total PnL, -$1.09 mean per trade**. Every category bucket negative including fee-free geopolitics (-2.42% mean edge on 535 trades). Asymmetric loss (1-in-16 full-loss > 15 small wins), not calibration; no tuning at the current entry slice can fix it.

**Restoration criteria (ADR-033 reversal conditions):**
- Fresh walk-forward on a narrower entry slice (e.g. sub-1c geopolitics only) showing net PnL > 0 after fees + 2% slippage margin, on ≥ 1,000 simulated trades.
- OR a structural change to the Polymarket fee schedule or market mix that invalidates the 2026-Q1 data prior.
- OR an ML-based filter that demonstrably removes the 1-in-16 full-loss case in historical data.

**Restoration procedure:**
1. Write the new walk-forward doc (`docs/bot-a-walkforward-<variant>-<date>.md`).
2. Log ADR-034+ recording the reversal, cite the positive-PnL walk-forward.
3. Set `BOT_A_ARCHIVED=false` in the bot LXC container `.env`.
4. Re-enable systemd units (`polymarket-bot-a.service`, `polymarket-bot-a-shadow.service`).
5. Paper-mode gate for 2 weeks before any live graduation.

**Archived kill date:** N/A (already archived). Review date removed.

---

## Bot B — Oraclemangle Kelly

**Status:** halted since Session 17 before paper-only pivot. Scorer is the weak link.
**Thesis restated:** directional Kelly bet on markets where the oraclemangle model's YES probability diverges ≥ 8 points from the CLOB price, dispute_risk ≤ 0.25, confidence ≥ 0.70. Moat is the calibrated UMA dispute-risk dataset.

**P0 blockers:**
- OQ-032: `recently_closed_cooldown_hours` on candidates (prevents Session 14 Bolsonaro re-entry). Target: 2026-04-19.
- B-2: local-LLM scorer with structured JSON output; replaces regex YES/NO derivation + free-tier Gemini dependency.
- B-3: import oraclemangle calibration dataset locally. Moat asset must be owned, not rented.

**Scoring criteria (must pass all three before any unhalt):**
- Brier score ≤ 0.06 on held-out 20% of the 2,870-market calibration set.
- Calibration curve within 5 points per decile bucket on held-out.
- No regex-based classification remaining anywhere in the scoring path.

**Unhalt gate (after scorer validated):**
- 30 paper days with ≥ 15 filled trades.
- Hit rate ≥ 60% on resolved paper positions.
- Then live at £200 for 60 days.

**Review date:** 2026-05-15 — reassess with new scorer + cooldown deployed.
**Kill date:** 2026-06-30 — if live hit rate < 55% on ≥ 10 resolved positions, archive the bot; moat dataset stays as a research asset.

---

## Bot C — Pyth Traditional-Asset — **ARCHIVED 2026-04-18 per ADR-034; active retry retired 2026-05-04 per ADR-093**

**Status:** ARCHIVED. `BOT_C_ARCHIVED=true` default; daemon early-exits in `bots/bot_c_pyth/__main__.py:main()`. The 2026-04 Hermes paper retry is retired by ADR-093; systemd is disabled on the bot LXC container and the repo unit is inert by default. Code and data are preserved at `bots/bot_c_pyth/`, `core/pyth_*`, and the historical Bot C DBs for restoration or shared research.

**Archival evidence:** `docs/bot-c-thesis.md` §8-9, ADR-034, ADR-093, `docs/reports/bot-c-extract-archive-audit-2026-05-02.md`, and `docs/bot-c-tweet-edge-handoff-2026-05-03.md`.

- Pyth Pro WSS disconnected 2026-04-15 17:37 UTC (HTTP 502), never recovered cleanly. 72+ hours of silent failure; bot operated on stale cached spot.
- Gamma scans return only 3–10 traditional-asset candidates per scan. Trade-cadence ceiling ~10/week even if all infra fixed — below Phase 1 viability window.
- The 2026-05 Hermes paper retry still showed no validated edge: roughly
  4-5 candidates per 500 Gamma markets, weak paper evidence, poor fill
  realism, no hard decision-time stale-bar gate, no live SELL path, and no
  strict walk-forward proof after fees/spread/slippage/adverse selection.
- External LLM review and Opus codebase review agreed the handoff features
  are diagnostic labels, not alpha generators.

**Restoration criteria (ADR-034 reversal conditions, ALL required):**
1. New thesis doc showing either (a) a market-universe expansion path (broader strike-priced scraper, cross-venue Kalshi), or (b) a variant thesis not dependent on Pyth-GBM.
2. Walk-forward backtest/replay on the chosen data source showing positive
   net EV after realistic fees, spread, slippage, and fill/no-fill/adverse
   selection costs on at least `100` simulated trades.
3. Demonstrably working Pyth/Hermes ingest with decision-time freshness
   assertions and more than `1` week of continuous bar data.
4. Complete paper and live exit path, including tested live SELL behavior.
5. Enough actionable candidates to prove the edge without months of waiting.

**Restoration procedure:**
1. Write the new thesis (`docs/bot-c-thesis-<variant>.md`).
2. Log a new ADR superseding ADR-034 and ADR-093, citing the positive-PnL
   walk-forward.
3. Fix Pyth/Hermes ingest (diagnose HTTP 502 pattern, retry with Hermes fallback).
4. Set `BOT_C_ARCHIVED=false` in the bot LXC container `.env`, restore the executor systemd
   settings, and re-enable `polymarket-bot-c.service`.
5. Paper-mode gate for 2 weeks before any live graduation.

**Archived kill date:** N/A. Review date removed.

---

## Bot D — Weather (research track)

**Status:** paper operational in the ADR-079 live-shaped lane. New entries
require verified settlement coverage, known end date, and `<=48h` lock-up.
**Thesis restated:** fade mispriced temperature tails on Polymarket weather markets. Edge from crowd's systematic over-pricing of tail outcomes (analogous to Bot A, weather-specific).

**P0 blockers:**
- D-1: resolved/superseded by ADR-079. `BOT_D_ENTRY_HALT=true` now blocks
  new entries when set, but normal paper collection is allowed only in the
  verified daily lane.
- D-2: finish OQ-058 station verification or keep unverified cities out of
  the live-candidate lane.

**Success criteria (must pass all before any live):**
- ≥ 50 forward paper trades closed in the verified daily lane.
- Net ROI positive after weather fees and 1c slippage stress.
- Ex-largest-win ROI positive.
- No orphan accounting, stale forecast-entry, or missing-end-date entries.
- Depth sufficient for `$5-$10` live entries, with `$25/$50` paper-depth
  coverage reported separately.

**Review date:** 2026-05-31 — with resolution sample in hand.
**Kill date:** 2026-05-31 — if the verified daily lane cannot show
outlier-resistant positive evidence, continue only by new ADR or archive. The
mathematical elegance (seasonal RMSE, skew-normal, METAR UHI) is not a
business; evidence is.

---

## Bot E — OBI Directional Crypto Scalper (research track)

**Status:** recorder asset (462MB of data) worth preserving. Current OBI model calibration: NO-GO, systematically overconfident at every strength bucket.
**Thesis restated:** order-book imbalance + regime filter predicts 15-min BTC/ETH/SOL Up/Down market outcomes at minutes 5-10 of the window. Maker-only entries due to fee structure (peak 1.80% taker crypto).

**P0 blockers:**
- E-2: replace `predicted_wr = 0.5 + |OBI|/2` with logistic regression / GBDT fit on recorded signals. Current formula is monotonically overconfident; data says the model is wrong, not the sample size. Target: 2026-05-15.

**P1 work:**
- E-3: widen feature set (OBI × multiple windows, depth asymmetry, CEX CVD, TTE, regime, realized vol).
- E-4: horizon sweep (try 30-90s forward; mean-reversion framing).
- E-5: extract 44KB `__main__.py` into modules.

**Success criteria (revised paper gate per ADR-022):**
- ≥ 300 trades in calibration.
- Positive net EV after realistic fill model + fees.
- Sharpe ≥ 1.0.
- Max drawdown ≤ 25%.
- Survived ≥ 2 distinct regimes without kill-switch.

**Review date:** 2026-05-31 — with replacement model's calibration verdict.
**Kill date:** 2026-06-30 — if revised paper gate not met with the new model, archive code. Recorder DB becomes a research dataset for future use. No Phase 6 / Phase 7 / "one more feature" extensions.

---

## Bot F — Dropped as Executor, Survives as Sensor

**Status:** executor dropped. 100% rejection rate on local data (all signals age > 90s) makes copy-trading structurally infeasible from this latency profile.
**New role:** intelligence / sensor feed only. No orders. Feeds Bot A/B as down-weighters via `crowd_signals` table.

**P0 work:**
- F-1: delete executor path; neuter `__main__.py` to read-only hunter + mirror observer. Target: 2026-04-20.

**P1 work:**
- F-2: new `crowd_signals` table populated by daily cron. Consumed by Bot A/B candidate filters as down-weighters ("don't enter markets that 6+ copy-bots just entered").

**No kill date.** Sensor-only infrastructure has low maintenance cost and carries second-order strategic value (anti-bot edge awareness).

---

## Review cadence

First week of every month:
1. Check review dates coming up this month.
2. Compute success metrics against current evidence.
3. Decide SCALE / CONTINUE / ARCHIVE.
4. Log decision as an ADR in `docs/decisions-log.md`.
5. Update this file.

No silent extensions. Every "continue" is a dated commitment with revised criteria.
