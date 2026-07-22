# GROK_OVERNIGHT_IMPLEMENTATION_SPEC_2026-05-18

**Version:** 1.0  
**Date:** 2026-05-18  
**Audience:** Grok (implementer) for overnight autonomous execution via `/implement`  
**Goal:** Complete the safe, local/read-only portions of the 2026-05-18 full codebase audit implementation, with primary focus on unblocking OQ-123 (wallet/Data API reconciliation) while respecting all hard safety gates. Profitability/ROI work is secondary and gated behind accounting correctness.

## 1. Current-State Analysis (Verified Live Evidence as of 2026-05-18)

**Live Posture (from the bot container + dashboard + registry):**
- Only approved live family: `bot_d_live_probe`, `bot_d_maker_live_probe`, `bot_d_station_lock` (the bot container), plus VPS probes for `bot_d_spike`, `bot_l_complete_set`, and the `$1` `bot_g_prime_live` micro-probe (data collection only, per ADR-149/135).
- Paused (R3, do not restart): `bot_i_persistence_live` (writes to separate `persistence_live.db`), `crypto_brownian_fv_live_maker`, `crypto_probability_gap_live_maker` (per ADR-181).
- Paper/research active: Multiple G maker shadows, D source/ensemble, I persistence paper, J/K, H recorder, wallet observer, etc.
- Key verified numbers (dashboard `/api/overview` + DB aggregates):
  - `bot_d_live_probe`: +$31.06 realised (11.07% ROI), 178 fills, 95 closed, last_fill ~2026-05-17, exposure $0.
  - `bot_d_maker_live_probe`: +$0.12, 17 fills, exposure $21.50.
  - `bot_g_prime_live`: -$189.13 (-78.71% ROI), 140 fills, 123 closed, exposure $0.80, last_fill 2026-05-10 (stale).
  - Paused FV: Brownian -$104.05 (-31.4%), Prob-gap -$63.25 (-21.55%, $10.65 exposure, 3 open positions).
- DB reality: `main.db` (positions/orders/trades/pnl_snapshots) is primary for most bots. `persistence_live.db` (live_entries table) is Bot I-specific. Neither equals whole-wallet truth (unowned weather rows, misclassified redeems in Bot I, historical gaps from fast 5m crypto markets).
- Dashboard: 26 inventory rows, services_summary 47 active/5 degraded. Explicit `accounting` block and per-row `freshness` already partially added in Session 450.
- OQ-123 status: Dry-run tool `scripts/wallet_reconcile_dryrun.py` exists and tested (pulls /positions + /trades, compares both DBs for the 6 critical bots, reports stale/unowned). Bot I report guard exists. Full write-path backfill job + permanent dashboard integration pending.

**Exact File References for Current State:**
- `core/bot_registry.py`: Canonical `BotMeta` for all ~40 bots, `status` ("live"/"paused"/"paper"), `systemd_unit`, `dashboard_visible`, `active_systemd_units()`.
- `dashboard/runtime_queries.py`: `_bot_inventory`, `_live_accounting_metrics`, `query_overview` (returns `bot_inventory`, `accounting` dict added in 450, `last_fill_at`).
- `core/portfolio.py`: `reconcile_live_positions_against_wallet` (existing single-bot, current /positions only).
- `scripts/wallet_reconcile_dryrun.py` (Session 450): The read-only multi-bot reporter (uses httpx for Data API, sqlite for both DBs).
- `scripts/research/persistence_paper_run.py`: Guard for paused Bot I.
- `data/main.db` + `data/persistence_live.db` on the bot container.
- `docs/open-questions.md`: OQ-123 full text + acceptance criteria 1-5.
- `docs/decisions-log.md`: ADR-181 (pause non-D live).
- `docs/active-operating-model-2026-05-02.md` and `docs/reports/project-closeout-analysis-2026-05-18.md`: Current posture tables.

**P0/P1 Risks (from Grok 2026-05-18 audit + closeout):**
- P0: OQ-123 unresolved — `main.db` + `persistence_live.db` diverge from wallet Data API (unowned rows, misclassified Bot I redeems, stale OPENs). Blocks any restart of paused lanes and makes dashboard P&L untrustworthy.
- P0: `polymarket-bot-i-persistence-daily-report.service` in failed state (now mitigated by guard but needs permanent fix + deployment).
- P1: Dashboard does not clearly separate "local bot-ledger" vs "wallet-reconciled" vs "unresolved" values; stale live rows (G prime) not degraded.
- P1: Zero-evidence probes (Bot L, some D variants) still appear active in some views.
- P2: No permanent scheduled backfill job; no integration of reconciliation results into `pnl_snapshots` or dashboard.
- No new live-risks introduced by Session 450 partial work (all dry-run/read-only).

## 2. Required Implementation Phases (High-Level)

**Phase 1: Wallet Reconciliation Dry-Run / Backfill Foundation** (Core of OQ-123)
- Evolve `scripts/wallet_reconcile_dryrun.py` or create `scripts/wallet_data_api_backfill.py` as the authoritative tool.
- Full historical fetch for 2026-05-16 onward (positions snapshot + trades/activity for buys/sells/redeems/rebates).
- Classifier logic: token/condition_id → bot ownership (main.db lookup + persistence_live + manual/unowned/rebate).
- Report + (optional, approval-gated) write to new reconciliation table.
- Support for both DBs and multi-bot (the 6 critical + extensible).

**Phase 2: Dashboard Whole-Wallet Truth Surface**
- Extend `runtime_queries.py` and inventory builder to consume reconciliation data.
- New fields in `/api/overview` and per-bot rows: `wallet_reconciled_realised_pnl`, `unresolved_rows_count`, `reconciliation_status` ("local_only" | "partial" | "fully_reconciled").
- Explicit labels so operator never mistakes local DB for whole-wallet truth.
- Freshness/degraded logic for live rows with old last_fill (already partial in 450; harden it).

**Phase 3: Bot I Daily-Report Guard (Permanent)**
- Ensure the guard in `persistence_paper_run.py` is robust and the corresponding systemd unit on the bot container no longer fails when paused.
- Optional: Make the report script itself check registry before any DB work.

**Phase 4: Stale Live Row / Freshness Handling**
- Generalize the Session 450 freshness warning into a first-class "degraded" signal in services_summary and priority_alerts.
- Tie to registry "live" status + last_fill age + reconciliation status.

**Phase 5: Maker-vs-Taker Paper Experiment Specs (from Audit)**
- Formalize the 3 experiments in `docs/maker-paper-experiments-2026-05-18.md` (already partially created) with precise bot_id, universe, entry/exit rules, fill realism (recorder + live fills), reward handling, metrics/gates (resolved n, ex-largest ROI, concentration, drawdown), kill gates, and test plan.
- No live promotion code.

**Phase 6: Profitability Roadmap + Supporting Reports**
- Codify the ranking (D live first, then G high-tail/FV paper/I persistence, blocked items last) with exact numbers from verified evidence.
- Update or create supporting reports that use the new reconciliation data.

**Phase 7: Tests, Docs, Verification, Safety**
- Comprehensive test coverage (fixtures, unit for classifier, integration for end-to-end dry-run).
- Update OQ-123, active-operating-model, decisions-log (new ADR for the backfill job), MEMORY, CHANGELOG.
- Full local + read-only the bot container verification run.
- Final report artifact.

## 3. Files to Create / Modify

**New Files:**
- `scripts/wallet_data_api_backfill.py` (or rename/evolve the existing dry-run into the canonical backfill tool with --dry-run default).
- `tests/fixtures/wallet_data_api/sample_positions_2026-05-18.json`
- `tests/fixtures/wallet_data_api/sample_trades_2026-05-18.json`
- `tests/test_wallet_data_api_backfill.py`
- `docs/GROK_OVERNIGHT_IMPLEMENTATION_CHECKLIST_2026-05-18.md`
- `docs/GROK_OVERNIGHT_ACCEPTANCE_CRITERIA_2026-05-18.md`
- (Optional) `docs/wallet_reconciliation_schema.md`

**Modify (with extreme care, read full file first):**
- `core/db.py`: Add `WalletReconciliation` model / table (see schema proposal below).
- `dashboard/runtime_queries.py`: Inventory builder, new accounting fields, freshness logic.
- `core/portfolio.py`: Extend or wrap the existing reconcile method for multi-bot + historical + persistence DB.
- `scripts/research/persistence_paper_run.py`: Harden the guard (if needed).
- `core/bot_registry.py`: Minor comments or new helper if useful for "reconciliation_enabled" bots.
- `docs/open-questions.md` (OQ-123 status + next steps).
- `docs/decisions-log.md` (new ADR for the backfill job + risk level).
- `docs/active-operating-model-2026-05-02.md` and `docs/reports/project-closeout-analysis-2026-05-18.md` (status updates).
- `MEMORY.md` and `CHANGELOG.md` (session closeout).
- Existing maker experiments doc (if further formalization needed).

## 4. Database Schema Proposal (wallet_reconciliations table)

New table in `main.db` (or dedicated reconciliation DB if preferred for isolation):

```sql
CREATE TABLE wallet_reconciliations (
    id INTEGER PRIMARY KEY,
    run_at DATETIME NOT NULL,
    wallet_address TEXT NOT NULL,
    condition_id TEXT,
    token_id TEXT NOT NULL,
    source TEXT NOT NULL,                    -- 'data_api_positions', 'data_api_trades', 'manual'
    event_type TEXT,                         -- 'BUY', 'SELL', 'REDEEM', 'REBATE', 'POSITION_SNAPSHOT'
    amount_token REAL,
    amount_usd REAL,
    price REAL,
    timestamp_ms INTEGER,
    bot_id TEXT,                             -- NULL = unowned/manual/rebate-only
    db_location TEXT,                        -- 'main.db', 'persistence_live.db', 'unowned'
    status TEXT NOT NULL,                    -- 'owned', 'unowned', 'rebate', 'reconciliation_only'
    notes TEXT,
    UNIQUE (wallet_address, token_id, timestamp_ms, event_type)
);
```

- Add Alembic migration in `migrations/versions/`.
- `PnlSnapshot` and dashboard queries can later join on this table.
- Backfill job writes here; never mutates core positions/orders without explicit approval + separate migration.

## 5. Dry-Run Wallet/Data API Backfill Design

**Core Class (in the backfill script or portfolio.py):**
- `WalletDataApiClient`: thin wrapper around httpx for /positions?user=..., /trades?user=...&start=..., (future /activity or rewards if needed).
- `ReconciliationClassifier`:
  - Load all relevant positions from main.db + persistence_live.db (by token_id/condition_id).
  - For each Data API row: lookup bot ownership.
  - Rules: exact token match in main → that bot; match in persistence → bot_i_persistence_live; no match → "unowned" or "manual" (with heuristic for weather rows belonging to D journals).
- `ReconciliationReporter`: produces the JSON/human report required by OQ-123 (per-bot wallet P&L, list of unowned, gaps).
- `ReconciliationWriter` (gated behind --execute and explicit confirmation): INSERT into the new table only.
- CLI: `python -m scripts.wallet_data_api_backfill --since 2026-05-16 --dry-run --json --bots bot_d_live_probe,bot_i_persistence_live,...`
- Always default to --dry-run. --execute requires extra env var or interactive prompt (never in overnight run).

**Safety:** The script must refuse to run if it detects any live trading process for paused bots.

## 6. Dashboard Changes Required

- In `query_overview` / `_bot_inventory`:
  - Add top-level `accounting` (already partially present): `wallet_reconciliation_run_at`, `total_unresolved_usd`, `fully_reconciled_bots`.
  - Per inventory row: `reconciliation_status`, `wallet_realised_pnl_usd`, `unresolved_exposure_usd`, `freshness` ("fresh" | "stale_7d" | "stale_30d").
- New helper `_wallet_reconciliation_snapshot(bot_id)` that reads the new table.
- Explicit labels in `pnl_note` and `headline` so no one can mistake local DB for whole-wallet.
- Degrade services_summary / priority_alerts when any "live" registry row has stale data or unresolved rows.

## 7. Other Required Work (Bot I Guard, Freshness, Maker-vs-Taker, Profitability)

- Bot I guard: Already present in Session 450; ensure it is the only path and that the systemd unit is updated on the bot container (gated deploy).
- Freshness: Harden the Session 450 logic into a reusable `_freshness_for_live_row(last_fill_at, registry_status)` used everywhere.
- Maker-vs-Taker paper experiments: Formalize the 3 specs already sketched (FV maker continuation, G high-tail to n=50, I persistence to 50/cell) with exact gates and test plan. No code that enables live.
- Profitability roadmap: Produce a canonical table (D live first, then paper candidates with maker lift, accounting-blocked last) and wire it into reports/dashboard where appropriate.

## 8. Test Strategy

- Unit: Classifier logic with 100% coverage using fixtures (sample Data API JSON + synthetic DB rows for owned/unowned/stale cases).
- Integration: End-to-end dry-run run against a test DB snapshot; assert report structure and numbers.
- Dashboard: Snapshot tests or contract tests for the new `accounting` and `freshness` fields in `/api/overview`.
- Safety: Explicit test that the backfill script refuses --execute without confirmation and never touches CLOB.
- Run: `uv run pytest tests/test_wallet_data_api_backfill.py -q` and full relevant suite.

## 9. Safety Gates (Non-Negotiable)

- All wallet code defaults to `--dry-run` / read-only.
- No CLOB client instantiation in the backfill path.
- Registry check before any action on paused bots.
- Explicit "this is a dry-run report only" banners in all output and dashboard.
- No changes to any `polymarket-*-live*.service` files or timers except the reporting guard.
- the bot container changes only via prepared deploy commands (never executed in the overnight run).

## 10. Rollback Plan

- Git revert the commit(s) containing the new script + schema + dashboard changes.
- `DROP TABLE IF EXISTS wallet_reconciliations;` (if created).
- Disable any new timer.
- Restore previous dashboard code on the bot container.
- All changes are additive or behind feature flags/dry-run defaults, so rollback is low-risk.

## 11. Acceptance Checklist (see separate file)

See `docs/GROK_OVERNIGHT_ACCEPTANCE_CRITERIA_2026-05-18.md`.

## 12. Effort & Autonomy Notes for /implement

This spec is designed for 4–8 hours of focused autonomous work on safe local + read-only the bot container tasks. The implementer must stop at any hard gate and document the exact command the operator must run next. Use the companion checklist and acceptance files.

**Do not** begin any write-path or the bot container deployment without explicit operator sign-off after reviewing the dry-run report.

---

*This spec is self-contained. All context, numbers, and file references are current as of the 2026-05-18 audit and Session 450 partial delivery.*