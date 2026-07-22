# GROK_OVERNIGHT_ACCEPTANCE_CRITERIA_2026-05-18

These are **hard, non-negotiable** acceptance criteria. The overnight implementation is considered complete only when every item below is either satisfied or explicitly marked "GATED – operator command required" with the exact command.

## Universal Safety Gates (Must Hold at All Times)

- [ ] No live orders were placed during the entire run (CLOB client was never instantiated for any trading path).
- [ ] No wallet funds were moved, wrapped, redeemed, or transferred (no `wrap_usdce_to_pusd.py --execute`, no redeem scripts with live flags).
- [ ] No live trading services were started, stopped, enabled, disabled, or had their unit files modified (`polymarket-bot-d-*.service`, FV live makers, Bot I live, etc. remain untouched except for the reporting guard already present).
- [ ] No caps, bankroll limits, or treasury paths were changed.
- [ ] No production data was deleted or overwritten.
- [ ] All wallet-related code defaults to `--dry-run` or read-only mode. Any `--execute` path requires an explicit extra confirmation step that was never triggered in this run.

## OQ-123 Wallet Reconciliation (Core Deliverable)

- [ ] A working dry-run `wallet_data_api_backfill.py` (or evolution of the Session 450 `wallet_reconcile_dryrun.py`) exists that:
  - Pulls positions and trades from the public Data API for the hot wallet since 2026-05-16.
  - Correctly queries both `main.db` and `persistence_live.db`.
  - Classifies every row as owned by a known bot, unowned/manual, rebate, or reconciliation-only.
  - Produces the exact report required by OQ-123 acceptance criteria 1–3 and 5 (per-bot wallet P&L, list of unowned positions/trades, gaps).
- [ ] The script was executed in dry-run mode at least once against real the bot container data (or a faithful snapshot) and the output is captured in the verification log.
- [ ] A `wallet_reconciliations` table (or equivalent) schema proposal + Alembic migration skeleton exists (write path remains gated).
- [ ] Dashboard `/api/overview` now contains explicit fields that clearly label whether each P&L/exposure value is:
  - "local bot-ledger only"
  - "wallet-reconciled"
  - "unresolved / pending OQ-123"
- [ ] Bot I daily-report unit no longer enters "failed" state when `bot_i_persistence_live` registry status is "paused" (guard is robust and tested).

## Dashboard & Freshness

- [ ] Every live registry row with `last_fill_at` older than 7 days is visibly marked degraded/stale in the overview and priority alerts (G prime live example must trigger).
- [ ] The top-level `accounting` block in the overview is present and accurate on the current the bot container dashboard after a safe deploy of the runtime_queries changes.

## Maker-vs-Taker & Profitability

- [ ] `docs/maker-paper-experiments-2026-05-18.md` contains the three concrete paper-only experiment specs with all required fields (bot_id, universe, maker entry rule, fill realism, reward eligibility, metrics/gates, kill gates, test plan).
- [ ] A profitability ranking table using the exact verified 2026-05-18 live numbers (D live +31.06/11.07%, etc.) is present and cross-referenced from the experiments doc and the main SPEC.

## Tests & Code Quality

- [ ] New test file `tests/test_wallet_data_api_backfill.py` exists with ≥80% coverage on the classifier and reporter (unit + fixture-based integration).
- [ ] All new and modified Python files pass `uv run py_compile`, `uv run ruff check --select=E,F`, and the relevant pytest modules.
- [ ] No new live-risk paths were introduced (confirmed by static grep for CLOB instantiation in the new backfill module).

## Documentation & Traceability

- [ ] OQ-123 in `docs/open-questions.md` has an updated "Current state" and "Next" section referencing the delivered artifacts.
- [ ] A new ADR (182 or next number) exists in `docs/decisions-log.md` recording the decision to build the dry-run-first wallet backfill job.
- [ ] `docs/active-operating-model-2026-05-02.md` and the project closeout report have status updates.
- [ ] `MEMORY.md` and `CHANGELOG.md` have accurate Session 450 entries.
- [ ] The final "Overnight Implementation Report" artifact exists in `docs/` and lists every file touched, test results, live evidence snapshots, and the exact list of remaining gated operator commands.

## Verification Evidence (must be captured)

- [ ] Read-only the bot container service list (only Bot D family active).
- [ ] Read-only `curl /api/overview` snapshot showing the new accounting/freshness fields (or the code that would produce them).
- [ ] Dry-run backfill report JSON from real data (or the command the operator must run to generate it).
- [ ] Full pytest output for the new test module.
- [ ] Git diff summary of all changes (must be purely additive or behind dry-run defaults).

**Any criterion not met must be listed at the end of the final report with the precise reason and the exact gated command required to resolve it.**

---

**Definition of Done for the Overnight Run**  
The run is successful when the implementer can truthfully say "All non-gated criteria above are green, all gated items have exact one-line commands documented, and no hard safety gate was violated." The operator will then decide on deployment.