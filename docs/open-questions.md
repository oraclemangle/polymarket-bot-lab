# Open Questions

**Last updated:** 2026-07-21 — Session 469 (open-source retirement kickoff): added OQ-134 (Bot B scorer path rewrite-vs-remove), OQ-135 (public repo name + bots/→strategies/ rename), OQ-136 (CHANGELOG full-vs-condensed in export), OQ-137 (little-rocky agents clone remove-vs-attribute) from the grok fan-out reports in `docs/open-source-retirement/grok/`. Note re OQ-132: gemini CLI is being disbanded; replacement is `agy` with gemini flash 3.6. No OQ closed; no live paths. See ADR-195..197. Prior Session 468 text follows for history.

**Prior:** 2026-07-20 — Session 468 (full reassessment write-up): added OQ-130 (fee-rate primary-source verification via VPN), OQ-131 (C3 fill-conditioned autopsy ownership), OQ-132 (Gemini CLI Antigravity migration), OQ-133 (canary.db ~57–58G retention on the local workstation). No OQ closed; no live paths. See `docs/reports/full-reassessment-2026-07.md`, ADR-191..194. Prior 2026-06-09 text follows for history.

**Prior:** 2026-06-09 — Session 467 (Claude Fable 5, creative edge mining): added OQ-127 (sports mid-band NO fade WANGZJ validation), OQ-128 (elite-human cheap-tail co-sign filter), OQ-129 (universe calibration tape harvest) from `docs/reports/creative-edge-mining-2026-06-09.md`. No OQ closed; no live paths. Prior 2026-06-07 text follows for history.

**Prior:** 2026-06-07 — Session 466 (Grok Build): P0 OQ-053: verified S465/ADR-188 guard+health+offload (code pins + VPS empirical active/fresh/0 failed/93% root this run + subagent /tmp/storage-verify... + local tests/sims pass; the bot container ssh timeout noted; untracked recovery files staged; OQ remains open per ADR-188 emergency note). P1 OQ-123: backfill/reconcile tooling + dry runs confirmed (dry default, classify vs main+persistence, public API, report shape; net reset 0s + fixture; gaps: no full dashboard accounting obj, heuristic bot map, unowned review needed on host; OQ-124/125 cross noted). P3 OQ-109: 31 ghost candidates /17 archived (sample bot-a* etc in systemd/); OQ-100/ Bot D gates (067/122/086/097) + OQ-125 no low-risk change this pass. New ADR-189. No OQ closed. All dry/read-only, no live paths. (See CHANGELOG 466 + decisions ADR-189 for cmds/outputs/pins.) Prior 2026-05-26 text follows for history.

Each question has a category, owner, and unlock condition.

Categories:
- **Blocking** — build cannot proceed without answer
- **Decision-required** — needs the operator's input (not researchable)
- **Research-required** — Claude Code can resolve next session
- **Live-probe candidate** — may draft a tiny capped live packet under
  ADR-163; still needs a new ADR and explicit the operator approval before trading
- **Scale-blocking** — a tiny live probe may run, but scaling or production
  claims are blocked until the gate clears
- **Deferred** — real but not needed now

Owners:
- **the operator** — only the user can answer
- **Claude** — next-session Claude Code can research and answer
- **Advisor** — requires external professional input
- **Empirical** — resolves via live system behaviour (paper or dry-run)

---

## Quick Index — Active Open Questions

_89 active, 27 resolved (in archive section), as of 2026-07-20 (added OQ-130/131/132/133 from full reassessment Session 468)._

### Bot D (weather)
- **[OQ-010](#oq-010-polymarket-weather-market-volume-claude)** — Polymarket weather-market volume
- **[OQ-028](#oq-028-widen-main-ingest-to-capture-weather-markets-claude)** — Widen main ingest to capture weather markets
- **[OQ-052](#oq-052-bot-d-live-exit-integrity-before-any-live-capital-proposal-codex)** — Bot D live-exit integrity before any live-capital proposal
- **[OQ-058](#oq-058-bot-d-remaining-settlement-source-audit-nbm-shadow-input-claude)** — Bot D remaining settlement-source audit + NBM shadow input
- **[OQ-067](#oq-067-bot-d-tiny-live-transfer-proof-and-scale-decision-empirical)** — Bot D tiny-live transfer proof and scale decision
- **[OQ-069](#oq-069-bot-d-tiny-live-loosened-entry-collection-review-empirical)** — Bot D tiny-live loosened entry collection review
- **[OQ-071](#oq-071-bot-d-final-sourcewunderground-lag-poller-claude)** — Bot D final-source/Wunderground lag poller
- **[OQ-073](#oq-073-bot-d-noaa-nbm-transfer-review-empirical)** — Bot D NOAA NBM transfer review
- **[OQ-074](#oq-074-bot-d-cross-model-dispersion-revisit-on-resolved-position-evidence-empirical)** — Bot D cross-model dispersion: revisit on resolved-position evidence
- **[OQ-075](#oq-075-bot-d-gribstream-and-99c-take-profit-review-empirical)** — Bot D GribStream and 99c take-profit review
- **[OQ-077](#oq-077-bot-d-nws-outlier-api-agreement-probe-review-empirical)** — Bot D NWS-outlier API-agreement probe review
- **[OQ-086](#oq-086-bot-d-spike-forward-validation-gate-empirical-operator)** — Bot D-Spike forward-validation gate
- **[OQ-093](#oq-093-bot-d-emosngr-shadow-calibration-benchmark-claude)** — Bot D EMOS/NGR shadow calibration benchmark
- **[OQ-096](#oq-096-bot-d-forecast-entry-payload-schema-gap-blocking-phase-1-emos-claude)** — Bot D forecast-entry payload schema gap blocking Phase 1 EMOS
- **[OQ-097](#oq-097-bot-d-spike-short-forward-validation-gate-empirical-operator)** — Bot D-Spike-Short forward-validation gate
- **[OQ-103](#oq-103-bot-d-polymarket-settlement-roundingfloor-rule-verification-claudeempirical)** — Bot D Polymarket settlement rounding/floor rule verification
- **[OQ-104](#oq-104-bot-d-tomorrowio-shadow-source-transfer-review-empirical)** — Bot D Tomorrow.io shadow-source transfer review
- **[OQ-110](#oq-110-expand-bot-d-station-divergence-sample-before-edge-conclusion-claude)** — Expand Bot D station divergence sample before edge conclusion
- **[OQ-112](#oq-112-bot-d-station-lock-paper-forward-proof-empirical)** — Bot D Station Lock paper forward proof
- **[OQ-116](#oq-116-bot-d-maker-live-probe-first-evidence-gate-empirical)** — Bot D maker live probe first evidence gate
- **[OQ-122](#oq-122-bot-d-ensemble-ladder-paper-basket-proof-empirical)** — Bot D Ensemble Ladder paper basket proof

### Bot H (maker-flow)
- **[OQ-100](#oq-100-bot-h-maker-v2-phase-2-build-readiness-after-recorder-burn-in-empirical-operator)** — Bot H Maker V2 Phase 2 build readiness after recorder burn-in

### Wallet-tag features
- **[OQ-099](#oq-099-wallet-tag-forward-validation-gate-before-any-bot-feature-plumbing-claude-empirical)** — Wallet-tag forward-validation gate before any bot-feature plumbing
- **[OQ-101](#oq-101-non-whale-wallet-copy-trade-feasibility-on-5m15m-markets-claude-operator)** — Non-whale wallet copy-trade feasibility on 5m/15m markets
- **[OQ-115](#oq-115-strict-settlement-backfill-bias-check-for-wallet-tag-sports-cohort-empirical)** — Strict settlement backfill bias check for wallet-tag sports cohort
- **[OQ-126](#oq-126-wallet-tag-elite-cap-paper-transfer-gate-empirical)** — Wallet-Tag Elite Cap Paper transfer gate
- **[OQ-128](#oq-128-elite-human-cheap-tail-co-sign-filter-validation-claude-empirical)** — Elite-human cheap-tail co-sign filter validation

### New edge research (2026-06-09 creative mining)
- **[OQ-127](#oq-127-sports-mid-band-no-fade-wangzj-historical-validation-claude)** — Sports mid-band NO fade — WANGZJ historical validation
- **[OQ-129](#oq-129-universe-calibration-tape-harvest-claude)** — Universe calibration tape harvest (daily resolved-market + pre-close price snapshots)
- **[OQ-130](#oq-130-fee-rate-primary-source-verification-via-vpn-claude-operator)** — Fee-rate primary-source verification via VPN
- **[OQ-131](#oq-131-c3-fill-conditioned-autopsy-ownership-claude-empirical)** — C3 fill-conditioned autopsy ownership
- **[OQ-132](#oq-132-gemini-cli-broken-antigravity-migration-operator)** — Gemini CLI broken (Antigravity migration)
- **[OQ-133](#oq-133-canarydb-5758g-retention-policy-on-the-local-workstation-operatorclaude)** — canary.db ~57–58G retention policy on the local workstation

### Bot G (longshot)
- **[OQ-043](#oq-043-bot-g-fill-path-investigation-recommended-fixes-claude)** — Bot G fill-path investigation + recommended fixes
- **[OQ-044](#oq-044-bot-g-paper-orders-never-convert-to-fills-recorder-driven-fill-path-missing-claude)** — Bot G paper orders never convert to fills (recorder-driven fill path missing)
- **[OQ-051](#oq-051-bot-g-split-cohort-ev-proof-before-any-tuning-or-live-argument-claude)** — Bot G split-cohort EV proof before any tuning or live argument
- **[OQ-063](#oq-063-bot-g-post-live-tiny-probe-proof-and-scale-decision-empirical)** — Bot G post-live tiny-probe proof and scale decision
- **[OQ-066](#oq-066-bot-g-xrpdoge-live-universe-proof-empirical)** — Bot G XRP/DOGE live-universe proof
- **[OQ-068](#oq-068-bot-g-crypto-recorder-replay-grid-for-parameter-tuning-empirical)** — Bot G crypto recorder replay grid for parameter tuning
- **[OQ-070](#oq-070-bot-g-live-on-chain-redemption-automation-claude-operator)** — Bot G live on-chain redemption automation

### Infrastructure / cross-cutting
- **[OQ-123](#oq-123-wallet-data-api-backfill-and-cross-db-ownership-reconciliation-claude)** — Wallet Data API backfill and cross-DB ownership reconciliation
- **[OQ-124](#oq-124-live-fleet-residual-exposure-closeout-and-restart-gate-claude-operator)** — Live fleet residual exposure closeout and restart gate
- **[OQ-125](#oq-125-quantstats-orphan-sell-fee-accounting-and-canonical-total-parity-on-real-ledgers-groknoel)** — QuantStats orphan-sell fee accounting and canonical-total parity on real ledgers
- **[OQ-108](#oq-108-vpn-enforcement-policy-vs-code-gap-noelclaude)** — VPN enforcement policy vs code gap
- **[OQ-109](#oq-109-ghost-systemd-service-files-for-archived-bots-claude)** — Ghost systemd service files for archived bots

### Crypto fair-value
- **[OQ-079](#oq-079-becker-dataset-crypto-fair-value-validation-reports-claude)** — Becker dataset crypto fair-value validation reports
- **[OQ-117](#oq-117-crypto-maker-shadow-promotion-gate-and-adr-number-reconciliation-empirical--operator)** — Crypto maker-shadow promotion gate and ADR number reconciliation
- **[OQ-118](#oq-118-cell-c-borderline-maker-probe-exchange-minimum-cap-decision-operator)** — Cell C borderline maker probe exchange-minimum cap decision

### Bot J (near-resolution wallet)
- **[OQ-113](#oq-113-bot-j-audit-remediation-gate-claude--empirical)** — Bot J audit-remediation gate (P0b/P1/P2/P3 from 2026-05-11 audit)

### Bot K (sports market-open taker)
- **[OQ-114](#oq-114-bot-k-near-term-forward-sample-gate-empirical)** — Bot K near-term forward sample gate before quoting Becker +506% as forward expectation

### Bot B (scorer)
- **[OQ-049](#oq-049-bot-b-scorer-health-and-halted-sweep-policy-claude)** — Bot B scorer health and halted-sweep policy
- **[OQ-060](#oq-060-bot-b-public-spin-off-boundary-operator-claude)** — Bot B public spin-off boundary

### Bot C (Pyth)
- **[OQ-017](#oq-017-bot-c-hermes-mapping-fallback-readiness-claude)** — Bot C Hermes mapping + fallback readiness

### Bot E (recorder)
- **[OQ-038](#oq-038-method-1-ta-herding-fade-reversion-check-folded-into-bot-e-poc-claude)** — Method 1 (TA-herding fade) reversion check folded into Bot E POC
- **[OQ-046](#oq-046-bot-e-recorder-wss-subscription-gap-for-near-resolution-markets-claude)** — Bot E recorder WSS subscription gap for near-resolution markets
- **[OQ-053](#oq-053-recorder-storage-retention-and-integrity-after-disk-full-recovery-codex)** — Recorder storage, retention, and integrity after disk-full recovery
- **[OQ-056](#oq-056-recorder-write_queue-saturation-under-sustained-pm-load-claude)** — Recorder write_queue saturation under sustained PM load
- **[OQ-072](#oq-072-revisit-5m15m-crypto-strategy-validation-on-full-recorder-tape-claude-urgent)** — Revisit 5m/15m crypto strategy validation on full recorder tape (Claude) [URGENT]

### Bot F (sensor)
- **[OQ-033](#oq-033-bot-f-hunter-n-threshold-not-binding-on-top-n-rankings-claude)** — Bot F Hunter N-threshold not binding on top-N rankings
- **[OQ-050](#oq-050-bot-f-wallet-flow-cohort-policy-before-allowlist-expansion-operator-claude)** — Bot F wallet-flow cohort policy before allowlist expansion

### Venues / cross-venue
- **[OQ-065](#oq-065-kalshi-uk-eligibility-and-venue-add-decision-operator-kalshi)** — Kalshi UK eligibility and venue-add decision
- **[OQ-087](#oq-087-helsinkibetfair-london-latency-feasibility-for-in-play-execution-claudeempirical)** — Helsinki↔Betfair London latency feasibility for in-play execution
- **[OQ-088](#oq-088-betfair-premium-charge-accrual-timeline-at-5k-50k-operator-scale-decision-required)** — Betfair Premium Charge accrual timeline at $5k-$50k operator scale
- **[OQ-089](#oq-089-insight-prediction-order-book-depth-distribution-claude)** — Insight Prediction order-book depth distribution
- **[OQ-090](#oq-090-pinnacle-uk-retail-accessibility-in-2026-claude)** — Pinnacle UK retail accessibility in 2026

### Infra / ops
- **[OQ-005](#oq-005-treasury-wallet-funding-mechanics-operator-deferred-by-operator-2026-04-15-operator-will-research)** — Treasury wallet funding mechanics (the operator)  [DEFERRED by the operator 2026-04-15 — the operator will research] (deferred)
- **[OQ-014](#oq-014-hardware-wallet-signing-path)** — Hardware wallet signing path
- **[OQ-057](#oq-057-rotate-telegram-bot-token-exposed-in-historical-journald-logs-operator)** — Rotate Telegram bot token exposed in historical journald logs
- **[OQ-080](#oq-080-vps-split-hosting-pilot-for-live-runtimes-operator-claude)** — VPS split-hosting pilot for live runtimes
- **[OQ-091](#oq-091-gcp-project-divine-beach-486012-p4-billing-disabled-claudenoel)** — GCP project `divine-beach-486012-p4` billing disabled
- **[OQ-102](#oq-102-vps-to-the-homelab-hypervisor-migration-and-recorder-backup-approval-operator-codex)** — VPS-to-the homelab hypervisor migration and recorder backup approval
- **[OQ-119](#oq-119-dashboard-live-accounting-and-per-bot-roi-truth-surface-codex)** — Dashboard live accounting and per-bot ROI truth surface

### Tax / posture
- **[OQ-004](#oq-004-hmrc-advisor-engagement-operator-advisor-deferred-by-operator-2026-04-15)** — HMRC advisor engagement (the operator + Advisor)  [DEFERRED by the operator 2026-04-15] (deferred)

### Other
- **[OQ-009](#oq-009-minimum-order-size-per-market-empirical)** — Minimum order size per market
- **[OQ-011](#oq-011-websocket-connection-limits-claude)** — WebSocket connection limits
- **[OQ-012](#oq-012-nonce-order-id-reuse-policy-claude)** — Nonce / order-ID reuse policy
- **[OQ-013](#oq-013-postgres-migration-from-sqlite)** — Postgres migration from SQLite
- **[OQ-015](#oq-015-v2-strategies-timesfm-crypto-copy-trading-etc)** — v2 strategies
- **[OQ-016](#oq-016-polymarket-v2-migration-status-claude)** — Polymarket V2 migration status
- **[OQ-029](#oq-029-reconcile-condition_id-id-space-mismatch-between-bots-claude)** — Reconcile condition_id ID-space mismatch between bots
- **[OQ-030](#oq-030-reconcile-bot-as-missing-buy-legs-from-polymarket-ctf-split-sells-claude)** — Reconcile Bot A's missing BUY legs from Polymarket CTF split-sells
- **[OQ-031](#oq-031-price_collectorpy-one-price-per-market-schema-flaw-claude)** — `price_collector.py` one-price-per-market schema flaw
- **[OQ-034](#oq-034-polymarket-v2-migration-live-money-graduation-gate)** — Polymarket V2 migration / live-money graduation gate
- **[OQ-039](#oq-039-14-day-reward-cascade-passive-measurement-window-before-rewards_monitor-build-claude)** — 14-day reward-cascade passive measurement window before rewards_monitor build
- **[OQ-040](#oq-040-category-level-historical-uma-dispute-rate-data-pipeline-claude)** — Category-level historical UMA dispute-rate data pipeline
- **[OQ-041](#oq-041-fleet-review-operator-decision-bundle-operator-extended-2026-04-22-after-glm-51-review)** — Fleet-review operator-decision bundle (the operator) — EXTENDED 2026-04-22 after GLM-5.1 review
- **[OQ-042](#oq-042-glm-51-deferred-fix-bundle-claude-after-oq-041-resolves)** — GLM-5.1 deferred-fix bundle
- **[OQ-045](#oq-045-permanent-env-relocation-outside-project-tree-operator-claude)** — Permanent `.env` relocation outside project tree
- **[OQ-047](#oq-047-tactical-review-execution-bundle-for-bots-cdfg-claude)** — Tactical review execution bundle for Bots C/D/F/G
- **[OQ-054](#oq-054-halt_flags-rows-carry-stale-unhalt-reason-text-despite-halted1-claude)** — `halt_flags` rows carry stale "unhalt" reason text despite `halted=1`
- **[OQ-059](#oq-059-contrarian-crowd-flow-edge-validation-empirical)** — Contrarian crowd-flow edge validation
- **[OQ-095](#oq-095-fleet-probability-score-decomposition-layer-claude)** — Fleet probability score decomposition layer

---

## Blocking


## Decision-required

### OQ-102 — VPS-to-the homelab hypervisor migration and recorder backup approval (the operator + Codex)

**Category:** Decision-required / infrastructure reliability.
**Owner:** the operator approves migration order and any service moves; Codex can
implement after approval.
**Surfaced by:** 2026-05-10 VPS/the homelab hypervisor role audit and ADR-144.

**Problem:** The VPS is currently running more than latency-dependent live and
paper loops. It also runs Bot H recorder/quote/replay/backfill and wallet
observer workloads that are better suited to the bot container. VPS disk is not critical
today (`57%` used), but the crypto recorder canary DB is already `27.6GB`
on a `75G` root disk and is not safely covered by the existing the homelab hypervisor backup.

**Acceptance criteria:** the operator approves or revises the migration sequence in
an internal role-audit report (not exported):
expand backups first; add disk threshold monitoring; migrate wallet observer;
migrate Bot H recorder/quote/replay/backfill; then decide the controlled
rollover/sharding/maintenance-window backup posture for
`bot_e_recorder_vps_canary.db`. No service move, stop, trading restart, live
order-path change, or wallet-touching service placement change proceeds
without explicit approval.

**Blocks:** Moving Bot H and wallet observer off the VPS; pruning any VPS
recorder data; changing `polymarket-redeem-zero-value-vps.timer` placement;
any automated action at the `80%`/`90%` VPS disk thresholds.

**Progress 2026-05-10:** Operator approved the first migration wave and
ADR-145 executed it. Bot H Maker V2 recorder/quote-paper/backfill/replay and
Wallet Observer/reporting now run on the bot container from verified final VPS snapshots.
The dashboard reads those three inventory lanes from the bot container. OQ-102 remains
open for the large VPS crypto recorder canary, disk-threshold dashboarding,
remaining non-latency report moves, and wallet-touching redemption placement.

**Progress 2026-05-10 Session 308 (post-audit hardening, ADR-146):**

- Stopped backing up the now-frozen VPS copies of `maker_recorder.db` and
  `wallet_observer.db`; archived those copies once to
  `<bulk-storage>/`, then deleted them from
  the VPS data dir.
- Added `scripts/bot-host_pull_backup.py` plus
  `longshot-the bot container-pull-backup.{service,timer}` (daily) so the new
  authoritative the bot container copies of `maker_recorder.db` and `wallet_observer.db`
  are protected by a SQLite-consistent pipeline equivalent to the VPS one.
  Output lands in `<bulk-storage>/ bot container/<run>/`.
- Added a dashboard guard: `query_bot_h` and `query_wallet_observer` now
  surface `data_source_warning` when a the bot container unit is active but the local DB
  is missing, so a misconfigured env doesn't silently flip the source label.
- Captured the `bot_e_recorder_vps_canary.db` rollover/sharding design in
  `docs/bot-e-recorder-vps-canary-rollover-design-2026-05-10.md`. No
  implementation authorized; the recommended sequence is (a) one-off
  maintenance-window full backup of today's state, (b) feature-flagged
  rollover code path, (c) operator-supervised first rollover at `8 GB`.

Disposition plan for the legacy the bot container Wallet Observer DB
(`data/migration_backups/20260510T085720Z-final-move/wallet_observer_legacy_observed_trades.db`):

- It uses the older `observed_trades` schema and was preserved instead of
  merged into the newer `wallet_observed_fills` schema.
- Default disposition: keep until **2026-08-10** (90 days), then operator
  reviews. If the newer the bot container `wallet_observer.db` plus the
  `<bulk-storage>/ bot container/` retention has been stable for 90 days, the
  legacy file may be deleted with operator approval. If a feature ever
  needs the older schema, build an explicit transform under
  `scripts/research/wallet_observer_legacy_transform.py` rather than
  mutating the preserved file in place.
- Until then, the file lives under `migration_backups/` with no automatic
  cleanup and is intentionally outside the daily the bot container backup pipeline.

Still open under OQ-102 after Session 308: `bot_e_recorder_vps_canary.db`
disposition decision, dashboard disk-threshold surfacing (ADR-144 Priority
2), the `polymarket-redeem-zero-value-vps.timer` placement decision, and
moving the remaining non-latency report timers (`bot_g_daily_probe`,
`bot_d_spike_daily_report`) off the VPS.

**Progress 2026-05-14 Session 365 (canary baseline cleanup executed):**

- Completed the one-off baseline backup follow-up for
  `bot_e_recorder_vps_canary.db`. the operator explicitly approved deleting the
  `.retired-2026-05-13` files before the original `18:57 UTC` 24h gate
  because VPS root had reached `91%` used.
- Before deletion, recomputed the retired main DB SHA256 on VPS as
  `8ba6cbabaa98665ccf96a4a7858f74c66443476b6f9d53ca858c5c81559a1f45`,
  matching the the homelab hypervisor archive decompressed SHA256 byte-for-byte.
- Deleted the retired main/WAL/SHM files. Disk space was initially still held
  by two orphaned `/tmp/_bot_l_audit2.py` audit readers; terminated only those
  stale non-systemd readers. No recorder or Bot G systemd unit was restarted.
- VPS root recovered from `91%` used (`6.6G` free) to `23%` used (`56G`
  free). Fresh canary DB health remained clean after cleanup:
  `quick_check=ok`, `gaps=0`, `pm_events=1,789,331`,
  `cex_trades=2,797,007`, `heartbeats=11,978`, `markets=1,422`.

Still open under OQ-102 after Session 365: bounded hot-window rollover /
backup posture for the VPS crypto recorder, dashboard disk-threshold
surfacing, `polymarket-redeem-zero-value-vps.timer` placement, and migration
of remaining non-latency report timers off the VPS.

### OQ-086 — Bot D-Spike forward-validation gate (Empirical + the operator)

**Category:** Live-probe candidate / scale-blocking validation.
**Owner:** Empirical resolves the sample; the operator decides any live promotion.
**Surfaced by:** 2026-05-07 Strategy E paper-lane build and ADR-125.

**Problem:** Strategy E's historical WANGZJ slice is positive, but the edge is
outlier-dependent and the first live-market implementation is a narrow
paper-only VPS lane. Forward validation must prove that real Gamma/CLOB
availability, city parsing, book depth, fees, and resolution timing preserve
the historical `6h-12h`, positive-EV-city edge. ADR-127 widened the paper
validation-plus entry band to `1c-15c` after first-day capacity proved sparse.

**Acceptance criteria:** Run `bot_d_spike` paper-only until `90` days or `200`
closed positions, whichever comes first. Keep the hard `6h-12h` window,
whitelist/blacklist, `1c-15c` entry band, hold-to-resolution exit, `$200`
deployed cap, and no live CLOB writes. At review time, archive or continue
only if forward ROI is above `+5%`, there are zero rule violations, and hit
rate is interpreted as a diagnostic versus the historical `3.6%` baseline
rather than an automatic `4%` kill gate. Any live promotion requires a new ADR
and explicit the operator approval.

**Fast-probe posture 2026-05-14 (ADR-163):** The `90` day / `200` close gate
now blocks scale and production claims, not a deliberately tiny live probe.
Codex may draft a capped Bot D-Spike live-probe packet if the packet states
max loss, caps, kill switch, rollback, and monitoring. Actual trading still
requires a new ADR and explicit the operator approval.

**Readiness progress 2026-05-14 (ADR-164):** Added the repo-local Bot D-Spike
tiny live-probe spec and guard tests: 6-12h TTR, whitelist-only 1c-15c
`BUY_YES`, `$2` max order, `$10` daily gross, `$20` open exposure, `10` max
concurrent positions, and kill switches for rule violation, `5` consecutive
resolved losses, realised P&L `<= -$8`, CLOB/auth/reconcile fault, or overlap
with other Bot D live exposure. Existing paper defaults were tightened to
mirror the proposed envelope. No live executor was enabled; actual trading
still requires a later activation ADR and the operator approval.

**Approval progress 2026-05-14 (ADR-165):** the operator approved the tiny live probe
and requested dashboard live status. The registry/dashboard now marks
`bot_d_spike` as a live probe. OQ-086 remains open as a scale-blocking gate:
the `90` day / `200` close forward-validation target is no longer an
activation blocker, but it still blocks scaling or durable edge claims.

**Progress 2026-05-15 aggressive review (ADR-170):** Current VPS runtime is
still the paper Bot D-Spike service, not an operational live order-placement
service. The latest daily report shows `45` closed positions, `2` wins,
`+$25.30` realised paper P&L, `+26.92%` ROI, and `2` open positions with
`$4.00` cost. ADR-170 keeps OQ-086 as a scale gate and recommends separate
operational approval to activate the already-approved `$2` max-order /
`$10` daily-gross / `$20` open-exposure live probe.

**Progress 2026-05-15 deployment (ADR-172):** the operator approved Bot D-Spike live
activation. The live order/reconcile path was implemented and deployed on the
VPS as `polymarket-bot-d-spike-live-probe-vps.service`, replacing the paper
service. The live-probe service is active under the approved `$2` max order /
`$10` daily gross / `$20` open exposure caps. First confirmed live scan logged
`placed=0`, `reconciled=0`, `mode=live`. OQ-086 remains open as a scale gate,
not an activation gate.

**Progress 2026-05-08 Strategy E2 check:** Ran the existing Strategy E
Murphy/bootstrap script on the larger `12h-24h` weather cheap-YES slice as
`docs/reports/strategy-e2-weather-cheap-yes-2026-05-08.md`. Result: **FAIL**.
The slice produced `13,578` WANGZJ trades, `666` wins, `4.90%` hit rate, and
`-$3,184.30` total P&L after the Strategy E fee model. Murphy resolution was
`0.00003` versus the `>0.001` gate and trading-day bootstrap ROI was
`-24.83%` with 95% CI `[-30.48%, +34.19%]`. Do not add a Strategy E2 paper
lane from this slice.

**Progress 2026-05-09 full Bot D audit:** VPS service is active and the lane
is collecting sample. Current forward state: `12` orders, `17` trade rows,
`5` closed matched groups, `0` wins, `-$9.99966` realised paper P&L, `7`
open positions, `$13.99954` open cost. Entry audit shows the intended
validation-plus shape: `6h-12h` TTR (`7.1542-11.9995h` observed), `1c-15c`
entry band, `$2` position size, and whitelist cities only (`Shanghai`,
`Hong Kong`, `Seoul`, `Ankara`, `New York`). This is `5/200` closes, so the
lane is not decision-grade and remains paper-only. Local dashboard bridge
code now computes this realised P&L, but VPS deploy/regeneration is pending
while SSH is unreachable.

**Progress 2026-05-09 top-3 follow-up:** VPS status bridge patch was deployed
through PVE as a jump host and `data/reports/vps_node/latest.json` was
regenerated. the bot container `/api/bot-d` now reports this lane correctly: `12`
orders, `17` trade rows, `5` closed matched groups, `0` wins, `-$10.00`
realised paper P&L, `7` open positions, and `$14.00` open cost. Still
`5/200`; keep paper-only.

### OQ-097 — Bot D-Spike-Short forward-validation gate (Empirical + the operator)

**Category:** Live-probe candidate / scale-blocking validation.
**Owner:** Empirical resolves the sample; the operator decides any live promotion.
**Surfaced by:** 2026-05-08 Session 246 build of `bot_d_spike_short` per ADR-133.

**Problem:** Strategy E2 short-TTR (`<6h × weather × cheap-YES × city
whitelist`) passed the same outlier-robustness check as Strategy E baseline
in the 2026-05-08 WANGZJ V2 re-validation (`40,496 trades, +36.1% as-is ROI,
+11.1% top-5 robust`). The new paper lane `polymarket-bot-d-spike-short-vps.service`
is running on `the-vps`. Forward validation must prove the
historical edge holds when the entries are actually placed, books are real,
fees are real, and outlier markets are not concentrated in the recent
sample. The `<6h` slice has the same top-25-outlier dependence as Strategy
E baseline (excl-top-25 ROI is `-29.7%`) so genuinely outlier-free forward
performance is not guaranteed.

**Acceptance criteria:** Run `bot_d_spike_short` paper-only until `90` days
or `200` closed positions, whichever comes first. Keep the hard `[0, 6)h`
window, the `bot_d_spike` city whitelist/blacklist, `1c-15c` entry band
(matching the parent lane's tuning), hold-to-resolution exit, `$200`
deployed cap, `30` daily entries cap, and no live CLOB writes. At review
time, archive or continue only if forward ROI is above `+5%`, hit rate is
above `4%`, top-5-robust ROI on closed positions is positive, and there are
zero rule violations (especially: zero co-position overlaps with the
`bot_d_spike` 6-12h lane, even though the disjoint TTR windows make this
expected). Any live promotion requires a new ADR and explicit the operator approval.

**Fast-probe posture 2026-05-14 (ADR-163):** The `90` day / `200` close gate
now blocks scale and production claims, not a deliberately tiny live probe.
Given the negative early forward sample, any live-probe packet must be framed
as paid outlier hunting with a very small max loss and a hard stop after the
first defined loss or rule violation. Actual trading still requires a new ADR
and explicit the operator approval.

**Progress:** Lane deployed 2026-05-08 21:01 UTC. First scan logged
`raw=1400 parsed=14 eligible=0 placed=0` (steady-state empty scan).
Awaiting forward signal.

**Progress 2026-05-08 Session 258 audit:** the bot container dashboard now reports the
short lane with the correct `1c-15c` entry band and `30` daily-entry cap.
However, `/api/bot-d` falls back to the bot container-local empty metrics because the VPS
status bridge does not expose `bot_d_spike_short`. The paper service may be
running on the VPS, but this audit could not verify it directly because
Tailscale SSH to `192.0.2.1` timed out. Next action: add
`polymarket-bot-d-spike-short-vps.service` and its DB/report summary to
`scripts/vps_node_status.py`, then re-check first entries/closes from the bot container.

**Progress 2026-05-09 full Bot D audit:** VPS service is reachable and
active. Current forward state: `6` orders, `9` trade rows, `3` closed
matched groups, `0` wins, `-$6.00001` realised paper P&L, `3` open
positions, `$5.99992` open cost. Entries obey the intended short window
(`1.7855-5.5879h` observed) and `1c-15c` band, but the sample is only
`3/200` closes and is too concentrated in `London`/`Madrid` to judge.
Dashboard API now exposes the VPS block; a follow-up patch also maps the VPS
metrics into the nested `simple` block so the Bot D tab no longer shows
the bot container-local count/open-position zeros for this lane. The VPS status bridge
P&L calculation was patched locally too, but deploy/regeneration is pending
because SSH to `vps-host` timed out during retry; realised P&L can
remain stale-zero in the dashboard until that bridge file lands.

**Progress 2026-05-09 top-3 follow-up:** VPS status bridge patch was deployed
through PVE as a jump host and `data/reports/vps_node/latest.json` was
regenerated. the bot container `/api/bot-d` now reports this lane correctly: `6` orders,
`10` trade rows, `4` closed matched groups, `0` wins, `-$8.00` realised paper
P&L, `2` open positions, and `$4.00` open cost. Still `4/200`; keep
paper-only.

### OQ-098 — Track 1 maker-flow cell-filtered respec on Track 3 success (Claude) [RESOLVED 2026-05-08]

**Category:** Research-required / strategy spec.
**Owner:** Claude can draft once the trigger condition fires.
**Surfaced by:** 2026-05-08 all-tracks synthesis cell-breakdown analysis.

**Problem:** The Track 1 maker-flow simulator (`/tmp/track1_maker_sim.py`
on the bot container) showed `+4.39%` blended net ROI on `1.43M` simulated fills, which
the operator judged too thin for a `4-6 session` build. However, the cell
breakdown showed three high-ROI sub-slices that together would be a much
tighter spec:

| filter | sim fills | sim cost | NET PnL | ROI |
|---|---:|---:|---:|---:|
| Politics 30-40c only | 49,276 | $229K | +$168K | +73.6% |
| Politics 0-10c only | 39,941 | $107K | +$61K | +57.1% |
| Sports 10-20c only | 9,550 | $29K | +$23K | +79.1% |
| **Top-3 cells combined** | **98,767** | **$365K** | **+$252K** | **~+69%** |

At `$5k` cap, a top-3-cell-filtered maker bot would project to `$30-50K/yr`
— competitive with or beating Strategy E2. But the AS-proxy uncertainty
compounds when filtering to thinner cells, the build cost is the same
`4-6 sessions`, and the quote-fill model is still untested live. The ADR
that would unlock this requires lifting the CLAUDE.md `Market-making /
rebate farming bot` kill-list line, which the operator has not yet done.

**Trigger to revisit:** Either of (a) Strategy E or Strategy E2 produces
genuine forward-positive performance, OR (b) Strategy E and Strategy E2
both forward-fail and the project needs a non-correlated edge candidate.
In case (a), the operator may want to diversify by adding Track 1; in case
(b), Track 1's structurally different edge source becomes the natural
backup.

**Acceptance criteria:** Draft a clean spec for `bot_h_maker_v2_filtered`
that quotes only on `politics 0-10c, politics 30-40c, sports 10-20c` cells,
with adverse-selection-loss tracking baked in from day 1, plus an updated
ADR-amendment proposal for CLAUDE.md kill-list. Include realistic fill-rate
sensitivity bands (`5%, 10%, 15%`) and toxicity-weight sensitivity
(`1x, 2x, 4x`).

**Status:** SUPERSEDED 2026-05-08 by ADR-134 + OQ-100. Operator
approved direct build after the robustness probe
(`docs/reports/track1-maker-flow-robustness-probe-2026-05-08.md`)
killed `politics 30-40c` (5-market mirage, excl-top-5 worst combo
`-90.9%`) but vindicated `politics 0-10c` and `sports 10-20c` across
all 5 sensitivity combos. Trigger condition not waited for; build
proceeded straight to ADR-134 with the narrowed top-2 cell scope.

### OQ-100 — Bot H Maker V2 Phase 2 build readiness after recorder burn-in (Empirical + the operator)

**Category:** Live-probe candidate / scale-blocking validation.
**Owner:** Empirical resolves the recorder evidence; the operator decides
Phase 2 build authorisation.
**Surfaced by:** 2026-05-08 Session 253 deploy of `bot_h_maker_v2`
Phase 1 wide CLOB recorder per ADR-134.

**Problem:** ADR-134 authorised a phased Track 1 build:

- **Phase 1 (deployed 2026-05-08 21:40 UTC):** wide CLOB recorder
  capturing politics + sports + awards + crypto markets (1c-50c, volume
  ≥ $1000) into `data/maker_recorder.db`. Running on
  `the-vps` as
  `polymarket-bot-h-maker-v2-recorder-vps.service`. NO quote engine,
  NO paper fills, NO order placement.
- **Phase 2 (gated):** quote engine + paper-fill simulator + AS tracker
  for the top-2 cells (politics 0-10c + sports 10-20c). Requires this
  OQ to resolve before build starts.

The Phase 1 recorder must collect enough forward data to confirm that
the WANGZJ-historical robustness check still holds in real markets
before we commit `3-4` more sessions building the quote engine.

**Acceptance criteria for Phase 2 build authorisation:**

1. Recorder uptime ≥ `95%` over the burn-in window (no silent stalls,
   no DB corruption, no resource exhaustion). Watchdog signal:
   continuous heartbeats every 30s and clean WSS reconnects on
   disconnect.
2. ≥ `30 days` of recorder data OR ≥ `1M pm_events` accumulated, whichever first.
3. `data/maker_recorder.db` size remains under `<10 GB` per the ADR-134
   budget; if approaching the cap, operator decides on rollover.
4. Real-data re-run of the maker-flow simulator on the recorder-derived
   trades in `politics 0-10c` and `sports 10-20c` produces
   excl-top-5 ROI **above +20%** in BOTH cells AND across the
   `5/10/15%` fill-rate × `1×/2×/4×` toxicity-weight sensitivity grid.
   This is the same bar that authorised the build.
5. AS-proxy validation: the 15-min `next_15min_avg_price` toxicity
   label correlates with the actual at-resolution outcome at
   `>0.30` AUC. If AUC < 0.30, the proxy is misspecified and Phase 2
   needs a different AS estimator.
6. Counterfactual cell mix audit: re-run the killed cells (politics
   30-40c, awards 0-10c) on the forward data. If any of them show
   excl-top-5 ROI > +20% on real V2 data, escalate as a separate
   spec-amendment ADR before Phase 2 cell list is finalised.

**Progress 2026-05-08 (Session 253):** Phase 1 deployed 21:40 UTC.
First 60s produced `202` `pm_events` across 9 markets in all 4 target
categories. Awaiting burn-in.

**Progress 2026-05-08 (Session 255):** Two analysis tools shipped to
make the gate check trivial when burn-in completes:

- `scripts/bot_h_maker_v2_recorder_daily_report.py` — recorder health
  snapshot (events by type/category, heartbeat continuity, longest
  gap, disk-budget extrapolation with days-to-cap projection).
- `scripts/research/maker_flow_recorder_replay.py` — re-runs the
  maker-flow simulator on `data/maker_recorder.db`-derived trades
  under the same robustness/sensitivity matrix that authorised
  ADR-134. Direct implementation of acceptance criterion #4. Exits
  non-zero when build is not yet authorised so it can drive a CI gate.

The daily report's first run uncovered a critical bug in
`bots/bot_h_maker_v2/capture.py`: `_make_pm_handler` extracted
`payload["market"]` (which is the condition_id in 0x hex) and stored
it as `asset_id`, leaving condition_id NULL on **95.1% of pm_events**.
Refactored handler now resolves condition_id correctly across all
three Polymarket WSS payload shapes; post-fix 172/172 events in 60s
had non-null condition_id (**100% vs 5% pre-fix**). Pre-fix events
remain in the DB with NULL condition_id but are recoverable from
`payload_json` at analysis time. 33 tests pass on VPS.

**Acceptance criterion #3 (disk budget) escalated and resolved
2026-05-08 (Session 257):** observed disk growth `~720-865 MB/day`
projected the original `90 days` budget to fail in `~14 days`.
Operator approved Plan B + Plan D from the four resolution paths
documented in Session 255. Both deployed.

- Plan B: ADR-134 §5 budget amended **10 GB → 30 GB**. a small EU VPS
  has 43 GB free; sustained `~600-720 MB/day` rate fits with ~50d
  headroom.
- Plan D: write-time filter in `bots/bot_h_maker_v2/capture.py` drops
  `book`/`price_change`/`last_trade_price`/`best_bid_ask` events
  whose `asset_id` is not in `state.token_to_condition`.
  `new_market`/`reconnect`/`disconnect`/`heartbeat` always kept.

**Empirical finding (correction to Session 255 narrative):** Plan D's
filter dropped **0 events** post-deploy over a 90s observation window.

**Progress 2026-05-08 Session 258 audit:** the bot container `/api/overview` sees the VPS
node as healthy and fresh, but the bridge service list omits
`polymarket-bot-h-maker-v2-recorder-vps.service`. Direct VPS SSH from this
host timed out, and the bot container has no local Bot H unit. Treat Bot H recorder as
"claimed deployed, not independently verified by this audit" until the status
bridge exposes service active state, DB bytes, event rate, heartbeat age, and
category coverage.

**Progress 2026-05-09 Session 261 closeout:** the bot container `/api/bot-h` is live and
uses the VPS bridge with `data_source=vps`. The bridge reports
`polymarket-bot-h-maker-v2-recorder-vps.service` active, recorder DB
`177,516,504` bytes, `104,548` lifetime/24h pm_events, `20` active markets,
`153.2` events/min over the last 5m, last event age `0.2s`, heartbeat last
age `1.5s`, and 24h category mix: politics `40,517`, crypto `25,443`, awards
`14,385`, sports `12,890`, unknown `11,313`. OQ-100 remains open because the
Phase 2 gate requires burn-in/replay evidence, not just recorder health.

The Polymarket WSS at this scope only delivers events for subscribed
asset_ids; the prior "95% broadcast pollution" hypothesis was a
LEFT-JOIN artefact from Session 255's pre-condition_id-fix events,
not real pollution. Plan B is the load-bearing fix; Plan D stays as
a safety net for future scope expansion (election surge, playoffs).

Daily report post-fix: **GREEN ✓**, `Days to 30 GB cap: 51.0d`,
100% condition_id resolution rate on new events.

If subscription scope grows substantially and disk growth approaches
the 30 GB cap before 30 days, the next lever is **payload truncation**
(drop `book`-event depth beyond top-5 levels each side, or skip full
`book` events relying on `best_bid_ask` + `price_change`). Tracked
as a future ADR amendment trigger, not blocking Phase 2 gate.

**Progress 2026-05-09 (Session 262):** Three follow-on tools shipped
to make the gate fire automatically when burn-in completes.

- **Resolution backfill** (`bots/bot_h_maker_v2/resolution_backfill.py`
  + `scripts/bot_h_maker_v2_recorder_resolution_backfill.py` +
  `polymarket-bot-h-maker-v2-resolution-backfill-vps.{service,timer}`)
  now runs every 6h. Schema migration via `_ensure_resolution_columns`
  in `bots/bot_h_maker_v2/schema.py` adds four nullable columns
  (`yes_won`, `resolved_at_ms`, `outcome_yes_price`,
  `last_resolution_check_ms`) idempotently. First live run on the
  recorder DB: 20 candidates queried, 18 returned by Gamma, 0
  resolved this pass (markets are forward-looking). Without this,
  the replay simulator returned `INSUFFICIENT_DATA` forever.

- **Daily replay cron** (`scripts/bot_h_maker_v2_recorder_daily_replay.py`
  + `polymarket-bot-h-maker-v2-daily-replay-vps.{service,timer}`)
  runs at 02:00 UTC daily. Wraps the existing replay simulator,
  writes dated archive + `latest.{md,json}` for the dashboard,
  prunes archives older than 90 days. Exit codes 0 (ok or
  insufficient), 1 (gate not passing), 2 (spec amendment needed)
  are SIGNAL not bug — `SuccessExitStatus=0 1 2` so systemd doesn't
  flag them as failures. First live run today: verdict
  `Phase 2 NOT authorised`, 45 taker BUY trades extracted from
  106,571 events, 19 markets indexed, all cells `INSUFFICIENT_DATA`
  (expected pre-resolution).

- **Phase 2 design doc**
  `docs/bot-h-maker-v2-phase-2-design-2026-05-09.md` — spec only,
  no code. Module layout, new tables (`maker_quotes`,
  `maker_paper_fills`, `maker_as_labels`), quote/fill/AS/PnL logic,
  kill triggers. Build estimate down to 4 sessions (from 4-6) once
  gate fires positive.

58 tests pass on VPS (was 37; added 21 across resolution + daily
replay).

**If acceptance fails:** Phase 2 is NOT built; recorder data is
preserved as a research asset. Operator decides whether to disable the
recorder service or keep it running for indefinite future analysis.

**Operator decision 2026-05-09 (Session 286):** Do not use the
`1M pm_events` trigger by itself for Phase 2 authorisation. Wait until
the recorder/replay path has `100` replayable trips before returning
OQ-100 for a build/no-build decision. Phase 1 remains recorder-only:
no quote engine, no paper fills beyond analysis/replay, and no order
placement.

**Operator acceleration 2026-05-09 (Session 302):** Per ADR-143, added an
early `bot_h_maker_v2_quote_paper` paper simulator before OQ-100 clears. It
writes paper quote/fill tables into `data/maker_recorder.db`, uses recorder
prints only, and loads no wallet keys. This is an evidence-collection
acceleration, not Phase 2/live authorisation: the `100` replayable trips plus
target-cell robustness gate remains binding before any live, sizing, or
feature claim.

**Progress 2026-06-07 (Grok Build Session 466):** OQ-100 remains open (no Phase 2 per operating-model/ADR-134/143; P2 this session focused Bot D paper evidence collection). OQ-100 **Live-probe candidate / scale-blocking validation** (owner Empirical + the operator). Cross OQ-100.

**Fast-probe posture 2026-05-14 (ADR-163):** The `100` replayable trips and
target-cell robustness gate now block scale, feature claims, and production
maker trading. They do not block a future tiny-live quote probe packet once
the quote engine exists, provided the packet caps max loss, names quote
inventory limits, kill conditions, rollback, and monitoring. No quote-engine
live order path may be enabled without a new ADR and explicit the operator approval.

### OQ-085 — Bot G seven-day microstructure probe and retirement decision (the operator + Claude) [SUPERSEDED 2026-05-09]

**Category:** Decision-required / live strategy retirement.
**Owner:** the operator decides live halt/retirement; Claude designs and reports the
probe.
**Surfaced by:** 2026-05-07 Bot G multi-model deep analysis.

**Resolution 2026-05-09 (final-evaluation pass):** Superseded by ADR-135
(emergency-pause Bot G Prime Live after live-shaped cohorts fail) and
ADR-136 (resume Bot G Prime Live as `$1` data-gathering micro-probe).
The seven-day probe was never the gating decision; the live-shaped
paper mirror (`bot_g_prime_shadow`) and the live account itself produced
the decisive `1 win / 55 resolved`, `-100%` ex-largest-win evidence
inside the same week. Bot G live continues only as a paper-tier
data-gathering probe at `$1` per entry. Any size, cap, symbol, band,
or lead expansion still requires a separate ADR. Daily probe reporting
remains valuable but is no longer gated by this OQ. See
`docs/reports/archived-and-recorder-final-evaluation-2026-05-09.md` and
ADR-138.

**Problem:** Bot G live is losing money and the research stack now points to a
structural taker-edge failure rather than a temporary bad run. The key
evidence is: live `bot_g_prime_live` at `1/48` resolved wins and `-73.15%`
ROI in the 30-day paper-vs-live diagnostic; same-market paired rows with
paper-only wins but no live-only wins; CEX-agree forward replays at `0/36`
the bot container and `0/31` VPS; no stable causal pre-fill feature in Bot G recorder
microstructure; Becker live-band edge turning negative under `1c` and `2c`
stress; and LightGBM finding outcome calibration but no useful taker edge.
External model critiques (GLM-5.1, Gemini 2.5 Pro, DeepSeek V4 Pro reasoning)
all recommended treating the current taker thesis as failed or near-failed.

**Acceptance criteria:** If the operator wants one more week before halting, run only
the current ADR-136 `$1` fixed-notional live probe with no size/cap/symbol/band/lead
expansion. Collect candidate-level, order-book, CEX-state, fill/no-fill,
latency, timezone, volatility, and news-window metadata. At the end of seven
days, produce a live-realistic bucket report. A positive bucket must have at
least `20` filled live entries, at least `2` wins, positive realised ROI, and
a paper-realistic replay that survives live fill/timeout mechanics. If no such
bucket exists, retire or halt Bot G taker live. If the probe is not run, the
current evidence is already sufficient to recommend halt after the operator approval.

**Blocks:** Any Bot G live size increase beyond `$1`, any cap increase, any
symbol expansion, any band/lead retune, or any claim that paper-main P&L is
decision-grade edge evidence.

**Progress 2026-05-07 operator posture:** the operator chose to keep Bot G live
trading for data gathering; ADR-136 later reduced the fixed live size to `$1`.
No parameter change beyond ADR-136 is authorized. The
candidate watch-list for the seven-day report is: CEX-flat, SOL/SOL-NO,
DOWN-vs-UP, `30s-45s` lead, UTC hour/news window, volatility regime, and
current-band sub-slices (`3.5c-4.5c` vs `4.5c-5.5c`). These are reporting
buckets, not live filters.

**Progress 2026-05-07 daily probe report deployed:** Added read-only
`scripts/bot_g_daily_probe_report.py` plus regression coverage in
`tests/test_bot_g_daily_probe_report.py`. The report groups the live probe by
CEX state, SOL/SOL-NO, DOWN-vs-UP, lead bucket, UTC hour,
session, volatility, macro/news window labels when present, and current-band
sub-slices. Deployed the script and VPS timer templates to
`vps-host` via public SSH after Tailscale SSH timed out. The first
manual and systemd runs succeeded, writing
`data/reports/bot_g_daily_probe/latest.md` and `.json`; timer next run is
`2026-05-08 06:10:56 UTC`.

**Progress 2026-05-09 sub-8c winner tracking:** Extended
`scripts/bot_g_daily_probe_report.py` so the daily VPS report now includes
one-cent entry-price buckets, sub-8c rows by price point, sub-8c rows by
symbol/side/price, and a `sub8_winners` tape listing every `<8c` entry that
resolved as a winner with bot, placed time, symbol, side, entry price, lead,
UTC hour, CEX tag, volatility, P&L, and question. Deployed the read-only script
to `vps-host` and regenerated
`data/reports/bot_g_daily_probe/latest.{md,json}`. The current tape has `14`
sub-8c winners across live/paper lanes; the only realised live winner is
SOL NO at `4c-5c`.

**Progress 2026-05-08 take-profit counterfactual (positive point estimate, NOT decision-grade):**
A read-only replay of all 154 Bot G placed entries against the recorder
book tape evaluated alternative exit rules. Report:
`data/reports/bot_g_math/take_profit_counterfactual_20260508T142203Z.{md,json}`.

**Aggregate:**

| Strategy | Total P&L (153 closed) | Mean ROI | Trigger rate |
|---|---:|---:|---:|
| Hold to resolution (current) | `$306.21` | `+49.1%` | n/a |
| TP at 10c | `$135.82` (`Δ −$170`) | `+5.9%` | `20.3%` |
| TP at 20c | `$279.25` (`Δ −$27`) | `+33.0%` | `17.0%` |
| **TP at 50c** | **`$623.25`** (**`Δ +$274`**) | **`+95.2%`** | **`13.1%`** |

**Bootstrap 95% CI on (TP − hold) delta (10,000 resamples):**

| TP threshold | Point delta | 95% CI lower | 95% CI upper | Verdict |
|---|---:|---:|---:|---|
| TP at 10c | `−$174` | `−$544` | `+$108` | INCONCLUSIVE |
| TP at 20c | `−$40` | `−$387` | `+$238` | INCONCLUSIVE |
| **TP at 50c** | **`+$274`** | **`−$47`** | **`+$605`** | **INCONCLUSIVE (point > 0, lower < 0)** |

**Read:** ~13% of placed entries spike to ≥ 50c before close. Exiting
at 50c roughly doubles the point-estimate P&L vs hold-to-resolution.
**But the bootstrap 95% CI lower bound is `−$47`** — the apparent edge
does not survive resampling at 95% confidence. The point estimate
suggests a real signal but the sample is too small (153 entries, 20
TP@50c triggers) to be decision-grade.

The improvement is concentrated in BTC NO 3.5c-5.5c (`+$32`), "unknown"
NO 3.5c-5.5c (`+$147`), XRP YES 5.5c-8c (`+$14`), and ETH YES 5.5c-8c
(`+$34` flipping a loss to a profit).

**Caveats:**
- 95% CI lower bound is negative ⇒ apparent edge is not statistically
  distinguishable from zero. More data needed.
- Recorder book coverage is `112/154 = 73%`. Entries with no
  post-entry book events fall through to hold-to-resolution, so TP
  rates are conservative.
- TP fill assumes we cross the spread at exactly the threshold.
  Live execution latency, slippage, and ask-vs-bid dynamics are not
  modelled.
- The existing inactive `polymarket-bot-g-prime-take-profit.service`
  was set up to test exactly this idea per ADR-128 but only collected
  9 entries / 8 settlements before going inactive.

**Operational implication:** counterfactual supports reactivating the
inactive TP@50c paper shadow service only as data collection for
≥ 150 more entries.
Re-run this bootstrap once the sample crosses 300 closed entries; if
the 95% CI lower bound moves above zero, propose live promotion via a
new ADR. Live promotion now is premature.

**Correction 2026-05-08 Codex audit:** the take-profit replay aggregate
now computes totals from raw fill-level rows, matching the bootstrap
point estimate instead of summing rounded per-cell values. The report's
decision read is unchanged: TP@50c has a positive point estimate but
the 95% CI still crosses zero, so reactivation is paper-shadow data
collection only, not live promotion evidence.

**Progress 2026-05-08 expanded clustered validation:** implemented and ran
`scripts/research/bot_g_tp50_expanded_clustered_validation.py` read-only on
the bot LXC container across `bot_g_prime`, `bot_g_prime_live`, `bot_g_prime_shadow`,
`bot_g_prime_late_cheap`, and `bot_g_prime_take_profit`. Report:
`docs/reports/bot-g-tp50-expanded-clustered-validation-2026-05-08.md`;
raw artifact:
`data/reports/bot_g_math/tp50_expanded_clustered_validation_20260508T145209Z.{md,json}`.
Result: **FAIL**. TP@50c point delta improved to `+$345.01`, but only
`218` settled raw entries were available versus the `300` gate; duplicate-safe
clusters were `183`; entry bootstrap 95% CI was `[-$18.61, +$722.69]`;
cluster bootstrap 95% CI was `[-$148.39, +$880.67]`; trading-day bootstrap
95% CI was `[-$174.19, +$885.66]`. Concentration also failed: `2026-05-06`
contributed `59.4%` of the point delta and UTC hour `02` contributed `64.7%`.
No live or paper service change is justified by this run.

**Progress 2026-05-08 safe rollout:** implemented an event-only
`bot_g.take_profit_shadow_signal` path in Bot G for the TP@50c formula. The
live service templates set the shadow signal to `50c` during the final `25s`
to `8s`, but the code does not call the CLOB sell path, does not call
`Portfolio.on_fill`, and does not close positions. This collects live
"would-have-exited" evidence for a future ADR without promoting the TP formula
into live execution.

**Progress 2026-05-08 deployment:** deployed the Bot G TP shadow hook to
`vps-host` and restarted active VPS Bot G lanes:
`polymarket-bot-g-prime-live.service`, `polymarket-bot-g-prime.service`,
`polymarket-bot-g-prime-shadow.service`,
`polymarket-bot-g-prime-late-cheap.service`, and
`polymarket-bot-g-prime-take-profit.service`. All returned `active`.
`polymarket-bot-g-prime-live.service` now has
`BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_ENABLED=true` and
`BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE=0.50`. The VPS DB had `0`
`bot_g.take_profit_shadow_signal` rows immediately after deployment, as no
post-restart TP trigger had occurred yet.

**Progress 2026-05-08 math edge monitor:** Added
`scripts/research/math_edge_data_monitor.py` and ran it on the bot container. Report:
`docs/reports/math-edge-data-monitor-2026-05-08.md`. the bot container showed `200`
Bot G `bot_g.entry_placed` rows in the 7-day window but `0`
`bot_g.take_profit_shadow_signal` rows and `0` paper take-profit exits. This
does not evaluate the VPS-only live hook because the VPS SSH alias timed out;
VPS TP-shadow accumulation still needs a reachable-host rerun.

**Progress 2026-05-08 Phase 2 hazard audit (math roadmap):** Phase 2 of the
math formula roadmap ran on LXC against `bot_g_prime` + `bot_g_prime_live`:
154 orders, 149 closed, 90 quoted for spike events. Results:

- Win-event empirical hit rate: `6.49%` (rare-event-corrected logit).
  Implied probability from 4–8c entry: 4–8%. Entries are mildly
  underpaying but not by enough to clear costs.
- Spike-to-threshold rates: `spike_10c=18.83%`, `spike_20c=14.29%`,
  `spike_50c=11.69%`.
- Murphy decomposition by cell: **resolution = 0.0000 in every cell.**
  Entry-implied probabilities have no discrimination power between
  winners and losers.
- Per-cell ROI: most cells return `~-106.9%` (total loss including fees);
  the cells with apparent positive ROI (8 of 39) all have lower bootstrap
  CI below `-100%` and top-2 P&L concentration ≥ 100% — entire
  apparent edge is one or two lottery wins.
- **Phase 2 verdict: FAIL.** No cell clears the §4 gate (positive ROI +
  lower CI > 0 + top-2 concentration < 80%).

**Progress 2026-05-09 Session 259 audit:** the operator confirmed ADR-136 is canonical
for current runtime posture: Bot G live stays active as a `$1` data-gathering
micro-probe. Updated `core/bot_registry.py` and the active operating model so
the dashboard no longer reports `active_policy_conflict`. ADR-135's negative
live-shaped evidence remains the scale/promotion blocker.

**Progress 2026-05-09 Session 261 closeout:** Found a concrete `$1` probe
execution bug during the commit-readiness pass: sizing with
`BOT_G_FIXED_TRADE_USD=1` and Decimal division can produce
`$0.999999...`, tripping the `$1` minimum-notional guard and skipping otherwise
valid entries. Patched the guard locally with a `0.000001` tolerance and added
`test_live_one_dollar_probe_passes_min_notional_guard`. This code fix is not
deployed to the live Bot G process in this session because restarting live Bot
G can enable real-money entries and needs explicit operator approval.

Reports: `data/reports/bot_g_math/hazard_score_20260508T133812Z.{md,json}`.

This is the Bot A failure mode (high apparent hit rate, no real
discrimination, lottery-shaped P&L) that Murphy decomposition was
designed to surface. Combined with the prior multi-model recommendation
to halt or retire, the operator-decision question is now whether to
halt/retire now or keep collecting at `$1` until OQ-085's seven-day mark.

### OQ-080 — VPS split-hosting pilot for live runtimes (the operator + Claude)

**Category:** Decision-required / infrastructure relocation.
**Owner:** the operator decides scope/provider; Claude benchmarks and proposes ADR.
**Surfaced by:** 2026-05-06 VPS capacity/latency assessment.

**Problem:** the homelab hypervisor/the bot LXC container is reaching capacity while live bots, crypto
recorders, dashboard surfaces, and paper research lanes are becoming more
latency-sensitive. A VPS may reduce CLOB/Gamma round-trip time and isolate
runtime services from local storage pressure, but moving live order-placement
surfaces changes the ADR-006 the homelab hypervisor deployment decision and ADR-014 VPN
posture. Secrets, wallet auth, database replication, watchdog routing,
backups, monitoring, and rollback must be designed before any live service
moves.

**Acceptance criteria:** Before moving any live bot, wallet/CLOB auth path, or
order-placement service to a VPS, produce a benchmark comparing current the bot LXC container latency against at least one candidate VPS region for CLOB, Gamma,
Binance/Coinbase/CEX inputs, Telegram, and Polygon RPC. If any service must
break out through a Swedish the VPN provider exit, benchmark both direct VPS egress and
VPS-to-the VPN provider-Sweden egress; the latter is the decision-grade number for
that service because the Swedish exit becomes the effective network edge. The
proposal must name exact services to move, exact services to keep on the homelab hypervisor,
provider, region, monthly cost, OS hardening, VPN/geofence posture, secret
handling, SQLite/recorder replication model, backup retention, health checks,
and a one-command rollback path. If accepted, record a new ADR superseding
the relevant parts of ADR-006/ADR-014.

**Progress 2026-05-06 Swedish breakout constraint:** the operator clarified that some
programs need to break out in Sweden through the VPN provider. This weakens the value
of a far-away low-latency VPS for those programs: an Ashburn VPS that tunnels
to Sweden still effectively exits in Sweden, while adding one extra tunnel
leg. Candidate regions for Swedish-breakout services should therefore include
EU/Nordic hosts near Sweden, or keep those services on the homelab hypervisor if the current
the VPN provider path benchmarks well enough. Non-Sweden services can still be
benchmarked separately for direct VPS egress.

**Progress 2026-05-06 Polymarket eligibility constraint:** Polymarket's
current public geographic-restriction help page says VPNs or similar tools
must not be used to bypass restrictions, and that permissions are based on
physical location rather than residency when users travel to non-restricted
countries. A VPS in a non-restricted EU country can be a valid hosting target
only if it is not being used to make a restricted-location operator appear
elsewhere. The relocation proposal must therefore separate technical egress
from account/trading eligibility and identify which services are data-only
versus order-placement.

**Progress 2026-05-06 Helsinki VPS baseline:** Created
`vps-host`, a a small EU VPS, `8 GB
RAM`, `80 GB` disk, Ubuntu `24.04`, IPv4 `198.51.100.1`, and two SSH public
keys. Read-only latency benchmark compared direct the VPS provider egress with current
the bot LXC container egress (`198.51.100.2`). Median total request times over five
samples: CLOB `237.5ms` vs LXC `637.4ms`; Gamma `109.3ms` vs `264.0ms`;
CLOB websocket edge HTTPS probe `144.6ms` vs `300.6ms`; Binance time
`307.1ms` vs `495.5ms`; Coinbase BTC ticker `116.7ms` vs `281.4ms`; Polygon
RPC `113.6ms` vs `298.1ms`; Telegram API `111.6ms` vs `324.7ms`;
Open-Meteo `363.1ms` vs `636.5ms`; NWS API `68.2ms` vs `271.0ms`; NOAA
TGFTP `1104.1ms` vs `1218.7ms`. Direct Helsinki materially improves the
trading/API path, but the Swedish-the VPN provider-on-VPS route still needs a separate
benchmark before any Sweden-breakout service moves.

**Progress 2026-05-06 VPS hardening:** Hardened `vps-host` before
any migration. Created non-root sudo user `operator` with laptop and the local workstation
SSH keys; disabled root SSH, password auth, keyboard-interactive auth, agent
forwarding, TCP forwarding, and X11 forwarding; restricted SSH login to
`operator`; enabled UFW default-deny inbound with only OpenSSH allowed; installed
and enabled baseline monitoring/ops tooling plus fail2ban, unattended
upgrades, sysstat, and vnstat; added an explicit fail2ban `sshd` jail.
Verified `operator` SSH and sudo, root SSH rejection, active firewall, active
fail2ban jail, and apt daily timers. No bot runtime, secret, wallet path, VPN,
or service was moved.

**Progress 2026-05-06 Bot G-first migration preference:** the operator clarified the
first candidate should be Bot G, not Bot E. Because Bot G has live-wallet
surfaces, the safe order is not to move `bot_g_prime_live` first. The VPS
pilot should start with Bot G read-only/paper surfaces: repo/runtime setup,
health checks, latency probes, Bot G report generation against copied
snapshots, then `bot_g_prime_shadow` or another paper-only Bot G lane using a
separate VPS paper DB. Only after parity, monitoring, backup/restore, and
rollback are proven should any ADR propose moving `bot_g_prime_live`,
keystore/passphrase handling, or CLOB order placement.

**Progress 2026-05-06 Bot G paper-runtime staging:** Completed the first safe
VPS deployment slice. Copied source only to `/home/operator/longshot-research`,
excluding `.env`, `.git`, `.venv`, production `data`, logs, caches, and
bytecode. Installed the Python runtime and project virtualenv, verified Bot
G-focused tests on the VPS (`76 passed`), and staged a disabled/inactive
paper-only unit `longshot-bot-g-prime-shadow-vps.service`. The unit has no
EnvironmentFile or secrets and resolves to `POLYMARKET_ENV=paper`,
`BOT_G_DRY_RUN=true`, `BOT_G_ID_OVERRIDE=bot_g_prime_shadow_vps`, and local
VPS DB paths. No VPS service was started and no production/LXC service,
wallet path, secret, live order path, or the VPN provider setting changed.

**Progress 2026-05-06 Bot G paper lane cutover:** Accepted ADR-112 and moved
four paper-only Bot G services to `vps-host`:
`polymarket-bot-g-prime.service`,
`polymarket-bot-g-prime-shadow.service`,
`polymarket-bot-g-prime-late-cheap.service`, and
`polymarket-bot-g-prime-take-profit.service`. The VPS units pin
`POLYMARKET_ENV=paper`, `BOT_G_ENV=paper`, and `BOT_G_DRY_RUN=true`; they use
a dedicated VPS Bot G paper ledger plus the VPS paper recorder feed. the bot container
copies are stopped/disabled, the bot container `/api/bot-g` reports these lanes as
`vps:active`, and `polymarket-bot-g-prime-live.service` remains active on
the bot container. No wallet/CLOB auth, keystore/passphrase, live order-placement path,
the VPN provider config, production recorder canonical write path, Bot D, watchdog, or
notifier moved.

**Progress 2026-05-10 Bot G sync/backfill:** the bot container was backfilled from the
latest VPS Bot G backup before ADR-149 activation. The backfill inserted the
missing VPS Bot G paper/live ledger rows into the bot container, regenerated the
lead-bucket report, and restarted the dashboard. the bot container `/api/bot-g` now shows
lead-bucket data available, backfilled paper rows, and the new high-tail
paper lane. VPS node-status now tracks `bot_g_prime_high_tail` alongside the
existing Bot G lanes.

**Progress 2026-05-06 live Bot G VPS relocation declined:** Accepted ADR-113.
Audited the operator's request to move `polymarket-bot-g-prime-live.service` to the
Helsinki VPS for latency. Because the service is a real live order-placement
path and the operator is UK-based, moving it to Helsinki would use
infrastructure location to bypass geographic restrictions. Official
Polymarket docs list `GB United Kingdom` as `Blocked` for order placement,
and Polymarket Help Center guidance says VPNs/proxies/anonymization tools must
not be used to circumvent restrictions. No live unit, wallet/CLOB auth,
keystore/passphrase, `.env`, the VPN provider config, or real-money order path was
moved.

**Progress 2026-05-06 Bot G VPS canary:** Continued without buying the VPS provider
backups. Stopped oversized recorder snapshot attempts (`10d` at `14G`, `48h`
at `15G`) before they could pressure the bot LXC container disk, then built a compact 6h
snapshot for the first VPS validation. The transferred snapshot contains
`478` Bot G orders, `926` trades, `462` positions, `6,078` events,
`1,195,338` BTC/ETH/SOL CEX trades, `739,528` Polymarket events, `1,113`
market rows, and `0` recorder gaps. Bot G reports ran successfully on the VPS
under `data/reports/vps_botg/20260506T084234Z`; the report window was thin
(`4` recent Bot G rows), so this validates runtime/reporting parity rather
than strategy performance. Installed and started one-hour, disabled-at-boot
canary services: `longshot-crypto-recorder-vps-canary.service` writes
BTC/ETH/SOL public telemetry to
`/home/operator/longshot-research/data/bot_e_recorder_vps_canary.db`, and
`longshot-bot-g-prime-shadow-vps.service` runs paper/dry-run only against the
canary recorder DB and local VPS `data/main.db`. Both have
`RuntimeMaxSec=3600` and should stop automatically around
`2026-05-06 09:47 UTC`. Health check showed the recorder active with
`28,063` CEX trades, `17,886` Polymarket events, `28` markets, `84`
heartbeats, and `0` gaps; Bot G logged `effective_paper=True`, saw one market
window, and had placed `0` paper orders. No live order-placement path, secret,
wallet auth, the homelab hypervisor runtime service, or the VPN provider config changed.

**Progress 2026-05-06 SSH recovery / access posture reset:** The first
hardening pass proved too brittle for early setup. After rescue and console
recovery, the operator disabled UFW, disabled fail2ban, flushed nftables, and restarted
SSH; remote access was restored. The the local workstation key is now installed for
`operator`, `operator` is back in the `sudo` group, and root has key-only emergency
fallback access. Current VPS SSH posture is intentionally less hardened until
the split-hosting pilot stabilizes: password SSH is enabled, root SSH is
`prohibit-password`, TCP/agent forwarding are allowed, UFW is inactive, and
fail2ban is inactive. Before any longer-running or live VPS service, rebuild a
minimal allow-SSH-first firewall and test access across a reboot.

**Progress 2026-05-06 preferred deployment route:** Reviewed the operator's proposed
the VPS provider offload plan. Adopt the direction but change the order. Tailscale is
recommended as the private control plane for VPS status, dashboard/watchdog
reachability, metrics, and future secret transfer if live relocation is ever
approved. Before moving more services, add a Phase 0: keep SSH stable in the
current less-hardened posture, install Tailscale, verify the local workstation/laptop and
the bot container or the the homelab hypervisor-facing monitor can reach the VPS over the tailnet, add a
read-only VPS status/dashboard bridge, and prove access survives a reboot
before rebuilding a minimal firewall. After Phase 0, move paper-only crypto
fair-value bots first, then the shared crypto recorder, then Bot G paper/shadow
lanes. Keep `bot_g_prime_live`, wallet/CLOB auth, keystore/passphrase transfer,
and any real-money order-placement path last and blocked until a new ADR
accepts live relocation. Corrections: the five Bot G units are not all
live-money surfaces; only `bot_g_prime_live` is live. The current dashboard is
single-host/single-DB and local-systemd oriented, so it will not align with VPS
canaries until the status bridge or DB replication exists. Becker/model replay
work should run on the local workstation or another offline analysis host, never the bot container or
the VPS runtime host. the bot container CPU cap/service-allocation quick wins remain useful
but should be applied only after checking current load and service state.

**Progress 2026-05-06 Phase 0 private control plane:** Installed Tailscale on
`vps-host` and enabled `tailscaled.service`. the operator approved the
node into the tailnet; VPS Tailscale state is `Running` with private IP
`192.0.2.1` and IPv6 `fd7a:115c:a1e0::f438:512d`. Removed Tailscale SSH
interception so normal key-based OpenSSH works over the private IP. laptop
SSH to `operator@192.0.2.1` works. the homelab hypervisor and the bot container can ping the VPS over
Tailscale at about `55ms`-`57ms`; the bot container does not yet have an accepted SSH key,
so dashboard integration should use a read-only private status path or a
deliberate the bot container status key. Added `scripts/vps_node_status.py` and deployed
it to the VPS as a read-only status reporter. Installed
`longshot-vps-node-status.service`/`.timer` so the VPS writes
`data/reports/vps_node/latest.json` and `.md` every minute. First report
confirms SSH and Tailscale services active, canary services inactive/disabled,
disk `4.8%` used, local paper DB empty except `12` events, and recorder canary
DB with `513,179` CEX trades, `230,888` Polymarket events, `230` markets,
`1,343` heartbeats, and `0` gaps. Added a VPS status HTTP bridge bound only to
`192.0.2.1:8091` and deployed dashboard support on the bot container. The the bot container
dashboard now consumes `http://192.0.2.1:8091/latest.json` over Tailscale
and `/api/overview` reports `vps_node.ok=True`, `status=healthy`, and `0`
recorder gaps. Rebooted `vps-host` and verified private SSH,
Tailscale, the status timer, and the private status HTTP bridge all returned;
the bot container dashboard still reported the VPS node healthy after reboot. This is
read-only node/status visibility, not VPS DB replication into the the bot container
trading database.

**Progress 2026-05-06 paper fair-value cutover:** Rebuilt minimal UFW on the
VPS with public `22/tcp` retained as setup fallback and all inbound
`tailscale0` traffic allowed. Added a persistent VPS paper feed for BTC/ETH/SOL
public telemetry and enabled VPS services for
`polymarket-crypto-prob-gap-paper.service` and
`polymarket-crypto-brownian-fv-paper.service`, both paper/dry-run only and
using VPS-local DB paths. Stopped and disabled the matching the bot container paper
services after the VPS services were active. The the bot container dashboard now overlays
these services as `vps:active` through the VPS status bridge. This moves the
first two paper-only loops off the homelab hypervisor without touching wallet/CLOB auth,
secrets, live services, the VPN provider config, the the bot container production recorder, or
the homelab hypervisor cgroup settings. Remaining gap: VPS paper DB rows are not yet
replicated into the the bot container main trading DB, so dashboard service state is
aligned but historical VPS paper fills/signals need either a read-only remote
summary bridge or deliberate DB replication.

**Progress 2026-05-06 VPS paper metrics bridge:** Added VPS-local crypto
fair-value summaries to the private VPS status JSON and updated the bot container
`/api/crypto-fair-value` to consume them whenever the lane is `vps:active`.
The dashboard now shows real VPS scan summaries/counts for the moved paper
lanes rather than stale the bot container DB rows. Verified current the bot container API output:
`crypto_probability_gap_paper` and `crypto_brownian_fv_paper` both report
`data_source='vps'`, `162` scan summaries, `289` markets seen, and `0` signals
so far. Remaining gap: VPS detailed order/trade rows are summarized, not fully
replicated into the bot container's main DB.

**Progress 2026-05-06 recorder shadow soak:** Added the bot container-vs-VPS recorder
comparison metrics to the private status bridge and dashboard overview. The
VPS shadow feed remains separate from the the bot container production recorder. Initial
comparison has `0` gaps on both, `4` active subscriptions on both, the bot container
heartbeat age `0.9s`, VPS heartbeat age `9.9s`, the bot container PM events/min `1419.9`,
VPS PM events/min `821.0`, the bot container CEX trades/min `2896.5`, and VPS CEX
trades/min `5110.8`. Created
`docs/vps-split-hosting-outline-2026-05-06.md` as the canonical outline of
completed and remaining VPS migration work. Created follow-up automation
`vps-recorder-soak-check` for roughly 12h and 24h soak checks before deciding
whether to move any additional runtime.

**Progress 2026-05-10 Bot G dashboard lag:** Bot G paper/live analysis found
that the bot container dashboard `main.db` has `127` `bot_g_prime` orders through
`2026-05-08 20:39 UTC`, while the latest the homelab hypervisor VPS backup has `158` through
`2026-05-10 10:44 UTC`. This confirms the remaining VPS detailed-row
replication/backfill gap still affects Bot G dashboard decisions. Before using
the dashboard as the Bot G decision surface, backfill or bridge the latest VPS
Bot G rows again and verify `/api/bot-g` against the the homelab hypervisor backup.

**Blocks:** Any relocation of `bot_g_prime_live`, `bot_d_live_probe`, wallet
auth material, CLOB order placement, or production recorder writes to a VPS.

### OQ-063 — Bot G post-live tiny-probe proof and scale decision (Empirical)

**Category:** Research-required / live validation.
**Owner:** Empirical; Claude reports; the operator decides scale/rollback.
**Surfaced by:** 2026-05-02 ADR-078 live activation.

**Problem:** The first live rung proves execution transfer, not durable edge.
Bot G Prime can start tiny-live at `4c-5c`, but size increases require live
evidence that fills, reconciliation, slippage, capacity, and outlier-adjusted
ROI match or beat paper expectations.

**Acceptance criteria:** After `10` live fills, verify zero auth/sizing/reject
errors and every fill is recorded under `bot_g_prime_live`. After `20` live
fills, verify median live entry slippage is within one tick of paper
expectation. After `50` live fills, verify ex-largest-two-wins ROI remains
positive before any size increase. Daily reporting must include realised P&L
vs cap, open live exposure, live fills count, and whether the `4c-8c` paper
shadow is still running.

**Progress 2026-05-02 live accounting halt:** the operator's Polymarket UI screenshot
showed wallet positions that the dashboard did not record as
`bot_g_prime_live` fills. `polymarket-bot-g-prime-live.service` was stopped
immediately to prevent further untracked live entries. Parser root cause was
fixed in `core/clob_v2.py`: V2 trade payloads can use `taker_order_id` or
`maker_orders` instead of `order_id`. The live service must remain stopped
until the missed fills are backfilled/reconciled and the dashboard shows the
actual wallet positions under `bot_g_prime_live`.

**Progress 2026-05-02 live resumed:** The missed live fills were backfilled
with `require_known_order=True`, the two already-resolved BTC positions were
settled locally at `$0`, and a stale local order row was marked
`EXCHANGE_CLOSED` after the exchange reported `0` open orders. Bot G Prime
Live is active again. Dashboard/API now reports `open_orders=0`,
`live_fills_count=2`, `settlement_fills_count=2`, `paper_fills_count=0`, and
realised P&L `-1.91` for `bot_g_prime_live`.

**Progress 2026-05-03 paper/live transfer check:** Overnight paper shadow
entries at `02:16` and `03:30` UTC produced one loss and one win. Live placed
the same `03:30` ETH/NO condition, but at `4c` instead of paper's `5c`, and
the real CLOB order did not fill. A read-only CLOB open-order check returned
`0` open orders, so the local stale `live` order row was marked
`EXCHANGE_CLOSED`. Bot G now reconciles absent live open orders automatically
so stale unfilled GTCs do not keep dashboard exposure open. This reinforces
that paper wins are not live proof until transfer/fillability is observed.

**Progress 2026-05-03 live transfer tuning:** ADR-083 keeps the live universe
at BTC/ETH/SOL and `4c-5c`, but lets Bot G Prime Live submit one tick above
the observed qualifying ask, capped at `5c`, and lowers the live scan interval
from `10s` to `5s`. Paper shadow remains unchanged. The next proof question
is whether this increases live fills without pushing median slippage beyond
one tick.

**Progress 2026-05-03 live band expansion:** the operator explicitly approved ADR-085:
Bot G Prime Live widens to observed `3.5c-5.5c`, keeps the one-tick transfer
bid capped at `5.5c`, and keeps the same `$5` entry size, `20` entries/day,
`$100` daily gross, `10` max open, and BTC/ETH/SOL-only universe. The next
proof question is whether the added `3.5c-4c` and `5c-5.5c` slices improve
live sample flow without degrading fill quality or ROI versus exact `4c-5c`.

**Progress 2026-05-03 pre-submit timing guard:** Production inspection showed
recent `1c` Polymarket fills were price improvement on submitted `4c`,
`5c`, or `5.5c` limits, not a strategy order at `1c`. The timing weakness was
stale scan time: `t_to_res_sec` was computed before later DB/CEX/depth/CLOB
work. ADR-088 adds a fresh pre-submit clock check and rejects entries with
less than `5s` fresh lead, emitting `bot_g.entry_stale_time_rejected` events.

**Progress 2026-05-03 live timing retune:** Post-guard validation showed Bot G
Prime Live healthy but idle after `08:30 UTC`; caps were clear and two later
attempts were rejected only because the fresh pre-submit clock was already
past close. ADR-089 keeps the `5s` guard but changes the live unit to scan
earlier/faster: `60s` entry window and `2s` scan interval.

**Progress 2026-05-03 live-transfer report:** Added a read-only Bot G
live-transfer report and lightweight entry timing telemetry. The first 24h the bot LXC container snapshot shows `9` live placed, `7` filled, `2` exchange-closed/no-fill,
`0` open, `3` stale rejected, placed-order fill rate `77.8%`, denominator fill
rate `58.3%`, `13` paper candidate entries, `5` matching live entries
(`38.5%`), and `7` closed live `4c-5c` round trips at `-100%` ROI so far.
Timing metrics will populate from the next post-deploy live entry or
fresh-clock rejection.

**Progress 2026-05-04 latency phases:** ADR-094 implemented the accepted Bot
G Phase 0-5 latency/reporting plan without changing size, caps, wallet, band,
symbols, or the `5s` fresh-clock guard. Disabled Prime CEX/depletion labels
are now skipped pre-submit in effective-live mode instead of blocking the
entry window; recorder hot-path indexes were built on the bot LXC container and `ANALYZE`
was run; the book query no longer uses a single `asset_id OR condition_id`
shape; the report now includes funnel, symbol, and fresh-lead slices. Fresh
36h report still mostly reflects pre-deploy entries: `7` placed, `6` filled,
`1` no-fill, `13` stale rejects, `0` open, and `6` closed live losses. The
first post-deploy live placement at `2026-05-04 12:09:04` verified the fast
path: `book_lookup_ms=3.183`, `prime_signal_ms=0.017`,
`capacity_depth_ms=0.913`, pre-submit cumulative timing about `5.089ms`, and
network submit response `924.426ms`. The next proof item is a larger
post-deploy sample to compare live/paper match rate and fill rate under the
faster path.

**Progress 2026-05-05 first live sample review:** A read-only the bot LXC container review
shows `32` Bot G Prime Live orders, `27` execution fills, `4`
exchange-closed/no-fill orders, and `1` stale local `live` order in the last
`96h`. Placed-order fill rate is `84.4%`. The first `10` execution fills
averaged `1.7c`; the later `17` averaged `3.65c`, so the probe is now
collecting materially more relevant `3.5c-5.5c` data. Profitability is still
unproven: all `27` closed live fills are losses in the transfer report
(`-$59.04`, `-100%` ROI). Production logs also showed repeated
`bot_g.reconcile_open_orders_failed err='size'`; `core/clob_v2.py` was
patched so missing-size V2 open-order payloads do not block absent open-order
reconciliation. the operator approved deployment. After the the bot LXC container patch and
`polymarket-bot-g-prime-live.service` restart, the stale local live order was
marked `EXCHANGE_CLOSED`; DB status shows no `OPEN`/`PARTIAL`/`live` orders
for `bot_g_prime_live`, and post-restart logs show no new size-key
reconciliation warnings.

**Progress 2026-05-05 watchdog DNS halt:** Telegram reported a watchdog kill:
`bot_g_prime_live halted by watchdog: cannot resolve clob.polymarket.com`.
Production DNS was resolving again by inspection, but the halt remains active
and Bot G Prime Live is skipping trading. Direct CLOB read found
`EXCHANGE_OPEN_COUNT=0`. A local `PARTIAL` order row remained because the
open-order reconciler only handled no-fill absent orders; patched and deployed
an accounting-only fix so absent partial-fill orders are also marked
`EXCHANGE_CLOSED` with `had_fill=true`. After one reconciliation, local DB has
no `OPEN`/`PARTIAL`/`live` rows for `bot_g_prime_live`. Resuming requires
explicit operator approval because clearing the halt re-enables real-money
entries.

**Progress 2026-05-05 DNS halt clear:** the operator approved clearing DNS watchdog
halts for Bot G Prime Live, Bot G paper shadow, and Bot D live probe, then
explicitly added Weather Fade paper. Those halt flags were cleared and the
scoped services were restarted. Bot C and Bot E halt flags were restored
because they were outside the final confirmation. Bot G Live resumed and
placed one new live order at `2026-05-05 04:39:12`; the fill reconciled and
the remaining order row was marked `EXCHANGE_CLOSED`, leaving one open live
position from that fill.

**Progress 2026-05-07 live size reduction:** the operator judged the Bot G edge likely
flawed but asked to keep the live probe running in case the strategy enters a
better win cluster. ADR-118 reduced active VPS `bot_g_prime_live` fixed entries
from `$5` to `$3`, while keeping the observed `3.5c-5.5c` band, one-tick cap,
entry caps, wallet reference, and BTC/ETH/SOL universe unchanged.

**Progress 2026-05-08 ADR-136 update:** the operator later reduced the active live
data probe again to `$1` fixed entries. ADR-135 still blocks scaling or
promotion; ADR-136 is only the minimum-size data-collection posture.

**Progress 2026-05-07 multi-model deep analysis:** Added
`docs/reports/bot-g-multi-model-deep-analysis-2026-05-07.md`. Local evidence
plus redacted external critiques (GLM-5.1, Gemini 2.5 Pro, DeepSeek V4 Pro
reasoning; Groq Qwen refused for token-limit) converge on the same read: Bot G
paper-main is an execution illusion, live fills are selected into bad outcomes,
and the pure taker longshot thesis should be halted after the operator approval unless
a tightly scoped seven-day `$3` microstructure probe disproves structural
no-edge. Opened OQ-085 to track that probe/retirement decision.

**Status 2026-05-09 — RESOLVED (no scale).** Per
`docs/reports/bot-g-final-review-2026-05-09.md`: 51 closed live entries
all-time, 1 win (SOL NO at 4c, +$19.14), -$82.84 / -80.6% ROI on VPS
(-$181.50 lifetime including pre-VPS-migration). ex-largest = -$101.98
(the single SOL NO win is propping up the entire ledger). 18/51 orders
EXCHANGE_CLOSED before fill = 35% miss rate. Every BTC and ETH cell is
-100%. The 50-fill ex-largest-two-wins criterion in this OQ's
acceptance was met decisively — no positive ROI under trimming. **No
scale decision is defensible.** Operator decision pending: keep `$1`
data probe or halt. ADR-136 unchanged; this OQ is resolved against
its own acceptance criteria.

**Progress 2026-05-10 high-tail reconciliation:** the operator flagged that more paper
trade data existed between the VPS and the homelab hypervisor copies. Read-only reconciliation
confirmed the bot container dashboard `main.db` has `127` `bot_g_prime` orders through
`2026-05-08 20:39 UTC`, while the latest the homelab hypervisor VPS backup
`<bulk-storage>/` has `158`
orders through `2026-05-10 10:44 UTC`. The fresher VPS ledger shows
`bot_g_prime` paper at `157` resolved / `13` wins / `+$277.01` / `+48.0%`
ROI, but only `+6.5%` ROI after removing the two largest wins. Current live is
still negative at `68` resolved / `1` win / `-$88.73` / `-81.6%` ROI and
`-100%` ex-largest. The only paper price band that survives top-two trimming
is `6.5c-8c` (`36` resolved / `7` wins / `+$182.30` / `+134.3%` ROI /
`+39.3%` ex-top-two), especially ETH NO (`9` resolved / `3` wins / `+9.4%`
ex-top-two). Report:
`docs/reports/bot-g-paper-live-reconciliation-and-live-adjustment-2026-05-10.md`.
This does not authorize a live change; it supports a possible ADR to replace
the current `$1` live probe with a narrower `6.5c-8c`, ETH/SOL-only, 45s
high-tail probe after the bot container dashboard backfill.

**Progress 2026-05-10 ADR-149 retune:** the operator approved the high-tail
recommendation. the bot container was backfilled first from the latest VPS backup, then
`bot_g_prime_live` was retuned on `vps-host` to `$1`,
`6.5c-8c`, `45s`, ETH/SOL only. BTC was removed from live. The live guard now
accepts only the old rollback profile or the ADR-149 profile. Pre-restart VPS
DB check showed no open live orders or positions. Post-deploy verification
showed `polymarket-bot-g-prime-live.service` active, CLOB credential
derivation successful, and the bot container `/api/bot-g` reporting live probe active
with the backfilled lead-bucket data available.

**Progress 2026-05-10 ADR-150 dashboard epoch:** the operator asked to archive the
old live history from the dashboard headline so the ADR-149 probe can be read
cleanly. Implemented a dashboard/read-model epoch split only: raw DB history
is unchanged, current `bot_g_prime_live` headline metrics start at
`2026-05-10T16:28:10+00:00`, and pre-epoch live history remains visible as an
archived legacy block. the bot container `/api/bot-g` now reports current live epoch P&L
`$0.00`, orders `0`, fills `0`, and archived legacy live P&L `-$99.91` over
`73` old orders.

**Blocks:** Any Bot G live size increase beyond `$1` entries, any cap
increase, any live symbol expansion beyond ETH/SOL, or any entry-band
expansion beyond observed `6.5c-8c`.

### OQ-067 — Bot D tiny-live transfer proof and scale decision (Empirical)

**Category:** Research-required / live validation.
**Owner:** Empirical; Codex reports; the operator decides continue/rollback/scale.
**Surfaced by:** 2026-05-03 ADR-084 Bot D tiny-live probe.

**Problem:** Bot D paper fills and paper P&L do not prove live fillability or
live execution quality. the operator approved a minimum-size `bot_d_live_probe`
plumbing run so the bot can collect real fill, slippage, reconciliation, and
exit evidence while `bot_d` paper continues in parallel.

**Current approved packet:** `$200` wallet allocation posture,
`evidence_gated` live sizing (`5` fixed baseline, selected verified slices up
to `40` dynamic shares), `$10` max order notional, `$150` max daily gross,
`$200` max filled-plus-resting exposure, `50` max concurrent positions,
verified settlement and known end-date required, wave/depth gates loosened for
collection, and NWS fallback entries disabled.

**Acceptance criteria:** After `5` live fills, verify every fill is recorded
under `bot_d_live_probe`, no live row lands under `bot_d`, and no untracked
wallet position exists. After `10` live fills, report live fill rate versus
paper candidates, median entry slippage, open-order reject/cancel counts, and
cap usage. After `20` live fills, report realised ROI, ex-largest-win ROI,
ex-largest-two ROI, stale exit count, and exit slippage before any decision to
continue, stop, or propose revised caps.

**Stop conditions:** Stop the live probe immediately on any untracked fill,
exit mismatch, stale live exit, cap breach, NWS fallback live entry, scipy
skew-normal fallback, or ledger pollution between `bot_d` and
`bot_d_live_probe`.

**Progress 2026-05-03 prep:** ADR-084, the systemd unit, fixed-share live
sizing, live caps, registry/watchdog/dashboard split, runbook, and regression
tests were prepared. The live service must remain stopped until final
operator activation.

**Progress 2026-05-03 Opus audit:** Opus returned `PASS WITH FIXES` for the
Bot D tiny-live probe. ADR-086 implements the accepted fixes: dedicated
watchdog env routing for `bot_d_live_probe`, paper-unit env precedence,
inline skew-normal fallback blocking for plumbing mode, required fixed shares
in live plumbing mode, explicit live-probe initial USD, live-probe dashboard
`open_orders_pnl` labeling, and regression coverage. OQ-067 remains open
until live transfer proof exists.

**Progress 2026-05-03 live activation:** the operator explicitly instructed Bot D
live activation. ADR-087 starts `polymarket-bot-d-live.service` under the
approved minimum-size packet. First live cycle: `12` raw markets, `7` kept,
`7` evaluated, `0` non-skip edges, `0` orders, `0` fills, and paper Bot D
remained active. OQ-067 remains open for first-fill and transfer proof.

**Progress 2026-05-03 no-trade diagnosis:** Later production inspection
confirmed Bot D live remained healthy but still had `0` orders and `0`
trades. Recent scans evaluated `8-9` markets, all with `multi_model`
forecasts, but every market was skipped before entry: mostly
`nws_disagrees` (`7-8` per scan), with occasional `below_threshold`. ADR-090
also fixes a shared-wallet reconciliation bug by requiring Bot D live fills
to match a known Bot D order before import. OQ-067 remains open for first
real Bot D fill and transfer proof.

**Progress 2026-05-03 slight loosen:** ADR-091 keeps the NWS second-opinion
guard but raises the live probe's NWS veto floor from `2.0F` to `3.0F`.
Scan summaries now include `nws_shadow` counts for the current floor, `3F`,
`4F`, and NWS-off lanes so the next review can compare actual first-fill
evidence against would-have-passed candidates.

**Progress 2026-05-03 candidate-quality report:** Added and ran
`scripts/bot_d_candidate_quality_report.py` on the bot LXC container as a read-only
production snapshot. The `72h` window found `3644` Bot D candidates/events:
`20` paper forecast-entry events, `3624` NWS veto candidates, `0` live-probe
orders/fills, and `6` recent paper fills. Setup tiers were `B=121`, `C=3523`,
`A=0`; average absolute edge was `0.0255`. Scan-level `nws_shadow`
would-tradeable counts were `0` for `3F`, `4F`, and NWS-off lanes, so this
does not justify another live loosen. Snapshot:
`docs/reports/bot-d-candidate-quality-report-2026-05-03.md`.

**Progress 2026-05-04 source-certainty phases:** Accepted the Bot D-only
phase plan after Opus review: Phase 0 live-order root cause, Phase 1 safe
labels, Phase 2 depth/cap evidence, Phase 3 label-sliced report, Phase 4
append-only outcome joins, Phase 5 late-stage source diagnostics, and Phase 6
only-if-gated loosening/scaling. Implemented local Phase 0/1/3 plumbing:
analysis labels in JSON payloads, `bot_d.entry_attempt` event support, and
label/root-cause slices in `scripts/bot_d_candidate_quality_report.py`.
Production read-only snapshot on the bot LXC container:
`docs/reports/bot-d-candidate-quality-report-2026-05-04.md`. The `72h`
window found `3339` candidates/events, `18` forecast-entry events, `3321`
NWS veto candidates, `0` live entry attempts, setup tiers `B=124`, `C=3215`,
`A=0`, and scan-level would-tradeable counts still `0` for `3F`, `4F`, and
NWS-off. The live service was not restarted; future production
`bot_d.entry_attempt` events require a later approved Bot D service deploy.

**Progress 2026-05-04 instrumentation deploy:** the operator approved deploying and
restarting Bot D so the Phase 0/1 instrumentation can record live evidence.
Remote compile passed and remote focused tests passed (`15 passed`). Restarted
`polymarket-bot-d.service` and `polymarket-bot-d-live.service`; both returned
active. First post-restart paper and live cycles each evaluated `6` markets,
found `0` non-skip / `0` tradeable edges, and placed `0` orders. Live remained
`bot_d_live_probe` with NWS floor `3.0F`. Post-restart 6h report:
`docs/reports/bot-d-candidate-quality-post-restart-2026-05-04.md`, showing
`155` C-tier candidates, `0` entry attempts, avg abs edge `0.0045`, and zero
would-tradeable shadow counts. Current idle state appears to be weak
candidate pressure, not a live executor failure.

**Progress 2026-05-06 live proof + paper alignment:** Bot D live now has
`34` live-probe orders, `29` fills, `21` positions, `6` closed positions, and
`1` redeemed position. A negative-risk NYC weather winner was redeemed
on-chain and recorded as `portfolio.redeem` for position `665`
(`+$0.345` realised). Paper Bot D was found healthy but stale-configured:
its recent entry attempts were all `nws_fallback` while live used the
NBM/GribStream/API-agreement stack. Paper Bot D's systemd unit was aligned to
the live probe's non-wallet data and strategy settings so the paper lane
remains comparable without sharing live wallet/cap flags. Dashboard cap
telemetry now exposes live-probe daily gross, exposure, and position slots.

**Progress 2026-05-09 full Bot D audit:** Live probe has moved from plumbing
proof to early edge proof: `71` orders, `70` live trade rows, `30` matched
closed groups, `22` wins, `+$11.2396` closed matched P&L, `+11.68%` ROI on
closed cost, `+9.35%` ex-largest-one ROI, and `+7.44%` ex-largest-two ROI.
Open state is controlled: `6` open positions, `$19.58` open exposure, and
`0` open orders. Live entries remain source-filtered (`24` multi-model,
`17` NOAA NBM, `4` GribStream; `0` NWS fallback entries), but the
NWS-outlier probe has only `6/10` required entries and the
`bot_d.forecast_resolution` label count remains `0`. Continue at `5` shares;
do not scale until the next live-source/tier review.

**Progress 2026-05-09 top-3 follow-up:** Diagnosed the `0`
`bot_d.forecast_resolution` label count. Runtime source snapshots only wrote
resolution labels if Gamma still returned the daily weather market after the
station's local day completed, which usually misses completed dailies. Added
`record_completed_forecast_resolutions()` to reconstruct completed markets
from recent `bot_d.source_snapshot` payloads, deployed the telemetry-only code
to the bot container, and ran a one-shot backfill. Result: `87` labels for `bot_d` and
`87` labels for `bot_d_live_probe`. No order path, cap, city, size, or
threshold changed. Ongoing automatic emission will take effect after the next
approved Bot D service restart; the one-shot backfill already unblocks the
first source/tier slicing pass.

**Progress 2026-05-09 paper promotion:** ADR-142 adds
`bot_d_source_shadow` as a separate paper-only Bot D lane using the live-shaped
weather settings under `polymarket-bot-d-source-shadow.service`. It exists to
compare source/tier/city slices against the live probe without mixing rows
into `bot_d` or `bot_d_live_probe`. This does not change the live probe, live
size, live caps, city filters, or entry thresholds. OQ-067 still blocks any
live scale decision until the live probe reaches the required source/tier and
outlier-reviewed sample.

**Progress 2026-05-10 live sizing analysis:** Read-only the bot container snapshot at
`2026-05-10T13:13:28Z` found `35` closed live weather lots and `8` open lots
for `bot_d_live_probe`. Current fixed `5`-share realised result is
`+$13.3067` P&L on `$109.5201` cost (`+12.15% ROI`). Price-band results:
`>=50c` `28` closed / `23` wins / `+$10.4827` / `+10.23% ROI`, `<10c`
`4` closed / `1` win / `+$3.8456` / `+349.00% ROI`, and `20-50c`
`3` closed / `1` win / `-$1.0216` / `-17.08% ROI`. Source/tier slices show
NOAA NBM `+19.72% ROI`, multi-model `+12.12% ROI`, GribStream-primary
`-10.32% ROI`, Tier `B` `+23.75% ROI`, Tier `A` `+0.54% ROI`, and Tier `C`
`-100% ROI`. Evidence-gated replay (`<10c=30`, `10-20c=20`, `20-50c=5`,
`>=50c=10`, no scaling for Tier `C`, Seattle/Denver, or GribStream-primary)
would have produced `+$50.0777` on `$180.5601` cost (`+27.73% ROI`) versus
the current `+$13.3067`. Snapshot:
`docs/reports/bot-d-live-sizing-analysis-2026-05-10.md`. No live sizing,
cap, threshold, city, service, order, or redemption change was made.

**Progress 2026-05-10 evidence-gated sizing rollout:** the operator approved the
sizing recommendation. ADR-147 moved `bot_d_live_probe` from fixed `5` shares
to `BOT_D_LIVE_SIZING_MODE=evidence_gated` and raised max order notional from
`$5.25` to `$10`, while keeping daily gross `$100`, open exposure `$150`, and
max concurrent positions `20` unchanged. Ladder: scale only Tier `B`
NOAA-NBM or multi-model entries outside Seattle/Denver; `<10c=30` shares,
`10-20c=20`, `20-50c=5`, `>=50c=10`, capped at `40` dynamic shares. Local
Bot D tests passed (`120 passed`), the bot container focused executor tests passed
(`38 passed`), and only `polymarket-bot-d-live.service` was restarted. First
post-restart cycle completed with `15` markets, `3` edges, `0` orders.

**Progress 2026-05-10 cheap-YES collection loosen:** Post-ADR-147 health
check found `58` entry attempts and no cap/health issue; the recurring
would-buy candidate was a Seattle cheap YES around `4.2-4.3c`, `noaa_nbm`,
`api_agreement_count=2`, blocked only because Tier `C`/Seattle stayed at
`5` shares and therefore fell below the local `$1` minimum. the operator approved
buying this Seattle-style YES. ADR-148 adds a cheap-YES collection lane:
`BUY_YES`, `<10c`, `noaa_nbm` or `multi_model`, and `api_agreement_count>=2`
gets at least `20` shares even if Tier `C` or Seattle, and auto-lifts to the
CLOB `$1` marketable-BUY floor when needed. The live unit sets
`BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=0`; daily gross, open exposure, max order,
max dynamic shares, and concurrency remain unchanged. Local Bot D tests pass
(`121 passed`). This is an evidence-collection loosen, not proof that the
Seattle/Tier `C` slice is profitable.

**Progress 2026-05-11 live order hygiene:** ADR-154 adds two guardrails after
live telemetry showed repeated CLOB rejections for sub-dollar marketable BUY
orders and a GribStream fallback snapshot with `forecast_mean_f=NaN`. Bot D now
blocks non-finite numeric decision inputs before sizing and blocks live BUY
orders below the observed `$1.00` exchange floor even when the local
min-notional env is `0`. ADR-148 cheap-YES remains active because qualifying
cheap YES trades already auto-lift to `$1.00` when the dynamic-share cap
allows it. Dashboard cap display now reads the live systemd unit env so the
operator sees the actual `50` live position slots.

**Progress 2026-05-12 expensive-NO guard:** ADR-156 responds to the NYC May 11
`60-61F` bounded-bucket loser where Bot D bought `NO` at `89.6c` while the
forecast mean was logged inside the YES bucket. Bot D now blocks `BUY_NO`
when forecast mean is inside a bounded YES bucket, raises the expensive-NO
source/distance guard trigger to `80c`, and stops intraday source extrema from
hard-zeroing bounded bucket probabilities.

**Progress 2026-05-12 live recovery:** the operator restored the the bot container tmpfs keystore
passphrase and Bot D live started cleanly. The next blocker was a fleet-cap
mode bug: live-mode cap accounting counted stale paper/archived exposure
because `_bot_is_paper()` trusted shared environment fallbacks before the bot
registry. ADR-157 fixes live/paper fleet-cap filtering to prefer canonical
registry status and cap-member bot ids. After deploy and restart,
`bot_d_live_probe` placed live order
`0xF00D000000000000000000000000000000000003f5afdcf039b26271fd469926` for NYC
May 13 high `66-67F` `BUY_NO`, `10` shares at `70.7c`. OQ-067 remains open
for realised transfer proof and source/tier review.

**Progress 2026-05-13 paper comparator cleanup:** Paper Bot D was active but
not trading because stale paper capacity blocked new entries: `16` old
`PAPER_OPEN` orders and `4` past-end open positions. Ran the DB-only
`cancel_paper_orders.py` cleanup on the bot container and cancelled all `16` stale paper
orders. The paper-resolution reconciler attempted the `4` old positions but
left those rows open due to the existing token/status mismatch path; this no
longer blocks paper trading. Paper Bot D resumed immediately and placed a new
Atlanta May 14 `BUY_NO` paper order at 2026-05-13 16:54 UTC. Live settings
were unchanged.

**Progress 2026-05-13 capacity and expensive-NO update:** the operator approved a
controlled collection-cap increase while keeping per-trade sizing unchanged.
ADR-158 raises Bot D live daily gross from `$100` to `$150` and filled-plus-
resting exposure from `$150` to `$200`. The expensive-NO guard now targets the
recent weak class directly: `80c+` bounded-bucket `BUY_NO` entries still need
source agreement and at least `2F` distance from the YES bucket, and C-tier
setups need at least `12c` absolute net edge. The code and live unit were
deployed to the bot container after backup
`/home/bot/polymarket-bot/data/backups/bot_d_params_20260513T174851Z`; the
live service restarted active and immediately blocked one weak high-priced NO
as `expensive_no_guard:tier_c_edge`. OQ-067 remains open for a post-change
review after at least `20` newly resolved live groups.

**Blocks:** Any Bot D live size increase beyond the ADR-147 ladder plus the
ADR-148 cheap-YES collection lane, any daily-cap or open-exposure increase,
and any claim that Bot D has cleared full live readiness.

**Progress 2026-05-15 aggressive review (ADR-170):** the bot container Bot D live is the
best existing candidate for faster learning. Current host unit already runs
the evidence-gated live probe with `$15` max order, `$300` daily gross, `$400`
open exposure, and `50` concurrent slots. Current DB state shows `2` open
live-probe positions with `$15.90` cost, no open live orders, active scan and
position-validation telemetry, and `20` resolved wallet positions closed by
external sync. ADR-170 recommends a controlled cap bump to `$20` max order,
`$500` daily gross, `$600` open exposure, and `60` concurrent only after
explicit the operator approval; all source, settlement, reconciliation, wallet, and
kill-switch controls remain binding.

**Progress 2026-05-15 deployment:** the operator approved the cap bump and it was
deployed on the bot container. `polymarket-bot-d-live.service` now reports
`BOT_D_LIVE_MAX_ORDER_USD=20`,
`BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=500`,
`BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD=600`, and
`BOT_D_LIVE_MAX_CONCURRENT_POSITIONS=60`. The service restarted active,
derived CLOB credentials, reconciled positions, scanned Gamma, and placed `0`
orders on the smoke cycle because no eligible temperature market passed the
filters.

### OQ-066 — Bot G XRP/DOGE live-universe proof (Empirical)

**Category:** Research-required / live validation.
**Owner:** Empirical; Codex reports; the operator decides any live symbol expansion.
**Surfaced by:** 2026-05-02 question about whether visible XRP/DOGE 15-minute
markets are recorded and could be added later.

**Problem:** ADR-081 expands recording and Bot G paper-shadow collection to
XRP/DOGE, but Bot G Prime Live remains intentionally narrower than the
recorded/paper universe. After ADR-149 the live universe is ETH/SOL only.
XRP/DOGE may have different liquidity, fill quality, spread behavior, and
resolution dynamics, so adding them directly to the live wallet would change
the experiment rather than merely increasing sample.

**Progress 2026-05-02:** Recorder defaults now include XRPUSDT and DOGEUSDT,
market discovery recognizes XRP/Ripple and DOGE/Dogecoin questions, Bot G
paper shadow allows BTC/ETH/SOL/XRP/DOGE, and Bot G Prime Live explicitly
allows only BTC/ETH/SOL.

**Progress 2026-05-09:** Aligned the VPS paper recorder feed with ADR-081:
`longshot-crypto-recorder-vps-paper-feed.service` now records
`BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT` and includes XRP/Ripple plus
DOGE/Dogecoin market tags. Crypto fair-value/Bot I scored paper entries remain
BTC/ETH/SOL-only by config validation; XRP/DOGE are record-only context until
the symbol-split evidence below clears.

**Progress 2026-05-10 ADR-149:** XRP/DOGE remain paper-only under the new
`bot_g_prime_high_tail` benchmark lane (`$1`, `6.5c-8c`, `45s`,
BTC/ETH/SOL/XRP/DOGE). `bot_g_prime_live` is narrower than before at ETH/SOL
only; BTC is no longer live. This keeps XRP/DOGE evidence collection running
without expanding the real-money symbol universe.

**Acceptance criteria:** Before any XRP/DOGE live enablement, report symbol
split sample counts, raw ROI, ex-largest-win ROI, ex-largest-two ROI,
fill/transfer rate, entry slippage, CEX-confirmed split, and `$25`/`$50`
capacity coverage for XRP and DOGE separately.

**Blocks:** Any Bot G Prime Live symbol-universe expansion beyond ETH/SOL.

### OQ-068 — Bot G crypto recorder replay grid for parameter tuning (Empirical)

**Category:** Research-required / Bot G parameter evidence.
**Owner:** Empirical; Claude reports; the operator decides any live parameter change.
**Surfaced by:** 2026-05-05 Bot G live/paper mismatch review and recorder
reframe.

**Problem:** the operator proposed lead-time-dependent bands such as `>60s to <45s =
5c-8c`, `>45s to <30s = 3c-5c`, and `<30s = 1c-3c`. That is a useful
hypothesis, but Bot G live parameters should not be changed from intuition
alone. The shared Crypto Recorder now captures symbol and inferred market
duration metadata, which gives us the raw tape needed to build a replay grid
by lead bucket, price bucket, symbol, duration, book depth, and transfer
quality.

**Acceptance criteria:** Before changing Bot G Prime Live lead windows,
price bands, or symbol universe, produce a recorder-backed report covering at
least lead buckets (`60-45s`, `45-30s`, `<30s`), price buckets (`1c-3c`,
`3c-5c`, `5c-8c`), symbol, market duration, fillable depth, and realised or
proxy outcome. Report raw ROI, ex-largest-win ROI, ex-largest-two ROI, sample
count, fill/transfer rate, and capacity coverage. Any proposed live change
must state the exact systemd/env values and the rollback trigger.

**Progress 2026-05-05 replay grid v1:** Added
`scripts/bot_g_crypto_replay_grid.py` and generated
`docs/reports/bot-g-crypto-replay-grid-2026-05-05.md` from the bot LXC container over a
`72h` window. The first read shows Bot G Prime Live at `36` placed, `31`
filled, `31` closed, `0` wins, `5` no-fills, and `-$71.33` (`-100%` ROI).
The paper shadow shows `53` placed/filled/closed, `4` wins, `+$131.52` raw
(`+71.7%` ROI), but ex-largest-two ROI is `-48.1%`. Live `3.5c-5.5c` has no
winning lead bucket yet; paper's `30s-45s` plus `5.5c-8c` pocket is
interesting but still jackpot-shaped (`8` closed, `2` wins, `+209.4%` raw,
ex-largest-two `-100%`). This does not yet justify a live parameter change.
Next improvement: add fillable depth/capacity from recorder book events so
the grid can distinguish visible cheap quotes from actually fillable size.

**Progress 2026-05-05 paper-shadow phase:** ADR-098 adds a daily
lead-bucket ROI report, a read-only recorder-join diagnostic, and two paper
shadow units without changing Bot G Prime Live. `bot_g_prime_shadow` mirrors
the current live lane (`3.5c-5.5c`, `60s`, BTC/ETH/SOL) so paper/live can be
compared on the same rule. `bot_g_prime_late_cheap` tests the replay-favoured
late-cheap lane (`1c-3c`, `30s` with `5s` fresh-clock floor) in paper only.
No live parameter change is justified until these forward paper lanes and
the live sample reach the agreed evidence thresholds.

**Progress 2026-05-05 operator surfaces:** Dashboard `/api/bot-g` now exposes
the lead-bucket report and the two paper research lanes, and Telegram accepts
`/botg` for a compact read-only Bot G report summary. This is monitoring only;
no live parameter, wallet, cap, or order path is controlled by Telegram.

**Progress 2026-05-10 ADR-149 instrumentation:** Added
`bot_g_prime_high_tail`, a paper-only `$1`, `6.5c-8c`, `45s`,
BTC/ETH/SOL/XRP/DOGE lane. The lead-bucket ROI report, daily probe report,
dashboard research shadows, and VPS node-status summary now include this lane
so ETH/SOL live can be compared against broader paper-only symbol coverage
without changing live risk. Initial order count is `0`; this OQ now collects
the forward sample needed to judge whether the high-tail slice is durable or
still jackpot-shaped.

**Progress 2026-05-05 take-profit paper probe:** ADR-101 adds
`bot_g_prime_take_profit`, a paper-only live-mirror entry lane that
synthetically exits if the recorder best bid reaches `70c` during the final
`25s` to `8s`. ADR-128 lowers the forward paper threshold to `50c` after the
first VPS sample produced no take-profit exits at `70c` and a live loser was
observed marking around `50c` before settlement. This tests the operator's take-profit idea without changing
`bot_g_prime_live`. It is not evidence for a live exit router until it has at
least `50` entries and the result is compared with `bot_g_prime_shadow`.

**Progress 2026-05-05 crypto strategy validation v0:** Added
`scripts/crypto_strategy_validation.py`, a read-only validation harness for
the proposed 5m/15m crypto strategy families. The first local run generated
`docs/reports/crypto-strategy-validation-2026-05-05.md` from the available
`data/bot_e_recorder.db` slice (`42` markets, `841` decision points). This is
not approval-grade evidence because outcomes are CEX-proxy labels rather than
Chainlink final settlement and the local slice is only about `4.6h`.
Headline result under `1c/share` slippage: probability-gap and CEX-order-flow
signals are negative overall, with only small ETH 5m buckets screening
positive. Next improvement: rerun the same script against a copied full
production Crypto Recorder DB and add actual settlement/Chainlink labels
before using the report for any parameter or paper-lane decision.

**Blocks:** Any Bot G Prime Live lead-window/band retune beyond the current
approved `60s` window, `3.5c-5.5c` observed band, and one-tick transfer bid.

### OQ-070 — Bot G live on-chain redemption automation (Claude + the operator)

**Category:** Operations / live settlement accounting.
**Owner:** Claude proposes; the operator approves any automated live wallet action.
**Surfaced by:** 2026-05-05 Bot G parameter audit and resolved-position
cleanup.

**Problem:** Bot G live positions currently resolve in the local DB via the
shared resolver, while on-chain `redeemPositions()` remains a manual sweep.
That was acceptable for the first tiny-live probe, but a future winning Bot G
live position should be redeemable without leaving wallet value stranded or
making dashboard P&L depend only on local resolution events.

**Acceptance criteria:** Before any Bot G size increase, design and test a
Bot-G-safe redemption flow that identifies resolved winning live positions,
simulates `redeemPositions()` on Polygon, requires explicit operator approval
or a separately approved automation rule, records transaction hashes, and
reconciles wallet balance against local realised P&L. The flow must not touch
Ledger treasury funds and must not print or persist secrets.

**Progress 2026-05-05 first winner manual redemption:** the operator explicitly
approved redeeming the first Bot G Prime Live win. The targeted dry run found
exactly one candidate: SOL Down, `31.2` shares, condition
`0xF00D0000000000000000000000000000000000085b42892ff91da10b49a7f735`,
current value `$31.20`, collateral `USDC.e`. Executed one on-chain
`redeemPositions()` transaction:
`92dee5a1a58ea3c85b24730e743e4d39daf20fa98922335c4c1ffa4fce786aa2`,
mined in block `86441968`. A follow-up dry run found zero remaining
redeemable candidates for that condition. Local Bot G settlement was then
reconciled so the dashboard ledger includes the win. Automation remains open:
the current path is still manual approval plus script execution.

**Progress 2026-05-08 zero-value standard sweep:** the operator explicitly approved
the safe zero-current-value sweep by replying `REDEEM`. Ran
`scripts/redeem_resolved_positions.py --execute --yes` on the VPS with the
live passphrase path. All `17` standard, non-negative-risk,
zero-current-value USDC.e redemptions mined successfully in Polygon blocks
`86567025` through `86567041`. Follow-up dry-run reports `11` open wallet rows
and `redeemable_candidates=0` under the safe default filter. A daily Codex
automation was suggested for future dry-run monitoring only; no unattended
on-chain execution was enabled.

**Progress 2026-05-08 standard zero-value automation:** the operator explicitly asked
for full automation. ADR-130 enables `polymarket-redeem-zero-value-vps.timer`
on the VPS. It runs the standard helper daily with `--execute --yes`, but only
under `--standard-zero-value-only` and gas/candidate caps. This resolves the
zero-value standard cleanup portion of OQ-070. Valuable winner rows,
negative-risk adapter redemptions, and condition-targeted claims remain manual
until separately approved.

**Blocks:** Any Bot G live size increase beyond the current `$5` tiny-live
probe and any claim that winner/nonzero-value or negative-risk wallet-realised
P&L is fully automated.

### OQ-072 — Revisit 5m/15m crypto strategy validation on full recorder tape (Claude) [URGENT]

**Category:** Research-required / strategy validation.
**Owner:** Claude.
**Priority:** Urgent next research session; data-only, no trading changes.
**Surfaced by:** 2026-05-05 Session 140 crypto strategy validation harness.

**Problem:** the operator asked whether the proposed 5m/15m crypto Up/Down strategy
families can be validated with existing recorder data. Session 140 added
`scripts/crypto_strategy_validation.py` and produced a v0 local report, but
the local recorder slice is only about `4.6h` (`42` markets, `841` decision
points), uses CEX start/end outcome labels rather than final Chainlink or
Polymarket settlement labels, and is too small to make a strategy decision.
This must be revisited before the idea gets lost or reappears as intuition.

**Acceptance criteria:**

1. Copy or back up the full production Crypto Recorder DB from the bot LXC container; do
   not run heavy analysis against the live writer DB.
2. Rerun `scripts/crypto_strategy_validation.py` over the full copied tape,
   with BTC/ETH/SOL split by `5m` vs `15m`, lead bucket, and symbol.
3. Add actual settlement labels where available, or Chainlink Data Streams
   labels if historical access is available; keep CEX-proxy labels clearly
   marked as provisional.
4. Report probability-gap, Brownian fair-value, closing-window pin fade, CEX
   order-flow, momentum-lag, mean-reversion, BTC lead-lag, and PM imbalance
   results after crypto taker fees and `0.5c`, `1c`, and `2c` per-share
   slippage stress.
5. Report raw ROI, median ROI, ex-largest-win ROI, ex-largest-two ROI,
   sample count, hit rate, and no-fill/missing-book coverage.
6. Make an explicit paper-lane decision: reject, keep data-only, or propose
   a paper-only shadow with exact rules. No live change may follow from this
   OQ without a separate ADR and the operator approval.

**Current evidence:** The v0 local report is
`docs/reports/crypto-strategy-validation-2026-05-05.md`. Under `1c/share`
slippage, after the sampled-volatility scaling correction, probability-gap
screened positive overall (`192` signals, `58.3%` hit rate, `+9.2%` avg ROI,
`+7.9%` ex-largest-two avg ROI). Brownian fair-value was negative overall
(`229`, `50.2%`, `-6.8%`, `-8.7%` ex-largest-two). Closing-window pin fade
was tiny (`16` signals), positive raw (`+16.4%`) but not robust overall
(`-1.7%` ex-largest-two), with a small ETH 5m 45s-120s bucket screening
strongly positive. CEX order-flow stayed negative overall (`249`, `48.6%`,
`-3.2%`, `-5.3%` ex-largest-two), while some ETH 5m buckets screened positive
but are underpowered.

**Progress 2026-05-06 72h validation:** Ran the validator on the bot LXC container against
the copied production recorder snapshot
`data/phase2_snapshots/bot_e_phase2_recorder_72h_20260503T133255Z.db`
(`2026-04-30 13:13:01 UTC` to `2026-05-03 13:32:53 UTC`). Report saved as
`docs/reports/crypto-strategy-validation-72h-2026-05-06.md`. Coverage:
`689` markets and `17,895` decision points, with `8,325` missing PM-price
decision points and `4` missing CEX outcomes. At `1c/share` slippage,
probability-gap screened best (`5,045` signals, `73.6%` hit rate, `+34.4%`
avg ROI, `+33.5%` ex-largest-two). Brownian fair-value also screened strongly
(`5,815`, `71.1%`, `+25.3%`, `+24.7%` ex-largest-two). CEX order-flow was
positive but weaker (`3,897`, `46.3%`, `+5.3%`, `+4.1%` ex-largest-two) and
barely survives `2c/share` slippage. Closing-window pin fade was negative
overall (`191`, `30.9%`, `-4.4%`, `-12.2%` ex-largest-two). Momentum-lag had
only `9` signals despite `100%` hit rate. PM imbalance, BTC lead-lag, and
mean-reversion were negative overall. This still uses CEX-proxy outcome
labels, so the next acceptance step is actual settlement/Chainlink labels and
fill-model calibration before any paper-lane decision.

**Progress 2026-05-06 paper-bot spin-off brief:** Added
`docs/crypto-fair-value-paper-bots-spin-off-2026-05-06.md` so a separate
session can implement two paper-only lanes without re-discovering the strategy
rules. The brief covers `crypto_probability_gap_paper` and
`crypto_brownian_fv_paper`, shared filters, stressed paper-fill tracks,
reporting, gates, tests, and stop conditions. This is still a proposal brief:
no code, service, or live trading setting changed.

**Progress 2026-05-06 paper-bot implementation:** ADR-108 implemented the two
paper-only lanes from the spin-off brief. `crypto_probability_gap_paper` and
`crypto_brownian_fv_paper` now have code, tests, report generation, registry
entries, and systemd unit templates. Only the `1c` stressed track writes the
normal Order/Trade/Position ledger; `0c` and `2c` tracks are preserved for the
report.

**Progress 2026-05-06 paper-live deployment:** The dashboard and crypto
fair-value code were deployed to the bot LXC container. `polymarket-crypto-prob-gap-paper`
and `polymarket-crypto-brownian-fv-paper` were installed, enabled, and active
in paper-live mode; `polymarket-dashboard` was restarted and now exposes
`/api/crypto-fair-value`. The unresolved part of OQ-072 is now actual
settlement/Chainlink labels plus fill calibration before any live discussion.

**Progress 2026-05-09 final paper-lane decision:** ADR-139 archives the two
current Crypto FV paper strategy lanes after forward paper failed robustness.
This resolves the "make an explicit paper-lane decision" clause for
probability-gap and Brownian FV as `reject/archive`. OQ-072 remains useful
only for future recorder-tape research families; it no longer authorizes or
keeps active these two paper services.

**Progress 2026-05-06 Opus audit follow-up:** The paper-live safety verdict
passed. Audit fixes aligned ADR/OQ docs with deployment reality, changed the
paper report DB connection to read-only mode, kept missing-book/stale metrics
as scan-level rather than misleading per-group zeros, added registry
cap-exclusion coverage, widened deployed book freshness to `15s`, and surfaced
book-miss rate on the dashboard. The missing-book rate remains the main
sampling-risk metric to watch before judging 24-hour evidence.

**Progress 2026-05-08 cost & microstructure audit:** ADR-132 ran a read-only
audit (`scripts/research/crypto_fv_microstructure_and_cost_audit.py`,
`docs/reports/crypto-fv-cost-and-microstructure-audit-2026-05-08.md`) against
72 hours of live recorder data — 418 5 m crypto Up/Down markets, 6,062
simulated `$5` paper fills. Two findings: (a) the live 10 s σ sampling step
is **not** biased by microstructure noise (Brownian `σ_per_step ∝ √step`
holds within ~5% on BTC/ETH/SOL); (b) the CEX-proxy gross edge clears
Polymarket taker fees plus a half-spread cost comfortably, netting
`prob_gap +$5,973` (`+40.2%` ROI, `+39.5%` ex-largest-two) and
`brownian_fv +$5,076` (`+32.9%`/`+32.4%`). Cost wedge ~10-13% of gross.
ADR-132 accepts "do not swap σ estimator, do not replace GBM closed form,
do not add HAR-RV/rough vol." The audit changes the prior on the bots from
"possibly structurally negative-EV" back to "edge plausible if Chainlink
agrees with the proxy." It does **not** clear OQ-078; the binding gate
remains real settlement-label evidence plus fill calibration. The
recommended next research step is to replace the OQ-078 fixed-N gate with
a `confseq` betting-CS sequential gate binned by trading day
(Waudby-Smith & Ramdas 2024) — explicitly deferred from ADR-132 and not
yet accepted.

**Historical block before ADR-139:** No Bot G live parameter change, Bot D
live parameter change, or live crypto fair-value proposal should be argued
from these strategy families unless a future ADR reopens them.

### OQ-078 — Crypto fair-value paper verdict and settlement-label gate (Empirical) [RESOLVED 2026-05-09]

**Status:** Resolved 2026-05-09 by ADR-139. Both current paper
strategy lanes are archived; shared recorder infrastructure remains
active data infrastructure.

**Historical note:** The remaining text below records the former gate and
progress trail. It no longer blocks active fleet decisions unless a future
ADR reopens the crypto fair-value strategy lanes.

**Category:** Research-required / paper validation.
**Owner:** Empirical; Claude reports; the operator decides keep/reject.
**Surfaced by:** 2026-05-06 ADR-108.

**Problem:** `crypto_probability_gap_paper` and `crypto_brownian_fv_paper`
are now implemented as paper-only lanes, but the evidence that justified them
uses CEX-proxy labels and retrospective recorder prices. A forward paper
sample is needed, and no live conclusion is valid without actual settlement
or Chainlink labels plus fill calibration.

**Acceptance criteria:** After at least `3` full paper days, and preferably
`7`, run `scripts/crypto_fair_value_paper_report.py` and review each bot by
symbol, duration, lead bucket, side, probability bucket, ask bucket, and fill
track. Keep a bot only if it has at least `500` signals, `150` simulated
filled entries under `1c` stress, `150` closed positions, hit rate at least
`55%`, average ROI under `1c` stress above `3%`, ex-largest-two ROI under
`1c` stress above `2%`, and average ROI under `2c` stress above `0%`.
Before any live discussion, join paper positions to actual Polymarket
settlement labels or Chainlink/Data Streams labels, compare simulated
fill/no-fill against observed exchange behavior, and run `200ms`, `500ms`,
and `1000ms` latency stress.

**Blocks:** Any live crypto fair-value service, wallet setting, size/cap
proposal, or Bot G/Bot D parameter change based on the new paper lanes.

**Progress 2026-05-06 Becker external replay:** The the local workstation Becker replay
weakens the standalone historical case for both crypto fair-value paper
lanes. `docs/reports/crypto-fair-value-becker-model-replay-2026-05-06.md`
scored `49,135,161` executable 15m fills and `$453.1M` notional. Probability
gap had `14,400,173` fills, `38.42%` win rate, `0.3850` average price, and
`-0.25%` average gross ROI. Brownian fair-value had `15,257,206` fills,
`41.07%` win rate, `0.4228` average price, and `-1.91%` average gross ROI.
This did not replace forward paper validation, but Becker replay was not
supportive live evidence. ADR-139 later archived the paper strategy lanes.

**Progress 2026-05-06 survivor stress:** Added
`docs/reports/crypto-fair-value-becker-survivor-stress-2026-05-06.md`.
The survivor report keeps the overall caution but narrows the remaining
historical pocket: under simple bucket-average `2c/share` stress,
probability-gap has `0` cheap `3c-10c` positive buckets, while Brownian has
`12` cheap positive buckets and `174,000` cheap positive fills. The strongest
high-fill cheap survivors are BTC 15m Brownian buckets: UP `120s-300s`
`3c-5c` (`21,365` fills, `7.95%` win rate, estimated `+44.15%` net ROI after
`2c/share`) and DOWN `120s-300s` `3c-5c` (`24,410` fills, `6.89%`,
estimated `+25.15%`). This is not live evidence; it only identifies buckets
for forward paper review.

**Progress 2026-05-06 robustness check:** Added
`docs/reports/crypto-fair-value-becker-robustness-2026-05-06.md`. The
per-fill robustness pass keeps the overall verdict negative after costs:
Brownian `-8.83%` average net ROI after `2c/share`, probability-gap `-8.63%`.
Binance kline coverage is clean for BTC/ETH/SOL (`260,640` rows per symbol,
`0` duplicate minutes, `0` gap events, `0` missing minutes). Walk-forward
cutoff `2025-12-01` leaves only two cheap buckets positive in both train and
test after `2c/share`: Brownian BTC DOWN `300s-600s` `5c-10c` (`5,912` train
fills at `+16.52%`, `57,175` test fills at `+14.72%`) and Brownian BTC UP
`45s-120s` `3c-5c` (`3,016` train fills at `+34.88%`, `16,932` test fills at
`+11.83%`). Calibration is poor outside the lowest decile; predicted
probabilities overstate observed win rates by about `6` to `20` percentage
points. This narrows the forward-paper watchlist but still does not authorize
paper or live parameter changes.

**Progress 2026-05-08 math audit follow-up:** Added
`docs/reports/math-audit-followup-2026-05-08.md`. the bot container read-only reruns of
`scripts/research/crypto_fv_microstructure_and_cost_audit.py` over 24 h and
168 h kept both paper variants positive after fees and half-spread stress:
24 h `brownian_fair_value +$948` / `probability_gap +$1,226`; 168 h
`brownian_fair_value +$9,211` / `probability_gap +$11,166`. The follow-up
also added `scripts/research/math_formula_sensitivity_probe.py`, which found
10s/60s sigma ratios of `0.391-0.405` across BTC/ETH/SOL and 24/72/168/504 h
windows, matching Brownian `sqrt(10/60)=0.408` with no detectable 10 s
microstructure-noise inflation. Even tripling fallback spread costs left 168 h
post-full P&L positive: `brownian_fair_value +$8,634`, `probability_gap +$10,573`.
Caveat tightened: Session 229's "64% missing-book decision points"
used the wrong denominator because the counter increments per generated fill;
fallback-book fill rates in the tagged rerun were `69-88%` by strategy/window.
ADR-132 remains accepted but should be read narrowly: current GBM/sigma math is
good enough for paper-only gating, while settlement labels, fill calibration,
and the fixed-N gate replacement remain unresolved.

**Progress 2026-05-08 label/CI readiness:** Added and ran
`scripts/research/crypto_fv_label_ci_readiness.py`; report:
`docs/reports/crypto-fv-label-ci-readiness-2026-05-08.md`. the bot container has only
`15` crypto FV signals in the 7-day window. No segment clears the `500`
signals / `150` simulated fills / `150` closed sample gate. Best-looking
single segment is not decision-grade: probability-gap BTC 15m `300s+` DOWN
had `1` signal, `3` closed fills, `+66.6%` ROI, and CI `[-100%, +100%]`.
This was the last pre-archive sample blocker before ADR-139 archived the
strategy lanes.

**Progress 2026-05-08 Session 258 audit:** Crypto FV remains sample blocked.
No segment in the 7-day readiness report met the `500` signals / `150`
simulated fills / `150` closed sample gate. Do not use crypto FV to justify a
live bot, Bot G retune, or size/cap change. The fastest useful action is still
more forward rows plus settlement/Chainlink labels, not more parameter search.

**Resolution 2026-05-09 final archive review:** Added
`docs/reports/crypto-fv-final-review-before-archive-2026-05-09.md`
and ADR-139. Current forward paper failed the keep gate. Probability
Gap: `145` signals, `145` 1c-stressed fills, `144` closed,
`71` wins, `-$104.00` fee-adjusted P&L, `-14.4%` ROI,
`-17.1%` ex-largest-win, `-19.7%` ex-largest-two. Brownian FV:
`198` signals, `198` 1c-stressed fills, `196` closed,
`103` wins, `-$100.80` fee-adjusted P&L, `-10.3%` ROI,
`-12.5%` ex-largest-win, `-13.9%` ex-largest-two. Positive cells
were underpowered or winner-sensitive; no active paper edge survives.
Archive both paper strategies, hide FV strategy surfaces, and retain
the shared crypto recorder feed for Bot G/future research under
ADR-122/ADR-081.

### OQ-079 — Becker dataset crypto fair-value validation reports (Claude)

**Category:** Research-required / offline validation.
**Owner:** Claude.
**Surfaced by:** 2026-05-06 ADR-109.

**Problem:** The Becker public dataset is now local on the bot LXC container and queryable,
but no project report yet joins it to the crypto fair-value paper lanes. The
current crypto fair-value evidence still depends on forward paper rows plus
CEX-proxy labels until settlement/fill calibration reports are written.

**Acceptance criteria:** Build read-only reports that use the external
Parquet dataset at
`/home/bot/polymarket-bot/data/external/prediction-market-analysis/repo/data`
without mutating active bot tables. At minimum:

1. Join crypto fair-value paper positions/signals to Polymarket market/token
   metadata and final outcome labels where available.
2. Compare simulated paper entries against chain `OrderFilled` evidence by
   token, time bucket, price bucket, and side to estimate fill/no-fill and
   slippage realism.
3. Compare local Crypto Recorder Polymarket trade events against public chain
   fills for gap detection.
4. Produce probability-gap and Brownian fair-value summaries by symbol,
   duration, lead bucket, ask bucket, model-probability bucket, and fill
   track.
5. Preserve the conclusion in `docs/reports/` and update OQ-078 with whether
   the external settlement/fill evidence supports, weakens, or rejects the
   two paper lanes.

**Blocks:** Treating the Becker dataset as validation evidence for live crypto
fair-value decisions until the reports above exist and are reviewed.

**Progress 2026-05-06 first fill-realism report:** Added and ran
`scripts/crypto_fair_value_becker_fill_report.py` against the the bot LXC container Becker
Parquet dataset. Report saved to
`docs/reports/crypto-fair-value-becker-fill-realism-2026-05-06.md` and
`.json`. Coverage: `71,240` resolved BTC/ETH/SOL 5m/15m Up/Down markets,
`142,480` tokens, `66,461,559` real CTF fills within `600s` of close,
`34,077` markets with fills, and `$1.002B` notional. The 15m comparable
cheap buckets (`3c-10c`, `45s-600s`) show abundant real fills, so the
`paper_taker_*` tracks are plausible for 15m liquidity. Buyer win rates mostly
track entry price (`~2.2%`-`4.0%` in `3c-5c`, `~4.9%`-`7.2%` in `5c-10c`),
so the report validates fillability but does not prove edge. The run found no
matched 5m CTF fills within `600s` despite 5m markets being present; 5m fill
realism remains unresolved pending a follow-up data-shape check or a newer
chain backfill.

**Progress 2026-05-06 the local workstation handoff:** Added
`scripts/backfill_binance_klines.py` and downloaded Binance 1m BTCUSDT,
ETHUSDT, and SOLUSDT klines for `2025-09` through `2026-02` to
`/home/bot/polymarket-bot/data/external/cex/binance/klines/1m`
(`781,920` rows, `260,640` per symbol). Added
`scripts/crypto_fair_value_becker_model_replay.py` for the next
settlement/fill-aware replay, but the first full run was stopped before
completion so the bot LXC container remains reserved for live operations. ADR-110 and
an internal analysis handoff (not exported) move the heavy replay and
5m data-shape investigation to the the local workstation.

**Progress 2026-05-06 the local workstation replay complete:** Copied the public/offline
Becker dataset and Binance 1m klines from the homelab hypervisor `fast-vm` to the Mac
Studio. Local verification: Becker data `50G`, Binance klines `68M`; DuckDB
counts matched the source copy (`408,863` markets, `404,540,000` trades,
`78,468,431` blocks). The the local workstation fill-realism rerun is saved as
`docs/reports/crypto-fair-value-becker-fill-realism-2026-05-06-local-workstation.md`
and `.json`, reproducing `66,461,559` final-600s fills, `34,077` markets with
fills, and `$1.002B` notional. The model replay is saved as
`docs/reports/crypto-fair-value-becker-model-replay-2026-05-06.md` and
`.json`: `49,135,161` scored 15m fills, `$453.1M` scored notional,
probability-gap `-0.25%` average gross ROI, and Brownian fair-value `-1.91%`
average gross ROI. This weakens the standalone historical case for both paper
lanes. The 5m diagnostic is saved as
`docs/reports/crypto-fair-value-becker-5m-fill-diagnostic-2026-05-06.md` and
`.json`; it found `34,290` resolved 5m markets and `68,580` 5m outcome
tokens, but `0` raw CTF fill matches before any lead-window filter. The
corresponding 15m token join found `112,272,154` raw fills across `34,277`
markets. OQ-079 remains partly open for recorder-vs-public-chain gap checks
and any future 5m mapping/backfill investigation.

**Progress 2026-05-06 survivor and 5m follow-up:** Added
`scripts/crypto_fair_value_becker_survivor_report.py` and
`scripts/crypto_fair_value_becker_5m_diagnostic.py`. The survivor report
shows that at `2c/share` stress, probability-gap has `18` positive buckets
but `0` cheap `3c-10c` positive buckets; Brownian has `20` positive buckets,
including `12` cheap positive buckets and `174,000` cheap positive fills.
The 5m diagnostic now checks both CTF and legacy tables: `34,290` resolved
5m markets and `68,580` structurally normal 5m CLOB token IDs match `0` CTF
fills and `0` legacy outcome-token rows. The corresponding 15m token IDs
match `112,272,154` CTF fills. Treat Becker as 15m-only for crypto
fill-realism/model-replay evidence unless a future source explains the 5m
token gap.

**Progress 2026-05-06 robustness report:** Added
`scripts/crypto_fair_value_becker_robustness_report.py` and generated
`docs/reports/crypto-fair-value-becker-robustness-2026-05-06.md` and `.json`.
The report adds per-fill cost stress, walk-forward bucket testing, calibration
deciles, and Binance kline coverage. Overall per-fill strategy stress remains
negative after costs. Only two cheap Brownian BTC 15m buckets pass the
train/test split after `2c/share` stress, while probability-gap has no cheap
walk-forward survivor. Calibration is poor outside the lowest decile, so
Brownian model probabilities should be treated as ranking features, not
decision-grade probabilities.

### OQ-073 — Bot D NOAA NBM transfer review (Empirical)

**Category:** Research-required / live forecast-source evidence.
**Owner:** Empirical.
**Surfaced by:** 2026-05-05 ADR-103 NOAA NBM bypass.

**Problem:** Bot D now has a station-targeted NOAA NBM forecast layer that can
trade during Open-Meteo cooldowns. NBM should be better than single-source NWS
fallback, but it is not yet proven against Bot D's live/paper outcomes.

**Acceptance criteria:** After at least 24 hours with
`BOT_D_NOAA_NBM_ENABLED=true`, report candidate counts, live placed orders,
fills, skip reasons, NWS disagreement rate, and resolved/unrealised PnL split
by `forecast_source` (`multi_model`, `noaa_nbm`, `nws_fallback`). If NBM
creates poor fills or repeated NWS vetoes, disable it and review station/date
parsing before re-enabling.

**Progress 2026-05-09 full Bot D audit:** NOAA NBM is now the dominant
fresh fallback while Open-Meteo is unavailable/cooldown-prone. Latest live
scan at `2026-05-09 14:42 UTC` had `17` raw markets, `11` kept, `11`
evaluated, `0` missing forecasts, and source mix `{"gribstream_nbm": 1,
"noaa_nbm": 10}`. Live forecast-entry source split is `24` multi-model,
`17` NOAA NBM, `4` GribStream, `0` NWS fallback. NBM has improved continuity,
but source-specific realised ROI is not yet decision-grade because resolution
labels are still missing and many closed groups pre-date the current source
payload shape.

**Progress 2026-05-09 source/tier follow-up:** Source labels now exist and
the first diagnostic split is positive for NOAA NBM but still too small for a
live-size decision. Live probe source split by closed lots: `multi_model`
`16` closed / `11` wins / `+$5.8403` / `+12.16%` ROI; `noaa_nbm` `10`
closed / `8` wins / `+$7.4771` / `+23.88%` ROI; `gribstream_nbm` `4`
closed / `3` wins / `-$1.7156` / `-10.34%` ROI. Keep NOAA NBM enabled;
repeat the source split at `50-60` closed live lots.

### OQ-075 — Bot D GribStream and 99c take-profit review (Empirical)

**Category:** Live-probe evidence / provider and exit quality.
**Owner:** Empirical.
**Surfaced by:** 2026-05-05 ADR-105.

**Problem:** Bot D live now has two new tiny-live mechanisms: GribStream NBM
as a paid shortcut ahead of direct NOAA NBM, and a `99c` best-bid
take-profit exit. Both should improve sample collection/capital recycling,
but neither is proven against live fills yet.

**Acceptance criteria:** After at least 24 hours with
`BOT_D_GRIBSTREAM_ENABLED=true` and `BOT_D_TAKE_PROFIT_ENABLED=true`, report
GribStream request count/credit use, forecast-source counts, live orders,
fills, NWS disagreement rate, take-profit triggers, take-profit fill rate,
average take-profit exit bid/limit, stale SELL count, and any ledger
mismatch. Disable GribStream if credit burn is high with no incremental live
orders over direct NOAA. Disable take-profit if stale SELLs or exit mismatches
appear.

**Progress 2026-05-05:** GribStream is live and producing
`forecast_sources={"gribstream_nbm":...}` during Open-Meteo cooldowns.
Take-profit is verified live: position `632` sold `5` NO shares at `0.994`
and is closed locally. The later `not enough balance / allowance` manual FOK
error was a false alarm caused by retrying after the position had already
sold.

**Progress 2026-05-06:** GribStream quota controls were deployed: target-date
only requests, `21600s` cache TTL, and short-circuiting when Open-Meteo plus
direct NOAA NBM already provide two non-NWS sources. The same non-wallet data
settings were added to paper Bot D so source comparisons are fair, with
future reviews required to watch total GribStream credit burn across both
services.

**Progress 2026-05-09 full Bot D audit:** Take-profit is working in live
evidence: `6` `bot_d.take_profit_exit` events in 24h, including best bids
`0.992-0.998`, and no open live exit orders at audit time. GribStream appears
in both paper/live source mixes, but DB telemetry still has `0`
`bot_d.gribstream_call` events, so credit use is not observable from the
dashboard/DB. Keep GribStream enabled for now, but add a call/credit counter
before any larger scan expansion.

**Progress 2026-05-09 telemetry follow-up:** Added
`bot_d.gribstream_call` audit events and dashboard usage counters. Restarted
Bot D paper/live and dashboard to activate telemetry. First post-restart scan
logged combined paper+live GribStream usage of `8` HTTP calls (`4` live,
`4` paper), `0` errors, `254` returned rows, and `10` date forecasts. This
confirms the quota view must be combined across paper and live because the
two processes do not share an in-memory GribStream cache. Current source
evidence remains too small to disable GribStream, but its closed-lot P&L is
negative so far (`4` closed, `3` wins, `-$1.7156`).

### OQ-077 — Bot D NWS-outlier API-agreement probe review (Empirical)

**Category:** Live-probe evidence / entry quality.
**Owner:** Empirical.
**Surfaced by:** 2026-05-05 ADR-107.

**Problem:** Bot D live scans were blocked mainly by NWS disagreements after
GribStream/direct NOAA NBM were added. ADR-107 allows a tiny-live entry only
when at least two non-NWS API sources agree within `2.0°F`, absolute net edge
is at least the live entry floor, and NWS is the moderate outlier no more
than `6.0°F` away.
This should collect evidence faster, but the edge is unproven until live fills
resolve.

**Acceptance criteria:** After at least `10` live
`nws_outlier_probe=true` entries or `7` calendar days, report fill count,
average entry price, realised/unrealised PnL, source mix, API agreement gap,
NWS gap, take-profit interactions, and comparison against ordinary Bot D live
entries. Keep the probe only if realised/unrealised ROI is positive or fill
quality is materially better without new exit/ledger issues. Disable it if
outlier entries underperform ordinary entries or create stale exits.

**Progress 2026-05-09 source/tier follow-up:** NWS-outlier probe is not yet
decision-grade. Current live split: normal entries `25` closed / `19` wins /
`+$11.3343` / `+13.81%` ROI; NWS-outlier probe `5` closed / `3` wins /
`+$0.2676` / `+1.93%` ROI. Keep collecting until at least `10` outlier
entries, but do not loosen around this probe yet.

**Progress 2026-05-09 full Bot D audit:** Live has `6` forecast-entry rows
with `nws_outlier_probe=true`, short of the `10`-entry gate. Recent payloads
show the intended condition shape (`api_agreement_count=2`,
`api_agreement_max_gap_f` under the configured `2.0°F` threshold, and
moderate NWS gaps), but the realised/unrealised split by outlier flag is not
yet large enough to judge. Keep the probe unchanged.

**Progress 2026-05-14 (ADR-167):** Aligned
`BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE` to `0.07` in Bot D live, paper, and
source-shadow units so the outlier probe matches the live entry edge floor.
The two-source agreement and max-NWS-gap constraints remain unchanged. OQ-077
remains open for the same `10` live outlier-entry or `7` calendar-day review.

### OQ-074 — Bot D cross-model dispersion: revisit on resolved-position evidence (Empirical)

**Category:** Deferred / model-refinement gating.
**Owner:** Empirical (resolves once the trigger fires).
**Surfaced by:** 2026-05-05 little-rocky handoff investigation; ADR-104.

**Problem:** A 5-model Open-Meteo cross-model dispersion signal could in
principle improve Bot D in two regimes the existing within-ensemble
std + city-RMSE channel may underweight: marine-layer uncertainty (SF max
mean std `3.71` °F, max `9.05` °F; LA max mean std `3.53` °F) and
orographic cold-air drainage (Denver min mean std `1.94` °F). Cannot be
tested today — Bot D has `0` local fills (`data/bot_d_candidate_quality_report.json`,
2026-05-03) and likely `<15` resolved positions on the bot LXC container.

**Trigger to revisit (all required):**

1. Bot D has at least `15` resolved paper positions in the
   `station_v1_2026_04_29` epoch (or successor) with audit-logged
   `bot_d.forecast_entry` events recording
   `forecast_mean_f`, `forecast_std_f`, `settlement_station`,
   `bucket_low_f`, `bucket_high_f`, `forecast_source`.
2. Realised net edge per position after `1.25%` round-trip fees is
   non-negative on those positions (per the kill-date threshold spirit;
   if edge is already negative the migration is moot).
3. Operator agrees to spend ~1 day pulling LXC data and re-running the
   experiment.

**Unblock checklist (when the trigger fires):**

1. Export from the bot LXC container:
   `sqlite3 /home/bot/.local/share/polymarket-bot/main.db "SELECT created_at, payload FROM events WHERE bot_id='bot_d' AND event_type='bot_d.forecast_entry'" > /tmp/bot_d_forecast_entries.jsonl`
   plus the corresponding `trades` + `positions` rows for FIFO PnL match
   (use `scripts/bot_d_readiness_report.py` as the reference resolver).
2. For each entry, fetch the 5-model `_seamless` historical forecast for the
   `settlement_station` lat/lon at the entry timestamp's market date using
   the reproducible probe in
   `docs/reports/bot-d-cross-model-dispersion-baseline-2026-05-05.md`.
3. Compute cross-model std at trade time; segment hit rate and realised
   net edge by std quartile.
4. Decision rule: migration is worth shipping only if the top-std quartile
   shows materially worse hit rate than the bottom quartile *after*
   controlling for Bot D's existing `forecast_std_f`. If the cross-model
   signal is collinear with what `adjusted_std` already captures, the
   migration adds complexity without information.

**Acceptance criteria:** A successor ADR (proposing migration or
permanent rejection) cites the resolved-position study results, including
the controlled-for-`adjusted_std` regression coefficient and per-quartile
hit-rate split.

**Blocks:** Any future migration of `little-rocky/research/clients/openmeteo.py`,
`little-rocky/research/signals/dispersion.py`, or HDD/CDD primitives into
Bot D, sidecar or otherwise.

### OQ-065 — Kalshi UK eligibility and venue-add decision (the operator + Kalshi)

**Category:** Decision-required / venue eligibility.
**Owner:** the operator; Kalshi support or counsel must confirm eligibility if this
venue is pursued.
**Surfaced by:** 2026-05-02 Kalshi blocker research.

**Problem:** Kalshi's 2026 help center says international access is available
in many countries, subject to the Kalshi Member Agreement, but the current
Kalshi Member Agreement restricted-jurisdiction list explicitly includes the
United Kingdom. The operator is UK-based. Adding Kalshi as a live venue would
therefore require a lawful eligibility path before any production API key,
funding, live order path, or venue integration work.

**Acceptance criteria:** Before any Kalshi live implementation, record one of:
written Kalshi confirmation that the operator is eligible to trade from the
operator's actual residence/access posture; a Member Agreement update removing
the United Kingdom restriction; or the operator's explicit decision to keep Kalshi
research/demo-only. If eligibility clears, write a new ADR covering venue
scope, tax/accounting treatment, custody/secrets, API usage limits, and whether
Kalshi is a standalone venue or only a public-data research feed.

**Blocks:** Any Kalshi live API key handling, funding path, production order
placement, real-money Kalshi bot, or cross-venue Polymarket-Kalshi execution.

### OQ-060 — Bot B public spin-off boundary (the operator + Claude)

**Category:** Decision-required / productization.
**Owner:** the operator decides posture; Claude prepares the redaction and release
checklist.
**Surfaced by:** 2026-05-02 active fleet revamp.

**Problem:** the operator wants to consider making Oraclemangle Kelly (Bot B) a
standalone public repo on GitHub and Hugging Face while selling the
oraclemangle resolution edge as the paid service. The repo is currently
private, operational, and mixed with homelab, wallet, runbook, and strategy
history that must not be exported blindly.

**Acceptance criteria:** A separate spin-off plan defines public/private
boundaries, removes operator-specific infra and history, replaces private
scorer calls with a documented interface, confirms no secrets/wallet material
or HMRC-relevant logs are present, and states what value remains free without
oraclemangle access.

**Progress 2026-05-02:** Bot B and Bot B Shadow were parked out of active
dashboard/API/reboot-readiness surfaces by ADR-072. Code, tests, history, and
this spin-off question remain intact; publicization is still deferred.

**Blocks:** Any public Bot B repo creation or Hugging Face publication.

### OQ-057 — Rotate Telegram bot token exposed in historical journald logs (the operator)

**Category:** Decision-required / security.
**Owner:** the operator.
**Surfaced by:** Session 41 V2 post-deploy journal scan on 2026-04-28.

**Problem:** Before Session 41, `httpx` INFO request logging printed full
Telegram API URLs in journald. Telegram embeds the bot token in the URL path,
so historical `polymarket-watchdog` / `polymarket-notify` logs contain the
old token.

**Mitigation already shipped:** `core.notify` now sets `httpx` and
`httpcore` loggers to WARNING when notification support is imported. After
restarting `polymarket-watchdog` and `polymarket-notify`, fresh journal scans
no longer showed full `httpx` request URLs.

**Unlocks:** Restore clean Telegram credential posture.

**Acceptance criteria:** the operator rotates the bot token via BotFather, updates
the bot LXC container `.env`, restarts `polymarket-watchdog` and `polymarket-notify`, and a
fresh journal scan shows no full Telegram API URLs. Consider journald vacuum /
retention trimming only after deciding how much incident history to preserve.

### OQ-004 — HMRC advisor engagement (the operator + Advisor)  [DEFERRED by the operator 2026-04-15]
the operator confirmed: deal with tax after profit is proven. Build continues with HMRC-ready logging in place (every trade stores `usd_gbp_rate` + `gbp_notional`) so the audit trail exists when it's time to engage an advisor. No code change.

Per ADR-010, the operator engages a chartered UK tax advisor in parallel with build. Specific question to put:
> "Does HMRC treat Polymarket ERC-1155 conditional-token PnL as CGT cryptoasset disposal, miscellaneous income, trade, or gambling for a UK-resident individual running an automated bot on an offshore venue?"
**Unlocks:** Tax-posture ADR-010 moves from "working assumption" to "confirmed" (or forces re-assessment).
**Status:** Not engaged.
**Cost:** ~£200 for a written opinion from a crypto-literate tax adviser.

### OQ-005 — Treasury wallet funding mechanics (the operator)  [DEFERRED by the operator 2026-04-15 — the operator will research]
How does fiat → USDC.e land in the Ledger treasury? Options:
- CEX (Kraken, Coinbase) → withdraw to Ledger → bridge to Polygon
- Direct Polymarket deposit bridge (supports 15 chains per CLOB spec)
- Moonpay / similar on-ramp
Each has different KYC, fee, and speed characteristics.
**Unlocks:** Concrete top-up runbook.
**Status:** Unresolved.

---


## Research-required (Claude can resolve)

### OQ-087 — Helsinki↔Betfair London latency feasibility for in-play execution (Claude/Empirical)

**Category:** Research-required / blocking-for-Bot-H-trader-promotion (not blocking for recorder).
**Owner:** Empirical (resolves via Bot H recorder once running).
**Surfaced by:** Session 211 addendum to adjacent-market edge survey (`docs/reports/adjacent-market-edge-survey-2026-05-07.md`).

**Problem:** The strategy-adversary verdict on a Betfair *trader* names Helsinki↔Betfair-London latency as a primary kill-argument: "a small EU VPS. You will be last in queue on every price that matters; your fills will be the toxic ones." The body of the survey recommends a paper-only recorder; this question only blocks the *trader* phase (post-2026-06-06).

**Resolution path:** Bot H recorder captures stream-event arrival timestamps + Betfair's reported event timestamps. Compute distribution of `(Bot_H_arrival - Betfair_event)` across 30 days. Compare against displayed-price-stale duration (how long is each price visible before the next update?). If `arrival_delay > stale_duration` for >50% of in-play ticks at the candidate edge windows, the latency adversary verdict is empirically confirmed.

### OQ-088 — Betfair Premium Charge accrual timeline at $5k-$50k operator scale (Decision-required)

**Category:** Decision-required (post-recorder phase; affects any trader EV calc).
**Owner:** the operator.
**Surfaced by:** Session 211 addendum.

**Problem:** Premium Charge (PC) activates above £250k lifetime profit AND >250 profitable markets AND charges-paid <20% of gross profit; marginal rate 20-60% on net winnings. The threshold timing affects the EV calculation for any Betfair trader build. At $5k bankroll generating hypothetically 50% annualized, lifetime £250k is years away. At $50k it's months. Decision input: at what realistic monthly P&L trajectory does PC start consuming edge?

**Unlock condition:** post-recorder; only relevant if Bot H promotes to trader phase.

### OQ-089 — Insight Prediction order-book depth distribution (Claude)

**Category:** Research-required / blocks any Insight port consideration.
**Owner:** Claude (1-day spawn-task).
**Surfaced by:** Session 211 addendum; the F5 capital-tier-mismatch concern dominates Insight's structural-edge thesis.

**Problem:** Insight Prediction has reportedly $2-10M TVL (vs Polymarket's $100M+). If most markets have <$500 best-ask depth, $5k positions are not capacity-feasible without observable price impact. Question: across active Insight Prediction markets in the operator's target categories, what is the distribution of best-ask + first-3-levels depth? At what fraction of markets can a $5k position fill without moving price more than 2pp?

**Unlock condition:** spawn-task on Insight API or web-scrape; ~1 operator-day.

### OQ-090 — Pinnacle UK retail accessibility in 2026 (Claude)

**Category:** Research-required / blocks Asian Handicap consideration.
**Owner:** Claude (30-min compliance check).
**Surfaced by:** Session 211 addendum.

**Problem:** Pinnacle is famously sharps-friendly (no account limits) and a key part of the lower-division-football soft-lines edge thesis. UK retail access has historically been gated; FCA rules around offshore-bookmaker access for UK customers may make this a grey area. Per the operator's "no grey areas" constraint, this is dispositive for the Asian Handicap candidate.

**Unlock condition:** verify Pinnacle's 2026 UK retail policy and whether VPN access is required for UK operators (which would violate the grey-area constraint).

### OQ-091 — GCP project `divine-beach-486012-p4` billing disabled (Claude/the operator)

**Category:** Research-required / non-blocking infrastructure side-issue.
**Owner:** the operator + Claude.
**Surfaced by:** Session 211 addendum (encountered when `gemini-vertex-pro` returned `403 PERMISSION_DENIED` due to disabled billing on the legacy GCP project).

**Problem:** `~/Code/CLAUDE.md` already notes that `divine-beach-486012-p4` is no longer accessible from the current account (permission denied as of 2026-05-01). The 2026-05-07 fallback model call discovered the error is now "billing disabled," not "permission denied" — different failure mode. The active project for LLM routing is `project-8ac59f14-ef70-4f26-ad6` ($300 Vertex credit), and `vertex-pro`/`vertex-flash` are the working aliases. This is a `~/.claude/.env` follow-up: ensure `model_call.py` 3-way consensus in this repo's CLAUDE.md is hitting current-billed providers.

**Unlock condition:** rotate any code or docs that still reference `divine-beach`-backed aliases; or update `~/.claude/models.yaml` so the `gemini-pro` alias points at the active project. Non-blocking for this repo.

---

### OQ-093 — Bot D EMOS/NGR shadow calibration benchmark (Claude)

**Category:** Research-required / Bot D probability calibration.
**Owner:** Claude.
**Surfaced by:** 2026-05-08 math formula audit follow-up
(`docs/reports/math-audit-followup-2026-05-08.md`).

**Problem:** ADR-024's skew-normal tail layer and hard `>=2` source agreement
guard are no longer the best available weather math baseline. 2022-2026
temperature post-processing literature supports station/lead-time/season-aware
EMOS/NGR, source-weighted BMA, and CRPS/Brier-scored benchmarks. Bot D does
not yet have a shadow benchmark that tests whether source disagreement should
be a calibrated variance/weighting feature instead of a binary allow/block.

**Acceptance criteria:** Build a read-only shadow benchmark that joins resolved
Bot D station/source observations to forecast-entry payloads and outputs
Gaussian/skew-normal current baseline vs EMOS/NGR-style calibration by station,
lead bucket, season, source set, and threshold distance. Report CRPS for the
temperature CDF, Brier/log loss/reliability for tradable YES/NO thresholds, and
realized EV after spread/fees/fill assumptions. No live guard or Bot D
parameter changes until the shadow model beats the current gate by station and
lead-time buckets.

**Progress 2026-05-08:** Phase 0/1 scripts implemented and run read-only on
the bot LXC container. Phase 1 failed before model fitting: `109` Bot D forecast-entry rows,
`0` joined settlement/source labels, `0` labeled rows. Report:
`docs/reports/bot-d-emos-shadow-benchmark-2026-05-08.md`. Blocker tracked in
OQ-096.

**Progress 2026-05-08 NWS observation join:** implemented and ran
`scripts/research/bot_d_emos_nws_observation_join.py` read-only on the bot LXC container to
join Bot D forecast entries to official NWS station observations. Report:
`docs/reports/bot-d-emos-nws-observation-join-2026-05-08.md`; raw artifact:
`data/reports/bot_d_math/emos_nws_observation_join_20260508T193706Z.{md,json}`.
Result: **FAIL**. The probe found `112` forecast-entry rows, `90`
complete-day rows, `88` NWS-supported rows, and `52` labeled rows, but no
station/lead bucket reached the `>=30` labeled-row gate. No EMOS/NGR/BMA score
is decision-grade yet, and no Bot D live parameter change is justified.

**Progress 2026-05-08 safe rollout:** Bot D source telemetry now writes
`observed_temperature_f`, `yes_resolved`, and one deduplicated
`bot_d.forecast_resolution` event per completed station/day market. The
EMOS/NGR shadow benchmark now consumes those resolution events before falling
back to source-snapshot labels. This unblocks future scoring once enough rows
accumulate; it does not change Bot D entry math or live parameters.

**Progress 2026-05-08 deployment:** deployed the Bot D forecast-resolution
telemetry to the bot container and restarted `polymarket-bot-d.service` plus
`polymarket-bot-d-live.service`; both returned `active`, and the recorder
remained `active`. the bot container had `0` `bot_d.forecast_resolution` rows immediately
after deployment because no completed station/day snapshot had been emitted
under the new code yet; existing `bot_d.source_snapshot` rows remain intact.

**Progress 2026-05-09 full Bot D audit:** the bot container still has `0`
`bot_d.forecast_resolution` rows for both `bot_d` and `bot_d_live_probe`
all-time. The source snapshots themselves are healthy (`1,606` live-probe
snapshots in the last 24h), but final resolution labels have not started
flowing. EMOS/NGR/BMA remains blocked on durable labels, not model code.

**Parking note 2026-05-09:** Do not lose the researched maths. EMOS/NGR,
source-weighted BMA, CRPS/Brier/log-loss scoring, reliability/resolution
decomposition, and source-dispersion-as-variance should be promoted into Bot D
only after the shadow benchmark becomes viable. Viability means: at least one
station/lead bucket has `>=30` labeled rows, the EMOS/NGR or BMA shadow model
beats the current Bot D skew-normal/source-gate baseline on Brier and log loss
in that same bucket, realized EV after fees/spread/fill assumptions does not
degrade, and reliability is neutral-or-better. Until those gates pass, Bot D
live remains on the current skew-normal + source-agreement guard and the new
math stays research/shadow-only.

### OQ-103 — Bot D Polymarket settlement rounding/floor rule verification (Claude/Empirical)

**Category:** Research-required / Bot D settlement correctness.
**Owner:** Claude verifies active market rule text and joins to actual
Polymarket resolutions; Empirical resolves via future counterfactual telemetry.
**Surfaced by:** 2026-05-10 Grok/Gemini weather-source review and
`docs/reports/bot-d-rounding-audit-2026-05-10.md`.

**Problem:** Bot D currently uses `nearest_int` settlement rounding unless a
city explicitly overrides it. Gemini claimed Polymarket temperature markets
truncate/floor instead of round. A the bot container telemetry audit found material
nearest-vs-floor sensitivity: `97 / 2,000` usable live-probe raw-station rows
and `11 / 147` completed live forecast-resolution labels would differ under
floor/truncate, concentrated in Fahrenheit markets near whole-degree
boundaries. This proves the rule matters, but it does not by itself prove the
oracle floors across all cities/sources.

**Acceptance criteria:** For each verified/live Bot D city, record exact active
Polymarket rule text or settlement evidence for rounding/truncation behaviour.
Join the `11` live `bot_d.forecast_resolution` disagreements to actual
Polymarket resolved outcome where available. If a city/source is confirmed to
floor/truncate, update only that city's `SettlementSpec.rounding`, add tests,
and log an ADR before live deployment.

**Current status:** Telemetry-only counterfactuals were added to source and
resolution payloads. The first actual-outcome join found `8 / 11` completed
live disagreements matched `nearest_int` and `3 / 11` matched `floor`, so live
decisioning remains unchanged. Re-run at `30` completed live disagreements or
on explicit rule-text evidence.

### OQ-104 — Bot D Tomorrow.io shadow-source transfer review (Empirical)

**Category:** Empirical / Bot D forecast-source validation.
**Owner:** Empirical.
**Surfaced by:** 2026-05-10 Grok/Gemini weather-source review and operator
request to shadow-test Tomorrow.io without affecting live entries.

**Problem:** Bot D currently relies on Open-Meteo, GribStream NBM, direct NOAA
NBM, NWS, METAR, and WU/Weather.com source telemetry. Tomorrow.io may provide a
useful independent/proprietary comparison source, but it must not influence
live entries until its station-level transfer quality is measured against
actual settlement outcomes.

**Acceptance criteria:** With `TOMORROW_API_KEY` configured, collect at least
`50` Bot D source snapshots with `tomorrow_io_snapshot.status == "ok"` and at
least `20` completed station-day comparisons. Report average error, average
absolute error, error by city/station, and whether Tomorrow.io improves or
worsens the source panel against realised settlement observations. Do not add
Tomorrow.io to `api_highs_f` / `api_lows_f` or any live gate before a reviewed
report and ADR.

**Current status:** Shadow-only plumbing deployed 2026-05-10. Without a
`TOMORROW_API_KEY`, events record `missing_key`; with a key, source snapshots
will log `tomorrow_io_snapshot`, `tomorrow_io_value_f`, and
`tomorrow_io_gap_to_station_f`. The source-edge report now summarizes
Tomorrow.io status and station-day gaps.

### OQ-094 — Bot G discrete hazard, score decomposition, and tail concentration audit (Claude) [RESOLVED 2026-05-09]

**Category:** Research-required / Bot G longshot validation.
**Owner:** Claude.
**Surfaced by:** 2026-05-08 math formula audit follow-up
(`docs/reports/math-audit-followup-2026-05-08.md`).

**Problem:** Bot G Prime's 3.5-5.5c rules are currently evaluated with
aggregate hit rate and ROI style reports. For low-base-rate longshots, the
right first audit is a discrete lead-bucket hazard table plus probability-score
decomposition and tail-concentration diagnostics. Without that, a profitable
bucket can be one or two sparse wins rather than repeatable resolution.

**Acceptance criteria:** Build a read-only report that emits candidate rows by
price bin, lead bucket, side, symbol, volatility bucket, resolved outcome, and
max best bid before close. Report win-given-alive hazard, best-bid spike
hazard at `10c`/`20c`/`50c`, Brier reliability/resolution/uncertainty, log
loss, top-1/top-2/top-5 P&L contribution, ROI ex-largest-k, and bootstrap
confidence intervals by market-day and symbol. No Bot G parameter or sizing
change until this audit is reviewed.

**Progress 2026-05-08:** Phase 2 script implemented and run read-only on the bot LXC container. Gate failed: `154` orders, `149` closed, `90` quoted for spikes; no cell
cleared positive post-cost ROI, lower bootstrap CI > 0, >=10 wins, resolution
> 0, and top-2 concentration < 80%. Report:
`docs/reports/bot-g-hazard-score-audit-2026-05-08.md`.

**Correction 2026-05-08 Codex audit:** Phase 2 script now reconstructs a
placed-fill lead-bucket panel and fits the discrete-time hazard models on
panel rows with the shared King-Zeng rare-event correction primitive. The
Phase 2 gate still fails; rerun on LXC before treating per-event hazard
coefficients from the original report as final.

**Status 2026-05-09 — RESOLVED.** The 2026-05-08 hazard audit, take-profit
replay, and 2026-05-09 final review (`docs/reports/bot-g-final-review-2026-05-09.md`)
all converge on the same finding: no Bot G Prime cell clears the
combined gate of post-cost ROI, lower bootstrap CI > 0, ≥10 wins,
resolution > 0, and top-2 concentration < 80%. Take-profit replay
shows 0/26 positions hit the 50c threshold. The discrete-hazard /
score-decomposition / tail-concentration audit is complete; the
answer is **no surviving cell**. No further parameter or sizing
change to Bot G is justified by the math audit. ADR-135 stands.

### OQ-095 — Fleet probability score decomposition layer (Claude)

**Category:** Research-required / cross-bot evaluation.
**Owner:** Claude.
**Surfaced by:** 2026-05-08 math formula audit follow-up
(`docs/reports/math-audit-followup-2026-05-08.md`).

**Problem:** The fleet still mixes calibration, discrimination, executable EV,
and replay quality in strategy-specific reports. Proper scoring literature
requires separating reliability/calibration from resolution/refinement, and the
prediction-market microstructure literature requires fees, spreads,
maker/taker role, missing-book rate, and settlement risk to be reported beside
probability quality.

**Acceptance criteria:** Build a read-only fleet scoring report for Bot D, Bot
G, and crypto fair-value paper lanes with Brier, log loss, spherical score,
reliability, resolution/refinement, ROI, spread, fees, missing-book rate,
settlement-label source, and fill/no-fill calibration. The report must make it
possible to distinguish "probabilities are calibrated" from "the trade is
executable after costs."

**Progress 2026-05-08:** Phase 3 script implemented and run read-only on the bot LXC container. Reporting gate passed with `188` scored decision rows and populated
sequential CI columns. Bot D contributed no rows because OQ-096 blocks labels;
crypto FV rows are tagged `proxy-only`. Report:
`docs/reports/fleet-probability-score-decomposition-2026-05-08.md`.

**Correction 2026-05-08 Codex audit:** Phase 3 now uses the shared
`sequential_ci` primitive instead of an inline confidence-sequence helper.
The reported intervals are 95% confidence sequences (`alpha=0.05`), not
90% intervals. The pass-gate verdict is unchanged.

---

### OQ-099 — Wallet-tag forward-validation gate before any bot-feature plumbing (Claude + Empirical)

**Category:** Research-required / forward validation.
**Owner:** Claude implements the observer + report; Empirical validates
the forward sample; the operator decides bot-feature plumbing.
**Surfaced by:** 2026-05-08 wallet-tag Murphy decomposition
(`docs/reports/wallet-tag-edge-finding-2026-05-08.md`).

**Problem:** The wallet-tag math primitives finding (PolyVerify
`bot_score < 30` cohort, +10.7pp edge, 95% CI [+4.4%, +184.8%] on 25,092
recent WANGZJ trades) is the first decision-grade edge candidate from
the math research cycle. Two independent halves of the cohort pass the
gate. But:

1. PolyVerify scrape from May 2026 has selection bias toward
   surviving wallets.
2. All numbers are historical. A live forward sample is needed to
   confirm the edge persists in real time, not just in the WANGZJ
   training cache.
3. CLAUDE.md scope kill-list rejects direct copy-trading. This
   finding is "wallet-tag features (Variant B)" — feature input, not
   direct copy. Operator approval is required before plumbing into any
   bot.

**Acceptance criteria (7-day forward window — see ADR-137,
operator decision 2026-05-08):**

1. Enable `polymarket-wallet-tag-forward.{service,timer}` on the bot container (or
   accept the operator's preferred host).
2. Enable `polymarket-wallet-tag-forward-resolutions.{service,timer}` to
   populate market settlement labels via Polymarket Gamma every 6h.
3. Run both timers for **7 days** (operator decision 2026-05-08; 30
   days was deemed too long). Target sample: ≥ 200 settled wallet
   trades for the bot_score_low_under_30 cohort.
4. Run `scripts/research/wallet_observer_report.py` and verify the
   forward Murphy decomposition for the cohort:
   - n ≥ 200 settled trades (verdict says INSUFFICIENT below this)
   - Resolution > 0.001
   - Top-2 P&L concentration < 50%
   - Bootstrap 95% CI lower bound on ROI > 0
5. If all four gates clear, write a new ADR proposing plumbing the
   wallet-tag feature into Bot D / Bot G / crypto FV as a
   candidate-filter input. **No copy-trading bot.**
6. If any gate fails, the edge was historical artifact. Disable both
   observer services, archive the data, do not promote.
7. If sample is INSUFFICIENT after 7 days, decide: extend window or
   accept that cohort throughput is too low for the forward gate.

**Why 7 days, not 30:** the 60-wallet cohort already produced 25k
trades over 90 days (~278/day) in the WANGZJ historical panel. At a
similar rate the forward observer will accumulate ~1.9k captured
trades in 7 days, of which ~10-30% should settle inside the window
(short-TTR markets). A 7-day window is plenty for the cohort-level
gate; the per-wallet sub-cohorts may be informational only.

**Open work to enable forward validation:**

1. ~~Operator must `sudo systemctl enable --now
   polymarket-wallet-tag-forward.timer` on the bot container.~~ **DONE 2026-05-08
   21:32 UTC.** Timer enabled and active on the bot container; first service run
   completed `exit=0`, 34.9 MB peak, 912 ms CPU; 212 successful HTTP
   polls, 0 errors; observer DB seeded with 17,884 historical trades
   from the 106 wallets.
2. ~~The observer DB needs a market-resolution backfill loop.~~ **DONE
   2026-05-08 21:49 UTC.** `wallet_observer_resolutions.py` deployed
   with `polymarket-wallet-tag-forward-resolutions.{service,timer}` on
   the bot container. First run `exit=0`, 13s wall clock, 260/500 markets fetched
   from Gamma (52% hit rate within 14-day age filter). Trades observer
   timer tightened from 30min to 15min cadence to halve the miss-rate
   on ttr<1h markets within the new 7-day forward window.

3. **Session 258 audit health check:** the bot container timers are active. Latest
   observer run completed successfully after polling `106` wallets, adding
   `24` new trades, and logging `0` errors. The DB held `17,930`
   `observed_trades`, `260` `observed_markets`, `424` `poll_log` rows,
   latest ingest `2026-05-08T22:06:28Z`, latest poll
   `2026-05-08T22:07:04Z`, and `0` poll errors. Gate remains open until the
   7-day settled-trade report passes the Murphy/top-k/bootstrap criteria.

4. **Session 261 closeout health check:** the bot container `/api/wallet-observer` is
   live and uses the VPS bridge with `data_source=vps`. The bridge reports
   `polymarket-wallet-observer.service` active, observer DB `79,761,224`
   bytes, `87,740` total fills, `65,182` fills in 24h, `87,734` fills in 7d,
   `58` distinct active wallets in 24h, latest fill age `26s`, Tier A
   `62,379` fills / `38` wallets, Tier B `2,803` fills / `20` wallets.
   This confirms collection health only; the forward validation gate remains
   settlement/Murphy/top-k/bootstrap based.

5. **Session 265 Bot I Persistence audit:** Added
   `docs/reports/bot-i-persistence-audit-2026-05-09.md`. The audit found no
   implemented `bot_i`; the only explicit Bot I backlog item is the unrelated
   price-ceiling directional prototype. For wallet persistence, keep observing
   but do not promote into any bot until two forward-gate blockers are fixed:
   (a) Data API observed trades use condition IDs as `market_id`, while Gamma
   backfill upserts numeric Gamma IDs into `observed_markets.market_id`, so the
   report join cannot reliably attach settlements; (b) the forward report
   scores all BUY trades as YES buys and ignores NO-token buys. Local DB state
   during audit: `17,882` observed trades, `86` observed markets, `0` settled
   markets. Focused tests `35 passed`.

6. **Session 266 blocker fixes:** Patched the forward-gate path so
   `condition_id` is the canonical settlement join key, Gamma numeric IDs no
   longer break the report join, and YES/NO BUY rows are scored by the bought
   token side. The the bot container forward-gate DB is now `data/wallet_tag_forward.db`;
   VPS Polygon event-recorder DB remains `data/wallet_observer.db`.

7. **Session 276 strategy-ranking pre-gate audit (2026-05-09):**
   Read-only inspection of the bot container `data/wallet_tag_forward.db`
   surfaced a mechanical risk that the gate at `T+7 = 2026-05-15`
   returns `INSUFFICIENT` regardless of cohort behaviour, because no
   markets are reaching the current settlement criterion:
   - 18,653 `observed_trades`; 309 `observed_markets`; **`0` settled
     markets**.
   - Trade age distribution: <1h=75; <6h=154; <24h=1,015; <3d=1,292;
     <7d=1,186; <14d=1,679; **>=14d=13,258 (legacy seed; backfill
     skips by `--max-age-days 14`)**. The actual forward sample is
     the **1,186 trades inside the 7-day window**.
   - Of 309 fetched markets: 271 are mid-shape, 31 are `YES_almost`
     (`["0.999*","0.001*"]`), 7 are `NO_almost` (`["0.001*",
     "0.999*"]`), **0 are decisive `["1","0"]` / `["0","1"]`**, and
     all 309 are `closed=0`. Polymarket's observed pattern is that
     closed markets dwell at the "almost" shape for hours-to-days
     before flipping decisive. The current
     `wallet_observer_resolutions._parse_outcome_prices` requires
     `abs(first - 1.0) < 1e-9` OR `abs(first) < 1e-9`, so the
     "almost" shape is treated as unsettled.

   **Recommended pre-gate data modification (P0 this week):**
   1. Add a relaxed proxy criterion to the resolution backfill:
      treat `outcomePrices[0] >= 0.999 OR <= 0.001` after
      `end_date_iso < now` as `proxy_settled = 1` with the
      corresponding `yes_won` label, while keeping `settled = 1`
      reserved for the strict closed+decisive shape.
   2. Widen `--max-age-days` from 14 → 30 so 7-day-window markets
      that take 14+ days to officially close are still labelled by
      backfill before the gate fires.
   3. Update `wallet_observer_report.py` to use `proxy_settled = 1`
      AS A FALLBACK ONLY when `settled = 1` count is below the
      cohort threshold; report both shapes in the markdown so the
      operator can audit.
   See `docs/reports/strategy-ranking-and-data-roadmap-2026-05-09.md`
   for the full evidence packet and ranking context.

8. **Session 284 implementation:** Patched the the bot container forward-gate
   resolution path locally for the P0 pre-gate data modification.
   `scripts/research/wallet_observer_resolutions.py` now adds
   backwards-compatible `proxy_settled` and `settlement_method` columns,
   treats `outcomePrices[0] >= 0.999 OR <= 0.001` after market
   `endDate` as a proxy-settled label, keeps strict `settled = 1` reserved
   for `closed=True` plus exact `0/1` outcome prices, skips already
   proxy-settled markets in future backfill passes, uses the configured
   HTTP rate-limit argument, and defaults `--max-age-days` to `30`.
   `scripts/research/wallet_observer_report.py` now uses proxy labels only
   while the strict-settled BUY sample is below the `200`-trade gate and
   reports strict/proxy counts plus the settlement scoring mode. Focused
   regression coverage confirms exact labels remain strict-only, near-final
   post-end markets score via proxy, pre-end near-final markets do not
   settle, proxy rows are not refetched, and proxy labels are excluded once
   strict labels clear the sample gate. Runtime deploy/restart remains
   pending; no the bot container service was touched in this session.

9. **Session 286 deploy + VPS observer join design:** Operator approved
   deploying the Session 284 the bot container forward-gate fix. Backed up the the bot container
   files under
   `/home/bot/polymarket-bot/backups/codex-20260509T154351Z`, deployed
   the three wallet-tag scripts plus the `--max-age-days 30` systemd unit,
   ran `systemctl daemon-reload`, and executed one
   `polymarket-wallet-tag-forward-resolutions.service` pass. The run
   completed `exit=0` in `13.6s`, queried `500` unresolved markets, fetched
   `191`, and newly proxy-labelled `39`. the bot container DB after deploy:
   `378` observed markets, `39` proxy-settled, `0` strict-settled, and
   `123` BUY trades joinable through strict+proxy settlement labels. The
   generated forward report still says `INSUFFICIENT`: `104` settled wallet
   trades, `0` strict-settled, `104` proxy-settled, hit `46.2%`, implied
   `49.4%`, edge `-3.3pp`, 95% CI ROI `(-63.2%, +1.5%)`.

 For the separate VPS Polygon `wallet_observer.db` settlement join,
   added a local-only implementation draft:
   `scripts/wallet_observer_settlement_join.py` plus
   `wallet_market_tokens` and `wallet_market_resolutions` helper tables in
   `bots/wallet_observer/schema.py`. The join maps CTF `token_id` to
   `condition_id`/`outcome_index` via Gamma `clob_token_ids`, then scores
   settlement by `winning_outcome_index` instead of assuming every binary is
   YES/NO. This is not deployed to VPS yet; review before rollout.

10. **Session 302 early paper-shadow promotion:** Per ADR-143, added
   `wallet_tag_feature_shadow` as a paper-only ledger before OQ-099 clears.
   It reads `data/wallet_tag_forward.db`, writes
   `data/wallet_tag_feature_shadow.db`, and recomputes post-fee P&L only for
   strict/proxy-settled BUY rows. This accelerates evidence collection but
   does **not** waive the OQ-099 gate: `>=200` settled/scored BUYs, positive
   CI lower, resolution, and concentration checks remain required before any
   bot feature plumbing.

**Blocks:** Any wallet-tag-feature integration into Bot D / Bot G /
crypto FV until forward sample passes the gate.

**Hard boundaries:**

- Both observer services are read-only HTTP polling. No wallet keys,
  no order placement.
- No bot code modified until forward validation completes and a new
  ADR is approved.
- ADR-136 (`$1` fixed-notional Bot G live data probe) unchanged.
- ADR-132 (crypto FV paper-only) unchanged.

---

### OQ-126 — Wallet-Tag Elite Cap Paper transfer gate (Empirical)

**Category:** Live-probe candidate / research-required.
**Owner:** Empirical; the operator approves any live packet.
**Surfaced by:** 2026-05-26 Wallet-Tag whale-cut audit and ADR-186.

**Problem:** The broad Wallet-Tag shadow is profitable on whale-sized
notional, and a recent four-wallet suffix cut is strongly positive, but it has
not yet proved transferability under tiny-wallet constraints: `$1` max entry
cost, `$15` max open exposure, one entry per wallet/market, settlement-label
quality, and concentration controls.

**Acceptance criteria:**

1. `wallet_tag_elite_cap_paper` reaches at least `100` closed capped entries.
2. Post-fee ROI is positive.
3. Ex-largest-win ROI is `> 5%`.
4. No single wallet, market, or market family dominates P&L.
5. Settlement-label and data-quality checks have no unresolved issue that
   changes the win/loss classification.
6. OQ-123 and OQ-124 are clean before any live packet is drafted.

**Blocks:** Any `$137` Wallet-Tag tiny-live packet, copy-trading feature
wiring, or cap lift.

---

### OQ-127 — Sports mid-band NO fade — WANGZJ historical validation (Claude)

**Category:** Research-required.
**Owner:** Claude.
**Surfaced by:** 2026-06-09 creative edge mining
(`docs/reports/creative-edge-mining-2026-06-09.md`).

**Problem:** Universe calibration on the local `data/backtest.db` tape
(5,695 resolved markets with a price `6-78h` pre-close, closes
2026-04-10..16) shows sports YES contracts priced `55-75c` hit only
`58.5%` vs `63.6c` implied (`n=557`). A NO-side fade at `25-45c` ran
`+9.22%` post-fee ROI, `+8.50%` ex-top-2, but the day-level bootstrap
95% CI is `[-5.78%, +23.27%]` because all closes fall in one week.
Independent corroboration: the 2026-05-08 wallet-tag study found human
BUYs at `30-50c` entry beat implied by `+10.1pp` with CI lower `+14.0%`
on `n=13,418`. Run-specific 2026-06-09; re-execute per the report.

**Acceptance criteria (Murphy gates per strategy-e2 pattern):**

1. WANGZJ replay (the bot container cache) of sports `55-75c` YES band, NO side,
   TTR `6-48h`, parabolic 5% taker fee, `n >= 5,000`.
2. Murphy resolution `> 0.001`; top-2 concentration `< 80%`;
   day-level bootstrap 95% CI lower `> 0`.
3. Edge not carried by one sport, market type (O/U vs moneyline), or
   season window.

**Blocks:** any paper-lane registration for this idea (further ADR +
the operator approval required even after PASS). FAIL on any gate archives the
idea.

---

### OQ-128 — Elite-human cheap-tail co-sign filter validation (Claude + Empirical)

**Category:** Research-required, then Empirical.
**Owner:** Claude.
**Surfaced by:** 2026-06-09 creative edge mining
(`docs/reports/creative-edge-mining-2026-06-09.md`).

**Problem:** The PolyVerify `bot_score<30` cohort's `0-15c` cheap-YES
corner is the only replicated strongly-positive slice in the repo:
historical CI lower `+40.5%` (`n=3,815`, wallet-tag-edge-finding
2026-05-08) and `+63.1%` ROI on the 2026-06-09 local settlement join
(`n=78`, `wallet_observer.db` × `backtest.db`). The same cohort's
mid-band buying is unprofitable locally, so the signal is specifically
cheap-tail selection skill. Proposal: a co-sign entry filter (only take
a cheap-YES entry if a cohort wallet bought the same token within N
hours), composable with any cheap-tail lane.

**Acceptance criteria:**

1. the bot container prod `wallet_observer.db` settlement join
   (`scripts/wallet_observer_settlement_join.py`) shows cohort `0-15c`
   forward ROI `> 0` on `n >= 100` settled forward rows
   (post-2026-05-08 only, to dodge scrape survivorship).
2. WANGZJ co-sign backtest shows hit-rate uplift `>= +3pp` vs the
   unfiltered cheap-YES baseline at matched price band and TTR.
3. Feature lands as a column in `wallet_tag_feature_shadow.py` only —
   no new bot, no CLOB writes.

**Blocks:** any cheap-YES lane revival (including Bot D spike variants)
that cites the co-sign filter as its edge source. Also feeds OQ-099.

---

### OQ-129 — Universe calibration tape harvest (Claude)

**Category:** Research-required (infra/data moat).
**Owner:** Claude.
**Surfaced by:** 2026-06-09 creative edge mining
(`docs/reports/creative-edge-mining-2026-06-09.md`).

**Problem:** The decision-useful calibration tape in `data/backtest.db`
exists by accident (one fetch window; `closed_time` is fetch time, not
resolution time, for all `49,883` rows). A small daily read-only
harvester (Gamma resolved markets + `6h/24h/48h` pre-close CLOB prices
into a `calibration_points` table) would manufacture the "second
sample" every tail idea has historically lacked, with true resolution
timestamps.

**Acceptance criteria:**

1. Daily harvester deployed (read-only HTTP, recorder-mount storage
   policy per OQ-053), `30` days of `calibration_points` with `< 1%`
   gap days.
2. First monthly per-category bucket-calibration drift report
   generated.

**Blocks:** nothing; accelerates OQ-127/128 re-validation cadence.

---

### OQ-130 — Fee-rate primary-source verification via VPN (Claude/the operator)

**Category:** Research-required (then Decision if formula changes).
**Owner:** Claude (method) / the operator (VPN or non-UK egress path).
**Surfaced by:** 2026-07-20 full reassessment
(`docs/reports/full-reassessment-2026-07.md`, ADR-191).

**Problem:** Sports fee max is **disputed**. A secondary source says sports
max `$0.75/100sh`; Codex cites `docs.polymarket.com/trading/fees` at
rate `0.05` → `$1.25/100sh` max (crypto `0.07` → `$1.75`). Formula used
in pack: `fee = C * feeRate * p * (1-p)`; makers 0 fee + 20–25% rebate
share. Polymarket domains are **geo-blocked** from all reachable UK
machines this session, so primary docs could not be re-fetched. All C1
sports ROI stress currently uses the conservative `$1.25/100sh` max.

**Acceptance criteria:**

1. From a VPN / non-UK egress path, capture the live primary fee page (or
   authenticated API equivalent) with date-stamped screenshot or HTML
   save (no secrets).
2. Confirm sports vs crypto `feeRate`, max fee per 100 shares, and maker
   rebate share.
3. If primary differs from `$1.25` sports max, re-run C1 fee-exact stress
   and update OQ-127 gates / report numbers; else close as confirmed
   conservative.

**Blocks:** claiming fee-exact C1 paper readiness; any live sports size
that depends on the lower `$0.75` assumption.

---

### OQ-131 — C3 fill-conditioned autopsy ownership (Claude + Empirical)

**Category:** Research-required.
**Owner:** Claude (primary) with Empirical kill on pre-registered gate.
**Surfaced by:** 2026-07-20 full reassessment (ADR-192).

**Problem:** Canary last-minutes mid-gaps (T-1min, CEX ≥10bps beyond
strike: PM `0.76–0.79` vs realized `1.00`, `+17–24pp`, n=`26+15`; also
`+23.7pp` n=26 at 10–20bps and `+20.6pp` n=15 at ≥20bps) are presumed a
**stale-quote mirage** until a fill-conditioned replay on the existing
`58G` canary tape proves executability. Near-resolution kill-list must
not reopen. Selection bias: `357/1271` windows processed, `509` skipped
dead books.

**Acceptance criteria:**

1. Named owner script/report on the local workstation canary path
   (`(local archive, not exported)` or Session 466 zstd archive) that scores
   **executable** windows only (touch/fill-conditioned, not mid-only).
2. Pre-registered kill (ADR-192): fill-conditioned ROI `≤ 0` on
   `n ≥ 200` executable windows → permanent archive of C3.
3. Write dated report under `docs/reports/` with n, ROI, skip reasons,
   and explicit "does not reopen near-resolution kill-list" statement.

**Blocks:** any paper or live C3 lane; any claim that the mid-gap is
tradeable edge.

---

### OQ-132 — Gemini CLI broken (Antigravity migration) (the operator)

**Category:** Decision-required / ops.
**Owner:** the operator.
**Surfaced by:** 2026-07-20 full reassessment session constraints.

**Problem:** Gemini CLI returns `IneligibleTierError` and needs
**Antigravity migration**. Multi-model consensus for this reassessment
therefore lacked a live Gemini pass (pack used internal + Grok + Codex
only).

**Acceptance criteria:**

1. Gemini CLI (or replacement path documented in
   `~/.claude/rules/llm-routing.md`) runs a smoke prompt successfully.
2. One-line note in MEMORY or routing rule that Gemini is restored or
   permanently decommissioned from the consensus stack.

**Blocks:** three-way Gemini+Codex+Grok consensus checks; not a trading
blocker.

---

### OQ-133 — canary.db ~57–58G retention policy on the local workstation (the operator/Claude)

**Category:** Research-required (infra/data moat); Decision on disk budget.
**Owner:** the operator (budget) / Claude (policy draft).
**Surfaced by:** 2026-07-20 full reassessment; Session 466 canary capture.

**Problem:** The post-VPS-decommission canary recorder lives on Mac
Studio at ~`57–58G` (`(local archive, not exported)` / compressed archive
`data/bot_e_recorder_vps_canary_20260705.db.zst`). There is no written
retention, checksum cadence, or rollover policy. OQ-053 covers the bot container
recorder rollover; this OQ covers the **Studio canary sole-copy window**
(2026-05-13→07-05) needed for C3 autopsy and C5 fill studies.

**Acceptance criteria:**

1. Written retention policy: keep raw, keep zstd only, or dual; minimum
   free disk; checksum verification schedule.
2. Confirm bit-for-bit or zstd integrity check is re-runnable (Session
   466 SHA-256 pattern).
3. Cross-link OQ-053 so the bot container and Studio policies do not conflict.

**Blocks:** safe deletion of any canary copy; long-term C3/C5 autopsy
reproducibility if disk is wiped ad hoc.

---

### OQ-134 — Bot B scorer path: rewrite-and-keep vs remove (the operator)

**Category:** Blocking (open-source export scope) — decision.
**Owner:** the operator decides; Claude has a recommendation.
**Surfaced by:** 2026-07-21 Session 469 oraclemangle boundary pass
(`docs/open-source-retirement/grok/oraclemangle-boundary.md` §5).

**Problem:** Bot B's scorer path (`bots/bot_b/scorer.py`, `http_scorer.py`,
`local_scorer.py`, `scoring_sweep.py`) integrates with / references the closed
Oraclemangle product (https://oraclemangle.com) — HTTP client plus branding and
upstream-path leftovers. No proprietary engine or calibration data is in-repo.
Two routes: (a) REWRITE+keep (de-brand, strip upstream internals, cite
oraclemangle.com — preserves a runnable reference example); (b) REMOVE the 4
scorer files, keep only the Bot B narrative/spec + the generic
`scorer_ensemble/` utility (cleanest product boundary).

**Recommendation:** (a) — the closed product's model and calibration data are
external, not in-repo; the scorer *integration code* is generic once de-branded,
and the "built it, didn't clear the gate" story is core lab value.

**FULLY RESOLVED 2026-07-22 (Session 470, ADR-198):** Operator superseded (a): Bot B
CODE is now EXCLUDE from the public export entirely, replaced by `docs/bot-b-reference.md`
(public post-mortem citing https://oraclemangle.com). The Session 469 de-brand of bot_b
code/spec stands for the private tree. The repo-wide doc de-brand listed below was
COMPLETED 2026-07-22 by the grok G1-G3 packets + Claude (residual sweep clean); see
CHANGELOG Session 470 and `docs/open-source-retirement/export-exclude.txt`.

**Original partial resolution (2026-07-21, Session 469):** Operator chose (a) rewrite+keep,
referencing the oraclemangle.com website. De-brand DONE for `bots/bot_b/*.py`,
`bots/bot_b/__init__.py`, `specs/bot-b-spec.md`, and `pyproject.toml` (removed the
external scorer's proprietary performance figures + calibration-corpus description,
upstream filesystem paths, topology, "moat" framing; replaced with
citations to https://oraclemangle.com; strategy logic untouched; bot_b compiles).
Per-bot `CLAUDE.md` files (e.g. `bots/bot_b/CLAUDE.md`) treated as EXCLUDE-at-export
(agent-ops + topology), same class as root CLAUDE.md/AGENTS.md, so not de-branded.

**STILL PENDING — repo-wide doc de-brand (bigger than first scoped):** the same
proprietary figures / upstream references appear in ~11 further non-backup files.
INCLUDED docs needing REWRITE: `docs/architecture-decision.md` (read-first doc!),
`docs/session-2026-04-17-edges-review.md`, `docs/phase-1-discovery.md`,
`docs/bot-b-scorer-rebuild-plan.md`, `docs/oraclemangle-ensemble-proposal.md`,
`research/oraclemangle-edge-distribution.md`. EXCLUDE-class (internal prompt/audit
dumps — confirm exclusion, else REWRITE): `research/prompts/codex-fleet-tactical-2026-04-23.md`,
`research/prompts/opus-fleet-strategy-2026-04-23.md`, `docs/codex-full-review-prompt-2026-04-22.md`,
`docs/audit/codex-fleet-review-2026-04-22.md`, `docs/SESSION-HANDOFFS.md`.

**Blocks:** the fresh export — this doc pass must complete before publish.

---

### OQ-135 — Public repo name + `bots/`→`strategies/` rename (the operator)

**Category:** Non-blocking (cosmetic/branding) — decision.
**Owner:** the operator.
**Surfaced by:** 2026-07-21 Session 469 structure pass
(`docs/open-source-retirement/grok/public-repo-structure.md`).

**Problem:** Working title for the public code repo is `bot-strategies`; open
whether to (1) confirm that name and (2) rename the `bots/` dir to `strategies/`
in the public export for clarity. Purely presentational; no code-behaviour impact.

**Blocks:** nothing hard; finalize before the single-commit export layout.

---

### OQ-136 — CHANGELOG in public export: full-redacted vs condensed (the operator/Claude)

**Category:** Non-blocking — decision.
**Owner:** the operator decides; Claude drafts either form.
**Surfaced by:** 2026-07-21 Session 469 structure pass.

**Problem:** The 1MB+ session `CHANGELOG.md` is part of the honesty story but
carries high topology/ops density. Ship the full file after redaction
(`docs/history/CHANGELOG.md`), or a curated `docs/history/session-highlights.md`.
Depends on how clean the redaction pass leaves the residual.

**Blocks:** the export's docs/history layout.

---

### OQ-137 — Little-rocky agents clone: remove vs attribute (the operator/Claude)

**Category:** Blocking (licence) — decision.
**Owner:** Claude recommends; the operator confirms.
**Surfaced by:** 2026-07-21 Session 469 provenance review
(`docs/open-source-retirement/grok/provenance-review.md` A1/C1).

**Problem:** `docs/archive-little-rocky/polymarket-agents-reference/` is an MIT
clone of Polymarket Agents with the upstream LICENSE file missing and no SPDX
headers. Not on the build path, zero public-export value. Route: (a) REMOVE from the
export (recommended); (b) restore upstream MIT LICENSE + NOTICE and keep.

**Recommendation:** (a) REMOVE — avoids dual-licence NOTICE clutter for no benefit.

**RESOLVED 2026-07-21 (Session 469):** Operator chose REMOVE. Deleted
`docs/archive-little-rocky/polymarket-agents-reference/` (116K, re-downloadable MIT
clone). The rest of `docs/archive-little-rocky/` (operator-authored Little Rocky notes)
is retained.

**Blocks:** none — resolved.

---

### OQ-138 — Unique per-bot names for the public export (the operator/Claude)

**Category:** Non-blocking (branding) — decision, deferred by operator ("still a while away").
**Owner:** Claude proposes a naming scheme; the operator approves.
**Surfaced by:** 2026-07-21 Session 469 operator request — wants unique names per bot
(not A/B/C/…) for the open-source release.

**Problem:** Bots are currently identified by letter (Bot A longshot-fade, Bot B
LLM directional, Bot C Pyth, Bot D weather, Bot E OBI crypto, Bot F whale/cascade,
Bot G longshot-prime, Bot H maker, Bot J/K, …). The public repo should give each a
unique, descriptive name. This touches directory names (`bots/bot_b/` → ?), the
`strategies/` rename question (OQ-135), systemd unit names (EXCLUDE anyway), spec/doc
titles, and cross-references — a wide but mechanical rename, best done as ONE pass just
before the fresh-single-commit export to avoid churning references twice.

**Recommendation:** defer until export-prep; Claude drafts a name table (letter →
unique name, mapped to each bot's strategy) for operator sign-off, then execute the
rename in a single pass. Do NOT start piecemeal now.

**Blocks:** nothing yet; sequence before the export layout is frozen (with OQ-135).

**Category:** Research-required / strategy feasibility.
**Owner:** Claude researches and reports; the operator decides whether any paper
copy-trade build is worth proposing.
**Surfaced by:** 2026-05-09 operator question: could we copy successful
non-whale wallets on 5m/15m markets with good ROI?

**Status (2026-05-09):** **NO BUILD / INSUFFICIENT DATA** —
`docs/reports/non-whale-copytrade-5m15m-analysis-2026-05-09.md` answered
the handoff. Local data alone cannot clear the gate; the production
forward signal is leaning negative.

**Problem:** The repo has several ingredients that could support a
non-whale copy-trade study: the VPS `wallet_observer.db`, the bot container
`wallet_tag_forward.db`, PolyVerify/retail wallet labels, Bot F
crowd-flow diagnostics, and crypto 5m/15m recorder/backtest artifacts.
However, direct copy-trading is kill-listed without proof because it can
be reactive, crowded, latency-sensitive, and selection-biased. The key
unknown is whether successful **non-whale** wallets still produce a
copyable post-signal edge after real best-ask execution, delay, fees,
spread, settlement joins, 5m/15m market parsing, and outlier controls.

**Acceptance criteria:** Execute
`docs/opus-non-whale-copytrade-5m15m-handoff-2026-05-09.md` and produce
`docs/reports/non-whale-copytrade-5m15m-analysis-2026-05-09.md` with:

1. A precise non-whale cohort definition and sensitivity grid.
2. Separate 5m and 15m results, primarily for BTC/ETH/SOL crypto
   Up/Down markets unless another 5m/15m family appears in the data.
3. Same-side copy, fade, random/shuffled, and opposite-side controls.
4. Latency scenarios from zero-lag upper bound through realistic WSS and
   current polling cadence.
5. Best-ask executable pricing where recorder data permits; last-fill
   prices labelled only as non-executable upper bounds.
6. Settlement-label joins that score the bought token side correctly.
7. Cohort-level gates: `>= 200` settled copied trades, positive net ROI
   after best-ask + 1c stress, trading-day bootstrap 95% CI lower `> 0`,
   top-2 P&L concentration `< 50%`, fillability `>= 60%`, and negative
   controls that do not reproduce the edge.

**Result (2026-05-09 Session 295, Opus execution):**

The full audit (`scripts/research/non_whale_copytrade_5m15m_audit.py`,
output `data/reports/non_whale_copytrade/audit.json`) returned the
verdict **NO BUILD**. Cohort C (PolyVerify low-bot-score ∩ non-whale)
has only **`7` wallets / `730` trades** on crypto Up/Down 5m/15m
locally, with **`81%` of trades concentrated in 3 wallets**. Every
settlement-dependent gate (net ROI, 95% CI, negative controls)
returned `INSUFFICIENT` because:

- `0 / 1067` crypto Up/Down trades have a settlement label in any
  local DB (`observed_markets.settled = 0/86`,
  `observer ∩ backtest.resolved_markets crypto = 0/289`).
- `0 / 1067` crypto Up/Down trades fall inside the local Bot E
  recorder's 5h window, so no executable best-ask reconstruction
  is possible.
- The current production observer (the bot container wallet-tag forward) reports
  **`-3.3pp` edge with 95% CI ROI `(-63.2%, +1.5%)` on 104 settled
  trades** across all categories, not just crypto. That is the
  closest forward signal and it is leaning negative.
- Fillability at the current `15-minute` polling cadence is `28.8%`
  for 5m and `5.6%` for 15m. Even at `1-second` WSS cadence, only
  `61.2%` of 5m BUYs are copyable with `≥ 60s` of trade time
  remaining; the rest happen too close to expiry.

Decision-rule check: `≥ 6 of 7` "NO BUILD" clauses in the handoff
fire on cohort C. The `NO BUILD` verdict is over-determined.

**Recommended next action:** keep the existing ADR-137 forward gate
running until **2026-05-15** and treat its cohort-level verdict as the
binding signal. Do not propose, scaffold, or schedule a non-whale
5m/15m copy-trade bot. Any future revisit must wait for: (a) a PASS at
2026-05-15 on the parent cohort, (b) a 5m/15m-specific sub-slice from
the production the bot container forward DB rather than the local seed, and (c)
WSS-grade wallet activity capture (15-min polling is structurally
incompatible with 15m markets).

**Hard boundaries:** No live orders, no wallet keys, no cap changes, no
bot runtime changes, and no copy-trading implementation without a new
ADR plus explicit operator approval. Wallet addresses and trade logs stay
local-sensitive and should be masked in reports.

**Blocks:** Any copy-trade bot proposal for 5m/15m markets.

---

### OQ-115 — Strict settlement backfill bias check for wallet-tag sports cohort (Empirical)

**Category:** Empirical / forward validation.
**Owner:** Empirical — resolves when Gamma strict settlements arrive.
**Surfaced by:** 2026-05-10 wallet-tag forward analysis. All 588 closed
forward trades are proxy-settled; zero are strict Gamma settlements.

**Status (2026-05-10):** **OPEN** — waiting for strict settlements.

**Problem:** The wallet-tag sports PASS cohort (+18.2pp edge, n=139) relies
entirely on proxy "near final" settlement logic. Proxy settlements use the
last observed market price as the outcome. For same-day sports/esports
markets, this could be systematically wrong if:

1. The market price at end-date does not reflect the actual outcome (e.g.
   injury, forfeit, referee decision).
2. The observer's 15-minute polling cadence misses the true final price.
3. Gamma's strict settlement disagrees with the proxy for a material
   fraction of sports markets.

**Acceptance criteria:**

1. `wallet_tag_forward.db` accumulates `>= 50` strict-settled sports trades
   from the top-7 wallet cohort.
2. Run `wallet_observer_report.py` on the strict-only subset.
3. Compare strict vs proxy edge for the same trades.
4. If strict edge is within `+/- 5pp` of proxy edge, proxy bias is acceptable.
5. If strict edge is `> 5pp` lower, the proxy was systematically optimistic
   and the sports PASS is unreliable.

**Monitoring:** `polymarket-wallet-tag-strict-monitor.timer` on the bot container runs
every 6h and alerts when strict settlements cross 50.

**Progress 2026-05-15 aggressive review (ADR-170):** the bot container currently shows
`polymarket-wallet-tag-strict-monitor.service` in `failed` state. The failure
is operational noise, not a trading loss: the DB was moved behind the ADR-168
external-storage symlink and the unit sandbox did not consistently include
the external target. Repo-local ADR-171 unit files now add the external DB
target to `ReadOnlyPaths`. Deploying the unit fix and running
`systemctl daemon-reload` still requires explicit operational approval. The
repo-local unit also marks gate-open exit `1` as `SuccessExitStatus=1` so the
timer can stay healthy while the script output carries the alert.

**Blocks:** Live promotion of wallet-tag sports filter (ADR-151).

---

### OQ-096 — Bot D forecast-entry payload schema gap blocking Phase 1 EMOS (Claude)

**Category:** Research-required / Bot D instrumentation.
**Owner:** Claude.
**Surfaced by:** 2026-05-08 Phase 0 data inventory + Phase 1 EMOS shadow
benchmark on LXC
(`docs/reports/math-formula-data-inventory-2026-05-08.md`,
`docs/reports/bot-d-emos-shadow-benchmark-2026-05-08.md`).

**Problem:** Phase 1 of the math formula roadmap (Bot D EMOS/NGR + BMA
shadow calibration) cannot fit any model on the existing LXC data
because the persisted `bot_d.forecast_entry` payload does not carry the
columns required to join entry decisions to settled outcomes per
station per lead bucket. The Phase 0 inventory shows `bot_d` has 76
resolved + 33 open positions and 67 forecast-entry events, but the
inventory found `Missing columns: bucket_low_f, settlement_station` for
`bot_d` and `Missing columns: bucket_low_f` for `bot_d_live_probe`.
The Phase 1 EMOS run on LXC returned
`forecast_entry_rows: 109, rows_with_settlement_label: 0, labeled_rows: 0`.
The math is locked and tested
(`scripts/research/bot_d_emos_shadow_benchmark.py`); the blocker is data
plumbing.

**Acceptance criteria:** Add the following fields to the persisted
`bot_d.forecast_entry` payload (or write a parallel
`bot_d.forecast_resolution` event keyed on `condition_id` /
`token_id`):

1. `settlement_station` — the station id used for the daily high/low
   resolution
2. `bucket_low_f` — the bucket lower bound in degrees F
3. `bucket_high_f` — the bucket upper bound in degrees F
4. `forecast_source` — which forecast source(s) were used for the entry
   (NWS, NBM, Open-Meteo, GribStream, etc.)
5. `forecast_mean_f` — the chosen entry forecast mean in degrees F
6. `forecast_std_f` — the chosen entry forecast standard deviation
7. `observed_temperature_f` — the actual settled station observation
   (populated by a resolution-time event)
8. `lead_hours` — entry-time-to-resolution time in hours

After persistence is in place, re-run Phase 1
`scripts/research/bot_d_emos_shadow_benchmark.py` against the
populated rows. Pass the Phase 1 gate per split doc §4 before any
ADR proposes promoting EMOS/NGR/BMA into a live signal.

**Blocks:** Phase 1 of the math formula roadmap. ADR-024 skew-normal
remains the live default until this is unblocked.

**Hard boundaries:** No live entry-rule change. The `>= 2 non-NWS
sources within 2.0°F` gate stays untouched. New persistence is
shadow-only.

**Progress 2026-05-08:** Confirmed by Phase 0/1 implementation. Bot D had
`76` resolved positions and `67` forecast-entry signals, but no usable
station/lead bucket because the resolution label join returned zero rows.

**Progress 2026-05-08 NWS observation join:** the manual NWS join partially
bypassed the original zero-label blocker for newer US station rows: `112`
forecast entries became `52` labeled rows after complete-day and NWS-support
filters. The blocker is now sample depth and durable resolution-time
observation capture, not total absence of entry payload fields. Keep this OQ
open until Bot D persists `observed_temperature_f` or an equivalent
`bot_d.forecast_resolution` event for every settled market, including
non-US/source-visible settlement coverage.

**Progress 2026-05-08 safe rollout:** implemented the
`bot_d.forecast_resolution` event path in `bots/bot_d_weather/source_monitor.py`
and updated `scripts/research/bot_d_emos_shadow_benchmark.py` to read it. The
remaining blocker is forward sample accumulation and source-visible/non-US
coverage, not code plumbing for US station rows.

**Progress 2026-05-08 deployment:** the bot container production code now contains the
`bot_d.forecast_resolution` event writer and updated EMOS/NGR benchmark loader.
Restarted Bot D paper/live services successfully. OQ remains open until the
new event count is non-zero and at least one station/lead bucket reaches the
Phase 1 sample gate.

**Progress 2026-05-08 math edge monitor:** the bot container monitor report
`docs/reports/math-edge-data-monitor-2026-05-08.md` found `62`
`bot_d.forecast_entry` rows in the 7-day window but `0`
`bot_d.forecast_resolution` rows all-time. This is expected immediately after
the safe rollout, but Phase 1 EMOS/NGR/BMA remains blocked until completed
station/day markets produce resolution labels.

**Progress 2026-05-08 Session 258 audit:** No change to the blocker. Bot D
EMOS/NGR remains a label/sample accumulation problem, not a live-strategy
candidate. Keep ADR-024 defaults until `bot_d.forecast_resolution` rows exist
and at least one station/lead bucket clears the Phase 1 sample gate.

---

### OQ-071 — Bot D final-source/Wunderground lag poller (Claude)

**Category:** Research-required / Bot D source-lag telemetry.
**Owner:** Claude.
**Surfaced by:** 2026-05-05 ADR-099 source-snapshot rollout.

**Problem:** Bot D now records raw station observations, market prices, bucket
lock/impossible states, raw station age, and physical lock age through
`bot_d.source_snapshot` events. True source lag is only partially measured:
`source_visible_timestamp` and `source_lag_seconds` remain null because we do
not yet poll the market-visible final source, usually the named station's
Weather Underground daily value or equivalent final settlement page.

**Acceptance criteria:** Add and verify a read-only final-source poller that
records when the resolving source first displays the final daily high/low for
each verified Bot D station. It must populate `source_visible_timestamp` and
`source_lag_seconds` without touching entry logic. If Wunderground cannot be
queried reliably, document the fallback source and its mismatch risk.

**Progress 2026-05-09 full Bot D audit:** `bot_d.source_snapshot` rows carry
station metrics and raw observed timestamps, but sampled rows still have
`source_visible_timestamp=null` and `source_lag_seconds=null`. The source-lag
moat remains unmeasured; do not claim a source-lag edge until this poller
exists.

**Progress 2026-05-10 Session 324:** Added the first read-only WU/METAR lag
monitor. Bot D now polls the WU-backed Weather.com current station endpoint by
expected ICAO station and records `final_source_snapshot`,
`source_visible_timestamp`, `source_lag_seconds`, and
`source_matches_station_metric` when the market-visible current source matches
the METAR-derived station metric. This is intraday current-source lag, not the
final WU daily-history table. Report:
`docs/reports/bot-d-wu-metar-lag-monitor-2026-05-10.md`. OQ-071 remains open
until `24-48h` of the bot container telemetry shows whether the lag is consistently
tradable.

### OQ-069 — Bot D tiny-live loosened entry collection review (Empirical)

**Category:** Research-required / live execution evidence.
**Owner:** Empirical.
**Surfaced by:** 2026-05-05 Bot D tiny-live sample-rate adjustment.

**Problem:** Bot D live has proven the live order path, but the tiny-live
sample is still too small for a useful fill/no-fill and ROI read. ADR-097
lowered the live edge threshold to `0.08` and disabled the entry depth
pre-check while keeping fixed 5-share size, caps, verified settlement, NWS
veto, and NWS fallback block unchanged.

**Acceptance criteria:** After at least 24 hours of the ADR-097 settings,
report live placed orders, fills, partials, resting age, cancellations,
resolved outcomes, realised P&L, cap blocks, and skip-reason mix for
`bot_d_live_probe`. Decide whether the next bottleneck is market scarcity,
maker fillability, NWS/ensemble vetoes, or ultra-low Kelly/tail suppression
before changing another live parameter.

**Progress 2026-05-05 pay-up loosen:** the operator approved spending a small amount
of entry edge to speed live evidence collection. ADR-100 lowers the live edge
floor to `0.07` and adds `BOT_D_LIMIT_OFFSET=0.012` for the live probe only.
Review after at least 24 hours should compare fills, resting order age,
slippage, realised/unrealised PnL, and skip-reason mix against the ADR-097
period. Size, caps, verified settlement, NWS veto, and live NWS fallback block
remain unchanged.

**Progress 2026-05-05 cap raise:** the operator approved raising the live probe
collection caps because the probe hit the `10/10` concurrent exposure count
while daily gross was only about `$28/$50`. ADR-102 sets `20` concurrent
positions, `$100` daily gross, and `$150` filled-plus-resting exposure while
keeping `5` shares, `$5.25` max order, verified settlement, NWS veto, and
live NWS fallback block unchanged. The next review should explicitly compare
cap usage before and after this raise.

**Progress 2026-05-06 cap snapshot:** Before paper/live alignment, live probe
usage was `$55.375/$100` daily gross, `15/20` open positions, and
`$49.385/$150` filled-plus-resting exposure. The dashboard now surfaces these
same cap counters directly in the Bot D live-probe card.

**Progress 2026-05-09 full Bot D audit:** Live is no longer cap-bound at the
audit point: `6/20` open positions, `$19.58/$150` open exposure, `0` open
orders, and `13` live trade rows in the last 24h. Recent skips are dominated
by signal/source/execution filters rather than caps: all-time live
`bot_d.entry_attempt` reasons include `kelly_zero=385`, `dedupe=292`,
`nws_fallback_entry_blocked=238`, `expensive_no_guard:distance=168`,
`placed=45`, `place_failed:PolyApiException=42`, `volume_too_low=18`,
`depth_too_low=9`, and `live_order_notional_cap=5`.

### OQ-058 — Bot D remaining settlement-source audit + NBM shadow input (Claude)

**Category:** Research-required / Bot D weather edge.
**Owner:** Claude.
**Surfaced by:** Session 47 Bot D settlement-station implementation on
2026-04-29.

**Problem:** Session 47 added `SettlementSpec` and corrected the highest-risk
verified station mismatches (notably NYC `KLGA` and Dallas `KDAL`), but not
every configured Bot D city has externally verified settlement text, rounding,
and station-source history. NBM percentile extraction is also still shadow
research, not part of the live decision path.

**Unlocks:** Safer Bot D live-graduation proposal after the model is
settlement-exact across all active cities and NBM is either promoted by
Brier/log-loss evidence or explicitly rejected.

**Acceptance criteria:** For every city in `bots.bot_d_weather.config.CITIES`,
record the active Polymarket resolution station/source/rounding rule or mark
the city paper-only. Add a no-key NBM point-extraction prototype for US
MaxT/MinT percentiles and compare its Brier/log-loss against the current
Open-Meteo + empirical gate in paper.

**Progress 2026-05-01:** Fresh production report keeps Bot D as the first
real-wallet candidate track, but shows the immediate blocker is daily/weekly
lock-up plus stale-open reconciliation. Add those reports before changing
thresholds or proposing live wallet use.

**Progress 2026-05-01 later:** Added `scripts/bot_d_readiness_report.py` and
deployed it to the bot LXC container. Production Bot D now reports `15` open paper orders
worth `$321.33`, split into `13` daily/low-lock-up orders and `2` weekly
orders, with `8` stale orders, `3` stale open positions, and `0` recent fills.
The dashboard exposes these blockers on `/api/bot-d` and the Bot D tab.
OQ-058 remains open for settlement-source completion, NBM shadow evidence,
and stale-open reconciliation before any live-wallet proposal.

**Progress 2026-05-01 daily cleanup:** Bot D stale paper state was cleaned
without touching live money: `8` expired paper orders cancelled, `3`
blank-condition orphan positions archived, and `1` weekly-lock paper order
cancelled. `BOT_D_MAX_LOCKUP_HOURS=48` now rejects new weekly-lock entries.
Book capture after Bot D order placement was added and production book
snapshotting produced `3` paper fills. OQ-058 remains open for settlement
source/NBM proof and resolved daily-only P&L.

**Progress 2026-05-01 station-capture start:** Added a Bot D station/source
coverage table to `scripts/bot_d_readiness_report.py` and the dashboard.
`bot_d.forecast_entry` payloads now include settlement station, observation
station, settlement source, rounding, unit, verification flag, forecast
source, forecast fetch timestamp, and forecast model timestamp when the source
exposes one. OQ-058 remains open for external station-rule verification,
production validation of the new payload fields, NBM shadow input, and
resolved daily-only P&L.

**Progress 2026-05-01 production deploy:** Deployed the station coverage and
forecast metadata changes to the bot LXC container. `/api/bot-d` now reports `24` active
cities, `16` with station configured, and `10` verified. A fresh post-restart
`bot_d.nws_veto` event included station/source/forecast fields
(`KIAH`, `wunderground`, `standard`, forecast fetch timestamp). No
post-deploy `bot_d.forecast_entry` event had occurred yet, so exact
forecast-entry payload validation remains open.

**Progress 2026-05-10 station mutation monitor:** Added
`scripts/bot_d_wu_station_audit.py`, a read-only active Gamma audit that
parses each active weather market's `resolutionSource` station and compares
it with `SettlementSpec`. First run checked `4` parsed active markets:
`3` matched the expected station and `1` was `missing_station` for Hong Kong,
which is not configured as verified/live. Report:
`docs/reports/bot-d-wu-station-audit-2026-05-10.md`. OQ-058 remains open for
daily automation and full city/source/rounding citations.

**Progress 2026-05-01 Phase 0/1:** Added Bot D forecast-entry validation to
the readiness report and dashboard: latest payload station/forecast-field
presence, model-vs-market probability samples, model timestamp buckets,
entry-depth coverage, and FIFO resolved P&L split for daily/low-lock-up
positions. the bot LXC container `/api/bot-d` now shows `15` forecast entries, latest
entry with station and forecast fields present, `15` model-vs-market
probability samples, average model-market gap `0.2608`, `14` depth samples,
average at-limit depth `$16.91`, `$25` coverage `2/14`, `$50` coverage
`1/14`. Daily/low-lock-up resolved FIFO P&L is `56` closed / `26` wins /
`+61.23%` ROI, but outlier adjustment fails: ex-largest-win ROI `-31.32%`,
ex-largest-two ROI `-33.86%`. OQ remains open for full station-rule
verification, NBM shadow input, and durable outlier-adjusted daily ROI.

**Progress 2026-05-02 forecast reliability:** Added Open-Meteo HTTP 429
handling to Bot D weather fetching: `Retry-After` cooldown, short in-process
forecast cache during cooldown, `max_connections=5`, and per-city request
pacing. Deployed to the bot LXC container and restarted with `BOT_D_ENV=paper`; post-restart
scans completed with `0` orders. This reduces paper-capture fragility but
does not close OQ-058; full settlement-rule verification, NBM shadow input,
and durable outlier-adjusted daily ROI remain open.

**Progress 2026-05-02 cooldown hardening:** After live-shaped Bot D paper
collection hit repeated Open-Meteo HTTP `429`s, increased the missing-header
fallback cooldown from `300s` to `1800s`. Local and LXC focused weather tests
passed (`35 passed`), Ruff passed, and LXC journal now confirms
`cooling down for 1800s`; the post-restart scan evaluated `0` markets and
placed `0` orders. OQ remains open for settlement-rule verification, NBM
shadow input, and durable outlier-adjusted daily ROI.

**Progress 2026-05-02 NWS fallback bypass:** Open-Meteo continued returning
HTTP `429`, which left Bot D with qualifying markets but `0` evaluated
forecasts. Added an NWS gridpoint fallback that produces conservative
`nws_fallback` forecasts when Open-Meteo is unavailable and no fresh cache can
cover the city. Follow-up audit added `BOT_D_EMPIRICAL_MIN_MEMBERS=5` so
single-point fallback forecasts do not trip the empirical ensemble-shape veto.
Local and LXC focused weather/audit tests passed (`49 passed`), Ruff passed,
and the first post-restart production scan evaluated `11/11` markets via NWS
fallback. It placed `0` orders because no edge passed; best audited net edge
was only `+3.5%`, below the `10%` threshold.

**Progress 2026-05-02 live-shaped paper policy:** ADR-079 now restricts new
Bot D paper entries to markets shaped like a future tiny-live lane: verified
settlement coverage, known Gamma `end_date`, and `<=48h` lock-up. Added
`BOT_D_ENTRY_HALT` as an executable entry guard and exposed the entry policy
in `scripts/bot_d_readiness_report.py`. Local and the bot LXC container compile/Ruff/tests
passed (`121 passed` across Bot D/readiness/dashboard-adjacent coverage).
Deployed to the bot LXC container via `hypervisor-host`/`pct exec <ctid>` and restarted
`polymarket-bot-d`; production readiness shows `14` daily open orders, `3`
open positions, no stale/weekly blockers, entry halt `False`, verified
settlement required, known end date required, and max lock-up `48h`. Fresh
journal confirms the candidate filter is active (`kept=12 dropped=5 raw=17`).
Open-Meteo returned HTTP `429`, so the first post-restart scan evaluated `0`
edges and placed `0` orders. OQ remains open for full station-rule
verification, NBM shadow input, and durable outlier-adjusted daily ROI.

**Progress 2026-05-02 scan telemetry:** Added persistent `bot_d.scan_summary`
events and a "Latest Scan" section to the Bot D readiness report. the bot LXC container
post-restart scan now shows `21` raw markets, `15` kept/evaluated, `0`
missing forecasts, `15` `nws_fallback` forecasts, `1` tradeable edge, and
skip buckets `12` below-threshold / `2` observed-constraint. The current
no-order reason was dedupe on the one Miami BUY_NO candidate. OQ remains open
for full station-rule verification, NBM shadow input, durable
outlier-adjusted daily ROI, and improved depth/slippage evidence.

**Progress 2026-05-02 strict lane:** ADR-080 now makes the Bot D
live-candidate paper lane wave-and-depth gated by default:
`BOT_D_REQUIRE_WAVE_FOR_ENTRY=true`, `BOT_D_DEPTH_GATE_ENABLED=true`, and
`BOT_D_MIN_ENTRY_DEPTH_USD=25`. Entries with insufficient executable ask-side
depth at the intended limit are skipped as `depth_too_low`. The readiness
verdict now reports insufficient depth sample, weak `$25` depth coverage,
insufficient resolved daily sample, and negative ex-largest-two ROI as
explicit blockers. the bot LXC container deploy passed remote compile/Ruff/tests
(`63 passed`) and fresh readiness now shows blockers
`insufficient_depth_sample`, `weak_entry_depth`, and
`negative_ex_outlier_roi`. OQ remains open for full station-rule verification,
NBM shadow input, and forward proof that the stricter lane produces positive
outlier-adjusted daily ROI.

**Progress 2026-05-02 dashboard surface:** The dashboard Bot D tab now shows
the strict-lane gates directly: verified settlement, known end date,
wave-required posture, depth gate, `$25` depth coverage, ex-largest-two ROI,
and latest scan summary. the bot LXC container `/api/bot-d` now exposes the strict-lane
fields and blockers after restarting `polymarket-dashboard`. OQ remains open
for evidence collection and model/station research, not visibility.

**Progress 2026-05-02 recent trades dashboard:** `/api/bot-d` now always
returns recent Bot D trades in default dashboard mode. the bot LXC container currently
returns `15` recent Bot D trade rows, so the dashboard Recent Trades table is
now populated without enabling detailed tabs. OQ remains open for forward
strict-lane performance evidence.

**Progress 2026-05-02 live-readiness hardening:** ADR-082 converted the
latest Bot D live audit into runtime blocks. Live entries now require
`BOT_D_LIVE_AUTHORIZED=true` plus a `live_ready=true` readiness report;
`nws_fallback` entries are blocked by default; paper exits use best-bid
pricing with `50` bps slippage and taker fees; live exits use best-bid minus
`0.005` and cancel stale SELLs after `10` minutes; skew-normal degradation
emits `bot_d.skewnorm_fallback` and blocks readiness. The dashboard now shows
live auth, NWS fallback posture, and skew fallback events. Local Bot D/
weather/readiness/dashboard tests passed (`92 passed`). Deployed to the bot LXC container;
remote compile/Ruff/tests also passed (`92 passed`). Production readiness now
shows `live_authorized=false`, `allow_nws_fallback_entry=false`, `50` bps
paper-exit slippage, `0.005` live-exit offset, and `10` minute stale-exit
handling. OQ remains open for forward strict-lane performance evidence and
full station/model research.

**Progress 2026-05-03 tiny-live prep:** ADR-084 prepares a separate
`bot_d_live_probe` tiny-live plumbing path while keeping `bot_d` paper
running. This does not close OQ-058: full station-source completion, NBM
shadow evidence, and durable outlier-adjusted daily ROI remain unresolved.
The transfer-specific live proof is tracked in OQ-067.

### OQ-059 — Contrarian crowd-flow edge validation (Empirical)

**Category:** Research-required / profitability edge.
**Owner:** Empirical.
**Surfaced by:** 2026-05-01 profitability deep dive and Opus handoff.

**Problem:** Bot F has enough wallet-flow and mirror infrastructure to observe
public sharp/copy-bot behavior, but direct copy-trading is a crowded 2026
strategy with lag, slippage, survivor bias, and clustered-wallet risk. The
more unique path is to measure whether public-wallet cascades create a
contrarian veto/fade signal for Bot B/D/E/G. This is not yet quantified.

**Unlocks:** Decides whether Bot F remains sensor-only, becomes a
cross-bot veto/confirm estimator, or earns a separate paper anti-crowd cohort.

**Acceptance criteria:**
- Define paper-only cohorts: curated sharps, high-frequency winners,
  category-pure sports wallets, and market-maker-like wallets.
- For every detected cascade, report signal age, spread/slippage, wallet
  overlap, category, time-to-resolution, and post-signal price drift at
  1m/5m/30m/6h.
- Report whether fading crowded signals, avoiding them, or confirming with
  them would have improved Bot D/E/G decisions net of spread and fees.
- No direct mirror allowlist expansion, sizing increase, or live proposal
  until this report shows positive forward paper EV and a new ADR records the
  chosen use.

**Progress 2026-05-01:** Bot F is demoted as a direct fast-ROI bot. Added
`core.crowd_signals` so other bots and reports can read recent cascade
pressure without depending on Bot F executor code. Added
`scripts/fast_roi_report.py` to include Bot F crowd-sensor state alongside
Bot E/G/D fast-ROI readiness.

**Progress 2026-05-01 later:** Production fast-ROI report showed Bot F crowd
sensor available but `0` recent cascades. The hourly fast-ROI timer now
captures this sensor state under `data/reports/fast_roi/`; the next missing
piece is post-cascade drift, not more Bot F execution.

**Progress 2026-05-01 Phase 0/1:** The hourly fast-ROI report now includes
Bot F post-signal drift scaffolding at `1m`, `5m`, `30m`, and `6h`, joined
from Bot F mirror signals to main-db book mids. the bot LXC container sampled `500` recent
mirror signals but measured `0` horizons because matching book snapshots were
not available, so no fade/avoid/confirm claim is supported yet.

**Progress 2026-05-08 direct recorder diagnostic:** Added
`scripts/research/bot_f_anti_crowd_join_diagnostic.py` and ran it on the bot container;
report: `docs/reports/bot-f-anti-crowd-join-diagnostic-2026-05-08.md`.
Result: **FAIL**. It loaded `500` Bot F mirror signals, found `0` distinct
tokens with usable recorder joins, and measured `0` of `500` starts at every
horizon (`60s`, `300s`, `1800s`, `21600s`). OQ-059 remains blocked at data
join coverage; the next attempt should map Bot F condition IDs to current
recorder market/token IDs before any anti-crowd EV test.

**Progress 2026-05-08 public trade-print fallback:** Repaired the OQ-059 join
path by adding a public Polymarket Data API fallback keyed by
`market=<condition_id>` to
`scripts/research/bot_f_anti_crowd_join_diagnostic.py`. the bot container rerun loaded
`200` mirror signals, fetched `33` markets, measured `174` rows at `60s`,
`180` rows at `300s`, `160` rows at `1800s`, and `6` rows at `21600s`.
This unblocks measurement but **does not support anti-crowd fading**: at the
5m horizon, same-side edge was `+1.91c`, same-side net after `2c/share` stress
was `-0.09c`, and fade net was `-3.91c` with only `35.0%` fade-net-positive
rows. The usable signal, if any, is same-side momentum at longer horizons, not
5m fade.

**Progress 2026-05-08 same-side momentum EV:** Added
`scripts/research/bot_f_crowd_momentum_ev_report.py` and ran it on the bot container;
report: `docs/reports/bot-f-crowd-momentum-ev-2026-05-08.md`. Result:
**same-side 30m momentum PASS, fade still rejected.** The run loaded `500`
Bot F mirror signals, fetched `64` markets, measured `1,340` observations,
and found `8` passing cells, all at the `1800s` horizon in same-side mode.
The broad all-market cell cleared at `1c` cost stress with `n=380`, `42`
market-days, `+4.27c` net edge, 95% CI `+0.79c..+7.97c`, `61.1%` net-positive
rate, and `8.8%` top-2 concentration. Stronger subcells: price `25c-50c`
at `+10.92c` net after `1c`, signal age `90s-5m` at `+5.26c` net after
`2c`, and trade size `<100` at `+4.16c` net after `2c`. These are overlapping
group views of one candidate edge family, not independent bot proposals. Next
step is a paper-only Bot F momentum filter/veto spec with executable
top-of-book fillability checks; no direct mirror expansion or live trading
proposal is supported yet.

**Progress 2026-05-08 Session 258 audit:** Ranking kept Bot F 30m same-side
momentum as a sensor candidate only. The next proof must be executable
fillability: top-of-book entry availability, expected slippage, and whether
the signal can be acted on before the 30m drift is already priced in. Anti-
crowd fade remains rejected.

**Progress 2026-05-09 final archive/recorder evaluation:** ADR-138 archives
the retired Bot F executor/default dashboard identity and removes it from the
active dashboard surface. This does **not** close OQ-059: the historical Bot F
signal dataset can still be mined for the 30m same-side momentum fillability
question above, but any future use is a new paper-only research/spec decision,
not a Bot F service restart or live-trading proposal.

**Progress 2026-05-09 paper promotion:** ADR-142 promotes a new
`bot_f_momentum_paper` ledger for the executable subset of the same-side
momentum result. The first implementation is deliberately BUY-only: it reads
`bot_f.db::mirror_signals`, accepts signals matching the strongest 1800s PASS
cells, records synthetic `$5` paper entries in
`data/bot_f_momentum_paper.db`, and closes them from public trade prints after
1800s. SELL same-side signals stay research-only because the fleet does not
have inventory to sell. OQ-059 remains open until this forward paper ledger
has at least `100` closed entries and survives post-fee ROI, ex-largest-two,
and fillability review.

### OQ-009 — Minimum order size per market (Empirical)
Docs reference `INVALID_ORDER_MIN_SIZE` but no published threshold. Community reports $1–$5 notional range.
**Unlocks:** Bot sizer floor value.
**Can resolve in:** One deliberately small dry-run order (expect reject, read error).
**Note:** Amoy CLOB path is gone (decommissioned ~2026-04 per ADR-017). This now needs a mainnet unfillable-price run under `POLYMARKET_ENV=live` — `scripts/dry_run_order.py --mainnet --token-id <X> --price 0.01 --size <threshold>` with varying `--size` until the exchange returns `INVALID_ORDER_MIN_SIZE`.
**Priority:** First live-env gate once keystore + VPN are provisioned.

### OQ-016 — Polymarket V2 migration status (Claude)
`py-clob-client-v2==0.0.2` was published 2026-04-08 by Polymarket Engineering. ADR-017 defers migration until the v2 client matures (≥0.1.0 and release notes). Track: the v2 client's version cadence, any V1 order-placement failures during paper phase, and any Polymarket docs changes that force the upgrade.
**Unlocks:** Full V2 compatibility (new collateral wrapper, CTF V2 routing, updated fee contracts).
**Priority:** Monitor during paper phase. Trigger: v2 client hits ≥0.1.0 OR V1 order failures observed.

### OQ-017 — Bot C Hermes mapping + fallback readiness (Claude)
Bot C's Pyth ingest currently runs against the paid Pro/Lazer endpoint. The free Hermes path is still a stub because Hermes uses a different stream schema and hex feed identifiers.
**Updated plan (2026-04-16):** test the **free-pyth tier first** when Pro trial expires 2026-04-22; only fall back to Hermes implementation if free-pyth is insufficient for Bot C's requirements. This is a cost + effort optimisation — avoid unnecessary infra change until evidence demands it.
**Unlocks:** Bot C continues post-trial without a migration if free-pyth passes.
**Can resolve in:** (a) 2026-04-22: trial lapses → observe whether free-pyth feeds the bot; (b) if insufficient, one focused implementation session to wire Hermes (schema confirm, 5 symbol mapping, replace `run_hermes()` stub, parity tests).
**Priority:** Passive observation until 2026-04-22; implementation only if free-pyth fails.

### OQ-010 — Polymarket weather-market volume (Claude)
Grok intel flagged weather as a low-crowding strategy but noted "Kalshi/PM cross hints" — ambiguous which venue has volume. If volumes on PM weather markets are too thin, the v1.5 backup plan (Bot C = weather) is dead.
**Unlocks:** Decision on v1.5 contingency.
**Can resolve in:** 30 min of Gamma API queries on weather markets + volume histograms.
**Priority:** Before Bot A/B kill decision at Week 12.

### OQ-011 — WebSocket connection limits (Claude)
Undocumented. Not blocking v1 (we only need 1 market sub + 1 user sub), but relevant if bot expands.
**Unlocks:** v2 scale headroom.
**Priority:** Deferred to v2.

### OQ-012 — Nonce / order-ID reuse policy (Claude)
Flagged by Kimi in Phase 2.5 verification. Undocumented. Not blocking v1 (bot's nonce strategy can be sequential per-daemon-start).
**Unlocks:** Long-running-daemon correctness.
**Priority:** Before first live session lasting >30 days.

### OQ-038 — Method 1 (TA-herding fade) reversion check folded into Bot E POC (Claude)

**Category:** one-shot research, record of negative result
**Owner:** Claude
**Why it's open:** `contrarian_edges.md` Method 1 ("fade short-term technical herding") proposes betting against bot-cluster overshoots on 5–15 min BTC binaries. The session 2026-04-17 edges review (§5) gates Bot E on a POC against the recorder data. Method 1 requires roughly the same tape (Polymarket WSS + Binance trade stream on crypto binaries). For ~1 hour of incremental work folded into the Bot E POC pass, we can measure empirical $\delta$ (signal-cluster spike) and 4-min reversion fraction and produce a defensible "do not build" record so Method 1 does not resurface in future sessions.
**Unlocks:** permanent archival of `contrarian_edges.md` Method 1 — either with positive evidence (unlikely given Bot E OBI falsification as prior) or with a three-number kill memo.
**Acceptance criteria:** `docs/bot-e-poc-results.md` contains a §"Method 1 reversion check" sub-section with (a) count of clustered-signal events, (b) median reversion fraction of initial spike at $t+4$ min, (c) mean per-trade net-of-fees+slippage EV in basis points. If mean EV < +5 bps OR reversion fraction < 0.5 on ≥ 500 events, Method 1 is archived.
**Blocks:** no active work; prevents reversion-fade ideas from cycling back.
**Revisit when:** Bot E POC runs (roadmap day 1).

### OQ-039 — 14-day reward-cascade passive measurement window before rewards_monitor build (Claude)

**Category:** build-gate / cheap data capture before committing code
**Owner:** Claude
**Why it's open:** Session 2026-04-17 §3.4.2 slates `core/rewards_monitor.py` for roadmap days 24–26. Source `contrarian_edges.md` Method 2 and the session doc both rely on the claim that reward-pool cancellation cascades produce predictable post-cascade price moves. That claim has not been measured on our own the bot LXC container Polymarket WSS tape. Mirrors the Bot E lesson: POC-before-build discipline would insert a passive 14-day measurement window between OQ-036 (TOS clearance) and code. Log cascade events (cancellation velocity > 40% of book in < 60s) + 5-min forward mid move, gather ≥ 50 events, compute empirical post-cascade P&L distribution. Cheap; no trading.
**Unlocks:** go/no-go on `core/rewards_monitor.py` build with evidence rather than source-doc claims of "$50–150/day."
**Acceptance criteria:** (a) ≥ 50 cascade events captured in 14 days, (b) median 5-min post-cascade absolute move > spread + expected fee, (c) no-trade distribution clearly bimodal (informed vs noise cascades distinguishable). If any fail, Method 2 execution is archived; scanner-only use is fine.
**Blocks:** `core/rewards_monitor.py` implementation (roadmap days 24–26).
**Revisit when:** OQ-036 (TOS status) resolves. Schedule 14-day window to begin on that clearance.

### OQ-040 — Category-level historical UMA dispute-rate data pipeline (Claude)

**Category:** data pipeline / Bot B ensemble sizing refinement
**Owner:** Claude (data aggregation), the operator (approve pipeline)
**Why it's open:** Bot B already applies per-market `dr_multiplier()` based on the external scorer's market-specific `dispute_risk` (Oraclemangle — https://oraclemangle.com). Layering a **category-level** historical shrinkage (geopolitics vs politics vs finance vs economics) on top captures a distinct prior: even a clean per-market prediction is still riskier when the whole category has a high historical dispute-rate base rate. `bots/bot_b/sizer.py` now exposes an optional `category` argument (session 2026-04-17 addendum); `bots/bot_b/config.py::CATEGORY_DISPUTE_RATES` is the empty dict that needs populating from the external scorer's historical category rates (see https://oraclemangle.com) or from public UMA resolution history.
**Unlocks:** meaningful category-level Kelly shrinkage (currently no-op because map is empty).
**Acceptance criteria:** (a) obtain per-category dispute rates from the external scorer / public UMA resolution history → `disputed_count / total_count` per category, (b) populate `CATEGORY_DISPUTE_RATES` in config OR load dynamically from the scorer ensemble's historical baserate estimator data path, (c) per-category rate inferred over ≥ 200 resolutions per category (else estimator abstains for that category), (d) unit test asserting that a populated rate reduces `size_position` output proportionally.
**Blocks:** none. Sizer scaffold shipped this session lets the system run backward-compatible with `{}` until data lands.
**Revisit when:** Bot B ensemble rebuild E1 (`historical_baserate.py`) is data-loaded. The same DB table the E1 estimator reads already has the category column — the dispute-rate aggregate is a neighbouring query.

### OQ-041 — Fleet-review operator-decision bundle (the operator) — EXTENDED 2026-04-22 after GLM-5.1 review

**Category:** Decision-required (10 items bundled).
**Owner:** the operator.
**Surfaced by:** `docs/audit/codex-fleet-review-2026-04-22.md` Section G (Q1-Q5) and `docs/audit/glm-5.1-fleet-review-2026-04-22.md` Section G (Q6-Q10). Triangulation + consolidated to-do list in `docs/audit/fleet-review-2026-04-22-triangulation.md` Part 6.

Each can be answered in one sentence; none require research.

**From Codex Section G:**

1. **Bot C archive vs un-archive — RESOLVED 2026-05-04.** ADR-093 archives
   Bot C active trading, disables `polymarket-bot-c.service` on the bot LXC container,
   removes the systemd drop-in, and keeps the repo unit inert with
   `BOT_C_ARCHIVED=true`.
2. **VPN kill-switch verification.** `core/watchdog.py:445-484` only checks DNS/HTTPS reachability; cannot prove traffic routes through the VPN provider. Provide `iptables-save` from the bot LXC container (wallet/CLOB addresses redacted) so Claude can confirm CLOB egress is blocked outside wg.
3. **Bot D isolated-tail daily loss cap.** Pick $50 / $100 / $200 while the wave detector (roadmap NEW-D-WAVE) is built. Default if no pick: $100.
4. **Maker rebates in graduation P&L.** Exclude from all graduation P&L until an actual USDC rebate credit is observed on-chain? (Current `include_in_ev=False` default already does this for EV math; the question is whether to strip from accounting P&L too.)
5. **Bot F mirror max signal age for non-crypto.** 60s or 120s? Crypto stays 90s per current spec.

**From GLM-5.1 Section G (added 2026-04-22 after second review):**

6. **Fleet cap fail-open vs fail-closed on DB error?** `core/fleet.py:265-293` currently returns `ok=True` on any DB exception (fail-open). GLM A1 flagged this as a safety issue — a corrupt / locked SQLite silently disables the cross-bot exposure cap. Fail-closed means a DB lock can freeze the entire fleet; fail-open means safety is conditional on DB health. Security posture leans fail-closed for live; reasonable to keep fail-open for paper. Pick one policy (or one per mode).
7. **FIFO or avg-cost as canonical P&L method?** **Amendment 2026-04-23:** the code now picks FIFO — `core/portfolio.py::_apply_to_position` was refactored in commit `0097bd6` to replay the token's full trade history through a FIFO lot queue on every SELL, recomputing `cost_basis_usd` and `avg_price` from remaining open lots. Dashboard cost-basis display now agrees with `get_realised_pnl` (also FIFO). HMRC-aligned. See ADR-040 amendment 2026-04-23. This question is retained for explicit operator acknowledgement only; the answer is already in the code.
8. **Bot D tail-scaled cap — intentional risk control or edge suppression?** GLM B4 observation: the cap reduces stakes on the most profitable entries (the tails ARE the edge), and the bot bleeds -$246/day on non-cohort days because isolated tails get fair-or-negative P&L after spread. **Answered in code 2026-04-24 via ADR-043:** hybrid posture. Detect the wave and keep wave entries full-size; keep isolated entries active but reduced-size. Historical and forward EV still need measurement before live.
9. **Target date for any bot going live?** All bots paper today. Several P0 fixes (A4 paper_override, A5 dashboard auth, A3 live-trade fee reconcile) are real-money-adjacent. Urgency on those depends on whether a live date exists. If "no live for 3 months" they stay P1.
10. **`data/backtest.db` retention.** 526 MB (50% of repo data footprint). Still actively used for replays, or archivable? If archivable, moves to `docs/memory-archive/` (gitignored).

**Unlocks:** clears 10 roadmap items. 6 architectural (cap fail-open policy, canonical P&L method, tail-cap disposition, live date urgency calibration, Bot C code-env match, data retention); 4 operational (iptables redact-provide, daily-loss cap pick, rebate policy, mirror age).

**Acceptance criteria:** the operator replies 1-10 in chat; Claude applies env / config / code changes per answer; ADR per item where behaviour changes; CLAUDE.md updates per bot where policy changes.

### OQ-042 — GLM-5.1 deferred-fix bundle (Claude, after OQ-041 resolves)

**Category:** Research-required (Claude does the work once OQ-041 gates clear).
**Owner:** Claude for all items; depends on OQ-041 G2, G3, G6, G10 for some.
**Surfaced by:** `docs/audit/fleet-review-2026-04-22-triangulation.md` Parts 3, 5, 7.

Five GLM-flagged items that are verified-real but deferred because they need either an operator decision or a coherent architectural fix.

1. **A2 cost_basis / FIFO unification.** Blocked on OQ-041 G2 answer. ~4h once the canonical method is picked.
2. **A3 clob.py:462 flat-fee bug.** Replace with `core/fees.py::taker_fee_per_share` after an empirical check of what Polymarket returns in `fee_rate_bps`. ~1h post-verification. Affects all LIVE-trade realised P&L accounting.
3. **A8 two fee-rate dicts deduplication.** Single source of truth in `core/fees.py`. Resolves A3 cleanly. ~1h once units are confirmed.
4. **A9 reconcile_live_fills transaction wrap.** Single-transaction for fill-apply + cursor-write to prevent double-apply on crash. ~1-2h.
5. **Analytical pursuits (GLM Section E) — scope list:**
   - P-1 / OQ-040 Category dispute-rate shrinkage for Bot B (~2h).
   - P-2 Per-category wallet P&L for Bot F (~2h).
   - P-3 Co-movement analysis on the 4 sharps (~1 day — affects Bot F sizing + Bot B E4).
   - P-5 Wire `crowd_signals` into Bot B as E4 WalletFlowEstimator (~1 day).
   - P-6 Reward-cascade 14-day passive log (~1h setup + 14d passive; decides Bot H viability later).
   - P-7 Bot E smart-money 30-90s post-open filter (~1h scope against recorder data).

Pick-off order once OQ-041 clears: P-6 (passive, zero risk, starts the clock) → P-1 (Bot B unhalt unlock) → P-3 (changes Bot F mirror math) → remaining per operator priority.

### OQ-043 — Bot G fill-path investigation + recommended fixes (Claude)

**Category:** Research-required.
**Owner:** Claude (operator will follow up later).
**Surfaced by:** 2026-04-23 Session 22b fleet audit.

**Findings (answer to "why is Bot G not landing any orders?"):**

1. **Paper mode does NOT require a real wallet.** `ClobWrapper(paper_override=True)` short-circuits `place_limit` to `_paper_fill` which generates a `paper-*` order_id and records the Order locally. No keystore access, no network call. The question "does it have to be a real wallet to confirm it would work?" is therefore **no** — paper mode is end-to-end functional without a wallet.

2. **Bot E recorder was dead for 31 hours** (SIGABRT 2026-04-21 22:34 UTC → reset-failed + restart 2026-04-23 04:33 UTC). During that window Bot G queried an unchanged `markets` table and correctly returned 0 candidates every scan. Separately fixed 2026-04-23 via watchdog permanent-failed detection (ADR-041).

3. **Running config on the bot LXC container** (from `.env`): `BOT_G_MAX_ENTRY_PRICE=0.05`, `BOT_G_MIN_BOOK_SIZE=1`, `BOT_G_ENTRY_SECONDS_BEFORE_RES=60`, `BOT_G_MIN_COUNTERPARTY_PRICE=0.90`. Entry only fires in the final 60 seconds before resolution when one side has collapsed ≤ 5¢ AND the counterparty side is ≥ 90¢. By design (ADR-036) this is a narrow window.

4. **Current-market snapshot (2026-04-23 04:43 UTC):** 3 active Solana Up/Down markets with `yes_price ≈ 0.50` (balanced). None has a side ≤ 5¢ yet; they only diverge in the final 15-30 seconds as CEX price movement determines outcome.

5. **Recorder event-type asymmetry (primary technical blocker):** In the 5 minutes after the recorder came back, 573 `price_change` events vs only 2 `best_bid_ask` events were written. `_latest_best_bid_ask` queries specifically for `event_type='best_bid_ask'` within 30 seconds, so it returns `None` almost always. Bot G would then skip the market for `yes_stale` / `no_stale`. **This is the real reason fills are rare, not a pure-liquidity issue** — the book data is there, it's just in a different event_type that Bot G doesn't read.

**Fix shipped 2026-04-23 (commit 920f055):**

`_latest_best_bid_ask` now takes `(token_id, condition_id, now_ms)` and
pulls the freshest book quote across all three event types:
- `best_bid_ask` payload: top-level `{best_bid, best_ask}` keyed by asset_id
- `price_change` payload: inner `price_changes[]` list — recorder keys these
  events by the condition_id (not per-token), so the query matches on
  `asset_id IN (token_id, condition_id)` and the new `_extract_bba_from_payload`
  helper iterates to find the matching token
- `book` payload: top-of-book = max(bids[].price), min(asks[].price)

Depth at best-ask still comes from the most recent `book` event (widened
to 90s since book events are snapshot-style).

**Verification (live probe 05:38 UTC, Bot G restarted with correct 0.05
ceiling after a .env clobber during deploy, see CHANGELOG):**
- Market at t-6.7min returned `bid=0.51 ask=0.53` via `price_change(4s old)`
  — exactly the event type the old code ignored.
- Recorder event mix now: price_change 15,674 / 5min, best_bid_ask 560
  / 5min, book 220 / 5min.

**Acceptance criteria — status:**
- ✅ `_latest_best_bid_ask` returns a value for tokens with pm_events in
  last 30s (not just `best_bid_ask`) — verified via live probe.
- ✅ Unit tests (9 new) cover all three event-type shapes + freshest-wins
  + all-stale-returns-None + book-depth lookup.
- ⏳ Bot G paper-fill count over 7-day observation window — open.

**Status:** Resolved pending 7-day fill-rate verification. Reopen if fill
count has not increased by 2026-04-30.

**Remaining risk:** none technical; the thesis itself (≤5¢ cheap side in
final 60s + 90¢ counterparty floor) is either validated by incoming fills
or falsified by their absence. Either outcome is informative.

**Not-in-scope for this OQ:** Changing the entry thesis (still 5¢ ceiling, 60s window, 90¢ counterparty floor). If the book-freshness fix lands and Bot G still doesn't fill, that'd be separate evidence the thesis itself needs revisit.

---

### OQ-044 — Bot G paper orders never convert to fills (recorder-driven fill path missing) (Claude)

**Category:** Blocking for Bot G P&L validation.
**Owner:** Claude / operator.
**Surfaced by:** 2026-04-23 Session 23 post-deploy check. Bot G placed 11
paper orders in 10 hours (OQ-043 fallback working), but all 11 remained
in `PAPER_OPEN` status with zero `Position` rows and `realised_pnl = $0`.

**Findings:**

1. **`core/portfolio.py::simulate_paper_fills` reads from the `Book` table.**
   Bot A/B/C/D populate `Book` via their book-watch infrastructure.
   Bot G does not — it consumes the recorder's `pm_events` table only
   (read-only piggyback, per `bot_g_longshot/CLAUDE.md`).

2. **Consequence:** `book is None` for every Bot G order → the function
   falls through to the synth-fill path, which is:
   - Gated on `PAPER_NO_BOOK_SYNTH_FILLS=true` (default `false`, and the
     in-file comment explicitly discourages enabling it for Bot E/G per
     Codex A-12 calibration concerns).
   - Gated on `order_age_s >= 60`. Bot G orders are placed at t-3s to
     t-60s before resolution, so most orders never hit 60s age before
     the market resolves.

3. **`reconcile_paper_resolutions` only processes `Position` rows.** Since
   Bot G creates zero Positions, settlement also never runs for these
   orders. They accumulate as dead `PAPER_OPEN` rows indefinitely.

**Fix options (pick one):**

A. **Recorder-driven paper-fill path.** Teach `simulate_paper_fills` to
   fall back to the recorder's `pm_events` (freshest
   `best_bid_ask`/`price_change`/`book` within 30s) when the `Book` table
   has no row for the token. Mirrors the OQ-043 fallback structure.
   Preserves calibration honesty (uses observed book, not limit-price
   assumption). ~40 LOC + tests.

B. **Bot G writes `Book` rows at entry time.** In `_try_enter_market`,
   after `clob.place_limit`, snapshot the verified (best_bid, best_ask,
   best_ask_size) tuple into `Book`. `simulate_paper_fills` then sees
   the book on its next tick and fills via the existing happy path.
   ~15 LOC. Simpler but spreads Book-writing responsibility outside the
   recorder.

C. **Change Bot G order type to FAK/IOC + teach simulator to fill-at-
   placement for those types.** Semantically most correct (Bot G IS
   effectively taking liquidity at best_ask), but touches CLOB wrapper
   and may affect Bot E. Highest blast radius.

**Recommendation:** A. Closest to the OQ-043 fix pattern, recorder-native,
no cross-bot regression risk. Log a separate ADR.

**Acceptance criteria:**
- Bot G `PAPER_OPEN` order count stays bounded (< 3 at steady state).
- `Position` row appears within 10s of each `entry_placed` log line.
- `reconcile_paper_resolutions` settles Bot G positions within 1h of
  market resolution (existing cadence).
- First realised P&L figure shows up on the dashboard.

**Blocks:** Bot G edge validation (can't measure P&L without fills).

---

### OQ-045 — Permanent `.env` relocation outside project tree (operator + Claude)

**Category:** Operational hardening.
**Owner:** Operator (systemd unit-file edits have fleet blast radius).
**Surfaced by:** 2026-04-23 Session 23 `.env` clobber incident (second
occurrence — SESSION-HANDOFFS.md:311 flagged the first).

**Problem:** `/home/bot/polymarket-bot/.env` lives inside the rsync deploy
target. Any deploy that forgets `--exclude=.env` overwrites the
operator-tuned env with whatever (usually-empty) `.env` the local repo
has. Session 22 and Session 23 both hit this; Session 23 recovered via
the homelab hypervisor daily backup (`<bulk-storage>/`).

The runbook now carries `--exclude='.env' --exclude='.env.*'` on both
rsync commands. That closes the documented path, but off-runbook deploys
still risk clobber.

**Fix:**

1. Move `.env` to `/home/bot/polymarket-bot.env` (sibling of the project
   dir, outside any rsync target).
2. Edit all 12 systemd unit files on the bot LXC container to change
   `EnvironmentFile=/home/bot/polymarket-bot/.env` →
   `EnvironmentFile=/home/bot/polymarket-bot.env`.
3. `systemctl daemon-reload` + restart each service; verify startup
   banners pick up the same env values (bankroll, max prices, etc.).
4. Update deploy-runbook to reference the new path.
5. Update `.env.example` header comment so future-Claude knows.
6. Optionally: write a `scripts/verify_env_present.sh` smoke test so
   pre-deploy verification catches "env file missing" before services
   start.

**Acceptance criteria:**
- `ls /home/bot/polymarket-bot/.env` returns `No such file or directory`.
- All 12 services active and running with the same banner values as
  before the move.
- Next deploy (dry-run) does not touch `/home/bot/polymarket-bot.env`.

**Risk:** one-time surgical change. If a service fails to find the new
EnvironmentFile, it'll start with defaults and paper mode stays paper —
no live-money exposure. Recovery: move .env back + fix unit file.

**Not-in-scope:** unifying `.env` across hosts (Mac laptop vs LXC) — that
remains per-host.

---

### OQ-046 — Bot E recorder WSS subscription gap for near-resolution markets (Claude)

**Category:** Data-ingest correctness. Affects Bot G (zero entries) and
Bot E trader (zero entries) whenever it triggers.
**Owner:** Claude (recorder code).
**Surfaced by:** Session 24 2026-04-23 investigation of Bot G zero-entry
and zero-telemetry post-17:14 deploy.

**Problem:** The Bot E recorder subscribes to WSS by market, one
`subscription_id` per market (n_assets=2 per subscription). Polymarket
hosts multiple strike markets per expiration (e.g. BTC 80400 / 78800 /
79200 all resolving at 18:00 UTC). On 2026-04-23 at 17:10:06 only ONE
BTC-18:00 market got subscribed; the other two did not, despite being
present in the recorder's own `markets` table. Symptom: for those 2
markets, `pm_events` stays empty, `_latest_best_bid_ask` returns None,
Bot G declines to enter AND candidate-distribution telemetry records
no observations.

Additionally, the 16:49:44 WSS reconnect did not resubscribe to every
previously-active subscription — some expiration buckets that were
subscribed pre-disconnect went silent post-reconnect.

**Evidence (2026-04-23 ~17:55 UTC):**

- Bot G market discovery: 3 BTC markets ending 18:00 UTC in 60s window.
- pm_events for all 6 token_ids across those 3 markets: 0 events in
  last 60s. Last event per token: 2026-04-23 17:14:14 (46 min old).
- Recorder currently streams `price_change` for 4 other markets (34
  events/min each), proving the WSS is healthy — just not subscribed
  to the right markets.
- Recorder journal shows `subscription_id=btc-20260423T1800 n_assets=2`
  at 17:10:06 but no follow-up subscription for the other strikes.

**Interim fix shipped (Session 24, commit pending):**

- `_latest_best_bid_ask` cutoff widened 30s → 90s.
- `_record_candidate_observation` now accepts single-side quotes
  (normalises missing side to Decimal("10") so `min(y,n)` picks the
  present side). Rejects only when BOTH sides are missing.

These don't fix the subscription gap — they only stop Bot G silently
dropping observations when one side happens to be fresh and the other
isn't.

**Real fix required:**

1. Audit `core/polymarket_ws.py` (or wherever subscription set is
   maintained) — confirm every market returned by market-discovery gets
   its own subscription, not just one per expiration bucket.
2. Add a `subscription_audit` heartbeat: every N min, log
   `expected_subs=X active_subs=Y diff=[...]` so gaps are visible.
3. On reconnect, re-play the full subscription set from the last known
   good state, not just re-run whatever was in the current scan tick.
4. Add a test: create 3 markets sharing an expiration, simulate a
   reconnect, assert all 6 token_ids remain subscribed.

**Acceptance criteria:**
- For any cid returned by `_active_markets_near_resolution`, at least
  one of {best_bid_ask, book, price_change} event arrives within 30s
  of now for both yes/no tokens, ≥99% of ticks.
- Over a 24h window, `bot_g.candidate_summary` events appear every 5
  min without gaps.
- Post-reconnect behaviour is identical to pre-disconnect
  (subscription set preserved).

**Risk:** The interim fix has no downside — it strictly loosens gates,
but `BOT_G_MAX_ENTRY_PRICE` still bounds actual entry. The real fix
touches the recorder (shared infrastructure), so must go through the
standard deploy flow with all consumers in mind (Bot E trader also
consumes this).

**Blocks:**
- OQ-044 eager-fill verification (no fills happen if books are empty).
- BOT_G_MAX_ENTRY_PRICE ceiling-tune decision (no telemetry = no data).
- Bot E post-17:14 tuning decision (same root cause — trader can't act
  on thresholds it can't evaluate).

---

### OQ-047 — Tactical review execution bundle for Bots C/D/F/G (Claude)

**Category:** Research-required.
**Owner:** Claude.
**Surfaced by:** `docs/audit/codex-fleet-tactical-review-2026-04-23.md`.
**Status:** Code shipped 2026-04-24 in Session 28; forward paper
measurement still required before closure.

**Problem:** The tactical review found four code-level blockers that are
small enough to fix surgically but material enough to distort paper
expectancy if left alone:

1. **Bot C:** no filled-position exit path. `analyst.py` only reviews open
   orders; filled positions hold to resolution even after edge collapse.
2. **Bot D:** `_tail_scaled_cap()` suppresses the 2-5 cent tickets that
   are currently the only profitable subtype.
3. **Bot F mirror:** paper orders are not reconciled into fills, and the
   executor anchors on stale whale prints instead of current recorder asks.
4. **Bot G:** widened 8-cent entry ceiling conflicts with the unchanged
   90-cent counterparty-purity floor.

**Execution order:**

1. Bot G purity-floor fix — cheapest and directly unblocks entry-rate
   measurement.
2. Bot C filled-position exit path — prevents more dead-capital paper
   holds while Hermes data accumulates.
3. Bot D tail-cap relaxation — changes realised EV, so ship only after
   the two pure-correctness fixes above.
4. Bot F mirror fill-path repair — only if the operator still wants the
   executor alive after review; otherwise keep the sensor role only.

**Acceptance criteria:**

- Bot G emits at least one `entry_placed` event on a cheap-side candidate
  day without relaxing the entry ceiling again.
- Bot C writes synthetic SELL trades when a fresh decision flips or
  collapses an existing open position.
- Bot D top-decile edge tickets size above the former 30% floor and the
  cap factor is visible in logs.
- Bot F creates Positions from crossing paper BUYs and reports
  filled-orders / placed-orders plus copy slippage.

**Implementation note 2026-04-24:**

- Bot G default counterparty floor now derives from `BOT_G_MAX_ENTRY_PRICE`
  with a 4c book-shape cushion; `0.08/0.88` books pass.
- Bot C added `review_open_positions()` and calls it after open-order
  review in `analyst.py`.
- Bot D tail cap defaults to `BOT_D_TAIL_CAP_FLOOR=0.60` and
  `BOT_D_TAIL_CAP_START=0.05`, with cap factor logged when applied.
- Bot F mirror uses current recorder asks for BUY copies within
  `BOT_F_MIRROR_MAX_COPY_SLIPPAGE=0.02`; crossing paper BUYs create
  Positions immediately.

**Blocks:** clean tactical measurement for all four paper bots.

---

### OQ-049 — Bot B scorer health and halted-sweep policy (Claude)

**Category:** Trading correctness / infrastructure health.
**Owner:** Claude.
**Surfaced by:** `docs/audit/remaining-bots-profitability-audit-2026-04-24.md`.
**Status:** Open.

**Problem:** Bot B remains halted for E2/ECE, but the daemon still runs
`run_sweep(budget=20)` every tick. On 2026-04-24 the external scorer HTTP
API (Oraclemangle — https://oraclemangle.com) returned repeated `502 Bad
Gateway`; the local circuit breaker reopened after 195 failures and DB
scores were stale since 2026-04-19. This burns operational headroom and
makes Bot B's paper state look active while the actual decision input is
stale.

**Acceptance criteria:**
- [ ] Add a scorer-health gate that records red/yellow/green state in DB or
  Events.
- [x] Skip scoring sweeps while Bot B is explicitly halted unless a manual
  `BOT_B_SCORE_WHILE_HALTED=true` override is set. **Progress 2026-05-01:**
  the Bot B scoring sweep (code excluded from export) now returns
  `skipped_reason="bot_b_halted"` and performs no HTTP/model calls while
  `halt_flags.bot_b.halted=1`, unless the override is set.
- [ ] Fail closed on stale scores for entry decisions; no candidate may use a
  score older than `MAX_SCORE_AGE_HOURS`.
- [ ] Decide whether the scorer/ensemble ownership belongs in this repo or
  stays at the external product boundary (https://oraclemangle.com); document
  with ADR if behaviour changes.
- [ ] Score local scorer / ensemble on held-out data with Brier <= `0.06`,
  weighted ECE <= `0.05`, and per-decile gap <= `0.05` for every bucket with
  `n >= 10`.

**Blocks:** Bot B unhalt and any live-capital allocation to the
Oraclemangle Kelly thesis.

---

### OQ-050 — Bot F wallet-flow cohort policy before allowlist expansion (the operator + Claude)

**Category:** Decision-required / research design.
**Owner:** the operator (policy), Claude (cohort analysis).
**Surfaced by:** `docs/audit/remaining-bots-profitability-audit-2026-04-24.md`.
**Status:** Open.

**Problem:** Bot F's sensor sees abundant fresh would-trade signals, but
the paper mirror's four-wallet allowlist produced only two paper orders
after the latest repair. The highest-volume fresh wallets are not
allowlisted and may be market makers, contract wallets, or hedged actors.
Copying them directly could import unobservable hedging risk and conflicts
with the repo's existing caution around copy-trading and market-making.

**Acceptance criteria:**
- Define paper-only cohorts: current curated sharps, high-frequency
  winners, category-pure sports wallets, and market-maker-like wallets.
- For each cohort, report signal count, fill rate, copy slippage,
  category concentration, time-to-resolution, and eventual P&L.
- No live mirror expansion without a new ADR and operator approval.
- Prefer using Bot F as a wallet-flow estimator for Bot B/E/D filters
  unless direct mirror P&L beats the filter-overlay path.

**Blocks:** Bot F allowlist changes and any Bot F mirror graduation call.

---

### OQ-051 — Bot G split-cohort EV proof before any tuning or live argument (Claude)

**Category:** Research-required / empirical validation.
**Owner:** Claude.
**Surfaced by:** Session 33 Bot G split-runner cleanup and ADR-044.
**Status:** Open.

**Progress 2026-04-30 (Session 50):** Split-cohort evidence is now strong
enough to reject the raw variants and narrow the hypothesis. Production
`scripts/bot_g_feature_analysis.py` on the bot LXC container matched 271 closed archived G
round trips: 1.5% WR, -$822.72 P&L, -73.5% ROI. By cohort: raw G 100 closed /
3 wins / -$205.34; jackpot 84 / 0 / -$350.40; scalp 87 / 1 / -$266.99. By
entry bucket, <=3c was 0-for-216 and -100% ROI; 5c-8c was 29 closed / 3 wins
/ +$94.05. ADR-055 archived `bot_g`, `bot_g_jackpot`, and `bot_g_scalp`, then
deployed paper-only `bot_g_prime` as the single forward cohort: 4c-8c,
30-second final window, required CEX confirmation, depletion telemetry.

**Problem:** Bot G's archived split variants disproved the broad cheap-side
thesis, but the surviving Prime hypothesis still needs forward proof. The
known failure mode remains jackpot concentration: one large winner can hide a
negative base process, especially on small samples.

**Acceptance criteria:**
- During observation, report settled trade count, win rate, realised P&L,
  ROI, largest-win contribution, and ex-largest-win ROI separately for
  `bot_g`, `bot_g_jackpot`, and `bot_g_scalp`.
- Run `scripts/bot_g_feature_analysis.py` with split bot IDs included.
- Run `scripts/bot_g_book_reload_signal.py` on the bot LXC container and test whether
  non-refill/depletion features separate cheap-side winners from losers.
- For Prime specifically, report settled trade count, win rate, realised P&L,
  ROI, largest-win contribution, ex-largest-win ROI, CEX-confirmed vs
  rejected candidates, and depletion telemetry by outcome.
- Deferred research note: if Prime needs extra CEX context, use lightweight
  locally derived OHLCV/regime features from recorder `cex_trades`; do not
  add Kronos as a dependency.
- No widening, sizing increase, hard depletion gate, or live-money proposal
  unless `bot_g_prime` stays positive after fees and after excluding the
  largest 1-2 wins.

**Blocks:** Bot G live-capital argument and any claim that Prime is
profitable.

**Progress 2026-05-01:** First the homelab hypervisor validation pass scoped to
`BOT_G_FEATURE_BOT_IDS=bot_g_prime` loaded `38` Bot G Prime trade rows and
matched `18` closed round trips. Overall paper P&L is `+$146.22` on `$78.78`
cost (`+185.6%` ROI), but largest-win concentration remains material:
largest win `+$120.00`, ex-largest-win ROI `+35.54%`, and
ex-largest-two-wins ROI `-100.0%`. Bucket split shows `0.03-0.05` carried
the result (`8` closed / `2` wins / `+$191.11` / `+563.8%` ROI), while
`0.05-0.08` is still dead (`10` closed / `0` wins / `-100.0%`). Next action:
patch the report to split exact `4c-5c`, fix symbol attribution, add fee
stress, and estimate `$25`/`$50` capacity before any live argument.

**Progress 2026-05-01 live-candidate pass:** Patched and deployed
`scripts/bot_g_feature_analysis.py` to split exact entry buckets, join
`bot_g.entry_placed` payloads for symbol/CEX/depletion metadata, apply V2
crypto taker-fee stress, and estimate `$25`/`$50` entry capacity from recorded
books. Current Bot G Prime result: `19` closed round trips, `+$141.95`,
`+170.9%` ROI, `+28.12%` ex-largest-win ROI, `-100.0%`
ex-largest-two-wins ROI. Exact `4c-5c` is the only positive cohort
(`9` closed / `2` wins / `+$186.83` / `+489.5%` ROI); `5c-8c` remains dead
(`10` closed / `0` wins / `-100.0%`). CEX-confirmed entries were `0/3`;
current CEX confirmation is not a promotion argument. Fee stress remains
positive, but recorded book capacity supported `$25` at the entry limit in
only `1/19` closed trades, so Bot G is live-candidate but not live-ready for
meaningful `$25-$50` order sizing.

**Progress 2026-05-01 all-available-history pass:** Checked the actual local
coverage. Bot G-specific history on the bot LXC container runs from `2026-04-23` to
`2026-05-01`, not months. Running all available Bot G cohorts
(`bot_g`, `bot_g_jackpot`, `bot_g_scalp`, `bot_g_prime`) matched `290` closed
round trips with total P&L `-$680.77` and ROI `-56.6%`. Exact entry buckets:
`<3c` was `188` closed / `0` wins / `-100.0%`; `3c-4c` was `28` / `0` /
`-100.0%`; `4c-5c` was `35` / `3` / `+$185.78` / `+133.4%`; `5c-8c` was
`39` / `3` / `+$49.16` / `+33.3%`. This supports the narrow `4c-5c` direction
but does not validate Bot G over months or at `$25-$50` capacity.

**Progress 2026-05-01 reporting rollout:** Added Bot G paper-validation
splits to the hourly fast-ROI report and dashboard: exact `4c-5c`, `5c-8c`,
all `4c-8c`, ex-largest-win ROI, ex-largest-two-wins ROI, CEX-confirmed vs
unconfirmed, and `$25`/`$50` capacity coverage. Future Bot G entry events now
log book depth at the entry limit, limit+1c, and limit+2c. This keeps the
operator-visible posture explicit: `4c-8c` remains paper data collection, but
only `4c-5c` currently carries a positive signal.

**Progress 2026-05-01 production deploy:** Deployed the Bot G reporting
rollout to the bot LXC container and manually ran the hourly report. Current dashboard/report
read: `4c-5c` `10` closed / `2` wins / `+421.22%` ROI; `5c-8c` `11` closed /
`0` wins / `-100.0%`; all `4c-8c` `21` closed / `2` wins / `+141.79%` ROI,
`+13.57%` ex-largest-win ROI, `-100.0%` ex-largest-two-wins ROI, and `$25`
at-limit capacity coverage `1/21`. No post-deploy `bot_g.entry_placed` event
had occurred yet, so exact `capacity_depth` payload validation remains open.

**Progress 2026-05-01 Phase 0/1:** Fresh post-deploy `bot_g.entry_placed`
at `2026-05-01 21:30:06 UTC` includes `capacity_depth`; dashboard and hourly
fast-ROI report now surface this latest telemetry status. The book-reload
script now has a fast `--main-db` mode that uses causal depletion fields
captured at entry and labels them with FIFO outcomes. the bot LXC container run on `14`
realised Prime entries: refilled entries (`depletion_ratio > 1.1`) were
`0/8`; depleted/slight-drop entries were `2/5`. This supports further
research as a veto feature, not a hard live gate.

**Progress 2026-05-02 capacity gate:** ADR-073 now defines the Bot G Prime
reporting gate: candidate status requires at least `20` closed `4c-5c` paper
round trips, positive ex-largest-win and ex-largest-two ROI in `4c-5c`, `$25`
at-limit depth coverage of at least `50%`, and `$50` limit+2c coverage of at
least `25%`. Dashboard and fast-ROI reports now show `blocked_by_trimmed_roi`,
`blocked_by_capacity`, `collecting_sample`, or `candidate` with failed checks.
This is reporting-only; Bot G remains paper-only and order behavior is
unchanged.

**Progress 2026-05-02 production read:** After deploy, `/api/bot-g` reports
gate status `blocked_by_trimmed_roi` with failed checks for minimum `4c-5c`
sample, ex-largest-two ROI, `$25` at-limit capacity, and `$50` limit+2c
capacity. Fast-ROI read: `4c-5c` is `12` closed / `2` wins / `+359.4%` ROI,
ex-largest-win `+127.4%`, ex-largest-two `-100.0%`, `$25` at-limit depth
`0/12`; all `4c-8c` is `31` closed / `4` wins / `+142.9%` ROI,
ex-largest-two `-24.0%`, `$25` at-limit depth `1/31`.

**Progress 2026-05-02 observational labels:** Added paper-only diagnostic
labels for `$25/$50` capacity class and depletion/reload class. Production
read: `toy_fill_only` carries nearly all Bot G ROI (`30` closed / `4` wins /
`+152.6%` ROI, ex-largest-two `-20.7%`), well as the only `sizeable_at_limit`
sample lost `-100.0%`. Depletion labels are not live gates: `depleted_or_slight_drop`
is raw-positive but ex-largest-two `-100.0%`; `refilled` is raw-positive but
ex-largest-win `-51.8%`. This strengthens the current conclusion that Bot G
is promising but still blocked by capacity/outlier shape.

**Status 2026-05-09 — RESOLVED.** Per
`docs/reports/bot-g-final-review-2026-05-09.md`: cohort-level evidence
is decisive across the full Bot G Prime family.
- `bot_g_prime` (paper, 4-8c): `143` closed / `13` wins / `+$327.42` /
  `+62.1%` ROI; ex-largest `+$207.42`; **ex-largest-2 `+$87.42`**.
  Survives ex-largest-2 trimming, but the headline is concentrated in
  the `6.5c-8c` jackpot bucket (per ADR-135: 6 wins / 25 closed /
  `+$192.54` / `+205%`). The live band `3.5c-5.5c` is decisively
  negative across paper mirror, late-cheap, take-profit, and live.
- `bot_g_prime_shadow` (paper 3.5-5.5c): `74` closed / `2` wins /
  `-$161.81` / `-57.4%` ROI; ex-largest worse.
- `bot_g_prime_late_cheap` (paper 1-3c): `152` closed / `1` win /
  `-$560.71` / `-86.4%` ROI; ex-largest worse. Thesis falsified.
- `bot_g_prime_take_profit` (paper 3.5-5.5c with synthetic 50c TP):
  `65` closed / `1` win / `-$184.15` / `-67.5%` ROI; ex-largest
  worse. Take-profit replay shows `0/26` positions ever hit the 50c
  threshold; **TP thesis decisively falsified**.
- `bot_g_prime_live`: `51` closed / `1` win (SOL NO at 4c) /
  `-$82.84` / `-80.6%` ROI; ex-largest = `-$101.98` (single win is
  propping up the entire ledger). 18/51 orders EXCHANGE_CLOSED before
  fill = 35% miss rate.
**No live promotion is defensible. ADR-135 emergency-pause posture
stands. ADR-136 `$1` data probe continues at operator's discretion.**
The split-cohort proof asked by this OQ is complete.

---

### OQ-052 — Bot D live-exit integrity before any live-capital proposal (Codex)

**Category:** Live-safety / trading correctness.
**Owner:** Codex.
**Surfaced by:** Session 34 seven-bot deployment readiness audit.
**Status:** Open.

**Progress 2026-04-25 (Session 36):** Core accounting hazard partially
fixed. Bot D now keeps synthetic SELL closes paper-only; live edge exits
place real CLOB SELL orders and leave `Position` rows open until
reconciliation imports a real fill. Paper-resolution reconciliation is now
gated to paper mode. Tests cover live no-synthetic-close behavior. Patch
was deployed to the the bot LXC container Bot D paper runtime and `polymarket-bot-d`
restarted active with `BOT_D_ENV=paper`. OQ stays open for
dashboard/Telegram mismatch alerting and the live exit runbook.

**Problem:** Bot D could synthetic-close local `Position` rows by writing a
SELL trade through `Portfolio.on_fill()` when an open order is cancelled or
when edge decays/flips. This is valid as paper accounting, but unsafe in
live mode: the DB can report the position closed while the wallet still
holds outcome tokens. The affected paths are
`bots/bot_d_weather/executor.py:437-472` and
`bots/bot_d_weather/executor.py:483-598`.

**Acceptance criteria:**
- [x] Synthetic Bot D SELL closes are explicitly paper-only.
- [x] Live Bot D exits place a real CLOB SELL order or leave the position
  open/unresolved with an alert.
- [x] Unit tests prove live mode cannot close local exposure without a real
  order path.
- [ ] Reconciliation surfaces any local/wallet exposure mismatch in dashboard
  and Telegram.
- [ ] The Bot D live runbook includes edge-decay, edge-flip, emergency-exit,
  and failed-exit handling.

**Progress 2026-05-01:** Dashboard now surfaces Bot D wallet-readiness and
lock-up blockers from the read-only readiness report: stale orders, stale
positions, daily/weekly order split, recent fills, and NWS veto/entry flow.
This is not full wallet/local exposure reconciliation yet, so the acceptance
item remains open.

**Progress 2026-05-01 later:** The dashboard now shows a clean daily-only Bot
D paper state after cleanup: stale orders `0`, stale positions `0`,
weekly-lock orders `0`, open positions `3`, and recent fills `3`. The live
runbook item remains open.

**Progress 2026-05-14 (ADR-166):** Added and deployed Bot D report-only open-position
validation. Each open Bot D position can now be classified as `HOLD`, `WATCH`,
`SELL_RECOMMENDED`, or `SELL_NOW` using current token book, entry cost,
mark-to-market loss, hours-to-end, fresh forecast edge when present, pending
SELL state, and latest raw settlement-station source snapshot. Raw station
invalidation and stop-loss-with-invalidating-data now produce validation
events, but validator-driven live auto-sell remains disabled by default via
`BOT_D_POSITION_AUTO_SELL_ENABLED=false`. OQ-052 remains open for dashboard /
Telegram mismatch alerting, runbook updates, and explicit operator approval
before any validator-driven live auto-sell is enabled.

**Auto-sell review gate:** Revisit after at least 30
`bot_d.position_validation` events, including at least 10
`SELL_RECOMMENDED` or `SELL_NOW` cases across at least one full weather week.
Before enabling validator-driven live auto-sell, the replay must show:
`SELL_NOW` would have saved money after spread/slippage on at least 80% of
cases, zero `SELL_NOW` exits on positions that later resolved as winners,
source snapshots stale or missing in no more than 20% of reviewed positions,
and executable bid availability when the recommendation fired. Enabling
requires explicit operator approval and either a runbook/dashboard update or a
new ADR if the operating posture changes.

**Blocks:** Bot D live-capital proposal, Bot D tiny-live stage, and any
claim that Bot D is execution-ready.

---

### OQ-053 — Recorder storage, retention, and integrity after disk-full recovery (Codex)

**Category:** Research-required / infrastructure reliability.
**Owner:** Codex.
**Surfaced by:** Session 37 fleet status recovery.
**Status:** Open.

**Progress 2026-06-03 (ADR-188):** the bot container Bot E recorder failed again after
the dedicated recorder mount reached `250G / 100%` with only about `27M`
free. The recorder journal showed bulk queue drops, systemd watchdog timeouts,
and start-limit exhaustion. Recovered by expanding the bot container `mp1` from `250G` to
`300G`, moving the failed oversized Bot E DB set out of the active hot path
under `data/recorder/bot_e_recorder_20260602T185637Z_failed_full.pending_offload/`,
starting a fresh active `bot_e_recorder.db`, mounting the homelab hypervisor bulk storage at
`data/recorder_archive`, and offloading the failed DB set to
`<bulk-storage>/ bot container`. Added an hourly storage-health timer
and a 15-minute recorder guard that stops only `polymarket-bot-e-recorder`
when recorder disk exceeds `90%` used or falls below `20GB` free, plus the
same guard as Bot E `ExecStartPre`. OQ-053 remains open for a permanent
rollover/retention design and verified integrity checks on archived recorder
segments.

**Progress 2026-06-07 (Grok Build Session 466):** Code audit + empirical verify (P0) of guard/health/offload per ADR-188/S465: guard.py:16-17/42-52 (DEFAULT_RECORDER_PATH, critical calc >=90% or <=20GB, if stop-on-critical: subprocess stop e-recorder only, json, return 2 if crit), health.py:21-25/74-80 (KILL_PCT=90, MIN_FREE recorder=20, criticals incl nested forks), bot-e-recorder.service:33 (ExecStartPre guard no-stop flag so pre-fails start on crit), recorder-storage-guard.{service:9 (with --stop), timer:5 OnCalendar=*:0/15}, storage-health.timer hourly (M). Tests: test_bot-host_storage_health.py:82-84 (rc=2 no stop calls), 113-114 (stop calls w/ flag). Subagent + VPS probe (the-vps): recorder active, 0 failed, 93% root (67G used/5.4G free run-spec 2026-06-07), fresh 54GB db + wal mtime now, qsize=0 drops, logs advancing; the bot container hypervisor-host ssh timeout (env, all attempts); local sims/ .venv pytest 15/15 pass. Offload ad-hoc (no unit in repo; .pending_offload/ + recorder_archive/ per recovery). Recovery files ?? untracked at start (pre git status snapshot taken per avoid-pattern); git add staged (A). No logic edit (smallest; no crash on non-crit). Gaps: no full retention/rollover (OQ stays open); VPS no guard equiv (root risk); guard.py was untracked. OQ-053 **Open** (research-required / infrastructure; owner Codex). See ADR-189, /tmp/storage-verify-the bot container-vps-20260603.md, CHANGELOG 466. Next: operator re-execute the bot container cmds on net host; add integrity to storage-health.

**Progress 2026-05-24 (Session 455):** the bot container Bot E recorder failed again from
recorder storage pressure. This was not the separate VPS: the full filesystem
was the homelab hypervisor the bot container `mp1` at
`/home/bot/polymarket-bot/data/recorder` (`fast-vm:subvol-105-disk-1`), which
had reached `100G / 100%`. Resized `mp1` in place to `250G`; final check
showed `101G` used, `150G` available, `41%` used. Reset/restarted
`polymarket-bot-e-recorder.service`; it remained active past the prior 180s
systemd watchdog abort point with fresh `pm_subs=14 cex_last_age_s=0`. Also
fixed `core/watchdog.py` to avoid `MAX(...)` scans on the hundreds-of-GB
recorder DB by reading latest append-only rows with
`ORDER BY id DESC LIMIT 1`. OQ-053 remains open: resize buys headroom, but
does not replace a retention/rollover policy or verified large-DB backup and
integrity plan.

**Progress 2026-05-07 (Session 205):** Added the homelab hypervisor pull backups for the
the VPS provider VPS state DBs. `hypervisor-host` now runs
`longshot-vps-pull-backup.timer` every 6 hours, pulling over Tailscale from
`root@192.0.2.1` into `<bulk-storage>/`. First verified run:
`<bulk-storage>/`; both
`bot_g_vps_main.db` and `main.db` passed table-count verification,
`PRAGMA quick_check`, SHA256 recording, and zstd validation. The large
VPS recorder DB remains unresolved: online SQLite `.backup` stalled under
active writes and a raw DB/WAL/SHM hot copy failed verification as malformed.
Do not prune or delete VPS recorder rows until a controlled rollover/sharding
or maintenance-window backup passes verification.

**Progress 2026-05-14 (ADR-168):** the bot container root-disk pressure was repaired and
hardened. Backups/snapshots were moved under mounted external storage at
`data/external/root-disk-relief-20260514/`; large live SQLite DBs and
WAL/SHM sidecars were moved under
`data/external/live-dbs-20260514/`; original service paths now use absolute
symlinks. Added `scripts/bot-host_storage_health.py` plus
`polymarket-storage-health.service/timer`, and capped journald. Final the bot container
checks after migration: `/` 7% used, `data/external` 36% used,
`data/recorder` 21% used, `0` broken data symlinks, DB smoke query clean, and
no failed units. OQ-053 remains open for the VPS crypto recorder rollover /
backup posture and broader retention policy.

**Progress 2026-05-15 aggressive review (ADR-171):** Found a post-ADR-168
storage-sandbox regression. `polymarket-wallet-observer.service` is active
and logging fresh fills, but it is writing a forked DB under
`data/data/external/live-dbs-20260514/wallet_observer.db` (`10,061` fills,
fresh `inserted_at`) while reports read the canonical
`data/external/live-dbs-20260514/wallet_observer.db` (`489,155` fills, stale
after the 2026-05-14 restart). `polymarket-wallet-tag-strict-monitor.service`
also failed opening the symlinked DB. Repo-local systemd units now include
`data/external` in the relevant read/write sandboxes, and
`scripts/bot-host_storage_health.py` now fails on nested
`data/data/external/**/*.db` forks. Host deployment, DB reconciliation, and
affected service restarts still require explicit operational approval.

**Progress 2026-05-15 deployment:** the operator approved the the bot container repair. Deployed
the external-DB sandbox fixes, reconciled the Wallet Observer nested fork into
the canonical DB (`489155` -> `500189` fills, `11034` unique rows inserted,
`quick_check=ok`), archived remaining nested `main.db`,
`persistence_live.db`, `wc_negrisk_basket_paper.db`, and `maker_recorder.db`
forks under `data/reconcile-backups/20260515T093007/nested-external-unmerged/`,
reloaded systemd, restarted affected units, and removed broken WAL/SHM
symlink sidecars. `bot-host_storage_health.py` now reports no broken symlinks, no
nested external DB forks, and no critical/warning conditions; `systemctl
--failed` is empty.

**Progress 2026-04-25 (Session 37):** Immediate outage resolved. The
duplicate `/home/bot/.cache/hf-source` HuggingFace cache was removed from
the LXC rootfs and symlinked to the existing ZFS-backed
`/home/bot/.cache/huggingface` mount. Rootfs recovered from 95% used to
35% used. `polymarket-bot-e-recorder` and `polymarket-bot-f-mirror` were
reset and restarted active. `bot_e_recorder.db` is readable and writing
fresh PM/CEX ticks, but a full SQLite `PRAGMA quick_check` on the 13GB DB
was too slow to complete during the recovery window.

**Problem:** The recorder is now large enough to make rootfs fill-up a
live data-quality risk. When disk reached 100%, Bot E recorder write
failures led to writer-stall abort and systemd restart-limit. Bot F mirror
also died on SQLAlchemy `database or disk is full`. Without retention,
mounting, integrity checks, and alerting, the same failure can recur and
silently starve calibration data.

**Acceptance criteria:**
- Decide whether recorder data belongs on rootfs, the ZFS-backed
  HuggingFace/cache mount, or a new dedicated data mount.
- Add a retention/rollover plan for `bot_e_recorder.db` that preserves the
  calibration windows Bot E/Bot G actually use.
- Complete a safe integrity check on `bot_e_recorder.db` and document
  whether any repair/export is needed.
- Add disk-pressure alerting before 85% rootfs use and a hard fail-safe
  before 95%.
- Document the recovery runbook: `systemctl reset-failed`, restart order,
  freshness queries, and DB corruption checks.

**Blocks:** Bot E calibration reliability, Bot G/Bot E tape-dependent
analytics, and any claim that recorder-dependent strategies have production
data continuity.

---

### OQ-054 — `halt_flags` rows carry stale "unhalt" reason text despite `halted=1` (Claude)

**Category:** Data hygiene / operator-audit clarity.
**Owner:** Claude.
**Surfaced by:** Session 39 Bot C archive-cleanup investigation.
**Status:** Open. Cosmetic, not blocking.

**Problem:** Six rows in `halt_flags` (`bot_a`, `bot_c`, `bot_d`,
`bot_e`, `bot_a_shadow`, `bot_b_shadow`) all carry `halted=1` with
`set_at='2026-04-25 17:15:25'` and `reason` text starting "Session 17f
late: unhalt for paper-data collection; all bots in BOT_X_ENV=paper".
The reason narrative says "unhalt" but the boolean is 1 (halted).
Either the writer (likely the watchdog or an operator script) used an
upsert that updated `halted` and `set_at` but failed to refresh
`reason`, or the operator originally set the row to `halted=0` and a
later watchdog pass flipped only the boolean. Bot C's case
specifically: ADR-034 archived it on 2026-04-18, so the operative
halt cause is "ADR-034 archived" — the row text doesn't reflect that.

**Why it matters:** any operator using the row's reason field to
diagnose why a bot is halted gets misleading information. Code paths
read only `halted`, so behaviour is correct; the data is just
confusing for human eyes.

**Acceptance criteria:**
- Find the writer that flipped `halted=1` on these rows (watchdog?
  manual SQL? archive script?).
- Patch it to also rewrite `reason` and `set_at` whenever the boolean
  changes.
- Backfill the 6 stale rows with current accurate reasons (e.g. for
  Bot C: "ADR-034 archived 2026-04-18 — Pyth ingest broken + thin
  market universe").
- Add a regression test that flips a halt and asserts the reason
  text reflects the new state.

**Blocks:** nothing operationally; useful for future operator audits
and any tooling that surfaces halt reasons in dashboards.

---

### OQ-056 — Recorder write_queue saturation under sustained PM load (Claude)

**Category:** Reliability — newly surfaced after the OQ-055 fixes.
**Owner:** Claude.
**Surfaced by:** Session 39, 2026-04-26 10:07 UTC external freshness
watchdog page.
**Status:** Mitigation #4 deployed 2026-04-29; 24h clean production soak
pending before closure.

**Problem:** The OQ-055 fixes (`4a0559d` WAL TRUNCATE on init,
`201d11f` writer-alive tick) prevented the *internal* writer-stall
abort. With internal aborts gone, the recorder now runs long enough
to expose a slower failure mode: ``write_queue`` (50,000-slot
asyncio queue) saturates under sustained PM event load. Once full,
new puts are dropped (``recorder.heartbeat_dropped_queue_full``),
and because heartbeats can't reach the DB, the *external*
``recorder.freshness`` watchdog correctly fires after 120 s. Symptom
chain: queue fills → heartbeats drop → freshness check fails
externally → ``halt_flags.bot_e=1``. Recorder process stays alive
(writer-loop iterates, internal abort doesn't fire); the writer
just can't drain fast enough.

**Observed instance (2026-04-26):**

- 08:28:13 UTC — recorder restarted (clean state)
- ~10:00 UTC — ``write_queue`` saturated at 50,000 (visible in
  ``recorder.heartbeat_dropped_queue_full`` storm)
- 10:07:25 UTC — external watchdog page; ``status="pm_subs=11
  cex_last_age_s=784"`` (CEX websocket also silent for 13 min,
  separate concern)
- 10:08:53 UTC — manual restart (queue cleared, freshness
  recovered to 14 s within 25 s)

**Hypotheses (in rough order of fit):**

1. **Sustained PM event rate exceeds the writer's drain rate** under
   ZFS/lz4 + 16 GB DB. ``BATCH_SIZE=200`` + ``FLUSH_INTERVAL=2.0`` =
   100 events/sec drain rate ceiling; if PM bursts exceed that,
   queue grows monotonically. Worth measuring: actual events/sec
   sustained from the WSS streams vs actual flushes/sec from the
   writer over a 30-min window.
2. **Brief writer pauses (e.g. SQLite checkpoint or fsync stall)
   leave the queue with no drain time** until they resolve, and the
   queue can fill within seconds at burst rate. A single 30 s pause
   at 200 events/sec = 6,000 queued; 90 s = 18,000.
3. **CEX websocket reconnect storms** could pump trades into the
   queue in batches. The 784 s CEX silence preceding the 10:07 page
   is a clue — was there a reconnect just before? The next saturation
   incident should be diagnosed against ``cex_ws.connected`` /
   ``cex_ws.disconnected`` log timestamps.

**Mitigation #1 deployed 2026-04-26 ~10:30 UTC:**

- Refactored the inline subscription-close block in
  ``bots/bot_e_recorder/capture.py`` into a module-level
  ``_close_subscription()`` helper that drops EVERY per-sub field
  from ``RecorderState``, including ``last_pm_by_sub_ms``. The
  previous code popped ``pm_tasks`` and ``pm_clients`` but left
  ``last_pm_by_sub_ms`` populated. Across market rotations the dict
  accumulated entries for every sub the recorder had ever seen,
  inflating heartbeat fan-out and the ``pm_subs=N`` status counter.
  Observed drift before the fix: 11 entries after 1h39m uptime
  versus ~3 actually live subs.
- Three regression tests under
  ``tests/bot_e_recorder/test_capture_writer.py::TestCloseSubscription``.
- This is a small bug. As predicted in the original OQ-056
  hypotheses, it did NOT fix the saturation — heartbeat volume is
  trivial. Saturation #2 fired at the ~56-minute mark right after
  this deploy. Saturation #3 followed.

**Mitigation #2 deployed 2026-04-26 ~12:55 UTC — synchronous=OFF:**

After three saturations confirmed Hypothesis 1 (writer drain rate
< sustained input rate), patched ``bots/bot_e_recorder/schema.py``
to set ``PRAGMA synchronous=OFF`` instead of ``NORMAL``. Effect:
each commit skips the per-transaction fsync. Trade-off: power-loss
or kernel-panic during a write can corrupt the WAL. Acceptable for
this DB (research/calibration data, UPS-backed homelab, redundant
ZFS pool, replaceable from upstream feeds). The trade does NOT
apply to ``data/main.db`` (trades, positions, halt flags).

Measured input rate at deploy: 70 events/sec sustained
(CEX ~45, PM ~25, heartbeats ~0.5). Pre-fix drain ceiling
~100/sec (one fsync per ~2 s flush) — too thin a margin against
bursty PM activity. Post-fix drain ceiling expected ~500-1000/sec.

Test: ``test_synchronous_off`` in
``tests/bot_e_recorder/test_schema.py`` asserts
``PRAGMA synchronous == 0`` after ``init_db``. Note: the pragma
is per-connection in SQLite, so other connections (analysis
scripts) querying the recorder DB will see their own default —
this only governs the *recorder's own* writer connection.

**Mitigation #3 deployed 2026-04-28 — 200,000-slot queue cap; refuted
by production 2026-04-29:**

Commit `7a5829d` raised
`bots/bot_e_recorder/capture.py::RecorderState.write_queue` from
50,000 to 200,000 slots after V2 cutover pushed peak observed event
rate from ~70/sec to ~3,000+/sec. The memory trade was fine on the bot LXC container, but it was only burst tolerance. Production later showed
`recorder.heartbeat_dropped_queue_full ... qsize=200000` starting
2026-04-28 20:01:30 UTC and continuing for hours. Read-only DB
freshness checks on 2026-04-29 found `pm_events`, `cex_trades`,
`heartbeats`, and `markets` all stale by ~36,200 seconds while the
recorder process was alive and consuming ~88% CPU. This proves
writer drain rate and/or event intake shape is still below sustained
V2 burst load; raising the buffer alone is not a real fix.

The old subscription-state leak appears absent in this incident.
Journald showed `recorder.subscription_audit n_markets=14
n_subscriptions=14` at 2026-04-28 20:00:25 UTC, immediately before
the first full-queue warnings at 20:01:30 UTC. Earlier rotations
logged matching opens and closes, including temporary market-count
drift that reconciled on the next scan. The frozen `pm_subs=14`
status after saturation is consistent with the discovery loop being
blocked on `await state.write_queue.put(...)`, not stale closed
subscriptions lingering in `last_pm_by_sub_ms`.

The next fix should not be framed as "add multiple SQLite writers".
SQLite serializes write transactions, so multiple writers alone will
mostly add lock contention. The architecture needs measured
throughput and backpressure: non-blocking / droppable market and
heartbeat writes so subscription reconciliation cannot freeze, larger
flush batches with queue-depth and rows/sec telemetry, selective PM
event capture or active-market thinning, and/or an append-friendly
raw-tape sink if the recorder must preserve every V2 event.

**Mitigation #4 deployed 2026-04-29 — priority queue + bulk
drop-on-full + larger flushes:**

Implemented the architecture fix in
`bots/bot_e_recorder/capture.py`. Recorder writes are split into a
bulk queue for PM/CEX/market tape and a 10,000-slot priority queue
for heartbeats and discovery status. Bulk writes use
`put_nowait`; when saturated they drop and increment
`recorder.write_queue_drop` counters instead of blocking the event
loop. Discovery now reconciles stale subscriptions before any
best-effort market snapshot enqueue, so a full bulk queue cannot
freeze `_close_subscription()` or leave `pm_subs` stale. The writer
drains priority rows first, then bulk rows in chunks, flushing up to
5,000 rows every 0.5 s, and emits `recorder.writer_metrics` with
queue depth, enqueue, flush, and drop counters.

Local verification: recorder suite 50 passed, compileall passed,
and Ruff passed on touched recorder files. the bot LXC container verification:
deployed `capture.py` and tests, remote recorder suite 50 passed,
then hard-killed and restarted the wedged recorder to drop the stale
in-memory backlog. Six-minute production soak showed
`bulk_qsize=0`, `priority_qsize=0`, `dropped={}`, fresh DB max
timestamps, and continuing subscription audits through market
rotation (`n_markets=7 n_subscriptions=7`). Bot E was unhalted after
freshness recovered.

**Acceptance criteria for closing this OQ:**
- Keep 24h production recorder uptime after Mitigation #4 with
  `bulk_qsize` bounded, `priority_qsize` bounded, `dropped={}`, and
  DB freshness under the watchdog threshold.
- Confirm no new `watchdog.recorder.freshness` Event rows after the
  2026-04-29 restart.
- Treat the 2026-04-28 20:01:30 UTC through 2026-04-29 restart window
  as unreliable for Bot E calibration/tuning.

**Blocks:** Bot E calibration/tuning trust until the 24h post-Mitigation #4
soak is clean. If queue depth or drops recur, the recorder needs capture
thinning or a different raw-tape sink before Bot E evidence is reliable.

**Related:** OQ-055 (writer-stall variant). OQ-056 is the failure
mode that *replaced* OQ-055 once the writer-alive tick made the
internal guard correct.

---


## Deferred

### OQ-034 — Polymarket V2 migration / live-money graduation gate

**Category:** Live-governance gate — V2 technical readiness is complete;
non-smoke live trading still requires explicit operator approval.
**Owner:** Operator + Claude Code.
**Surfaced by:** audit 2026-04-18 meta-review missed risk M-05 (neither
Codex, Claude, nor security-audit flagged this; MEMORY.md
`polymarket_v2_migration.md` is the authoritative project-side record).

**Context:**
- Polymarket shipped V2 ~2026-04-07. Collateral changed (USDC.e → Polymarket USD),
  a new `py-clob-client-v2` is required, the CTF Exchange V2 contract is
  canonical, and Amoy CLOB was decommissioned.
- Repo at HEAD still imports `py_clob_client.client.ClobClient` in `core/clob.py`.
  New `core/clob_v2.py` + `core/polymarket_v2.py` scaffolds exist but are not
  yet wired into Bot A/B/C/D/E executors.
- The live live-gate (preflight.verified) was written against V1 addresses.
  Running live through the V1 client post-decommission will fail
  authentication at best, or route orders to a stale contract at worst.

**Trigger:** any live-graduation request for any bot. Watchdog + fleet-cap
infra does NOT gate on V2 readiness — the operator + Claude must verify
before flipping `POLYMARKET_ENV=live`.

**Unblock checklist:**
1. Install and smoke-test `py-clob-client-v2` (contract addresses, auth flow).
2. Port `ClobWrapper` to V2 (or add `ClobWrapperV2` and a flag).
3. Rerun `scripts/preflight_check.py` against V2 contracts; re-emit
   `preflight.verified` Event.
4. Update ADR (ADR-033 or later) documenting the cut-over decision.
5. Full paper→live smoke test on Bot A with small-size orders.

**Progress 2026-04-26 (Session 39):**

Verified Polymarket's V2 spec end-to-end against the official docs
(``docs.polymarket.com/v2-migration``) and the public
``py-clob-client-v2`` repo. Confirmed cutover slipped from the
originally-anticipated 2026-04-22 to **2026-04-28 11:00 UTC**. ~1 h
maintenance window, all open orders wiped.

Code changes shipped (paper-mode-only, V1 still wired):
- ``core/polymarket_v2.py`` cutover date corrected; added
  ``BYTES32_ZERO`` constant for builder/metadata defaults.
- ``core/config.py`` ``Settings.polymarket_builder_code`` field
  added (env-driven, operator-only secret).
- ``core/clob_v2.py`` accepts ``builder_code`` in the constructor,
  resolves via env → settings → ``BYTES32_ZERO``, normalises to
  lowercase 0x-prefixed bytes32, falls back on invalid values.
  Plumbed through ``OrderArgs.builder_code`` on every live order.
  New ``get_clob_market_info(condition_id)`` helper returns the
  V2 single-call response shape ``{mts, mos, fd: {r, e, to}, t,
  rfqe}`` verbatim.
- ``pyproject.toml`` adds ``py-clob-client-v2>=1.0.0`` alongside
  the V1 client until cutover.
- 7 new regression tests under ``TestBuilderCode`` and
  ``TestGetClobMarketInfo`` (resolution rules, normalisation,
  invalid-fallback, response-shape handling).
- ``test_cutover_timestamp_is_parseable`` updated to assert day=28.
- Suite total: 1170 passing / 1 pre-existing dashboard failure.

What still has to happen before/on 2026-04-28:
- **Operator-only:** grab the personal builder code from
  polymarket.com's settings UI (it's a public identifier, not
  secret, but only the operator can fetch it from their account).
  Set ``POLYMARKET_BUILDER_CODE=0x...`` in the bot LXC container ``.env``.
- **Operator decision:** USDC.e → pUSD migration via website (one
  click for UI users) OR via API ``CollateralOnramp.wrap()`` from
  our code. The website path keeps the same hot wallet
  (``0xc1da…4485a``) and avoids new code; recommended.
- **Claude (cutover day):** flip the import in each bot's
  ``__main__.py`` from ``ClobWrapper`` to ``ClobWrapperV2``,
  ``pip install py-clob-client-v2`` on the bot LXC container, restart all bot
  services, verify clean startup.
- **Claude (post-cutover):** re-run ``scripts/preflight_check.py``
  against V2 addresses; emit fresh ``preflight.verified`` event.
- **Claude (cleanup follow-up):** remove the V1 ``py-clob-client``
  dependency from ``pyproject.toml`` once V2 is stable; archive
  ``core/clob.py``.

**Progress 2026-04-28 (Session 41):**

Polymarket V2 is live per the official migration docs. Local code has moved
from pre-cutover-ready to V2-routed:

- ``core/clob_v2.py`` now uses the official
  ``/clob-markets/{condition_id}`` endpoint and the V2 SDK's typed payloads
  for single-order cancel, market cancel, and market-filtered open-order
  lookup.
- ``scripts/approve_polymarket.py`` now targets pUSD + V2 standard /
  neg-risk exchanges from ``core.polymarket_v2`` instead of V1 USDC.e
  exchange approvals.
- ``scripts/mark_cutover_cancelled_orders.py`` added as a DB-only, dry-run
  default cleanup for pre-cutover live/open ``Order`` rows that Polymarket
  wiped during migration.
- ``scripts/cutover_v2_flip.py --apply`` was run locally. Result: 21 import
  lines across 20 bot/script files now import
  ``ClobWrapperV2 as ClobWrapper`` from ``core.clob_v2``.
- Local post-cutover preflight passed V2 address checks; V1 auth/collateral
  checks skipped as expected after cutover.
- Local and the bot LXC container cleanup dry-runs found 0 candidate rows. No order-cleanup
  production DB mutation was performed.
- Verification: V2 focused suite 95 passed; executor/watchdog/liquidation
  smoke suite 144 passed; compileall passed.
- Source overlay deployed to the bot LXC container; all 14 `polymarket-*` services
  restarted active.
- `scripts/preflight_check.py --commit` ran on the bot LXC container and wrote a
  successful POST-cutover `preflight.verified` Event.
- `core.notify` logging hardening shipped after a journal scan found the
  Telegram bot token in historical `httpx` request URLs; see OQ-057.

**Progress 2026-04-29 (Session 44):**

On-chain wallet migration completed. Wallet `0x5359B1d4…3714cd`:

- USDC.e 454.034104 → pUSD 454.034104 via `scripts/wrap_usdce_to_pusd.py`
  (smoke + `--all`, txs `0xfad7e642…e7721`, `0x2e30fbd2…20787`).
- Pre-approved `CollateralOnramp` MAX for any future USDC.e top-up
  (`0xf6c31f58…39540`).
- `pUSD → CTF Exchange V2` MAX (`0x7a33ea0d…e5f7`).
- `pUSD → NegRisk Exchange V2` MAX (`0x26bf03bf…c397`).
- `ConditionalTokens.setApprovalForAll(true)` for CTF V2
  (`0x2a728e01…64b9`) and NegRisk V2 (`0x227ab7fe…1c74`).
- End-to-end V2 smoke: `scripts/dry_run_order.py --mainnet` placed BUY
  5 @ $0.01 on a non-neg-risk binary market and cancelled clean
  (`order_id 0x1caa76f1…086f9`). The `/auth/api-key` 400 is benign —
  L1 credentials already derived; HMAC auth on the order path
  succeeded.

See ADR-050 for the decision rationale and full tx list.

**Progress 2026-04-29 (Session 45):**

V2 readiness re-verified after wallet migration:

- Official Polymarket docs still match repo constants: pUSD collateral,
  CTF Exchange V2 / NegRisk Exchange V2 addresses, unchanged CLOB auth
  headers, and per-order `builderCode`.
- Local and the bot LXC container preflight pass the post-cutover V2 address gate.
- the bot LXC container runtime has `py-clob-client-v2==1.0.0`, `web3==7.15.0`, keystore
  and passphrase paths present, `POLYMARKET_ENV=live`, and a non-zero
  `POLYMARKET_BUILDER_CODE` resolving through `ClobWrapperV2`.
- On-chain readback via Polygon mainnet: USDC.e `0.000000`, pUSD
  `454.034104`, MAX pUSD allowances for both V2 exchanges, and
  `ConditionalTokens.isApprovedForAll(...) == true` for both V2 exchanges.
- All 14 expected `polymarket-*` services are running.
- Critical bot/script imports are routed through `core.clob_v2`; remaining
  V1 SDK imports are confined to `core/clob.py` and `scripts/preflight_check.py`.
- Recent logs show successful CLOB `/book` reads and paper orders through
  `core.clob_v2`; watchdog pages are Bot B scorer liveness, not CLOB/V2.
- `core.config.Settings.polygon_rpc_url` default changed from
  `https://polygon-rpc.com` to `https://polygon-bor.publicnode.com` after
  the former returned HTTP 401 on the bot LXC container. Deployed and verified against
  Polygon chain ID 137.

Still open before non-smoke live trading:

- Operator approval before any non-smoke live order.
- Bankroll/posture allocation for the specific bot being graduated.
- Keep V1 ``py-clob-client`` for at least 24h of clean V2 runtime, then
  remove it and archive ``core/clob.py``.

### OQ-013 — Postgres migration from SQLite
Per ADR-013, SQLite is adequate for v1. Migration deferred until volume justifies.
**Trigger:** >1,000 writes/day sustained, or multi-process write contention.

### OQ-014 — Hardware wallet signing path
Per ADR-005 + ADR-009, not in v1 because py-clob-client doesn't support it. Building a signing relayer is 2–3 weeks of infra work.
**Trigger:** Bot scales beyond $5k live exposure (hot wallet cap raises risk of a key compromise becoming materially painful).

### OQ-031 — `price_collector.py` one-price-per-market schema flaw (Claude)

**Category:** data integrity / prerequisite for any Bot C price modeling
**Owner:** Claude (propose), the operator (approve)
**Why it's open:** Bot C's `price_collector.py` persists only one price point per market per ingest cycle rather than the full sub-second tick stream. Any downstream work that needs price **history** — GBM model refresh, Markov transition matrix estimation (Entry 008), volatility calibration, regime detection — is blocked because the history simply isn't there. The schema silently drops data.
**Revisit when:** the Pyth Pro vs free-pyth decision (OQ-017) is resolved at 2026-04-22. Bot C's modeling approach will be re-evaluated; the schema fix is a prerequisite to any of those paths.
**Acceptance criteria:** `price_collector` stores every tick with source, symbol, price, local_ts_ms, source_ts_ms — or at minimum every distinct price in a rolling per-market buffer. `prices` table (or equivalent) queryable as a time series. Volume budget stays within current Bot C disk allocation.
**Blocks:** OQ-024 (Bot C strategy direction), Entry 008's D24 (Markov alternative to GBM).

---

### OQ-033 — Bot F Hunter N-threshold not binding on top-N rankings (Claude)

**Category:** Bot F ranking correctness
**Owner:** Claude
**Why it's open:** Hunter rankings latest run top-5 all show `trades=4–8` — well below the documented ≥100 trade minimum in Entry 004 / Bot F idea 001. The filter applies correctly when excluding unknown wallets (e.g. `0xeebde7a0…` from Entry 008 was correctly rejected), but top-rank selection surfaces small-N luck accounts with WR=1.000. Need to walk `bots/bot_f/discovery.py` to find whether the N-threshold is a post-rank filter (wrong) vs a pre-rank filter (right) and whether it's being bypassed for top-rank surfacing.
**Revisit when:** any Bot F consumer (dashboard widget, Mirror eligibility, future Trigger) starts to use Hunter ranks for actual trade decisions. Until then, the ranking is measurement-only and the bug is latent.
**Acceptance criteria:** top-10 hunter_rankings rows all have `trade_count ≥ 100`; filter sequence documented in code; unit test covering "9-trade luck account does not appear in top-40".

---

### OQ-030 — Reconcile Bot A's missing BUY legs from Polymarket CTF split-sells (Claude)

**Category:** accounting / audit trail
**Owner:** Claude (propose), the operator (approve before re-running)
**Why it's open:** Patch A (commit `6811edd`, 2026-04-16) correctly stopped counting orphan SELLs as realised profit. Consequence: Bot A's post-patch realised P&L reports $0 even though the bot actually earned some spread via the CTF split-sell mechanic (buy NO at $0.989 + auto-sell YES at $0.97 = net cost ~$0.019 per share for the NO; today Bot A has ~10 such entries). The missing legs should be recoverable via `Portfolio.reconcile_live_fills(clob, "bot_a")` which fetches the CLOB's user-trades API with a cursor. Running this unreviewed risks re-inflating apparent realised if the new inserts don't match correctly with existing Trade rows (duplicates or mis-paired SELLs). Want a focused session with test coverage.
**Revisit when:** operator bandwidth allows a careful run-through; no hurry — current accounting is conservative-correct, bot keeps running.
**Acceptance criteria:** after reconcile, (a) every orphan SELL has a matching BUY in Trade table, (b) realised P&L matches the dashboard's on-chain-derived USDC.e delta minus open cost basis, (c) no duplicate Trade rows created, (d) unit test covers the split-sell pairing logic.

---

### OQ-028 — Widen main ingest to capture weather markets (Claude)

**Category:** data integrity / analytics
**Owner:** Claude (propose), the operator (approve)
**Why it's open:** ADR-021 chose a Bot D dual-write as the tactical fix because the main ingest pipeline does not currently capture the Gamma pages containing weather markets. Production DB inspection 2026-04-16 confirmed 0 of 10,055 `markets` rows mention temperature / °F / °C, while Bot D's 15 orders reference 15 condition_ids none of which exist in the table. The dual-write solves it for Bot D, but the underlying ingest gap remains — any future weather-adjacent bot, or Bot D retrospective queries against trades that predate ADR-021, will hit the same wall.
**Revisit when:** Bot A backfill work stabilizes (currently mid-flight — `scripts/backfill_history.py` proposed but not merged). Not before — ingest service is live and feeds Bot A, so widening it without the backfill settled risks colliding concerns.
**Acceptance criteria:** ingest stores at least one `markets` row per weather market Bot D would trade, within the usual Gamma scrape cadence. When done, the Bot D dual-write in `upsert_market_minimal` becomes redundant (but can stay — it's idempotent and costs nothing).

---

### OQ-029 — Reconcile condition_id ID-space mismatch between bots (Claude)

**Category:** data integrity / cross-bot analytics
**Owner:** Claude
**Why it's open:** Bot D stores Gamma's numeric `id`/`conditionId` (e.g. `1986334…`) in `orders.condition_id`, while Bot A stores the Polymarket hex `condition_id` (`0xabc…`). Both end up in the same column. Cross-bot joins on `markets.condition_id` currently work per-bot but not across bots. ADR-021's dual-write preserves the inconsistency (Bot D still writes its numeric gamma_id as the primary key).
**Revisit when:** either OQ-028 is resolved (ingest supplies the hex condition_id alongside the Gamma numeric id, then Bot D can migrate to hex), OR a cross-bot analytic actually needs the join.
**Mitigation today:** dashboard query layer should document the split so readers don't assume a single namespace.

---

### OQ-015 — v2 strategies (TimesFM crypto, copy-trading, etc.)
Deferred per ADR-012 until v1 has a clear winner or loser.
**Trigger:** Week-16 decision point.

---


## Resolved (historical — kept for audit)

_Resolved entries are kept verbatim for audit. Newest first by the resolution date in the title; legacy `OQ-R*` Phase 2 items at the bottom._

### OQ-048 — Bot E calibration memory-bound and rejection telemetry (Claude)

**Category:** Research-required / calibration integrity.
**Owner:** Claude.
**Surfaced by:** Session 27 host-unwedge and
`docs/audit/remaining-bots-profitability-audit-2026-04-24.md`.
**Status:** Closed by ADR-092 on 2026-05-03.

**Problem:** `scripts/bot_e_calibration_spike.py` still scales memory with
recorder DB age because large recorder queries load unbounded CEX and
Polymarket event windows. Session 27 added a flock guard so duplicate
timers no longer collide, but the underlying calibration run can still
pressure LXC memory as `bot_e_recorder.db` grows. The profitability audit
also found Bot E placed/cancelled 20 paper orders in the last 24h with 0
fills, but rejection reasons are mostly log-only rather than daily
DB-countable. Session 51 revalidated current production state and found the
older 69-fill/20-cancel framing stale: `main.db` now shows 308 FILLED Bot E
orders, while today's journal still shows thousands of log-only
`cex_cvd_skip`, `depth_skip`, `halt_active`, `signal`, and `ttl_cancel`
events. Treat pre-dated audit numbers as historical priors only.

**Acceptance criteria:**
- Add `BOT_E_CALIBRATION_LOOKBACK_HOURS` or equivalent bounded window to
  calibration loaders. **Progress 2026-04-30:** implemented in
  `scripts/bot_e_calibration_spike.py` for PM replay, CEX prices,
  maker-fill simulation, adverse-selection measurement, and BTC regime data.
- Deduplicate repeated `last_trade_price` scans across maker-fill and
  adverse-selection measurement.
- Add DB-visible rejection counters/events for `signal_none`,
  `cex_cvd_skip`, `depth_skip`, `try_enter` rejection, `order_placed`,
  `paper_filled`, and `ttl_cancel`. **Progress 2026-04-30:** implemented
  scan-level `bot_e.scan_summary` counters plus per-signal Events for
  signal, CEX/depth skips, entry rejections, TTL cancels, fleet-cap breaches,
  and order failures; deployed to the bot LXC container paper trader and verified writing
  to `main.db`.
- Regression test against a small fixed recorder fixture so bounded
  loading does not change math unexpectedly. **Progress 2026-04-30:** added
  bounded maker-fill simulation coverage and telemetry cursor coverage.
- After the bounded calibration path exists, derive lightweight CEX
  OHLCV/regime features directly from recorder `cex_trades` and test them
  inside the existing E-2 held-out model pipeline. Kronos is rejected for
  Bot E per ADR-057.
- Before any Bot E threshold, model, or execution change, attach the
  ADR-058 validation packet: current production DB/journal window,
  recorder-health freshness, current public Polymarket docs/status/news
  context, expected metric movement, and rollback criteria. **Progress
  2026-04-30:** added `scripts/bot_e_cancel_autopsy.py`; paper-only
  execution defaults changed to `BOT_E_MAKER_OFFSET=0.000` and
  `BOT_E_ORDER_TTL_SEC=600` while live defaults remain `0.001` and `300s`.
  Production autopsy found `book 0/69` coverage for recent Bot E paper orders,
  so Bot E now persists fetched YES/NO CLOB books into `main.db.books` for
  honest `simulate_paper_fills("bot_e")` behavior.

**Blocks:** Bot E threshold tuning, Kelly graduation, and any live-mode
argument for the OBI scalper.

**Progress 2026-05-01 Phase 0/1:** `scripts/bot_e_cancel_autopsy.py` now
reports `$25` and `$50` book-depth coverage per TTL/offset scenario. the bot LXC container
read saw `20` recent Bot E orders; the first scenarios filled `14/20`, with
`$25` coverage `12/14` and `$50` coverage `9/14`. This improves capacity
visibility only; Bot E remains gated by adverse-selection/fill-quality proof.

**Progress 2026-05-03 Phase 0 replay plan:** Created
`docs/bot-e-fill-conditioned-replay-plan-2026-05-03.md` after read-only
discovery and sanitized external-model brainstorming. The next Bot E action is
not threshold tuning; it is a fill-conditioned replay dataset/report that
carries the full denominator: signals, skips, rejections, placements, cancels,
no-fills, fills, fill delay, adverse movement, and outcomes. Phase 1 should
use copied DB snapshots or strict bounded query windows because read-only
production SQLite inventory over SSH can hang on the large recorder/main DBs.
No Bot E runtime settings, thresholds, sizing, services, or live-money posture
changed.

**Progress 2026-05-03 Phase 1 replay dataset:** Added
`scripts/bot_e_fill_conditioned_replay.py` and
`tests/test_bot_e_fill_conditioned_replay.py`. The CLI is bounded and
read-only, emits replay-signal rows plus optional actual `main_order`
denominator rows, includes fill delay, depth, adverse 30/60/300s, and bounded
outcome labels, and writes only requested CSV/JSON artifacts. Review fixes
landed for bounded market metadata, OBI warmup, bounded depth lookup,
schema-tolerant optional `main.db` reads, and Bot E `BUY_YES`/`BUY_NO` paper
fill matching. Verification passed on focused replay tests, the wider Bot E
test slice, Ruff, CLI help, and `git diff --check`. No Bot E runtime settings,
thresholds, sizing, services, or live-money posture changed.

**Progress 2026-05-03 Phase 2 fill replay:** Ran the replay on copied 24h the bot LXC container slices and wrote `docs/reports/bot-e-phase2-fill-replay-2026-05-03.md`.
The run produced `270` denominator rows: `241` optimistic `replay_signal` rows
and `29` actual `main_order` rows. Actual Bot E paper orders filled `15/29`
(`51.7%`) but 30s adverse movement was `9/14` (`64.3%`), above the existing
60% toxicity stop line. Optimistic replay signals filled `137/241` (`56.8%`)
with 30s adverse `52/120` (`43.3%`), showing the last-trade ceiling understates
actual-order toxicity. Phase 3 should compute EV and missed-winner/missed-loser
accounting before any threshold or execution proposal. No Bot E runtime
settings, thresholds, sizing, services, or live-money posture changed.

**Progress 2026-05-03 Phase 3 EV packet:** Added
`docs/reports/bot-e-phase3-ev-2026-05-03.md`. Outcome coverage remains
partial: `16/29` actual paper orders and `8/15` actual fills were labelled;
all four actual `BUY_NO` fills remain unlabelled in this artifact. Actual
labelled fills produced `-0.55` P&L/share on `5.55` cost basis (`-9.9%` ROI)
despite `62.5%` WR. Optimistic replay fills produced only `+0.57` P&L/share
on `59.43` cost basis (`+1.0%` ROI) before costs, and a flat `1c`/share
execution haircut turns replay negative. Actual unfilled labelled orders
missed `7` winners and avoided `1` loser; actual 30s-adverse labelled fills
were `0%` WR and `-100%` ROI. This packet does not support Bot E threshold,
offset, TTL, sizing, runtime, or live-posture changes. Next useful research is
a bounded copied 72h or 7d Phase 2/3 packet; if larger actual-order EV remains
negative, retire active Bot E tuning and keep recorder/data reuse.

**Progress 2026-05-03 Phase 3 72h EV packet:** Added
`docs/reports/bot-e-phase3-72h-ev-2026-05-03.md`. The 72h copied snapshot
covered `2026-04-30T13:32:55.076Z` to `2026-05-03T13:32:55.076Z` and produced
`807` denominator rows: `737` optimistic replay signals and `70` actual Bot E
paper orders. Outcome coverage was `721/807` rows and `377/419` filled rows.
Actual labelled fills produced `-2.189` P&L/share on `17.189` cost basis
(`-12.7%` ROI) before costs. Optimistic replay fills produced only `+2.082`
P&L/share on `174.918` cost basis (`+1.2%` ROI), and a flat `1c`/share
execution haircut turns it negative. Actual unfilled labelled orders missed
`19` winners and avoided only `3` losers. The 24h packet's `75c+` actual-order
bucket collapsed to `+1.0%` ROI before costs and negative after `1c`/share.
This larger packet confirms Bot E does not currently have a tradable edge. No
Bot E runtime settings, thresholds, sizing, services, or live-money posture
changed. Next decision packet: ADR to retire active Bot E tuning and keep
recorder/data reuse, unless the operator wants one final 7d packet for closure.

**Resolution 2026-05-03:** Added
`docs/reports/bot-e-external-consensus-2026-05-03.md` and ADR-092. External
reviewers were given only sanitized aggregate strategy metrics and agreed with
the local verdict: retire Bot E as an active trading strategy, keep recorder
data, bounded replay, outcome labels, and offline feature extraction as shared
infrastructure. Bot E no longer blocks threshold tuning or live graduation
because those paths are closed; any future trading reconsideration requires a
new ADR with fresh actual-order EV evidence after realistic costs.

---

### OQ-055 — Recurring `recorder.writer_stall_abort` failures (Claude)

**Category:** Reliability — recurring incident, root cause partially
addressed.
**Owner:** Claude.
**Surfaced by:** Session 39 watchdog page during cleanup work.
**Status:** Mitigation deployed 2026-04-26 06:27 UTC; root cause for
the *first* stall in a clean run still undiagnosed.

**2026-04-26 06:27 UTC — Mitigation deployed (WAL inheritance).**
Added `PRAGMA wal_checkpoint(TRUNCATE)` to
`bots/bot_e_recorder/schema.py:init_db` so each process start begins
with an empty WAL instead of inheriting the prior crashed run's
pages. This addresses the *decreasing-inter-stall-interval* pattern
(110 min → 6.5 min → 2 min across three restarts overnight) which is
the symptom of WAL inheritance compounding checkpoint pressure
across restarts. Verified: live WAL dropped from 4.2 MB (pre-restart)
to 362 KB (post-restart).

**2026-04-26 06:33 UTC — Root cause for *first* stall identified.**
The recorder stalled again 5:59 min after the WAL fix went live.
This was the cleanest reproduction yet — empty WAL, fresh process —
and the py-spy stack dump showed *every threadpool worker idle*. No
thread was inside `_flush_batch` or any SQLite call. The writer was
literally not doing anything. The "stall" was a false positive: the
guard logic was using `state.last_flush_ts` ("time of last successful
flush") as a proxy for "writer is alive", but flushes only happen
when there's data in `write_queue`. During a quiet market window
(no PM events + brief CEX gap > 90 s), the queue stays empty for
longer than the threshold and the guard fires unnecessarily.

**2026-04-26 06:38 UTC — Mitigation deployed (writer-alive tick).**
Added `state.last_flush_ts = time.time()` at the top of every
`writer_loop` iteration in
`bots/bot_e_recorder/capture.py`. The timestamp now means
"writer-loop is alive", not "writer-loop just flushed". A genuine
SQLite or threadpool wedge still blocks the loop body for >90 s and
fires the abort correctly because the tick only happens at the top
of each iteration. Two regression tests under
`tests/bot_e_recorder/test_capture_writer.py::TestWriterAliveTick`:
tick fires when queue is empty, and ticks advance across multiple
loop iterations.

**Status:** This pair of fixes addresses both observed symptoms (the
inheritance cascade + the quiet-market false positive). What remains
truly open is whether there's a legitimate writer wedge case that
the abort guard should still catch — i.e., a real SQLite hang or
threadpool deadlock on this hardware/ZFS combination. We have no
direct evidence of one yet; the hypotheses listed below should be
revisited only after the alive-tick fix has had a clean uptime
sample (target: 24 h without abort).

**Problem:** `polymarket-bot-e-recorder.service` has now SIGABRT-ed on
the same `recorder.writer_stall_abort` path at least three times:

- Session 22b (the original incident — see memory observation 3995).
- Session 37 (2026-04-25 morning, recovered as part of disk-full
  remediation).
- 2026-04-25 21:15:42 UTC — flush age 119s vs 90s threshold; SIGABRT;
  19 rapid restarts; systemd start-rate-limit tripped → `failed`.
  Watchdog correctly paged at 21:57 once heartbeat staleness crossed
  120s. Recovery: `systemctl reset-failed && systemctl restart`.

In each case the recovery is a clean restart and recorder runs fine
for hours-to-days afterwards. Nothing is corrupted; the writer just
wedges intermittently and the abort handler doesn't unwedge it.

**Hypotheses (in rough order of fit):**

1. SQLite checkpoint stall on the new ZFS-backed
   `data/recorder/bot_e_recorder.db` (Session 38 migration). lz4
   compression + WAL checkpoint + 13G DB might pause writes long
   enough to cross the 90s flush threshold under burst load. Test:
   plot writer-flush-age over time, see if stalls cluster around
   checkpoint events.
2. py-spy subprocess used in the abort handler itself wedges on
   `subprocess.communicate()` (visible in the most recent stack
   dump — `asyncio_1` was inside `_communicate` at the moment of
   abort). The abort handler may be amplifying rather than just
   recording the wedge.
3. CEX websocket burst exhausts the writer queue. CEX recently
   measured at 2,372 trades/min; if the writer flush coalesces
   poorly, queue depth could explode in a few seconds.

**Acceptance criteria:**
- Pick one of the three hypotheses based on evidence (writer-stall
  log, ZFS arc/checkpoint metrics, queue-depth telemetry) and
  prove or rule it out.
- Either raise the 90s flush threshold (cheap mitigation, masks
  the problem) or fix the underlying stall cause.
- Document the chosen direction as an ADR.
- Add a regression check: writer-flush-age histogram, alert if 99th
  percentile > 60s for >5 minutes.

**Blocks:** nothing immediately (recovery is one shell command,
documented in the watchdog's own alert text), but each incident
loses ~45 minutes of recorder data and pages the operator.

---

### OQ-084 — NegRisk basket arb scanner on non-crypto multi-outcome markets (Claude) — RESOLVED 2026-05-07

**Resolution (Session 197, 2026-05-07):** CLOSED. v1 naive scanner
flagged `7` opportunities; v2 gated scanner finds `0` real arbs across
`1,425` qualifying multi-outcome events. `252` events show illusory
naive-arb (illiquid field markets), `6` are cumulative-threshold
non-baskets, `1` near-arb at `-4%` (MLS 3-way W/L/D with no edge after
fees). The IMDEA `$29M` figure is gated by infra (`<1s` poll cadence,
WebSocket CLOB streaming, `neg-risk-ctf-adapter` atomic basket
execution) and capital (field-market liquidity provision is market
making, not arb). Per ADR-119, NegRisk basket arb track CLOSED at
$200 solo scale. See `docs/reports/polymarket-negrisk-closure-
2026-05-07.md`.

**Category:** Research-required / new strategy direction.
**Owner:** Claude.
**Surfaced by:** 2026-05-07 Session 196 closure of crypto 5m/15m corner.

**Problem:** Crypto 5m/15m Up/Down markets have been definitively
exhausted across 10 strategy variants. The next direction with
documented edge is **NegRisk basket arbitrage on multi-outcome
markets**. Per arXiv 2508.03474 (IMDEA, AFT 2025), `$29M` of `$39.6M`
total Polymarket arb extracted Apr 2024-Apr 2025 came from NegRisk
basket rebalancing — 73% of all arb, at 29× capital efficiency vs
binary arb. Median mispricing was sum-to-`$0.60`. Top arber averaged
`$496/trade × 4,049 trades`, well within $200 wallet scale. Categories
include US elections (N-way brackets), sports brackets (NFL playoffs,
World Cup, March Madness), weather brackets (Bot D's domain), and
geopolitical scenarios.

**Acceptance criteria:** Build a read-only scanner-only report, starting
with `scripts/polymarket_negrisk_scanner.py`, with no systemd unit or
runtime package. The scanner must:

1. Use the gamma client (or direct gamma API) to enumerate active
   multi-outcome events.
2. Filter to events with `negRisk: true` (or equivalent
   neg-risk-eligible flag).
3. For each negRisk event, fetch top-of-book best_ask for the YES
   outcome of every constituent market.
4. Compute `sum(best_ask)` across the basket.
5. Apply per-side fees from Polymarket fee schedule.
6. Flag opportunities where `sum + fees < $1.00`.
7. Report opportunity frequency, magnitude (sum-to-X), per-leg sizes,
   and category breakdown.
8. Run as a one-shot snapshot (not a continuous service) for initial
   validation. If signal is confirmed, second-pass adds historical
   sampling from gamma `volume24hr` and `volumeNum` fields to estimate
   per-day frequency.

The scanner must respect:
- No bot/service/paper/live/cap/wallet/order-path change.
- Read-only against gamma API; no order placement.
- Polymarket V2 conventions (post-Apr 28 2026): use neg-risk-ctf-adapter
  contract awareness for atomic execution feasibility (basket fills
  must use the adapter to avoid leg risk).
- Output: Markdown + JSON report under `docs/reports/`.

**Blocks:** Any neg-risk runtime, paper service, dashboard surface,
paper parameter, live parameter, cap, wallet, or order-path change for
the basket-arb lane.

**Status:** Open.

### OQ-082 — the bot container watchdog blocked by failed the VPN provider egress probe (Claude) [RESOLVED 2026-05-06]

**Category:** Blocking / live safety system.
**Owner:** Claude.
**Surfaced by:** 2026-05-06 Bot G live VPS migration audit.

**Problem:** The Bot G VPS audit found `polymarket-watchdog.service` inactive
on the bot container. The service failed at 2026-05-06 18:34:23 UTC because its hard
dependency `polymarket-wg-vpn.service` failed after the egress probe saw
`198.51.100.3`/fail instead of the expected the VPN provider path. Bot G live is now
VPS-hosted, but the bot container still hosts live Bot D and the watchdog remains a live
safety system.

**Unlock condition:** Restore the the bot container Polymarket egress/VPN health path or
deliberately revise the watchdog dependency model, then verify
`polymarket-watchdog.service` is active with a fresh `ActiveEnterTimestamp`
after the fix. Record the remediation in `CHANGELOG.md` and update this OQ
with the exact service state, egress IP, and any ADR impact.

**Resolution 2026-05-06:** Accepted ADR-116 and deliberately revised the
watchdog dependency model. `polymarket-watchdog.service` no longer hard
requires `polymarket-wg-vpn.service`; it starts after
`network-online.target` and keeps the in-process CLOB reachability check
scoped to the bot container-hosted bots. Deployed the unit plus the
`core.watchdog`/`bots.watchdog_daemon` VPS-host filtering to the bot container. Verified
`polymarket-watchdog.service` active/running with `NRestarts=0`,
`MainPID=1229`, and
`ActiveEnterTimestamp=Wed 2026-05-06 19:07:34 UTC`. the bot container direct egress was
`198.51.100.3`; VPS Bot G direct egress remained `198.51.100.1` with no
the VPN provider requirement. the bot container Bot G halt rows stayed `halted=0` with unchanged
`set_at=2026-05-06 18:10:12.103427`.

---

### OQ-083 — Maker-side Phase B2 simulator validation gate (Claude) [RESOLVED 2026-05-06]

**Category:** Research-required / maker-side crypto research.
**Owner:** Claude.
**Surfaced by:** 2026-05-06 Codex review of
`docs/maker-bot-validation-handoff-codex-2026-05-06.md`.

**Problem:** Becker and recorder evidence now support a maker-side
BTC/ETH/SOL 15m research lane more than any taker variant, but the proposed
Phase B2 design is not ready to become a bot or service. The main unresolved
risk is fillability: historical trades at a price do not prove that this
wallet's maker SELL quote would have been first enough in queue to fill before
adverse selection or cancellation. Phase A also needs corrected band labelling
in two helper tables before those tables are reused for targeting, and Phase
B1 needs more robust resolution labelling.

**Acceptance criteria:** Build an offline simulator/report only, starting with
`scripts/maker_simulator_paper.py`, with no systemd unit or runtime package.
The report must target UP-side `5.5-15c`, lead `300-600s` first, with DOWN as
a control; model join-best-ask, improve-best-ask-by-one-tick, and
worse-than-best-ask-by-one-tick quote ladders; use official current maker fee
`0` and maker rebate `0` as the base case; resolve outcomes via
`market_resolved.winning_asset_id` where available with price-threshold
sensitivity fallback; quarantine reconnect/gap/stale-book/tick-size-change
windows; estimate lower-bound queue-ahead fills from observed trade prints
rather than book depletion alone; report lower-bound and upper-bound fill
rates; report ROI per collateral dollar-minute and per quote attempt; stress
cancel latency at `200ms`, `500ms`, and `1000ms`; and include
adverse-selection diagnostics comparing filled vs unfilled quote outcomes.

**Blocks:** Any `bots/maker_paper/` package, paper-only service, dashboard
surface, paper parameter, live parameter, cap, wallet, or order-path change
for the maker-side lane.

**Result (2026-05-06):** Built `scripts/maker_simulator_paper.py` and ran it
read-only on the bot container/the bot LXC container against
`/home/bot/polymarket-bot/data/recorder/bot_e_recorder.db`. Report:
`docs/reports/maker-simulator-paper-2026-05-06-the bot container.md` with JSON sidecar
`docs/reports/maker-simulator-paper-2026-05-06-the bot container.json`. Verdict:
`FAIL`. The run covered 905 candidate markets, 103 markets with posted
quotes, and 170 unique quote attempts. Failed criteria: UP lower-bound fills
at 500ms were `41 < 150`; quarantine fraction was `23.39% > 5%`; minimum
fills for a positive pass-labelled cell were `1 < 50`; and DOWN control ROI
exceeded UP (`1.18%` vs `1.03%`). Positive aggregate UP ROI alone is not
decision-grade because the fill count, quarantine, and control-side gates
failed.

**Amendment 1 result (2026-05-06):** Applied
`docs/maker-simulator-build-amendment-1-2026-05-06.md` and re-ran the
simulator read-only on the bot container/the bot LXC container. Report:
`docs/reports/maker-simulator-paper-2026-05-06-the bot container-amendment1.md`.
Verdict: `FAIL`. The amended run covered 907 candidate markets, excluded
260 weekend markets, left 647 weekday candidates, posted quotes in 54
markets, and produced 114 unique quote attempts across four cancel-latency
regimes (`200/300/500/1000ms`). Failed criteria: UP lower-bound fills at
300ms were `16 < 150`; quarantine fraction was `47.64% > 5%`; minimum fills
for a positive pass-labelled cell were `1 < 50`; and top-10 taker wallet
concentration could not be evaluated because the recorder has no
`fill_events`/taker-wallet table. The amendment's manipulation-defense
question is `NO`: the lane does not earn decision-grade positive ROI
excluding toxic-marked fills under 300ms cancel latency on weekday markets
only.

**Status:** Resolved 2026-05-06 as failed after the base run and Amendment 1
rerun. No maker-side runtime package, paper-only service, dashboard surface,
paper parameter, live parameter, cap, wallet, or order-path change is
authorized from this result. Reopening the maker-side lane requires new
evidence and a follow-up decision record.

### OQ-081 — Project-wide Becker/Binance audit before bot adjustments (Claude + the operator) [RESOLVED 2026-05-06]

**Category:** Research-required / project audit.
**Owner:** Claude audits and reports; the operator decides any bot adjustment scope.
**Surfaced by:** 2026-05-06 the local workstation Becker robustness analysis.

**Problem:** The Becker public Polymarket dataset plus Binance klines have
now produced useful crypto fair-value evidence, including a negative overall
verdict, two Brownian BTC 15m survivor pockets, and a 5m token-coverage gap.
the operator noted that a full project audit is required to determine whether this
data can aid further analysis before any paper or live bot adjustments occur.

**Acceptance criteria:** Audit all active, parked, and shared-data strategy
surfaces against the local Becker/Binance data to identify where the dataset
can and cannot provide decision-grade evidence. At minimum, review Longshot
Prime/Bot G, crypto fair-value paper lanes, Crypto Recorder/Bot E shared
data, Pyth/Hermes/Bot C research surfaces, Bot D weather, parked Bot B, and
archived Bot A/F surfaces. For each surface, classify the data as
`decision-grade`, `supporting-only`, `not applicable`, or `unsafe/misleading`;
name the exact report or join required; name any data gaps; and explicitly
state whether paper-only adjustments, live adjustments, or no adjustments are
allowed. No paper or live bot parameter/cap/order-path change may be made from
this audit without a follow-up ADR where required and the operator approval for any
live-money effect.

**Blocks:** Any paper/live bot adjustment justified by the Becker/Binance
offline data outside the already documented crypto fair-value forward-paper
watchlist.

**Resolution 2026-05-06:** Added
`docs/reports/project-wide-becker-binance-audit-2026-05-06.md`. The audit
classifies Becker/Binance as decision-grade only for 15m crypto fair-value
paper-triage. It supports a narrow paper-only Brownian BTC 15m watchlist for
forward report review: BTC DOWN `300s-600s` `5c-10c` and BTC UP `45s-120s`
`3c-5c`. It is supporting-only for Bot G, Crypto Recorder/Bot E shared data,
and Bot C/Pyth research; not applicable to Bot D weather, Bot B, and Bot F;
and unsafe/misleading for Bot A-style long-horizon tail fading. No paper or
live parameter, cap, wallet, order-path, symbol, or running-service change is
authorized by this audit. The operative next gate remains OQ-078 forward
paper with settlement/Chainlink labels, fill/no-fill calibration, exact fee
modelling, and latency stress.

**Follow-up 2026-05-06 Bot G edge test:** Used the audit's "supporting-only"
allowance to test Bot G Prime's design premises against Becker. Added
`scripts/bot_g_becker_edge_report.py` and
`docs/reports/bot-g-becker-edge-2026-05-06.md`/`.json`. Coverage: `73,900`
resolved BTC/ETH/SOL 15m Up/Down tokens, `4,831,522` fills in Bot G's lead
`5-60s` window, all matched to Binance 1m closes. Result: the unconditional
pool in Bot G's price-band + lead-window is a loser after costs (live band
`3.5-5.5c` averages `+12.75%` gross, `-8.02%` at `1c`, `-22.29%` at `2c`;
paper band `4-8c` averages `+9.52%` gross, `-21.37%` at `2c`), which
confirms the design premise that an unfiltered cheap-tail buy is not edge.
Becker's CEX-direction overlay shows a large historical lift: live `agree`
fills (`42,465`) win `16.35%` and average `+266.83%` gross / `+152.54%` at
`2c`; live `disagree` fills (`59,984`) win `0.51%` and average `-92.42%` at
`2c`; live `flat` fills (`61,152`) win `1.65%` and average `-74.90%` at
`2c`. Every symbol × side × `agree` cell is positive at `2c/share` stress,
strongest on BTC DOWN (`+214.77%` live, `+224.18%` paper) and weakest on
ETH UP (`+78.90%` live, `+98.46%` paper). Caveats: Becker fill window ends
`2026-01-25`, Binance 1m is coarser than Bot G's tick feed, Becker carries
fillability survivorship bias, and per-share cost stress at `1c`/`2c` is
uniform. No Bot G band/lead/symbol/cap/sizing/fresh-clock/order-path change
is authorized from this evidence alone. The next gate is to replay Bot G's
own `data/main.db` paper/live fills with the same CEX-tag overlay; if the
forward agree/disagree split mirrors Becker, an ADR may propose flipping
`BOT_G_PRIME_REQUIRE_CEX_CONFIRM` from `false` to `true` on the paper
shadow only.

**Follow-up 2026-05-06 Bot G own-data CEX replay:** Completed the forward
replay gate with `scripts/bot_g_cex_gate_replay_report.py` and preserved the bot container
and VPS reports in `docs/reports/bot-g-cex-gate-replay-2026-05-06-the bot container.*`
and `docs/reports/bot-g-cex-gate-replay-2026-05-06-vps.*`. Result does not
mirror Becker. the bot container: `207` resolved rows with known CEX state, `agree`
`0/36` with `-100.0%` ROI, `disagree` `3/77` with `-26.6%` ROI, and `flat`
`9/94` with `+92.3%` ROI. VPS paper ledger: `164` resolved rows, `agree`
`0/31` with `-100.0%` ROI, `disagree` `3/57` with `-11.1%` ROI, and `flat`
`8/76` with `+109.2%` ROI. Therefore the CEX gate remains supporting-only
historical evidence, not an approved Bot G operating change. Do not enable
`BOT_G_PRIME_REQUIRE_CEX_CONFIRM` on the paper shadow or live unit from the
current data.

**Follow-up 2026-05-06 Track 1 multi-model brainstorm:** Ran a
hypothesis-generation pass against the Becker + Bot-G-replay evidence with
GLM-5.1 and DeepSeek R1 (DeepSeek V4 Pro/Flash, Gemini 3.1 Pro, Kimi K2
Thinking, and Groq Kimi K2 attempted but failed with timeouts/errors).
Synthesis report:
`docs/reports/track1-multi-model-hypothesis-brainstorm-2026-05-06.md`.
The brainstorm produced `16` deduplicated hypotheses ranked by expected
lift and false-positive risk. Convergent strictly-causal Tier A: (1)
counterparty/wallet archetype clustering on Becker, (2) pre-fill CEX
micro-trajectory at sub-second resolution on Bot G ticks, (3) multi-wallet
cascade detection per condition_id window, (4) time-of-day session gate.
Contradictory Tier C: volatility-regime conditioning (GLM proposes low 1h
realized vol, R1 proposes high IV; one direction is wrong). Three Tier D
hypotheses use post-fill data and are flagged research-only — they cannot
become entry gates without re-introducing the look-ahead bias that
flipped the original Becker conclusion. No Bot G config, paper, live, or
service change was authorized; this report only ranks future tests.
Recommended next test: Tier A item #1, counterparty/wallet archetype
clustering on Becker, the largest analytical gap in prior work.

**Follow-up 2026-05-06 Script 1 Becker hypothesis validation:** Ran the
ranked hypotheses on the full Becker dataset with strict walk-forward
split (cutoff `2025-12-01`). Added
`scripts/becker_hypothesis_validation_report.py` and
`docs/reports/becker-hypothesis-validation-2026-05-06.md`/`.json`.
Coverage: `73,900` resolved 15m tokens, `66,079,487` fills in lead
`5-600s`, `89,519` unique wallets. Result: **none of the 8 tested
hypotheses produces positive ROI on the test split at `2c/share`
stress.** Counterparty maker archetype ranges from `-6.17%` (taker_heavy
maker) to `-20.98%` (light maker) ROI 2c overall. Cascade-detection
buckets cluster around `-9%` to `-13%`. Time-of-day shows one positive
test cell (UTC hour 22, `+3.78%`) but train is `-12.71%` for the same
hour — noise. ETH/SOL × BTC-state cells all between `-8.92%` and
`-17.85%`. Lead-band `300-600s` is least-bad at `-7.82%`; Bot G's
`5-60s` window is the worst. Price-band `20c+` is least-bad at
`-3.78%`; Bot G's `3.5-5.5c` band is `-35.07%` test (cheap tails get
crushed by the `2c` per-share fee proxy because the fee is a huge
fraction of the entry price). Volatility-regime deciles cluster at
`-6.23%` to `-14.44%` — both the GLM low-vol and DeepSeek R1 high-vol
hypotheses are rejected. Tier D post-fill validator (research only)
shows `true_flat` is the WORST bucket at `-10.02%` test, opposite to
Bot G's strictly-causal `+92.3%` flat finding — confirming the
look-ahead bias was the issue and Bot G's flat signal is either a
sub-second microstructure phenomenon, a regime-specific signal, or
sample-size noise. Cannot be distinguished from this report alone.
Implication: single-feature edge from Becker historical analysis is
exhausted; the next step is Script 2 (recorder microstructure
validation on Bot G's own forward fills) which can see sub-second CEX
state. No Bot G/FV/Bot D/Bot B/recorder config, service, paper, live,
or order-path change is authorized from this report.

**Follow-up 2026-05-06 Script 2 recorder microstructure validation:** Ran
`scripts/recorder_microstructure_validation_report.py` on the bot container against
Bot G's actual `main.db` and `bot_e_recorder.db`. Coverage: `220` orders,
`210` resolved fills across the five Bot G prime variants, last `30`
days. Baseline: `5.71%` win rate, `+12.36%` ROI on `$723.54` cost basis
(positive but small). Multi-window pre-fill CEX-state buckets show NO
robust edge: pre-`5s` flat `+21.4%` ROI (Wilson `[3.59%, 11.03%]` win
rate), pre-`15s` flat `+42.5%`, pre-`30s` flat `+2.6%`, pre-`60s` flat
`+4.2%`. Wilson 95% CI overlaps baseline at every window — **no bucket
is statistically distinguishable from baseline.** The Session 171
"+92.3% flat" finding was a window-specific artifact + sample-size
noise; multi-window view does not replicate it. The strongest visible
pattern is `flat-at-5s × agree-at-60s` (`31` resolved fills, `9.68%`
win rate, `+182%` ROI) but Wilson CI `[3.35%, 24.90%]` includes
baseline. CV-quintile q1 (lowest pre-fill volatility) shows `+89%` ROI
on `39` fills, weakly supporting the GLM hypothesis but again not
statistically separable. Per-bot inconsistency is concerning:
`bot_g_prime` (paper main) flat is `+82.5%` ROI on `88` fills while
`bot_g_prime_live` flat is `-66.5%` on `36` fills — possible
paper-vs-live execution divergence. Per-symbol: SOL flat is the only
positive symbol cell (`14.71%` win, `+108%` ROI on `34` fills). Tier D
post-fill `agree` correctly wins (post-30s agree `14.89%` win) — that
is the look-ahead-confirmed consistency check, not actionable. **No
single-feature filter survives the multi-window, statistical-significance
gate.** Bot G's small positive baseline ROI is the current operating
state; no CEX-gate flip is justified, and no other parameter change is
authorized from this report. Next gate: investigate the
paper-vs-live performance divergence (separate research) before any
Bot G adjustment.

**Follow-up 2026-05-06 Session 175 paper-vs-live divergence diagnostic:**
Ran `scripts/bot_g_paper_vs_live_divergence_report.py` on the bot container against
`100` paper orders and `69` live orders (last `30` days). Verdict:
**execution illusion confirmed.** Paper has `100%` fill rate; live
`92.75%` (with only `17%` `FILLED` plus `39%` `matched`, `43%`
`EXCHANGE_CLOSED`-timed-out). Paper median slippage `0 bps` (fills at
limit); live median slippage `-2000 bps`, p25 `-4000 bps`, min
`-8181 bps` — MM only sells at the floor. Live `actual/limit` cost
ratio `0.5462` (live paid 55c per dollar of intended exposure). Paper
cost basis `$367` vs live `$117` for similar order counts; paper ROI
`+80.39%` on a fictitious cost basis. Live ROI `-73.15%` on `$117` of
real money, `1` win in `48` resolved positions. Same-market head-to-
head (`27` markets where both bots placed orders): both won `1`, paper-
only won `2` (both because live `EXCHANGE_CLOSED`-timed-out), live-only
won `0`, both lost `24`. **Bot G paper-main is not a meaningful research
signal.** All paper-derived "edge" findings (Sessions 171, 174,
Becker `agree` lift, etc.) are contaminated by the unrealistic
instant-fill-at-limit-price assumption. Real Bot G performance is the
live `-73%` ROI on `30` days. This triggers operator review of: (a)
whether to retire the `bot_g_prime` paper-main as a research signal or
fix its paper-fill simulator to model adverse selection, (b) whether
Bot G live continuation is justified given current loss rate, (c)
whether the same paper-illusion contaminates other paper bots' "edge"
evidence (FV paper bots, Bot D). No bot config, paper, live, cap,
wallet, fresh-clock, order-path, or service change is authorized from
this report — but it explicitly flags an operator-decision moment.

**Follow-up 2026-05-06 Session 177 maker-side ROI + wallet shrinkage:**
After the Codex+Grok external brainstorm proposed maker-side strategies
and tree-based models as the highest-leverage untested directions, I
ran Phase A: maker-side ROI with realistic fees (Becker `fee_usd`)
plus wallet performance persistence with shrinkage. Added
`scripts/becker_maker_and_wallet_analysis.py` and
`docs/reports/becker-maker-and-wallet-analysis-2026-05-06.md`/`.json`.
Coverage: `73,900` resolved 15m tokens, `66,079,487` fills. Findings:
(a) audit's `2c/share` fee proxy was `~22x` too punitive — real
Becker fees average `0.29%` of price overall, `0.90%` at `3.5-5.5c`;
(b) buyer ROI is still negative even at realistic fees (`-35.81%`
test for cheap tails), so the audit's "buyer of cheap tails is a
loser" conclusion stands; (c) **maker-side at zero fees has positive
E[ROI] across every cheap-and-mid price band on both train and test
splits** — magnitude `+0.3%` to `+2.2%` per share-equivalent;
(d) strongest cells: BTC/ETH/SOL UP at `8-15c` with `30s-600s` lead,
`+1.5%` to `+2.2%` test ROI; (e) DOWN-side is mostly flat (±0.3%) —
asymmetric over-pricing of UP tails; (f) wallet shrinkage with
`α=50` produces no meaningful quintile gradient — small-sample
wallets all shrink to global rate, flattening the distribution.
Implication: this is the first historical evidence of a positive-EV
pocket. Magnitude is too small to deploy live as-is (per-share `+1-2%`
becomes much smaller after realistic fillability/queue modeling), but
it justifies building a maker-only paper research lane as the next
step. Bot G's taker strategy is unchanged by this finding — it
remains a confirmed loser. No bot config, paper, live, cap, wallet,
fresh-clock, order-path, or service change is authorized from this
report; it is supporting-only research evidence per OQ-081. Any
maker-side research lane proposal would require a separate ADR after
forward paper validation.

**Follow-up 2026-05-06 Session 179 recorder maker-side validation
(Phase B1):** Validated Phase A's maker-side finding on current
(May 2026) recorder data before scoping a maker simulator. Added
`scripts/recorder_maker_side_validation.py` and
`docs/reports/recorder-maker-side-validation-2026-05-06-the bot container.md`/
`.json`. Coverage: `171` candidate BTC/ETH/SOL 15m markets in last
`42` days, `55` resolved (yes_price or no_price `>0.95` within
`±300s` of `end_date_iso`), `9,884` trade events in lead `5-600s`
window. Findings: (a) **direction validates Phase A** — maker-side
positive at cheap-mid bands, negative at high prices; (b)
collateral-based maker ROI `+1.95%` to `+10.49%` at cheap-mid
bands on the recorder, vs Phase A's `+0.3%` to `+2.2%` per share-
equivalent; the recorder's higher numbers reflect a small-sample +
selection-biased survivor effect on resolved markets, not a regime
shift; (c) `50c+ × 5-30s` lead shows `46.93%` win rate vs `~85%` at
longer leads (`473` fills) — incidental finding suggesting late-
window mean-reversion in high-price markets, separate from the
maker-side thesis; (d) sample is too small (55 markets) for
confident magnitude, but not contradictory of Phase A. Implication:
the maker-side direction is robust across both regimes.
Recommendation: run Phase D (LightGBM on Becker, faster) before
Phase B2 (maker simulator with fillability modeling) — D uses
already-loaded data and tests for any non-linear taker signal we
haven't explored. Whether D surfaces new edge or not, B2 is the
correct next concrete step. No bot config/paper/live/cap/wallet/
order-path change authorized; this is supporting-only research per
OQ-081.

**Follow-up 2026-05-06 Session 182 LightGBM taker signal (Phase D):**
Added `scripts/becker_lightgbm_taker_signal.py` and
`docs/reports/becker-lightgbm-taker-signal-2026-05-06.md`/`.json`.
Pipeline: built `66M`-fill feature parquet with `19` features
(price, lead, fee, shares, symbol/side, calendar, strictly-causal
Binance returns at `1m`/`5m`/`10m`, vol `60m`+`10m`, wallet train
log volume), trained LightGBM on `5M`-row stratified train sample,
evaluated on `55,595,402` test rows. Result: **strong discrimination,
zero profitable taker edge.** Test AUC `0.8632` (random `0.5`),
near-perfect calibration at decile resolution, but no edge-threshold
filter produces materially positive buyer ROI on test. Best cell
`edge=0.03` → `4.1M` fills, `+0.16%` ROI (Wilson CI essentially
zero). **Top `0.1%` by predicted edge is the WORST**: predicted
`38.77%` vs actual `23.11%` win rate (`16pp` overestimate), buyer
ROI `-19.06%` — model is overconfident at the extremes where it
would actually trade. Feature `price` dominates importance (gain
`22.4M` vs next `200k`, `100×` separation) — model learned that
price predicts outcome, which is true but already priced in. **Final
verdict on the taker direction:** every variant tested fails. Becker
market is well-calibrated at the bucket level; individual mispricings
exist but cannot be reliably picked out at realistic fees. Bot G's
design premise has no edge in this dataset. The **maker-side
direction (Phase A + B1)** remains the only positive-EV pocket
across the entire analysis. **Phase B2 (maker simulator)** is the
clear next concrete step. Bot G live continuation is now an
explicit operator-decision moment given the trajectory `-73%` ROI on
real money plus negative results across every taker hypothesis.
No bot/paper/live/cap/wallet/order-path change authorized from this
report; supporting-only per OQ-081.

### OQ-076 — Bot D CLOB SELL funder address confirmation (the operator) [RESOLVED 2026-05-05]

**Category:** Decision-required / live exit plumbing.
**Owner:** the operator.
**Surfaced by:** 2026-05-05 Bot D take-profit activation attempt; ADR-106.

**Resolution 2026-05-05:** False alarm. The automated post-fix take-profit
SELL succeeded before the manual FOK retry. the bot LXC container DB shows order
`0x7a3714...b1eaf` filled, SELL trade
`fb4fc024-6485-4be6-8778-6fc40c704a9e` at `0.994` for `5` shares, and
position `632` closed at size `0`. No proxy/funder env change is required for
the current hot wallet.

### OQ-092 — Execute zero-value resolved-position redemption sweep (the operator) [RESOLVED 2026-05-04]
_(Renumbered 2026-05-08 from OQ-063 to OQ-092 to resolve a duplicate ID. The active OQ-063 is the Bot G post-live tiny-probe entry that the rest of the repo references.)_

**Category:** Decision-required / wallet maintenance.
**Owner:** the operator.
**Surfaced by:** 2026-05-04 Polymarket account Active-view cleanup.

**Problem:** The account Active view still shows resolved BTC/SOL/ETH rows
because the wallet holds losing ERC-1155 CTF token balances. Read-only audit
found `13` standard, non-negative-risk, redeemable, zero-current-value rows.
The script `scripts/redeem_resolved_positions.py` can redeem/burn them with
`redeemPositions(..., [1, 2])`, but executing it sends real Polygon
transactions from the hot wallet.

**Acceptance criteria:** the operator explicitly approves or rejects the exact
zero-value sweep. If approved, run the helper with `--execute --yes`, verify
the Polymarket Active view drops the `13` resolved crypto rows, and confirm
the NYC May 6 weather row remains untouched.

**Resolution 2026-05-04:** the operator explicitly approved the exact 13-row sweep.
The helper was deployed to the bot LXC container and executed as `bot`; all `13`
transactions mined successfully. Post-checks show `open=2`,
`redeemable_zero_standard=0`, and the remaining Active rows are weather
positions.

### OQ-061 — Bot C extract-or-archive decision (Claude) [RESOLVED 2026-05-04]

**Category:** Research-required / fleet cleanup.
**Owner:** Claude.
**Surfaced by:** 2026-05-02 active fleet revamp.

**Problem:** Pyth Directional (Bot C) remains active enough to keep in the
dashboard, but it may soon be archived to focus on Longshot Prime, Weather
Fade, Maker Flow, and Oraclemangle Kelly. Before archiving, we need to identify
whether Bot C owns reusable market-data, Pyth, modeling, or synthetic-fill
features worth extracting into shared modules.

**Acceptance criteria:** Produce a short extraction map listing Bot C features
to keep, modules/tests to archive, dashboard/API impact, and any data-retention
requirements. If nothing useful remains, propose an ADR to archive Bot C from
active surfaces.

**Progress 2026-05-02:** Extraction map written at
`docs/reports/bot-c-extract-archive-audit-2026-05-02.md`. Verdict: keep Bot C
on the active dashboard for now, extract reusable Pyth/probability/parser
pieces first, and then decide whether to explicitly unarchive the service in
code or write a later archive ADR.

**Resolution 2026-05-04:** the operator approved retiring Bot C after local review,
external-model confirmation, and Opus codebase review. ADR-093 archives Bot C
from active/paper trading surfaces. The active registry/dashboard/readiness
path now excludes `bot_c`; `polymarket-bot-c.service` is disabled in
production and inert by default in repo systemd. Reusable assets retained:
Pyth/Hermes feed registry, bar models, ingest code, GBM/probability math,
question parser, historical bars, and `bot_c_decisions`. Any final replay is
research-only and not a prerequisite for decommission.

### OQ-064 — Bot G decimal overlap band expansion after transfer proof (Empirical) [RESOLVED 2026-05-03]

**Category:** Research-required / live validation.
**Owner:** Empirical; Claude reports; the operator decides any band change.
**Surfaced by:** 2026-05-02 paper-shadow winner without live fill and the operator's
question about widening scope around the current `4c-5c` band.

**Problem:** The dashboard/report now includes an exploratory `3.5c-5.5c`
overlap split, but the live Bot G Prime unit remains intentionally hard-guarded
at `4c-5c`. Decimal analysis bands are useful for evidence slicing, but live
orders must respect each market's tick size and should not be widened until
paper candidates transfer into actual live fills.

**Acceptance criteria:** Before any live band change, report the `3.5c-5.5c`
sample count, raw ROI, ex-largest-win ROI, ex-largest-two ROI, capacity
coverage, and paper-to-live transfer rate. Any proposed live change must state
the exact live min/max prices and whether the target markets support
sub-cent ticks.

**Blocks:** Any Bot G live entry-band expansion beyond the current `4c-5c`
unit configuration.

**Resolution 2026-05-03:** the operator explicitly approved widening Bot G Prime Live
to observed `3.5c-5.5c` with max submitted limit `5.5c` and unchanged caps.
ADR-085 records the live-band change. Ongoing proof and rollback monitoring
move back to OQ-063.

### OQ-062 — Bot G tiny-live activation approval and caps (the operator) [RESOLVED 2026-05-02]

**Category:** Decision-required / live activation.
**Owner:** the operator.
**Surfaced by:** 2026-05-02 Bot G tiny-live readiness prep.

**Problem:** Bot G Prime is being prepared for a possible first small
real-wallet probe, but current work is reporting-only. No live activation,
wallet setting, or real-money order is authorized by the runbook or dashboard.

**Acceptance criteria:** the operator explicitly approves or rejects Bot G live
activation, first trade size, daily entry cap, max open positions, max daily
loss, and rollback procedure. If approved, record the exact caps in a new
session changelog/memory entry and confirm the ADR-073 candidate gate status
before touching service environment.

**Progress 2026-05-02:** ADR-074 and
`docs/bot-g-tiny-live-runbook-2026-05-02.md` define a proposed tiny-live
probe at `$5` starting size, `10` entries/day, `$50` daily gross notional, and
`5` max open positions. This is a proposal only; Bot G remains paper/dry-run.

**Progress 2026-05-02 Opus audit follow-up:** ADR-075 fixed the live-path
accounting gaps without reducing paper collection: live orders no longer
persist as `PAPER_OPEN`, Bot G polls `Portfolio.reconcile_live_fills()` when
effective-paper is false, live-only caps are code-visible, and
`bot_g.runtime_state` events expose `BOT_G_ENV`, `BOT_G_DRY_RUN`,
`POLYMARKET_ENV`, and `effective_paper` to the dashboard. Production runtime
state after deploy confirms global `POLYMARKET_ENV=live`, but Bot G remains
effective-paper because `BOT_G_ENV=paper`, `BOT_G_DRY_RUN=true`, and
`paper_override=true`.

**Progress 2026-05-02 wallet-sizing follow-up:** the operator selected `$200` as the
Bot G tiny-live wallet allocation. ADR-076 originally recorded the
fixed-notional packet, later superseded by ADR-077:
`$5` entries (`2.5%` of wallet), `10` entries/day, `$50` daily gross notional
(`25%` of wallet turnover), and `5` max open positions (`$25` intended open
stake, `12.5%` of wallet). Live activation itself remains unapproved and
blocked until a future explicit go-live instruction.

**Progress 2026-05-02 cap-update follow-up:** the operator updated the prepared cap
packet to `$100` daily gross notional and `10` max open positions while
keeping `$200` wallet, `$5` fixed entries, and `10` entries/day. ADR-077
records the current packet. With `$5` entries and `10` entries/day, the entry
count still binds actual daily order flow at `$50`; the `$100` gross cap is an
outer ceiling for a later approved size/count increase.

**Resolution 2026-05-02:** the operator explicitly approved activating Bot G Prime
live now. ADR-078 records the accepted live packet: separate
`bot_g_prime_live` unit, `4c-5c` live band, `20` entries/day, `$100` daily
gross notional, `10` max open positions, `$200` wallet posture, `$5` fixed
entries, and the existing `bot_g_prime` service retained as the `4c-8c`
paper shadow. The live unit must carry `BOT_G_LIVE_APPROVED_AT=2026-05-02`.

**Blocks:** Resolved. Post-live proof is tracked separately under OQ-063.

### OQ-032 — Bot B re-entry after manual position close (Claude) [RESOLVED 2026-04-18]

**Category:** trading correctness / emergency-playbook hole
**Owner:** Claude
**Why it's open:** Session 14 recommendation was to SELL Bolsonaro NO (170-day resolution) to free capital. Sell executed at 11:31 UTC; $20.17 proceeds returned to wallet. Verified by 12:21 UTC re-mark: **Bolsonaro NO is back in Bot B's positions at cost ~$20.31.** Root cause: Bot B's `has_existing_position` only gates on status='OPEN'; our UPDATE to status='CLOSED' made the market look fresh, Bot B's candidate filter passed, and Bot B re-entered within its next scan cycle. Net: ~$0.25 in slippage+fees, zero capital freed.
**Revisit when:** operator wants to do another manual position close while Bot B is unhalted. **Do not repeat the Session-14 sell playbook without one of:** (a) halt Bot B before selling, (b) add a "recently-closed" cooldown to Bot B's candidate filter, (c) blacklist the specific condition_id post-sale.
**Acceptance criteria:** design a `recently_closed_cooldown_hours` config knob (default 72h) that checks `closed_at` timestamps on CLOSED positions; Bot B skips any condition_id closed within the cooldown window. Add unit test covering the Bolsonaro scenario.
**Blocks:** any "trim positions for capital" operation while Bot B is live.

**RESOLUTION (2026-04-18, Session 17i audit, 1 day ahead of 2026-04-19 kill-date target):**
- `BOT_B_RECENTLY_CLOSED_COOLDOWN_HOURS` env knob (default 72) landed at [`bots/bot_b/config.py:76`](../bots/bot_b/config.py#L76) (Session 17g).
- `_recently_closed_cids()` helper reads CLOSED position `closed_at` timestamps: [`bots/bot_b/candidates.py:54`](../bots/bot_b/candidates.py#L54).
- Candidate filter threads the cooldown set: [`bots/bot_b/candidates.py:87`](../bots/bot_b/candidates.py#L87).
- Regression coverage: [`tests/test_bot_b_cooldown.py`](../tests/test_bot_b_cooldown.py) (6.1K, Bolsonaro-scenario included).
- Escape hatch: `BOT_B_RECENTLY_CLOSED_COOLDOWN_HOURS=0` disables without redeploy.
- **Unblocks:** "trim positions for capital" playbook — still halt Bot B first as belt-and-braces, but re-entry within the cooldown window is now code-prevented.

---


### Phase 2 / pre-numbering items

### OQ-R1 — Strategy choice (resolved ADR-002, ADR-003 at Phase 3)
Resolved to Bot A (longshot fade) + Bot B (oraclemangle Kelly).

### OQ-R2 — Oraclemangle dependency (resolved ADR-004 at Phase 3)
Resolved to port into this repo, don't consume upstream.

### OQ-R3 — UK access (resolved Phase 2.5)
Resolved: UK explicitly blocked; proceeding under ADR-011 capped-exposure + VPN posture (working assumption).

### OQ-R4 — Fee V2 structure (resolved Phase 2 + Phase 2.5)
Resolved: geopolitics fee=0, politics/finance/economics ≤5 bps, maker rebates 20–25%.

### OQ-R5 — py-clob-client safety (resolved Phase 2.5)
Resolved: local EIP-712 + HMAC signing, no remote key handling, no sensitive logging.

### OQ-R6 — Bankroll + drawdown (resolved by the operator 2026-04-15)
Confirmed: £5k total / £1k per bot at full scale / 15% per-bot drawdown kill / 20% aggregate. **Test-phase amounts will be lower** — bot code reads `BOT_A_BANKROLL_GBP` / `BOT_B_BANKROLL_GBP` from env, so the operator can start paper at £100 or whatever and ramp per the graduation ladder in `specs/test-protocol.md` without code changes.

### OQ-R7 — Tax + ToS posture (resolved by the operator 2026-04-15)
Confirmed: proceed under posture (c)/(c). Tax will be dealt with after profit is established; HMRC-ready logging stays on by default (see OQ-004). Capped $2k exposure + the VPN provider VPN unchanged from Session 1. ADR-010, ADR-011, ADR-014 all stand.

### OQ-R8 — Rotation + Week-1 start (resolved by the operator 2026-04-15)
Confirmed: the operator is home for the next 6 weeks from 2026-04-15. Week-1 shared infra is already built (see CHANGELOG Session 2). **New calendar:** Weeks 1–2 finish shared infra + Bot A + Bot B; Weeks 3–4 paper-run; Week 5 graduation decision at £100 or equivalent; Week 6 live ramp per protocol. 4-on/4-off assumption shelved until a rotation date is set.

### OQ-105 — Bot G live missing fleet exposure guard (Claude) [RESOLVED 2026-05-12]
**Category:** Blocking
**Owner:** Claude
**Unlock:** Add `check_fleet_exposure(BOT_ID, actual_notional)` before `clob.place_limit` in `_try_enter_market`, mirroring Bot D. One-line fix. Audit finding #1.

**Resolution 2026-05-12:** ADR-157 fixed live/paper fleet-cap filtering to
use canonical registry status and cap-member bot ids before environment
fallbacks. Live-mode fleet caps now ignore paper/archived exposure and cover
the live bot ids that can place real orders.

### OQ-106 — VPS watchdog daemon gap for live bots (the operator/Claude) [RESOLVED 2026-05-12]
**Category:** Decision-required
**Owner:** the operator
**Unlock:** Decide whether to (a) deploy a minimal watchdog daemon on the VPS that reads the shared halt DB and cancels orders for VPS live bots, (b) extend the bot container watchdog to route cancel via SSH/API to VPS, or (c) accept the gap and document it. Audit finding #2/#4.

**Resolution 2026-05-12:** Chose option (a). ADR-155 adds a
`LONGSHOT_WATCHDOG_HOST_ROLE=vps` scope so the existing watchdog code can run
on the VPS and include `bot_g_prime_live` in live-cap/cancel coverage, plus
`systemd/polymarket-watchdog-vps.service` as the deployable unit template.
The unit was deployed and enabled on `vps-host` via the the homelab hypervisor
hop on 2026-05-12; live Bot G stayed active and was not restarted.

### OQ-107 — Repository not under version control (the operator) [RESOLVED 2026-05-14]
**Category:** Blocking
**Owner:** the operator
**Unlock:** `git init` and commit current state. No code changes required. Audit finding #9.

**Resolution 2026-05-14:** Repository is under git; current sessions show
normal `git status` output with tracked and untracked changes. The remaining
work is ordinary commit hygiene, not repository initialisation.

### OQ-108 — VPN enforcement policy vs code gap (the operator/Claude)
**Category:** Decision-required
**Owner:** the operator
**Unlock:** Decide whether to (a) implement iptables/WireGuard enforcement scripts in the repo per `CLAUDE.md` policy, (b) accept the current DNS+HTTPS probe as sufficient and update `CLAUDE.md` to match reality, or (c) rely on the homelab hypervisor-level tunnel management and document the LXC has no tunnel control. Audit finding #5.

### OQ-109 — Ghost systemd service files for archived bots (Claude)
**Category:** Research-required
**Owner:** Claude
**Unlock:** Remove or move to `systemd/archived/` the 22 ghost service files identified in the dead-code register. One session. Audit finding #18.

**Progress 2026-06-07 (Grok Build Session 466, P3 start):** Audit: `ls systemd/ | grep -E 'bot-(a|b|c|f|g|j|k|d-spike-short|wc|crypto)'` ~31 potential ghosts (e.g. polymarket-bot-a-*.service/timer, bot-b*, bot-g-prime*); `ls systemd/archived/` 17. Sample units in root systemd/ for archived per registry (bot_a status=archived core/bot_registry.py:53, bot_d_spike_short:191 etc). Matches OQ-109 + overhaul-plan-2026-05-30.md:79-81 (ghosts for disabled/archived). No file moves (smallest; edit existing only rule). OQ-109 **Research-required** (owner Claude); progress: count confirmed, list for operator review + archive action per plan. Cross ADR-187.

### OQ-110 — Expand Bot D station divergence sample before edge conclusion (Claude)
**Category:** Research-required
**Owner:** Claude
**Unlock:** Re-run `scripts/bot_d_station_divergence_replay.py` when n >= 100 matched rows. Current n=28 shows 35.7% outcome-flip rate but station-informed PnL (-$68.78) underperforms forecast-based (-$6.38). Sample too small to determine if this is noise or if city-grid forecasts are actually more predictive than METAR station data for these markets. Report at `docs/reports/bot-d-station-divergence-2026-05-10.md`.

### OQ-111 — Bot L BTC 5m complete-set convergence paper lane (Claude)
**Category:** Live-probe candidate / scale-blocking validation
**Owner:** Claude
**Unlock:** Build a paper-only replay/live-paper lane for the xuanxuan008-style BTC 5-minute complete-set/convergence pattern. Starting evidence is in `docs/reports/xuanxuan-btc-5m-strategy-analysis-2026-05-13.md`: public activity shows paired Up/Down buying plus MERGE events, while the local recorder found last-24h BTC 5m paired top-of-book opportunities where YES+NO ask summed below 99.5c/98.5c and bid summed above 100.5c. Gate must include depth, queue, slippage, merge/redeem mechanics, fees, and ex-largest-opportunity robustness before any live proposal.

**Status 2026-05-13:** Paper lane built and deployed on the VPS as
`polymarket-bot-l-complete-set-paper-vps.timer`. First 24h backfill wrote
`154` signals across `30` BTC 5m markets, with `45` surviving a 1c round-trip
haircut. OQ remains open for forward sample size, depth/queue validation,
split/merge mechanics, and ex-largest-opportunity robustness before any live
proposal.

**Audit 2026-05-13 (`docs/reports/bot-l-complete-set-audit-2026-05-13.md`,
verdict YELLOW):**

- Claimed numbers reproduce exactly against the VPS DB (`154` signals /
  `45` executable / `30` markets / raw `+$2.3084` / exec `+$1.9665`).
- **Depth is silently unenforced.** `154/154` signals have `yes_size IS NULL
  OR no_size IS NULL`; the systemd unit omits `--min-depth-shares` so the
  default `0` makes the depth gate dead code.
- **BUY-MERGE arb and SPLIT-SELL arb are aggregated** into one
  `executable_pnl_usd` even though they price two different operations
  with different gas, capital, and atomicity assumptions. The simulator
  itself tags SELL as "inventory/split research only" in the payload.
- **Concentration is structural:** top-1 market is `24.3%` of executable
  P&L; top-3 `46.4%`. Ex-largest-10 leaves only `$0.49` over the remaining
  `35` rows (~`$0.014/row`, below the assumed haircut).
- **Forward signal rate is zero.** All `154` signals came from the initial
  one-shot 24h backfill (run 1). The subsequent `90` incremental runs over
  the next 2+ hours advanced the cursor through `~4,600` recorder events
  and produced `0` new signals.
- **Test fixture uses a crossed book** (`bid=0.51 > ask=0.48`) and the
  simulator records both BUY and SELL from it. The audit recommends a
  `parse_quote` sanity check rejecting `bid > ask`.
- Isolation is clean: no CLOB client, wallet, keystore, passphrase, env,
  or live-ledger writes anywhere in Bot L source; `include_in_cap=False`;
  systemd `ProtectSystem=strict` with `ReadWritePaths` scoped to `data/`
  and `logs/`.

**Promotion gates required (all):**

- ≥ `500` executable forward signals (depth-validated), ≥ `50` distinct
  markets, ≥ `14` days observation including ≥ 1 weekend.
- Top-1 market concentration `< 10%`, top-3 `< 25%`.
- BUY and SELL ex-largest-10 P&L `> +0.5%` of cost basis, separately,
  with the SPLIT-and-sell path explicitly modelled including Polygon gas.
- Depth check: both legs ≥ `gross_cost_usd / adjusted_sum` shares observed
  at quote time.
- Negative control: same threshold logic on ETH and SOL 5m markets must
  produce comparable signal rate; a 10× rate gap implies symbol-specific
  noise.

Until all gates clear and a new ADR is approved, Bot L stays paper-only.
ADR-159's safety boundary is unchanged.

**Progress 2026-05-14:** Implemented the audit next-actions without changing
the ADR-159 paper-only boundary. `parse_quote` now rejects crossed books and
records depth diagnostics distinguishing missing, invalid, and zero/negative
size fields plus direct-vs-book fallback source. Bot L simulator and VPS node
status now split executable P&L and executable signal counts into BUY and
SELL buckets. Added a read-only daily report script/timer and a read-only
sensitivity sweep script using disposable paper DBs. Deployed to
`vps-host`, enabled the daily report timer, and ran the requested
`--full-refresh --lookback-hours 168`: baseline is now `255` signals,
`82` executable, `45` markets, raw `+$3.7180`, executable `+$3.1252`,
BUY executable `+$1.6252` over `38` signals, SELL executable `+$1.5000`
over `44` signals. A 9-combo sweep over slippage `0/0.005/0.010` and pair age
`500/1000/2000ms` ranked slippage `0`, pair age `2000ms` highest with
`103` executable signals and `+$2.4860` executable P&L. OQ-111 remains open:
depth-validated forward sample size, concentration, ex-largest robustness,
gas/merge modelling, and ETH/SOL negative controls still have not cleared.

**Progress 2026-05-14, full-audit follow-up:** Read the full
`docs/reports/bot-l-complete-set-audit-2026-05-13.md` and actioned the
remaining implementation-level findings. Added a no-lookahead
`stale_after_end_date` block so after-close signals are recorded as
non-executable, forward failure counters for diagnosing signal-rate collapse,
and richer daily gate slices (top-1/top-3 concentration, ex-largest
`{1,5,10,20}`, pair age, signal rate, reason counts). Added and ran
`scripts/bot_l_complete_set_depth_probe.py` on the VPS: over `168h`,
`best_bid_ask` had `58,620` BTC 5m rows with `0` direct sizes, while `book`
had `49,370` rows with `48,760` usable bid sizes and `48,760` usable ask
sizes. So the size blocker is not that depth is absent from the recorder; it
is that Bot L's signal rows are mostly sourced from `best_bid_ask` and need a
nearby book-depth join. Ran the audit-specific 27-combo threshold sweep
(`raw_buy=0.990/0.995/0.998`, `raw_sell=1.002/1.005/1.010`,
`slippage=0.0025/0.005/0.010`, pair age `1000ms`); top rows produced `62`
executable signals and `+$1.7264` executable P&L. Current report slices still
fail the concentration gates: top-1 `15.26%`, top-3 `29.19%`. Next OQ-111
implementation step: join candidate signals to the latest same-asset `book`
snapshot within a strict freshness window and require both legs to have
depth >= `gross_cost_usd / adjusted_sum` before `executable=1`.

**Progress 2026-05-14, depth enforcement:** Implemented the fresh-book join.
Bot L now keeps latest same-asset `book` snapshots separately from price
quotes, rejects future/stale depth joins, and only marks a row executable when
`--require-depth` is active and both legs have depth at least
`gross_cost_usd / adjusted_sum` within `--max-depth-age-ms 1000`. The VPS
paper unit now runs with depth enforcement. Backed up the previous paper DB to
`data/bot_l_complete_set_paper.db.pre-depth-reset-20260514T074156Z`, reset the
Bot L paper tables, and rebuilt the `168h` baseline. Depth-enforced baseline:
`104` signals, `37` executable, `16` markets, raw `+$1.4496`, executable
`+$1.1687`; BUY executable `+$0.5087` over `16` signals, SELL executable
`+$0.6600` over `21` signals. Verified `0` executable rows have NULL YES/NO
size. Concentration still fails promotion gates: top-1 `13.29%`, top-3
`37.62%`. Depth-enforced sensitivity sweep over slippage `0/0.005/0.010` and
pair age `500/1000/2000ms` ranked slippage `0`, pair age `2000ms` highest
with `101` executable signals and `+$2.4459` executable P&L; deployed haircut
slippage `0.005` remains `37` executable and `+$1.1687`. OQ-111 remains open:
forward-only depth-validated sample size, concentration, SPLIT/MERGE gas, and
ETH/SOL negative controls still have not cleared.

**Fast-probe posture 2026-05-14 (ADR-163):** Bot L may be considered for a
tiny live-probe packet before the old `500` signal / `50` market gate clears,
but only if the packet resolves complete-set atomicity, split/merge gas,
depth freshness, max-loss, and stuck-inventory rollback. The old gate now
blocks scaling and any durable edge claim. Actual trading still requires a
new ADR and explicit the operator approval.

**Readiness progress 2026-05-14 (ADR-164):** Added a Bot L BUY/MERGE-only
tiny live-probe spec and tests. The prepared shape is max bundle gross `$1`,
daily gross `$10`, open exposure `$20`, max `2` concurrent bundles, gas cap
`$0.25`, mandatory same-asset fresh-book depth join, and no live
SELL/SPLIT action. Kill switches cover unhedged leg `>$2`, net realised
`<= -$3` after gas, depth join failure, merge failure, stuck inventory, and
atomicity/reconciliation anomalies. OQ-111 remains open for actual merge
implementation detail, gas/reconcile proof, and forward depth-validated
sample quality before any activation ADR.

**Approval progress 2026-05-14 (ADR-165):** the operator approved the BUY/MERGE tiny
live probe and requested dashboard live status. The registry/dashboard now
marks `bot_l_complete_set` as a live probe. OQ-111 remains open for scale:
forward-only depth-validated sample size, concentration, gas/merge evidence,
negative controls, and stuck-inventory/reconciliation proof still block any
size increase or durable edge claim.

**Progress 2026-05-15 aggressive review (ADR-170):** Current VPS runtime is
still the paper timer, not an operational live BUY/MERGE service. Latest
daily report shows `140` signals, `49` executable, executable P&L `+$1.8266`,
BUY executable P&L `+$0.8766`, SELL executable P&L `+$0.9500`, top-1
concentration `22.76%`, and top-3 concentration `39.12%`. ADR-170 keeps the
concentration/gas/depth gates as scale blockers and recommends operational
activation only for the already-approved BUY/MERGE `$1` bundle probe; live
SELL/SPLIT remains unapproved.

**Progress 2026-05-15 deployment (ADR-172):** the operator approved Bot L BUY/MERGE
tiny-live activation. A conservative live-probe runner/timer was implemented
and deployed on the VPS, but it is intentionally self-blocking under the
approved `$1` cap when the exchange `5`-share minimum cannot be met. The
first confirmed live-probe pass returned `below_exchange_min_shares` at
`$1.0000` gross / `1.0309` shares and placed no order. OQ-111 remains open
for a revised minimum viable bundle cap decision, actual MERGE transaction
path, gas accounting, stuck-inventory recovery, and scale evidence.

**Progress 2026-05-15 cap adjustment (ADR-173):** the operator approved adjusting Bot
L caps so it can trade. The max BUY bundle cap was raised from `$1` to `$5`,
daily gross remains `$10`, open exposure remains `$20`, and scope remains
BUY-both-legs only. The runner was hardened to persist/cancel-attempt a
one-leg YES fill if the NO leg rejects, to require a fresh executable signal
(`<=120s`), and to check both live books exist before submitting orders.
OQ-111 remains open for MERGE, gas, stuck-inventory recovery, concentration,
and scale evidence.

### OQ-112 — Bot D Station Lock paper forward proof (Empirical)
**Category:** Live-probe candidate / scale-blocking validation
**Owner:** Empirical
**Unlock:** Review `bot_d_station_lock` after at least `30` resolved paper
fills or `14` days of forward runtime, whichever comes first. Required
evidence: fill count, resolved correctness, realised paper P&L, ROI after a
conservative spread/slippage haircut, reject histogram, rounding-disagreement
rate, WU mutation unsafe rate, station-source age distribution, and
lag-to-repricing where Polymarket prices move after station certainty. The
lane remains paper-only until a new ADR explicitly accepts a live proposal.

**Status 2026-05-13:** Built, tested, and deployed on the bot container as
`polymarket-bot-d-station-lock.service`. First scan saw `6` weather
candidates and wrote `0` entries / `6` skips.

**Progress 2026-05-14 Session 371:** Read-only the bot container review showed the service
active with `1,586` candidates, `1,585` skips, `1` paper fill, and `1`
resolution since deployment. The resolved paper fill was Atlanta
`2026-05-13`, `BUY_NO`, paper trade `$5`, realised P&L `+$1.2112`, and
`resolved_correct=True`. The reporting script failed on the bot container because
SQLAlchemy was not installed there; patched
`scripts/bot_d_station_lock_report.py` to read `events` via stdlib SQLite and
added a focused regression. OQ-112 remains open: the lane has `1/30` resolved
paper fills and less than `14` days of runtime.

**Fast-probe posture 2026-05-14 (ADR-163):** The `30` resolved fills / `14`
day gate now blocks scale and production claims, not a tiny station-certainty
live-probe packet. Any packet must cap exposure tightly and prove settlement
station, rounding, WU/METAR mutation, and stale-source behavior are monitored
before orders can be enabled. Actual trading still requires a new ADR and
explicit the operator approval.

**Readiness progress 2026-05-14 (ADR-164):** Added the Bot D Station Lock
tiny live-probe spec and guard tests: hard-lock only, `$5` max order, `$20`
daily gross, `$25` open exposure, `5` concurrent positions, and kill switches
for any classifier/settlement mismatch, `2` hard-lock losses, realised P&L
`<= -$10`, stale station data, or live order/reconcile anomaly. The paper
service default caps now mirror the proposed tiny-live envelope. No live
executor was enabled; actual trading still requires a later activation ADR
and the operator approval.

**Approval progress 2026-05-14 (ADR-165):** the operator approved the tiny live probe
and requested dashboard live status. The registry/dashboard now marks
`bot_d_station_lock` as a live probe. OQ-112 remains open as the scale gate:
the `30` resolved fill / `14` day target still blocks scaling or production
claims.

**Progress 2026-05-15 aggressive review (ADR-170):** Current the bot container runtime is
still `BOT_D_ENV=paper` with `BOT_D_STATION_LOCK_PAPER_ONLY=true`, despite
dashboard live-probe approval. ADR-170 keeps OQ-112 as a scale gate and
recommends separate operational approval to activate the already-approved
hard-lock-only `$5` max-order / `$20` daily-gross / `$25` open-exposure probe.

**Progress 2026-05-15 deployment (ADR-172):** the operator approved Station Lock
tiny-live activation. The live order/reconcile path was implemented and
deployed on the bot container as `polymarket-bot-d-station-lock-live-probe.service`,
replacing the paper service. The live-probe service is active under the
approved `$5` max order / `$20` daily gross / `$25` open exposure caps. OQ-112
remains open as a scale and settlement-transfer gate, not an activation gate.

### OQ-116 — Bot D maker live probe first evidence gate (Empirical)
**Category:** Scale-blocking
**Owner:** Empirical
**Surfaced by:** 2026-05-15 ADR-174.

**Question:** Does the separate `bot_d_maker_live_probe` lane improve Bot D
live execution quality versus the existing taker lane without introducing
adverse-selection losses, stale quote risk, or operator burden?

**Current approved envelope:** `$200` wallet posture, `$5` normal minimum
quote notional, `$10` max order, `$100` daily gross, `$100` open exposure,
`20` max concurrent positions/orders, `180s` quote max age, verified Bot D
settlement cities only, BUY maker quotes only. ADR-175 adds two safety
exceptions: no quoting when the market is ended or inside
`BOT_D_MAKER_MIN_ENTRY_HOURS_TO_END=3`, and cheap/late BUY_YES maker quotes
are capped at `$2` by default.

**Acceptance criteria:** Review after the first of:

1. `10` maker fills,
2. `25` maker quotes placed, or
3. `48` hours runtime.

The review must include quote count, fill count, cancel count, stale-cancel
count, realised P&L, ROI, open exposure, daily gross usage, adverse-selection
summary by fill price bucket, comparison against `bot_d_live_probe` taker
fills over the same window, and any untracked/duplicate/stale quote anomaly.

**Blocks:** Any cap increase, size increase, city expansion, or conversion
from tiny-live experiment to normal Bot D live capacity for this maker lane.

### OQ-122 — Bot D Ensemble Ladder paper basket proof (Empirical)
**Category:** Live-probe candidate / scale-blocking validation
**Owner:** Empirical
**Surfaced by:** 2026-05-16 ADR-179 after reviewing the public ensemble
ladder weather-bot write-up.

**Question:** Does `bot_d_ensemble_ladder` produce positive event-level ROI
from adjacent cheap YES temperature baskets after fees/slippage, or is the
public write-up's three-day result too concentrated in a few lottery wins?

**Current lane:** Paper-only `bot_d_ensemble_ladder`. It writes
`bot_d_ensemble_ladder.plan` and `bot_d_ensemble_ladder.scan_summary` Event
rows only. It uses station-exact verified cities, an `18h-30h` time-to-end
window, ICON/GFS/ECMWF deterministic forecasts, closest-pair consensus,
max spread `3.0C`, each leg `1c-45c`, total YES basket price `<=95c`, and
`$2` nominal stake per leg.

**Acceptance criteria before any live proposal:** At least `30` resolved event
baskets and at least `7` calendar days of runtime. Report event-basket count,
leg count, win rate, realised event-level P&L, ROI after taker fees and a
spread/slippage haircut, ROI excluding the largest win, city-level ROI,
model-spread bucket ROI, and whether `bias_correction=true` changed forecast
outputs versus the no-bias shadow. A tiny-live packet may only be proposed if
ROI is positive after excluding the single largest winning basket and no
enabled city shows persistent negative outlier behavior.

**Blocks:** Any live trading, cap proposal, or merge of ladder logic into the
main Bot D live/taker/maker lanes.

### OQ-113 — Bot J audit-remediation gate (Claude + Empirical)
**Category:** Live-probe candidate / scale-blocking validation
**Owner:** Claude (P0b redesign + P2/P3 code work); Empirical (concentration analysis at n>=200); the operator (P1 daily-cap raise).
**Surfaced by:** 2026-05-11 Session 341 comprehensive Bot J audit
(`docs/audits/bot_j_audit_2026-05-11.md`).

**Already cleared (verified 2026-05-14):**
- **P0a — Dead/incorrect `after` cursor.** Session 371 found the live scan
  path still effectively empty because `run_once()` queried the observer DB
  for rows after the observer DB's own `MAX(ingested_at)`. Patched
  `bots/bot_j_nr_wallet/executor.py` to scan qualifying rows and skip
  already-recorded deterministic paper order IDs instead.
- **P2 — Silent YES default** in `_token_side` is already fixed.
  `bots/bot_j_nr_wallet/executor.py:167-176` logs
  `bot_j.unknown_token_side` and returns `None`; caller at line 197
  skips the entry instead of recording a YES.

**Still open before any Bot J live or feature-plumbing promotion:**

1. **P0b — Strict-settlement gate unreachable.** Across `1,619`
   proxy-settled markets, the wallet-tag strict-settlement monitor
   returns `0` strict settlements (`settled=1`). The threshold of `50`
   will never fire. Redesign the gate to use proxy-settlement data, or
   replace it with a settlement-bias-corrected backfill (related to the
   wallet-tag strict-settlement backfill bias check).
2. **P1 — Daily entry cap.** Current `10/day` samples roughly `15%` of
   the `63-77` qualifying sports conditions/day. Operator decision: raise
   to `20/day` to accelerate calibration toward `n>=200`, or accept the
   slower pace to keep DB growth bounded.
3. **P1 — Signal concentration.** One wallet (`0x397e4f...`) drives `64%`
   of qualifying entries and `89%` of edge. Two wallets are net negative.
   Add per-wallet quality tracking to the executor and rebuild the cohort
   math without the dominant wallet so the edge claim survives a
   leave-one-out check.
4. **P2 — Sports keyword over-matching.** Tokens `"game"`, `"map"`,
   `"vs."` match non-sports content. Empirical false-positive rate is
   `4.3%` today but is fragile against new market types. Tighten the
   filter or add a category cross-check.
5. **P3 — Hardcoded values.** Taker-fee assumption (`is_maker=False`)
   and USD/GBP rate (`0.79`) are baked in. Pull both from `core/fees`
   and a daily FX snapshot.
6. **Investigate — 65% NULL-question gap.** `762` of `1,158` qualifying
   cohort trades have no `question` text in `observed_markets`. Confirm
   whether this is observer backfill incompleteness or a Gamma-side
   gap.

**Acceptance criteria (all must clear):** P0b redesign deployed with
non-zero forward firings; per-wallet quality tracker landed; leave-one-out
edge still positive at `n>=200`; keyword filter tightened or false-positive
budget signed off; FX/fee values sourced from canonical helpers; question
NULL gap explained or filled.

**Fast-probe posture 2026-05-14 (ADR-163):** Bot J is not a live-probe
candidate until P0b settlement scoring and per-wallet concentration tracking
are fixed. After those are fixed, the `n>=200` leave-one-out gate blocks
scale and production claims rather than a tiny capped live probe. Any live
probe still requires a separate ADR and explicit the operator approval.

**Kill trigger:** if the dominant-wallet edge does not survive the
leave-one-out check at `n>=200`, retire Bot J as a strategy lane and keep
the observer-derived data as research-only.

### OQ-114 — Bot K near-term forward-sample gate (Empirical)
**Category:** Live-probe candidate / scale-blocking validation
**Owner:** Empirical resolves the forward sample; the operator decides any live
promotion.
**Surfaced by:** 2026-05-11 Session 338 Bot K deployment after Becker
sports-taker replay
(`docs/reports/becker-sports-taker-replay-2026-05-11.md`) and Session 340
audit (`docs/reports/bot-k-audit-2026-05-11.md`).

**Problem:** The Becker replay returned `1,245` resolved trades, `81.7%`
win rate, `+506%` fixed-`$5` ROI across every league and sub-category.
That number is a survivorship-biased replay: the entry proxy is the
*first on-chain fill per market*, which silently excludes markets that
never attracted any on-chain trade. Forward Bot K paper started
2026-05-11 and has produced only `4` paper entries to date — all
far-dated 2026 World Cup and NBA Finals futures with no near-term
resolution. The headline `+506%` cannot be carried forward without a
near-term forward sample.

**Acceptance criteria (all):**

1. **n_near_term >= 50** closed Bot K paper entries on markets with
   `time_to_resolution_hours < 168` at entry.
2. **Forward WR >= 60%** and **forward net ROI >= +20%** after fees on
   that subset (versus `81.7% / +506%` replay baseline).
3. **Cross-league spread.** At least `3` distinct leagues represented,
   no single league `> 50%` of entries; survivorship-bias note retained.
4. **Esports check.** Esports sub-segment WR must independently exceed
   `60%`; the Becker replay had it at `66.7%` (weakest segment).
5. **Robustness.** Forward ROI excluding the largest `5` wins must
   stay positive after fees.

**Next action:** broaden discovery so Bot K is not constrained to
far-dated futures — either add a `time_to_resolution_hours` ceiling
(e.g. `<= 168h`) in `bots/bot_k_sports_taker/executor.py` so futures
are skipped, or relax `initial_yes_price` band selection to cover
late-game sports markets. Do not quote the `+506%` Becker number as a
forward expectation in any report until this OQ clears.

**Progress 2026-05-14 Session 372:** Chose the near-term ceiling path under
ADR-161. Bot K paper now skips markets with `time_to_resolution_hours > 168`
when recorder `markets.end_date_ts` is available. This does not authorize live
trading; it makes the paper lane collect near-term evidence that can resolve
quickly enough for this OQ.

**Fast-probe posture 2026-05-14 (ADR-163):** Bot K is one of the preferred
first tiny-live packet candidates because its historical sample is large and
the remaining question is live forward transfer. The `50` near-term closed
paper-entry gate now blocks scaling and quoting Becker `+506%` as a forward
expectation; it does not block drafting a small live-probe packet after the
near-term filter has produced an initial viable sample. Actual trading still
requires a new ADR and explicit the operator approval.

**Kill trigger:** if forward WR < `60%` or forward ROI < `+20%` after
fees at `n_near_term >= 50`, archive Bot K and keep the Becker replay
script as research-only.

**Progress 2026-05-15 aggressive review (ADR-170):** Bot K remains a strong
future candidate but not an immediate live probe. the bot container paper is active with
only `5` open forward entries so far. The Becker replay remains promising,
but ADR-170 keeps the near-term forward-sample gate intact before any live
activation packet.

### OQ-117 — Crypto maker-shadow promotion gate and ADR number reconciliation (Empirical + the operator)

**Owner:** Empirical resolves maker-shadow performance; the operator resolves the ADR
numbering conflict before any live conversion.
**Surfaced by:** 2026-05-15 Session 387 crypto maker-conversion goal.

**Problem:** The operator goal names ADR-131 for the maker-conversion and Cell
C decision, but ADR-131 is already occupied in this repo by the Bot D
zero-value negative-risk redemption cleanup. The maker-conversion evidence is
also below the live/probe threshold: Bot I maker replay has only `n=2`, Cell C
maker paper has `n=4`, crypto FV maker shadows have `n=2`/`n=4`, and Bot G
maker shadows are active but still at `n=0`.

**Acceptance criteria:**

1. Reconcile the ADR number conflict without deleting or moving existing
   ADR-131. Use the next valid ADR number unless the operator explicitly instructs a
   different archival convention.
2. Keep all in-scope taker baselines running until each maker shadow reaches
   `n>=50` or the 5-day S5 gate.
3. For each bot, file maker-vs-taker ROI, fill/sample count, and S6 decision
   in the final maker-conversion report before any live executor switch.
4. File the Cell C outcome as live `$5`, live `$1` probe, or rejection only
   after the Cell C maker-paper gate reaches `n>=50` or the 5-day gate.

**Current state 2026-05-15 23:58 UTC:** S1-S4 are complete and pushed to
`origin/main`. the bot container maker paper-shadow services are active, the S5 comparator
timer and 15-minute gate-watch timer are active, and the settlement-aware
comparator shows crypto FV probability-gap maker at 91/91/90 with `+23.56%`
ROI and Brownian maker at 105/105/93 with `+21.51%` ROI. Those FV rows are
`S6_READY`, but they are archived/paper-only lanes in the active operating
model, so this is a review/ADR input rather than live-switch authorization.
The review packet in
`docs/reports/crypto-fv-maker-s6-review-2026-05-15.md` shows the rows pass
ex-largest-win, ex-largest-two, and 1c/2c stress on the current cohort, but
fail or remain weak on symbol concentration, duration concentration,
lead-bucket concentration, and real queue/fillability evidence. The Bot G
maker starvation diagnosis also found that Gamma can drop near-expiry 5m
markets before their advertised endDate; the shared crypto recorder now
retains active subscriptions until endDate plus 90s so Bot G's final-minute
quote feed does not disappear early. The 22:59 UTC and 23:04 UTC post-fix Bot
G windows produced live quotes and ten paper `MAKER_GTC` orders across
`bot_g_prime_live_maker`, `bot_g_prime_maker`,
`bot_g_prime_shadow_maker`, and `bot_g_prime_high_tail_maker`; all cancelled
before/at market close, proving the quote/entry path is alive but not yet
proving maker fills. Bot G maker shadows, Bot I maker shadows, and Cell C
remain below their S6/S7 decision gates. No live executor has been converted,
no live order was placed, and Cell C remains undecided.

**Progress 2026-05-15 23:13 UTC:** Bot G maker paper now has a forward-only
maker-fill reconciliation path. Open paper `MAKER_GTC` BUY bids fill only from
subsequent recorder `last_trade_price` prints where the taker side is `SELL`
and the print price is at or below the bid; fills write normal Portfolio
accounting with zero fee and a `bot_g.maker_paper_filled` event. This does not
change any live/taker service and does not retroactively mutate the ten
already-cancelled paper maker orders.

**Progress 2026-05-15 23:30 UTC:** The current comparator confirms forward
maker-paper fills across all active Bot G maker shadows:
`bot_g_prime_live_maker` is `4/4/0`, `bot_g_prime_maker` is `8/6/0`,
`bot_g_prime_shadow_maker` is `7/3/0`, and `bot_g_prime_high_tail_maker` is
`8/2/0`. These are fill-count advances, not resolved closes, so all Bot G
maker rows remain below the S6 decision gate.

**Progress 2026-05-15 23:33 UTC:** FV settlements advanced without changing
Bot G maker counts. Brownian maker now has 93 closed rows and clears headline
ROI/ex-largest/stress checks, but the reopen decision remains blocked by
ADR-139 concentration/fillability evidence rather than raw ROI.

**Progress 2026-05-15 23:39 UTC:** Bot G maker fills advanced again:
`bot_g_prime_live_maker` is `6/6/0`, `bot_g_prime_maker` is `12/11/0`,
`bot_g_prime_shadow_maker` is `10/5/0`, and
`bot_g_prime_high_tail_maker` is `12/6/0`. Probability-gap maker now has 85
closed rows and clears headline ROI/ex-largest/stress checks, but the FV
reopen decision remains blocked by ADR-139 concentration/fillability evidence.

**Progress 2026-05-15 23:42 UTC:** Bot G maker fills advanced again:
`bot_g_prime_live_maker` is `6/6/0`, `bot_g_prime_maker` is `12/12/0`,
`bot_g_prime_shadow_maker` is `11/9/0`, and
`bot_g_prime_high_tail_maker` is `12/7/0`. These remain fill-count advances,
not resolved closes, so all Bot G maker rows remain below the S6 decision
gate.

**Progress 2026-05-15 23:45 UTC:** Bot G maker fills advanced again:
`bot_g_prime_live_maker` is `6/6/0`, `bot_g_prime_maker` is `14/14/0`,
`bot_g_prime_shadow_maker` is `13/11/0`, and
`bot_g_prime_high_tail_maker` is `14/9/0`. These remain fill-count advances,
not resolved closes, so all Bot G maker rows remain below the S6 decision
gate.

**Progress 2026-05-15 23:48 UTC:** FV maker order/fill counts advanced without
new FV closed rows. Bot G maker rows are unchanged from 23:45 UTC and remain
below the S6 decision gate because resolved closes are still zero.

**Progress 2026-05-15 23:50 UTC:** Bot G maker fills advanced again:
`bot_g_prime_live_maker` is `6/6/0`, `bot_g_prime_maker` is `16/16/0`,
`bot_g_prime_shadow_maker` is `15/13/0`, and
`bot_g_prime_high_tail_maker` is `16/10/0`. These remain fill-count advances,
not resolved closes, so all Bot G maker rows remain below the S6 decision
gate.

**Progress 2026-05-15 23:52 UTC:** Probability-gap FV maker advanced to 89
closed rows and clears headline ROI/ex-largest/stress checks with wider margin,
but the FV reopen decision remains blocked by ADR-139 concentration/fillability
evidence.

**Progress 2026-05-15 23:58 UTC:** Probability-gap FV maker advanced to 90
closed rows and clears headline ROI/ex-largest/stress checks with wider margin,
but the FV reopen decision remains blocked by ADR-139 concentration/fillability
evidence.

**Progress 2026-05-16 00:01 UTC:** The first 2026-05-16 comparator shows Bot G
maker rows advanced to `7/6/0`, `18/21/0`, `17/15/0`, and `18/11/0`. These
remain fill-count advances, not resolved closes, so all Bot G maker rows remain
below the S6 decision gate. FV probability-gap and Brownian are unchanged at
91/91/90 and 105/105/93; FV remains review-only under ADR-139 pending the same
concentration/fillability evidence.

**Progress 2026-05-16 00:16 UTC:** The gate-watch comparator advanced Bot G
shadow maker to `19/16/0` and Bot G high-tail maker to `20/16/0`, while Bot G
live-maker and Prime maker remained `7/6/0` and `18/21/0`. These are still
fill-count advances with zero resolved Bot G maker closes, so S6 remains WAIT.
FV probability-gap maker is `94/94/90` with `+22.81%` ROI, and Brownian maker
is `108/108/106` with `+17.80%` ROI. The FV rows remain review-only under
ADR-139 because the concentration/fillability block is unchanged.

**Progress 2026-05-16 00:31 UTC:** Bot G maker rows now have resolved closes:
live-maker `10/8/3`, Prime maker `22/23/10`, shadow maker `22/18/10`, and
high-tail maker `23/18/10`. The first closed sample is mixed, with live-maker
and high-tail positive but Prime/shadow negative; all four rows remain below
`n>=50`, so S6 remains WAIT. FV probability-gap maker is `99/99/90` with
`+21.66%` ROI, and Brownian maker is `115/115/108` with `+17.21%` ROI. The FV
rows remain review-only under ADR-139 because the concentration/fillability
block is unchanged.

**Progress 2026-05-16 00:46 UTC:** Bot G maker rows advanced to live-maker
`12/12/3`, Prime maker `28/33/10`, shadow maker `28/27/10`, and high-tail
maker `26/28/10`. Closed counts remain below `n>=50`, so S6 remains WAIT; the
current ROI mix is positive for live-maker/high-tail and negative for
Prime/shadow. FV probability-gap maker is `104/104/98` with `+19.76%` ROI, and
Brownian maker is `121/121/113` with `+17.25%` ROI. The FV rows remain
review-only under ADR-139 because the concentration/fillability block is
unchanged.

**Progress 2026-05-16 01:01 UTC:** Bot G maker rows advanced to live-maker
`14/16/3`, Prime maker `31/41/10`, shadow maker `31/30/10`, and high-tail
maker `29/33/10`, but closed counts did not advance from the prior checkpoint.
All four rows remain below `n>=50`, so S6 remains WAIT. FV probability-gap
maker is `106/106/98` with `+19.39%` ROI, and Brownian maker is `124/124/113`
with `+16.83%` ROI. The FV rows remain review-only under ADR-139 because the
concentration/fillability block is unchanged.

**Progress 2026-05-16 01:16 UTC:** Bot G maker rows advanced to live-maker
`16/18/3`, Prime maker `34/43/10`, shadow maker `34/34/10`, and high-tail
maker `32/38/10`, but closed counts again did not advance from the prior
checkpoint. All four rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `110/110/108` with `+19.04%` ROI, and Brownian maker
is `131/131/113` with `+15.93%` ROI. The FV rows remain review-only under
ADR-139 because the concentration/fillability block is unchanged.

**Progress 2026-05-16 01:31 UTC:** Bot G maker closed counts advanced to
live-maker `18/22/11`, Prime maker `37/51/21`, shadow maker `37/41/21`, and
high-tail maker `35/43/21`. All rows remain below `n>=50`, so S6 remains
WAIT. The resolved Bot G maker sample is now weak for three of four rows:
Prime, shadow, and high-tail are negative ROI, while live-maker remains
positive but only has 11 closed rows. FV probability-gap maker is `115/115/109`
with `+18.87%` ROI, and Brownian maker is `137/137/132` with `+18.82%` ROI.
The FV rows remain review-only under ADR-139 because the concentration/
fillability block is unchanged.

**Progress 2026-05-16 01:46 UTC:** Bot G maker order/fill counts advanced to
live-maker `19/23/11`, Prime maker `38/52/21`, shadow maker `37/41/21`, and
high-tail maker `38/46/21`, but closed counts did not advance. All rows remain
below `n>=50`, so S6 remains WAIT, and three of four Bot G maker rows still
have negative ROI on the resolved sample. FV probability-gap maker is
`119/119/109` with `+18.24%` ROI, and Brownian maker is `141/141/132` with
`+18.29%` ROI. The FV rows remain review-only under ADR-139 because the
concentration/fillability block is unchanged.

**Progress 2026-05-16 02:01 UTC:** Bot G maker order/fill counts advanced to
live-maker `21/25/11`, Prime maker `38/52/21`, shadow maker `37/41/21`, and
high-tail maker `42/51/21`, but closed counts did not advance. All rows remain
below `n>=50`, so S6 remains WAIT, and three of four Bot G maker rows still
have negative ROI on the resolved sample. FV probability-gap maker is
`122/122/119` with `+17.67%` ROI, and Brownian maker is `147/147/132` with
`+17.54%` ROI. The FV rows remain review-only under ADR-139 because the
concentration/fillability block is unchanged.

**Progress 2026-05-16 02:16 UTC:** Bot G maker order/fill counts advanced to
live-maker `23/27/11`, Prime maker `38/52/21`, shadow maker `37/41/21`, and
high-tail maker `46/54/21`, but closed counts did not advance. All rows remain
below `n>=50`, so S6 remains WAIT, and three of four Bot G maker rows still
have negative ROI on the resolved sample. FV probability-gap maker is
`125/125/119` with `+17.24%` ROI, and Brownian maker is `151/151/132` with
`+17.08%` ROI. The FV rows remain review-only under ADR-139 because the
concentration/fillability block is unchanged.

**Progress 2026-05-16 02:31 UTC:** Bot G maker closed counts advanced to
live-maker `25/30/18`, Prime maker `38/52/25`, shadow maker `37/41/24`, and
high-tail maker `48/56/31`. All rows remain below `n>=50`, so S6 remains WAIT.
Live-maker and high-tail are positive ROI, while Prime and shadow remain
deeply negative. FV probability-gap maker is `132/132/119` with `+16.33%` ROI,
and Brownian maker is `157/157/151` with `+20.43%` ROI. The FV rows remain
review-only under ADR-139 because the concentration/fillability block is
unchanged.

**Progress 2026-05-16 02:46 UTC:** Bot G live-maker advanced to `27/31/18`,
high-tail advanced to `49/56/31`, and Prime/shadow remained `38/52/25` and
`37/41/24`. All rows remain below `n>=50`, so S6 remains WAIT. Live-maker and
high-tail are positive ROI, while Prime and shadow remain deeply negative. FV
probability-gap maker is `134/134/119` with `+16.08%` ROI, and Brownian maker
is `161/161/151` with `+19.92%` ROI. The FV rows remain review-only under
ADR-139 because the concentration/fillability block is unchanged.

**Progress 2026-05-16 03:01 UTC:** Bot G high-tail maker advanced to
`51/58/31`; live-maker, Prime maker, and shadow maker remained `27/31/18`,
`38/52/25`, and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains
WAIT. FV probability-gap maker is `137/137/133` with `+19.12%` comparator ROI,
and Brownian maker is `166/166/151` with `+19.32%` comparator ROI. The
refreshed closed-row robustness check still does not clear ADR-139:
probability-gap rows are BTC `105/133`, 5m `122/133`, and 120s-300s
`121/133`; Brownian rows are BTC `109/151`, 5m `137/151`, and 120s-300s
`136/151`. FV remains review-only until concentration and real fillability
evidence improve or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 03:16 UTC:** Bot G rows were unchanged from 03:01 UTC
and remain below `n>=50`, so S6 remains WAIT. FV probability-gap maker is
`141/141/133` with `+18.58%` comparator ROI, and Brownian maker is
`169/169/165` with `+22.20%` comparator ROI. The refreshed closed-row
robustness check still does not clear ADR-139: probability-gap rows are BTC
`105/133`, 5m `122/133`, and 120s-300s `121/133`; Brownian rows are BTC
`120/167`, 5m `150/167`, and 120s-300s `147/167`. FV remains review-only until
concentration and real fillability evidence improve or a narrower explicit ADR
scope is accepted.

**Progress 2026-05-16 03:31 UTC:** Bot G live-maker advanced to `27/31/20`,
high-tail advanced to `51/58/34`, and Prime/shadow remained `38/52/25` and
`37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `147/147/133` with `+17.82%` comparator ROI, and
Brownian maker is `175/175/170` with `+20.13%` comparator ROI. The refreshed
closed-row robustness check still does not clear ADR-139: probability-gap rows
are BTC `105/133`, 5m `122/133`, and 120s-300s `121/133`; Brownian rows are
BTC `123/170`, 5m `152/170`, and 120s-300s `149/170`. FV remains review-only
until concentration and real fillability evidence improve or a narrower
explicit ADR scope is accepted.

**Progress 2026-05-16 03:46 UTC:** Bot G high-tail advanced to `56/62/34`;
live-maker, Prime maker, and shadow maker remained `27/31/20`, `38/52/25`,
and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `151/151/148` with `+16.50%` comparator ROI, and
Brownian maker is `181/181/170` with `+19.46%` comparator ROI. The refreshed
post-report closed-row robustness check still does not clear ADR-139:
probability-gap rows are BTC `119/150`, 5m `137/150`, and 120s-300s `135/150`;
Brownian rows are BTC `123/170`, 5m `152/170`, and 120s-300s `149/170`. FV
remains review-only until concentration and real fillability evidence improve
or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 04:01 UTC:** Bot G high-tail advanced to `59/67/34`;
live-maker, Prime maker, and shadow maker remained `27/31/20`, `38/52/25`,
and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `154/154/152` with `+16.29%` comparator ROI, and
Brownian maker is `185/185/170` with `+19.04%` comparator ROI. The refreshed
closed-row robustness check still does not clear ADR-139: probability-gap rows
are BTC `120/152`, 5m `138/152`, and 120s-300s `136/152`; Brownian rows are
BTC `123/170`, 5m `152/170`, and 120s-300s `149/170`. FV remains review-only
until concentration and real fillability evidence improve or a narrower
explicit ADR scope is accepted.

**Progress 2026-05-16 04:16 UTC:** Bot G high-tail advanced to `62/71/34`;
live-maker, Prime maker, and shadow maker remained `27/31/20`, `38/52/25`,
and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `157/157/152` with `+15.98%` comparator ROI, and
Brownian maker is `189/189/170` with `+18.64%` comparator ROI. The refreshed
post-report closed-row robustness check still does not clear ADR-139:
probability-gap rows are BTC `124/156`, 5m `142/156`, and 120s-300s `139/156`;
Brownian rows are BTC `123/170`, 5m `152/170`, and 120s-300s `149/170`. FV
remains review-only until concentration and real fillability evidence improve
or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 04:31 UTC:** Bot G high-tail advanced to `65/79/41`;
live-maker, Prime maker, and shadow maker remained `27/31/20`, `38/52/25`,
and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `163/163/156` with `+15.45%` comparator ROI, and
Brownian maker is `196/196/191` with `+17.83%` comparator ROI. The refreshed
post-report closed-row robustness check still does not clear ADR-139:
probability-gap rows are BTC `126/158`, 5m `143/158`, and 120s-300s `139/158`;
Brownian rows are BTC `138/191`, 5m `169/191`, and 120s-300s `164/191`. FV
remains review-only until concentration and real fillability evidence improve
or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 04:46 UTC:** Bot G high-tail advanced to `67/82/41`;
live-maker, Prime maker, and shadow maker remained `27/31/20`, `38/52/25`,
and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `166/166/156` with `+15.18%` comparator ROI, and
Brownian maker is `198/198/191` with `+17.65%` comparator ROI. No new closed FV
rows landed after the 04:31 UTC robustness refresh, so the ADR-139
concentration/fillability blockers remain unchanged.

**Progress 2026-05-16 05:01 UTC:** Bot G high-tail advanced to `68/84/41`;
live-maker, Prime maker, and shadow maker remained `27/31/20`, `38/52/25`,
and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `171/171/156` with `+14.73%` comparator ROI, and
Brownian maker is `203/203/198` with `+17.15%` comparator ROI. The refreshed
post-report closed-row robustness check still does not clear ADR-139:
probability-gap rows are BTC `132/164`, 5m `147/164`, and 120s-300s `143/164`;
Brownian rows are BTC `146/201`, 5m `176/201`, and 120s-300s `172/201`. FV
remains review-only until concentration and real fillability evidence improve
or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 05:16 UTC:** Bot G high-tail stayed at `68/84/41`;
live-maker, Prime maker, and shadow maker remained `27/31/20`, `38/52/25`,
and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains WAIT. FV
probability-gap maker is `176/176/156` with `+14.31%` comparator ROI, and
Brownian maker is `210/210/201` with `+17.24%` comparator ROI. The refreshed
post-report closed-row robustness check still does not clear ADR-139:
probability-gap rows are BTC `138/173`, 5m `154/173`, and 120s-300s `148/173`;
Brownian rows are BTC `148/205`, 5m `179/205`, and 120s-300s `174/205`. FV
remains review-only until concentration and real fillability evidence improve
or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 05:31 UTC:** Bot G high-tail advanced on closes to
`68/84/48`, but ROI compressed to `-3.56%`; live-maker, Prime maker, and shadow
maker remained `27/31/20`, `38/52/25`, and `37/41/24`. All Bot G rows remain
below `n>=50`, so S6 remains WAIT. FV probability-gap maker is `180/180/173`
with `+15.88%` comparator ROI, and Brownian maker is `215/215/210` with
`+14.94%` comparator ROI. The refreshed post-report closed-row robustness check
still does not clear ADR-139: probability-gap rows are BTC `141/176`, 5m
`156/176`, and 120s-300s `150/176`; Brownian rows are BTC `152/210`, 5m
`181/210`, and 120s-300s `177/210`. FV remains review-only until concentration
and real fillability evidence improve or a narrower explicit ADR scope is
accepted.

**Progress 2026-05-16 05:46 UTC:** Bot G high-tail stayed at `68/84/48` with
ROI `-3.56%`; live-maker, Prime maker, and shadow maker remained `27/31/20`,
`38/52/25`, and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains
WAIT. FV probability-gap maker is `184/184/173` with `+15.54%` comparator ROI,
and Brownian maker is `219/219/210` with `+14.67%` comparator ROI. No new
closed FV rows landed after the 05:31 UTC robustness refresh, so the ADR-139
concentration/fillability blockers remain unchanged.

**Progress 2026-05-16 06:01 UTC:** Bot G high-tail stayed at `68/84/48` with
ROI `-3.56%`; live-maker, Prime maker, and shadow maker remained `27/31/20`,
`38/52/25`, and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains
WAIT. FV probability-gap maker is `187/187/173` with `+15.29%` comparator ROI,
and Brownian maker is `224/224/219` with `+12.66%` comparator ROI. The
refreshed post-report closed-row robustness check still does not clear
ADR-139: probability-gap rows are BTC `138/173`, 5m `154/173`, and 120s-300s
`148/173`; Brownian rows are BTC `158/219`, 5m `189/219`, and 120s-300s
`184/219`. Brownian remains positive after ex-largest-two and 2c stress, but
the margin compressed to `+9.27%` and `+8.71%` respectively. FV remains
review-only until concentration and real fillability evidence improve or a
narrower explicit ADR scope is accepted.

**Progress 2026-05-16 06:16 UTC:** Bot G high-tail stayed at `68/84/48` with
ROI `-3.56%`; live-maker, Prime maker, and shadow maker remained `27/31/20`,
`38/52/25`, and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains
WAIT. FV probability-gap maker is `192/192/173` with `+14.89%` comparator ROI,
and Brownian maker is `229/229/219` with `+12.38%` comparator ROI. The
refreshed post-report closed-row robustness check still does not clear
ADR-139: probability-gap rows advanced to BTC `152/189`, 5m `167/189`, and
120s-300s `161/189`; Brownian rows remain BTC `158/219`, 5m `189/219`, and
120s-300s `184/219`. Probability-gap remains positive after ex-largest-two and
2c stress, but the margin compressed to `+8.72%` and `+7.54%` respectively.
FV remains review-only until concentration and real fillability evidence
improve or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 06:31 UTC:** Bot G high-tail stayed at `68/84/48` with
ROI `-3.56%`; live-maker, Prime maker, and shadow maker remained `27/31/20`,
`38/52/25`, and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains
WAIT. FV probability-gap maker is `196/196/189` with `+11.56%` comparator ROI,
and Brownian maker is `232/232/229` with `+10.72%` comparator ROI. The
post-report closed-row robustness check still does not clear ADR-139:
probability-gap rows remain BTC `152/189`, 5m `167/189`, and 120s-300s
`161/189`; Brownian rows advanced to BTC `168/230`, 5m `198/230`, and
120s-300s `192/230`. Brownian remains positive after ex-largest-two and 2c
stress, but the margin compressed to `+7.68%` and `+6.93%` respectively. FV
remains review-only until concentration and real fillability evidence improve
or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 06:46 UTC:** Bot G high-tail stayed at `68/84/48` with
ROI `-3.56%`; live-maker, Prime maker, and shadow maker remained `27/31/20`,
`38/52/25`, and `37/41/24`. All Bot G rows remain below `n>=50`, so S6 remains
WAIT. Bot I Persistence maker advanced to `40/40/40` with `+10.00%` ROI, still
below the maker `n>=50` decision gate. Cell C remains `4/4/4` with `-22.08%`
ROI, below S7. FV probability-gap maker is `200/200/189` with `+11.33%`
comparator ROI, and Brownian maker is `237/237/230` with `+10.86%` comparator
ROI. The post-report closed-row robustness check was unchanged from the 06:31
recompute, so FV remains review-only until concentration and real fillability
evidence improve or a narrower explicit ADR scope is accepted.

**Progress 2026-05-16 07:11 UTC:** Cell C crossed the S7 sample trigger:
`bot_i_cell_c_maker` is `69/69/69` with `-0.90%` ROI and `$-0.60` net P&L.
That is borderline under Z5, so the goal's live path would be the `$1/trade`
probe rather than the `$5/trade` packet. ADR-176 records that the `$1/trade`
probe is currently H6-blocked because the exchange 5-share minimum requires
roughly `$4.75-$4.95` notional in the 95-99c Cell C band. No Cell C live
service was deployed, no Bot I live executor was switched, and no live order
was authorized.

**Progress 2026-05-16 07:20 UTC:** FV probability-gap maker advanced to
`207/207/203` with `+10.54%` comparator ROI, and Brownian maker advanced to
`245/245/230` with `+10.50%` comparator ROI. The refreshed closed-row
robustness still does not clear ADR-139: probability-gap remains BTC
`164/203`, 5m `179/203`, and 120s-300s `173/203`; Brownian remains BTC
`168/230`, 5m `198/230`, and 120s-300s `192/230`. FV remains review-only
until concentration and real fillability evidence improve or a narrower
explicit ADR scope is accepted.

**Progress 2026-05-16 07:35 UTC:** FV Brownian maker advanced to
`249/249/246` with `+14.45%` comparator ROI, while probability-gap maker
advanced to `210/210/203` with `+10.39%` comparator ROI. The refreshed
closed-row robustness still does not clear ADR-139: probability-gap remains
BTC `164/203`, 5m `179/203`, and 120s-300s `173/203`; Brownian is now BTC
`183/246`, 5m `210/246`, and 120s-300s `205/246`. FV remains review-only
until concentration and real fillability evidence improve or a narrower
explicit ADR scope is accepted.

**Progress 2026-05-16 07:50 UTC:** FV probability-gap maker advanced to
`212/212/203` with `+10.29%` comparator ROI, and Brownian maker advanced to
`252/252/246` with `+14.28%` comparator ROI. These were unclosed fill-count
advances only, so the closed-row ADR-139 concentration/fillability blockers
remain unchanged from 07:35.

### OQ-118 — Cell C borderline maker probe exchange-minimum cap decision (the operator)

**Owner:** the operator.
**Surfaced by:** 2026-05-16 Session 432 maker S7 Cell C H6 block.

**Problem:** The Cell C maker candidate reached the S7 sample gate at
`69/69/69` with `-0.90%` ROI. The maker-conversion goal's Z5 rule maps that
borderline result to a `$1/trade` live probe. The Cell C 95-99c price band is
not executable at `$1/trade` under the exchange 5-share minimum: a valid BUY
requires about `$4.75-$4.95` notional. The current live Bot I helper clamps
shares up to `MIN_POLYMARKET_SHARES=5`, so starting a nominal `$1` live probe
would silently create near-`$5` exposure and breach H6.

**Acceptance criteria:**

1. the operator explicitly chooses one of:
   - raise the Cell C borderline probe cap to the minimum executable notional
     for 95-99c markets, approximately `$5/trade`, with daily/open caps named;
   - reject/defer Cell C live despite the borderline maker sample;
   - change the Cell C live price band to one that can satisfy the `$1/trade`
     cap without breaching the exchange minimum.
2. If raised, a new superseding ADR names the exact per-trade cap, daily gross
   cap, open-exposure cap, kill date, service unit, and post-start monitoring.
3. Until that ADR exists, `bot_i_cell_c_maker` remains paper-only and the Bot I
   live taker executor remains unchanged.

**Current state 2026-05-16 07:11 UTC:** ADR-176 accepted the borderline Cell C
decision but blocks deployment on H6. No live Cell C service exists, no live
order was placed, and S5/S6 monitoring continues for the rest of the maker
conversion goal.

### OQ-119 — Dashboard live accounting and per-bot ROI truth surface (Codex)

**Owner:** Codex.
**Surfaced by:** 2026-05-16 Session 435 profitability/ROI goal handoff.

**Problem:** the operator can see live trades in the Polymarket account but the the bot container
dashboard does not reliably show per-bot live P&L. Read-only inspection found
that local source expects `/api/overview` to include `bot_inventory`, but the
deployed the bot container `dashboard.runtime_queries.query_overview()` returned no
`bot_inventory` key at 2026-05-16 07:44 UTC. Older `fleet_bots` rows can also
mix realised P&L with open exposure semantics. Example: `_trade_metrics()`
correctly reports `bot_d_maker_live_probe` at `$0.00` realised P&L with
`15` BUY fills and about `$20.53` open exposure, while older overview rows can
make the open cost look like negative P&L.

**Acceptance criteria:**

1. the bot container `/api/overview` exposes an active inventory/live-accounting table for
   every active live bot, sourced from the canonical bot registry where
   possible.
2. Each live row separately shows realised P&L, open exposure/cost basis,
   open order notional, open positions, fill count, closed count, and last fill
   timestamp.
3. Open BUY cost is never displayed as realised loss until a position is
   closed or resolved.
4. `bot_d_maker_live_probe` has a regression test proving `$0.00` realised
   P&L with non-zero open exposure when it only has BUY fills.
5. Dashboard deployment to the bot container is done only with explicit approval for
   `polymarket-dashboard.service` restart; no bot services or live order paths
   are touched.

**Current state 2026-05-16 07:49 UTC:** Handoff written in
`docs/codex-profitability-roi-goal-2026-05-16.md`. No dashboard patch or the bot container
restart has been performed in this closeout session.

### OQ-120 — Crypto FV maker tiny-live activation approval (the operator)

**Owner:** the operator.
**Status:** Resolved 2026-05-16 by the operator approval and ADR-178 activation.
**Surfaced by:** 2026-05-16 Session 436 crypto FV maker tiny-live preparation.

**Problem:** Probability-gap maker and Brownian FV maker paper shadows now have
enough positive early evidence to justify preparing a capped live probe, but
ADR-139 still blocks a silent full promotion and the evidence window is only
about 20 hours. ADR-177 prepared separate blocked-by-default live-maker paths
and systemd units, but no activation has been approved.

**Acceptance criteria:**

1. the operator explicitly approves or rejects activation of one or both FV maker
   tiny-live probes.
2. If approved, the approval names exact caps. The prepared history-derived
   packet is:
   probability-gap `$5` max order, `$250` daily gross, `$100` open exposure,
   `20` max concurrent positions; Brownian `$5` max order, `$300` daily gross,
   `$120` open exposure, `24` max concurrent positions; both lanes use `90s`
   stale quote cancellation.
3. Activation starts one lane first, verifies known-order accounting and first
   scan telemetry, then starts the second lane only after the first lane is
   healthy.
4. Any activation/deployment records the the bot container service state, first order/event
   evidence, and rollback status in `CHANGELOG.md` and `MEMORY.md`.

**Current state 2026-05-16 13:15 UTC:** the operator approved both FV maker tiny-live
services. `polymarket-crypto-prob-gap-live-maker.service` and
`polymarket-crypto-brownian-fv-live-maker.service` were deployed and started
on the bot container with the ADR-177 caps. Activation monitor
`polymarket-crypto-fv-live-monitor-20260516.service` is running and writing
`data/reports/crypto_fv_live_monitor/activation-20260516T1306Z.jsonl`.
Initial live fills confirmed known-order accounting and small open exposure.
Two early SQLite lock restarts occurred during fill reconciliation; ADR-178
records the mitigation: SQLite `busy_timeout` plus staggered scan intervals
of `9s` probability-gap and `13s` Brownian. Post-mitigation check through
13:15 UTC showed both services active with no new traceback.

### OQ-121 — Redeemer should return or immediately wrap to pUSD (Codex)

**Owner:** Codex.
**Surfaced by:** 2026-05-16 Session 436 USDC.e -> pUSD wallet conversion.

**Problem:** Polymarket V2 docs state that redeeming winning tokens should
return pUSD through the adapter flow. The repo's current
`scripts/redeem_resolved_positions.py` standard path calls the lower-level CTF
`redeemPositions(collateralToken, zeroParent, conditionId, [1, 2])` directly.
For legacy positions whose collateral is USDC.e, that direct path can leave the
wallet with USDC.e after redemption. the operator observed this in the wallet. The
operational workaround is to run `scripts/wrap_usdce_to_pusd.py --all`, which
was executed successfully on 2026-05-16 for `132.251160` USDC.e.

**Acceptance criteria:**

1. Decide whether the standard redeemer should switch to the Polymarket V2
   adapter path where possible, or keep direct CTF redeem and automatically
   wrap any USDC.e balance delta into pUSD after successful redemption.
2. Add a dry-run-first test that proves a USDC.e-collateral winner redemption
   leaves the wallet with no residual USDC.e when the wrap flag/default is
   enabled.
3. Preserve the existing safety gates for broad winner redemption:
   condition-id gates, max-candidate caps, gas caps, and explicit `--execute
   --yes`.
4. Document the final behavior in the redemption runbook and changelog before
   enabling any unattended winner redemption.

**Current state 2026-05-16:** Manual wrap completed with tx
`90d266b35719d3c68cebc6dc35f4bbf44a55f1c8e379d085b3f9f26722bc4606`, block
`86966531`; follow-up check showed `0.000000` USDC.e and `336.739737` pUSD.

**Current state 2026-05-16 20:18 UTC:** the operator reported the wallet had run out
of pUSD while holding `136.965771` USDC.e. the bot container dry run confirmed the USDC.e
balance and sufficient onramp allowance. Executed the approved wrap in tx
`865e6fda428f5cbef18028daa6c2510a0267abcd7986ca72d48c7ce0424fb1c3`, block
`86984549`; immediate post-wrap pUSD was `139.917852`. Added and enabled
`polymarket-wrap-usdce-to-pusd.timer` per ADR-180; it runs every `5` minutes
and exits cleanly on zero USDC.e. This resolves the operational workaround
portion of OQ-121, but the redeemer itself still needs a code-level decision:
adapter redeem versus direct CTF redeem plus automatic post-redeem wrap.

### OQ-123 — Wallet Data API backfill and cross-DB ownership reconciliation (Claude)

**Category:** Blocking / Research-required.
**Owner:** Claude.
**Status:** Open.
**Created:** 2026-05-17.
**Surfaced by:** Session 447 Bot I live stop and wallet-accounting gap.

**Problem:** The hot wallet now has real trades/redeems that are not fully
represented in the shared `data/main.db`. FV live rows exist in `main.db`, but
Bot I live writes to `data/persistence_live.db`; Bot I's local P&L logic also
misclassified several redeemed winners as losses. Current wallet Data API open
positions include weather rows that do not match `main.db` or Bot D journaled
placements. The dashboard cannot be treated as whole-wallet P&L until every
wallet activity row is owned, reconciled, or explicitly marked unowned.

**Acceptance criteria:**

1. Build or run a wallet Data API backfill that pulls every hot-wallet buy,
   sell, redeem, and rebate row for the affected 2026-05-16/2026-05-17 window.
2. Classify each row into one of: `main.db` known bot, Bot I
   `persistence_live.db`, manual/unowned, rebate, redemption-only, or ignored
   with reason.
3. Produce a report with per-bot wallet-level P&L/ROI, current open exposure,
   and a list of unowned positions/trades.
4. Repair Bot I accounting so redeemed winners are not booked as losses before
   any Bot I restart is considered.
5. Add or update the dashboard accounting surface so live wallet activity not
   found in `main.db` is visible rather than silently omitted.

**Current state 2026-05-18 (Grok overnight implementation complete):**
- Canonical `scripts/wallet_data_api_backfill.py` (with WalletDataApiClient / ReconciliationClassifier / Reporter per SPEC) + full tests in `tests/test_wallet_data_api_backfill.py` + fixtures. Re-uses hardened dry-run fetch logic; always --dry-run default, execute path refuses without env confirm. `/activity` already authoritative.
- `tests/test_wallet_reconcile_dryrun.py` + persistence guard test cover classifier, end-to-end fixture dry-run, execute refusal, dashboard accounting/freshness fields.
- Dashboard `runtime_queries.py` extended: per-inventory `reconciliation_status`/`wallet_realised_pnl_usd`/`unresolved_exposure_usd`/`freshness` (via reusable `_freshness_for_live_row`), top-level accounting with run_at/unresolved/fully_reconciled. Explicit "local-only" labels + stale_7d/30d for live rows (G-prime triggers).
- `core/db.py` + Alembic migration skeleton for `wallet_reconciliations` table.
- Bot I guard in persistence_paper_run.py is narrow (--live-bot-i-report flag only); paper runs unaffected. Test proves exit 0 on paused.
- Maker paper experiments doc + profitability ranking (D live +31.06 first) updated with backfill prerequisite.
- ADR-182 recorded the dry-run-first decision. OQ-123 unblocks on operator review of real the bot container dry-run report + gated deploy of the additive changes.
- All work local/read-only the bot container queries; no live orders, no --execute, no service restarts, no data deletion.

**Next for OQ-123:** Operator: (1) run `ssh hypervisor-host 'pct exec <ctid> -- python -m scripts.wallet_data_api_backfill --wallet 0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA --since 2026-05-16 --json'` (read-only), (2) review unowned/stale output, (3) if clean: gated deploy of runtime_queries + backfill + db model to the bot container, (4) after table backfilled, update OQ to closed. No restart of paused lanes until report reviewed + new ADR.

**Progress 2026-06-07 (Grok Build Session 466, P1):** Tooling audit (backfill.py:261-301 parser --main-db/--persistence-db/--bots/--wallet/--since/--json/--dry-run default/--execute gated behind WALLET_BACKFILL_CONFIRM + no-write this run; 56-109 WalletDataApiClient public /positions /trades /activity httpx no auth; 111-183 ReconciliationClassifier token_id/condition match to load_local_open + persistence_live_entries, heuristic bot_id, status=owned/unowned/rebate/reconciliation_only; 186-249 Reporter summary wallet_current_positions/trades/activity/local_open/owned/unowned/activity_by_type/zero_value_redeems/rebate_events + samples + recommendation). Empirical dry: .venv/bin/python -m ... --json (net "Connection reset by peer" on fetches -> 0s summary, "dry_run_complete", INFO no DB writes/no CLOB; exit 0); --use-fixtures (classified 4, unowned samples with raw). Reconcile base shares logic. Gaps vs canonical (OQ-123/ADR-182): cross-DB recon incomplete (no full token->bot map in classify; unowned rows need review; heuristic bot_id); residual exposure vs OQ-124. Dashboard /api/overview accounting object *is present* (since ~5/18 per ADR-182 design + subagent direct read) at runtime_queries.py:2972-2982 (verbatim excerpt: `"accounting": { "wallet_reconciliation_run_at": None, "wallet_reconciliation_status": "OQ-123 pending — local DB(s) only until wallet_data_api_backfill.py dry-run is reviewed and backfill table populated. Run scripts/wallet_data_api_backfill.py --dry-run (read-only) for authoritative gap report.", "persistence_live_db_separate": True, "main_db_is_not_whole_wallet": True, "total_unresolved_usd": 0.0, "fully_reconciled_bots": 0, "reconciliation_note": "per-row fields now include reconciliation_status / wallet_realised_pnl_usd / freshness (local_only until OQ-123 write path approved)" }`; per-row at 1732-1743: `row.update({ "reconciliation_status": "local_only", "wallet_realised_pnl_usd": None, "unresolved_exposure_usd": ..., "reconciliation_note": "local bot-ledger; run wallet_data_api_backfill.py for wallet-reconciled view" })` with comment "Reconciliation surface (OQ-123 phase 2) — local DB only until backfill table is written."). Current values are pending/null/local_only (as designed until table populated + review + write path). Gaps remain: prod the bot container dry-run review + backfill table pop (write gated), queries join to surface real values (not yet), heuristic classify. Matches subagent "present" + "accounting key present: True" + "Dashboard truth surface: present (accounting object in query_overview:2972". No extension (smallest; read-only/dry only, no risk path). Subagent oq123-investigate referenced (report /tmp/oq123-progress-audit-20260603.md; reconciled its internal present/lacks in this fix pass). OQ-123 **Blocking / Research-required** (owner Claude); measurable forward: confirmed tooling shape + dry path + report + accurate surface status; update after host dry report review + new ADR. Cross OQ-124/125. Pins: backfill.py:140 (classify_row), 291 (execute guard), runtime_queries.py:2972-2982 (accounting verbatim), 1732-1743 (per-row), 85 (_freshness), ADR-182. (Corrected 2026-06-07 post-review; was stale "lacks" + wrong 65-69 cite pre-fix.)

### OQ-124 — Live fleet residual exposure closeout and restart gate (Claude/the operator)

**Category:** Blocking / Decision-required.
**Owner:** Claude/the operator.
**Status:** Open.
**Created:** 2026-05-19.
**Surfaced by:** ADR-183 full live-service halt.

**Problem:** All live services are stopped and disabled, and both live wallets
show `0` exchange-resting CLOB orders. However, local ledgers still show
residual open positions from live lanes, especially Bot D maker/FV on the bot container
and Bot D-Spike/Bot L on the VPS. Those positions need a clean closeout policy
before any live restart, otherwise the dashboard can mix old exposure with a
future probe.

**Acceptance criteria:**

1. Produce a wallet-level residual exposure report from Data API `/positions`,
   `/closed-positions`, `/activity`, and local `main.db`/`persistence_live.db`.
2. Classify each open/residual row as redeemable, unresolved, stale-local-only,
   or manual/unowned.
3. Decide whether each residual row should be held to resolution, redeemed,
   manually sold, or locally marked stale.
4. Confirm dashboard live rows display paused/inactive status, residual
   exposure, and legacy P&L without implying active live trading.
5. Require a new ADR and explicit the operator approval before any live service is
   re-enabled.

**Current state 2026-05-19:** Live service units and wallet-action timers were
stopped/disabled on the bot container and the VPS. Halt flags were set with
`operator_halt_2026-05-19_all_live_services_off`. Both the bot container and VPS
emergency cancel-all dry runs reported `no live orders on the wallet`.

### OQ-125 — QuantStats orphan-sell fee accounting and canonical-total parity on real ledgers (Grok/the operator)

**Category:** Research-required / Decision-required (operator data).
**Owner:** the operator (run on the bot container/VPS ledgers) / Grok (code fix once counts known).
**Status:** Open.
**Created:** 2026-05-24.

**Progress 2026-06-07 (Grok Build Session 466):** Low-risk audit note from 460 (orphan-sell fee vs portfolio.get_realised_pnl on gaps; missing regression on shared seed). No ledger run (local dev main 0 rows; no prod). OQ-125 **Research-required / Decision-required** (owner the operator/Grok). Cross ADR-184, OQ-123. No code.
**Surfaced by:** Session 460 ADR-184 Grok Build audit.

**Problem:** The quantstats_bot_tearsheet adapter's trade FIFO matches portfolio.get_realised_pnl lot semantics and dashboard _trade_metrics (same BUY_/SELL_ normalisation, same redeem add, same closed-only realised). However:
- Orphan sell fees (unmatched SELL rows from historical reconcile gaps) are dropped in the adapter's per-event PnL (no subtraction) while portfolio subtracts every trade fee globally. On any bot with orphan_sells>0 this causes script total_realised_pnl_usd and period returns to overstate vs canonical.
- No test asserts that for a non-orphan seed the script's aggregated realised_pnl + trade_level_roi exactly equals what portfolio.get_realised_pnl + manual cost sum would yield.
- Operator has not yet run the script (with --capital-base-usd explicit) against current active bot ledgers to report orphan_sells counts, whether totals match existing ROI reports, and whether the capital fallback is ever used.

**Acceptance criteria:**
1. Operator runs `python scripts/quantstats_bot_tearsheet.py --bot-id <active> --db /path/to/prod/main.db --out-dir /tmp/qs-audit --capital-base-usd <wallet> --period daily` (read-only) on the bot container and VPS for Bot D, Bot G probes, etc. and reports the "diagnostics"."orphan_sells" and "total_realised_pnl_usd" vs dashboard/portfolio numbers for same window.
2. If orphan_sells==0 on all active, P2 risk is latent only; close OQ.
3. If >0, apply the exact fix from Session 460 P2 (track/subtract orphan sell fees; add match-to-portfolio regression test).
4. Confirm no redeem+trade double-count on same capital in prod data for the same token/condition.

**Current state 2026-05-24:** Audit used only synthetic toy DBs (never workspace or prod data/main.db). All 10 audit questions answered yes except the orphan edge (P2) and test coverage (P3). Real-QuantStats path verified in isolated uv env on toy data. Recommend fix before using on any ledger that may have pre-2026-05 reconcile gaps. OQ blocks production reliance on the adapter for capital decisions until counts known and (if needed) code updated.
