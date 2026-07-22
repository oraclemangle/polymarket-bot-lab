# Decisions Log — ADR Format

Material decisions in this project. Each ADR is immutable once accepted; if a decision is reversed or superseded, a new ADR records the change and the old one's status updates. Do not edit an accepted ADR's Decision or Rationale sections retrospectively.

ADRs are numbered in order of acceptance.

---

<!-- ADR-INDEX:BEGIN -->
## ADR Index

_192 ADRs total: 185 active, 7 superseded, 0 reversed, 0 other. Newest first; ADRs are immutable, status updates only. (Index count after ADR-191..194; body also holds ADR-189/190 from prior sessions.)_

### Superseded / reversed (historical)

| ADR | Title | Status |
|---|---|---|
| [ADR-004](#adr-004-oraclemangle-is-ported-not-consumed) | Oraclemangle is ported, not consumed | superseded by ADR-015 |
| [ADR-030](#adr-030-bot-e-archived-spread-capture-poc-decisively-failed) | Bot E archived — spread-capture POC decisively failed | superseded by ADR-037 (2026-04-22) |
| [ADR-056](#adr-056-kronos-can-be-evaluated-for-bot-e-only-as-an-offline-shadow-feature) | Kronos can be evaluated for Bot E only as an offline shadow feature | superseded by ADR-057 |
| [ADR-064](#adr-064-profitability-path-is-a-contrarian-edge-tournament-not-all-bot-loosening) | Profitability path is a contrarian edge tournament, not all-bot loosening | superseded by ADR-065 |
| [ADR-076](#adr-076-bot-g-first-live-wallet-is-200-with-fixed-5-entries) | Bot G first live wallet is $200 with fixed $5 entries | superseded by ADR-077 |
| [ADR-077](#adr-077-bot-g-tiny-live-cap-packet-uses-100-daily-gross-and-10-max-open) | Bot G tiny-live cap packet uses $100 daily gross and 10 max open | superseded by ADR-078 |
| [ADR-113](#adr-113-do-not-move-bot-g-live-order-placement-to-vps-for-geographic-bypass) | Do not move Bot G live order placement to VPS for geographic bypass | superseded by ADR-115 (2026-05-06, same day) |

### Active by domain

#### Bot D (weather) (46)

- **[ADR-179](#adr-179-add-bot-d-ensemble-ladder-as-a-paper-only-adjacent-yes-basket-lane)** — Add Bot D Ensemble Ladder as a paper-only adjacent YES basket lane
- **[ADR-175](#adr-175-block-endednear-ended-bot-d-weather-entries-and-cap-cheap-late-maker-yes-quotes)** — Block ended/near-ended Bot D weather entries and cap cheap late maker YES quotes
- **[ADR-174](#adr-174-add-bot-d-maker-live-probe-under-a-separate-capped-ledger)** — Add Bot D maker live probe under a separate capped ledger
- **[ADR-169](#adr-169-promote-beijing-zbaa-into-bot-d-verified-weather-coverage)** — Promote Beijing ZBAA into Bot D verified weather coverage
- **[ADR-167](#adr-167-promote-austin-kaus-and-align-bot-d-nws-outlier-probe-with-live-edge-floor)** — Promote Austin KAUS and align Bot D NWS-outlier probe with live edge floor
- **[ADR-166](#adr-166-add-bot-d-report-only-live-position-validation-with-raw-station-exit-signals)** — Add Bot D report-only live-position validation with raw station exit signals
- **[ADR-162](#adr-162-bot-d-live-scale-up--premium-tier-no-sizing--distance-gate-restore)** — Bot D live scale-up + premium-tier NO sizing + distance-gate restore
- **[ADR-160](#adr-160-add-bot-d-station-lock-as-a-paper-only-late-station-certainty-lane)** — Add Bot D Station Lock as a paper-only late station-certainty lane
- **[ADR-158](#adr-158-raise-bot-d-live-capacity-and-replace-expensive-no-distance-with-tieredge-gate)** — Raise Bot D live capacity and replace expensive-NO distance with tier/edge gate
- **[ADR-156](#adr-156-bot-d-blocks-high-confidence-no-when-the-forecast-mean-is-inside-the-yes-bucket)** — Bot D blocks high-confidence NO when the forecast mean is inside the YES bucket
- **[ADR-154](#adr-154-bot-d-live-order-hygiene--block-invalid-forecast-values-and-exchange-subfloor-orders)** — Bot D live order hygiene — block invalid forecast values and exchange-subfloor orders
- **[ADR-148](#adr-148-add-bot-d-cheap-yes-collection-lane-and-remove-internal-live-min-notional-gate)** — Add Bot D cheap-YES collection lane and remove internal live min-notional gate
- **[ADR-147](#adr-147-move-bot-d-live-probe-from-fixed-five-share-sizing-to-an-evidence-gated-ladder)** — Move Bot D live probe from fixed five-share sizing to an evidence-gated ladder
- **[ADR-131](#adr-131-automate-bot-d-zero-value-negative-risk-redemption-cleanup)** — Automate Bot D zero-value negative-risk redemption cleanup
- **[ADR-129](#adr-129-block-expensive-bot-d-no-entries-without-source-agreement-and-large-bucket-distance)** — Block expensive Bot D NO entries without source agreement and large bucket distance
- **[ADR-127](#adr-127-tune-bot-d-spike-to-validation-plus-paper-settings-after-first-day-capacity-check)** — Tune Bot D-Spike to validation-plus paper settings after first-day capacity check
- **[ADR-120](#adr-120-split-bot-d-into-archived-longshot-fade-paper-and-live-range-fade-live_probe-push-kill-date)** — Split Bot D into archived longshot-fade (paper) and live range-fade (live_probe); push kill date
- **[ADR-114](#adr-114-keep-bot-d-paper-shadow-aligned-with-tiny-live-data-settings)** — Keep Bot D paper shadow aligned with tiny-live data settings
- **[ADR-107](#adr-107-add-bot-d-nws-outlier-probe-using-api-agreement)** — Add Bot D NWS-outlier probe using API agreement
- **[ADR-105](#adr-105-add-gribstream-nbm-shortcut-and-99c-take-profit-to-bot-d-tiny-live)** — Add GribStream NBM shortcut and 99c take-profit to Bot D tiny-live
- **[ADR-104](#adr-104-park-little-rocky-5-model-dispersion-migration-until-bot-d-has-resolved-position-evidence)** — Park little-rocky 5-model dispersion migration until Bot D has resolved-position evidence
- **[ADR-103](#adr-103-add-noaa-nbm-station-guidance-as-bot-ds-first-open-meteo-bypass)** — Add NOAA NBM station guidance as Bot D's first Open-Meteo bypass
- **[ADR-102](#adr-102-raise-bot-d-tiny-live-collection-caps-while-keeping-per-order-size-fixed)** — Raise Bot D tiny-live collection caps while keeping per-order size fixed
- **[ADR-100](#adr-100-pay-up-slightly-for-bot-d-tiny-live-fills)** — Pay up slightly for Bot D tiny-live fills
- **[ADR-099](#adr-099-add-bot-d-settlement-source-telemetry-before-trading-on-late-certainty)** — Add Bot D settlement-source telemetry before trading on late certainty
- **[ADR-097](#adr-097-loosen-bot-d-tiny-live-entry-collection-without-increasing-trade-size)** — Loosen Bot D tiny-live entry collection without increasing trade size
- **[ADR-095](#adr-095-loosen-bot-d-tiny-live-plumbing-enough-to-collect-real-fills)** — Loosen Bot D tiny-live plumbing enough to collect real fills
- **[ADR-091](#adr-091-bot-d-live-nws-veto-floor-is-loosened-to-3f-with-shadow-counters)** — Bot D live NWS veto floor is loosened to 3F with shadow counters
- **[ADR-090](#adr-090-bot-d-live-reconciliation-ignores-fills-without-a-known-bot-d-order)** — Bot D live reconciliation ignores fills without a known Bot D order
- **[ADR-087](#adr-087-bot-d-live-probe-activated-at-minimum-size)** — Bot D live probe activated at minimum size
- **[ADR-086](#adr-086-bot-d-live-probe-activation-requires-audit-hardening)** — Bot D live-probe activation requires audit hardening
- **[ADR-084](#adr-084-bot-d-gets-a-separate-tiny-live-plumbing-probe)** — Bot D gets a separate tiny-live plumbing probe
- **[ADR-082](#adr-082-bot-d-live-readiness-blockers-are-enforced-at-runtime)** — Bot D live-readiness blockers are enforced at runtime
- **[ADR-080](#adr-080-bot-d-live-candidate-paper-entries-require-wave-plus-depth-proof)** — Bot D live-candidate paper entries require wave plus depth proof
- **[ADR-079](#adr-079-bot-d-paper-collection-is-live-shaped-only)** — Bot D paper collection is live-shaped only
- **[ADR-070](#adr-070-bot-g-is-co-priority-with-bot-d-but-must-be-v2-fee-aware)** — Bot G is co-priority with Bot D but must be V2-fee-aware
- **[ADR-069](#adr-069-bot-d-first-wallet-proof-is-daily-only-until-resolved-pl-clears)** — Bot D first-wallet proof is daily-only until resolved P&L clears
- **[ADR-068](#adr-068-bot-d-live-readiness-must-be-dashboard-visible-before-wallet-work)** — Bot D live-readiness must be dashboard-visible before wallet work
- **[ADR-067](#adr-067-bot-d-stays-real-wallet-priority-while-fast-roi-reporting-leads-tuning)** — Bot D stays real-wallet priority while fast-ROI reporting leads tuning
- **[ADR-060](#adr-060-bot-dg-get-paper-only-trade-flow-probes)** — Bot D/G get paper-only trade-flow probes
- **[ADR-053](#adr-053-bot-d-paper-pl-is-epoch-sliced-not-cleared)** — Bot D paper P&L is epoch-sliced, not cleared
- **[ADR-052](#adr-052-bot-d-uses-settlement-station-modeling-before-live-graduation)** — Bot D uses settlement-station modeling before live graduation
- **[ADR-046](#adr-046-bot-d-live-exits-must-be-real-clob-sell-orders-not-synthetic-fills)** — Bot D live exits must be real CLOB SELL orders, not synthetic fills
- **[ADR-045](#adr-045-seven-bot-deployment-posture-fix-bot-d-before-any-live-capital)** — Seven-bot deployment posture - fix Bot D before any live capital
- **[ADR-043](#adr-043-bot-d-wave-regime-sizing-instead-of-broad-isolated-tail-sizing)** — Bot D wave-regime sizing instead of broad isolated-tail sizing
- **[ADR-025](#adr-025-phase-3-adversarial-audit-remediation-emergency-halt-fee-sentinel-bot-a-two-level-exit-config-tuning-bot-d-exact-temp-blacklist-uhi-cross-bot-overlap-orphan-sell-alert-adverse-selection-guard-gap-quarantine-application-archetype-monitor)** — Phase 3 adversarial-audit remediation (emergency halt, fee sentinel, Bot A two-level exit + config tuning, Bot D exact-temp blacklist + UHI, cross-bot overlap, orphan-SELL alert, adverse-selection guard, gap-quarantine application, archetype monitor)
- **[ADR-021](#adr-021-bot-d-dual-writes-a-minimal-markets-row-on-every-order)** — Bot D dual-writes a minimal `markets` row on every order

#### Bot G (longshot) (29)

- **[ADR-150](#adr-150-archive-bot-g-live-dashboard-history-at-the-adr-149-epoch-boundary)** — Archive Bot G live dashboard history at the ADR-149 epoch boundary
- **[ADR-149](#adr-149-retune-bot-g-prime-live-to-1-65c-8c-ethsol-high-tail-probe)** — Retune Bot G Prime Live to $1 6.5c-8c ETH/SOL high-tail probe
- **[ADR-140](#adr-140-retire-bot-g-late-cheap-and-take-profit-paper-lanes-after-final-review)** — Retire Bot G late-cheap and take-profit paper lanes after final review
- **[ADR-136](#adr-136-resume-bot-g-prime-live-as-1-data-gathering-micro-probe)** — Resume Bot G Prime Live as $1 data-gathering micro-probe
- **[ADR-135](#adr-135-emergency-pause-bot-g-prime-live-after-live-shaped-cohorts-fail)** — Emergency-pause Bot G Prime Live after live-shaped cohorts fail
- **[ADR-128](#adr-128-lower-bot-g-paper-take-profit-probe-to-50c-and-keep-late-cheap-collecting)** — Lower Bot G paper take-profit probe to 50c and keep late-cheap collecting (partially superseded by ADR-140 for `bot_g_prime_late_cheap` and `bot_g_prime_take_profit`)
- **[ADR-118](#adr-118-reduce-bot-g-prime-live-per-entry-size-while-preserving-the-live-probe)** — Reduce Bot G Prime live per-entry size while preserving the live probe
- **[ADR-117](#adr-117-keep-bot-g-prime-paper-collection-running-with-a-zero-roi-floor)** — Keep Bot G Prime paper collection running with a zero ROI floor
- **[ADR-115](#adr-115-move-bot-g-live-order-placement-to-vps-with-revised-geographic-policy)** — Move Bot G live order placement to VPS, with revised geographic policy
- **[ADR-112](#adr-112-move-bot-g-paper-lanes-to-vps-on-a-dedicated-paper-ledger)** — Move Bot G paper lanes to VPS on a dedicated paper ledger
- **[ADR-101](#adr-101-prove-bot-g-take-profit-exits-in-paper-before-any-live-exit-router)** — Prove Bot G take-profit exits in paper before any live exit router
- **[ADR-098](#adr-098-add-bot-g-read-only-parameter-reports-and-paper-shadows)** — Add Bot G read-only parameter reports and paper shadows
- **[ADR-096](#adr-096-reframe-bot-e0-as-the-shared-crypto-recorder-for-bot-g-replay)** — Reframe Bot E0 as the shared crypto recorder for Bot G replay
- **[ADR-094](#adr-094-make-bot-g-prime-live-optional-labels-non-blocking-and-index-recorder-hot-paths)** — Make Bot G Prime Live optional labels non-blocking and index recorder hot paths
- **[ADR-089](#adr-089-bot-g-prime-live-scans-earlier-and-faster-while-keeping-the-fresh-clock-guard)** — Bot G Prime Live scans earlier and faster while keeping the fresh-clock guard
- **[ADR-088](#adr-088-bot-g-live-entries-require-a-fresh-pre-submit-clock-check)** — Bot G live entries require a fresh pre-submit clock check
- **[ADR-085](#adr-085-bot-g-prime-live-expands-to-35c-55c-tiny-live-band)** — Bot G Prime Live expands to 3.5c-5.5c tiny-live band
- **[ADR-083](#adr-083-bot-g-tiny-live-crosses-one-tick-for-transfer)** — Bot G tiny-live crosses one tick for transfer
- **[ADR-081](#adr-081-bot-g-records-xrpdoge-while-live-stays-btcethsol)** — Bot G records XRP/DOGE while live stays BTC/ETH/SOL
- **[ADR-078](#adr-078-activate-bot-g-prime-live-as-separate-4c-5c-tiny-live-unit)** — Activate Bot G Prime live as separate 4c-5c tiny-live unit
- **[ADR-075](#adr-075-bot-g-tiny-live-fixes-must-preserve-paper-collection-while-making-live-accounting-honest)** — Bot G tiny-live fixes must preserve paper collection while making live accounting honest
- **[ADR-074](#adr-074-bot-g-tiny-live-prep-is-reporting-only-until-explicit-approval)** — Bot G tiny-live prep is reporting-only until explicit approval
- **[ADR-073](#adr-073-bot-g-live-candidate-gate-requires-trimmed-roi-and-capacity-proof)** — Bot G live-candidate gate requires trimmed ROI and capacity proof
- **[ADR-071](#adr-071-active-fleet-revamp-promotes-longshot-prime-and-archives-bot-af-surfaces)** — Active fleet revamp promotes Longshot Prime and archives Bot A/F surfaces
- **[ADR-061](#adr-061-disable-bot-g-prime-hard-cex-confirmation-in-paper)** — Disable Bot G Prime hard CEX confirmation in paper
- **[ADR-055](#adr-055-bot-g-prime-replaces-raw-split-variants-for-paper-research)** — Bot G Prime replaces raw split variants for paper research
- **[ADR-044](#adr-044-bot-g-parallel-paper-cohorts-for-jackpot-vs-scalp-attribution)** — Bot G parallel paper cohorts for jackpot vs scalp attribution
- **[ADR-036](#adr-036-bot-longshot-fade-g-near-resolution-cheap-side-entries-on-crypto-updown)** — Bot Longshot Fade (G) — near-resolution cheap-side entries on crypto Up/Down
- **[ADR-002](#adr-002-bot-a-thesis-mechanical-longshot-fade)** — Bot A thesis — mechanical longshot fade

#### Bot B (Oraclemangle) (5)

- **[ADR-072](#adr-072-park-bot-b-outside-active-dashboard-and-reboot-readiness-surfaces)** — Park Bot B outside active dashboard and reboot-readiness surfaces
- **[ADR-065](#adr-065-offensive-profitability-rewrite-promotes-bot-b-and-fusion-to-p0)** — Offensive profitability rewrite promotes Bot B and fusion to P0
- **[ADR-029](#adr-029-bot-b-scorer-rebuilt-as-multi-estimator-ensemble)** — Bot B scorer rebuilt as multi-estimator ensemble
- **[ADR-015](#adr-015-bot-b-scorer-via-upstream-oracle-mangle-http-api-instead-of-in-repo-port)** — Bot B scorer via upstream oracle-mangle HTTP API (instead of in-repo port)
- **[ADR-003](#adr-003-bot-b-thesis-oraclemangle-kelly-directional)** — Bot B thesis — Oraclemangle Kelly directional

#### Bot C (Pyth) (5)

- **[ADR-121](#adr-121-builder-code-rebate-harvest-blocked-at-current-bot-configuration)** — Builder-code rebate harvest BLOCKED at current bot configuration
- **[ADR-093](#adr-093-retire-bot-c-active-trading-and-keep-pythhermes-research-assets)** — Retire Bot C active trading and keep Pyth/Hermes research assets
- **[ADR-062](#adr-062-normalize-bot-c-to-hermes-paper-executor-in-systemd)** — Normalize Bot C to Hermes paper executor in systemd
- **[ADR-034](#adr-034-bot-c-archived-pyth-infra-broken-thin-market-universe)** — Bot C archived — Pyth infra broken + thin market universe
- **[ADR-019](#adr-019-dashboard-stays-python-served-with-static-assets-not-a-js-build-stack)** — Dashboard stays Python-served with static assets, not a JS build stack

#### Bot E (recorder) (13)

- **[ADR-124](#adr-124-back-up-vps-state-dbs-now-require-controlled-recorder-rollover-before-freeing-vps-recorder-space)** — Back up VPS state DBs now; require controlled recorder rollover before freeing VPS recorder space
- **[ADR-122](#adr-122-keep-recorder-infrastructure-running-indefinitely)** — Keep recorder infrastructure running indefinitely
- **[ADR-092](#adr-092-retire-bot-e-active-trading-and-keep-recorderdata-reuse)** — Retire Bot E active trading and keep recorder/data reuse
- **[ADR-059](#adr-059-bot-e-loosens-paper-execution-before-signal-gates)** — Bot E loosens paper execution before signal gates
- **[ADR-058](#adr-058-bot-e-changes-require-current-data-and-public-context-validation)** — Bot E changes require current-data and public-context validation
- **[ADR-057](#adr-057-kronos-is-rejected-for-bot-e-retain-only-lightweight-cex-feature-extraction)** — Kronos is rejected for Bot E; retain only lightweight CEX feature extraction
- **[ADR-049](#adr-049-bot-e-recorder-uses-prioritycontrol-plane-queue-plus-bulk-drop-on-full)** — Bot E recorder uses priority/control-plane queue plus bulk drop-on-full
- **[ADR-037](#adr-037-bot-e-un-archived-for-paper-data-collection-and-tuning)** — Bot E un-archived for paper data-collection and tuning
- **[ADR-027](#adr-027-phase-5-bot-e-signal-upgrades-tte-stratification-signed-cex-cvd-gate-depth-at-best-gate)** — Phase 5 Bot E signal upgrades — TTE stratification, signed CEX CVD gate, depth-at-best gate
- **[ADR-026](#adr-026-phase-4-bot-e-data-flow-instrumentation-realistic-maker-fill-sim-per-fill-event-emission-adverse-selection-halt-wiring-calibration-gate-runner)** — Phase 4 Bot E data-flow instrumentation (realistic maker-fill sim, per-fill Event emission, adverse-selection halt wiring, calibration-gate runner)
- **[ADR-024](#adr-024-phase-2-three-llm-audit-remediation-seasonal-rmse-skew-normal-narrow-live-window-correlation-adjusted-cap-lot-based-pnl-trailing-halt-wired-ewma-obi-recorder-gap-detection)** — Phase 2 three-LLM audit remediation (seasonal RMSE, skew-normal, narrow live window, correlation-adjusted cap, lot-based PnL, trailing halt wired, EWMA OBI, recorder gap detection)
- **[ADR-023](#adr-023-phase-1-three-llm-trading-audit-remediation-fees-parabolic-bot-e-maker-only-paper-cross-bot-fleet-cap-db-backed-calibration-gate)** — Phase 1 three-LLM trading-audit remediation (fees parabolic, Bot E maker-only paper, cross-bot fleet cap, DB-backed calibration gate)
- **[ADR-022](#adr-022-bot-e-pivot-to-obi-directional-mandatory-bot-e0-recorder-phase)** — Bot E pivot to OBI-directional + mandatory Bot E0 recorder phase

#### Bot F (sensor) / Wallet-tag (8)

- **[ADR-186](#adr-186-add-wallet-tag-elite-cap-paper-as-a-capped-paper-only-lane)** — Add Wallet-Tag Elite Cap Paper as a capped paper-only lane
- **[ADR-151](#adr-151-wallet-tag-sportsesports-feature-filter--lift-near-resolution-kill-list-line-for-wallet-quality-signal-only-paper-only)** — Wallet-tag sports/esports feature filter — lift near-resolution kill-list line for wallet-quality signal only, paper-only
- **[ADR-137](#adr-137-wallet-tag-forward-validation-window--7-days-dual-timer-observer--resolution-backfill)** — Wallet-tag forward validation window — 7 days, dual-timer observer + resolution backfill
- **[ADR-126](#adr-126-deploy-passive-wallet-observer-for-245-retail-tier-wallets-polygon-ctf-v2-negrisk-v2)** — Deploy passive wallet observer for 245 retail-tier wallets (Polygon CTF V2 + NegRisk V2)
- **[ADR-066](#adr-066-bot-f-becomes-shared-sensor-infrastructure-not-a-fast-roi-trader)** — Bot F becomes shared sensor infrastructure, not a fast-ROI trader
- **[ADR-050](#adr-050-v2-wallet-migration-completed-on-chain-session-44)** — V2 wallet migration completed on-chain (Session 44)
- **[ADR-040](#adr-040-session-22-fleet-review-cleanup-fee-reconcile-canonical-bot-registry-wallet-masking-misc-correctness)** — Session 22 fleet-review cleanup — fee reconcile, canonical bot registry, wallet masking, misc correctness
- **[ADR-032](#adr-032-bot-f-rehabilitation-estimator-supplier-crowd-signal-producer)** — Bot F rehabilitation — estimator supplier + crowd-signal producer

#### Crypto fair-value (5)

- **[ADR-178](#adr-178-activate-crypto-fv-maker-tiny-live-probes-on-the bot container)** — Activate crypto FV maker tiny-live probes on the bot container
- **[ADR-177](#adr-177-prepare-crypto-fv-maker-tiny-live-probes-behind-explicit-approval)** — Prepare crypto FV maker tiny-live probes behind explicit approval
- **[ADR-139](#adr-139-archive-crypto-fair-value-paper-strategies-and-retain-recorder-infrastructure)** — Archive crypto fair-value paper strategies and retain recorder infrastructure
- **[ADR-132](#adr-132-crypto-fair-value-microstructure-and-post-cost-audit-gates-the-verdict-not-a-model-swap)** — Crypto fair-value microstructure and post-cost audit gates the verdict, not a model swap
- **[ADR-108](#adr-108-implement-crypto-fair-value-paper-lanes-not-live-trading)** — Implement crypto fair-value paper lanes, not live trading

#### Bot K (sports taker) (2)

- **[ADR-161](#adr-161-bot-k-paper-filters-to-near-term-sports-markets-before-live-probe-review)** — Bot K paper filters to near-term sports markets before live-probe review
- **[ADR-153](#adr-153-bot-k--sports-taker-market-open-paper-lane)** — Bot K — Sports Taker (market-open) paper lane

#### Strategy E (1)

- **[ADR-123](#adr-123-accept-strategy-e-ttr-windowed-cheap-yes-hold-to-resolution-as-paper-only-with-empirical-edge-basis-from-wangzj-5-year-backtest)** — Accept Strategy E (TTR-Windowed Cheap-YES Hold-to-Resolution) as paper-only with empirical-edge basis from WANGZJ 5-year backtest

#### Fees / market rules (2)

- **[ADR-038](#adr-038-polymarket-taker-fee-formula-remove-double-price-multiplier)** — Polymarket taker fee formula — remove double-price multiplier
- **[ADR-028](#adr-028-phase-5-follow-ups-status-fee-parser-telegram-notify-bot-a-volume-capture-test-env-cleanup)** — Phase 5 follow-ups status (fee parser, Telegram notify, Bot A volume capture, test-env cleanup)

#### Infra / ops (13)

- **[ADR-194](#adr-194-approve-small-hetzner-vps-eur-5-8mo-for-recorder--calibration-harvester)** — Approve small the VPS provider VPS (~EUR 5–8/mo) for recorder + calibration harvester
- **[ADR-188](#adr-188-recover-the bot container-bot-e-recorder-by-bulk-offload-and-hard-disk-guard)** — Recover the bot container Bot E recorder by bulk offload and hard disk guard
- **[ADR-171](#adr-171-harden-the bot container-systemd-sandboxes-for-external-db-symlink-targets)** — Harden the bot container systemd sandboxes for external DB symlink targets
- **[ADR-168](#adr-168-keep-the bot container-root-disk-for-code-and-config-bulk-data-on-mounted-storage)** — Keep the bot container root disk for code and config; bulk data on mounted storage
- **[ADR-157](#adr-157-fleet-cap-livepaper-filtering-uses-registry-status-before-env-fallbacks)** — Fleet-cap live/paper filtering uses registry status before env fallbacks
- **[ADR-155](#adr-155-vps-hosted-live-bots-get-a-local-watchdog-scope)** — VPS-hosted live bots get a local watchdog scope
- **[ADR-130](#adr-130-automate-safe-zero-value-standard-wallet-redemptions-on-the-vps)** — Automate safe zero-value standard wallet redemptions on the VPS
- **[ADR-125](#adr-125-clarify-strategy-e-paper-build-gates-and-deploy-first-lane-on-the-vps)** — Clarify Strategy E paper-build gates and deploy first lane on the VPS
- **[ADR-116](#adr-116-decouple-the bot container-watchdog-startup-from-legacy-vpn-egress-probe)** — Decouple the bot container watchdog startup from legacy the VPN provider egress probe
- **[ADR-111](#adr-111-use-a-tailscale-first-vps-split-hosting-pilot-before-moving-live-order-placement)** — Use a Tailscale-first VPS split-hosting pilot before moving live order placement
- **[ADR-063](#adr-063-scope-watchdog-halts-and-alert-on-halt-transitions)** — Scope watchdog halts and alert on halt transitions
- **[ADR-047](#adr-047-watchdog-cancel-routing-defaults-to-per-bot-registry-status)** — Watchdog cancel routing defaults to per-bot registry status
- **[ADR-018](#adr-018-reject-zero-touch-passphrase-restore-from-disk)** — Reject zero-touch passphrase restore from disk

#### General / cross-cutting (44)

- **[ADR-193](#adr-193-c5-maker-reopen-blocked-behind-fill-conditioned-replay-gate)** — C5 maker reopen blocked behind fill-conditioned replay gate
- **[ADR-192](#adr-192-c3-stale-quote-mirage-presumption--pre-registered-permanent-kill)** — C3 stale-quote-mirage presumption + pre-registered permanent kill
- **[ADR-191](#adr-191-full-reassessment-2026-07-verdict-c1-primary-c2-runner-up)** — Full reassessment 2026-07 verdict: C1 primary, C2 runner-up
- **[ADR-187](#adr-187-execute-approved-paper-lane-pausearchive-packet)** — Execute approved paper-lane pause/archive packet
- **[ADR-185](#adr-185-complete-fleet-wide-audit-and-unprofitable-lanes-shutdown)** — Complete fleet-wide audit and unprofitable lanes shutdown
- **[ADR-184](#adr-184-external-trading-frameworks-stay-out-of-live-runtime-quantstats-allowed-only-as-optional-offline-analytics)** — External trading frameworks stay out of live runtime; QuantStats allowed only as optional offline analytics
- **[ADR-183](#adr-183-halt-all-live-services-while-keeping-paper-and-recorders-alive)** — Halt all live services while keeping paper and recorders alive
- **[ADR-182](#adr-182-wallet-data-api-dry-run-backfill-job--dashboard-truth-surface-oq-123-foundation)** — Wallet Data API dry-run backfill job + dashboard truth surface (OQ-123 foundation)
- **[ADR-181](#adr-181-pause-bot-i-live-and-keep-only-bot-d-live-during-loss-reassessment)** — Pause Bot I live and keep only Bot D live during loss reassessment
- **[ADR-176](#adr-176-block-cell-c-1-maker-live-probe-until-the-exchange-minimum-is-explicitly-authorized)** — Block Cell C $1 maker live probe until the exchange minimum is explicitly authorized
- **[ADR-173](#adr-173-raise-bot-l-live-probe-bundle-cap-to-exchange-minimum-viable-size)** — Raise Bot L live-probe bundle cap to exchange-minimum viable size
- **[ADR-172](#adr-172-activate-approved-d-spike-station-lock-and-bot-l-live-probe-runtimes)** — Activate approved D-Spike, Station Lock, and Bot L live-probe runtimes
- **[ADR-170](#adr-170-next-aggressive-live-probe-packet-prioritizes-capped-learning-over-old-sample-gates)** — Next aggressive live-probe packet prioritizes capped learning over old sample gates
- **[ADR-165](#adr-165-operator-approves-three-tiny-live-probes-and-dashboard-live-status)** — Operator approves three tiny live probes and dashboard live status
- **[ADR-164](#adr-164-prepare-tiny-live-probe-readiness-packets-without-enabling-live-trading)** — Prepare tiny live-probe readiness packets without enabling live trading
- **[ADR-163](#adr-163-adopt-fast-tiny-live-probe-doctrine-while-preserving-fund-safety)** — Adopt fast tiny-live probe doctrine while preserving fund safety
- **[ADR-119](#adr-119-close-negrisk-basket-arb-track-at-200-solo-operator-scale)** — Close NegRisk basket arb track at $200 solo-operator scale
- **[ADR-110](#adr-110-run-heavy-offline-crypto-validation-on-the-local-workstation-keep-the-homelab-hypervisor-live-first)** — Run heavy offline crypto validation on the local workstation, keep the homelab hypervisor live-first
- **[ADR-109](#adr-109-store-becker-prediction-market-data-on-fast-vm-for-offline-validation)** — Store Becker prediction-market data on fast-vm for offline validation
- **[ADR-106](#adr-106-trust-exchange-neg-risk-metadata-for-live-clob-signing)** — Trust exchange neg-risk metadata for live CLOB signing
- **[ADR-054](#adr-054-fleet-paper-performance-is-epoch-sliced-in-the-operator-dashboard)** — Fleet paper performance is epoch-sliced in the operator dashboard
- **[ADR-051](#adr-051-default-polygon-rpc-moves-to-publicnode)** — Default Polygon RPC moves to PublicNode
- **[ADR-048](#adr-048-polymarket-v2-live-cutover-uses-clobwrapperv2-fleet-wide)** — Polymarket V2 live cutover uses ClobWrapperV2 fleet-wide
- **[ADR-042](#adr-042-oq-047-paper-only-tactical-rollout-for-bots-cdfg)** — OQ-047 paper-only tactical rollout for Bots C/D/F/G
- **[ADR-041](#adr-041-session-22-post-deploy-ops-fixes-heartbeat-permanent-failed-detection-second-orphan-dedup)** — Session 22 post-deploy ops fixes — heartbeat, permanent-failed detection, second orphan-dedup
- **[ADR-039](#adr-039-glm-51-fleet-review-remediation-paper_override-read-only-dashboard-auth-adverse-selection-docstring-snapshot_daily-single-call)** — GLM-5.1 fleet-review remediation (paper_override read-only, dashboard auth, adverse-selection docstring, snapshot_daily single-call)
- **[ADR-035](#adr-035-paper-mode-position-reconciliation-via-gamma-resolution-poll)** — Paper-mode position reconciliation via Gamma resolution poll
- **[ADR-033](#adr-033-bot-a-archived-walk-forward-disproves-net-pnl-thesis)** — Bot A archived — walk-forward disproves net-PnL thesis
- **[ADR-031](#adr-031-fleet-wide-exec-policy-dynamic-limit-ladder-toxicity-filter)** — Fleet-wide exec-policy — dynamic limit-ladder + toxicity filter
- **[ADR-020](#adr-020-dashboard-overview-optimizes-for-operator-questions-not-full-system-exhaust)** — Dashboard overview optimizes for operator questions, not full-system exhaust
- **[ADR-017](#adr-017-stay-on-py-clob-client-0346-through-paper-phase-defer-py-clob-client-v2-migration)** — Stay on `py-clob-client` 0.34.6 through paper phase; defer `py-clob-client-v2` migration
- **[ADR-016](#adr-016-marketsvolume_24h_usd-column-sourced-from-gamma-scraper)** — `markets.volume_24h_usd` column sourced from Gamma scraper
- **[ADR-014](#adr-014-vpn-posture--wireguard-vpn-split-tunnel-on-the-homelab-hypervisor)** — VPN posture — WireGuard VPN split-tunnel on the homelab hypervisor
- **[ADR-013](#adr-013-sqlite-over-postgres-for-v1-storage)** — SQLite over Postgres for v1 storage
- **[ADR-012](#adr-012-rejected-strategy-alternatives-consolidated)** — Rejected strategy alternatives (consolidated)
- **[ADR-011](#adr-011-tos-posture-c-capped-exposure-vpn-working-assumption)** — ToS posture (c) — capped-exposure + VPN (WORKING ASSUMPTION)
- **[ADR-010](#adr-010-tax-posture-c-build-advise-in-parallel-working-assumption)** — Tax posture (c) — build + advise in parallel (WORKING ASSUMPTION)
- **[ADR-009](#adr-009-key-management-encrypted-keystore-ledger-treasury)** — Key management — encrypted keystore + Ledger treasury
- **[ADR-008](#adr-008-test-protocol-30-day-paper-graduation-thresholds-kill-rules)** — Test protocol — 30-day paper, graduation thresholds, kill rules
- **[ADR-007](#adr-007-shared-infrastructure-built-once-before-either-bot)** — Shared infrastructure built once before either bot
- **[ADR-006](#adr-006-deploy-to-the-homelab-hypervisor-not-the-local-workstation)** — Deploy to the homelab hypervisor, not the local workstation
- **[ADR-005](#adr-005-signature-type-0-eoa-for-v1-auth)** — Signature type 0 (EOA) for v1 auth
- **[ADR-001](#adr-001-build-two-bots-in-parallel-not-one)** — Build two bots in parallel, not one

---

<!-- ADR-INDEX:END -->

## ADR-001: Build two bots in parallel, not one

**Date:** 2026-04-14
**Status:** accepted
**Context:** Phase 3 required choosing a build strategy. A single bot couldn't answer "which thesis wins" without a comparator; three+ would fragment attention and capital for a solo operator.
**Decision:** Build **two** bots side-by-side with genuinely different theses. Both must pass shared infrastructure, kill-switch, and observability bars.
**Rationale:** Two gives a clean A/B on real money with enough statistical power to learn in 16 weeks. One would create selection bias ("obviously the one I built"). Three+ means neither ships well.
**Alternatives considered:** Single bot on highest-conviction thesis; three bots (rejected — solo operator bandwidth); sequential builds (rejected — timeline doubles).
**Consequences:** Shared infra investment is justified (used by both). Architecture decisions must consider A/B observability. Capital split halves each bot's starting stake.

---

## ADR-002: Bot A thesis — mechanical longshot fade

**Date:** 2026-04-14
**Status:** accepted
**Context:** Needed a baseline that does NOT depend on an LLM or oraclemangle, to isolate whether model-driven edge adds value above rule-driven edge.
**Decision:** Bot A buys NO on Polymarket markets where `yes_price ≤ 0.05`, in categories {geopolitics, politics, finance, economics}, `days_to_resolution ∈ [30, 180]`, `volume_24h ≥ $5,000`, `book_depth ≥ $500`. Holds to resolution. Position size fixed at $30 per market.
**Rationale:** The crowd systematically over-prices tail outcomes in prediction markets (base-rate + lottery-ticket psychology). Mechanical rule is auditable, reproducible, trust-level-1. Hold period 30–180 days is long enough that speed-based competitors self-select out. Grok intel shows one wallet did $300→$117k over 31k predictions on this pattern — archetype exists and is thinly populated.
**Alternatives considered:** Momentum-based taker (too crowded); cross-venue arb (Kalshi KYC-hostile); copy-trading (reactive, no edge).
**Consequences:** Bot A's failure invalidates the base-rate thesis, not the LLM thesis. Bot A's success without Bot B would call oraclemangle's value into question. Per-market $30 cap means we need ~33 concurrent positions to deploy £1k — diversification forced.

---

## ADR-003: Bot B thesis — Oraclemangle Kelly directional

**Date:** 2026-04-14
**Status:** accepted (scorer implementation path superseded by ADR-015)
**Context:** User has access to an externally calibrated dispute-risk scorer (Oraclemangle — https://oraclemangle.com). Not using it is strategic malpractice. But the external service was operationally unreliable for bot consumption at decision time.
**Decision:** Bot B was planned to integrate with that external scorer and derive/persist local fields (`claude_pick`, implied probability) inside this project's codebase. Filters: `dispute_risk ≤ 0.25`, `claude_confidence ≥ 0.7`, `|p_model − p_market| ≥ 0.08`. Sizes at 0.25 × Kelly with dispute-risk penalty multiplier. Categories same as Bot A. (Implementation path later superseded by ADR-015 HTTP client.)
**Rationale:** A bounded local integration avoids depending on a broken external cron. Fixing local field persistence is a 1–3 day task vs waiting on the external service. The edge is model-vs-crowd on resolution ambiguity using the external scorer signal (see https://oraclemangle.com).
**Alternatives considered:** Consume the external scorer live via API (rejected — service unreliable at the time); rewrite a scorer from scratch (rejected — month+ of work for zero gain); wait for external-service fix (rejected — blocks this project indefinitely).
**Consequences:** This repo owns Bot B integration code only, not the external scorer product. External-service changes do not automatically propagate. Scorer path later moved to HTTP per ADR-015.

---

## ADR-004: Oraclemangle is ported, not consumed

**Date:** 2026-04-14
**Status:** superseded by ADR-015
**Context:** Phase 2.5 audit revealed the external scorer service (Oraclemangle — https://oraclemangle.com) was effectively non-operational for bot consumption (stale outputs; trading tables empty).
**Decision:** Bot B does **not** consume the external service's private DB or modify that product. Integration is owned in this repo at a controlled boundary; the external product remains separate (https://oraclemangle.com). (Path later refined by ADR-015.)
**Rationale:** Coupling launch to fixing a separate product's ops is not acceptable risk. A bounded local integration is auditable and gives the bot its own operational surface.
**Alternatives considered:** Consume the external service's DB (rejected — stale); fix that product's daemon and consume (rejected — coupling blocks both projects); build a new scorer from scratch (rejected — loses access to the external calibrated product).
**Consequences:** ~1 day of integration work in Week 3. This repo does not ship the external scorer's code or calibration data.

---

## ADR-005: Signature type 0 (EOA) for v1 auth

**Date:** 2026-04-14
**Status:** accepted
**Context:** `py-clob-client` supports three signature types: 0 (EOA), 1 (Magic/email proxy), 2 (browser wallet proxy).
**Decision:** Use `signature_type=0` with no `funder` (signer == funder) for v1. Single EOA hot wallet.
**Rationale:** Simplest path. No proxy complexity. No delegated-signing surface. Matches the "dedicated hot wallet, encrypted keystore, capped exposure" model.
**Alternatives considered:** Type 1 (rejected — requires Magic/email flow the bot shouldn't touch); Type 2 (rejected — proxy-wallet complexity for no gain at this scale).
**Consequences:** Hot wallet's private key must be available at daemon start (via age-encrypted keystore + passphrase from tmpfs). No hardware wallet path possible in v1 because py-clob-client doesn't support it.

---

## ADR-006: Deploy to the homelab hypervisor, not the local workstation

**Date:** 2026-04-14
**Status:** accepted
**Context:** User is a offshore-worker on rotation; the local workstation sleeps, offshore work rotations are weeks long, satellite internet is unreliable. Bot must tolerate operator-unreachable for 14 days.
**Decision:** Production bot runs on the homelab hypervisor (always-on). the local workstation is dev-only.
**Rationale:** Bot's paper and live phases overlap with at-sea rotations. Bot must run unattended. the homelab hypervisor is already provisioned (Dell Precision 3620, 32 GB RAM, Xeon, Quadro P2000) and hosts always-on services. the local workstation would halt during rotations.
**Alternatives considered:** Cloud VPS (rejected — adds monthly cost with no privacy gain over homelab); Mac mini dedicated (rejected — user doesn't have one, the local workstation sleeps); laptop (rejected — not always-on).
**Consequences:** the homelab hypervisor node runs the daemon via systemd. Telegram alerts twice daily even on quiet days (silence ≠ success). Auto-restart after 3 crashes halts bot pending human review. VPN (WireGuard VPN) runs on the the homelab hypervisor node.

---

## ADR-007: Shared infrastructure built once before either bot

**Date:** 2026-04-14
**Status:** accepted
**Context:** Both bots need CLOB wrapper, keystore, ingest, DB, portfolio tracker, watchdog, Telegram. Building them twice is waste.
**Decision:** Week 1 builds shared infra in `core/`: `clob.py`, `keystore.py`, `ingest.py`, `db.py`, `portfolio.py`, `watchdog.py`, `notify.py`, `backtest.py`, plus the VPN provider VPN on the homelab hypervisor. Bot-specific code in `bots/bot_a/` and `bots/bot_b/`.
**Rationale:** Single source of truth for order placement, key handling, logging, alerts. Bug fixes propagate to both bots. Simpler testing.
**Alternatives considered:** Per-bot duplication (rejected — maintenance nightmare); shared infra inside one bot, other bot imports (rejected — circular).
**Consequences:** Week 1 has no visible bot output. Shared code must be boring, stable, well-tested before Week 2. Estimated 6.25 days.

---

## ADR-008: Test protocol — 30-day paper, graduation thresholds, kill rules

**Date:** 2026-04-14
**Status:** accepted
**Context:** Without concrete thresholds, "test the bot" becomes vibes.
**Decision:**
- Paper phase: 30 days minimum; Bot A ≥60 entries + 5 resolutions; Bot B ≥20 entries + 10 resolutions
- Graduate to live at £250 when: paper Calmar ≥0.8, no unexplained log events in last 14 days, manual code review passed, live $5 dry-run succeeded
- Scale: £250→£500 at 30 live days positive + <10% drawdown; →£1,000 at 60 live days positive + <12% drawdown
- Kill: 15% drawdown, 4 consecutive negative weeks, bot-specific death pattern, any unexplained bug revealing unbounded-loss potential
**Rationale:** Concrete thresholds are the only defence against motivated reasoning at decision points. Dates and numbers. No "we'll see."
**Alternatives considered:** Pure P&L threshold (rejected — ignores drawdown shape); vibe-based review (rejected — every trader who lost money reviewed their trades and kept going).
**Consequences:** User commits to following the rules even when "this time it's different." Rules can be changed only by a superseding ADR.

---

## ADR-009: Key management — encrypted keystore + Ledger treasury

**Date:** 2026-04-14
**Status:** accepted
**Context:** Hot wallet needs to sign orders unattended. Private key must be available to the daemon but not exposed.
**Decision:**
- One EOA hot wallet, age-encrypted keystore at `~/.config/polymarket-bot/keystore.age`
- Passphrase from tmpfs, populated via SSH on boot (no passphrase on disk)
- Hot wallet capped at **$2,000 live exposure** at any moment
- Ledger-held treasury wallet, separate EOA, manual top-ups to hot only
- No hardware-wallet signing path in v1 (py-clob-client doesn't support)
**Rationale:** Risk-budget appropriate. Loss bounded by hot-wallet cap. Treasury compromise requires physical Ledger access.
**Alternatives considered:** Hardware-wallet signing (rejected — out of scope to build); AWS KMS / HashiCorp Vault (rejected — cloud dependency for no gain); shared-signer service (rejected — adds attack surface).
**Consequences:** Losing the hot wallet loses up to $2k. Treasury loss requires physical Ledger compromise. Every daemon restart requires SSH + passphrase on tmpfs population.

---

## ADR-010: Tax posture (c) — build + advise in parallel (WORKING ASSUMPTION)

**Date:** 2026-04-14
**Status:** accepted (pending user confirm in architecture-decision.md §9)
**Context:** UK tax treatment of Polymarket PnL is ambiguous (CGT / miscellaneous / trade / gambling).
**Decision:** Proceed under working assumption of CGT-on-ERC-1155-disposal. Log every trade in HMRC-ready format from day 1 (timestamp, market id, side, size, price, fee, USD↔GBP rate at trade time). Engage chartered UK tax advisor in parallel with build. If advisor returns adverse opinion, pause and re-assess.
**Rationale:** Waiting for advisor opinion (2–4 weeks) blocks build. Logging HMRC-ready from day 1 preserves optionality for any eventual treatment. CGT is the most common treatment for crypto-asset disposals and a reasonable default.
**Alternatives considered:** Pause build until opinion (rejected — kills momentum); proceed without logging (rejected — can't undo). Gambling treatment (rejected — systematic bot pushes toward trade/income).
**Consequences:** Trade log format must be HMRC-ready. If opinion returns "trade + NI," we re-evaluate sizing and whether the project still makes economic sense.

---

## ADR-011: ToS posture (c) — capped-exposure + VPN (WORKING ASSUMPTION)

**Date:** 2026-04-14
**Status:** accepted (pending user confirm in architecture-decision.md §9)
**Context:** UK is explicitly blocked by Polymarket's Help Center geo-restrictions. Canonical ToS page renders empty HTML (unclear acceptance mechanism).
**Decision:** Proceed with max $2,000 live exposure across both bots. All CLOB traffic via WireGuard VPN on the homelab hypervisor node, split-tunnel, exit node outside UK. `iptables` kill-switch blocks CLOB egress if VPN drops.
**Rationale:** Account-level risk (termination + open-position forfeiture) is bounded by the $2k cap. Legal exposure is capped by the absence of operative ToS text to accept. VPN handles the network-level geo surface; legal-level posture is in ADR-010.
**Alternatives considered:** Proceed without exposure cap (rejected — unbounded loss on account termination); pause (rejected — same as ADR-010).
**Consequences:** Never more than $2,000 in open positions aggregate. VPN is a hard dependency — bot halts if VPN fails. Exit node choice (Stockholm / Amsterdam) is a policy choice the user can change.

---

## ADR-012: Rejected strategy alternatives (consolidated)

**Date:** 2026-04-14
**Status:** accepted
**Context:** Before locking Bot A + Bot B, we considered and rejected several strategy classes. Recording here so future sessions don't revisit without reason.
**Decision:** The following are OUT OF SCOPE for this repo unless a new ADR supersedes:

| Strategy | Rejected because |
|---|---|
| Market-making / rebate farming | Needs $50k–$500k inventory, sub-100ms requote, adverse-selection engineering. Wrong capital tier, wrong infra. |
| Near-resolution crypto scalping (5/15-min BTC/ETH/SOL) | Spreads at 0.3–0.5¢; latency-bound; UK loses to Virginia-colocated bots; crypto is worst fee category. |
| Delta-neutral volatility split on crypto | Gas + one-leg-fill risk; 1–2%/cycle insufficient margin; crypto category. |
| Cross-venue arbitrage (Polymarket ↔ Kalshi) | Kalshi KYC hostile to UK; Manifold matcher already flagged broken; requires simultaneous fills. |
| Copy-trading verified sharps (Theo4 / Fredi9999) | Reactive, no edge; survivor bias; can't unwind losing copy. |
| Pure sentiment / news-latency | Speed game; UK RTT kills it. |
| Weather directional (GFS vs crowd) | **Deferred to v1.5** if Bot A/B fails. Rejected v1 because Polymarket weather volume unverified (Kalshi-dominant). |
| TimesFM short-horizon crypto | **Deferred to v2.** Good candidate but crypto category fees + crowding. |

**Rationale:** Solo UK operator with 16-week build. Each rejection has a specific reason. Future sessions proposing any of these must write a new ADR arguing the reason has changed.
**Alternatives considered:** All listed above.
**Consequences:** Future sessions that drift into these require explicit user sign-off.

---

## ADR-013: SQLite over Postgres for v1 storage

**Date:** 2026-04-14
**Status:** accepted
**Context:** The external scorer product and this repo both used SQLite successfully at the expected volume. User's the homelab hypervisor has no Postgres set up. Migration is a week of work.
**Decision:** Use SQLite + SQLAlchemy + Alembic migrations for this project's v1. Table design supports later Postgres migration (standard SQL, no SQLite-specific features).
**Rationale:** Zero setup friction. Sufficient for the expected volume (<1k trades/week, <10k market snapshots/week). Daily encrypted backup to Backblaze B2 covers durability.
**Alternatives considered:** Postgres on the homelab hypervisor (rejected — week of setup for no current benefit); Postgres on managed cloud (rejected — monthly cost); DuckDB (rejected — OLAP, wrong fit).
**Consequences:** Single-writer constraint. Migration deferred to v2 if volume grows.

---

## ADR-014: VPN posture — WireGuard VPN split-tunnel on the homelab hypervisor

**Date:** 2026-04-14
**Status:** accepted (pending ADR-011 confirmation)
**Context:** UK is blocked at the network level by Polymarket. Need a routing layer that doesn't leak the operator's UK origin.
**Decision:** WireGuard VPN on the the homelab hypervisor node. Split-tunnel: only `clob.polymarket.com`, `gamma-api.polymarket.com`, `ws-subscriptions-clob.polymarket.com`, and UMA subgraph endpoints route through VPN. Everything else direct. Exit node in Europe, NOT UK. `iptables` kill-switch blocks those hosts if VPN drops.
**Rationale:** the VPN provider: no-log policy, cash payment option, WireGuard support, reliable infrastructure. Split-tunnel reduces bandwidth cost of routing unrelated traffic. Exit node outside UK satisfies the geo surface.
**Alternatives considered:** Full-tunnel VPN (rejected — bandwidth waste); commercial VPS in Europe as jump (rejected — another system to maintain); Tor (rejected — latency unacceptable for CLOB).
**Consequences:** Bot hard-depends on VPN up. the VPN provider subscription (~€5/month) becomes operating cost.

---

## ADR-015: Bot B scorer via upstream oracle-mangle HTTP API (instead of in-repo port)

**Date:** 2026-04-15
**Status:** accepted (interim — full in-repo port remains a possibility post-paper-phase)
**Context:** specs/bot-b-spec.md originally called for porting a large external scorer into this repo. The externally calibrated dispute-risk scorer (Oraclemangle — https://oraclemangle.com) already exposes an HTTP scoring API. Using that endpoint costs no additional port effort.
**Decision:** Bot B's scorer is `bots/bot_b/http_scorer.py::HttpScorer` — an HTTP client that calls the external scorer's `GET /v1/score` endpoint. It derives `claude_pick` and `claude_implied_prob` locally from the response fields the external service returns, then persists scorer fields to this project's `scores` table. The DB-read-only `StoredScorer` from Session 3 remains available for tests that seed `scores` rows directly.
**Rationale:** (1) Eliminates a large port of work we'd have to re-verify. (2) The "bug fix" in the spec is local persistence of `claude_pick` + `claude_implied_prob` — doing that in `HttpScorer` fixes it without touching the external product. (3) Coupling to the external API rather than its code means we inherit improvements. (4) Unblocks Week-2 paper trading immediately.
**Alternatives considered:** (a) Full in-repo port — rejected, too much work when a running service exists. (b) Build a scorer from scratch in this repo, skipping the external product — rejected, loses the calibrated dispute-risk signal (see https://oraclemangle.com). (c) Shared SQLite read from the external product's DB — rejected, introduces cross-product DB coupling with no clear ownership.
**Consequences:** Hard dependency on the external scorer service being reachable over HTTP (https://oraclemangle.com). If the service is down, Bot B's scoring sweep silently backs off (logged as `bot_b.scorer.exhausted`) and lifecycle.tick() finds no fresh candidates. No mainnet order risk. API credentials provisioned via env (`ORACLEMANGLE_API_KEY` / `ORACLEMANGLE_API_URL`).

---

## ADR-016: `markets.volume_24h_usd` column sourced from Gamma scraper

**Date:** 2026-04-15
**Status:** accepted
**Context:** Session 3 bot A/B filters referenced `volume_24h` but the `markets` schema didn't persist it — the scraper ignored the field, and lifecycle.tick() fell back to an empty `volume_map`, causing the volume filter to reject every candidate.
**Decision:** Added `volume_24h_usd DECIMAL(18,2) NOT NULL DEFAULT 0` to `markets`. `Scraper._upsert_batch` reads `volume24hr | volume_24h | volumeNum` from the Gamma payload and persists it on every ingest tick. `build_candidates()` reads the column; `volume_map` kwarg survives as a per-market override for tests.
**Rationale:** A column is cheaper than a secondary table. The Gamma payload already carries this field — we just weren't storing it.
**Alternatives considered:** Separate `volume_snapshots` history table (rejected — not needed for v1; filter only wants "most recent"). Computing from trade feed (rejected — Gamma API is authoritative and cheaper).
**Consequences:** Alembic revision `2a92772f19ea`. All existing rows default to 0 (a fresh scraper run refreshes them within 15 min).

---

## ADR-017: Stay on `py-clob-client` 0.34.6 through paper phase; defer `py-clob-client-v2` migration

**Date:** 2026-04-15
**Status:** accepted
**Context:** Polymarket published `py-clob-client-v2` on PyPI on 2026-04-08 (author: `engineering@polymarket.com`, repo: `github.com/Polymarket/py-clob-client-v2`), in parallel with a live-service change that removed `/supported-assets` (now 404) and decommissioned `clob-amoy.polymarket.com` (no DNS). The incumbent `py-clob-client` is at 0.34.6 (2026-02-19, still the PyPI "latest") and still pins USDC.e as mainnet collateral. The V2 package is at 0.0.2 and was published exactly twice, minutes apart. `clob.polymarket.com` mainnet `/markets` still returns 200 with the pre-V2 schema, and Polygon mainnet still has code at the pinned exchange address.
**Decision:** Stay on `py-clob-client==0.34.6` through the 30-day paper phase. Preflight's OQ-008 switches its `--live` probe from the dead `/supported-assets` endpoint to a `/markets?limit=1` reachability check; the collateral assertion still comes from the pinned client. `dry_run_order.py`'s former Amoy default errors cleanly with a pointer to this ADR. Re-evaluate V2 migration when the v2 client reaches ≥0.1.0, shows release notes, and has an independent consumer.
**Rationale:** (1) The v2 client at 0.0.2 is visibly pre-alpha — no release notes, two commits the same day, no documentation. Migrating to it now would replace a thoroughly-audited dependency with an untested one on the eve of paper trading. (2) The V1 mainnet CLOB still accepts traffic with the pre-V2 addresses and schema — live orders should route exactly as today. (3) The only hard V1 break we can observe is `/supported-assets` and `clob-amoy` being gone, both cosmetic for our purposes (we have other reachability probes and Amoy never covered anything mainnet doesn't). (4) Paper trading is unaffected by client version regardless. (5) If V1 truly breaks we'll see it as order-placement failures during paper, well before any real money is at risk.
**Alternatives considered:**
- *Migrate to `py-clob-client-v2` now* — rejected. 0.0.2 is not production software; we'd be debugging upstream alongside our own code.
- *Vendor both clients, pick at runtime* — rejected. Complexity with no benefit before V1 actually fails.
- *Fall back to direct REST + eth-account signing, bypassing the client* — rejected. Rewrites `core/clob.py` for no current gain; loses the HMAC canonical-string compatibility that OQ-006 verified.
- *Use `/collateral-asset` or similar metadata endpoint as the live probe* — rejected. Every endpoint we tried (`/exchange`, `/collateral-asset`, `/assets`, `/fee`, `/meta`) returned 403; `/markets` is the one public metadata endpoint that 200s reliably.
**Consequences:**
- OQ-008 now passes live (`/markets` reachability + pinned USDC.e). The blocking `preflight.failed` event from Session 6 is superseded.
- If Polymarket retires V1 endpoints during paper, Bot A/B orders will start failing at place-time. That is the trigger to migrate — until then, don't.
- Introduces an explicit re-evaluation item post-paper: "V2 migration — v2 client status, live V1 order success rate."
- `docs/open-questions.md` OQ-008 flips from OPEN to RESOLVED; Amoy dry-run sub-task is retired (endpoint gone, coverage moved to mainnet unfillable-price).

---

## ADR-018: Reject zero-touch passphrase restore from disk

**Date:** 2026-04-15
**Status:** accepted
**Context:** Session 9 audit reviewed `systemd/polymarket-passphrase.service`, a systemd unit that copied the age-keystore passphrase from `/etc/polymarket/keystore-passphrase` on disk into tmpfs at boot so bots could start unattended after a reboot.
**Decision:** Remove the disk-backed passphrase restore unit from the repo. The passphrase remains tmpfs-only and operator-delivered after boot, per ADR-009. Any future automation must preserve the "no passphrase on disk" rule.
**Rationale:** The repo's security posture is explicit: passphrase on tmpfs, no secret-at-rest copy outside the encrypted keystore. A root-owned plaintext passphrase file defeats that design and makes reboot convenience win over the only secret-separation boundary we currently have.
**Alternatives considered:** Root-owned plaintext file in `/etc` (rejected — violates ADR-009 and the repo security rules); systemd credential store on disk (rejected — still at-rest secret material, same core problem); operator re-delivery on reboot (accepted — manual but aligned with the threat model).
**Consequences:** Reboots remain a manual operator touch-point before live trading resumes. `systemd/polymarket-passphrase.service` has been deleted from the repo and stays out until a design exists that preserves tmpfs-only secret handling.

---

## ADR-019: Dashboard stays Python-served with static assets, not a JS build stack

**Date:** 2026-04-15
**Status:** accepted
**Context:** The dashboard outgrew the original one-file stdlib page. The desired UI is a low-scroll operator desk with dense panels and tabs, but the repo is still Python-first and systemd-first with no need for a full SPA toolchain.
**Decision:** Keep the dashboard backend Python-served and read-only, and serve the frontend as static assets from the repo. The implementation lives under `dashboard/` with `dashboard/server.py`, `dashboard/runtime_queries.py`, and `dashboard/static/`. Do not introduce React/Vite/Node for this ops surface.
**Rationale:** This keeps deployment simple, avoids adding a second toolchain to a trading bot repo, and still gives enough UI freedom for tabs, client-side refresh, and dense operator panels. The dashboard is an operator tool, not a product frontend.
**Alternatives considered:** Keep extending the single-file page (rejected — already too coupled); Streamlit (rejected — wrong fit for a dense trading-desk layout); full frontend stack with bundler (rejected — too much operational overhead for a LAN dashboard).
**Consequences:** Dashboard UI work stays isolated in static assets and Python JSON views. Client-side regressions should be covered with dashboard-only tests that hit the served shell and JSON contracts, not bot tests. If the dashboard later becomes a standalone product surface, revisit a dedicated frontend stack then.

---

## ADR-020: Dashboard overview optimizes for operator questions, not full-system exhaust

**Date:** 2026-04-16
**Status:** accepted
**Context:** The Session 10 dashboard refactor produced a capable tabbed desk, but the first screen still spent too much space on service telemetry and per-bot scaffolding. The user explicitly wanted a lightweight dashboard that answers: "Is the bot making money, what is it doing right now, and how has it been performing?"
**Decision:** Keep the existing `dashboard/` architecture, but make Overview and Orders & Positions the primary operator surfaces. Overview now leads with total P&L, daily P&L, win rate, volume, open positions, balance/capital, equity and daily-PnL charts, strategy contribution, current exposure, largest position, open positions, and recent trades. Bot tabs remain for drill-down only.
**Rationale:** The dashboard is an operator tool, so its top-level job is compression, not exhaustiveness. The operator should be able to answer the core money/risk/activity questions in one scan without scrolling through system detail first.
**Alternatives considered:** Keep the earlier dense desk unchanged (rejected — too much signal dilution); collapse everything into a single page with no tabs (rejected — creates unnecessary scroll); move more logic into the frontend (rejected — query layer should own the business summary contract).
**Consequences:** Dashboard query code now computes summary metrics directly, including win-rate and volume fallbacks. The UI surfaces backend limitations explicitly when trade history is too thin to support a real win rate, rather than hiding the gap.

---

## ADR-022: Bot E pivot to OBI-directional + mandatory Bot E0 recorder phase

**Date:** 2026-04-16
**Status:** accepted
**Context:** The original Bot E scope (approved 2026-04-15 per CLAUDE.md out-of-scope update) was a CEX-vs-Polymarket lag arbitrage on 15-min BTC markets, spec'd at `docs/bot-e-spec.md`. The spec requires sub-650ms end-to-end latency and a eu-west-1 VPS. Two independent peer reviews (Grok, Codex — archived under `docs/bot-e-peer-review-responses/`) converged on: (a) the CEX-lag strategy is crowded by HFT-colocation and likely not viable for our latency profile; (b) order-book-imbalance (OBI) + technicals at t−10min to t−5min is a candidate viable strategy on existing infra; (c) article-derived thresholds and wallet-ROI evidence are survivorship-biased and not sufficient to start building a trader without local-data validation; (d) a data-only recorder ("Bot E0") with local latency stamps, heartbeat-tracked capture, and no order placement is the correct first phase; (e) the paper gate as inherited (200 trades ≥75% WR) is statistically infeasible for a true 60–65% directional edge and must be rewritten.
**Decision:**
1. **Pivot Bot E from CEX-lag arbitrage to OBI-directional**, targeting entries in minutes 5–10 of each 15-min BTC/ETH/SOL Up/Down window. Deploys on existing homelab (LXC), not VPS.
2. **Phase 0b (Bot E0 recorder) is mandatory and blocks any trader code execution.** Bot E0 is a pure data-collection module: Polymarket WSS (CLOB book + orders_matched), CEX WSS (Binance), Chainlink price feed, all with local receipt timestamps, no order placement.
3. **Phase 0c extends `core/backtest.py`** with a 2026 Polymarket fee curve, realistic slippage derived from recorded book depth, and latency injection. Phase 0c consumes Bot E0 output.
4. **Phase 0d is the go/no-go decision.** Out-of-sample OBI conditional expectancy after fees+slippage must show positive EV by (minute-to-expiry × liquidity × regime) bucketing. If negative, Bot E closes with zero capital at risk.
5. **Phase 1 trader** is only built if 0d = GO. Scope: pure OBI signal + binary choppiness hard-gate (skip if >0.65, no tuning surface in v1) + fixed $2/trade sizing + telemetry + resilience (heartbeat, REST fallback, feed-divergence halt) + primary/secondary tagging schema.
6. **Revised paper gate**: ≥300 trades, positive net EV after modelled costs, Sharpe ≥1.0, max drawdown ≤25%, survived ≥2 distinct regimes without kill-switch. Replaces the inherited arbitrage gate.
7. **Timeline compression judgment call**: Operator target is <1 week rollout. Codex recommended 1–2 weeks of recording for statistical confidence. Compromise — recorder runs 3–4 days initial (sufficient for provisional calibration given ~1,440 markets/day × 4 days ≈ 5,760 market windows), with a re-calibration pass at 7 days and 14 days of accumulated data. Provisional calibration thresholds are explicitly flagged as v0.5; paper trading runs with conservative thresholds until 14-day recalibration.
**Rationale:** Grok and Codex converged independently on the "recorder first" structural argument. The article-derived evidence is strong enough to invalidate the CEX-lag default but not strong enough to justify jumping straight to an OBI trader. Building Bot E0 with zero trading code costs 3 days and eliminates the single biggest retail-bot failure mode (cargo-culting thresholds from third-party claims). If the recorded data shows no edge after our real fees and latency, we save the ~100 hours of trader-code work.
**Alternatives considered:**
- Build the trader directly with article-derived thresholds (`abs(imbalance) > 0.20`, 2-min window): rejected. Both reviewers flagged this as survivorship bias; our market microstructure is not identical to any article's.
- Extend backtester only, skip recorder: rejected (Codex's central contribution). We have no convenient historical orders_matched data, and even if we did, we need OUR latency, not someone else's.
- Wait 1–2 full weeks before any build: rejected. Operator time-constraint. Trader skeleton is built in parallel with recorder capture period; only the calibrated thresholds wait.
- Colocate in eu-west-1 and pursue CEX-lag: rejected. Infrastructure cost + operator preference for existing homelab stack.
**Consequences:**
- The original `docs/bot-e-spec.md` is partially superseded. Updated spec reflects this ADR.
- Two new packages: `bots/bot_e_recorder/` (Phase 0b) and `bots/bot_e_btc_scalp/` (Phase 1).
- New shared infra: `core/polymarket_ws.py`, `core/cex_ws.py`, `core/chainlink_source.py` — used by both recorder and trader.
- `reason_code` schema changes: two additional columns on `trades` and `orders` for primary `strategy_signal` tag and optional tertiary `reason_detail` free-text (per Codex C-S4). Existing `reason_code` column becomes the five-question secondary enum.
- Bot E v1 Kelly fraction is fixed $2/trade (not k=0.25) until 300+ calibrated paper trades exist.
- Regime classifier is binary hard-gate in v1 (`choppiness > 0.65 → skip`), hard-coded threshold, not env-overridable. Tunable in v1.1 once recorder data justifies a different value.
- OQ-028 (widen main ingest) and OQ-029 (condition_id ID-space split) remain open and are not blocked by this ADR.
- **Blockers before Phase 1 code**: verify Polymarket 2026 fee structure (flat vs dynamic near 50¢); verify Chainlink BTC tick dimensional units. Both logged in Phase 0a verification tasks.
- **Phase 0a verification results (2026-04-16):**
  - **Fee structure CONFIRMED dynamic.** Taker fees are parabolic, peaking at **1.80% for crypto at 50¢ price**, shrinking to ~0 at 1¢/99¢. Category-specific peaks: Crypto 1.80%, Economics 1.50%, Mentions 1.56%, Culture 1.25%, Weather 1.25%, Finance 1.00%, Politics 1.00%, Tech 1.00%, Sports 0.75%, Geopolitics 0%. **Makers pay 0 and earn 20–25% rebate** of counterparty's fee. Source: Polymarket docs 2026-03, referenced in docs/bot-e-peer-review-responses/grok-2026-04-16.md G1.
  - **Impact on Bot E design:** A taker round-trip at 50¢ BTC = **3.60%** — completely erases any realistic directional edge at that price point. **Bot E must be maker-only for entries** (limit orders inside the spread, wait for fills). Effective maker cost ≈ −0.36% to −0.45% (negative = rebate). Post-rebate edge gate `EDGE_NET_THRESHOLD_MAKER = 0.01` (1%) is achievable.
  - **Chainlink BTC/USD tick format CONFIRMED: 8 decimal places**, integer representation (e.g. 3030914000000 → $30,309.14). The v96 article's `|dir_10m| > 30` is dimensionally broken. **Bot E regime classifier normalises to basis points of current price** (`dir_bps = |dir_10m_usd| / current_price * 10_000`). Starting hard-coded threshold `REGIME_TREND_MIN_BPS = 50` (~$42 at $85k BTC) pending recorder-derived calibration.

---

## ADR-021: Bot D dual-writes a minimal `markets` row on every order

**Date:** 2026-04-16
**Status:** accepted
**Context:** Production-DB inspection (the bot LXC container `main.db`) while quantifying an Entry 006 TTR-filter question for Bot D showed Bot D's 15 orders reference 15 distinct `condition_id` values and **zero** of them exist in the `markets` table. The `markets` table has 10,055 rows but none mention temperature / °F / °C — the main ingest pipeline either filters weather markets out or queries Gamma pages that never contain them. Consequence: every analytic that joins `orders -> markets` returns `<no-market-row>` for Bot D, blocking TTR analysis, per-market P&L attribution, backtest replay seeding, and cross-bot dashboard views.
**Decision:** Bot D's executor performs a best-effort upsert into `markets` using Gamma metadata already in-memory at entry time (`bots/bot_d_weather/executor.py` `try_enter`, inside the same session that writes `Order` + `Position`). The write is wrapped in a `try / except` that logs but never re-raises — a failed market upsert must not block a trade from being recorded. Adds a shared helper `upsert_market_minimal` to `core/db.py`; extends `WeatherMarket` with an optional `end_date` field populated from Gamma's `endDate`.
**Rationale:** Smallest change that unblocks analytics. Writes only rows Bot D actually trades against, so the `markets` table doesn't bloat with the thousands of unselected weather markets. Does not touch Bot A/B/C ingest paths (zero risk to other bots). Operator feedback (`feedback_risk_vs_profit.md`): safety controls must not block profit — the try/except is the concrete embodiment of that rule for this write.
**Alternatives considered:**
- **Option 1 — widen the main ingest to cover weather.** Cleaner long-term (solves the class of problem, not just Bot D). Deferred, not rejected: larger blast radius, touches the ingest service Bot A depends on live, and Bot A's backfill work is mid-flight. Logged as OQ-028 to revisit once backfill stabilizes.
- **Dual-write inside discovery.py on every parse.** Rejected: would write thousands of markets Bot D never touches. `markets` table bloat with low analytic value.
- **Background reconciliation job.** Rejected: added complexity (another service/cron) for the same end result.
**Consequences:**
- `markets` rows written by Bot D use `condition_id = gamma_id` (numeric string from Gamma `id`/`conditionId`), different ID space from Bot A's hex `condition_id`. No row-level collision, but cross-bot queries must know about both ID spaces. Flagged as OQ-029.
- TTR analysis becomes re-runnable once ≥24h of Bot D trades carry the dual-writen row.
- If the upsert starts failing silently in volume, it has no trade-path impact, so it's easy to miss. Mitigation (follow-up, not built here): Telegram alert when the `bot_d.entry.market_upsert_failed` rate exceeds 1% of entries.

---

## ADR-023: Phase 1 three-LLM trading-audit remediation (fees parabolic, Bot E maker-only paper, cross-bot fleet cap, DB-backed calibration gate)

**Date:** 2026-04-17
**Status:** accepted
**Context:** Three-LLM audit (Gemini / GLM-5.1 / Codex) of Bots A/D/E converged on two independent P0 findings plus two Codex-only P0 findings. Meta-review in `docs/audit/bots-a-d-e-audit-responses/README.md` adjudicated the reviews and produced a phased action plan. This ADR covers Phase 1 — the must-fix-before-any-further-live-scaling work block.
**Decision:** Ship seven coordinated changes as a single work block:

1. **Fee curve parabolic.** `core/fees.py` now implements `fee_rate = feeRate × p × (1-p)` per Polymarket docs. Previous triangular shape under-charged 17–47% at every off-peak price. Economics peak corrected 0.0150 → 0.0125, mentions 0.0156 → 0.0100. Maker rebate is category-aware (crypto 20%, others 25%) and returns **0 by default** for EV/edge math (rebates are discretionary pool distributions, not guaranteed per-fill revenue). The accounting path still records nominal rebate for dashboard display.
2. **De-dup Bot D fee function.** `bots/bot_d_weather/strategy.py:_polymarket_taker_fee` now delegates to `core.fees.taker_fee_rate("weather", p)` — single source of truth.
3. **Bot E paper-mode taker override removed.** `_compute_maker_limit` ignores any `order_style_override != "maker"` and logs a warning. Paper mode now produces maker-only fills identical to live mode — calibration data is transferable.
4. **Bot E state hydration from DB.** `_hydrate_open_positions()` reads `Position WHERE bot_id='bot_e' AND status='OPEN'` on startup AND after each reconcile loop, so sizer caps operate on persisted exposure (previously only in-memory; reset to empty on every restart).
5. **Paper-trade counter is DB-backed.** `_paper_fill_count()` reads `COUNT(*) FROM trades WHERE bot_id='bot_e' AND order_id LIKE 'paper-%'` each iteration. Replaces the hardcoded `PAPER_FIXED_TRADE_USD=$30` / `PAPER_FIXED_TRADE_THRESHOLD=200` constants with `config.BOT_E_PAPER_FIXED_USD` / `BOT_E_PAPER_TRADE_THRESHOLD` env fields, counting fills (not placed orders) and persisting across restarts.
6. **Cross-bot pre-trade aggregate cap.** New module `core/fleet.py` with `check_fleet_exposure(bot_id, intended_usd)`. Reads positions + open orders across all bots atomically from the shared DB. Default deployable cap = `FLEET_WALLET_USD × FLEET_DEPLOYABLE_FRAC` (0.80). Wired into Bot A (`executor.try_enter`), Bot B (`executor.try_enter`), and Bot E (`__main__.run`) immediately before `clob.place_limit`.
7. **Bot E keystore plumbing.** `config.BOT_E_KEYSTORE_PATH` now required for live mode and must differ from the shared `polymarket_passphrase_path`. Paper mode ignores the setting. Live startup refuses (exit 2) if unset or identical.

**Rationale:** All three reviewers agreed items 1 and 3 block live graduation for Bot D and Bot E respectively. Items 4–5 were Codex-unique P0s with mechanical evidence (file/line refs in meta-review). Item 6 addresses the Session-14 repeat risk (all three P1, Codex P0). Item 7 is a security boundary — Bot E's live capital should not share a keystore with bots that can independently breach their own caps. Shipping them as a block keeps the fee/calibration/cap/keystore changes coherent; shipping independently would leave windows where, e.g., fees are parabolic but Bot E paper still uses taker fills (calibrating on numbers the parabolic math then under-costs).
**Alternatives considered:**
- **Widen the paper-mode OBI threshold to restore fill rate instead of removing the taker override.** Rejected. The taker-override's bid-derived price is the deeper bug: even if we used a real taker model, paper-live divergence at resolution-level OBI was uncalibrated. Maker-only with wider OBI threshold is the clean separation.
- **Treat maker rebate as deterministic with a 0.20–0.25 default.** Rejected per Codex AF-1 and Polymarket docs. Rebates are daily pool distributions; a per-fill EV inclusion systematically inflates modeled edge. Opt-in flag is preserved for callers that have reconciled actual rebate receipts.
- **Rebuild the per-bot aggregate cap in `core/fleet.py` and deprecate `AGGREGATE_EXPOSURE_CAP_USD` / `_GBP`.** Deferred. Keeping both layers means the per-bot cap is the bot's own defense-in-depth and the fleet cap is cross-bot. Deprecating the per-bot caps requires a migration of tests, watchdog config, and operator runbooks — out of scope for Phase 1.
- **Atomic fleet check via DB row-level lock.** Deferred. SQLite serializes writes already; operator DB is single-writer in practice. If migration to PostgreSQL happens, revisit.

**Consequences:**
- Bot D net-edge calc now uses correct fees; some paper entries that previously passed will now skip. Expected and correct.
- Bot E paper fill rate drops — that drop IS the signal (tells operator whether the maker offset is viable live). OBI threshold may need tuning downward before the 200-fill gate fires.
- `state.open_positions` hydration means cap checks no longer pass trivially after restart. Any over-sized pre-restart position will be visible to the sizer immediately.
- `core/fleet.py` adds one DB round-trip per try_enter call. Measured: negligible on SQLite local (~2ms). Will need revisit if a bot goes >100 scans/min.
- Bot E **cannot go live** until `BOT_E_KEYSTORE_PATH` is set to a distinct keystore path; paper unaffected.
- Test suite: 533 pass (fees rewritten, `test_main_loop.test_fixed_30_used_before_threshold` updated for new config field, new `tests/test_fleet.py` added with 6 cases).
- Follow-ups queued for Phase 2: seasonal RMSE, skew-normal CDF for extreme temps, narrow live entry window, correlation-adjusted crypto bucket cap, lot-based realized PnL, wire `should_halt_trailing`, EWMA OBI, recorder gap detection.

---

## ADR-024: Phase 2 three-LLM audit remediation (seasonal RMSE, skew-normal, narrow live window, correlation-adjusted cap, lot-based PnL, trailing halt wired, EWMA OBI, recorder gap detection)

**Date:** 2026-04-17
**Status:** accepted
**Context:** Phase 2 of the three-LLM trading audit (Gemini / GLM-5.1 / Codex). Phase 1 (ADR-023) shipped the P0 fixes; Phase 2 addresses the P1 reliability/accuracy issues identified in the meta-review. Goal: make Bot D defensible for live graduation and Bot E calibration-trustworthy.
**Decision:** Ship eight coordinated changes:

1. **Seasonal RMSE for Bot D.** `bots/bot_d_weather/config.py` now carries a northern/southern-hemisphere monthly multiplier table (0.70 summer → 1.40 winter). `effective_rmse_f(city_cfg, month)` returns the seasonally-adjusted RMSE. `BOT_D_RMSE_SEASONAL=true` (default). Sydney and Buenos Aires flagged `southern_hemisphere=True`.
2. **Skew-normal CDF for Bot D extreme-temp markets.** `bots/bot_d_weather/strategy.py:_range_probability_with_shape` uses `scipy.stats.skewnorm` when `BOT_D_USE_SKEW_NORMAL=true` (default), with `BOT_D_SKEW_HIGH=2.0` / `BOT_D_SKEW_LOW=-2.0`. Gaussian fallback on any scipy import error. Only applied to `temp_type in {"high","low"}` — range buckets stay Gaussian.
3. **Narrow Bot E live entry window.** `BOT_E_LIVE_ENTRY_WINDOW_MIN/MAX_SEC` default 300/600 (t-5m to t-10m). Paper mode retains the wide 180/900 window for calibration data collection. `__main__.run` selects per `is_live`.
4. **Correlation-adjusted crypto bucket cap.** Defaults tightened: `BOT_E_CRYPTO_BUCKET_CAP_FRAC` 0.15 → 0.10; `BOT_E_AGGREGATE_EXPOSURE_CAP_FRAC` 0.30 → 0.25. New `BOT_E_CRYPTO_CORRELATION_ADJ=true` + `BOT_E_CRYPTO_AVG_CORRELATION=0.80`. Sizer applies `sqrt(1 + ρ)` inflator when the candidate position introduces a new crypto symbol alongside existing ones (multi-asset correlation fold-in).
5. **Lot-based realized PnL.** `core/portfolio.py:get_realised_pnl` replaces lifetime-average-buy cost basis with per-lot FIFO matching. Each BUY becomes a distinct inventory parcel; each SELL consumes oldest parcels first. Re-entries (buy→sell→buy→sell on same token) no longer blend cost basis across rounds. Patch A (orphan-SELL skip) preserved for un-matched SELL remainders.
6. **Trailing-loss halt wired.** Bot E main loop now calls `should_halt_trailing(state, trailing_n, trailing_window)` each iteration, alongside `_is_db_halted`. A 12-of-20 losing streak with no 5-in-a-row now halts the bot (previously invisible to all halts).
7. **EWMA OBI.** `bots/bot_e_btc_scalp/signal.py:compute_obi` accepts `decay_half_life_sec` kwarg; 0 = rectangular (original), >0 = exponential weighting. Default `BOT_E_OBI_DECAY_HALF_LIFE_SEC=30`. Raw volumes still used for `min_trades`/`min_volume` gates so the decay change doesn't silently reduce signal frequency.
8. **Recorder gap detection.** `core/backtest_bot_e.py` adds `detect_gaps(db_path, max_gap_ms=5000)`, `quarantine_ranges(gaps, buffer_ms=5000)`, `in_quarantine(ts, ranges)`. A WSS reconnect with missed trades would otherwise poison calibration invisibly (meta-review M-3). Backtester callers can now exclude events that fall in quarantine windows.

**Rationale:**
- Seasonal RMSE and skew-normal are the two most impactful Bot D accuracy fixes. Reviewer evidence: 2× RMSE spread between summer/winter; upper-tail underestimation on high-temp fades. Both are config-gated so operators can A/B-test their effect in paper.
- Narrow live window + correlation-adjusted cap + lot-based PnL are all about making Bot E's calibration transferable AND its live risk accounting honest. Without lot-based PnL the second-round-trip P&L would have distorted the Bolsonaro-style re-entry already seen in Session 14 retrospective.
- Trailing halt was pre-built scaffolding that nobody wired; GLM-5.1 AF-2 caught it.
- EWMA OBI is the "free upgrade" all three reviewers flagged; rectangular window wastes signal information.
- Gap detection is preventative — the recorder has already seen one WSS reconnect, and no tooling existed to detect the data-quality impact on calibration.

**Alternatives considered:**
- **Per-city empirical RMSE from 30 days of actual forecast errors.** Correct long-term; premature at ~2 weeks of paper data. Hardcoded monthly table is the v1.
- **Full empirical distribution (per-city-per-month histogram).** More accurate than parametric skew-normal, requires 2+ years of data. Not available; skew-normal is the stepping stone.
- **Correlation estimated from live trades, not hardcoded.** Correct long-term; requires 200+ multi-asset fills. Hardcoded 0.80 is defensible from public BTC/ETH/SOL correlation stats and is an env var, so operators can re-tune.
- **Shift to Postgres for multi-writer atomic cap enforcement.** Deferred. SQLite serializes writes; single operator; not worth the migration now.
- **Rebuild `should_halt_trailing` with windowed time rather than rolling-N outcomes.** Deferred. Rolling-N matches reviewer framing (Entry 006 source); time-windowed is a v2 experiment.

**Consequences:**
- Bot D net-edge calculations will differ in winter vs summer (intentional — previously overconfident in winter). High-temp fade edges will compress under skew-normal (correct; Gaussian was inflating them).
- Bot E paper mode keeps 3-15m window (data collection); live mode narrows to 5-10m. Operators transitioning to live should expect fewer signals/day but higher win rate.
- Three-asset crypto positions that previously fit under 15/30 caps may now be rejected under 10/25 + correlation fold. This is the intended effect of Session-14 hardening.
- Realized P&L numbers on the dashboard may shift slightly after the first redeploy — the lot-based method corrects prior blended cost bases. Operator should verify against recent round-trips manually once post-deploy.
- The trailing halt will now fire on losing streaks the bot previously traded through. Expected post-deployment: some halts that operators have to manually unhalt. That's the control working as designed.
- EWMA OBI with 30s half-life will produce signals with different timing than the rectangular baseline. Calibration data collected before this change should not be mixed with post-change data without re-labelling.
- Gap-detected windows are flagged but NOT automatically excluded; the backtester caller decides. This is intentional — operator should review gap windows before deciding whether to exclude them from a specific calibration run.
- Test suite: 558 passed (up from 533 after Phase 1). New tests: 10 seasonal/skew + 15 EWMA/gap/lot/correlation.
- Follow-ups queued for Phase 3: Bot A abnormal-exit two-level system, Bot A `MIN_DAYS_TO_RESOLUTION` 14→21, Bot A `REPOST_STALE_HOURS` 6→2, METAR urban-heat-island offsets, orphan-SELL recon alert, emergency repo-wide halt flag, daily fee-schedule scraper, fleet strategy-archetype review.

---

## ADR-025: Phase 3 adversarial-audit remediation (emergency halt, fee sentinel, Bot A two-level exit + config tuning, Bot D exact-temp blacklist + UHI, cross-bot overlap, orphan-SELL alert, adverse-selection guard, gap-quarantine application, archetype monitor)

**Date:** 2026-04-17
**Status:** accepted
**Context:** Phase 3 follows the adversarial audit (2026-04-17) that rated Bot A BORDERLINE, Bot D BORDERLINE-leaning-INVALID, and Bot E INVALID. Phase 3 lands the minimum-path structural changes required to make the three-bot portfolio credible together. It does NOT validate the bots' edges — that requires paper data collection (30–90 days depending on bot) outside the scope of a code shipment.
**Decision:** Ship nine coordinated changes:

1. **Repo-wide emergency halt (`core/emergency_halt.py`)** — single flag every bot reads pre-trade. Persisted via a `HaltFlag` row with `bot_id="__ALL__"`; env var `EMERGENCY_HALT=true` overrides. Wired into `bot_a.executor.try_enter`, `bot_b.executor.try_enter`, `bot_d_weather.executor.try_enter`, and the top of `bot_e_btc_scalp.__main__.run` scan loop.
2. **Polymarket fee-schedule sentinel (`scripts/check_polymarket_fees.py`)** — fetches docs.polymarket.com/trading/fees, parses the per-category peak rates, compares against `core.fees.TAKER_FEE_RATE_BY_CATEGORY`. If geopolitics ≠ 0 OR any category drifts ≥0.5%, sets the emergency halt and exits 2 (cron-friendly). `--dry-run` for inspection.
3. **Bot A config tuning (`bots/bot_a/config.py`)** — `MIN_DAYS_TO_RESOLUTION` 14 → 21 (GLM-5.1 Q9). `REPOST_STALE_HOURS` 6 → 2 (Gemini, Codex silent).  New `REEVAL_EXIT_YES_PRICE=0.15` and `REEVAL_VOLUME_DOUBLE_MULT=2.0` for two-level abnormal exit. `ABNORMAL_EXIT_YES_PRICE` now env-overridable. `executor.should_cut_loss` takes optional entry/current volume; exits at 0.15 only when 24h volume has at least doubled since entry (genuine news-driven repricing signal).
4. **Bot D tightening (`bots/bot_d_weather/{config,discovery,strategy}.py`)** — `BOT_D_EDGE_THRESHOLD` 0.08 → 0.10. `BOT_D_BLACKLIST_EXACT_TEMP=true` default (rejects thin-liquidity 1°F-wide markets). `CityConfig.urban_heat_island_f` field; NYC=2.0, Dallas=2.0, Miami=2.0, Chicago=1.0, Atlanta=1.0. Strategy METAR branch adds the UHI offset when shifting the same-day-high mean.
5. **Cross-bot condition_id overlap (`core/fleet.detect_cross_bot_overlap`)** — scans all OPEN positions; flags any condition_id held by >1 bot with the list of bot_ids and total notional. Meta-review surfaced this as a 2× concentration masquerading as diversification.
6. **Orphan-SELL alert (`core/portfolio.detect_orphan_sells` + `emit_orphan_sell_alert`)** — FIFO-replay of trades to find un-matched SELL remainders older than `max_age_hours`. Writes `Event(event_type="portfolio.orphan_sell_alert", severity="warn")` rows for watchdog/dashboard consumption.
7. **Bot E adverse-selection guard (`bots/bot_e_btc_scalp/adverse_selection.py`)** — ring-buffer tracker of post-fill midpoint moves. `should_halt(last_n=20, adverse_threshold=0.60)` returns True when ≥60% of last 20 fills moved against the fill direction. Operator-facing halt signal: if true, either widen maker offset or stop the bot.
8. **Gap quarantine applied (`core/backtest_bot_e.iter_events` + `calibrate`)** — `quarantine` kwarg on `iter_events` skips events inside any range; `calibrate` auto-detects gaps via `detect_gaps` and passes the derived `quarantine_ranges` into the event stream. Prevents WSS-reconnect data-loss from poisoning calibration invisibly.
9. **Strategy-archetype concentration monitor (`core/fleet.archetype_exposure_breakdown` + `single_factor_alert_needed`)** — maps bots to {short_surprise, short_obi_reversion, momentum, copy} and sums notional per archetype. Alerts when any archetype ≥70% of fleet exposure. Meta-review M-1: the entire current fleet is short_surprise; the only structural fix is adding a non-fade bot.

**Rationale:** Each of the nine items maps 1:1 to a finding in the adversarial audit's "conditions for using all three" or "what I would change" blocks. Shipping them individually would leave gaps — e.g. the fee scraper is only useful if it can trigger a halt, so emergency_halt and fee scraper must ship together. Adverse-selection guard and gap-quarantine are both about making Bot E's paper calibration trustworthy; neither alone is sufficient.

**Alternatives considered:**
- **Lock deployable fraction to 0.50 instead of building cross-bot overlap detection.** Rejected. Rough cap doesn't help you see WHY the fleet is concentrated; the overlap detector is diagnostic, not throttling.
- **Put emergency halt in `core/config.py` as a setting.** Rejected. A halt must survive a process restart without config reload, hence the DB-backed path. Env-var fallback preserves operator-override without DB access.
- **Make fee-scraper scrape a GitHub mirror of the docs.** Deferred. The official docs URL is the source of truth; the script gracefully handles fetch failure.
- **Count adverse-selection at position-resolution time instead of post-fill.** Rejected. Position-resolution is a noisier signal (15-minute markets have event noise unrelated to fill quality). Post-fill midpoint is the cleanest adverse-selection metric.
- **Treat "exact X°F" markets as entries with a 0-probability model output.** Rejected. Blacklisting at parse-time is cleaner; the Gaussian/skew-normal output on a 1°F-wide bucket is dominated by model error anyway.
- **Hard-code UHI offsets rather than CityConfig field.** Rejected. The field is env-overridable by default (it's just a CityConfig mutable construct); operators will want to tune per-city once paper data accrues.

**Consequences:**
- Bot A will enter fewer trades: 21-day min cuts ~30% of the current candidate pool; 2h stale cancel means more frequent repost; two-level exit means some positions exit at 0.15 instead of 0.25.
- Bot D rejects all "exact X°F" markets; edge threshold 10% will admit fewer entries. The 11-paper-position cluster at ≥70% should rebalance or shrink.
- Cross-bot overlap will produce real alerts — Bot A and Bot B both fade tail geopolitics; overlap on the same condition_id is expected. The alert is diagnostic, not a trade blocker.
- Archetype concentration alert will fire immediately on startup because every live bot maps to `short_surprise` (the whole point of the meta-review finding M-1). This is loud and correct.
- Bot E adverse-selection guard will be silent until ≥20 fills are observed. After that, if adverse rate ≥60%, operators know the bot is losing the information game and should widen offset or stop.
- Gap-quarantine applied in calibrate: if the recorder has ANY gap >5s, the affected windows are excluded. A historical calibration run that fails under this filter indicates the recorder is losing data and needs operational attention before the number is trustworthy.
- Fee sentinel should be scheduled via systemd timer on the bot LXC container daily; on drift detection it sets the halt and every bot's next try_enter will refuse until cleared.
- Emergency halt failure-open on DB error: documented in the module's docstring. An operator who wants fail-closed can set `EMERGENCY_HALT=true` in the env as a belt-and-braces.
- Test suite: **592 passed** (up from 558 after Phase 2; +33 Phase 3, −2 rewritten for UHI + blacklist semantics).
- Nothing in Phase 3 validates actual edge. The adversarial audit's "conditions for using all three" still require 30–90 days of measured data. Phase 3 just makes that measurement honest.

---

## ADR-026: Phase 4 Bot E data-flow instrumentation (realistic maker-fill sim, per-fill Event emission, adverse-selection halt wiring, calibration-gate runner)

**Date:** 2026-04-17
**Status:** accepted
**Context:** Phase 3 made the three-bot portfolio structurally safe. Phase 4 makes Bot E's data flow honest so the 14-day go/no-go decision is decidable. Without these four items, the existing calibration was treating every OBI signal as a guaranteed fill (47 "signals" → 47 "outcomes"), producing a false-positive bias directly visible in the 97.5% predicted vs 57.9% realised win rate on the strongest OBI bucket.
**Decision:** Ship four coordinated items:

1. **Realistic maker-fill simulation in `scripts/bot_e_calibration_spike.py`.** New `simulate_maker_fills()` function: for each signal, read forward in `pm_events` for `fill_timeout_sec` (default 60s) and mark `filled=True` only if a `last_trade_price` event on the target asset has `price <= maker_limit`. `maker_limit = signal_price - 10bps`. The simulator ignores queue position (optimistic ceiling; documented). Signals extended with `asset_id_at_signal`, `signal_price`, `maker_limit`, `filled`, `fill_ts_ms`, `fill_price`.

2. **Adverse-selection measurement in the same spike.** `measure_adverse_selection()` reads the latest `last_trade_price` in `[fill_ts_ms, fill_ts_ms + 30s]` and sets `moved_against=True` if that price is below the fill price. Aggregated by `compute_fill_and_adverse_rates()`. Feeds two new decision gates in `decide()`:
   - `MIN_FILL_RATE_FOR_GO = 0.30` — blocks go-file if maker fill rate < 30%.
   - `MAX_ADVERSE_RATE_FOR_GO = 0.60` — blocks go-file if adverse rate ≥ 60%.
   JSON output gains a `fill_realism` block with the measured rates + limitations notice.

3. **Per-fill Event emission + adverse-selection halt wiring in `bots/bot_e_btc_scalp/__main__.py`.** New helper `_emit_new_fill_events_and_track(tracker)`:
   - Scans the `trades` table for rows not previously seen (module-level `_emitted_fill_trade_ids`).
   - Writes one `Event(event_type="bot_e.fill")` per new fill with payload `{trade_id, order_id, condition_id, token_id, side, fill_price, fill_size, fee_usd, midpoint_at_event_emit}`.
   - Registers each new fill with the `AdverseSelectionTracker`.
   - Measures post-fill midpoint from the recorder DB via new `_read_pm_last_trade_price(asset_id)` helper (read-only SQLite lookup on most recent `last_trade_price`).
   Called each scan after fill reconciliation. Trader then calls `tracker.should_halt(last_n=BOT_E_ADVERSE_WINDOW_N, adverse_threshold=BOT_E_ADVERSE_HALT_THRESHOLD)`; on halt, scan continues without placing new entries.
   Config: `BOT_E_ADVERSE_WINDOW_N=20`, `BOT_E_ADVERSE_HALT_THRESHOLD=0.60`.

4. **Daily calibration-gate runner `scripts/bot_e_calibration_gate.py`.** Systemd-friendly wrapper around the spike. Exits 0 on GO, 2 on NO-GO. Optional Telegram notification via `BOT_E_CALIBRATION_NOTIFY=true`.

**Rationale:** The 2026-04-16 calibration JSON on disk showed 47 signals / 53.2% WR / 0.38 ECE with no fill-realism check. Re-running the Phase 4 spike against the same recorder DB produces 22 filled signals (47% fill rate), 50.0% WR, 0.35 ECE, 22.7% adverse rate. That's the real signal: fill rate is borderline, WR is coin-flip, ECE remains overconfident. Without these instruments, any future "GO" verdict would be based on the old taker-override assumption that no longer matches the trader code. Per-fill Event emission also gives the dashboard + post-hoc analytics a clean feed without re-reading the Trade table every request.

**Alternatives considered:**
- **Model queue position explicitly.** Rejected. Would require ingesting the full order book per tick; recorder doesn't capture that depth. Optimistic fill-rate ceiling is honest and documented.
- **Measure adverse selection on book midpoint instead of last_trade_price.** Better in theory; not available without book-snapshot recording. Using last_trade_price at ~30s post-fill is a reasonable proxy.
- **Delay emission of per-fill Event until we have the adverse measurement.** Rejected. Event emission is the right signal of "fill happened"; the measurement can be added by a separate row type (`bot_e.fill_measured`) if needed later.
- **Put adverse tracker state in DB.** Rejected. In-process ring-buffer of 50 fills is small enough that a restart-induced reset takes one market session to repopulate. Persisting would require another table and a schema migration for a metric that's a near-term halt signal, not a historical record.

**Consequences:**
- Running the spike on existing recorder data (4.6h) re-produces the calibration JSON with NEW fields: `n_signals_eligible=47`, `n_signals_filled=22`, `fill_rate=0.468`, `adverse_rate=0.227`. Verdict remains NO-GO (same three reasons as before: n<200, WR<0.52, ECE>0.10). Fill rate is above the 30% floor → not yet the blocker. Adverse rate is below 60% → also not blocking. **The blocker is raw signal quality, not adverse selection.**
- Trader main loop now halts on adverse-selection AFTER ≥20 fills are observed. Before that, the gate is silent (fail-open on insufficient data, per the module's design).
- Per-fill Events will appear in the dashboard immediately after first paper fills are reconciled.
- Calibration-gate runner should be added as a daily systemd timer on the bot LXC container (example unit in the script's docstring).
- Test suite: **603 passed** (up from 592 after Phase 3; +11 Phase 4 tests).
- No live trader behavior changes until the first paper fills land; the wiring is dormant until then.

---

## ADR-027: Phase 5 Bot E signal upgrades — TTE stratification, signed CEX CVD gate, depth-at-best gate

**Date:** 2026-04-17
**Status:** accepted
**Context:** Second-opinion reviewer flagged the Bot E signal as "2024-tier" and recommended queue imbalance + signed aggressor + external signal filter. My own triage prioritized three items from that list: TTE-bucket stratification (cheapest highest-impact — forces honest live-window read on existing paper data), signed CEX CVD confirmation gate (leverages existing `cex_trades.is_buyer_maker` column to validate OBI direction against Binance flow), and a depth-at-best gate (prevents maker-order entry into thin books). Queue-imbalance feature deferred to Phase 6 — expensive and contingent on items 1-3 not killing the thesis first.
**Decision:** Ship three items:

1. **TTE stratification in `bot_e_calibration_spike.py`.** `SignalObs.min_to_expiry` already present. New `TTE_BUCKETS` (3-5min, 5-7min, 7-10min, 10-15min) + live-window aggregate (`5-10min_aggregate` = union of 5-7 and 7-10). `compute_stats` now returns per-TTE `BucketStats`. `decide()` extended with `tte_buckets` param; if the live-window bucket has n≥20 AND realised WR < MIN_REALISED_WR_FOR_GO OR ECE > MAX_ECE_FOR_GO, the go-file flips to NO-GO even if the aggregate looked fine. JSON output emits `by_tte_bucket` array.

2. **Signed CEX CVD confirmation gate.** New helpers in `bot_e_btc_scalp/__main__.py`:
   - `_read_cex_cvd(symbol, now_ms, window_sec)` — reads `cex_trades` table, computes signed notional CVD = Σ(price×size where is_buyer_maker=0) − Σ(price×size where is_buyer_maker=1) over the window.
   - `_cex_cvd_gate_ok(symbol, signal_side, now_ms)` — returns (ok, reason). Blocks when CVD magnitude ≥ BOT_E_CEX_CVD_MIN_USD AND direction disagrees with signal. Fails open on DB unreachable or CVD below threshold (insufficient evidence).
   Wired after `maybe_fire` returns a signal: if disagrees → skip entry, log `bot_e.cex_cvd_skip`.
   Config: `BOT_E_CEX_CVD_GATE=true`, `BOT_E_CEX_CVD_WINDOW_SEC=60`, `BOT_E_CEX_CVD_MIN_USD=1000`.

3. **Depth-at-best gate.** New helper `_depth_gate_ok(book, signal_side, best_price)`:
   - Sums bid-side order notional within `BOT_E_DEPTH_BAND_WIDTH` (default 5bps) of `best_price`.
   - Blocks when total < `BOT_E_DEPTH_MIN_USD` (default $500).
   - Fails open if book is None, non-dict, or levels aren't a list (defensive against MagicMock in tests, real-API weirdness in prod).
   Config: `BOT_E_DEPTH_GATE=true`, `BOT_E_DEPTH_MIN_USD=500`, `BOT_E_DEPTH_BAND_WIDTH=0.005`.

**Rationale:**
- TTE stratification is the cheapest item (~20 LoC). Without it, a paper-window-wide calibration number can falsely approve a go even when the live window itself is garbage. This plugs the paper/live mismatch gap the reviewer identified.
- CEX CVD gate is the highest-leverage signal upgrade available from EXISTING recorder data. `cex_trades.is_buyer_maker` was already captured; wiring the gate is ~100 LoC. If Polymarket OBI lags Binance CVD (the crowding hypothesis), this gate will block the lagging signals — improving precision without reducing recall below a survivable level. Concretely testable: the go-file will show how many signals were skipped for `cex_cvd_disagrees` vs `cex_cvd_confirms` vs `cex_cvd_small`.
- Depth-at-best gate addresses the fill-starvation half of the "maker-only in thin markets" problem. A 5bps-band $500-notional floor is loose; operators can tighten it.
**Alternatives considered:**
- **Queue imbalance feature (reviewer's item #1).** Deferred. ~300 LoC, needs stateful book reconstruction across reconnects. Only justified if items 1-3 don't kill the thesis first.
- **Polymarket signed aggressor inference from book + trade comparison.** Fragile; deferred.
- **Make CVD a weighted signal rather than a hard gate.** Simpler to ship as a gate; can be softened later if kill-rate is too high.
- **Tighten live entry window to 3-7 min now.** Deferred pending data. The reviewer suggested 3-7m but the actual right answer comes from TTE-stratified WR numbers we're now computing.

**Consequences:**
- Re-running the spike on existing 4.6h recorder data with Phase 5 live: 22 filled signals all in the 5-7min bucket (makes sense given entry window 300-600s). Live-window WR 0.500, ECE 0.363. Verdict NO-GO with the new live-window reasons added to the output.
- CEX CVD gate will be silent until Bot E actually fires signals. When it does, three new log lines distinguish outcomes: `bot_e.cex_cvd_skip` (disagrees), `bot_e.cex_cvd_pass` (confirms or small), and a post-hoc metric emerges from `bot_e.signal` vs `bot_e.cex_cvd_skip` event ratios.
- Depth gate will also be silent until signals fire. In thin-book regimes expect `bot_e.depth_skip` logs; operators can tune the threshold downward if too many valid opportunities are blocked.
- The two new gates reduce signal frequency by design. That's the correct side of the precision-vs-recall trade-off given current crowding concerns.
- Test suite: **618 passed** (up from 603 after Phase 4; +15 Phase 5).
- Phase 6 candidate: queue-imbalance feature from book snapshots, if items 1-3 haven't produced a kill verdict within 14 days of live data.

## ADR-028: Phase 5 follow-ups status (fee parser, Telegram notify, Bot A volume capture, test-env cleanup)

**Date:** 2026-04-17
**Status:** accepted (tracking)
**Context:** After Phase 4 deploy I flagged four items as Phase 5 candidates but not shipping. Updating status after Phase 5 ship.

**Status per item:**

- **Fee-schedule parser refinement** — NOT SHIPPED. The regex returned zero categories on the real docs page. The sentinel degrades gracefully (no false positive halt). Low priority because the fallback behavior is safe and Polymarket fee changes have public press coverage anyway. Defer to an operator session; the fix is ~20 LoC once someone samples the rendered HTML structure.
- **Telegram notify for calibration gate** — NOT SHIPPED. Stubbed behind `BOT_E_CALIBRATION_NOTIFY=true` env flag. Operator can wire `core.notify.send_telegram_alert` integration when desired. Same pattern as other bots' notifications.
- **Bot A volume-at-entry capture** — NOT SHIPPED. The two-level exit gate in `should_cut_loss` accepts optional volume fields; when omitted (current state), it defaults to hard-exit-only semantics. Wiring requires either (a) Gamma re-query at exit time, or (b) a new `positions.entry_volume_usd` column. (a) is faster; (b) is cleaner. Defer until operator picks.
- **LXC env-dependent test failures** — NOT SHIPPED. 15 tests (bot_a_sizer, bot_b_executor, test_config, test_notify) rely on test-default env vars overridden by LXC `.env`. Orthogonal cleanup; fix is to give these tests explicit monkeypatch of their env vars. Not blocking any Phase 1-5 functionality.

**Decision:** Track these in this ADR rather than the open-questions file — they're known-and-scoped follow-ups, not open design questions.

---

## ADR-029: Bot B scorer rebuilt as multi-estimator ensemble

**Date:** 2026-04-17
**Status:** accepted (scaffolding landed; estimators E2/E3/E4 pending implementation per plan)
**Context:** Bot B has been halted since Session 17. The single-point-of-failure pattern — one HTTP call to the external scorer (Oraclemangle — https://oraclemangle.com), response-parsed locally — has been the gating risk item for unhalting. External review of the method analysis in `docs/session-2026-04-17-edges-review.md` identified method 5.1 (multi-estimator ensemble) as the highest-leverage upgrade available to the fleet.
**Decision:** Replace Bot B's single-scorer with a 4-estimator ensemble:
- **E1 — HistoricalBaseRateEstimator** (non-LLM). Buckets resolved UMA markets by `(category, price_bucket, dtr_bucket)`, returns Beta(2,2)-shrunk YES-rate. Structural independence guarantor.
- **E2 — OraclemangleEstimator** (refactor of existing `http_scorer.py`; wraps the external scorer at https://oraclemangle.com). Returns EstimatorOutput; parse failure raises `EstimatorAbstainError` rather than returning 0.5.
- **E3 — LocalSentimentEstimator** (local-qwen35, privacy-preserving). Bootstrap-disabled pending independence validation with E2.
- **E4 — WalletFlowEstimator** (reads Bot F Mirror aggregates as probability prior, not timing signal). Bootstrap-disabled pending F-2 `crowd_signals` table.

Ensemble logic: weighted mean (Brier-inverse-square weights, 0.05 floor, renormalized), weighted-variance gate (abstain if > 0.03), output passed through Calibrator (Identity bootstrap → Platt after 50+ resolutions → Isotonic if Platt MAE > 0.02).
**Rationale:** Independence of votes is the whole point. Without a non-LLM vote, the ensemble is four variants of one model. Variance gate catches genuine uncertainty rather than false-confidence averaging. Calibrator applied once at output rather than per-estimator.
**Alternatives considered:**
- Keep single scorer + add circuit breaker (half-measure; doesn't address probability-source fragility).
- Rebuild as a single re-trained scorer (rejected — longer work, loses Bot F rehabilitation angle).
- Bayesian model averaging (rejected — adds complexity without empirical precedent in this domain).
**Consequences:**
- `bots/bot_b/scorer_ensemble/` module landed this session; 30 tests passing.
- Existing `http_scorer.py` remains in place until E2 refactor lands; Bot B stays halted.
- Unhalt gate (existing `docs/bot-b-scorer-rebuild-plan.md`) augmented: Brier ≤ 0.12 on held-out 2026 resolutions, per-estimator ≤ 0.18 or weight ≤ 0.05, variance gate rejects ≥ 15% of candidates (sanity), Platt residual MAE < 0.02.
- `WeightTracker` persists predictions to a new `scorer_predictions` SQLite table; weekly batch job (to land with E2) reconciles against resolutions.
- Quarter-Kelly sizing unchanged; ensemble improves probability input only.

---

## ADR-030: Bot E archived — spread-capture POC decisively failed

**Date:** 2026-04-17
**Status:** superseded by ADR-037 (2026-04-22)
**Context:** External reviewer critiqued the Bot E vol-harvest pivot draft (docs/session-2026-04-17-edges-review.md §3.2) on three grounds: (1) vol-harvest framing mathematically incoherent, (2) sizing formula inverted creating directional exposure, (3) fill-rate asymmetry on binaries likely fatal absent sub-10ms infra. Agreed on all three. Pivoted plan to a 1-day POC gate on the existing recorder dataset.
**Decision:** POC ran as `scripts/bot_e_poc_recorder.py` against `data/bot_e_recorder.db`. Results in `docs/bot-e-poc-results.md`. All three gates fail:
- Q1 (universe): 4 qualifying markets vs scaled threshold of 20.
- Q2 (early-window fraction): nominally passes (0.505 vs 0.30) but on a statistically meaningless 4-market base.
- Q3 (fill asymmetry): infinite (winner fill rate 0.0). Not adverse selection — NO fills on either side in the thin-spread regime.

Structural finding: a market-efficient equilibrium means high-liquidity markets have no sub-threshold spread, and low-liquidity markets with sub-threshold spread have no taker flow to fill our passive bids. The 4 "qualifying" markets had min sum-bid of 0.01, 0.10, 0.56, 0.57 — degenerate post-uncertainty cases with zero trades.

**Archive Bot E**. Kill date 2026-06-30 unchanged. Bot E recorder service continues running (cheap sensor; data asset retained for future theses). Bot E1 trader code under `bots/bot_e_btc_scalp/` stays in repo (history valuable) but marked deprecated via CLAUDE.md.

No second pivot; any future Bot E resurrection requires a new ADR with a new thesis.
**Rationale:** Structural failure is stronger than the reviewer's original "adverse selection" concern. The trap is empty — there are no fills to be adversely selected. Reviewer's critique saves both a 2-week build and a paper-trading cycle on a broken strategy.
**Alternatives considered:** Re-run POC after 30 more days of recorder data (rejected — structural efficient-market mechanism is unlikely to reverse with more samples; recorder stays live so Q3 2026 re-run is cheap if we ever need it). Narrow to mins 0–5 only (already in revised spec; POC confirms even this is moot because the qualifying universe is empty regardless of lifecycle window).
**Consequences:**
- `docs/bot-e-vol-harvest-thesis.md` and `docs/session-2026-04-17-edges-review.md` §3.2 superseded.
- Revised full-backtest spec (§5.3 of session doc) is never built.
- OQ-037 resolved (current `core/backtest_bot_e.py::calibrate` does not separate winner/loser fill, and is a stub — moot given archive).
- One week of Bot E revised-backtest work reclaimed; reallocated to Bot B ensemble acceleration.

---

## ADR-031: Fleet-wide exec-policy — dynamic limit-ladder + toxicity filter

**Date:** 2026-04-17
**Status:** accepted (scaffolding landed; per-bot integration pending)
**Context:** Session doc §3.3 identified method 2.1 (passive limit-order execution) as an existing fleet baseline but underoptimized. Two upgrades proposed: dynamic replacement ladder (step + cancel stale limits) and toxicity filter (block placement / freeze limits during hostile aggressive flow).
**Decision:** New module `core/exec_policy.py` provides two primitives:
- `compute_toxicity(flow, intended_side) -> float` — ratio of aggressive flow against our side to total aggressive flow. Pure function.
- `next_ladder_action(limit, book, flow, atr, policy, now_ts) -> (state, new_price)` — state machine over `PLACED / STEP_1 / STEP_2 / FROZEN / CANCELLED`. Priority: freeze on high tox > book-move cancel > age-cancel > age-stepping.
- `LadderManager` — in-memory per-bot manager, cancel-storm breaker tripped at > 30 cancels / 5 min.

Default off fleet-wide (`EXEC_POLICY_ENABLED=false`). Enable on Bot A paper first; measure cost-basis delta over 7 days; if > +20 bps, roll to B (post-unhalt), C, D.
**Rationale:** Pure-function design keeps bot executors small and policy unit-testable. Toxicity metric borrowed from sports-betting-line adverse-selection literature; thresholds (0.70 freeze / 0.80 block) are priors to tune (OQ-035). Cancel-storm breaker prevents a mis-tuned policy from storming the CLOB.
**Alternatives considered:**
- Bake into each bot executor (rejected — N² bug surface).
- Centralize in `core/clob.py` wrapper (rejected — CLOB wrapper must stay thin per existing design).
- Skip toxicity filter, ship only ladder (rejected — toxicity is the adverse-selection guard, not optional).
**Consequences:**
- 28 tests passing. Module is imported nowhere yet (default off; bot wiring pending).
- Per-bot config additions required (`BOT_A_EXEC_POLICY_ENABLED` etc.).
- Dashboard additions planned: per-bot fill rate, ladder step count, toxicity-block rejection count.

---

## ADR-032: Bot F rehabilitation — estimator supplier + crowd-signal producer

**Date:** 2026-04-17
**Status:** accepted (planning; no code shipped in this session)
**Context:** Bot F Phase 2 Trigger was cancelled 2026-04-17 because local signals exceeded a 90s freshness cutoff for execution timing (ecosystem too crowded). The Hunter + Mirror data pipeline remains valuable for non-timing uses.
**Decision:** Repurpose Bot F outputs:
1. `bots/bot_f/estimator.py` (NEW) — exposes Mirror-aggregated wallet flow as a probability estimator (EstimatorOutput) consumable by Bot B's ensemble (E4 slot). 90s freshness cutoff is irrelevant for probability priors.
2. `bots/bot_f/crowd_signals.py` (NEW) — daily cron over Mirror data. Emits `CrowdCascade` rows to a new `crowd_signals` table: `(market_id, cascade_start_ts, n_wallets, dominant_side, gross_usd, price_move_bps)`. Cascade defined as ≥ 6 copy-bot wallets moving same-side on same market within 60s.
3. Bot A / Bot D filter consumers: if same-direction cascade within 6h, halve size or skip (front-run-fade avoidance).

No trading execution added. Phase 2 Trigger remains cancelled. Hunter classifier must pass on cascade participants (bots only, not humans).
**Rationale:** Data asset has value; the cancelled path was execution timing, not data itself. Rehab is cheap (3 days) and unlocks Bot B's E4 estimator plus Bot A/D filter hardening.
**Alternatives considered:**
- Archive Bot F entirely (rejected — data asset already captured, cost to keep running is low).
- Resurrect Phase 2 Trigger with relaxed freshness (rejected — original cancellation reason is structural, not tunable).
- Build cascade-fade mini-bot ("G-fade") as a counter-trade — deferred; needs 30 days of cascade data first.
**Consequences:**
- Supersedes the 2026-04-17 Bot F Phase 2 cancellation (Phase 2 Trigger stays cancelled; non-timing uses are NEW scope).
- Bot B ensemble E4 gated on this landing.
- Bot A/D filter changes are additive; kept behind feature flags until validated.

---

## ADR-033: Bot A archived — walk-forward disproves net-PnL thesis

**Date:** 2026-04-18
**Status:** accepted
**Context:** Bot A was the original mechanical longshot-fade bet: NO-side fade on geopolitics/politics/finance/economics markets with `yes_price ≤ 0.05`, DTR 21-180 days, 93-96% hit-rate spec estimate. Session 17g accelerated hardening (two-level exit, 21-day DTR, stale-repost). OQ-030 (live-fills reconcile) had kept realised PnL provisional.

Session 17j's 2026-04-18 walk-forward backtest against the public SII-WANGZJ / Polymarket_data dataset (`docs/bot-a-walkforward-wangzj-2026-04-18.md`) produced a decisive verdict:

- 12,521 simulated entries — larger than Bot A could ever collect in live operation.
- Hit rate 93.7% — thesis spec satisfied.
- Mean PnL per trade −$1.09. Total PnL −$13,613.58. Max drawdown $13,666.58.
- Every entry-price bucket negative (00c through 05c), every category bucket negative including fee-free geopolitics (−2.42% mean edge, −$388 on 535 trades).

The thesis failure mode is **asymmetric loss**, not calibration. At 5% entry prices, a win returns ~5% on notional; a full-loss returns −100%. The 1-in-16 loss dominates the 15 × 5% wins arithmetically, even before fees. No tuning of filters, sizing, or fee-category mix within the current entry slice can produce net positive PnL.

**Decision:** Archive Bot A effective 2026-04-18.

1. **In-tree archival via env flag.** `BOT_A_ARCHIVED=true` is default in `bots/bot_a/__main__.py` and `bots/bot_a/shadow_main.py`; both daemons early-exit at startup. Watchdog's `dispatch_cancel("bot_a")` skips `exec_a.cancel_all()` when the flag is set. Code, tests, and imports remain untouched so a future revert is a single env-var flip plus systemd re-enable.

2. **Systemd units disabled on the bot LXC container.** Operator action (not in-session): `systemctl disable --now polymarket-bot-a.service polymarket-bot-a-shadow.service`. Open positions are left to resolve; no force-close.

3. **Archetype mapping retained.** `core.fleet.BOT_ARCHETYPE["bot_a"]` unchanged so historical `archetype_exposure_breakdown` queries over pre-archive Position rows still resolve.

4. **Bankroll reallocated.** £200 freed; operator-directed reallocation to Bot C thesis work (Phase 1) and Bot E E-2 replacement model (Phase 1).

**Rationale:**

- 12,521 entries is an empirical verdict, not a small-sample artefact. The walk-forward is a superset of anything the live bot could produce in months.
- Hit-rate-based success criteria in `docs/kill-dates.md` were reading the wrong column. The PnL column is decisive.
- Keeping an unprofitable paper bot running burns compute, skews fleet concentration metrics (`short_surprise` archetype dominance), and produces operational noise (95 drawdown kill events in 12h on 2026-04-16 per production sitrep).

**Alternatives considered:**

- **Keep running paper-only for more data.** Rejected. The walk-forward already captures more data than paper could. Paper is informative when evidence is sparse; here it's oversupplied.
- **Tune the filter (e.g. sub-1c geopolitics only).** Rejected as current-session action, held as reversal path. The walk-forward sliced by bucket (00c through 05c) and category — 00c geopolitics was the closest to break-even but still negative. A narrower slice may work but needs its own walk-forward before any resurrection.
- **Keep shadow running for ongoing comparison.** Rejected. Shadow mirrors live state; no value comparing live-stopped to paper-on. Archiving both keeps the "restore from one env flip" contract.
- **Hard delete code.** Rejected. The restoration path (narrower slice, ML filter, fee-schedule change) is credible enough to keep the code warm.

**Reversal criteria (explicit):**

1. Fresh walk-forward on a narrower entry slice (or different market mix) producing net PnL > 0 after fees + 2% slippage, on ≥ 1,000 simulated trades.
2. OR a structural Polymarket fee-schedule change that inverts the fee math.
3. OR an ML-based filter that demonstrably removes the 1-in-16 full-loss case in the SII-WANGZJ historical data.

Any of the above requires a new ADR logging the reversal, the positive-PnL walk-forward doc, and a 2-week paper-mode gate before live.

**Consequences:**

- Fleet reduces to Bot B (halted, Phase 2), Bot C (paper, thesis Phase 1), Bot D (paper, waiting for resolutions), Bot E (paper, Phase 1 E-2 model build), Bot F (sensor). All four live tracks except Bot D are research-track, pre-revenue.
- Fleet archetype concentration rebalances toward `momentum_obi` (Bot E) + TBD (Bot C, once thesis written), breaking the all-short_surprise pattern flagged in the Session 17j meta-review.
- `docs/kill-dates.md` Bot A section rewritten. Review cadence retained for Bot B/C/D/E.

---

## ADR-034: Bot C archived — Pyth infra broken + thin market universe

**Date:** 2026-04-18
**Status:** accepted
**Context:** Session 17m P1.1 Phase 1 work required a Bot C thesis doc + backtest by 2026-04-22 (Pyth Pro trial expiry). Writing the thesis doc surfaced two decisive production findings:

1. **Pyth ingest silently broken since 2026-04-15 17:37 UTC.** Journalctl on `polymarket-bot-c.service` shows `pro: connection error: server rejected WebSocket connection: HTTP 502` at 17:37:46; subsequent reconnects never recovered. `HB pro=no-ticks hermes=disabled` heartbeat has fired every 30 seconds for 72 hours. Bot continues scanning Gamma and evaluating markets, but using **stale cached spot** — AAPL frozen at 264.90509 across multiple scans before crash. Pyth Pro trial was due to expire 2026-04-22; likely already revoked server-side.

2. **Market universe structurally thin.** Gamma scans return **3 parseable traditional-asset candidates per scan** at 2026-04-18 21:47; pre-crash snapshots on 2026-04-15 returned 10. `bots/bot_c_pyth/discovery.py::parse_question` only matches a narrow question-phrasing template. Best-case 10 candidates/scan × 3–5 filtered = ~2–5 actionable markets at any moment; at 10 trades/week (all filters clean + Pyth fixed) the 30-trade paper-gate criterion takes 3+ weeks, pushing the verdict past Pyth Pro expiry.

**Decision:** Archive Bot C effective 2026-04-18 using the ADR-033 pattern:

1. `BOT_C_ARCHIVED=true` default env flag in `bots/bot_c_pyth/__main__.py`. `main()` early-exits with a loud warning before touching Pyth / Gamma. Restoration is one env flip.
2. the bot LXC container systemd action (not in-session): `systemctl disable --now polymarket-bot-c.service`.
3. Retain code, tests, and `core/fleet.BOT_ARCHETYPE` entry so historical DB queries resolve and restoration requires no refactor.
4. Cancel Pyth Pro subscription post-2026-04-22 (operator action); Hermes free-tier path in `core/polymarket_v2.py` remains available if restoration is attempted.
5. Retained analyst/ingest code + 7,015 PythBarPro rows + 12,336 PythTickRecent rows from 2026-04-15 17:11–17:36 as dataset asset.

**Rationale:**

- Thin market universe is not fixable by tuning — it's a structural limit on Polymarket's traditional-asset market listings. The `parse_question` regex could be widened, but that's a 1-week sprint and doesn't change the underlying fact that Polymarket's strike-priced markets are a niche listing category.
- Pyth infra fix is a separate 1-day diagnosis (auth revalidation, WSS reconnect hardening, fallback to Hermes) — justifiable if market universe were adequate, not on current state.
- Operator's data-collection priority (Phase 1) is better served by P1.2 Bot E ML replacement model and P1.3 Bot F cascades cron, both of which have working data pipelines and higher trade cadence ceilings.

**Alternatives considered:**

- **1-week infra-fix sprint: diagnose Pyth + widen parse_question + bump bankroll.** Rejected for this session; held as operator-approvable alternative if they want to invest the week.
- **Let Bot C keep running on stale spot.** Rejected — evaluating with stale spot produces zero signal value (`model=0.000` or `1.000` on every market per logs) and still burns compute.
- **Archive cleanly with hard code delete.** Rejected. Pattern-match ADR-033: retain code for restoration, low maintenance cost.

**Reversal criteria (explicit):**

1. New thesis doc showing either (a) a market-universe expansion path, e.g. scraping a broader set of strike-priced markets from Polymarket plus Kalshi, or (b) a variant thesis (not Pyth-GBM) that the existing code could serve.
2. Backtest on whatever data source is chosen showing positive net EV after fees on ≥ 30 simulated trades.
3. Demonstrably working Pyth or Hermes ingest with > 1 week of continuous bar data.

**Consequences:**

- Fleet after ADR-034: **Bot B** (halted, Phase 2), **Bot D** (paper, waiting), **Bot E** (paper, Phase 1 ML), **Bot F** (sensor, Phase 1 cascades). Three live research tracks, one waiting.
- `docs/kill-dates.md` Bot C section updated to ARCHIVED. Review cadence removed.
- Pyth Pro monthly cost freed at expiry (operator decision: cancel renewal).
- Phase 1 reduces from 4 parallel work streams to 2 (Bot E + Bot F) plus passive Bot D observation.

## ADR-035: Paper-mode position reconciliation via Gamma resolution poll

**Date:** 2026-04-19
**Status:** accepted
**Context:** Session 17r-ext surfaced the Bot D counterpart of the Session 17n Bot E cleanup: 22 OPEN paper positions on `bot_d`, 17 of which had `markets.end_date` in the past (2026-04-17 through 2026-04-19) and 3 of which were orphaned with NULL `end_date`. Paper mode never triggers the on-chain `on_redeem` path, and `simulate_paper_fills` only closes via SELL fills that are never issued for markets that have already resolved on-chain. Without loop-level reconciliation, paper positions accumulate OPEN indefinitely past resolution, inflating fleet-cap exposure and hiding realised P&L.

The Session 17n Bot E cleanup was manual SQL (see CHANGELOG 2026-04-19, Session 17n entry). The `RESOLVED_DB_CLEANUP` status string referenced in prior audits (`audit/security-audit-2026-04-18.md` L-3, `docs/audit/4d4c1be-full-repo-audit-codex-2026-04-18.md` M-1) turned out to exist only in CHANGELOG prose — Codex confirmed it has no code-side cleanup function. This ADR replaces the manual-SQL pattern with a loop-level settlement path.

**Decision:** Add `Portfolio.reconcile_paper_resolutions(bot_id)` that polls Gamma for each OPEN position's condition_id, and synthesises a SELL at the settlement price (`$1.00` for the winning token, `$0.00` for the losing token) via `on_fill`, which closes the Position via the existing SELL path and writes a Trade row for FIFO P&L.

1. Core method lives in `core/portfolio.py` next to `simulate_paper_fills`.
2. Synthetic trades use `paper-resolve-<position_id>` prefix (distinct from `paper-fill-` and `synth-paper-fill-`) so calibration analytics can filter.
3. Each settlement emits a `portfolio.paper_resolve` Event with position_id, settle price, cost basis, and size.
4. Wired into `bots/bot_d_weather/__main__.py` on an hourly cadence via `BOT_D_PAPER_RESOLVE_INTERVAL_S` (default 3600s). One Gamma call per OPEN position; cheap on public Gamma.
5. CLI wrapper `scripts/reconcile_paper_resolutions.py --bot-id bot_d [--execute]` for one-shot LXC runs. Dry-run by default.
6. Orphan positions (no Market row + Gamma cannot resolve) emit `portfolio.paper_resolve.orphan` warn events but are left OPEN — upstream ingest gap is tracked separately.

**Rationale:**

- Gamma is the canonical public source for market resolution status; polling it avoids needing the keystore or CLOB in paper mode.
- Synthesising a SELL at settlement price is the cleanest fit for existing FIFO P&L — `get_realised_pnl` does not need to change.
- Hourly cadence is adequate: Polymarket UMA resolution has a multi-hour dispute window, and positions resolving a few hours late does not affect research validity.
- Scoped to Bot D in this session per operator directive (don't touch bot_b, Bot E paper state is preserved per `current_state.md`). Bot E / bot_a_shadow / bot_b_shadow can be wired by flipping `BOT_X_PAPER_RESOLVE_INTERVAL_S` and adding the 6-line main-loop snippet in a follow-up.

**Alternatives considered:**

- **Mark stale OPENs as `RESOLVED_DB_CLEANUP` without settling.** Rejected: loses Bot D's kill-date signal (`≥ 15 resolved positions at 1.25% fees` per `bots/bot_d_weather/CLAUDE.md`), which depends on realised P&L being measurable.
- **Derive settlement from `markets.yes_price` under the assumption it converges to 1/0 post-resolution.** Rejected: Gamma ingest filters on `closed=false`, so the cached `yes_price` is the last pre-resolution quote, not the settlement.
- **Nightly cron instead of in-loop.** Rejected: in-loop is simpler ops and already has FX rate + DB session plumbing warm.

**Reversal criteria:**

- Gamma begins returning unreliable `outcomePrices` for resolved markets (e.g. post-V2 migration hides them), in which case fall back to on-chain CTF `payoutDenominator` via web3.
- Operator finds the hourly cadence produces visible-in-dashboard settlement lag that materially affects research. Bump cadence or switch to an event-driven trigger.

**Consequences:**

- Bot D `get_open_exposure` returns real active cost basis, not stale OPENs. Fleet-cap accounting becomes honest.
- Bot D `get_realised_pnl` incorporates settled outcomes within ~1h of Gamma close — kill-date measurement at 2026-05-31 becomes data-driven rather than a manual-SQL artefact.
- Pattern is reusable: Bot E, bot_a_shadow, bot_b_shadow can adopt the same 6-line main-loop integration when operator greenlights.

## ADR-036: Bot Longshot Fade (G) — near-resolution cheap-side entries on crypto Up/Down

**Date:** 2026-04-20
**Status:** accepted

**Context:**

Session 17s (autonomous sweep) built a unified 3-strategy backtest (`scripts/backtest_strategies.py`) on 766 resolved 15-min/5-min crypto Up/Down markets in the Bot E recorder DB. Results:

| Strategy | Closed | WR | ROI |
|---|---|---|---|
| OBI Scalp (Bot E v1-like) | 173 | 37.0% | **−27.65%** |
| Longshot Fade | 52 | 7.7% | **+2006.83%** |
| Cross-Asset Correlation Arb | 19 | 21.1% | −15.63% |

Full methodology, caveats, and per-fill audit in `docs/backtest-three-methods-2026-04-20.md`.

The Longshot Fade thesis: in the final ~60 seconds before resolution, Polymarket's losing side routinely trades at ≤2¢ while the actual tail probability of a last-second CEX reversal is meaningfully non-zero (~5-10% empirically). Buying the cheap side for $5 notional produces 4 wins × ~$752 that cover 48 losses × $2.85 with room to spare.

**Decision:** Ship Longshot Fade as **Bot G**, a separate bot in paper mode:

- `bots/bot_g_longshot/` (new module)
- Env config: `BOT_G_*` prefix (`FIXED_TRADE_USD=5`, `MAX_ENTRY_PRICE=0.02`, `ENTRY_SECONDS_BEFORE_RES=60`, `MIN_BOOK_SIZE=20`)
- Risk caps: `MAX_CONCURRENT_POSITIONS=10`, `MAX_DAILY_ENTRIES=100`, rolling-ROI kill-switch (≥100% over last 100 closed)
- Depends on the Bot E recorder DB (read-only); no own WSS or CEX feed
- Settles via `Portfolio.reconcile_paper_resolutions` hourly (ADR-035)
- Deployed as `polymarket-bot-g-longshot.service` on the bot LXC container

**Rationale:**

- **Separate bot, not Bot E variant.** Different entry window (t-60s vs t-2 to t-15min), different thesis (tail lotto vs directional drift), different risk profile (asymmetric payoff vs symmetric). Merging would complicate both.
- **≤2¢ threshold and 60s window chosen from backtest.** Operator explicitly asked for Grok review (see `docs/grok-prompt-longshot-crypto-updown.md`) to get external input on threshold tuning before live scaling.
- **$5 fixed trade size** matches backtest assumptions and limits per-trade max loss to ≤$5.
- **Paper-only v0.** Operator directive: always paper until ≥50 closed live paper fills show ROI ≥ +200% (lower bar than backtest's +2007% to absorb fee/slippage).

**Alternatives considered:**

- **Fold into Bot E as a mode.** Rejected — mixing OBI directional logic with longshot tail logic in one daemon makes ops and kill-switches muddy. Clean separation is cheap.
- **Higher entry threshold (e.g. ≤5¢).** Deferred to Grok input / post-50-trade review. Backtest threshold was 2¢.
- **Keep as backtest-only until Grok review lands.** Rejected — shipping the bot in paper mode lets us collect live-paper-fill data in parallel with the Grok review; both converge to the same decision.

**Reversal criteria:**

- Live-paper realised ROI < +200% on ≥ 50 closed trades → archive.
- Win rate < 5% on ≥ 100 closed trades → archive (edge evaporated, likely market-makers pulled quotes).
- Max drawdown > $100 in any 24h → halt and re-evaluate.

**Consequences:**

- Fleet after ADR-036: **Bot B** (halted, LLM+RAG), **Bot D** (paper, weather-fade), **Bot E** (paper, OBI scalp — retained for live-data collection despite backtest bleed), **Bot F** (sensor, whale/cascade), **Bot G** (paper, longshot fade).
- Zero additional infra cost — Bot G piggybacks on Bot E recorder.
- Per-trade max loss capped at $5 (the fixed trade size).
- Day-1 scale: $100/day deployed risk cap.

---

## ADR-037: Bot E un-archived for paper data-collection and tuning

**Date:** 2026-04-22
**Status:** accepted (supersedes ADR-030; extends ADR-022)
**Context:** ADR-030 (2026-04-17) archived Bot E1 trader after the spread-capture POC failed and the OBI calibration returned WR=0.500 on 22 signals. Sometime in the following days the `polymarket-bot-e-trader.service` was restarted on the bot LXC container for continued paper data collection (ADR-036 side-note: "Bot E retained for live-data collection despite backtest bleed"). This left a documentation/reality gap: the module CLAUDE.md still says "ARCHIVED — do not resume development" while the bot has since produced 69 closed paper trades at **56.5% FIFO-matched win rate, net +$12.68 realised**. This ADR formally records the un-archive and reframes Bot E's purpose.
**Decision:**
Bot E1 (`bots/bot_e_btc_scalp/`) is **un-archived for paper trading only**. Not live-money; the kill-date in ADR-022 / ADR-030 (2026-06-30) is unchanged. The bot exists to collect calibrated live-data and validate tuning hypotheses against the recorder DB, not to scale to live capital.

- Module `CLAUDE.md` status line updated from "ARCHIVED" → "PAPER / tuning-phase".
- `BOT_E_ENV=paper` remains the invariant; any live flip requires a new ADR.
- OK to add config knobs and filter changes that the 69-trade data supports, subject to paper backtests before deploy.

Immediate tuning actions authorised by this ADR (based on 2026-04-22 drill-down, n=69):
- **`BOT_E_MAX_SHARES_PER_POSITION = 15`** — caps a 68-share outlier that cost $30 (17% of all losses from one trade).
- **`BOT_E_MIN_ENTRY_PRICE = 0.40`** — drops [0.0, 0.4) bucket (25% WR, n=4) to focus on the [0.4, 0.6) bread-and-butter bucket (56% WR, n=61).

**Rationale:** The original archive was based on 22 signals. 69 trades is a 3× sample that shows a thin but real edge (WR 56.5%, net positive after fees). Archiving a paper bot that is generating signal for free would forfeit the research value. The tuning parameters are not a new thesis — they are guards against tail-sizing risk and a low-SNR entry bucket that the data identifies empirically.
**Alternatives considered:**
- Keep archived, delete the systemd unit (rejected — discards free signal + live paper P&L data that the original ADR-030 had no visibility into).
- Graduate Bot E to live capital now (rejected — 69 trades is far short of the 300-trade paper gate in ADR-022).
- Write a brand-new Bot (Bot H/I) using the same OBI recorder (rejected — no need, existing code works and has live data attached).
**Consequences:**
- Module CLAUDE.md updated, ADR-030 shows as superseded.
- Bot E1 status across fleet docs: PAPER / tuning-phase.
- Config tuning below is the first landing; future tuning follows the same "drill-down → ADR amendment → deploy" discipline.
- Kill date and live-gate criteria from ADR-022 remain binding.

## ADR-038: Polymarket taker fee formula — remove double-price multiplier

**Date:** 2026-04-22
**Status:** accepted
**Context:** Codex fleet review (`docs/audit/codex-fleet-review-2026-04-22.md`, Section A #7) flagged that `core/fees.py` computed `fee_usd = baseRate × size × price² × (1-price)` instead of the official Polymarket formula `fee_usd = C × feeRate × p × (1-p)`. Verified against `docs.polymarket.com/trading/fees` (WebFetch 2026-04-22): the parabolic value `baseRate × p × (1-p)` is **fee in USDC per share**, not a fraction of notional. The prior implementation labelled it as a rate and multiplied by `notional = price × size`, double-counting price. Understatement = 50% at p=0.50, 95% at p=0.05. Every bot's EV filter, P&L, and graduation gate was affected; Bot D and Bot G (cheap-side strategies) were hit hardest.
**Decision:**
Canonical fee API is now `taker_fee_per_share(p, category) → Decimal` — the USDC charged per share. Callers multiply by shares (not notional):
```python
gross_fee = size * taker_fee_per_share(p, category)
```
Legacy `taker_fee_rate` remains as an alias returning the same numeric value; only the semantic label and the `fee_for_fill` / `round_trip_cost_rate` / maker-rebate call sites changed.

Files touched:
- `core/fees.py` — renamed function, fixed `fee_for_fill`, `round_trip_cost_rate`, `maker_rebate_per_share`. Kept legacy names as aliases.
- `bots/bot_d_weather/strategy.py` — removed the `fee_per_share = fee_rate * entry_price` multiplication (the old U-15 comment described the wrong direction of bug and has been rewritten).
- `tests/test_fees.py` — updated `fee_for_fill` and `round_trip_cost_rate` assertions to the corrected values (e.g. 100 crypto shares at p=0.5: $1.80 USDC, up from $0.90).

**Rationale:** The official Polymarket doc formula and the parabolic "peak 1.80% for crypto" phrase are consistent once interpreted as "1.80% of max payout at p=0.5" (i.e. 1.80¢ per share on $1-resolution shares). The prior code also satisfied the 1.80% peak if one interprets it as "1.80% of notional at p=0.5", but a WebFetch of the docs returned the explicit `fee = C × feeRate × p × (1-p)` formula. Empirical match of doc wording + formula resolves the ambiguity.
**Alternatives considered:**
- Keep the old interpretation and argue Codex misread the docs (rejected — WebFetch confirmed Codex).
- Rename everywhere + remove the legacy alias (rejected — churn in 2 caller sites with no behaviour upside).
- Introduce an opt-in flag so old behaviour is preserved for backtests (rejected — old behaviour was a bug; backtest replays should rerun under the corrected formula).
**Consequences:**
- All active bots' realised P&L becomes more negative (or less positive) on non-0.50-priced fills because previously-unaccounted fees now hit the books. Biggest swing on Bot G (cheap-side) and Bot D (NO tails near 0.95).
- Graduation gate tests tied to paper EV must be re-run against corrected fees before any live-graduation decision. Folded into roadmap item E1/E2.
- Bot B's edge threshold (8pt divergence) becomes ~1.5pt less effective at extreme prices; operator should revisit after the ensemble E2 estimator lands.
- Fee-schedule sentinel `scripts/check_polymarket_fees.py` unchanged — it compares peak values which are invariant under the rename.

## ADR-039: GLM-5.1 fleet-review remediation (paper_override read-only, dashboard auth, adverse-selection docstring, snapshot_daily single-call)

**Date:** 2026-04-22
**Status:** accepted
**Context:** `docs/audit/glm-5.1-fleet-review-2026-04-22.md` ran independently of Codex against the same prompt. It surfaced 5 real bugs Codex missed. Four are inexpensive safety / correctness fixes and are shipped here; one (cost_basis/FIFO split brain) blocks on an operator-canonical-method decision and is deferred to the to-do list in `docs/audit/fleet-review-2026-04-22-triangulation.md`. Triangulation doc is the durable record.
**Decision:** Ship as one ADR because all four fixes are Class-A real-money-adjacent safety or correctness items with no interdependencies and no controversial trade-offs. Each has a regression test in `tests/test_glm_review_fixes.py`.

1. **`ClobWrapper.paper_override` is read-only after construction** (V1 and V2). Setter raises `PermissionError` with an explicit "construct a new wrapper" message. Prior code exposed the attribute as plain mutable state, so any imported wrapper reference could flip `paper_override = False` and flip a paper bot live at runtime. No legitimate caller mutates the attribute post-init (verified via grep across all bots + tests).
2. **Dashboard auth hardens the empty-string bypass and timing-unsafe compare.** `DASHBOARD_API_KEY=""` now emits a one-shot WARNING while still treating empty as "auth disabled" (backwards-compat for existing deploy scripts). `supplied == key` replaced with `hmac.compare_digest(...)` to kill the timing side-channel. Unset behaviour (no env var → loopback-only) unchanged.
3. **Bot E `adverse_selection.measure` docstring + code alignment.** Code was correct under the same-side convention the call-site uses; the old docstring incorrectly said BUY_NO adverse means "rose" and the inline comment contradicted the docstring. Rewrote docstring to match the same-side convention; collapsed the two identical branches into one. Call-site today hardcodes `fill_side="BUY_YES"` so the logic is dead code until Bot E gets a BUY_NO entry path, but the correction is defensive.
4. **`Portfolio.snapshot_daily` no longer double-replays FIFO.** Added optional `realised_pnl` / `unrealised_pnl` kwargs to `get_drawdown_pct`; `snapshot_daily` now passes them so the full FIFO trade history is replayed exactly once per snapshot instead of twice. Backwards-compatible: omitting the kwargs reproduces the old behaviour. Performance win scales with Bot E's trade count.

**Rationale:** Each fix is a one-to-two-hour change with an obvious safety or correctness payoff. Batching them in one ADR reduces commit overhead without hiding any controversial decision. The `paper_override` read-only choice in particular is defensive-programming best practice for a real-money switch — if a future code path legitimately needs to "toggle" paper mode, it can build a new wrapper instance, which is 3 lines of code.
**Alternatives considered:**
- Make `paper_override` mutable but log on every change (rejected — logs get ignored; a hard-stop `PermissionError` is a louder signal).
- Keep `DASHBOARD_API_KEY=""` silent (rejected — users debugging "why does my key not work?" need to see the warning).
- Leave the adverse-selection branches duplicated but correct (rejected — two identical branches are a maintenance trap for the next reader).
- Cache `get_realised_pnl` at the Portfolio level instead of passing kwargs (rejected — cache invalidation on fills is a whole new state machine; kwargs are surgical).
**Consequences:**
- Any caller that happened to mutate `paper_override` post-init now raises at runtime. Audited: none in repo. If this breaks downstream, the error message is the instruction for how to fix it.
- Dashboard deploys that exported `DASHBOARD_API_KEY=""` now see a WARNING line on first request; behaviour otherwise identical.
- `snapshot_daily` is ~2× faster for bots with large trade history. Dashboard snapshots already run on-demand, so no cron tuning needed.
- Triangulation doc `docs/audit/fleet-review-2026-04-22-triangulation.md` captures the full to-do list. Future sessions read that, not the raw reviews.

## ADR-040: Session 22 fleet-review cleanup — fee reconcile, canonical bot registry, wallet masking, misc correctness

**Date:** 2026-04-22
**Status:** accepted
**Context:** After the Session 20 (Codex) and Session 21 (GLM-5.1) remediations, the triangulation doc's to-do list had a stack of items that were mechanically clear but had been grouped as "deferred" either because they needed empirical verification, touched multiple callers, or were architectural clean-ups. This ADR batches what turned out to be doable in one autonomous session. Items still pending after this land are listed in the Consequences section.

**Decision:** Shipped as one ADR because none of these items is independently interesting enough for its own ADR, and together they retire roughly half of the triangulation doc's Part 7 to-do list.

1. **A3 `clob.py` / `clob_v2.py` live-trade fee reconcile.** Replaced the flat `fee_rate_bps × price × size / 10000` formula with a `core/fees.py::fee_for_fill` call keyed on category (looked up via Market row by token_id). Empirical verification: WebFetch of `docs.polymarket.com/trading/fees` confirmed feeRate is a decimal fraction (0.072 for crypto) used in the parabolic formula `fee = C × feeRate × p × (1-p)`. The SDK's `fee_rate_bps` field is stored on `Order` objects as integer-bps (base_rate × 10000) per `py_clob_client_v2.clob_types`. Ignoring the trade-response field entirely and computing from our canonical category map removes the unit-ambiguity risk and fixes the missing `(1-p)` factor in one move.

2. **A8 fee-rate dict deduplication.** `config.py::FEE_RATE_BY_CATEGORY_BPS` is now DERIVED from `core/fees.py::TAKER_FEE_RATE_BY_CATEGORY` at import time (`baseRate × 10000`). Crypto went from 72 (which under the /10000 convention was 0.72%, 10× too low) to 720 (0.072 = 7.20% baseRate = 1.80% peak, matching Polymarket docs). Downstream: `ingest.py` still writes `fee_rate_bps` to `Market.fee_rate_bps` from this dict; values will now shift 10× higher on next ingest. Dashboard / sizer consumers that read `fee_rate_bps` directly get the correct scale.

3. **Canonical bot registry.** New `core/bot_registry.py` is the single source of truth for every bot's `bot_id`, `archetype`, `systemd_unit`, `status`, `bankroll_env`, and `include_in_cap` membership. `core/fleet.py::known_bots` and `BOT_ARCHETYPE` are now derived from the registry; `bots/watchdog_daemon.py` cancel-wrapper coverage tuple is too. Adding a bot is now one entry in `REGISTRY` instead of patches to five files. `test_bot_registry.py` asserts the contract with 8 regression tests.

4. **A-12 paper synthetic-fill default flipped to false.** `PAPER_NO_BOOK_SYNTH_FILLS` now defaults to `"false"`. Bot E/G microstructure calibration relies on honest fill realism; the old default-true permitted synth fills and contaminated graduation metrics. Opt-in for legacy Bot A/B archived paths via `PAPER_NO_BOOK_SYNTH_FILLS=true`. Three existing tests updated to opt in where they exercise the fallback path.

5. **A-17 Bot C duplicate-order guard widened.** `has_open_order` now checks `("OPEN", "PAPER_OPEN", "PARTIAL", "PAPER_PARTIAL", "live")` instead of just `("OPEN", "PAPER_OPEN")`. Polymarket's CLOB sets resting orders to `live`; partial-fill statuses were also slipping through, letting Bot C double-enter markets.

6. **A-18 Orphan-SELL alert idempotency.** `emit_orphan_sell_alert` now hashes `(bot_id, trade_id, side, filled_at)` into a 16-char dedup key stored on the alert's payload and skips re-emission if the key already exists. Prior behaviour fired the same alert every scan (the known 8× repeat noise). Return value is now the count of NEW emissions, not total orphans.

7. **A-16 wallet masking.** `bots/notify_daemon.py` log line now emits `0xABCD…1234` instead of the full address. Wrap/unwrap scripts default to the masked form too; full address only when `--show-full-address` is explicitly passed. The dashboard was already masked by default (`DASHBOARD_SHOW_FULL_WALLET=1` opt-in), so no change there.

**Rationale:** Each item is a small, bounded correctness or safety improvement. Batching them avoids 7 separate commits. All have regression tests. All are backwards-compatible where possible (synth-fill default is the one behaviour change that affects existing paper runs — flagged in CHANGELOG with migration note).

**Alternatives considered:**
- Keep the `clob.py` flat-fee formula and just add the `(1-p)` factor (rejected — ambiguous unit of `fee_rate_bps` from API makes it fragile; canonical category lookup is more defensible).
- Leave `FEE_RATE_BY_CATEGORY_BPS` as a separate hand-maintained dict and add a sanity-check test (rejected — the drift already happened once at 10× scale; a test would have caught the NEXT drift but not the current one).
- Put the bot registry in a TOML file (rejected — Python module gives type hints and lets shadows/sensors carry behaviour flags like `include_in_cap`).

**Consequences:**

*Landed items retire these triangulation-doc to-do entries:* D-2 (A3 fix), D-3 (A8 dedup), Codex A-12 (synth default), A-17 (Bot C guard), A-18 (orphan-SELL), A-16 (wallet masking), Codex Section C first-pass of canonical registry (remaining: shell-script and markdown-doc migration).

*Still deferred, unchanged from triangulation doc:*
- ~~D-1 / A2 cost_basis vs FIFO split brain (blocked on OQ-041 G2).~~ **Amended 2026-04-23 (see below) — actually shipped.**
- ~~D-4 / A9 reconcile transaction wrap (determined NOT a practical bug: `on_fill` is idempotent by `trade_id`, so the "double-apply on crash" scenario is self-healing — noted in Session 22 CHANGELOG for future-me).~~ **Amended 2026-04-23 (see below) — actually shipped.**
- D-5 Bot D tail-cap disposition (blocked on OQ-041 G3).
- V2 migration smoke test, recorder stall root cause, 6 analytical pursuits — all unchanged.

*Behaviour change requiring operator awareness:*
- `PAPER_NO_BOOK_SYNTH_FILLS` default flip may cause open paper orders on stale-book tokens to stop filling on next scan. Set `PAPER_NO_BOOK_SYNTH_FILLS=true` in the LXC `.env` if you want the old behaviour on Bot A/B archived paths.
- `Market.fee_rate_bps` values for newly-ingested markets jump 10× (72 → 720 for crypto etc.). Any downstream query that treats this as "max percentage × 10000" now gets correct scale; anything treating it as "percentage of notional × 100" was already wrong.

### Amendment 2026-04-23 — two additional changes also shipped in commit 0097bd6

During the post-deploy audit on 2026-04-23 (see `docs/audit/fleet-review-2026-04-23-execution.md` and CHANGELOG Session 22b), two changes were verified on `main` that the original ADR text above said were deferred. Both went in via commit `0097bd6` alongside the items explicitly listed; they arrived from a parallel Claude session's edits to `core/portfolio.py` that were picked up when the Session 22 commit was staged. This amendment acknowledges them so the ADR and the code agree.

**1. A2 cost_basis ↔ FIFO unification — SHIPPED (unintentional but correct).**

`core/portfolio.py::_apply_to_position` no longer uses average-cost reduction on SELL. After each SELL that doesn't close the whole position, it replays the token's full BUY/SELL trade history through a FIFO lot queue and recomputes `pos.cost_basis_usd` and `pos.avg_price` from the remaining open lots. The ORIGINAL ADR said this was blocked on OQ-041 G2 (FIFO vs average-cost operator pick). The parallel session picked FIFO unilaterally.

- **Alignment with the rest of the system:** consistent. `get_realised_pnl` was already FIFO (Session 17s). Dashboard `cost_basis_usd` display now agrees with realised-P&L accounting.
- **HMRC posture:** FIFO is the correct choice for UK tax reporting (matches the logging Bot B/D already produce). No regression.
- **Behaviour on existing positions:** no immediate change until the next SELL against any multi-BUY token. When it fires, the recomputation overwrites the stored average-cost figure with the FIFO figure. That's expected.
- **Operator call G2 in OQ-041 is now answered by the code** — FIFO is canonical. Kept in the operator-question list for explicit acknowledgement but no longer blocks anything.

**2. A9 reconcile_live_fills transaction wrap — SHIPPED.**

`core/portfolio.py::reconcile_live_fills` now wraps the per-trade `on_fill` loop in `s.begin_nested()`. The ORIGINAL ADR reasoned this was a non-bug because `on_fill` is idempotent by `trade_id`. That reasoning is still valid — replay was already safe. The wrap doesn't change correctness; it adds defense-in-depth (atomic cursor-advance + fill-apply).

- **No behaviour change** on the happy path or any normal replay path.
- **Benefit:** removes one more class of "what if SQLite locked mid-loop" edge case from the threat model. Zero cost.
- **No revert needed.**

**Net:** the original ADR text above should be read as reflecting what Session 22 was SCOPED to ship. The amendment reflects what actually landed. No regression tests broke (1,052 green at Session 22, 1,054 at Session 22b). If a future session reverts either change, that's a separate architectural discussion — these amendments document the state of `main` as-of `bf718ad`.

## ADR-041: Session 22 post-deploy ops fixes — heartbeat, permanent-failed detection, second orphan-dedup

**Date:** 2026-04-23
**Status:** accepted
**Context:** Session 22 deploy to the bot LXC container surfaced three observability / alerting gaps discovered during the same-day fleet audit.
1. Bot G was silent for 11 hours because its `bot_g.scan` log only fires when `markets_in_window > 0`. That silence masked the Bot E recorder's death on 2026-04-21 22:34 UTC — recorder sat in systemd `failed` state for 31 hours, Bot G silently consumed an empty `markets` table, no alert fired.
2. The existing `_check_recorder_freshness` correctly flagged the stale DB but the alert message didn't say "systemctl reset-failed + restart", leaving the operator without an actionable recovery command for the permanent-failed case.
3. `reconcile_paper_resolutions` emits `portfolio.paper_resolve.orphan` events once per reconcile cycle per orphan position. Bot D has 3 long-standing orphans (positions 81/82/83) generating ~72 events/day of identical noise. Session 22 Codex A-18 fix only covered `emit_orphan_sell_alert`, not this second orphan path.

**Decision:** Ship three surgical fixes together.

1. **Bot G heartbeat log.** `bots/bot_g_longshot/__main__.py` now emits `bot_g.scan_empty open=%d daily=%d` at INFO every ~300s (throttled via `run_loop._last_empty_scan_log` monotonic attribute) when `markets_in_window == 0`. Makes the "bot alive but no candidates" state distinguishable from "bot hung or recorder dead" without spamming the journal on every 10s tick.

2. **Watchdog actionable recovery instructions.** `core/watchdog.py::_check_recorder_freshness` now probes `systemctl is-failed polymarket-bot-e-recorder.service` via subprocess when heartbeat staleness triggers. If the service is in `failed` state, the alert message includes the recovery command `systemctl reset-failed polymarket-bot-e-recorder && systemctl restart polymarket-bot-e-recorder`. Subprocess call is best-effort — any exception silently degrades to the prior alert message.

3. **Second orphan-dedup path.** `reconcile_paper_resolutions` now hashes `(bot_id, position_id, UTC_date)` into a 16-char dedup key and checks existing events before emitting. A position that stays orphan fires at most one alert per UTC day per position instead of once per reconcile cycle. Complements Codex A-18 which covered `emit_orphan_sell_alert`.

**Rationale:** All three were symptom-level fixes for the same day's incident. Batching keeps the change surface minimal and the rationale coherent in one ADR. Regression tests in `tests/test_session22_ops.py`.
**Alternatives considered:**
- Auto-reset-failed + restart from the watchdog (rejected — watchdog runs as `bot`, doesn't have privileges for system-level `systemctl` commands without a sudoers rule; alert-only is the right scope).
- Log every Bot G empty scan at DEBUG instead of throttled INFO (rejected — DEBUG isn't captured in default journal; the ops value is visibility at INFO).
- Use a separate deduplication table instead of hashing into the event payload (rejected — event payload is already indexed by event_type + bot_id; hash check is O(daily orphan count), fine).
**Consequences:**
- LXC `polymarket-bot-g-longshot.service` logs one heartbeat every ~5 min even during quiet-market periods. Net log volume: still lower than Bot E trader.
- Future recorder permanent-failed incidents surface as a Telegram alert (via notify_daemon) with the recovery command in the message body. Operator can execute without cross-referencing runbooks.
- Bot D orphan-SELL noise drops from ~72/day to 3/day (once per orphan per day) until the underlying ingest bug is fixed.

## ADR-042: OQ-047 paper-only tactical rollout for Bots C/D/F/G

**Date:** 2026-04-24
**Status:** accepted
**Context:** Session 25's tactical review identified four code-level blockers
distorting paper measurement across Bots C/D/F/G. The operator asked whether
the changes would make the bots profitable, then explicitly approved trying
the rollout. Profitability is not knowable from the code change alone; the
decision here is to remove measurement and lifecycle blockers while keeping
all affected bots in paper mode.

**Decision:** Ship the OQ-047 bundle as a paper-only tactical rollout.

1. **Bot G counterparty floor derives from entry ceiling.** The default
   `BOT_G_MIN_COUNTERPARTY_PRICE` is now `max(0.85, 1 - max_entry - 0.04)`.
   With the current 8c ceiling, this admits `0.08/0.88` books that the old
   fixed 0.90 floor rejected.
2. **Bot C filled-position exits.** `BotCExecutor.review_open_positions()`
   writes synthetic SELL fills when a fresh decision shows the held side's
   edge has collapsed below 2% or flipped negative. `analyst.py` calls this
   after open-order review.
3. **Bot D tail sizing.** Tail cap defaults move from a hard 30% floor to a
   configurable 60% floor for 5c-and-cheaper tickets, interpolating back to
   full size at 20c. Cap factor is logged when applied.
4. **Bot F mirror fill realism.** BUY copies use the current recorder ask
   when the ask is within 2c of the whale print. Crossing paper BUYs are
   eagerly filled into `Position` rows; copies outside the slippage band are
   skipped.

**Rationale:** These are measurement-correctness changes, not live-money
graduation. Bot C needed an exit leg before any forward EV data could be
trusted. Bot G's fixed purity floor contradicted the existing 8c tune. Bot
D's cap suppressed the reviewed profitable subtype while still leaving a
tail-risk guard in place. Bot F's executor could not evaluate trailing stops
or copy slippage without Positions.

**Alternatives considered:**
- Leave Bot F sensor-only (rejected for now because the operator asked to try
  the rollout and the paper-only fill path is bounded by a 2c slippage guard).
- Remove Bot D tail cap entirely (rejected because payoff concentration is
  still real; 60% is a conservative measurement step).
- Set Bot G counterparty floor to 0.85 unconditionally (rejected because it
  weakens the near-certainty-pair thesis more than needed for the 8c tune).

**Consequences:**
- No live-money path changes. Bot F still hard-requires
  `BOT_F_MIRROR_ENV=paper`; Bot G/C/D retain their existing paper/live guards.
- Paper trade count may rise for Bot G and Bot D. That is intentional, but
  forward P&L must be bucketed by this ADR before considering live promotion.
- OQ-047 remains open until forward paper data validates entry rate, exit
  behavior, tail-bucket EV, and Bot F fill-rate/slippage.

## ADR-043: Bot D wave-regime sizing instead of broad isolated-tail sizing

**Date:** 2026-04-24
**Status:** accepted
**Context:** Session 31/32 review of Bot D concluded that the raw
SII-WANGZJ cheap-tail fade is not profitable by itself: high win rate, but
negative expectancy after the rare full-loss tail is included. Prior audits
also converged on the same mechanism: Bot D's apparent profit came from a
clustered weather cohort, not a persistent isolated-tail edge. The operator
rejected demotion and asked for changes aimed at profitability.

**Decision:** Keep Bot D active, but distinguish wave regimes from isolated
tails.

1. After one-bet-per-event, Bot D groups tradeable decisions by
   `(date, temp_type, side)`.
2. Groups with at least `BOT_D_WAVE_MIN_MARKETS=3` are `wave` entries and
   keep `BOT_D_WAVE_SIZE_FACTOR=1.00`.
3. Non-wave decisions are not disabled. They are `isolated` entries sized
   by `BOT_D_ISOLATED_SIZE_FACTOR=0.50`, preserving data collection while
   cutting the known bleed source.
4. `BOT_D_REQUIRE_WAVE_FOR_ENTRY=false` by default. It is available for
   replay or a future stricter paper experiment, but not the default.
5. The historical Bot D backtest path now has wave-selection flags so this
   decision can be tested against `data/backtest.db` variants.

**Rationale:** Trading less often at full size is acceptable if it improves
expectancy. Isolated weather tails are the failure mode identified by both
Codex and GLM reviews; clustered same-direction model/market disagreement is
the plausible edge. A hybrid design avoids the operator's concern that Bot D
would simply stop trading while still reducing exposure to low-conviction
isolated tails.

**Alternatives considered:**
- Keep the Session 28 tail-cap relaxation only (rejected — it increases
  exposure to both waves and isolated tails, which does not address the
  documented -EV isolated regime).
- Require waves and drop all isolated entries (rejected as the default
  because it slows data collection too much and the operator explicitly asked
  not to demote Bot D).
- Remove tail caps entirely (rejected — single-market payoff concentration
  remains real and the Lagos trade is exactly the risk shape we need to
  control).

**Consequences:**
- Bot D paper entries now carry `regime`, `wave_count`, and
  `size_multiplier` in decision/executor logs.
- Isolated entries may fall below Polymarket minimum share size more often;
  those are skipped by the existing `below_min_size` guard.
- No live-money decision is implied. Live graduation still requires V2
  readiness, explicit operator approval, and forward EV proof excluding
  the largest 1-2 wins.

## ADR-044: Bot G parallel paper cohorts for jackpot vs scalp attribution

**Date:** 2026-04-24
**Status:** accepted
**Context:** Session 31 found Bot G has liveness but not proven positive
EV. Existing Bot G logic already models two regimes: a higher-variance
jackpot thesis around cheaper entries and a closer-to-expiry scalp thesis.
Running one shared `bot_g` ledger makes it hard to tell whether any
positive P&L comes from a repeatable regime or from one lottery-style win.

**Decision:** Add and run paper split variants for Bot G:

1. `bot_g_jackpot` uses the same code with `BOT_G_ID_OVERRIDE`, a <=3c
   entry ceiling, and t=60s jackpot mode only.
2. `bot_g_scalp` uses the same code with `BOT_G_ID_OVERRIDE`, a <=5c
   entry ceiling, and t=30s scalp mode only.
3. The split systemd units explicitly disable the opposite mode. This is
   required because the base Bot G config can run both modes in one
   process.
4. Both split services run paper/dry-run only. They are attribution and
   measurement tools, not a live-money graduation.

**Rationale:** If Bot G has an edge, it will show up as a cohort-specific
P&L distribution, not as one blended longshot ledger. Separate bot IDs make
P&L, exposure, halt flags, and post-hoc analysis clean without duplicating
strategy code.

**Alternatives considered:**
- Keep one `bot_g` process and infer mode from order tags (rejected because
  Position/Trade/PnL ledgers still blend capital and drawdown).
- Replace the original Bot G service with one tuned variant (rejected
  because that discards baseline comparison data).
- Run both regimes inside the existing `bot_g` process only (rejected
  because the shared ledger keeps drawdown and ROI attribution muddy).

**Consequences:**
- Bot G now has three paper cohorts available for comparison:
  `bot_g`, `bot_g_jackpot`, and `bot_g_scalp`.
- OQ-051 tracks the empirical proof requirement. No tuning increase or
  live-capital argument is valid until a split cohort is positive after
  excluding the largest 1-2 wins.
- the bot LXC container was verified running `polymarket-bot-g-jackpot.service` and
  `polymarket-bot-g-scalp.service` in paper/dry-run mode at 2026-04-24
  19:20 UTC.
- No wallet action or live order was performed in this session.

## ADR-045: Seven-bot deployment posture - fix Bot D before any live capital

**Date:** 2026-04-24
**Status:** accepted
**Context:** The operator requested a full seven-bot deployment-readiness
audit with external Polymarket research and an investment-committee style
decision. The objective was fastest realistic path to positive
risk-adjusted ROI, not fastest possible live deployment. The audit found
that no bot is safe for live capital today. Bot D has the clearest
near-term edge source, but live execution is blocked by synthetic exit
accounting, incomplete V2 migration, fail-open fleet exposure behavior, and
forward EV proof requirements.

**Decision:** Do not deploy any bot live now. Focus next engineering work
on Bot D safety fixes, then paper trade Bot D through a strict forward gate.

1. Bot D is the first focus for ROI because its weather edge is externally
   modelable, lower-fee than crypto, and recently improved by wave-regime
   sizing.
2. Bot D cannot receive live capital until OQ-052 live-exit integrity,
   OQ-034 V2 migration, fail-closed fleet caps, and forward paper EV gates
   are resolved.
3. Bot E and Bot G remain paper-only comparison/tournament candidates.
4. Bot F remains sensor-only.
5. Bot B remains halted until scorer health and calibration are fixed.
6. Bot A remains archived; Bot C remains low-priority paper/research.

**Rationale:** Bot D has the shortest path where the blockers are concrete
engineering and validation work rather than a new strategy invention. Bot E
and Bot G can produce data quickly, but their current live edge depends on
fragile fill assumptions. Bot B may have the highest long-term alpha ceiling
if external-scorer calibration (https://oraclemangle.com) is restored, but it
is not the shortest reliable ROI path today.

**Alternatives considered:**
- Deploy Bot D now with tiny capital (rejected because local synthetic
  exits can hide real wallet exposure).
- Deploy Bot G now because the old backtest looked excellent (rejected
  because current paper evidence is negative and fee-adjusted cheap-tail EV
  is unproven).
- Deploy Bot E now because it is high cadence (rejected because recent
  fill evidence is poor and CVD/depth gates fail open).
- Rebuild Bot B first (rejected for fastest-ROI path because scorer
  reliability and calibration are unresolved).

**Consequences:**
- The five Session 34 audit docs are the canonical deployment review for
  this decision.
- OQ-052 tracks Bot D live-exit integrity.
- Any future live proposal should start by showing the Stage 0/1/2 gates in
  `docs/audit/live-deployment-readiness-checklist-2026-04-24.md` are
  satisfied.
- No wallet action, live order, deployment, or key change was performed.

## ADR-046: Bot D live exits must be real CLOB SELL orders, not synthetic fills

**Date:** 2026-04-25
**Status:** accepted
**Context:** ADR-045 selected Bot D as the first ROI focus, but Session 34
identified OQ-052: Bot D could close local `Position` rows by writing
synthetic SELL trades when edge decayed or flipped. That behavior is useful
for paper accounting, but unsafe in live mode because it can make the DB
report a flat position while the wallet still holds outcome tokens.

**Decision:** Split Bot D exit semantics by mode.

1. Paper mode may synthesize SELL fills through `Portfolio.on_fill()` for
   edge-decay, edge-flip, and paper settlement accounting.
2. Live mode must place a real CLOB SELL order for the held token and keep
   the `Position` open until fill reconciliation imports the real fill.
3. Live exit attempts must emit Events for placed, skipped, failed, and
   below-min-size outcomes.
4. Paper-resolution reconciliation must only run in paper mode.
5. Fleet exposure checks must fail closed in live mode when the snapshot is
   unavailable or the deployable cap is nonpositive.

**Rationale:** Live accounting must be proven by exchange fills, not local
intent. A resting or failed SELL order is still risk; closing the local
position before the exchange fill hides that risk and can lead to duplicate
exposure, false P&L, and failed operator decisions.

**Alternatives considered:**
- Keep synthetic live exits but alert (rejected because alerts do not fix
  false accounting).
- Use FAK/FOK live exits immediately (deferred because response/fill
  semantics need V2 live smoke testing; GTC SELL is safer for Phase 0).
- Disable Bot D exits in live entirely (rejected because edge-flip risk
  remains unbounded).

**Consequences:**
- Bot D live exits now create SELL `Order` rows rather than SELL `Trade`
  rows.
- Realized P&L only changes after `Portfolio.reconcile_live_fills()` sees
  the exchange fill.
- OQ-052 is partially implemented but remains open for dashboard/Telegram
  exposure-mismatch alerting and the operator runbook.
- The implementation was deployed to the the bot LXC container Bot D paper runtime after
  tests passed. No wallet action, live order, live-capital mode switch, or
  key change was performed.

## ADR-047: Watchdog cancel routing defaults to per-bot registry status

**Date:** 2026-04-25
**Status:** accepted
**Context:** Session 37 recovered `polymarket-watchdog` after it had been
dead since 2026-04-20. Once restarted, the process loaded global
`POLYMARKET_ENV=live` but did not inherit each bot's per-service paper env
vars, so its cancel wrappers initially treated paper services such as Bot
C, Bot D, Bot E, Bot F mirror, and Bot G variants as live routes. The
watchdog was stopped immediately before leaving that unsafe routing active.

**Decision:** Watchdog cancel routing must derive paper/live mode in this
order:

1. Explicit per-bot env var inside the watchdog process.
2. Variant-aware shared env mapping (`bot_f_mirror` -> `BOT_F_MIRROR_ENV`
   / `BOT_F_ENV`; Bot G variants -> `BOT_G_ENV`).
3. Canonical `core.bot_registry` status, where anything not marked `live`
   is treated as paper.
4. Global `POLYMARKET_ENV` only for unknown bot IDs.

The watchdog only loads the hot-wallet keystore when at least one cancel
route resolves to live. Bot A and Bot B also receive per-bot CLOB wrappers
instead of a shared global wrapper.

**Rationale:** A watchdog is a safety system, not a strategy process. Its
default failure mode must avoid sending live cancel traffic for paper bots
when service-local env state is absent. The registry is the canonical fleet
metadata and is safer than global live mode for mixed paper/live operation.

**Alternatives considered:**
- Add all per-bot env vars to the watchdog unit only (rejected because any
  future bot variant could repeat the same omission).
- Require the keystore whenever global `POLYMARKET_ENV=live` is set
  (rejected because an all-paper fleet would then lose the kill-switch when
  the runtime passphrase file is missing).
- Keep global fallback first and rely on operator review (rejected because
  the issue only appears after restart and can silently misroute safety
  actions).

**Consequences:**
- Mixed fleets can keep global `POLYMARKET_ENV=live` while paper bots
  remain protected from live cancel routing.
- Watchdog can run for an all-paper fleet without keystore/passphrase
  availability.
- Live graduation of any bot still requires its explicit per-bot env or
  registry status to be changed deliberately.
- The patch was deployed to the bot LXC container after local and container tests passed.
  No wallet action, live order, live-capital mode switch, or key change was
  performed.

## ADR-048: Polymarket V2 live cutover uses ClobWrapperV2 fleet-wide

**Date:** 2026-04-28
**Status:** accepted
**Context:** Polymarket V2 is now live. The official migration docs state
that V1 SDKs are not backward-compatible after cutover and that pre-cutover
open orders were wiped. Session 40 found concrete V2 wrapper and operations
gaps that had to be fixed before applying the import flip: wrong
`get_clob_market_info` endpoint, V1-shaped V2 cancel payloads, V1 USDC.e
approval targeting, and no local cleanup path for wiped pre-cutover open
orders.

**Decision:** Route all bot/script `ClobWrapper` imports through
`core.clob_v2.ClobWrapperV2` now that V2 is live. Keep the legacy
`core/clob.py` and `py-clob-client` dependency temporarily for tests,
preflight compatibility, and rollback inspection, but do not use V1 wrapper
imports in bot/script startup paths.

**Rationale:** Running bots against V1 after 2026-04-28 11:00 UTC is a hard
failure mode. The V2 wrapper now matches the official endpoint and SDK
payload shapes for the audited gaps, and the repo has a dry-run default DB
cleanup tool for open rows wiped by Polymarket's migration.

**Alternatives considered:**
- Leave import flip until after LXC deploy prep (rejected because local main
  would still start paper bots through dead V1 routes after cutover).
- Remove `py-clob-client` immediately (deferred until at least 24h clean V2
  runtime because legacy wrapper/tests/preflight still use it for controlled
  compatibility checks).
- Execute on-chain pUSD approvals or live smoke in this session (rejected
  without explicit operator approval because wallet approvals and live orders
  touch real funds).

**Consequences:**
- All bot/script startup paths that used `ClobWrapper` now instantiate the V2
  wrapper under the same import alias.
- `scripts/approve_polymarket.py` targets pUSD and V2 exchanges, not USDC.e
  and V1 exchanges.
- Pre-cutover live/open DB cleanup is available through
  `scripts/mark_cutover_cancelled_orders.py`, defaulting to dry-run.
- The V2 source overlay was deployed to the bot LXC container, all 14 `polymarket-*`
  services restarted active, and committed post-cutover V2 preflight passed.
- `core.notify` was hardened in the same session to suppress `httpx` URL
  logging after historical journald logs exposed the Telegram bot token.
- Remaining OQ-034 work is operational: verify builder code, wrap pUSD, run
  V2 approvals, and only run live smoke after explicit operator approval.
- Remaining OQ-057 work is operator-owned Telegram token rotation.

## ADR-049: Bot E recorder uses priority/control-plane queue plus bulk drop-on-full

**Date:** 2026-04-29
**Status:** accepted
**Context:** After Polymarket V2 cutover, Bot E recorder input rate jumped
from ~70 events/sec pre-cutover to thousands/sec during peak bursts. The
first mitigation, raising `RecorderState.write_queue` from 50,000 to
200,000 slots in `7a5829d`, failed in production: the queue filled, DB
timestamps went stale by ~10 hours, and the process stayed alive at high CPU.
The old subscription-state leak was absent; the remaining failure was
backpressure coupling raw event tape to liveness and subscription
reconciliation.

**Decision:** Keep a single SQLite writer, but split recorder ingestion into
two queues:

1. A high-priority queue for liveness/control-plane rows: heartbeats and
   discovery status.
2. A bulk queue for PM/CEX/market tape that uses best-effort drop-on-full
   with explicit counters.

Discovery must reconcile stale subscriptions before any best-effort DB
enqueue. The writer drains priority rows first, then bulk rows in larger
chunks, with 5,000-row / 0.5 s flush behavior and `recorder.writer_metrics`
telemetry.

**Rationale:** The recorder's first duty is to stay operationally truthful:
heartbeats, subscription audits, and stale-sub cleanup must keep moving even
when raw tape exceeds SQLite's instantaneous drain rate. Preserving every
raw event by blocking the event loop is worse than explicitly dropping bulk
tape under overload, because it causes false liveness, stale DB windows, and
watchdog halts. Multiple SQLite writers are not the primary fix because
SQLite still serializes write transactions and would mostly move the
bottleneck into lock contention.

**Alternatives considered:**
- Increase the queue again (rejected because 200,000 slots already failed;
  a larger buffer only delays saturation under sustained intake/drain
  mismatch).
- Add multiple SQLite writer tasks (rejected as the standalone fix because
  SQLite serializes writes).
- Immediately move raw tape to a new storage engine (deferred; the priority
  queue plus larger flushes should be measured first, and the migration has a
  larger blast radius).
- Drop all PM events under load without counters (rejected because silent
  loss would poison Bot E calibration).

**Consequences:**
- Under overload, Bot E recorder may lose raw PM/CEX/market tape, but loss is
  counted and logged as `recorder.write_queue_drop`.
- Heartbeats and discovery status have a separate path, reducing false
  `recorder.freshness` halts.
- Subscription reconciliation can continue even when the bulk queue is full.
- Bot E calibration windows must exclude any interval with non-zero drop
  counters.
- If queue depth or drops recur during the 24h soak, the next step is event
  thinning or moving raw tape to an append-friendly sink.

## ADR-050: V2 wallet migration completed on-chain (Session 44)

**Date:** 2026-04-29
**Status:** accepted
**Context:** Session 41 flipped the bot fleet to `ClobWrapperV2` and
verified V2 connectivity at the API layer, but explicitly deferred all
on-chain wallet operations: the hot wallet still held USDC.e, had no pUSD
balance, and had zero allowances on the V2 CTF / NegRisk exchanges. The bots
were V2 in software but V1-shaped on chain — any V2 order would route to V2
contracts and revert at settlement because pUSD was not held and not
authorized for transfer.

**Decision:** Execute the wallet migration in this session under explicit
operator approval, with a smoke-first ordering:

1. Smoke wrap: `scripts/wrap_usdce_to_pusd.py --amount-usd 5 --execute` to
   verify the `CollateralOnramp` path on mainnet with a small amount before
   committing the full balance.
2. Bulk wrap: `--all` once the smoke wrap confirmed 1:1 ratio, no fee, and
   correct recipient.
3. V2 approvals: `scripts/approve_polymarket.py --execute` to set MAX pUSD
   allowances to both V2 exchanges and `setApprovalForAll(true)` on
   `ConditionalTokens` for both V2 exchanges.
4. End-to-end smoke: `scripts/dry_run_order.py --mainnet` to place an
   unfillable BUY (price 0.01, well below mid) on a non-neg-risk binary
   market and immediately cancel — confirms the full V2 path
   (signing → auth → order routing → cancel) works against the new approvals.

**Rationale:** The smoke-then-bulk ordering keeps any first-time
misconfiguration cost capped at $5. Doing approvals second avoids the
case where the wallet held pUSD but couldn't actually spend it, and doing
the round-trip last verifies the approvals beyond a static balance/allowance
read. Running the full sequence in one session minimizes the time the
fleet sits in the V2-software-but-V1-onchain mixed state where any
accidental order fills would revert.

**Alternatives considered:**
- Wrap via the Polymarket UI (rejected: UK geo-block on the operator's
  network without VPN; the bot LXC container is already VPN'd and has the keystore).
- Wrap the full balance in one shot without a smoke (rejected: no upside
  vs. the smoke-first ordering, and a misconfigured `CollateralOnramp`
  address would have lost the entire balance).
- Defer the on-chain work until Session 45 (rejected: the V2 software fleet
  was already running and any fill would have reverted; closing the gap
  same-day is the lower-risk path).
- Run `setApprovalForAll(false)` on the V1 exchanges first (deferred:
  V1 contracts are unused post-cutover so V1 allowances cannot be
  exploited; revoking is cleanup, not safety).

**Consequences:**
- Wallet `0x5359B1d4…3714cd` is now fully V2-shaped on chain: 454.034104
  pUSD, zero USDC.e, MAX pUSD allowances on both V2 exchanges, and
  `setApprovalForAll(true)` for ConditionalTokens on both V2 exchanges.
- Bots can place V2 orders without settlement-revert risk.
- The `CollateralOnramp` is still approved MAX for USDC.e, so any future
  USDC.e top-up to the wallet can be wrapped with a single tx.
- The `/auth/api-key` 400 observed during the smoke order is a known
  side-effect of cached L1 credentials and does not block placement; if it
  ever turns into a real auth failure, `core.clob_v2.ClobWrapperV2` and
  the `create_or_derive_api_creds` path are the right place to look.
- OQ-034 reduces to two operator-owned items: builder-code env-var
  verification on the bot LXC container, and explicit approval before any non-smoke
  live order.

**References:**
- CHANGELOG entry `## [2026-04-29] — Session 44: V2 wallet migration completed
  on-chain` for the full tx hash list.
- ADR-048 for the V2 cutover decision (the software side of this work).

## ADR-051: Default Polygon RPC moves to PublicNode

**Date:** 2026-04-29
**Status:** accepted
**Context:** Session 45 V2 readiness verification found that
`core.config.Settings.polygon_rpc_url` still defaulted to
`https://polygon-rpc.com`. On the bot LXC container, that endpoint returned HTTP 401 during
plain `eth_chainId` reads. CLOB order placement does not depend on this RPC,
but on-chain maintenance scripts and balance/allowance diagnostics do.

**Decision:** Change the default Polygon RPC URL to
`https://polygon-bor.publicnode.com`, matching the fallback already used by
`scripts/approve_polymarket.py` and `scripts/swap_native_to_usdce.py`.

**Rationale:** A default public RPC must work without an account-specific API
key. PublicNode returned Polygon chain ID 137 from the bot LXC container during verification,
while the old default returned 401. Keeping a dead default creates false
negatives in future V2 balance, allowance, wrap, unwrap, and P&L diagnostics.

**Consequences:**
- `get_settings().polygon_rpc_url` is usable on the bot LXC container without extra env.
- Scripts that explicitly require `POLYGON_RPC` are unchanged.
- Operators can still override `POLYGON_RPC_URL` / `polygon_rpc_url` in env if
  a paid or private RPC is preferred later.

## ADR-052: Bot D uses settlement-station modeling before live graduation

**Date:** 2026-04-29
**Status:** accepted
**Context:** Bot D previously used city-center forecast coordinates plus a
legacy urban-heat-island adjustment when fresh METAR exceeded the ensemble
mean. A Grok verification pass on the Bot D weather-edge brief confirmed the
opposite operating assumption for current daily Polymarket city-temperature
markets: rules are station-specific and commonly point at Wunderground pages
for airport/ASOS stations, e.g. NYC `KLGA` and Dallas `KDAL`. For 1-2 F
buckets, modeling Manhattan or DFW while settlement uses LaGuardia or Love
Field can erase the edge even if execution and fee logic are correct.

**Decision:** Make settlement station the Bot D modeling anchor:

1. Add `SettlementSpec` as the canonical per-city station/source/rounding
   metadata layer.
2. Move verified city forecast coordinates to the settlement station instead
   of the city center, including Dallas `KDAL` and NYC `KLGA`.
3. Remove UHI uplift from verified station-settled markets by setting their
   `urban_heat_island_f` compatibility field to zero.
4. Apply settlement rounding in the strategy layer before empirical bucket
   comparison.
5. Store raw ensemble member highs/lows and use empirical member-count
   probability as a disagreement gate against the fitted CDF model.
6. Fetch same-day METAR/SPECI observations from AviationWeather and use
   max-so-far/min-so-far as hard constraints where the bucket is already
   impossible or already reached.

**Rationale:** This is the highest-confidence profitability fix surfaced by
the weather deep dive. It attacks structural model error rather than adding
more execution features or premature ML. The empirical-probability gate keeps
the existing skew-normal model but prevents it from trading when the raw
ensemble shape says the fitted distribution is overconfident.

**Alternatives considered:**
- Keep city-center coordinates plus UHI offsets (rejected: settlement is the
  airport/station, so UHI turns into a bias rather than a correction).
- Replace the current probability model entirely with member counts
  (rejected: the fitted CDF still provides useful smoothing when member
  count is sparse; the safer first move is disagreement gating).
- Promote NBM or LGBM immediately (deferred: both need shadow calibration and
  Brier/log-loss evidence before affecting entries).
- Use Wunderground scraping for intraday max-so-far first (deferred:
  AviationWeather provides structured METAR/SPECI records for the same ICAO
  station and is easier to test/operate).

**Consequences:**
- Bot D no longer models verified US station markets as urban-core markets.
- Dallas uses `KDAL`, closing the `KDFW` edge leak.
- Same-day impossible buckets can be faded in paper mode instead of only
  nudging the mean.
- Some previously attractive CDF-only paper signals will now be skipped as
  `ensemble_shape_disagrees`.
- Remaining international and non-verified city settlement specs must be
  audited before relying on them for live sizing.

## ADR-053: Bot D paper P&L is epoch-sliced, not cleared

**Date:** 2026-04-29
**Status:** accepted
**Context:** After Session 47 changed Bot D's settlement model, the operator
asked whether to clear Bot D P&L so new paper trades could be judged on the
new station-fix logic. Deleting or rewriting old paper records would create a
clean-looking chart but would destroy the before/after evidence needed to
prove the new model improved performance.

**Decision:** Preserve all historical Bot D paper data and start a new
paper-performance epoch instead:

1. Default `BOT_D_PAPER_EPOCH_ID` to `station_v1_2026_04_29`.
2. Default `BOT_D_PAPER_EPOCH_START` to `2026-04-29T19:10:00+00:00`.
3. Tag new Bot D forecast-entry audit events with the epoch ID and start
   timestamp.
4. Expose epoch-sliced Bot D order, trade, status, and theoretical paper P&L
   metrics through `/api/bot-d`.
5. Show the epoch metrics as a separate `Station-Fix Epoch` dashboard panel
   while keeping lifetime metrics visible.

**Rationale:** The operator needs a clean view of station-fix paper
performance, but the old data is still useful for regression analysis,
before/after comparisons, and auditing why live graduation was delayed.
Epoch slicing gives both. It also avoids any DB mutation that could
accidentally erase order or trade rows needed for later reconciliation.

**Alternatives considered:**
- Delete old Bot D orders/trades/events (rejected: loses evidence and risks
  breaking reconciliation/audit assumptions).
- Rename the bot ID for new paper trades (rejected: would fragment filters,
  dashboards, and service configuration for little benefit).
- Keep only lifetime metrics and rely on manual date filtering (rejected:
  too easy to misread during live-graduation review).

**Consequences:**
- Bot D dashboards now show lifetime and station-fix epoch performance
  separately.
- Old paper P&L remains visible and can be compared against the new cohort.
- The epoch boundary is configurable by env if the operator wants to start a
  later cohort after another material model change.
- No database rows were deleted or rewritten.

## ADR-054: Fleet paper performance is epoch-sliced in the operator dashboard

**Date:** 2026-04-30
**Status:** accepted
**Context:** After the V2/pUSD migration and multiple bot-specific strategy
changes, the old dashboard mixed stale paper history with the current bot
implementations. The operator asked whether the Bot D epoch pattern should
apply to every bot, while keeping old records in the background and reducing
the dashboard to the metrics that matter operationally.

**Decision:** Keep every historical order, trade, position, and event, but
make dashboard bot cards current-epoch-first:

1. Non-Bot-D bots default to `fleet_epoch_2026_04_30` beginning
   `2026-04-30T00:00:00+00:00`.
2. Bot D keeps its station-fix epoch from ADR-053.
3. Every dashboard bot summary reports only four headline metrics for the
   current epoch: P&L, paper amount, trade count, and active state.
4. Raw lifetime records remain available through the Orders & Positions,
   Events & Health, and underlying API payloads.
5. Bot G dashboard routing must match the visible UI; `/api/bot-g` is exposed
   because the frontend already had a Bot G tab.

**Rationale:** Deleting old history would hide evidence and make before/after
reviews weaker. Showing lifetime history as the default view also makes the
operator overfit stale pre-fix numbers. Epoch slicing gives a clean current
cohort without losing the audit trail. The simplified view reduces cognitive
load when checking the fleet from a phone or during alerts.

**Alternatives considered:**
- Clear old P&L for every bot (rejected: destroys audit and regression data).
- Keep the old detailed dashboard as the default (rejected: too much surface
  area for an operator health check).
- Create new bot IDs for every post-change cohort (rejected: fragments
  services, alerts, and DB queries).

**Consequences:**
- Dashboard headline metrics now answer the operational question first:
  is the bot active, how much paper capital is currently deployed, how many
  trades happened in the current cohort, and what is current-epoch P&L?
- Old records remain queryable for deeper analysis and tax/audit history.
- Future major bot changes can start a new epoch via env overrides without
  mutating the database.

## ADR-055: Bot G Prime replaces raw split variants for paper research

**Date:** 2026-04-30
**Status:** accepted
**Context:** The three Bot G paper variants produced enough evidence to reject
raw cheap-side longshot buying as a live-candidate thesis. Production feature
analysis on the bot LXC container matched 271 closed round trips across `bot_g`,
`bot_g_jackpot`, and `bot_g_scalp`: 1.5% win rate, -$822.72 P&L on
$1,119.36 cost, -73.5% ROI. The only positive bucket was the 5c-8c entry
band (29 closed, 3 wins, +$94.05 P&L, +91.7% ROI), while <=3c entries were
0-for-216 and -100% ROI. The operator asked to proceed with Bot G Prime and
archive anything not needed.

**Decision:** Archive the raw Bot G variants and run a single paper-only
`bot_g_prime` service:

1. `bot_g`, `bot_g_jackpot`, and `bot_g_scalp` remain in the registry as
   archived evidence, excluded from fleet caps and watchdog cancel routing.
2. `bot_g_prime` is the only active G-family bot and writes to its own DB
   ledger.
3. Prime only considers the 4c-8c final-window dislocation band, defaults to
   a 30-second entry window, requires CEX direction confirmation, and records
   book-depletion telemetry without making depletion a hard gate yet.
4. The dashboard shows only `bot_g_prime` as active and recomputes archived
   G-cohort summaries from DB trades so late-settling paper positions do not
   freeze stale evidence.

**Rationale:** The old variants were burning paper capital in the exact
regions the empirical data rejects. Keeping all three live would create more
negative evidence, not a better ensemble. Prime is the narrow hypothesis that
survived the data: late, non-zero cheap-side dislocations where external CEX
movement supports the Polymarket side.

**Alternatives considered:**
- Keep all three variants and add Prime as a fourth (rejected: dilutes focus
  and keeps trading cohorts with -73% aggregate ROI).
- Delete old Bot G code and records (rejected: loses the evidence trail that
  justified Prime).
- Make book depletion a required entry gate immediately (rejected: plausible,
  but not yet validated on enough winning/losing examples).

**Consequences:**
- Bot G remains paper-only; no live-capital implication.
- `polymarket-bot-g-prime.service` is the only active G service on the bot LXC container.
- Future Bot G live arguments must use `bot_g_prime` forward data, not the
  archived raw cohorts.
- OQ-051 stays open with a narrower acceptance target: prove Prime EV after
  fees and excluding the largest 1-2 wins before any widening, sizing
  increase, or live proposal.

## ADR-056: Kronos can be evaluated for Bot E only as an offline shadow feature

**Date:** 2026-04-30
**Status:** superseded by ADR-057
**Context:** The operator asked whether `shiyu-coder/Kronos` can improve Bot
E. Kronos is an MIT-licensed financial K-line foundation model family that
forecasts OHLCV-style candlestick sequences. Bot E already has an E-2 plan to
replace the failed linear OBI proxy with a held-out logistic/GBDT model using
recorder-derived Polymarket and CEX features. Bot E's immediate blocker is
OQ-048: memory-bounded calibration plus DB-visible rejection telemetry.

**Decision:** Evaluate Kronos for Bot E only as an offline/shadow CEX
forecast feature after OQ-048 is fixed:

1. Aggregate recorder `cex_trades` into short OHLCV bars for BTC/ETH/SOL.
2. Run Kronos-mini or Kronos-small offline against copied recorder data, not
   inside the live trader loop.
3. Emit shadow features such as predicted direction, predicted move bps,
   forecast dispersion, and predicted volatility into an analysis dataset.
4. Test those features inside the existing Bot E chronological train/val/test
   pipeline and judge them by the current held-out gates: ECE, Brier,
   calibration slope, and held-out sample count.
5. Do not change `data/bot_e_calibration.json`, Bot E thresholds, sizing, or
   live/paper entry decisions unless the Kronos-augmented model beats the
   existing E-2 acceptance criteria out-of-sample.

**Rationale:** Kronos is relevant because Bot E's missing signal is CEX
short-horizon direction/regime quality, and the recorder already stores the
CEX trade tape needed to build K-lines. It is not a direct Polymarket model:
it does not know CLOB queue position, maker fill probability, fee impact, or
Polymarket order-book microstructure unless those remain separate local
features. Treating it as a shadow feature preserves Bot E's anti-cheating
discipline while giving the model a chance to add real directional
information.

**Alternatives considered:**
- Put Kronos directly into Bot E's live loop (rejected: adds Torch/Hugging
  Face runtime risk and unvalidated latency without held-out evidence).
- Replace the Bot E E-2 logistic/GBDT plan with Kronos (rejected: larger
  model, weaker interpretability, and no Polymarket-specific fill realism).
- Ignore Kronos entirely (rejected: cheap offline test against existing
  recorder data may surface useful CEX regime features).

**Consequences:**
- No live-capital or paper-trading behavior changes.
- OQ-048 remains the first Bot E task.
- If Kronos fails held-out Bot E metrics, it is archived as a research note.
- If Kronos passes, a later ADR is required before promoting any derived
  feature into the Bot E runtime path.

## ADR-057: Kronos is rejected for Bot E; retain only lightweight CEX feature extraction

**Date:** 2026-04-30
**Status:** accepted
**Context:** ADR-056 allowed an offline Kronos shadow-feature evaluation for
Bot E. The operator then rejected the idea unless there was a smaller useful
takeaway. Bot E's next blocker is still OQ-048: bounded calibration,
DB-visible rejection telemetry, and fill-quality measurement. Adding a
Torch/Hugging Face dependency does not solve that blocker.

**Decision:** Do not use Kronos for Bot E. Retain only the lightweight idea:
derive CEX OHLCV/regime features directly from recorder `cex_trades` and
test them inside the existing Bot E E-2 held-out model pipeline.

**Rationale:** Bot E needs execution truth before model complexity:
fill rate by reason, adverse selection, depth/CVD unavailable states,
price-bucket EV, and calibration windows that do not starve the recorder.
Kronos adds dependency weight and inference complexity before the system can
even count rejected/fillable opportunities reliably. Simple local CEX bars
capture the useful signal class without importing a foundation model.

**Alternatives considered:**
- Keep ADR-056's Kronos shadow evaluation (rejected: premature complexity).
- Add Kronos to Bot E runtime as a live gate (rejected in ADR-056 and still
  rejected).
- Ignore CEX bar features entirely (rejected: the recorder already has the
  data, and simple features can be tested cheaply after OQ-048).

**Consequences:**
- ADR-056 is superseded.
- No Kronos dependency, model download, service, or runtime path will be
  added for Bot E.
- The next Bot E profitability work stays OQ-048 first, then lightweight
  feature and threshold tests against held-out paper outcomes.

## ADR-058: Bot E changes require current-data and public-context validation

**Date:** 2026-04-30
**Status:** accepted
**Context:** The operator required that pre-dated Bot E evidence, including
OQ-048 telemetry and earlier audits, be validated against real-time production
data and current public market/API context before any strategy changes proceed.
Session 51 read-only checks showed why this rule is needed: older notes that
referenced 69 fills or 20 placed/cancelled orders are stale against current
production, where `main.db` now shows 308 FILLED Bot E orders and the journal
still shows thousands of log-only skips/cancels that OQ-048 must make
DB-countable.

**Decision:** No Bot E threshold, model, sizing, execution, or graduation
change is accepted unless it includes a validation packet:

1. Current production DB/journal evidence for the relevant window, usually
   24h and 7d when enough data exists.
2. Recorder-health evidence for the same window: heartbeat freshness,
   market-event coverage, reconnects/disconnects, and missing-feed states.
3. Current public Polymarket context checked immediately before the change:
   official docs/changelog/status and any material market-structure news
   relevant to fees, CLOB behavior, order signing, WebSocket events, outages,
   or resolution semantics.
4. Read-only analysis on copied data or shadow mode before changing live or
   paper thresholds.
5. Expected metric movement and rollback criteria.

**Rationale:** Bot E is a microstructure strategy. Stale fill counts,
pre-V2 assumptions, recorder gaps, fee changes, or API outage context can
invert the conclusion of an otherwise tidy backtest. Treating historical docs
as priors and forcing fresh validation prevents the system from optimizing
against dead market structure.

**Alternatives considered:**
- Trust latest written audit until contradicted (rejected: current telemetry
  already contradicted older Bot E fill/order counts).
- Require validation only before live mode (rejected: bad paper thresholds
  contaminate calibration and delay kill/scale decisions).
- Pause Bot E entirely until all OQ-048 work is complete (rejected: read-only
  paper telemetry remains useful while the validation rule prevents unsafe
  changes).

**Consequences:**
- OQ-048 is now explicitly a validation and instrumentation blocker, not just
  a calibration-memory blocker.
- Future Bot E proposals must include fresh production and public-context
  evidence in the same change set or decision note.
- No code, live settings, wallet state, GO files, or order paths changed by
  this ADR.

## ADR-059: Bot E loosens paper execution before signal gates

**Date:** 2026-04-30
**Status:** accepted
**Context:** The operator asked to get trades flowing after the dashboard
showed Bot E with many current-epoch paper orders, zero fills, and zero P&L.
The latest verified production snapshot from 2026-04-30 showed Bot E placing
58 current-epoch paper orders, all cancelled, with recent `bot_e.ttl_cancel`
events carrying `ttl_sec=300`. Current public context was rechecked before
the change: official Polymarket docs/status still show V2/CLOB available,
crypto taker fees, and zero maker fees. During this session, the production
host was unreachable from the dev machine, so no LXC deployment was performed
and local DB report dry-runs were not treated as production evidence.

**Decision:** Loosen Bot E execution in paper mode only:

1. Paper default `BOT_E_MAKER_OFFSET` becomes `0.000` instead of `0.001`.
2. Paper default `BOT_E_ORDER_TTL_SEC` becomes `600` instead of `300`.
3. Live-mode defaults remain `0.001` maker offset and `300` seconds TTL.
4. Add a read-only cancel-autopsy report before any further loosening:
   `scripts/bot_e_cancel_autopsy.py`.
5. Add a fleet trade-flow report so Bot D/F/G changes require fresh
   order/fill/event evidence instead of a blind threshold relaxation:
   `scripts/fleet_tradeflow_report.py`.
6. Persist fetched Bot E YES and NO CLOB books into `main.db.books` so the
   shared paper-fill simulator can evaluate Bot E token orders honestly.

**Rationale:** The current Bot E bottleneck is execution/fill opportunity,
not signal generation volume. Lowering OBI, depth, or CEX CVD gates would
increase placed orders but would not explain whether the existing 58 paper
orders failed because the quote was too passive, the TTL was too short, or the
signals were adverse. A longer paper TTL and zero offset increase fill
opportunity while staying maker-style and preserving calibration discipline.
The first production autopsy also showed `book 0/69` coverage for Bot E
orders, so persisting the books already fetched by the trader is required
before TTL/offset tuning can produce honest paper fills.

**Alternatives considered:**
- Disable CEX/depth gates immediately (rejected: increases noisy orders
  without proving fill quality).
- Enable synthetic no-book fills (rejected: creates fake P&L and corrupts
  microstructure calibration).
- Use taker/crossing orders (rejected: crypto taker fees and live
  reproducibility risk; requires a new ADR).
- Loosen Bot D weather vetoes in the same pass (rejected: requires current
  settlement/weather validation).
- Loosen Bot G Prime thresholds (rejected: archived G variants were negative;
  Prime needs forward evidence first).

**Rollback criteria:**
- Revert paper offset to `0.001` or TTL to `300` if the cancel autopsy or
  forward paper data shows adverse rate above `60%` over at least 20 measured
  fills, fill rate still below `10%` over 50 orders, or the longer TTL ties up
  paper exposure enough to block other current-epoch probes.

**Consequences:**
- Bot E should place quotes that are easier to fill in paper while remaining
  maker-style.
- No live-money behavior changes unless runtime environment explicitly
  overrides the live defaults.
- The next production step is to re-run the cancel autopsy and fleet flow
  report after a fresh paper window with book coverage present.

## ADR-060: Bot D/G get paper-only trade-flow probes

**Date:** 2026-04-30
**Status:** accepted
**Context:** After Bot E started filling, the next production flow report
showed Bot D and Bot G Prime as the relevant remaining bottlenecks. Bot D had
`1,168` `bot_d.nws_veto` events and no orders over the 24h window. Recent
vetoes were concentrated in Chicago, Miami, and Denver with model-vs-NWS
disagreements of roughly 3.1°F to 7.9°F against a 2.0°F threshold. Bot G
Prime was active but sparse: `188` candidate-summary events, `1` Prime entry,
and `2` fill rows. Current public Polymarket context was checked before the
change: the status page showed systems operational, and official fee docs
still showed maker fees at zero with taker fees by category.

**Decision:**

1. Add a paper-only Bot D NWS-veto override for strong model edges:
   `BOT_D_NWS_VETO_OVERRIDE_ENABLED=true` and
   `BOT_D_NWS_VETO_OVERRIDE_MIN_EDGE=0.15`.
2. Keep Bot D live mode conservative: the NWS veto remains hard in live mode.
3. Widen Bot G Prime's final entry window from `30s` to `45s`.
4. Keep Bot G Prime's price band, CEX confirmation, size, and depletion
   behavior unchanged.
5. Do not change Bot F allowlists or Bot B/C behavior in this pass.

**Rationale:** Bot D is not lacking candidates; it is blocked at the NWS veto.
A paper-only strong-edge override creates outcome data to test whether the NWS
second opinion saves money or filters winners. Bot G Prime's thesis is narrow
because archived G variants were negative; widening the time window is the
least invasive way to increase sample size without reviving losing price
buckets or disabling CEX confirmation.

**Rollback criteria:**
- Disable Bot D's override if override-tagged paper entries show negative EV,
  a losing streak of 5 closed positions, or settlement audit finds station or
  rounding mismatch in the traded city.
- Revert Bot G Prime to `30s` if 45-second entries concentrate outside the
  historically positive 5-8c band, show worse adverse movement than 30-second
  entries, or lower realised paper ROI after 20 closed Prime trades.

**Consequences:**
- More Bot D and Bot G paper trades should flow without touching real money.
- Any live-mode proposal still requires a separate ADR, current-data packet,
  and explicit operator approval.

## ADR-061: Disable Bot G Prime hard CEX confirmation in paper

**Date:** 2026-04-30
**Status:** accepted

**Context:** Production Bot G Prime telemetry on 2026-04-30 showed many
price-qualified 4-8c candidates but only one paper entry. The latest hard
rejections were `cex_not_confirmed`, while candidate summaries still showed
13 of 18 to 17 of 22 recent candidates inside the current 8c ceiling. This
means the CEX filter is currently the sample-size bottleneck, not market
discovery or price-band strictness.

**Decision:** For paper data collection, set
`BOT_G_PRIME_REQUIRE_CEX_CONFIRM=false` in the Bot G Prime systemd unit while
leaving the 4-8c price band, 88c counterparty floor, $5 paper size, daily cap,
and `BOT_G_ENV=paper` / `BOT_G_DRY_RUN=true` unchanged.

**Rationale:** The hard CEX gate is an unproven filter. With the gate enabled,
the strategy cannot generate enough samples to determine whether CEX
confirmation improves win rate or merely rejects profitable tails. Paper-only
unconfirmed entries create a measurable comparison bucket without risking real
funds.

**Reversal trigger:** Restore `BOT_G_PRIME_REQUIRE_CEX_CONFIRM=true` if the
unconfirmed paper bucket underperforms the confirmed bucket after at least 50
closed Bot G Prime positions, or if same-day monitoring shows obvious adverse
selection concentrated in unconfirmed entries.

## ADR-062: Normalize Bot C to Hermes paper executor in systemd

**Date:** 2026-04-30
**Status:** accepted

**Context:** Bot C was active and seeing current Silver/AAPL edges, but after
clearing its stale DB halt flag it still refused every current entry with
`horizon_too_long`. Production `systemctl cat` showed why: an older drop-in
contained a bare `Environment=` reset after the paper-cap drop-in, erasing the
intended `BOT_C_MAX_HOURS_TO_RESOLUTION=2160` and related paper settings.

**Decision:** Make the canonical Bot C systemd unit explicitly run the Hermes
paper executor with `BOT_C_ENV=paper`, `--enable-executor`, and the intended
paper caps: 2160-hour max horizon, $1000 paper bankroll, $10 paper size,
10 concurrent paper positions, and $100 minimum 24h volume.

**Rationale:** This is not a new live thesis. It restores the already-approved
paper data-collection posture after systemd drop-in drift made the running
service stricter than intended. Bot C remains paper-routed even while the
global Polymarket stack is live.

**Reversal trigger:** Re-archive or re-halt Bot C if Hermes data staleness
returns, forced exits exceed the existing watch threshold, or the current
paper sample remains structurally too thin to evaluate.

## ADR-063: Scope watchdog halts and alert on halt transitions

**Date:** 2026-05-01
**Status:** accepted

**Context:** After the 2026-04-30 paper trade-flow loosening, Bot C, Bot D,
and Bot E were re-halted at `2026-05-01 00:37 UTC`. Production inspection on
2026-05-01 showed repeated watchdog events for stale Bot B scoring
(`watchdog.scorer.liveness`, kill severity, `bot_id='bot_b'`) and WSS
no-fill warnings, while C/D/E halt flags were still carrying stale
operator-unhalt reason text. The prior watchdog implementation had two
operational hazards: silenced checks could still halt without a Telegram page,
and unscoped kill checks fell back to a legacy bot list that omitted newer
paper bots while still capable of stopping the old paper fleet.

**Decision:**

1. Watchdog kill checks must declare a bot scope whenever the affected surface
   is narrower than all active trading bots.
2. Bot B scorer liveness is Bot B only.
3. Market-catalog freshness is scoped to Bot A/B/C/D/G Prime.
4. Paper aggregate exposure is scoped to Bot C, Bot D, Bot E, Bot F mirror,
   and Bot G Prime.
5. VPN/CLOB liveness remains fail-closed for active trading bots.
6. Telegram halt alerts and `watchdog.halt` Events are emitted on halt
   transitions, not on every repeated failed check tick.
7. Telegram `/status` should show the non-archived fleet, not only Bot A/B.

**Rationale:** A stale Bot B scorer is a Bot B readiness problem, not a reason
to stop unrelated paper data collection. Repeated check-failure Events remain
available for diagnosis, but the operator needs a distinct transition signal
when a bot actually moves into halted state. Explicit scopes keep future bots
from falling through stale legacy lists.

**Consequences:**

- C/D/E paper trading can continue while Bot B remains halted behind the
  scorer rebuild and calibration gate.
- A future real CLOB/VPN outage still halts active trading bots fail-closed.
- The local fleet status packet can be consumed by an LLM or other hook
  without scraping dashboard visuals.

**Rollback trigger:** Revert only if a scoped infrastructure outage allows a
bot to keep placing orders while its required data/execution dependency is
provably unavailable. In that case, add the bot to the relevant explicit
scope rather than restoring unscoped fleet halts.

## ADR-064: Profitability path is a contrarian edge tournament, not all-bot loosening

**Date:** 2026-05-01
**Status:** superseded by ADR-065

**Context:** The operator asked for a deep review of project history, external
repo research, discovery chats, bot audits, and current production telemetry
to decide whether there is a viable path to profitability and ROI. Prior docs
show repeated failures of broad or crowded theses: Bot A's longshot fade is
negative walk-forward, archived Bot G variants are strongly negative, Bot E's
old spread-capture POC failed in the no-flow/spread tradeoff, Bot F direct
copy-trading is likely crowded, and Bot B's scorer path is currently stale.
Fresh 2026-05-01 validation showed Polymarket public systems operational,
official docs still favor maker economics over taker-heavy churn, and the bot LXC container
paper telemetry has adequate bankroll but still incomplete proof quality.

**Decision:** The path to profitability is a ranked contrarian edge
tournament:

1. Bot D is the first ROI candidate: settlement-exact weather mispricing,
   station/source/rounding proof, NBM/METAR shadow validation, and
   ex-largest-win forward paper gates.
2. Bot F is promoted as a wallet/crowd-flow sensor before any direct
   copy-trading expansion. The next edge to test is anti-crowd veto/fade,
   tracked as OQ-059.
3. Bot E and Bot G Prime remain paper-only microstructure probes until fill
   quality, adverse selection, and ex-outlier bucket EV are proven with current
   production data.
4. Bot B remains halted until scorer health, stale-score policy, and local
   ensemble/calibration work satisfy OQ-049.
5. Bot A stays archived; Bot C stays low-priority paper/research unless new
   evidence changes its Polymarket-specific edge.

**Rationale:** The user's requested "opposite of what every other bot trader
does" edge is not a literal always-fade rule. A blind fade of crowded flow is
just another uncalibrated directional bot. The defensible opposite is to avoid
the crowded surfaces: speed races, direct wallet copying, taker-heavy crypto
chasing, and rebate farming. The fleet should instead test slow-truth and
crowd-saturation edges where the operator can be better than public bots:
settlement exactness, external data validation, calibrated abstention, and
post-cascade drift.

**Artifacts:** `docs/opus-profitability-edge-handoff-2026-05-01.md` is the
handoff document for Opus review and the canonical plan for this decision.

**Consequences:**

- Future trade-flow tuning must attach a current-data proof packet instead of
  only loosening parameters.
- Any live proposal must identify which ranked edge hypothesis it belongs to
  and satisfy that hypothesis's proof gates.
- The next highest-value research item outside Bot D is OQ-059, because it
  tests whether Bot F can provide a genuinely unique anti-crowd edge.

**Rollback trigger:** Supersede this ADR only if a current forward-paper report
shows another bot has materially better risk-adjusted ROI after fees,
slippage, largest-win exclusion, and live-readiness checks.

## ADR-065: Offensive profitability rewrite promotes Bot B and fusion to P0

**Date:** 2026-05-01
**Status:** accepted

**Context:** Opus reviewed
`docs/opus-profitability-edge-handoff-2026-05-01.md` and found that the
document was disciplined but too defensive for the operator's fast-ROI goal.
The strongest critique was that the prior plan demoted the durable external
edge: an externally calibrated dispute-risk scorer (Oraclemangle —
https://oraclemangle.com). Weather settlement exactness, wallet-flow
observation, and ensemble disagreement are useful craft, but they are easier
for other operators to replicate than access to that external calibrated
product. Opus also rejected `$100` tiny-live as ROI evidence, flagged fixed-N
gates as weak for correlated markets, and argued that fusion across bots
should be the thesis rather than a future integration.

**Decision:**

1. Bot B / external-scorer integration (https://oraclemangle.com) becomes P0.
2. Fusion becomes the product: Bot F crowd-flow, Bot B probability/confidence,
   and D/E/G market-specific signals should feed a transparent scoring layer
   before any opaque fused trader exists.
3. `$100` tiny-live is reclassified as a plumbing test only. ROI-live evidence
   requires a separate operator-approved `$500-$1,000` allocation with
   `$25-$50` orders.
4. Fixed-N promotion gates are replaced by Bayesian/posterior and
   block-bootstrap style reporting where trades are correlated.
5. D/E/G live candidacy is hard time-boxed to 2026-06-01.
6. Competitive-intel and capacity analysis are required before claiming a
   contrarian edge or ROI path.

**Artifacts:** `docs/offensive-profitability-strategy-2026-05-01.md`.

**Immediate implementation:** Bot B scoring sweeps now respect the explicit
halt state. `run_sweep()` performs no scorer calls while `bot_b` is halted
unless `BOT_B_SCORE_WHILE_HALTED=true` is set, satisfying the first slice of
OQ-049 without changing live order behavior.

**Rationale:** Fast ROI still needs discipline, but the discipline must force
a decision instead of extending paper forever. The external-scorer-first plan
preserves the unique asset, while fusion gives the fleet a reason to exist as
a system rather than a pile of unrelated bots.

**Consequences:**

- Bot D remains a possible near-term cashflow candidate, but no longer carries
  the main strategic thesis alone.
- Bot F's primary value is cross-bot crowd intelligence, not direct mirror
  trading.
- Bot E/G must justify themselves through capacity, adverse-selection, and
  reward/slippage math, not just improved trade count.
- Any live ROI allocation still requires explicit operator approval.

**Rollback trigger:** Supersede if Bot B cannot be locally owned/calibrated by
2026-06-01 and one of D/E/G independently proves a higher-capacity,
outlier-resistant ROI path.

## ADR-066: Bot F becomes shared sensor infrastructure, not a fast-ROI trader

**Date:** 2026-05-01
**Status:** accepted

**Context:** The operator challenged whether Bot F whale watching is a good
bot. Prior Bot F docs and the 2026 public bot landscape point to the same
answer: direct whale/copy trading is crowded, lagged, and easy to replicate.
Copying visible wallets risks slippage, clustered signals, hedged flows, and
survivor bias. The useful asset is the signal tape Bot F already creates:
mirror signals, detected cascades, and crowd-pressure features that can
improve or veto faster ROI bots.

**Decision:**

1. Bot F is demoted as a standalone fast-ROI trader.
2. Bot F mirror execution remains paper/measurement only.
3. Bot F sensor functions are promoted into shared infrastructure for Bot E,
   Bot G Prime, Bot D, and Bot B.
4. `core.crowd_signals` is the shared read-only adapter for recent cascade
   pressure.
5. `scripts/fast_roi_report.py` is the first consumer: it ranks Bot E/G/D
   fast-ROI readiness while showing Bot F crowd-sensor context.

**Rationale:** This keeps the useful contrarian part of Bot F while removing
the weakest thesis. A crowd sensor can help avoid toxic trades or identify
fade candidates; a direct copy bot competes with public tooling and starts
late by construction.

**Consequences:**

- Future work should wire Bot F pressure into reports first, then paper vetoes
  or fade tests only after evidence.
- No direct mirror allowlist expansion or live Bot F proposal without a new
  ADR and positive latency-adjusted cohort proof.
- Fast ROI priority is Bot E first, Bot G Prime second, Bot D daily/low-lock-up
  subset third, Bot F as sensor, Bot B as background external-scorer work.

**Rollback trigger:** Supersede only if direct Bot F mirror paper data beats
the sensor-overlay approach after slippage, latency, fees, and wallet overlap
are measured.

## ADR-067: Bot D stays real-wallet priority while fast-ROI reporting leads tuning

**Date:** 2026-05-01
**Status:** accepted

**Context:** The operator clarified that Bot D had been in line as the first
bot to take to the real wallet and should remain prioritized. Fresh production
evidence on 2026-05-01 showed a split picture: Bot E and Bot G Prime are now
producing fast paper fill flow, but Bot E fills show high short-horizon
adverse movement and Bot G Prime's positive ROI disappears after removing the
largest win. Bot D has the cleaner real-wallet thesis, but current production
state shows zero fills in the 24h fast-ROI report, stale/open paper lock-up,
and many NWS vetoes.

**Decision:**

1. Bot D remains the preferred first real-wallet candidate track.
2. Bot D does not get generic threshold loosening until daily/weekly lock-up,
   stale-open reconciliation, settlement-source proof, depth/slippage, and
   trimmed/ex-outlier ROI are reported.
3. Bot E and Bot G Prime remain fast-turnover paper learning surfaces, not
   wallet-priority candidates.
4. `scripts/fast_roi_report.py` now runs hourly on the bot LXC container through
   `polymarket-fast-roi-report.timer` and writes JSON/Markdown under
   `data/reports/fast_roi/`.
5. Bot G feature analysis now reports ex-largest-win and
   ex-largest-two-wins ROI so jackpot-shaped results cannot masquerade as
   steady edge.

**Rationale:** This preserves the user's intended Bot D promotion path without
ignoring current production evidence. Fast turnover is useful for learning,
but live priority should follow durable, explainable edge. Bot E needs
fill-quality improvement, Bot G needs outlier-resistant proof, and Bot D needs
lock-up and settlement validation before any real wallet action.

**Consequences:**

- Bot D work moves next to daily/weekly split and stale-open reconciliation.
- Bot E tuning must reduce toxic fills before loosening execution parameters.
- Bot G Prime remains paper until ex-largest-win ROI is positive.
- The hourly report gives a stable hook for dashboard, Telegram, or later LLM
  status checks without touching order flow.
- No real-money action is authorized by this ADR.

**Rollback trigger:** Supersede if Bot D daily/low-lock-up proof fails and
either Bot E or Bot G Prime produces outlier-resistant, fee/slippage-adjusted
ROI with sufficient capacity for `$500-$1,000` live allocation.

## ADR-068: Bot D live-readiness must be dashboard-visible before wallet work

**Date:** 2026-05-01
**Status:** accepted

**Context:** Bot D remains the preferred first real-wallet candidate track,
but production state has stale paper orders, stale open positions, no recent
fills, and weekly-lock-up exposure mixed with daily/low-lock-up flow. Previous
dashboard visuals showed Bot D as simply active, which made it too easy to
miss why the bot was not wallet-ready.

**Decision:**

1. Bot D live-readiness is a first-class dashboard and report surface.
2. `/api/bot-d` includes the read-only readiness report: stale/open state,
   daily/weekly duration split, recent fills, forecast-entry count, and NWS
   veto count.
3. The Bot D tab uses the weather-specific panel and displays Wallet
   Readiness plus Lock-Up before epoch/order details.
4. Live-ready remains `false` until stale paper state is reconciled, fresh
   daily fills are observed, weekly lock-up is separated, and the existing
   settlement/depth/trimmed-ROI gates clear.

**Rationale:** The operator needs one glance to answer: "is Bot D online,
trading, and wallet-ready?" Active service state is not enough. Bot D can be
active and still blocked from live capital.

**Consequences:**

- Dashboard now matches the promotion plan: Bot D is wallet-priority but
  blocked.
- Future Telegram/LLM hooks can consume the same readiness packet without
  inventing separate status logic.
- No order flow, wallet state, or real-money behavior changes.

**Rollback trigger:** Supersede if Bot D live-readiness moves to a different
canonical report/API surface.

## ADR-069: Bot D first-wallet proof is daily-only until resolved P&L clears

**Date:** 2026-05-01
**Status:** accepted

**Context:** After adding Bot D readiness reporting, production showed the
bot was still mixing stale expired paper orders, blank-condition orphan paper
positions, and weekly-lock orders with the desired daily weather lane. It
also had zero recent fills because current Bot D orders had no recorded book
snapshots after placement, so the paper-fill simulator had no observed books
to cross against.

**Decision:**

1. Bot D first-wallet proof is daily/low-lock-up only.
2. New Bot D entries with market lock-up over `48h` are rejected with
   `lockup_too_long`.
3. Existing stale expired paper orders may be cancelled by the guarded
   `scripts/cancel_paper_orders.py` filters.
4. Existing blank-condition orphan paper positions may be archived by
   `scripts/archive_orphan_paper_positions.py` because they cannot resolve
   through Gamma.
5. Bot D captures a public CLOB book snapshot after order placement so paper
   fills are measured against observed books.

**Rationale:** The fastest credible Bot D ROI path needs bankroll turnover
and honest fill evidence. Weekly weather contracts and stale impossible paper
rows make the dashboard look active while hiding that capital is idle. Book
capture fixes the immediate "orders but no fills" observability gap without
loosening the strategy threshold.

**Consequences:**

- Bot D can keep collecting daily paper fills without weekly lock-up.
- Dashboard P&L now reflects active open daily positions instead of stale
  accounting residue.
- Live-ready remains false until daily-only realised P&L, depth/slippage, and
  trimmed/ex-outlier ROI clear.
- No live order behavior or wallet state is changed.

**Rollback trigger:** Supersede if weekly weather contracts prove higher
risk-adjusted monthly turnover than daily contracts after resolved paper data.

## ADR-070: Bot G is co-priority with Bot D but must be V2-fee-aware

**Date:** 2026-05-01
**Status:** accepted

**Context:** The operator clarified that Bot G should receive as much focus as
Bot D because it may become live soon. Current official Polymarket CLOB V2
docs and the repo fee model make crypto the highest taker-fee category, while
makers are not charged taker fees and maker rewards require reconciliation
before they can be counted as edge. Bot G Prime has encouraging paper P&L, but
its evidence is small-sample and concentrated in the lower `4c-5c` late-tail
subset rather than the full `4c-8c` band. The reviewed
`lihanyu81/polymarket_lp_tool` repo is a passive liquidity management tool,
not a Bot G alpha source, but it contains useful execution-control patterns.

**Decision:**

1. Bot G Prime gets equal strategy-focus priority with Bot D.
2. Bot D remains the first-wallet weather candidate until its daily-only
   resolved P&L, depth/slippage, and trimmed ROI gates clear.
3. Bot G live candidacy centers on the `4c-5c` Prime subset, not the broad
   `4c-8c` band.
4. Bot G reporting must include V2 crypto fee stress: maker-entry,
   taker-entry, and mixed-leg assumptions at `$25` and `$50` order sizes.
5. Bot G should be maker-first where possible. Any taker-heavy live proposal
   must clear fees, spread, slippage, and latency explicitly.
6. Useful patterns from `lihanyu81/polymarket_lp_tool` may be extracted as
   local execution infrastructure: post-only cancel/replace, reward scoring
   visibility, reward-band tick handling, fill-risk telemetry, structural
   quote-risk checks, and Telegram/web operator controls.
7. The LP repo's passive liquidity strategy itself is not imported and is not
   treated as a unique edge.

**Artifacts:** `docs/reports/bot-g-v2-fee-lp-tool-review-2026-05-01.md`.

**Rationale:** The strongest against-the-grain crypto lane is not joining the
common short-horizon speed race. Bot G's plausible edge is buying neglected
late tail convexity when the market overprices certainty and the CEX tape plus
crowd sensor do not invalidate the tail. CLOB V2 fees make this especially
important: a crypto taker strategy needs a much larger edge than a maker-first
or resting-limit strategy.

**Consequences:**

- Bot G work moves to cohort isolation, fee stress, and dashboard/report
  proof, not generic parameter loosening.
- Bot D and Bot G are both P0 in the fast-ROI list, with different live gates.
- Bot E may reuse some extracted execution tooling, but Bot G remains the
  primary beneficiary of this review.
- No live order behavior, wallet state, or real-money authorization changes.

**Rollback trigger:** Supersede if fresh Bot G paper data shows the `4c-5c`
subset fails after V2 fee stress and outlier adjustment, or if another Bot G
cohort produces stronger fee-adjusted, capacity-aware ROI.

## ADR-071: Active fleet revamp promotes Longshot Prime and archives Bot A/F surfaces

**Date:** 2026-05-02
**Status:** accepted

**Context:** The repo still carried an old A/B-era active model in dashboard
surfaces and cold-start docs even though recent validation shifted attention
to Longshot Prime, Weather Fade, Maker Flow, Oraclemangle Kelly, and Pyth
Directional. Bot A is useful only as archived code/history. Bot F direct
copying has been demoted; its useful value is crowd/cascade sensor data, not
a standalone trader. Stale active labels create risk for future sessions by
making dead or low-priority bots look operationally equal to current proof
tracks.

**Decision:**

1. Longshot Prime (Bot G Prime) is the primary engineering sprint and first
   live-candidate challenger, but remains paper-only until capacity,
   fee-stress, and outlier-adjusted ROI gates clear.
2. Weather Fade (Bot D) remains operational and stays the first likely
   real-wallet candidate unless Longshot Prime proves scalable,
   outlier-resistant edge first.
3. Maker Flow (Bot E) remains operational at lower priority.
4. Oraclemangle Kelly (Bot B) remains maintained and may become a future
   public spin-off repo only after a separate redaction and product-boundary
   review.
5. Pyth Directional (Bot C) remains incubating; extract useful data/modeling
   pieces before any archive decision.
6. Longshot Fade (Bot A) and legacy Whale Mirror/Sensor (Bot F) are removed
   from active dashboard/API/reporting surfaces. Their code and historical
   records remain available for archive/audit.
7. Bot F crowd, cascade, and mirror-signal data is retained as shared sensor
   infrastructure and reported under neutral crowd-sensor naming.
8. Use strategy names first and bot letters as legacy identifiers.
9. No live wallet settings, bankroll values, order ranges, or real-money
   behavior are changed by this revamp.

**Artifacts:** `docs/active-operating-model-2026-05-02.md`.

**Rationale:** The operator needs the dashboard and cold-start docs to reflect
the current ROI path. Longshot Prime is where the fastest live-candidate work
is happening, but dashboard prominence must not imply live readiness. Archiving
Bot A and Bot F active surfaces reduces false signal while preserving their
code and data for future extraction.

**Consequences:**

- Dashboard `/api/bot-a` and `/api/bot-f` are retired.
- Fleet overview, orders, positions, and trade metrics filter archived Bot A/F
  IDs by default.
- Fast-ROI reporting keeps crowd-sensor data without treating Bot F as a
  direct ROI bot.
- Bot B publicization and Bot C archive/extraction remain open questions.

**Rollback trigger:** Supersede if the operator explicitly reactivates Bot A
or Bot F as active trading surfaces, or if a new canonical bot registry
replaces dashboard-local active fleet definitions.

## ADR-072: Park Bot B outside active dashboard and reboot-readiness surfaces

**Date:** 2026-05-02
**Status:** accepted

**Context:** After ADR-071, the operator reviewed the dashboard and decided
the active monitor should show four clean bots: Longshot Prime, Weather Fade,
Pyth Directional, and Maker Flow. Oraclemangle Kelly (Bot B) and its shadow
remain strategically interesting as a later public spin-off, but showing them
beside current proof tracks creates dashboard noise and risks future sessions
treating parked productization work as active ROI work.

**Decision:**

1. Remove Bot B and Bot B Shadow from active dashboard tabs, `/api/bot-b`,
   overview fleet tiles, aggregate dashboard orders/positions/trades, and
   active reboot-readiness targets.
2. Keep Bot B code, tests, historical records, and OQ-060 spin-off planning
   intact.
3. Keep Bot B in aggregate exposure-cap membership while it remains a paper
   bot with possible outstanding exposure, so parking the dashboard does not
   weaken risk accounting.
4. Do not stop services, change live wallet settings, alter bankrolls, place
   orders, or change trading behavior as part of this dashboard cleanup.

**Rationale:** The active dashboard should answer what needs monitoring now.
Bot B is a productization/release-boundary problem, not a current live
candidate proof track. Hiding it from active surfaces lowers cognitive load
without deleting the external-scorer-backed code path or its future spin-off option.

**Consequences:**

- Active dashboard/API surfaces are now four monitored bots: Bot G Prime, Bot
  D, Bot C, and Bot E.
- `/api/bot-b` returns 404 like archived Bot A/F dashboard routes.
- Dashboard aggregate queries filter Bot B/B-shadow rows by default.
- Reboot-readiness scripts no longer require Bot B/B-shadow service state for
  a green active-fleet check.

**Rollback trigger:** Supersede if the operator reactivates Bot B as an active
paper/live proof track before the public spin-off work, or if the spin-off
plan creates a separate dashboard/API contract.

## ADR-073: Bot G live-candidate gate requires trimmed ROI and capacity proof

**Date:** 2026-05-02
**Status:** accepted

**Context:** Bot G Prime's paper results are improving, but the known failure
modes remain jackpot-shaped ROI and thin books. The dashboard already reports
exact `4c-5c`, `5c-8c`, and all `4c-8c` cohorts, ex-largest-win ROI,
ex-largest-two ROI, CEX split, and `$25/$50` capacity coverage. The operator
needs one visible gate that says why Bot G is still paper-only even when raw
P&L looks good.

**Decision:**

1. Bot G Prime stays in paper mode at `4c-8c` for data collection.
2. Only the `4c-5c` cohort is eligible for live-candidate interpretation.
3. Candidate status requires all of:
   - at least `20` closed `4c-5c` paper round trips;
   - positive `4c-5c` ROI after excluding the largest win;
   - positive `4c-5c` ROI after excluding the largest two wins;
   - `$25` entry-limit depth coverage at least `50%`;
   - `$50` limit+2c depth coverage at least `25%`.
4. If trimmed ROI fails, the gate reports `blocked_by_trimmed_roi`.
5. If trimmed ROI passes but capacity fails, the gate reports
   `blocked_by_capacity`.
6. If ROI and capacity pass but sample size is still below threshold, the gate
   reports `collecting_sample`.
7. The gate is reporting-only. It does not change Bot G order placement,
   sizing, bankroll, live mode, or wallet settings.

**Rationale:** Bot G's upside is convex, so raw ROI can be true and still not
be tradeable at meaningful size. The gate forces the live discussion to pass
through sample size, outlier resistance, and book depth before any wallet
proposal. The `$25` and `$50` thresholds are deliberately small because this is
the first real-wallet rung, not a scale-up rule.

**Consequences:**

- Dashboard and fast-ROI reports expose a single Bot G gate status plus the
  failed checks.
- Bot G can look good in raw P&L while still reporting blocked status.
- Capacity simulation now shows limit, limit+1c, and limit+2c coverage for
  `$25` and `$50`, so the operator can see whether edge only exists at toy
  paper sizes.
- Real-money use still requires explicit operator approval even if the gate
  eventually reports `candidate`.

**Rollback trigger:** Supersede if later paper data shows a better threshold
set for the first live rung, or if the operator chooses a different minimum
live order size.

## ADR-074: Bot G tiny-live prep is reporting-only until explicit approval

**Date:** 2026-05-02
**Status:** accepted

**Context:** Bot G Prime has become the main fast-ROI challenger, and the
operator expects any first live run to start with small trades to prove the
edge transfers from paper to real execution. Current evidence is still not
live-ready: ADR-073 has not cleared, `4c-5c` remains sample/capacity limited,
and raw ROI is still vulnerable to jackpot-shaped wins.

**Decision:**

1. Add Bot G tiny-live probe preparation to reports, dashboard, and runbook
   without changing Bot G strategy logic, order settings, wallet settings, or
   service environment.
2. The proposed first probe caps are `$5` starting trade size, `10` entries
   per day, `$50` daily gross notional, and `5` max open positions.
3. The probe plan is not authorization. Bot G remains paper/dry-run until
   the operator explicitly approves live activation and the exact caps.
4. Any first live probe is a plumbing and edge-transfer test, not an ROI-live
   scaling decision.
5. The dashboard and hourly fast-ROI report must show that live activation is
   blocked by explicit approval and by any uncleared ADR-073 gate check.

**Artifacts:** `docs/bot-g-tiny-live-runbook-2026-05-02.md`.

**Rationale:** Preparing the checklist now reduces friction if Bot G clears
the evidence gate, while keeping the dangerous step separate. The proposed
caps match the current paper stake and keep first live exposure small enough
to diagnose execution before discussing scale.

**Consequences:**

- `/api/bot-g`, the dashboard tab, and the hourly fast-ROI report now expose
  a tiny-live probe readiness object.
- The readiness object is reporting-only and must not be consumed by trader
  order-placement code.
- Future live activation still requires a separate documented approval event.

**Rollback trigger:** Supersede if the operator chooses different first-probe caps or
if Bot G is killed/parked before any live probe.

## ADR-075: Bot G tiny-live fixes must preserve paper collection while making live accounting honest

**Date:** 2026-05-02
**Status:** accepted

**Context:** The Opus Bot G audit on 2026-05-02 correctly found that Bot G's
recent readiness/reporting commits were reporting-only, but the pre-existing
trader live path still had paper-era assumptions. The operator wants to move
Bot G toward tiny-live soon and does not want the paper edge collection muted
by overbroad safety changes.

**Decision:**

1. Fix Bot G live accounting without changing paper entry logic, paper price
   bands, paper trade size, CEX/depletion settings, or paper daily entry cap.
2. Persist live Bot G orders with the CLOB response status, not hardcoded
   `PAPER_OPEN`.
3. Keep eager fill strictly paper-only.
4. When Bot G's effective CLOB path is live, use the existing shared
   `Portfolio.reconcile_live_fills()` poller to import live fills into local
   `Trade` and `Position` rows.
5. Keep proposed tiny-live caps code-visible as live-only caps:
   `10` entries/day, `$50` daily gross notional, and `5` max open positions.
   These live caps do not reduce the current paper collection cap.
6. Surface Bot G's three-flag runtime posture: `BOT_G_ENV`,
   `BOT_G_DRY_RUN`, and global `POLYMARKET_ENV`.
7. Record Bot G runtime state in `bot_g.runtime_state` events so the
   dashboard does not rely only on dashboard-process environment defaults.

**Rationale:** The useful audit lesson is not to freeze Bot G; it is to make
the first live rung observable. Bot G can continue collecting paper evidence
at current speed while the live path becomes less capable of hiding real
fills, real open orders, or global-env confusion.

**Consequences:**

- Paper Bot G behavior remains unchanged except for richer runtime telemetry.
- A future live probe can reconcile fills through the same portfolio path used
  by other live-capable bots.
- Dashboard readiness now distinguishes live intent from effective live CLOB
  state.
- Daily gross notional and max-open caps apply only when effective-paper is
  false.

**Rollback trigger:** Supersede if Bot G gets a dedicated WSS fill listener or
if the operator chooses different first-live caps.

## ADR-076: Bot G first live wallet is $200 with fixed $5 entries

**Date:** 2026-05-02
**Status:** superseded by ADR-077

**Context:** the operator selected `$200` as the intended wallet amount for the first
Bot G Prime live probe and asked that the trade amount be based on this.
Bot G is still collecting paper data, and changing the paper stake or entry
logic would weaken the comparison between paper and first live fills.

**Decision:**

1. Record `$200` as the proposed Bot G tiny-live wallet allocation.
2. Keep the first live entry size fixed at `$5`, which is `2.5%` of the
   selected wallet and matches the current paper stake.
3. Keep the proposed daily live caps at `10` entries/day and `$50` daily gross
   notional, equal to `25%` wallet turnover.
4. Keep the proposed max open positions at `5`, equal to `$25` intended open
   stake or `12.5%` of the selected wallet at `$5` entries.
5. Do not switch Bot G tiny-live sizing to bankroll-fraction or Kelly sizing
   for the first live rung.
6. Keep these settings as reporting/prep until explicit live approval.

**Rationale:** `$5` is small enough to make the first live rung a bounded
plumbing and edge-transfer test while preserving comparability with the paper
sample. Fixed-notional sizing avoids silently scaling exposure from bankroll
variables.

**Consequences:**

- Dashboard, hourly report, runbook, systemd env, and runtime-state telemetry
  now expose the `$200` wallet packet.
- Paper Bot G entry behavior and paper collection speed remain unchanged.
- Any future size increase requires a separate decision after live fill,
  slippage, reconciliation, capacity, and outlier-adjusted ROI checks pass.

**Artifacts:** `docs/bot-g-tiny-live-activation-packet-2026-05-02.md`.

**Rollback trigger:** Supersede if the operator chooses a different wallet amount,
trade size, or first-live cap packet.

## ADR-077: Bot G tiny-live cap packet uses $100 daily gross and 10 max open

**Date:** 2026-05-02
**Status:** superseded by ADR-078

**Context:** After ADR-076, the operator kept the `$200` live wallet allocation and
`$5` fixed entry size, but changed the desired first-live caps to `$100`
daily gross notional and `10` max open positions. Bot G remains paper-only
until explicit live approval.

**Decision:**

1. Keep the proposed Bot G tiny-live wallet allocation at `$200`.
2. Keep first live entries fixed at `$5`, or `2.5%` of the wallet.
3. Keep the daily entry cap at `10` entries.
4. Set the live-only daily gross notional ceiling to `$100`, or `50%` of the
   wallet.
5. Set live-only max open positions to `10`, equal to `$50` intended open
   stake or `25%` of the wallet at `$5` entries.
6. Do not activate live mode or change real wallet settings as part of this
   cap update.

**Rationale:** The updated packet reflects the operator's preferred first-live
headroom while preserving fixed-notional sizing and paper comparability. With
`$5` entries and `10` entries/day, the entry-count cap still binds actual
daily order flow at `$50`; the `$100` gross ceiling only becomes binding if a
later approved change raises entry size or entry count.

**Consequences:**

- Bot G's live-only config, Prime systemd unit, dashboard, hourly report,
  runbook, and activation packet now expose `$100` daily gross and `10` max
  open positions.
- Paper Bot G behavior remains unchanged.
- Live activation still requires a separate explicit instruction and approval
  stamp.

**Artifacts:** `docs/bot-g-tiny-live-activation-packet-2026-05-02.md`.

**Rollback trigger:** Supersede if the operator chooses a different wallet amount,
trade size, daily entry cap, gross cap, or max-open cap.

## ADR-078: Activate Bot G Prime live as separate 4c-5c tiny-live unit

**Date:** 2026-05-02
**Status:** accepted

**Context:** the operator explicitly approved activating Bot G Prime live now, with
`20` entries/day, `$100` daily gross notional, `10` max open positions, `$200`
wallet posture, and `$5` fixed entries. The existing `bot_g_prime` service is
already collecting useful `4c-8c` paper data, and mixing live rows into that
ledger would weaken the paper/live comparison.

**Decision:**

1. Add a separate live systemd unit,
   `polymarket-bot-g-prime-live.service`.
2. Run the live unit as `bot_g_prime_live`, not `bot_g_prime`.
3. Keep the live entry band at `4c-5c`:
   `BOT_G_MIN_ENTRY_PRICE=0.04` and `BOT_G_MAX_ENTRY_PRICE=0.05`.
4. Keep the existing `polymarket-bot-g-prime.service` as the `4c-8c`
   paper shadow under `bot_g_prime`.
5. Use fixed `$5` entries, `20` entries/day, `$100` daily gross notional,
   `10` max open positions, and `$200` live-wallet reporting posture.
6. Require `BOT_G_LIVE_APPROVED_AT=2026-05-02` for Bot G live startup.
7. Refuse live startup under `bot_g_prime` so paper-shadow history cannot be
   contaminated by live rows.
8. Keep `bot_g_jackpot` and `bot_g_scalp` disabled/archived for this live
   probe.

**Rationale:** A separate live ledger gives the operator clean monitoring:
real-money `4c-5c` execution on one surface, broader `4c-8c` paper collection
on the other. Jackpot and scalp variants are disabled because their archived
cohorts were negative/non-candidate and they add a second G-family live risk
path without improving the current evidence.

**Consequences:**

- The dashboard active fleet includes both `bot_g_prime_live` and the
  `bot_g_prime` paper shadow.
- Watchdog and reboot-readiness surfaces include the new live unit.
- Paper Bot G behavior remains unchanged.
- Live results must be judged separately from paper data, with post-live
  review before any size increase.

**Artifacts:** `systemd/polymarket-bot-g-prime-live.service`,
`docs/bot-g-tiny-live-runbook-2026-05-02.md`,
`docs/bot-g-tiny-live-activation-packet-2026-05-02.md`.

**Rollback trigger:** Disable/stop `polymarket-bot-g-prime-live.service` and
keep `polymarket-bot-g-prime.service` paper-only if live auth, fills,
reconciliation, slippage, or dashboard telemetry deviates from expectation.

## ADR-079: Bot D paper collection is live-shaped only

**Date:** 2026-05-02
**Status:** accepted

**Context:** Bot D remains a paper operational weather candidate, but its
historical paper evidence is contaminated by weekly lock-up, unverified
settlement-source coverage, sparse depth, and outlier-dominated resolved P&L.
the operator rejected the little-rocky ensemble migration for now and asked for the
next concrete path to make Bot D profitable and one day live-capable.

**Decision:**

1. Resume Bot D paper collection only for markets shaped like a future
   tiny-live packet.
2. Require verified settlement station/source/rounding coverage before a new
   Bot D entry is allowed.
3. Require a known Gamma `end_date` before a new Bot D entry is allowed.
4. Keep the first-wallet proof lane at `48h` max lock-up.
5. Keep `BOT_D_ENTRY_HALT` as an explicit hard switch that blocks new Bot D
   entries when set.
6. Keep Bot D live blocked until forward paper evidence clears daily-only,
   fee-adjusted, slippage-stressed, ex-outlier ROI gates.

**Rationale:** The profitable Bot D thesis is settlement-exact weather
mispricing, not generic weather forecasting. Paper trades in unverified
cities, missing-end-date markets, or weekly lock-up markets do not answer the
live question and can make the operator mistake activity for edge.

**Consequences:**

- Bot D may produce fewer paper entries.
- Every new entry should be more decision-relevant for the future live packet.
- Station verification work stays on OQ-058.
- NBM and additional model inputs remain shadow research until they improve
  forward paper Brier/log-loss against this narrower lane.

**Artifacts:** `bots/bot_d_weather/config.py`,
`bots/bot_d_weather/executor.py`, `bots/bot_d_weather/__main__.py`,
`scripts/bot_d_readiness_report.py`.

**Rollback trigger:** Supersede this ADR only if Bot D's verified daily lane
cannot collect enough sample and the operator explicitly approves a broader paper
research cohort that is labelled separately from the live-candidate lane.

## ADR-080: Bot D live-candidate paper entries require wave plus depth proof

**Date:** 2026-05-02
**Status:** accepted

**Context:** After ADR-079 narrowed Bot D to verified daily markets, the
readiness report still showed two live-readiness blockers: weak entry-depth
evidence and negative outlier-adjusted daily ROI. Production scan telemetry
also showed the immediate candidate flow was isolated rather than wave-shaped.
ADR-043 kept isolated entries active for data collection, but that broader
research posture is no longer the right default for the first live-candidate
lane.

**Decision:**

1. Default `BOT_D_REQUIRE_WAVE_FOR_ENTRY=true` for new Bot D entries.
2. Add a pre-entry depth gate: `BOT_D_DEPTH_GATE_ENABLED=true` and
   `BOT_D_MIN_ENTRY_DEPTH_USD=25`.
3. Before placing an entry, Bot D fetches and persists the token order book,
   then requires executable ask-side notional at the intended limit to cover
   both the intended order size and the `$25` minimum-depth floor.
4. Depth failures return `depth_too_low` and do not place paper orders.
5. The Bot D readiness verdict now treats insufficient depth samples, weak
   `$25` depth coverage, insufficient resolved daily sample, and negative
   ex-largest-two ROI as explicit blockers.
6. Bot D remains paper-only; this decision does not authorize live capital.

**Rationale:** Paper entries that could not have filled at visible size are
not useful live-readiness evidence. Isolated weather tails were already the
documented bleed source; continuing to collect them by default delays the
answer to the only question that matters for a first wallet: whether
settlement-exact, wave-shaped, depth-supported weather entries work after
spread, slippage, and outlier adjustment.

**Consequences:**

- Bot D will trade less often.
- New paper fills should be more transferable to a tiny-live packet.
- Historical negative/outlier-heavy rows are preserved, but the forward lane
  is stricter and easier to judge.
- If the wave/depth lane cannot collect enough sample, the fallback is not
  silent loosening; it requires a separate research cohort label or a
  superseding ADR.

**Artifacts:** `bots/bot_d_weather/config.py`,
`bots/bot_d_weather/executor.py`, `scripts/bot_d_readiness_report.py`.

**Rollback trigger:** Supersede only if the strict lane collects fewer than
`10` depth-supported entries over a full market week and the operator explicitly
chooses a labelled broader paper-research lane.

## ADR-081: Bot G records XRP/DOGE while live stays BTC/ETH/SOL

**Date:** 2026-05-02
**Status:** accepted

**Context:** the operator asked whether the other visible short-horizon crypto
markets, especially XRP and Dogecoin, were being recorded so they could be
evaluated later. Bot G Prime Live is already active with real funds, so any
market-universe expansion must not change the live experiment. The current
live proof lane is still BTC/ETH/SOL at `4c-5c`; XRP/DOGE need forward paper
evidence before they can be considered for live trading.

**Decision:**

1. Expand the Bot E recorder default CEX/market discovery universe to include
   BTC, ETH, SOL, XRP, and DOGE.
2. Allow the Bot G paper shadow (`bot_g_prime`) to evaluate BTC/ETH/SOL/XRP/
   DOGE so it can collect forward transfer evidence.
3. Keep Bot G Prime Live (`bot_g_prime_live`) explicitly locked to
   BTC/ETH/SOL.
4. Add a Bot G allowed-symbol guard so systemd unit env must opt each runtime
   into its intended symbol universe.
5. Add DOGE/XRP parsing coverage to recorder and Bot G analysis tests.

**Rationale:** Wider recording is useful and low-risk; widening live trading
is a strategy change. Separating the paper shadow from the live unit preserves
the current live proof while collecting the data needed to judge XRP/DOGE
later.

**Consequences:**

- Recorder load increases modestly because XRPUSDT and DOGEUSDT CEX streams
  are added.
- Paper Bot G can create XRP/DOGE paper entries if they pass the existing
  entry gates.
- Live Bot G does not trade XRP/DOGE unless a future ADR and unit config
  change explicitly approve it.
- Future feature-analysis reports can split XRP/DOGE once enough sample
  exists.

**Artifacts:** `bots/bot_e_recorder/config.py`,
`bots/bot_e_recorder/market_discovery.py`,
`bots/bot_g_longshot/config.py`, `bots/bot_g_longshot/__main__.py`,
`systemd/polymarket-bot-e-recorder.service`,
`systemd/polymarket-bot-g-prime.service`,
`systemd/polymarket-bot-g-prime-live.service`,
`scripts/bot_g_feature_analysis.py`.

**Rollback trigger:** Remove XRP/DOGE from recorder and paper-shadow env if
the added universe causes recorder instability, materially stale books for
BTC/ETH/SOL, or noisy paper entries that cannot be cleanly separated in
reporting.

## ADR-082: Bot D live-readiness blockers are enforced at runtime

**Date:** 2026-05-02
**Status:** accepted

**Context:** A follow-up Bot D live-readiness audit found that dashboard
blockers were advisory rather than executable. The highest-risk gaps were:
`BOT_D_ENV=live` plus global live mode could place real orders without a
readiness verdict; NWS fallback forecasts could act as both signal and veto;
paper exits were too optimistic versus live spread/fee/slippage; live SELL
exits could sit stale; and scipy/skew-normal degradation was only logged.

**Decision:**

1. Add `BOT_D_LIVE_AUTHORIZED=false` as a separate operator flag. Live Bot D
   entries require both this flag and `scripts/bot_d_readiness_report.py`
   returning `live_ready=true`.
2. Block entries from `forecast_source=nws_fallback` by default via
   `BOT_D_ALLOW_NWS_FALLBACK_ENTRY=false`; the strategy no longer treats the
   NWS fallback value as an independent NWS second opinion.
3. Price paper exits from the current best bid when available, apply
   `BOT_D_PAPER_EXIT_SLIPPAGE_BPS=50`, and charge weather taker fees on
   synthetic SELL fills.
4. Price live exits from best bid minus `BOT_D_LIVE_EXIT_LIMIT_OFFSET=0.005`.
   Cancel and warn on stale live SELL orders after
   `BOT_D_EXIT_STALE_MIN=10`.
5. Persist `bot_d.skewnorm_fallback` events when scipy/skewnorm degrades to
   Gaussian and treat recent fallback as a readiness blocker.
6. Surface the new live-auth, fallback, and skew-degradation state on the Bot
   D dashboard.
7. Bot D remains paper-only; this decision does not authorize live capital.

**Rationale:** A live candidate needs code-level stops, not dashboard-only
advice. The current evidence still fails depth and outlier-adjusted ROI gates,
so the only safe default is to make the live path impossible until both the
operator and the readiness report agree.

**Consequences:**

- Bot D cannot accidentally go live from env-flag drift.
- Bot D will place fewer paper entries during Open-Meteo cooldowns.
- Forward paper ROI will be more conservative because exit spread, slippage,
  and fees are charged.
- Stale exit handling is now visible in events and dashboard state.

**Artifacts:** `bots/bot_d_weather/config.py`,
`bots/bot_d_weather/executor.py`, `bots/bot_d_weather/strategy.py`,
`scripts/bot_d_readiness_report.py`, `dashboard/static/app.js`.

**Rollback trigger:** Supersede only after a new live packet clears the
quantitative gates and the operator explicitly approves the exact authorization flag
and snapshot-bound live posture.

## ADR-083: Bot G tiny-live crosses one tick for transfer

**Date:** 2026-05-03
**Status:** accepted

**Context:** Bot G Prime Live is active at BTC/ETH/SOL `4c-5c` with `$5`
entries. Overnight paper/live comparison showed a transfer gap: the paper
shadow bought a winning ETH/NO setup at `5c`, while live saw the same
condition, posted at `4c`, and did not fill. the operator approved a narrow change to
increase live trade flow without widening the live band or adding new live
symbols.

**Decision:**

1. Keep Bot G Prime Live restricted to BTC/ETH/SOL and `4c-5c`.
2. Add `BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS`, defaulting to `0`, so live
   runtimes can submit a limit up to N ticks above the observed qualifying
   ask.
3. Set the live unit to `BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS=1`.
4. Cap the submitted live limit at `BOT_G_MAX_ENTRY_PRICE`; with the current
   live unit this means the limit cannot exceed `5c`.
5. Size live orders against the submitted limit price, not the observed ask,
   so worst-case notional remains within the `$5` fixed trade budget.
6. Set `BOT_G_SCAN_INTERVAL_S=5` on the live unit to reduce missed short
   entry windows.
7. Leave the `bot_g_prime` paper shadow unchanged so it remains a comparison
   baseline.

**Rationale:** This changes execution transfer, not the evidence universe.
The live proof currently needs fills to test slippage/reconciliation and
edge; posting one tick too passively can create false negatives where the
paper candidate was valid but live never participates. Capping at `5c` keeps
the existing live thesis intact.

**Consequences:**

- Live fills should increase.
- Average live entry price may be worse by up to one tick.
- Size at `4c` candidates drops from `125` shares to `100` shares when the
  submitted limit is `5c`, keeping max notional near `$5`.
- Paper/live comparisons must account for the new submitted-limit field and
  the observed ask recorded in `bot_g.entry_placed` payloads.

**Artifacts:** `bots/bot_g_longshot/config.py`,
`bots/bot_g_longshot/__main__.py`,
`systemd/polymarket-bot-g-prime-live.service`,
`tests/test_bot_g_longshot.py`.

**Rollback trigger:** Set `BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS=0` and
restore `BOT_G_SCAN_INTERVAL_S=10` if live slippage exceeds one tick, fills
cluster in weak non-transferable setups, or live ROI diverges materially from
the `4c-5c` paper shadow after the next milestone review.

## ADR-084: Bot D gets a separate tiny-live plumbing probe

**Date:** 2026-05-03
**Status:** accepted

**Context:** Bot D paper is now profitable on raw paper accounting, but the
readiness report still fails the durable live-readiness evidence gates,
especially weak entry-depth sample and negative ex-largest-two daily ROI. the operator
approved a deliberately small real-wallet probe because paper fills do not
prove live transfer: live can miss fills, pay spread, and expose
reconciliation or stale-exit faults that paper cannot measure.

**Decision:**

1. Keep the existing `bot_d` service running as the paper shadow.
2. Add a separate live identity and ledger: `bot_d_live_probe`.
3. Prepare a separate `polymarket-bot-d-live.service` with:
   - wallet allocation posture: `$200`;
   - fixed entry size: `5` shares;
   - max order notional: `$4`;
   - max daily gross notional: `$50`;
   - max open exposure: `$50`;
   - max concurrent positions: `10`.
4. Add `BOT_D_ID_OVERRIDE` so the same Bot D code can write either `bot_d`
   paper rows or `bot_d_live_probe` live rows without mixing ledgers.
5. Let the live-readiness gate permit only this named plumbing probe when
   `BOT_D_LIVE_AUTHORIZED=true`,
   `BOT_D_LIVE_PROBE_MODE=plumbing`,
   `BOT_D_ID_OVERRIDE=bot_d_live_probe`, and
   `BOT_D_LIVE_APPROVED_AT=2026-05-03` are all set.
6. Keep stricter Bot D live-shape protections active for the probe:
   verified settlement required, known end date required, wave required,
   depth gate enabled, `$25` minimum entry-depth evidence, NWS fallback
   entries disabled, live exits best-bid-based, and stale exits warned after
   `10` minutes.
7. Surface the live probe separately in the registry, watchdog cap
   membership, and dashboard.
8. Do not start or enable the live unit during prep; final service activation
   remains a separate explicit operator action.

**Rationale:** This is a transfer-quality experiment, not a size-up. The
small fixed-share order reveals whether the model can place, fill, record,
exit, and reconcile live weather trades while capping loss from a bad first
sample. The separate bot id keeps live fills auditable and leaves the paper
Bot D series intact.

**Consequences:**

- Bot D can gather real fill/slippage/reconciliation evidence at minimum
  practical size.
- Dashboard and reports can compare `bot_d` paper behaviour with
  `bot_d_live_probe` live behaviour without ledger contamination.
- Full Bot D live readiness remains blocked by OQ-058 and the live-transfer
  proof tracked in OQ-067.
- Any untracked live fill, exit mismatch, stale live exit, or cap breach is a
  stop condition.

**Artifacts:** `bots/bot_d_weather/config.py`,
`bots/bot_d_weather/executor.py`, `bots/bot_d_weather/__main__.py`,
`core/bot_registry.py`, `core/watchdog.py`,
`dashboard/runtime_queries.py`, `dashboard/static/app.js`,
`systemd/polymarket-bot-d-live.service`,
`docs/bot-d-tiny-live-runbook-2026-05-03.md`.

**Rollback trigger:** Stop and disable `polymarket-bot-d-live.service`, keep
`bot_d` paper running, and leave `bot_d_live_probe` rows as audit evidence if
any live fill is untracked, any live exit cannot be matched, daily gross or
open exposure exceeds the approved caps, or realised live slippage/rejects
make the probe non-informative.

## ADR-085: Bot G Prime Live expands to 3.5c-5.5c tiny-live band

**Date:** 2026-05-03
**Status:** accepted

**Context:** Bot G Prime Live is now producing real fills, but the `4c-5c`
band can still miss live transfer opportunities near the edges. the operator
explicitly approved widening Bot G Prime Live to observed `3.5c-5.5c` while
keeping the same one-tick transfer bid, symbols, trade size, daily gross cap,
daily entry cap, and max-open cap. This is a live real-money entry-band
change and supersedes the `4c-5c` live-band constraint in ADR-078 and the
non-widening clause in ADR-083.

**Decision:**

1. Set `bot_g_prime_live` observed-entry bounds to:
   `BOT_G_MIN_ENTRY_PRICE=0.035` and `BOT_G_MAX_ENTRY_PRICE=0.055`.
2. Keep `BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS=1`.
3. Keep `BOT_G_ENTRY_TICK_SIZE=0.01`, so an observed `4.5c` ask can submit a
   `5.5c` limit, while any observed `5.5c` ask is capped at `5.5c`.
4. Keep the same live caps: `$5` fixed entry budget, `20` entries/day,
   `$100` daily gross, `10` max open positions, `$200` wallet posture.
5. Keep the same live universe: BTC/ETH/SOL only. XRP/DOGE remain
   paper/recording-only until OQ-066 clears.
6. Keep the `bot_g_prime` paper shadow at `4c-8c` for broader data
   collection.
7. Continue to size orders against the submitted limit price so worst-case
   notional remains within the `$5` fixed budget.

**Rationale:** The point of the tiny-live phase is to get enough real
transfer data to judge fillability, slippage, reconciliation, and early edge.
The added lower slice (`3.5c-4c`) is cheaper than the prior live band, and
the added upper slice (`5c-5.5c`) is small enough to gather edge evidence
without changing the cap packet. More live rows are useful only while caps and
ledger separation remain strict.

**Consequences:**

- Live trade count should rise versus the original `4c-5c` band.
- Average entry price can rise above `5c`, capped at `5.5c`.
- The `5c-5.5c` slice must be reviewed separately from exact `4c-5c` because
  `4c-5c` remains the strongest historical signal.
- Paper/live comparison must track observed ask versus submitted limit.

**Artifacts:** `bots/bot_g_longshot/config.py`,
`systemd/polymarket-bot-g-prime-live.service`,
`tests/test_bot_g_longshot.py`,
`docs/active-operating-model-2026-05-02.md`.

**Rollback trigger:** Restore `BOT_G_MIN_ENTRY_PRICE=0.04` and
`BOT_G_MAX_ENTRY_PRICE=0.05` if the added `3.5c-4c` or `5c-5.5c` slices show
materially worse fill quality, settlement loss rate, or slippage than exact
`4c-5c`, or if live daily loss approaches the existing cap faster than the
original band.

## ADR-086: Bot D live-probe activation requires audit hardening

**Date:** 2026-05-03
**Status:** accepted

**Context:** Opus reviewed the prepared Bot D tiny-live probe at HEAD
`dc7b6b8`. Verdict was "PASS WITH FIXES": the real-money entry path and caps
were sound, but activation should not depend on shared `.env` assumptions,
dashboard labels, or manual skew-normal preflight checks.

**Decision:**

1. Give `bot_d_live_probe` a dedicated watchdog mode key,
   `BOT_D_LIVE_PROBE_ENV`, so shared `BOT_D_ENV=paper` cannot make watchdog
   cancel routing build a paper CLOB for live probe orders.
2. Move `EnvironmentFile=` before `Environment="BOT_D_ENV=paper"` in the
   paper Bot D unit, so the service-local paper setting wins over `.env`.
3. Keep the live unit's env ordering as-is and add
   `BOT_D_INITIAL_USD=200` so the probe baseline is explicit.
4. Block plumbing-mode live entries inline when a recent
   `bot_d.skewnorm_fallback` event exists for `bot_d_live_probe`.
5. Require `BOT_D_LIVE_FIXED_SHARES > 0` when Bot D is in live plumbing mode,
   so a missing env line cannot silently revert to Kelly-sized live entries.
6. Rename the dashboard live-probe open-order exposure field from
   `paper_pnl` to `open_orders_pnl` and add a `bot_d_live_probe` initial
   USD baseline.
7. Add regression coverage for the dedicated watchdog routing, probe
   authorization guards, notional/open-exposure caps, skew fallback blocker,
   fixed-share import guard, systemd env precedence, and live-probe dashboard
   labeling.

**Rationale:** These fixes remove activation-time ambiguity without changing
Bot D's market-selection strategy or approved live caps. The probe remains a
minimum-size execution-transfer test.

**Consequences:**

- Watchdog live cancels for `bot_d_live_probe` no longer depend on shared
  Bot D paper env.
- Paper Bot D cannot be flipped live by a later `.env` edit that sets
  `BOT_D_ENV=live`.
- A broken scipy/skew-normal environment blocks live probe entries directly,
  not only through the readiness report.
- Dashboard JSON no longer labels live-probe exposure as paper P&L.
- Final live activation still requires explicit operator instruction.

**Artifacts:** `bots/watchdog_daemon.py`, `systemd/polymarket-bot-d.service`,
`systemd/polymarket-bot-d-live.service`,
`bots/bot_d_weather/config.py`, `bots/bot_d_weather/executor.py`,
`dashboard/runtime_queries.py`, `tests/bot_d_weather/test_executor.py`,
`tests/dashboard/test_dashboard.py`, `tests/test_watchdog_daemon_modes.py`,
`tests/test_bot_registry.py`.

**Rollback trigger:** Revert only if a deployment environment cannot support
the dedicated live-probe env key or the fixed-share import guard. Do not start
`polymarket-bot-d-live.service` until these guards are present in production.

## ADR-087: Bot D live probe activated at minimum size

**Date:** 2026-05-03
**Status:** accepted

**Context:** the operator explicitly instructed: "okay take it live now." ADR-084
prepared the separate `bot_d_live_probe` ledger and ADR-086 closed the Opus
pre-activation audit gaps. Production preflight on the bot LXC container passed: scipy
imports, watchdog routes `bot_d_live_probe` through `BOT_D_LIVE_PROBE_ENV`,
dashboard exposes the live probe separately, and the live service was
inactive/disabled with zero fills and zero open orders before activation.

**Decision:**

1. Start and enable `polymarket-bot-d-live.service` on the bot LXC container.
2. Keep the approved minimum-size packet unchanged:
   - `$200` wallet allocation posture;
   - `5` shares per entry;
   - `$4` max order notional;
   - `$50` daily gross notional;
   - `$50` max open exposure;
   - `10` max concurrent positions.
3. Keep `bot_d` paper running in parallel as the shadow ledger.
4. Keep NWS fallback live entries disabled and the verified-settlement,
   known-end-date, wave-required, depth-gated lane active.
5. Stop immediately on any untracked fill, exit mismatch, stale live exit,
   cap breach, NWS fallback live entry, skew-normal fallback, or ledger
   pollution between `bot_d` and `bot_d_live_probe`.

**First-cycle result:** The live unit started at `2026-05-03 08:49 UTC`.
Startup logged `bot_d: executor enabled (bot_id=bot_d_live_probe
bot_d_env=LIVE)`. The first scan saw `12` raw weather markets, kept `7`,
evaluated `7` via `multi_model`, found `0` non-skip edges, and placed `0`
orders. Dashboard after the first cycle showed `bot_d_live_probe` active with
`0` live fills, `0` live open orders, and `$0` reserved notional. Paper Bot D
remained active.

**Consequences:**

- Bot D is now a real-money tiny-live probe.
- The experiment has not yet produced a live order or fill.
- OQ-067 now tracks live transfer milestones before any continuation/scale
  decision.

**Artifacts:** `systemd/polymarket-bot-d-live.service`, dashboard
`/api/bot-d`, `docs/bot-d-tiny-live-runbook-2026-05-03.md`, OQ-067.

**Rollback trigger:** Disable and stop `polymarket-bot-d-live.service` on any
runbook stop condition or if the first live fill is not recorded under
`bot_d_live_probe`.

## ADR-088: Bot G live entries require a fresh pre-submit clock check

**Date:** 2026-05-03
**Status:** accepted

**Context:** the operator noticed Bot G Prime Live fills displaying at `1c` in the
Polymarket UI and asked whether the bot was still entering around the intended
`45s` pre-close window. Production inspection showed the bot was not
submitting `1c` limits: recent orders submitted `4c`, `5c`, or `5.5c` limits
and received price-improved `1c` fills. The real issue was timing discipline:
the trader computed `t_to_res_sec` once at scan start, then performed book,
filter, depth, and CLOB work before submission. That stale timestamp could
make an entry look `40s` pre-close while the order reached the exchange at or
after the visible close.

**Decision:**

1. Keep the Bot G Prime Live thesis unchanged: observed `3.5c-5.5c`, one-tick
   transfer bid capped at `5.5c`, `$5` entries, BTC/ETH/SOL only.
2. Add `BOT_G_MIN_ENTRY_LEAD_SECONDS` with default `5`.
3. Recompute wall-clock `fresh_t_to_res_sec` immediately before sizing and
   submission.
4. Reject entries whose fresh pre-submit lead is below the configured floor.
5. Emit `bot_g.entry_stale_time_rejected` events with the initial and fresh
   time-to-resolution values for audit.

**Consequences:**

- Bot G cannot use stale scan time to submit into/after close.
- This is an execution-timing guardrail, not a price-band, sizing, symbol, or
  wallet change.
- A small number of last-second entries may be skipped; that is intentional
  because those fills are not clean proof of the `45s` transfer thesis.

**Artifacts:** `bots/bot_g_longshot/__main__.py`,
`bots/bot_g_longshot/config.py`,
`systemd/polymarket-bot-g-prime-live.service`,
`tests/test_bot_g_longshot.py`.

**Rollback trigger:** Revert only if production logs show valid pre-close
orders being rejected while `fresh_t_to_res_sec >= 5`, or if the guard creates
an unexpected live submission failure mode. Do not remove the guard to chase
entry count without an explicit operator decision.

## ADR-089: Bot G Prime Live scans earlier and faster while keeping the fresh-clock guard

**Date:** 2026-05-03
**Status:** accepted

**Context:** After ADR-088 deployed, Bot G Prime Live remained active and
healthy but stopped placing new trades after `2026-05-03 08:30 UTC`. Read-only
production validation showed CLOB auth/polling was healthy, caps were not hit
(`5/20` daily entries, `0/10` open positions), and the dashboard matched the
database. Two later entry attempts reached the submit path but were rejected
by the fresh-clock guard because the order would have gone out after the close
(`fresh_t_to_res_sec=-23s` and `-4s`). the operator approved changing timing
parameters to improve live transfer without loosening the strategy band.

**Decision:**

1. Change only `polymarket-bot-g-prime-live.service`.
2. Increase `BOT_G_PRIME_ENTRY_SECONDS` from `45` to `60`.
3. Keep `BOT_G_ENTRY_SECONDS_BEFORE_RES` aligned at `60`.
4. Lower `BOT_G_SCAN_INTERVAL_S` from `5` to `2`.
5. Keep `BOT_G_MIN_ENTRY_LEAD_SECONDS=5`.
6. Keep the live band, symbols, sizing, and caps unchanged:
   observed `3.5c-5.5c`, one-tick transfer bid capped at `5.5c`,
   BTC/ETH/SOL only, `$5` entries, `20` entries/day, `$100` daily gross,
   and `10` max open.

**Consequences:**

- Bot G Prime Live starts looking `15s` earlier and scans more often, so it
  should have more time to submit before close.
- The fresh-clock guard remains the final protection against stale scan time
  and late orders.
- This change can increase trade count, but it does not expand the price
  band, symbol universe, wallet allocation, or per-trade risk.

**Artifacts:** `systemd/polymarket-bot-g-prime-live.service`,
`tests/test_bot_g_longshot.py`.

**Rollback trigger:** Revert to `45s` / `5s` if the live bot begins taking
materially worse fills, shows a higher late-order/rejection rate, or the
expanded timing window degrades the observed live cohort versus the paper
shadow.

## ADR-090: Bot D live reconciliation ignores fills without a known Bot D order

**Date:** 2026-05-03
**Status:** accepted

**Context:** After Bot D tiny-live activation, the operator asked why no Bot D live
trades had appeared. Production logs showed Bot D was scanning normally but
all candidates were skipped before entry, mostly by the NWS second-opinion
veto. The same inspection found repeated `bot_d.reconcile.fail` warnings:
Bot D's live process polled wallet-level CLOB trades and attempted to write
unrelated fills under `bot_d_live_probe`, then failed the DB foreign-key check
because no matching Bot D order existed. Bot G Prime Live already avoids this
shared-wallet hazard with `require_known_order=True`.

**Decision:**

1. Keep Bot D tiny-live entry filters unchanged.
2. Keep the strict NWS veto unchanged.
3. Change only live fill reconciliation so Bot D calls
   `Portfolio.reconcile_live_fills(..., require_known_order=True)`.
4. Ignore CLOB fills unless their `order_id` matches a known local Bot D order.

**Consequences:**

- Bot D no longer attempts to import Bot G or manual wallet fills as
  `bot_d_live_probe`.
- The no-trade state remains explained by strategy gates, not a broken scanner.
- A genuine Bot D live fill still reconciles normally because the Bot D order
  row exists before the exchange fill arrives.

**Artifacts:** `bots/bot_d_weather/__main__.py`,
`tests/bot_d_weather/test_main_safety.py`.

**Rollback trigger:** Revert only if a confirmed Bot D order fills on CLOB but
is not imported despite the matching local order row existing.

## ADR-091: Bot D live NWS veto floor is loosened to 3F with shadow counters

**Date:** 2026-05-03
**Status:** accepted

**Context:** Bot D live probe remained healthy but had not produced any live
orders. Production scans showed the dominant blocker was the NWS
second-opinion veto: recent cycles evaluated `8-9` markets and skipped
`7-8` per scan as `nws_disagrees`. the operator wanted a small loosen to collect live
transfer data, while also measuring whether the loosened lane would admit
useful or noisy candidates.

**Decision:**

1. Keep the independent NWS second-opinion guard active.
2. Keep NWS fallback live entries disabled.
3. Make the NWS veto floor env-configurable with
   `BOT_D_NWS_VETO_MIN_THRESHOLD_F`.
4. Keep the default floor at `2.0F` for paper/backward-compatible behavior.
5. Set the live probe unit to `BOT_D_NWS_VETO_MIN_THRESHOLD_F=3.0`.
6. Add `nws_shadow` scan-summary counts for `3F`, `4F`, and NWS-off lanes:
   would-clear-edge and wave-gated would-tradeable counts.

**Consequences:**

- Bot D live can admit candidates where model/NWS disagreement is between
  `2.0F` and `3.0F`, improving the chance of first-fill transfer evidence.
- The guard still blocks larger disagreements and single-source NWS fallback
  entries.
- The shadow counters let us evaluate whether `3F`, `4F`, or NWS-off would
  have materially changed entry flow before changing the guard again.
- No wallet, size, daily gross, open exposure, or concurrent-position cap
  changes.

**Artifacts:** `bots/bot_d_weather/config.py`,
`bots/bot_d_weather/strategy.py`, `bots/bot_d_weather/__main__.py`,
`systemd/polymarket-bot-d-live.service`,
`tests/bot_d_weather/test_audit_fixes.py`,
`tests/bot_d_weather/test_weather.py`, `tests/test_bot_registry.py`.

**Rollback trigger:** Restore the live floor to `2.0F` if the looser lane
places low-quality fills, creates exit mismatches, or the shadow counters show
the extra candidates are isolated/noisy rather than useful transfer evidence.

## ADR-092: Retire Bot E active trading and keep recorder/data reuse

**Date:** 2026-05-03
**Status:** accepted

**Context:** Bot E / Maker Flow was still active as a lower-priority
paper-only maker-flow strategy after ADR-071 and ADR-059. Sessions 109, 111,
and 112 built and ran fill-conditioned replay packets to test whether the
method had transferable edge after actual fills, no-fills, adverse movement,
and outcome labels. The 24h packet showed actual labelled fills at `-9.9%`
ROI before costs and optimistic replay at only `+1.0%` before costs. The
larger 72h packet produced `807` denominator rows (`737` optimistic replay
signals and `70` actual paper orders), with outcome coverage on `721/807`
rows and `377/419` filled rows. Actual labelled fills were `-12.7%` ROI
before costs; optimistic replay was only `+1.2%` before costs and turned
negative after a flat `1c`/share execution haircut. Actual unfilled labelled
orders missed `19` winners and avoided only `3` losers. The 24h `75c+`
actual-order bucket fell to `+1.0%` before costs in the 72h packet and
negative after `1c`/share. External model review, using only sanitized
aggregate metrics, confirmed the local conclusion.

**Decision:**

1. Retire Bot E as an active trading-strategy development track.
2. Do not tune Bot E thresholds, maker offsets, TTL, sizing, model inputs,
   execution behavior, or live posture from the current evidence.
3. Keep the Bot E recorder/data path as shared market-data infrastructure.
4. Keep the bounded replay/outcome-label tooling as reusable validation
   infrastructure.
5. Keep OBI, CEX-flow, depth, TTE, and adverse-movement feature extraction as
   offline research inputs for other bots.
6. Treat the existing optimistic last-trade fill replay as an upper-bound
   diagnostic only, not a proof of tradable edge.
7. Park Bot E maker-flow signal and maker-only execution logic as a failed
   strategy case study.

**Consequences:**

- Bot E is no longer a candidate for live-money graduation.
- Bot E is no longer a target for threshold/model/execution tuning.
- Active engineering time should move to Bot G live transfer, Bot D live
  probe evidence, and reusable data/replay infrastructure.
- Recorder data can still support Bot G/Bot D/Bot C research where useful.
- The dashboard/registry can be cleaned up in a later implementation step so
  Bot E is shown, if at all, as data infrastructure rather than an active
  trading bot.
- This ADR records a strategy decision only; no service was stopped or
  runtime setting changed in the ADR-writing session.

**Reusable components:**

- `bots/bot_e_recorder/` market tape.
- `scripts/bot_e_fill_conditioned_replay.py` bounded denominator replay.
- `scripts/bot_e_cancel_autopsy.py` actual paper-order/book diagnostics.
- `scripts/bot_e_extract_features.py` and `bots/bot_e_btc_scalp/features.py`
  as offline feature sources after reuse review.
- Toxic-fill and adverse-movement metrics as possible cross-bot risk filters.

**Reconsideration gate:** Reopen Bot E trading development only if a future
ADR presents fresh copied-data evidence where actual paper-order EV, not just
optimistic replay EV, is positive after realistic fees/slippage; the result
survives at least a 7d bounded window; adverse-fill risk is predictable before
entry rather than only visible after fill; and the edge is not concentrated in
a tiny bucket.

**Artifacts:** `docs/reports/bot-e-phase2-fill-replay-2026-05-03.md`,
`docs/reports/bot-e-phase3-ev-2026-05-03.md`,
`docs/reports/bot-e-phase3-72h-ev-2026-05-03.md`,
`docs/reports/bot-e-external-consensus-2026-05-03.md`, OQ-048.

**Rollback trigger:** Reverse only if fresh actual-order evidence clears the
reconsideration gate above. Do not reverse based on optimistic replay alone.

## ADR-093: Retire Bot C active trading and keep Pyth/Hermes research assets

**Date:** 2026-05-04
**Status:** accepted

**Context:** Bot C / Pyth Directional was originally archived by ADR-034 after
Pyth Pro ingest failed silently and the strike-priced market universe proved
thin. It was later allowed to run as a Hermes free-tier paper/research lane,
creating a code-state mismatch: `BOT_C_ARCHIVED=true` remains the code
default, while production service posture kept the paper executor active.
The 2026-05-02 extraction audit and 2026-05-03 tweet-edge handoff identified
reusable components but did not establish a tradable edge.

The final review combined local code/data inspection, sanitized external LLM
checks, and Opus codebase review. All reviews reached the same conclusion:
Bot C can produce useful market-data and probability-model research, but it
is not working as a trading bot. Recent production evidence showed a thin
candidate universe, weak paper results, poor fill evidence, and no validated
walk-forward edge. Structural live-readiness gaps remain: no hard
decision-time stale-bar assertion, no implemented live SELL path, synthetic
paper fills that do not model queue/adverse selection, and a backtest harness
that is too coarse to prove net EV after fees, spread, slippage, and fill
costs.

**Decision:**

1. Retire Bot C as an active/paper trading-strategy development track.
2. Remove Bot C from active dashboard, fleet-cap, reboot-readiness, watchdog,
   and long-running service expectations.
3. Disable the production `polymarket-bot-c.service` and keep the repo
   systemd unit inert by default.
4. Preserve Bot C code and data for research reuse rather than hard-deleting
   the bot package.
5. Treat any final Hermes-corpus replay as optional, read-only research. It
   can improve the archive record, but it is not required to justify
   decommissioning.
6. Do not invest in Bot C parser widening, endpoint work, thresholds, sizing,
   execution, or live posture unless a new ADR presents fresh evidence that
   clears the reversal gate.

**Reusable components retained:**

- `core/pyth_feeds.py` feed registry.
- `core/pyth_models.py` bar and decision schemas.
- `core/pyth_ingest.py` Pyth/Hermes capture logic.
- `bots/bot_c_pyth/strategy.py` GBM/barrier and fee-net probability math.
- `bots/bot_c_pyth/discovery.py` strike-priced question parser.
- Historical Pyth/Hermes bars and `bot_c_decisions` rows as read-only audit
  and replay assets.
- Order-status guard and paper/live isolation patterns as reference code.

**Reversal criteria:**

Bot C can return to active status only through a new ADR that supersedes both
ADR-034 and ADR-093 and attaches evidence for all of the following:

1. A materially larger actionable universe, or a new thesis that does not
   depend on the old thin traditional-asset strike market set.
2. Strict walk-forward replay/backtest evidence over enough out-of-sample data
   to produce at least `100` simulated trades.
3. Positive net EV after realistic Polymarket fees, spread, slippage,
   fill/no-fill, and adverse-selection costs.
4. Decision-time bar freshness assertions with hard skips on stale feeds.
5. Complete and tested paper/live exit handling, including live SELL support.
6. Calibration and mark-out evidence showing the model is not merely selecting
   stale or adversely filled prices.

**Consequences:**

- Active engineering attention moves to Bot G live-transfer evidence, Bot D
  live-probe/source-certainty evidence, and shared replay/data infrastructure.
- Bot C can still inform future directional research, but only as a preserved
  research asset.
- The dashboard should no longer show a Pyth Directional active tab or active
  fleet tile.
- Reboot readiness should no longer require `polymarket-bot-c.service` to be
  enabled.

**Artifacts:** `core/bot_registry.py`, `dashboard/static/index.html`,
`dashboard/static/app.js`, `scripts/verify_reboot_readiness.sh`,
`systemd/polymarket-bot-c.service`, OQ-061,
`docs/active-operating-model-2026-05-02.md`, `docs/kill-dates.md`.

**Rollback trigger:** Reverse only if the full reversal criteria above clear.
Do not reverse based on diagnostic labels, optimistic replay, parser widening,
or Hermes ingest freshness alone.

## ADR-094: Make Bot G Prime Live optional labels non-blocking and index recorder hot paths

**Date:** 2026-05-04
**Status:** accepted

**Context:** Bot G Prime Live is running the tiny-live proof lane under
OQ-063. After the 2026-05-04 tweet-edge handoff review and Opus audit, the
next accepted phase plan was:

1. Phase 0: fix timing telemetry so it reports true step deltas.
2. Phase 1: make disabled Prime analysis labels non-blocking in live mode.
3. Phase 2: add recorder indexes for Bot G hot-path reads.
4. Phase 3: keep the book query semantics but avoid the slow `OR` shape.
5. Phase 4: expand reporting into a full missed-trade funnel.
6. Phase 5: add analysis-only labels for symbol, price zone, setup label, and
   fresh lead bucket.

The latest live-transfer report showed a severe transfer bottleneck: `13`
stale rejects, `7` placed live orders, `6` fills, `1` no-fill, and timing
payloads where cumulative `prime_signal_ms` averaged about `54s`. The live
unit is Prime-only, but `BOT_G_PRIME_REQUIRE_CEX_CONFIRM=false` and
`BOT_G_PRIME_REQUIRE_DEPLETION=false`; those fields were being collected as
labels, not gates. A label should not consume nearly the entire `60s` live
entry window.

**Decision:**

1. Keep Bot G Prime Live strategy unchanged: no change to entry band, symbols,
   fixed trade size, caps, wallet, live approval, or fresh-clock guard.
2. In effective-live mode, skip pre-submit CEX/depletion lookups when their
   gates are disabled and record a `skipped` label instead.
3. Keep the existing behavior when a gate is enabled: if CEX confirmation or
   depletion is required, it must still run before submit and can reject.
4. Record both timing deltas and cumulative timing payloads so future reports
   can distinguish step cost from total elapsed time.
5. Add recorder indexes:
   `pm_events(asset_id, event_type, received_at_ms)` and
   `cex_trades(symbol, trade_time_ms)`.
6. Rewrite the Bot G book lookup away from a single `(asset_id=? OR
   asset_id=?)` query while preserving OQ-043 semantics that price-change
   events may be keyed by condition id.
7. Expand the read-only Bot G live-transfer report with funnel counts, symbol
   labels, and fresh-lead buckets.

**Consequences:**

- Live entries can submit earlier when optional labels are disabled, which may
  increase valid live attempts without changing the actual entry criteria.
- The first post-deploy day may show more live attempts; existing `20/day`,
  `$100/day`, `10` max-open, and `$5` size caps remain the hard risk bounds.
- CEX/depletion labels for live disabled-gate entries are deliberately marked
  skipped; deeper labels can be filled later by read-only/offline reporting if
  needed.
- Recorder index creation is a production maintenance action on the large
  recorder DB and can take several minutes. It does not change recorder rows
  or trading rules.

**Rollback trigger:** If post-deploy Bot G entries show unexpected band/symbol
drift, cap breach, missing accounting, or increased untracked live exposure,
revert the Bot G live code to the prior pre-submit label behavior and keep the
recorder indexes in place unless they are shown to harm recorder write health.

## ADR-095: Loosen Bot D tiny-live plumbing enough to collect real fills

**Date:** 2026-05-04
**Status:** accepted

**Context:** Bot D live probe was active but had no fills while paper appeared
healthy. Production inspection on the bot LXC container showed the paper "fills" were mostly
settlement/reconciliation from older paper positions, while live had reached
entry attempts but was blocked by execution plumbing and overly strict probe
settings:

1. Two live attempts failed with Polymarket `not enough balance / allowance`
   because py-clob-client-v2 neg-risk maker orders require allowance/approval
   for the neg-risk adapter address.
2. The `$4` max-order cap blocked fixed 5-share entries when price exceeded
   80c.
3. The `$25` depth gate blocked tiny 5-share orders in thin weather books.
4. `BOT_D_REQUIRE_WAVE_FOR_ENTRY=true` blocked isolated setups, leaving no
   live execution data.

the operator explicitly approved mixing the fixes and wanted Bot D trading at the
smallest practical live size.

**Decision:**

1. Keep Bot D tiny-live caps small and unchanged except max order notional:
   5 fixed shares, `$5.25` max order notional, `$50` max daily gross,
   `$50` max open exposure, and 10 max concurrent positions.
2. Keep safety filters: NWS veto enabled, NWS fallback entries blocked,
   verified settlement required, known end date required, live authorization
   required, separate `bot_d_live_probe` ledger required.
3. Allow isolated live-probe entries by setting
   `BOT_D_REQUIRE_WAVE_FOR_ENTRY=false`; wave labels remain recorded.
4. Disable the decision-time live probe depth floor by setting
   `BOT_D_MIN_ENTRY_DEPTH_USD=0`, allowing small resting orders instead of
   requiring immediate displayed depth.
5. Add and approve the Polymarket V2 neg-risk adapter path in the canonical
   approval script.
6. Normalize V2 maker fills from nested `maker_orders` and mark matching live
   order rows `FILLED`/`PARTIAL` during fill reconciliation.

**Consequences:**

- Bot D live can now collect real fill/no-fill data at the intended tiny size.
- Isolated trades are no longer blocked in the live probe, so the probe is an
  execution/data-collection lane, not a proof of wave-only profitability.
- Removing the depth floor can post resting orders into thin markets; loss is
  still bounded by fixed shares, per-order cap, daily gross cap, and max open
  exposure.
- Maker-fill parsing is now required for correct dashboard exposure, exits,
  and cap accounting under V2.

**First result:** Bot D live placed and filled a 5-share BUY_NO position on
NYC May 6 low 62-63F at 77c, order
`0xF00D0000000000000000000000000000000000076f96548a266b37a75714ba19`.
After a one-time repair reconciliation, the local ledger shows the order as
`FILLED`, a trade row, and an `OPEN` position under `bot_d_live_probe`.

**Rollback trigger:** If Bot D live shows untracked fills, cap drift, bad
ledger separation, unexpected non-weather entries, or exit/reconciliation
mismatch, stop `polymarket-bot-d-live.service`, restore wave-only/depth-gated
settings, and keep paper Bot D running while the live ledger is reconciled.

## ADR-096: Reframe Bot E0 as the shared crypto recorder for Bot G replay

**Date:** 2026-05-05
**Status:** accepted

**Context:** Bot G Prime Live has enough fills to start comparing live
transfer against the paper shadow, but parameter work needs a broader
market tape: symbols, market window length, lead-time buckets, book state,
and replay slices. The existing `bots/bot_e_recorder` service already captures
Polymarket crypto Up/Down market data plus Binance CEX trades, and remains
data-only with zero order placement. ADR-092 retired Bot E trading, so the
recorder should be treated as shared infrastructure rather than an active
Bot E strategy surface.

**Decision:**

1. Keep the deployed module path, database path, and systemd unit name for
   compatibility, but label the service as the shared "Crypto Recorder".
2. Preserve all existing `BOT_E_*` environment names while adding
   `CRYPTO_RECORDER_*` aliases for new or future deployments.
3. Add Bot-G-useful market metadata to recorder snapshots:
   `symbol` and inferred `duration_minutes`.
4. Migrate existing recorder DBs in place with `ALTER TABLE ... ADD COLUMN`
   and create indexes for symbol/end-time and duration scans.
5. Keep recorder changes strictly data-only; do not change Bot G live bands,
   sizing, symbols, caps, wallet posture, or fresh-clock guard.
6. Dashboard recorder panels should present the recorder as crypto telemetry
   and remain compatible with DBs that have not yet run the metadata
   migration.

**Consequences:**

- Future Bot G parameter research can compare BTC/ETH/SOL/XRP/DOGE and 5-min
  vs 15-min market windows from one tape.
- The old `Bot E0` name remains in paths and some historical docs, but active
  operator surfaces should describe it as the Crypto Recorder.
- Existing recorder services can restart without env-file churn; the new
  aliases are optional.
- This does not make Bot E an active trading candidate again.

**Rollback trigger:** If the recorder migration harms capture health or
dashboard availability, revert the metadata/dashboard labeling changes while
leaving captured rows intact. Do not change Bot G live execution rules as a
recorder rollback.

## ADR-097: Loosen Bot D tiny-live entry collection without increasing trade size

**Date:** 2026-05-05
**Status:** accepted

**Context:** Bot D tiny-live proved the end-to-end live path works, but after
roughly a day the sample was still too small for useful fill/no-fill evidence:
one filled order, one partial order, one resting live order, and one cancelled
order in the last 36 hours. A 24-hour diagnostic showed `207` tradeable scan
outcomes but only `4` placed attempts. The biggest blocked bucket was
`nws_fallback_entry_blocked` (`150` attempts), but live NWS fallback remains
intentionally hard-blocked because it is a single-source forecast path. The
next safest levers are lower edge threshold and removal of the live pre-entry
depth check.

**Decision:**

1. Keep Bot D live probe fixed at `5` shares per entry.
2. Keep `BOT_D_LIVE_MAX_ORDER_USD=5.25`,
   `BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=50`,
   `BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD=50`, and
   `BOT_D_LIVE_MAX_CONCURRENT_POSITIONS=10`.
3. Keep verified settlement, known end date, NWS veto, and live NWS fallback
   block enabled.
4. Lower the live probe strategy edge floor from the default `0.10` to
   `BOT_D_EDGE_THRESHOLD=0.08`.
5. Disable the live probe entry depth pre-check with
   `BOT_D_DEPTH_GATE_ENABLED=false`, allowing small maker orders to rest even
   when displayed depth at the candidate limit is thin.

**Consequences:**

- Bot D live should place more tiny orders and collect more execution data
  without increasing per-order, daily, open-exposure, or concurrency risk.
- Some extra orders may rest without filling; that is useful live execution
  evidence for the probe.
- The change does not authorize NWS fallback trading or larger position size.
- If order count rises but fills still lag, the next review should separate
  candidate scarcity from maker fillability before loosening any forecast
  quality guard.

**Rollback trigger:** If Bot D live shows untracked fills, cap drift, excess
resting orders, dashboard/ledger mismatch, or adverse behaviour from lower
edge entries, restore `BOT_D_EDGE_THRESHOLD=0.10` and
`BOT_D_DEPTH_GATE_ENABLED=true`, restart only
`polymarket-bot-d-live.service`, and reconcile the live probe ledger before
resuming.

## ADR-098: Add Bot G read-only parameter reports and paper shadows

**Date:** 2026-05-05
**Status:** accepted

**Context:** Bot G Prime Live has a live sample, but the sample is still too
small and currently has no winners. Paper and recorder evidence suggest
possible timing and price-band effects, especially a late-cheap `1c-3c` lane,
but the existing paper shadow does not mirror the live rule and the replay
result is not enough to justify changing live parameters. the operator approved
proceeding with the next safe phases while keeping live unchanged.

**Decision:**

1. Keep `polymarket-bot-g-prime-live.service` unchanged: `3.5c-5.5c`,
   `60s` window, `2s` scan, `5s` fresh-clock floor, BTC/ETH/SOL, `$5`
   entries, `20` entries/day, `$100` daily gross, `10` max open, and CEX
   confirm disabled.
2. Add `polymarket-bot-g-prime-shadow.service` as a paper-only live mirror:
   `bot_g_prime_shadow`, `3.5c-5.5c`, `60s`, BTC/ETH/SOL, and no live transfer
   price improvement.
3. Add `polymarket-bot-g-prime-late-cheap.service` as a paper-only research
   lane: `bot_g_prime_late_cheap`, `1c-3c`, `30s`, `5s` fresh-clock floor,
   BTC/ETH/SOL.
4. Add `scripts/bot_g_lead_bucket_roi_report.py` plus a daily systemd timer
   to report ROI, outlier-adjusted ROI, fill rate, Wilson intervals, and
   lead/price/symbol/side splits across Bot G live and paper lanes.
5. Add `scripts/bot_g_recorder_join_diagnostic.py` as a read-only diagnostic
   joining Bot G orders to nearby Crypto Recorder book snapshots.
6. Fix Bot G runbook and Bot G CLAUDE.md drift so the current live band is
   recorded as `3.5c-5.5c` with CEX confirm disabled.
7. Surface the same read-only report state in the dashboard and Telegram via
   `/botg`, without adding any remote live-control command.

**Consequences:**

- Parameter learning improves without changing real-money behaviour.
- The two new paper services may increase local paper order volume and DB
  writes; they can be stopped independently if recorder/dashboard health
  degrades.
- The late-cheap lane remains paper-only until OQ-068 produces enough forward
  evidence and the operator approves a separate live ADR.
- The daily report gives the operator one place to compare live, live-mirror
  paper, continuity paper, and late-cheap paper.
- Telegram `/botg` gives a compact read-only version of the same report for
  mobile checks.

**Rollback trigger:** If the paper-shadow services create excessive DB load,
dashboard latency, recorder lag, or Bot G live reconciliation noise, stop and
disable the new paper units and timer. If the Telegram/dashboard summaries
mislead or slow the operator surfaces, hide those read-only panels/commands.
Do not change Bot G live as a rollback for paper-shadow instrumentation.

## ADR-099: Add Bot D settlement-source telemetry before trading on late certainty

**Date:** 2026-05-05
**Status:** accepted

**Context:** Public weather-market research and Bot D's own station-fix work
agree that the edge is not generic "forecast the city"; it is knowing the
specific resolving station/source better than the market. the operator asked to roll
out all phases for measuring source lag, station-specific bias, and late-day
finalization. This must be telemetry-first because Bot D is already running a
tiny live probe and no new source-derived live entry rule has been proven.

**Decision:**

1. Add read-only `bot_d.source_snapshot` events during every Bot D scan.
2. Each snapshot stores market identity, station/source metadata, market YES
   price, same-local-day station extrema, latest station observation
   timestamp, station-sample count, bucket state, raw station age, and
   physical lock age where applicable.
3. Bucket states are analysis labels only:
   `no_station_data`, `pending`, `already_yes`, `already_no`, `locked_yes`,
   and `locked_no`.
4. Add `scripts/bot_d_source_edge_report.py` to summarize late-certainty
   counts, station/source coverage, lock age, raw station age, and forecast
   residuals from existing `bot_d.forecast_entry` events joined to source
   snapshots.
5. Surface a compact Source Edge panel in the Bot D dashboard API/UI.
6. Keep all source telemetry non-blocking. Source-label failures must never
   block scans, entries, exits, reconciliation, watchdog, or dashboard.

**Consequences:**

- Bot D now records the data needed to measure whether late-stage station
  certainty is actually tradeable.
- The current rollout does not trade from late-certainty labels. Entry
  thresholds, live fixed shares, caps, NWS veto, and NWS fallback block remain
  unchanged.
- True final-source lag is not yet complete: `source_visible_timestamp` and
  `source_lag_seconds` are intentionally null until a market-visible
  Wunderground/final-source poller is added and verified.
- Station-specific bias can now be measured from forecast entries plus station
  snapshots, but it needs resolved/late-day samples before it should change
  live behaviour.

**Rollback trigger:** If source snapshots create scan latency, provider
rate-limit problems, dashboard errors, or event-table pressure, disable with
`BOT_D_SOURCE_SNAPSHOT_ENABLED=false`, restart Bot D services, and keep the
report/dashboard code dormant until the collector is tuned.

## ADR-100: Pay up slightly for Bot D tiny-live fills

**Date:** 2026-05-05
**Status:** accepted

**Context:** Bot D's tiny-live probe is now placing and filling real orders,
and the first live positions are performing positively on the Polymarket
Active view. the operator wants faster live evidence collection and explicitly accepts
spending a small amount of edge per entry to prove whether the model transfers
to real fills. Recent diagnostics showed the largest remaining blocker is
`nws_fallback_entry_blocked`, but live NWS fallback remains intentionally
blocked because it is a single-source path. The safer next lever is execution
aggressiveness and a modest live-only edge-floor reduction, not bigger size or
weaker settlement/forecast safeguards.

**Decision:**

1. Keep Bot D live probe fixed at `5` shares per entry.
2. Keep `$5.25` max order, `$50` daily gross, `$50` max open exposure, and
   `10` max concurrent positions unchanged.
3. Keep verified settlement, known end-date, NWS veto, and live NWS fallback
   block unchanged.
4. Lower the live probe edge floor from `0.08` to
   `BOT_D_EDGE_THRESHOLD=0.07`.
5. Add live-only entry pay-up with `BOT_D_LIMIT_OFFSET=0.012`, allowing Bot D
   to cross up to about `1.2c` worse than the candidate midpoint when it has
   already passed the model and safety gates.

**Consequences:**

- Bot D should collect more live fills without increasing position size or
  wallet exposure.
- Average entry price may be worse by up to about `1.2c`, so ROI per filled
  position can fall even if the model is correct.
- This tests fill transfer and execution quality, not full profitability.
- If fills remain slow, the next bottleneck is likely forecast-source
  availability or candidate scarcity, not the order price.

**Rollback trigger:** If the lower edge floor or pay-up creates obvious bad
fills, ledger mismatch, cap drift, untracked fills, or a materially worse live
PnL path, restore `BOT_D_EDGE_THRESHOLD=0.08`, remove
`BOT_D_LIMIT_OFFSET=0.012`, restart only
`polymarket-bot-d-live.service`, and review the live probe ledger before any
further parameter change.

## ADR-102: Raise Bot D tiny-live collection caps while keeping per-order size fixed

**Date:** 2026-05-05
**Status:** accepted

**Context:** After ADR-100, Bot D live was not near the dollar daily cap but
was at the `10/10` concurrent exposure count. the operator asked to accelerate live
data collection by raising the live probe caps to `20` concurrent positions,
`$100` daily gross, and `$150` filled-plus-resting buy exposure. This is a
real-money cap increase, but the per-order risk remains constrained by fixed
`5` shares and `$5.25` max order.

**Decision:**

1. Raise `BOT_D_LIVE_MAX_CONCURRENT_POSITIONS` from `10` to `20`.
2. Raise `BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD` from `$50` to `$100`.
3. Raise `BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD` from `$50` to `$150`; this cap
   counts open position cost basis plus resting buy-order notional.
4. Keep fixed `5` shares and `BOT_D_LIVE_MAX_ORDER_USD=5.25` unchanged.
5. Keep verified settlement, known end-date, NWS veto, and live NWS fallback
   block unchanged.

**Consequences:**

- Bot D can collect more same-day live evidence before hitting the
  concurrency cap.
- Worst-case outstanding exposure can rise materially, but individual orders
  remain tiny and total exposure remains below the `$200` live wallet posture.
- The larger cap can make a bad-model day more visible in PnL faster; this is
  intentional live evidence collection, not strategy graduation.

**Rollback trigger:** If Bot D shows untracked fills, ledger mismatch, daily
gross drift, cap-enforcement errors, or noticeably worse live PnL after the
cap raise, restore `BOT_D_LIVE_MAX_CONCURRENT_POSITIONS=10`,
`BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=50`, and
`BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD=50`, then restart only
`polymarket-bot-d-live.service`.

## ADR-103: Add NOAA NBM station guidance as Bot D's first Open-Meteo bypass

**Date:** 2026-05-05
**Status:** accepted

**Context:** Bot D's live probe was repeatedly blocked by Open-Meteo `429`
cooldowns. The existing bypass was NWS gridpoint fallback, but live correctly
blocks `nws_fallback` entries because it is a single-source path and the NWS
second-opinion veto becomes degenerate. the operator asked to start the build-out of
free/paid alternatives, while skipping GribStream for now. NOAA's National
Blend of Models station text products provide station-level guidance from the
closest usable NBM grid point, including Bot D's resolving airports, without a
paid API key or GRIB decoder.

**Decision:**

1. Add NOAA NBM station text guidance as a middle forecast layer:
   Open-Meteo ensemble first, then NOAA NBM, then NWS fallback last.
2. Parse NBM `NBH` and `NBS` station bulletins from NOAA's public S3 bucket
   for the Bot D observation/settlement airport station.
3. Build `ForecastResult(source="noaa_nbm")` from NBM `TMP`/`TSD` rows,
   grouped by each station's local market date.
4. Keep NWS gridpoint forecast as the independent second opinion when NBM is
   used.
5. Keep live `nws_fallback` entries blocked. This change allows NBM-sourced
   forecasts to trade; it does not authorize generic single-source NWS
   fallback trading.
6. Cache NBM text products in-process for `3600s` to avoid downloading large
   station-bulletin files for every city on every scan.

**Consequences:**

- Bot D can keep evaluating US weather markets during Open-Meteo cooldowns
  without dropping into the blocked `nws_fallback` source.
- NBM is station-targeted and transparent, but it is still a point/blended
  guidance source rather than a true ensemble. Empirical ensemble-shape vetoes
  remain inactive for NBM because `ensemble_count=1`.
- The first scan after deploy may download large NBM text files; the cache
  should keep later scans cheap within the process lifetime.
- This is the free NOAA path. GribStream remains a future optional shortcut if
  direct NOAA text/GRIB access proves too slow or incomplete.

**Rollback trigger:** If NBM fetches create scan latency, NOAA throttling,
dashboard/API errors, bad station mappings, or suspicious live entries,
set `BOT_D_NOAA_NBM_ENABLED=false`, restart only Bot D services, and continue
with Open-Meteo plus blocked NWS fallback until the NBM parser is fixed.

## ADR-101: Prove Bot G take-profit exits in paper before any live exit router

**Date:** 2026-05-05
**Status:** accepted

**Context:** the operator observed that Bot G live tails sometimes spike well above
entry before final settlement, then still resolve against us. He proposed a
paper-first concept: keep buying the current `3.5c-5.5c` near-close lane, but
sell if the token value reaches about `60c`, `70c`, or `80c` with around
`10s` left. This could improve realised ROI if late spikes are frequent and
fillable, but a live exit router would introduce new latency, queue-position,
partial-fill, and accounting risks. The right first step is a paper-only probe.

**Decision:**

1. Add `bot_g_prime_take_profit` as a separate paper-only Bot G tuning lane.
2. Keep entry settings aligned with the live mirror:
   `3.5c-5.5c`, `60s`, BTC/ETH/SOL, fixed `$5`, `20/day`, and no live price
   improvement.
3. Enable a paper-only synthetic take-profit exit when an open paper position's
   recorder best bid reaches `0.70` during the final `25s` to `8s`.
4. Emit `bot_g.paper_take_profit_exit` events for every synthetic exit.
5. Do not change `bot_g_prime_live`, live size, live caps, live symbols,
   live entry timing, or live CLOB order/fill paths.

**Consequences:**

- The take-profit idea now collects forward evidence without risking real
  funds or contaminating the live ledger.
- Paper exits assume the observed best bid is fillable; this is optimistic
  until a live sell-path audit proves queue and latency transfer.
- A later live take-profit router requires a separate ADR and explicit
  real-money approval.

**Rollback trigger:** If the paper take-profit service creates recorder load,
dashboard/API errors, noisy synthetic exits, or confusing reporting, stop and
disable only `polymarket-bot-g-prime-take-profit.service`. Leave Bot G Prime
Live and the existing paper shadows unchanged.

## ADR-104: Park little-rocky 5-model dispersion migration until Bot D has resolved-position evidence

**Date:** 2026-05-05
**Status:** accepted

**Context:** A handoff doc from `~/Code/little-rocky/HANDOFF_TO_BOT_D.md`
proposed migrating three pieces into Bot D: a 5-model Open-Meteo
`historical-forecast` client (`gfs_seamless`, `icon_seamless`,
`icon_global`, `ukmo_seamless`, `meteofrance_seamless`), a cross-model
dispersion signal, and HDD/CDD primitives. Read-only investigation produced
the following findings:

1. Technical feasibility is confirmed. Open-Meteo `historical-forecast` serves
   ICON-seamless, UKMO-seamless, MeteoFrance-seamless, GFS-seamless, and
   ECMWF IFS for US ICAOs without an API key, free tier 600/min, 5 000/hr,
   10 000/day. The handoff's `_global` model identifiers are wrong; use
   `_seamless` for batched calls.
2. Cross-model dispersion is real and geographically heterogeneous. A 30-day
   probe (2026-04-05 to 2026-05-04) over Bot D's 11 US settlement stations
   produced mean cross-model std of `1.61` °F, p90 `2.67` °F, max `9.05` °F
   on SF max temperature. SF and LA max-temp dispersion (mean `3.71` /
   `3.53` °F) is ~3× the mainland baseline; Denver min-temp (mean
   `1.94` °F, max `4.08` °F) is the orographic outlier; Houston min-temp
   (mean `0.71` °F) is the quietest. `43.2%` of city-day-vars exceed
   `1.5` °F std.
3. Bot D already has multi-model coverage. GFS (31) + ECMWF (51) = 82 pooled
   ensemble members feeding `adjusted_std = sqrt(raw_std² + city_rmse²)`,
   plus NWS gridpoint veto, plus METAR intraday calibration, plus the
   recently-shipped NOAA NBM bypass (ADR-103). Cross-model std would
   partially double-count Bot D's existing uncertainty channels.
4. Bot D has no local resolved-position sample.
   `data/bot_d_candidate_quality_report.json` generated `2026-05-03` reports
   `0` fills, `0` candidates, `0` scans, status
   `insufficient_candidate_pressure`. The kill-date trigger
   (`2026-05-31`) requires `>=15` resolved positions; no evidence base
   exists yet to evaluate any sizing or signal change.
5. Bot D's CLAUDE.md research-track discipline states verbatim: "Do not add
   new data sources or model refinements until the verified daily lane has
   forward evidence... measurement precision < decision relevance: verified
   daily settlement entries are the measurable economic question. Adding
   sophistication before that measurement does not help."

**Decision:**

1. Do not migrate any code from `~/Code/little-rocky/` into Bot D at this
   time. No edits to `bots/bot_d_weather/`, no new data-source files, no
   audit-payload schema changes.
2. Do not add the 3 candidate models (ICON-seamless, UKMO-seamless,
   MeteoFrance-seamless) as primary, sidecar, or shadow forecast sources.
3. Do not migrate HDD/CDD primitives. Bot D markets are
   temperature-threshold bets, not heating/cooling-load bets; the primitives
   do not apply.
4. Preserve the dispersion baseline characterisation as a reference report
   under `docs/reports/bot-d-cross-model-dispersion-baseline-2026-05-05.md`
   so the analysis can be re-run cheaply if the question is reopened.
5. Open OQ-074 to gate any future revisit on resolved-position evidence.

**Rationale:** The technical work is feasible but the operating doctrine
says do not act. Cross-model dispersion likely overlaps with the existing
within-ensemble std + RMSE channel; the only way to know whether it adds
information is against a resolved-position sample, which Bot D does not yet
have. The cheapest correct move is to park the work with a clean re-entry
path rather than ship sophistication that cannot be evaluated.

**Alternatives considered:**

- **Wholesale migration** (rejected — violates Bot D research-track
  discipline; partial redundancy with existing 82-member ensemble; HDD
  primitives irrelevant to threshold markets).
- **Sidecar logger** that adds `cross_model_disagreement_f` to the
  `bot_d.forecast_entry` audit payload only, no sizing change (rejected for
  now — still introduces an unproven external dependency on a forecast
  source whose value cannot be tested until resolved-position sample
  arrives; revisit under OQ-074).
- **Retrospective the bot LXC container study** pulling logged `bot_d.forecast_entry`
  events and re-fetching 5-model historical forecasts at trade timestamps
  (rejected — local quality report implies fewer than `15` resolved
  positions on production; cost of operator export not justified by likely
  sample size).

**Consequences:**

- No production code, audit schema, or live behaviour changes from this
  ADR.
- Reproduction command and 30-day baseline preserved in
  `docs/reports/bot-d-cross-model-dispersion-baseline-2026-05-05.md`.
- The handoff doc at `~/Code/little-rocky/HANDOFF_TO_BOT_D.md` is treated
  as read-only context; little-rocky stays a research archive per its own
  pivot brief.
- HDD/CDD primitives are explicitly out-of-scope for Bot D under this ADR.
- If the dispersion question is reopened, OQ-074 is the unlock checklist.

**Rollback trigger:** None — this ADR records inaction. Reversal would be
a successor ADR proposing concrete migration steps once OQ-074's trigger
fires.

## ADR-105: Add GribStream NBM shortcut and 99c take-profit to Bot D tiny-live

**Date:** 2026-05-05
**Status:** accepted

**Context:** Bot D tiny-live is producing useful live positions but still
needs more real fill/exit evidence. Open-Meteo cooldowns previously forced
the bot into blocked `nws_fallback`; ADR-103 added free direct NOAA NBM as a
working bypass. the operator then provided a GribStream API token and approved using
GribStream as a paid shortcut. He also asked whether positions trading above
`99c` should be auto-sold; these positions have little remaining upside and
still consume capital, hold resolution/source risk, and clutter the live
probe.

**Decision:**

1. Add GribStream NBM as an optional, token-gated forecast layer before
   direct NOAA NBM:
   Open-Meteo ensemble, GribStream NBM, direct NOAA NBM station text, then
   NWS fallback.
2. Read the GribStream token only from `GRIBSTREAM_API_TOKEN` in runtime env.
   Do not commit the token or write it to systemd unit files.
3. Emit GribStream forecasts as `ForecastResult(source="gribstream_nbm")`.
   GribStream does not disable the NWS second-opinion guard and does not
   authorize live `nws_fallback` entries.
4. Enable GribStream only for `bot_d_live_probe` initially, to conserve the
   free-plan credit budget while we measure live behaviour.
5. Add Bot D take-profit exits controlled by
   `BOT_D_TAKE_PROFIT_ENABLED`, `BOT_D_TAKE_PROFIT_MIN_BID`,
   `BOT_D_TAKE_PROFIT_LIMIT_OFFSET`, and
   `BOT_D_TAKE_PROFIT_MIN_HOURS_TO_END`.
6. Trigger take-profit only from executable book best bid, not from Gamma
   `lastTradePrice` or UI current price.
7. Preserve the existing pending-exit dedupe so a position cannot spawn
   multiple live SELL exits.

**Consequences:**

- Bot D live can keep using a station-targeted NBM provider when Open-Meteo
  is unavailable without waiting for large direct NOAA text downloads.
- GribStream is paid/credit-metered; OQ-075 tracks daily credit use and
  whether it is worth keeping ahead of direct NOAA.
- A `99c` best-bid take-profit gives up the final `~1c/share` of theoretical
  upside, but banks near-certain live winners, frees the small probe wallet,
  and reduces settlement/source dispute exposure.
- Take-profit is an exit-path change, not an entry loosening. It should not
  increase gross risk, but it must be reviewed for fill quality and missed
  later redemptions.

**Rollback trigger:** If GribStream burns credits too quickly, fails during
scans, or produces suspicious station/date mappings, set
`BOT_D_GRIBSTREAM_ENABLED=false` and restart only Bot D live. If take-profit
creates stale SELLs, unexpected realised losses, or ledger mismatches, set
`BOT_D_TAKE_PROFIT_ENABLED=false`, cancel any unintended resting SELLs, and
restart only Bot D live.

## ADR-106: Trust exchange neg-risk metadata for live CLOB signing

**Date:** 2026-05-05
**Status:** accepted

**Context:** Bot D's first `99c` take-profit attempts on the NYC May 5
temperature position failed at CLOB V2 with `invalid signature`. Dry signing
showed the local client was producing type-0 EOA orders, but the local DB
marked the temperature token as `is_neg_risk=0` while the exchange's
`get_neg_risk(token_id)` returned `true`. After deploying exchange-first
neg-risk lookup, Bot D placed a live GTC SELL at `0.993`; reconciliation
recorded a SELL fill at `0.994` for `5` shares and closed position `632`. A
later manual FOK retry returned `not enough balance / allowance` because the
position had already sold, not because the funder path was broken.

**Decision:**

1. For live CLOB V2 orders, prefer the exchange's `get_neg_risk(token_id)`
   result over the local `markets.is_neg_risk` cache.
2. Keep the local DB flag as the paper/fallback source only.
3. Keep optional `POLYMARKET_SIGNATURE_TYPE` and
   `POLYMARKET_FUNDER_ADDRESS` runtime settings for future proxy-wallet
   support, but do not require them for the current hot wallet.
4. Keep Bot D take-profit enabled under ADR-105.

**Consequences:**

- Future live orders sign with exchange-correct neg-risk metadata instead of
  trusting stale ingest fields.
- The first automated Bot D take-profit exit is verified: order
  `0x7a3714...b1eaf`, SELL fill `0.994`, `5` shares, position `632` closed.
- No extra funder/proxy-wallet migration is required for the current live
  probe.
- The optional signature/funder settings remain available if a future
  Polymarket account type requires them.

**Rollback trigger:** If exchange neg-risk lookup fails broadly or slows live
entry materially, revert to DB-first lookup and block take-profit/exit orders
on any token where DB and exchange disagree.

## ADR-107: Add Bot D NWS-outlier probe using API agreement

**Date:** 2026-05-05
**Status:** accepted

**Context:** After enabling GribStream NBM and direct NOAA NBM, Bot D live
remained active but stopped placing new entries. Production scan summaries
showed the binding blocker was not cap usage: `bot_d_live_probe` was below
its `$150` exposure cap and `20` concurrent-position cap. The main blocker was
`nws_disagrees` on GribStream-led candidates. Shadow counters showed multiple
candidates per scan would clear if NWS were disabled, but none would clear the
simple `4°F` NWS floor. Concrete examples showed GribStream/direct NBM near
each other while NWS was `~5-6°F` away. the operator approved a small live-data probe
to compare the APIs rather than continue collecting no fills.

**Decision:**

1. Attach a non-NWS API panel to every forecast result when available:
   primary source plus GribStream NBM and/or direct NOAA NBM comparison
   forecasts for the same city/date.
2. Keep NWS as the default second-opinion veto.
3. Permit a tiny-live entry through the NWS veto only when all of these hold:
   `BOT_D_NWS_OUTLIER_PROBE_ENABLED=true`, absolute net edge is at least
   `0.08`, at least two non-NWS API sources agree within `2.0°F`, NWS is no
   more than `6.0°F` away from the primary model, and the source is not
   `nws_fallback`.
4. Persist the API panel, agreement count, agreement gap, NWS gap, and
   `nws_outlier_probe` flag in Bot D audit payloads.
5. Enable the probe only for the `bot_d_live_probe` systemd unit. Do not
   increase per-order size, daily gross cap, open exposure, or wallet
   allocation.

**Consequences:**

- Bot D can collect live fills in the exact regime currently blocking trades:
  NWS is the outlier but two station-targeted/model APIs agree.
- This is not an NWS-off mode. Single-source forecasts, `nws_fallback`, weak
  edge, loose API agreement, and large NWS gaps remain blocked.
- Source/outlier labels are now measurable in entry snapshots, so OQ-077 can
  decide whether the probe should stay, tighten, or be reverted.

**Rollback trigger:** If the probe creates poor fills, repeated stale exits,
or worse realised/unrealised PnL than ordinary Bot D entries, set
`BOT_D_NWS_OUTLIER_PROBE_ENABLED=false` in the live unit, reload systemd, and
restart only `polymarket-bot-d-live.service`.

## ADR-108: Implement crypto fair-value paper lanes, not live trading

**Date:** 2026-05-06
**Status:** accepted

**Context:** The 72-hour Crypto Recorder validation showed two positive
strategy families under CEX-proxy labels and slippage stress:
`probability_gap` and `brownian_fair_value`. At `1c/share` slippage,
probability-gap produced `5,045` signals, `73.6%` hit rate, `+34.4%` average
ROI, and `+33.5%` ex-largest-two ROI. Brownian fair-value produced `5,815`
signals, `71.1%` hit rate, `+25.3%` average ROI, and `+24.7%`
ex-largest-two ROI. The caveat is binding: those outcomes are CEX-proxy
labels, not final Chainlink/Polymarket settlement labels, and the historical
fill model is not calibrated against real exchange behavior.

**Decision:**

1. Add two paper-only lanes:
   `crypto_probability_gap_paper` and `crypto_brownian_fv_paper`.
2. Keep the implementation in a new `bots/crypto_fair_value/` package rather
   than extending Bot G Prime Live or Bot D.
3. Read only the shared Crypto Recorder for market, CEX, and book state.
4. Hard-fail non-paper runtime posture: dry-run must be true, live env plus
   non-dry-run is forbidden, and live wallet/keystore env settings are
   rejected.
5. Use three taker-fill tracks for every signal:
   `paper_taker_top`, `paper_taker_stressed_1c`, and
   `paper_taker_stressed_2c`.
6. Write the main Order/Trade/Position ledger only from the `1c` stressed
   track; store the `0c` and `2c` tracks in signal events for the report.
7. Add a report script that groups by bot, strategy, symbol, duration, lead
   bucket, side, model-probability bucket, ask bucket, and fill track.
8. Add systemd unit templates. Session 150 subsequently deployed the paper
   lanes to the bot LXC container, enabled both crypto paper services, and restarted only
   `polymarket-dashboard`.

**Consequences:**

- The two strongest 72-hour crypto strategy candidates now collect forward
  paper evidence without touching Bot G Prime Live, Bot D, wallets, caps,
  symbols, or live CLOB order paths.
- Normal dashboard/portfolio PnL for these paper lanes is deliberately
  conservative by defaulting to the `1c` stressed track.
- The report can still compare `0c`, `1c`, and `2c` fill assumptions from the
  same signal event.
- Live movement remains blocked until OQ-078 supplies forward paper evidence,
  settlement/Chainlink labels, latency stress, and fill calibration, followed
  by a separate ADR and explicit the operator approval.
- Deployment of the paper services does not authorize any live-wallet or real
  CLOB order behavior; both units pin `POLYMARKET_ENV=paper` and dry-run.

**Rollback trigger:** If the paper lanes create excessive DB volume, poor data
freshness, stale unresolved positions, or any accidental live-path dependency,
disable the corresponding systemd unit, keep the code dormant, and review
OQ-078 before restarting.

## ADR-109: Store Becker prediction-market data on fast-vm for offline validation

**Date:** 2026-05-06
**Status:** accepted

**Context:** Jon Becker's public `prediction-market-analysis` repo publishes a
large Polymarket/Kalshi Parquet dataset. It can help validate crypto
fair-value paper lanes by adding actual Polymarket market metadata,
settlement-derived outcomes, chain `OrderFilled` events, fees, token IDs, and
block timestamps. the bot LXC container rootfs is backed by `local-lvm`, which was already
near pressure (`87.7%` used before the change). The the homelab hypervisor `fast-vm` ZFS pool
had about `404G` free and already hosts non-backed-up high-volume data
mountpoints for the bot LXC container.

**Decision:**

1. Store the external public dataset on a dedicated the bot LXC container `fast-vm`
   mountpoint, not on `local-lvm` and not inside the live recorder mount.
2. Mount it at `/home/bot/polymarket-bot/data/external` with `200G` size and
   `backup=0`.
3. Keep Becker's repo and extracted Parquet under
   `/home/bot/polymarket-bot/data/external/prediction-market-analysis/repo`.
4. Use the dataset for offline validation/reporting only. Do not make active
   paper or live bot loops depend on it.
5. Use an isolated external repo `.venv` for DuckDB/PyArrow analysis rather
   than modifying the production bot `.venv`.

**Consequences:**

- the bot LXC container now has local read-only-style access to `408,863` Polymarket market
  rows, `404,540,000` CTF trade rows, `2,207,336` legacy trade rows, and
  `78,468,431` block timestamp rows from the public dataset.
- The dataset can support OQ-079 validation reports for crypto fair-value
  settlement labels, chain-fill calibration, recorder gap checks, and
  historical price-bucket baselines.
- The data is not in the homelab hypervisor backups because it is public, large, and
  replaceable.
- Active bot operation remains independent of the external dataset.

**Rollback trigger:** If the external dataset creates storage pressure,
delete `/home/bot/polymarket-bot/data/external/prediction-market-analysis`
and remove `mp2` from the bot LXC container after confirming no report job is running.

## ADR-110: Run heavy offline crypto validation on the local workstation, keep the homelab hypervisor live-first

**Date:** 2026-05-06
**Status:** accepted

**Context:** The Becker dataset and Binance kline backfill make crypto
fair-value validation a large DuckDB/Pandas workload. the bot LXC container is also the
production runtime host for live/paper bots, recorder, dashboard, watchdogs,
VPN posture, and hot-wallet-adjacent operational surfaces. the operator asked whether
the the local workstation should run the analysis instead of consuming the homelab hypervisor capacity.

**Decision:**

1. Use the the local workstation as the primary host for heavy offline crypto
   fair-value analysis.
2. Copy public/offline data from the homelab hypervisor `fast-vm` to the the local workstation before
   running large DuckDB/Pandas jobs.
3. Keep the homelab hypervisor/the bot LXC container as the live/runtime host for bot services, recorder,
   dashboard, watchdogs, and VPN/geofence posture.
4. Keep the the homelab hypervisor `fast-vm` dataset as a source copy until the the local workstation
   copy is verified, but do not use the bot LXC container for long heavy model replay jobs
   unless explicitly chosen for a small smoke test.
5. Do not move wallets, CLOB auth, live order-placement services, caps, or
   strategy thresholds as part of this analysis split.

**Consequences:**

- Live services remain isolated from large research queries and DuckDB spill
  pressure.
- The the local workstation can use local CPU/RAM/storage for the next OQ-079 model
  replay and 5m data-shape investigation.
- the homelab hypervisor remains responsible for always-on bot runtime until a separate
  relocation ADR supersedes ADR-006/ADR-014.
- The data transfer must exclude transient `.venv` and `duckdb-tmp`
  directories and should be verified by size and a smoke query before
  analysis results are trusted.

**Rollback trigger:** If the the local workstation copy is incomplete, unavailable, or
too slow, keep the data on `fast-vm` and run only bounded, scheduled offline
jobs on the bot LXC container after confirming live service headroom.

---

## ADR-111: Use a Tailscale-first VPS split-hosting pilot before moving live order placement

**Date:** 2026-05-06
**Status:** accepted

**Context:** the bot LXC container is CPU saturated and the a small EU VPS
improves direct request latency to CLOB, Gamma, CEX inputs, Polygon RPC,
Telegram, and weather APIs. The first hardening attempt also proved that the
VPS is still in setup mode: SSH/firewall posture must remain recoverable while
services are moved gradually. The dashboard is currently single-host/single-DB
and local-systemd oriented, so it cannot yet show VPS service health or VPS
paper/canary state.

**Decision:** Use `vps-host` as a split-hosting pilot behind
Tailscale before moving any additional runtime service. Phase 0 is mandatory:
keep SSH stable, install and verify Tailscale, build a read-only VPS
status/dashboard bridge, verify private reachability from the laptop/Mac
Studio and the homelab hypervisor/the bot container side, and prove access survives a reboot before
rebuilding a minimal firewall. After Phase 0, move paper-only crypto
fair-value bots first, then the shared crypto recorder, then Bot G paper/shadow
lanes. Keep `bot_g_prime_live`, wallet/CLOB auth, keystore/passphrase transfer,
production recorder writes, and any real-money order-placement path blocked
until a future ADR explicitly accepts live relocation.

**Rationale:** Tailscale gives the solo operator a private control plane for
status, dashboard, watchdog, metrics, and future approved secret transfer
without exposing internal services on public IPv4. Paper-first movement
reduces the homelab hypervisor load while preserving rollback and avoiding premature
wallet/CLOB risk. Requiring dashboard/status visibility before more migration
prevents a split-brain setup where services run on the VPS but the operating
surfaces still report only the bot container state.

**Alternatives considered:** Move Bot G live first for latency (rejected: it
touches wallet/CLOB order placement before observability and rollback are
proven); expose dashboard/status on public IPv4 (rejected: unnecessary attack
surface); keep everything on the homelab hypervisor and only cap the bot container CPU (rejected as
insufficient capacity relief); fully harden firewall before private
reachability/reboot tests (rejected after lockout recovery showed setup
posture needs to stay recoverable).

**Consequences:** The VPS can host paper/canary workloads and read-only status
now, but live funds remain on the homelab hypervisor until a later ADR. Dashboard work must
consume VPS status/DB summaries before additional migration. the bot container/the homelab hypervisor
quick wins remain allowed but should be applied deliberately after checking
current service state.

---

## ADR-112: Move Bot G paper lanes to VPS on a dedicated paper ledger

**Date:** 2026-05-06
**Status:** accepted

**Context:** After the VPS recorder and crypto fair-value paper services were
running behind the Tailscale status bridge, the bot container remained CPU-constrained.
The heaviest remaining safe candidates were Bot G paper/shadow loops:
`polymarket-bot-g-prime.service`,
`polymarket-bot-g-prime-shadow.service`,
`polymarket-bot-g-prime-late-cheap.service`, and
`polymarket-bot-g-prime-take-profit.service`. These services are explicitly
paper-only and dry-run, while `polymarket-bot-g-prime-live.service` touches the
live order-placement surface and remains blocked from VPS relocation.

**Decision:**

1. Move the four Bot G paper services to `vps-host`.
2. Keep the service names unchanged on the VPS so the bot container dashboard service
   overlay can report them as `vps:active`.
3. Run the services as `operator` from `/home/operator/longshot-research`.
4. Pin every moved unit to `POLYMARKET_ENV=paper`, `BOT_G_ENV=paper`, and
   `BOT_G_DRY_RUN=true`.
5. Read market/book data from the VPS paper recorder:
   `/home/operator/longshot-research/data/bot_e_recorder_vps_canary.db`.
6. Use a dedicated Bot G VPS ledger,
   `/home/operator/longshot-research/data/bot_g_vps_main.db`, cloned as a slim
   Bot G-only subset of the bot container `main.db`, rather than reusing the VPS
   crypto fair-value `main.db` or copying the bot container's full 9 GB database.
7. Extend the VPS status bridge and the bot container dashboard to report Bot G paper
   metrics from the VPS ledger.
8. Keep `polymarket-bot-g-prime-live.service`, wallet/CLOB auth material,
   keystore/passphrase handling, the VPN provider posture, watchdog, notifier, Bot D,
   and the production recorder canonical write path on the bot container.

**Rationale:** The dedicated Bot G VPS ledger avoids mixing Bot G paper state
with the already-running crypto fair-value VPS paper ledger, avoids a large
database transfer, and gives a clear rollback path. Preserving the same
systemd unit names lets the dashboard represent the moved services without
changing the operator-facing Bot G model. Paper-only pins and dry-run pins
make the move capacity-focused rather than a live trading relocation.

**Consequences:**

- the bot container no longer runs the four Bot G paper services.
- the bot container dashboard `/api/bot-g` reports the moved Bot G paper services as
  `vps`/`vps:active`.
- the homelab hypervisor CPU pressure is materially reduced while the live Bot G process
  remains local.
- Bot G paper history now lives in the VPS Bot G ledger for the moved lanes;
  the bot container keeps the pre-cutover source DB and live Bot G state.
- Any future move of `bot_g_prime_live` still requires a separate ADR and
  explicit the operator approval.

**Rollback trigger:** If any moved Bot G paper service fails health checks,
shows stale runtime state, writes unexpected live-mode state, or causes
dashboard mismatch, stop and disable the four VPS units, copy any desired
paper rows back only after review, and re-enable the four the bot container paper units
from their existing unit files. Do not alter `bot_g_prime_live` as part of
that rollback.

---

## ADR-113: Do not move Bot G live order placement to VPS for geographic bypass

**Date:** 2026-05-06
**Status:** superseded by ADR-115 (2026-05-06, same day)

**Context:** the operator requested moving `polymarket-bot-g-prime-live.service` from
the bot container to `vps-host` for latency. The live service is an actual
order-placement path with `POLYMARKET_ENV=live`, `BOT_G_ENV=live`, and
`BOT_G_DRY_RUN=false`. Moving it would require transferring `.env`, keystore,
passphrase runtime state, wallet/CLOB auth, and starting a real-money service
from Helsinki egress. The operator is UK-based. Official Polymarket
Geographic Restrictions documentation says builders should check geographic
eligibility before placing orders and lists `GB United Kingdom` as `Blocked`.
Polymarket Help Center guidance also says VPNs, proxies, or anonymization
tools must not be used to circumvent restrictions.

**Decision:** Do not move `polymarket-bot-g-prime-live.service`, any wallet/
CLOB auth material, keystore/passphrase, or real-money order-placement path to
the VPS when the purpose is to make a UK-based operator appear to trade from
Helsinki or another non-UK egress location.

**Consequences:**

- Bot G live remains on the bot container under the current live-control posture.
- VPS remains approved for paper/data workloads, read-only reports, status
  bridge, recorder shadow/feed, and paper-only Bot G lanes.
- Latency improvement alone is not sufficient to justify live relocation when
  it conflicts with platform geographic restrictions.
- A future live relocation can be reconsidered only if the operator is
  physically in an eligible jurisdiction and the move is not a geographic
  bypass; that future change would still require a separate ADR, secret
  handling plan, rollback path, and explicit approval.

**Rollback trigger:** Not applicable; no live migration was performed.

---

## ADR-114: Keep Bot D paper shadow aligned with tiny-live data settings

**Date:** 2026-05-06
**Status:** accepted

**Context:** Bot D live probe started producing useful fills after the
Open-Meteo -> GribStream NBM -> direct NOAA NBM -> blocked NWS fallback stack,
99c take-profit, API-agreement outlier probe, and small live collection
loosens. Paper Bot D stayed active but had not placed a fresh paper order for
several days; production inspection showed paper was running older service
settings and recent paper entry attempts were dominated by `nws_fallback`,
while live used the newer source stack.

**Decision:** Align `polymarket-bot-d.service` with the live probe's
non-wallet data and strategy settings: verified settlement, known end date,
`BOT_D_EDGE_THRESHOLD=0.07`, `BOT_D_LIMIT_OFFSET=0.012`, GribStream NBM with
`21600s` cache, direct NOAA NBM, the NWS-outlier API-agreement probe, disabled
depth gate, `3.0F` NWS veto floor, blocked NWS fallback entries, paper exit
slippage, and 99c take-profit. Do not copy live-only identity,
authorization, wallet, fixed-share, or live cap variables into paper.

**Dashboard change:** Add live-probe cap telemetry to `/api/bot-d` and the
Bot D dashboard card: daily gross, buy/sell split, remaining daily limit,
filled-plus-resting exposure, remaining exposure, and open position slots.

**Rationale:** The paper lane is only useful as a shadow if it sees the same
forecast sources and comparable entry posture as live. Keeping wallet/cap
flags separate preserves the `bot_d`/`bot_d_live_probe` safety boundary.

**Risk controls:** GribStream credit burn must be reviewed across both
services because cache state is per-process. NWS fallback entries remain
blocked. Live size remains fixed at `5` shares; no cap or bankroll increase is
authorized by this ADR.

**Reversal:** Remove the added paper unit environment variables or set
`BOT_D_GRIBSTREAM_ENABLED=false` for paper if GribStream credit burn rises
without improving paper/live comparability.

## ADR-115: Move Bot G live order placement to VPS, with revised geographic policy

**Date:** 2026-05-06
**Status:** accepted (supersedes ADR-113)

**Context:** ADR-113 (same day, earlier) declined moving
`polymarket-bot-g-prime-live.service` to `vps-host` on geographic
restriction grounds. Operator reviewed that decision in Session 180 and
authorised the move, noting that the prior conclusion was based on an overly
conservative reading of Polymarket's geographic guidance and that the
operator-level posture toward this is unchanged today regardless of which
host runs the order-placement service. Material facts that informed the
re-decision:

- The same wallet (`0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`) signed
  orders before and after the move; nothing about the operator's identity,
  jurisdiction, or KYC posture has changed.
- the bot container was already routing CLOB traffic through the VPN provider SE WireGuard
  (`vpn_host` check + `iptables` egress block on tunnel drop); the VPS path
  goes through a small EU VPS. The new posture
  is *less* of a "circumvention tool" pattern than the prior one, not more.
- The CPU pressure problem on the the homelab hypervisor
  (an internal offload plan (not exported)) is real and ongoing;
  Phase 1 (paper bots) and Phase 2 (recorder/data) had already moved without
  policy concern in Session 170.
- The operator is solo and accepts the platform-rules judgment as their
  own, not delegated to ADR-113's framing.

**Decision:** Move `polymarket-bot-g-prime-live.service` to
`vps-host`. Keep the same wallet, the same hot-wallet cap
(`BOT_G_LIVE_WALLET_USD=200`), the same per-trade size (`$5`), the same
strategy parameters, and the same daily caps. Replace the bot container's
`/run/user/<uid>/polymarket/passphrase` tmpfs path with a
`/run/polymarket/passphrase` system path on the VPS, populated by an
explicit `polymarket-passphrase.service` oneshot. Add `Requires=` on the
oneshot to the live unit so the bot cannot start without the passphrase
in tmpfs. Disable and archive (do not delete) the the bot container unit file.

**Rationale:** Operator authority on platform-policy interpretation
overrides ADR-113's earlier conservative reading. The VPS posture is
*better* on the "no VPN circumvention" axis than the the bot container + the VPN provider
posture it replaces. The CPU offload benefit and the operational cleanliness
of the VPS (already running the four paper bot_g lanes since Session 170)
are real.

**Alternatives considered:**

- *Keep on the bot container* — rejected; CPU saturation on the the homelab hypervisor is the
  reason for the offload plan, and ADR-113's stated objection is no longer
  the operator's view.
- *Move and add the VPN provider on the VPS too* — rejected; adding a VPN to the
  VPS path would re-introduce the circumvention pattern ADR-113 was
  worried about. a small EU VPS.
- *Defer until paper-only experiment* — rejected; the four paper variants
  have been on VPS since Session 170 with no anomalies, the live path uses
  identical code (sha256 confirmed), and the cutover window was tight
  (10 seconds downtime).

**Consequences:**

- Real-money orders now sign from `198.51.100.1` (a small EU VPS
  the same wallet. Polymarket sees the same authenticated wallet from a
  new IP and ASN.
- the bot container keeps the keystore, passphrase oneshot, and archived unit file for
  30 days as a hot rollback path. T+30 review on 2026-06-05: shred the bot container
  secrets if VPS has been clean.
- the bot container watchdog (`core/watchdog.py`) was patched to exclude VPS-hosted
  bots (`VPS_HOSTED_BOTS` constant) from `_active_trading_bot_ids()`,
  `LIVE_CAP_BOTS`, and `MARKET_CATALOG_BOTS`. Without this, the
  the bot container watchdog's CLOB-reachability check could halt VPS bots in
  the bot container's `main.db` even though the bots use VPS egress and read their
  own `bot_g_vps_main.db`.
- `scripts/vps_node_status.py` was updated to track
  `polymarket-bot-g-prime-live.service` and `polymarket-passphrase.service`
  and to include `bot_g_prime_live` in the `BOT_G_VPS_BOT_IDS` summary.
  The the bot container dashboard now correctly attributes the bot to VPS via the
  existing `vps:active` overlay.
- Stale `halt_flags` rows on the bot container's `main.db` for the four moved bot_g
  bots (prime, live, shadow, late_cheap) were cleared in this session
  with `reason="Session 180 2026-05-06 cleared stale the bot container halt; bot_g
  moved to VPS (ADR-115)"`.

**Rollback trigger:** Any of (a) more than three crashes per 24 hours on
VPS, (b) sustained Polymarket auth failures from the VPS provider egress, (c)
unexpected on-chain wallet activity that does not match bot_g entry
behaviour, (d) the VPS provider instance or networking outage > 30 minutes.
Procedure documented in
`docs/bot-g-vps-live-migration-2026-05-06.md`.

**Reversal:** Re-enable the archived the bot container unit, stop and disable the
VPS unit, optionally shred VPS secrets. ~2 minutes. Both hosts retain
keystore + passphrase during the 30-day retention window.

## ADR-116: Decouple the bot container watchdog startup from legacy the VPN provider egress probe

**Date:** 2026-05-06
**Status:** accepted

**Context:** The Bot G VPS migration audit found the bot container
`polymarket-watchdog.service` inactive because the unit hard-required
`polymarket-wg-vpn.service`. The the VPN provider probe failed at
2026-05-06 18:34:23 UTC after direct the bot container egress reported
`198.51.100.3`. Bot G live now runs on the Helsinki VPS with direct
the VPS provider egress and no the VPN provider requirement. the bot container still hosts Bot D paper,
Bot D tiny-live, dashboard, notifier, and watchdog, so the watchdog must
stay running even if the legacy external egress probe fails.

**Decision:** Remove the hard `Requires=`/`After=` dependency on
`polymarket-wg-vpn.service` from `polymarket-watchdog.service`; start
watchdog after `network-online.target` instead. Keep the in-process CLOB
reachability check in `core.watchdog` as the live-path safety check, scoped
only to the bot container-hosted active trading bots. Also exclude `VPS_HOSTED_BOTS`
from `bots.watchdog_daemon` cancel-wrapper construction so the bot container does not
create live CLOB clients for VPS-hosted Bot G lanes.

**Rationale:** A failed legacy egress unit should not suppress the safety
daemon. Watchdog should run, record the failing health check, and halt only
the the bot container bots whose order paths use the bot container egress. VPS-hosted bots use their
own DB and egress path and must not be halted or cancelled by the bot container.

**Consequences:**

- the bot container watchdog now starts independently of the legacy the VPN provider egress unit.
- the bot container watchdog still requires the passphrase service because
  `bot_d_live_probe` can need live CLOB cancel/preflight coverage.
- VPS Bot G remains direct the VPS provider egress with no the VPN provider dependency.
- `polymarket-wg-vpn.service` can remain as a separate diagnostic or
  legacy route helper, but it is no longer a startup gate for watchdog.

**Rollback trigger:** If the bot container watchdog produces false-green CLOB reachability
while direct the bot container Polymarket egress is actually unusable, restore the prior
unit dependency or replace it with a more precise route-aware preflight before
starting watchdog.

## ADR-117: Keep Bot G Prime paper collection running with a zero ROI floor

**Date:** 2026-05-06
**Status:** accepted

**Context:** After moving Bot G to VPS, the main paper Prime service was
active but no longer collecting new samples because the default
`BOT_G_MIN_ROLLING_ROI_PCT=100` kill gate fired at `59.1%` rolling ROI.
That ROI is positive but below the historical "edge must be huge" live
candidate gate. the operator asked to get paper operational again as part of the VPS
recovery.

**Decision:** Set `BOT_G_MIN_ROLLING_ROI_PCT=0` for the VPS
`polymarket-bot-g-prime.service` paper unit. Leave the live Bot G service
caps, entry band, pre-submit freshness guard, and strategy parameters
unchanged.

**Rationale:** The main paper lane is a data-collection surface. A positive
rolling ROI should not stop paper sample collection just because it is below
the old `100%` aspirational live-candidate threshold. A zero floor preserves
a basic "do not keep collecting if this turns loss-making" guard while
unblocking paper operation.

**Consequences:**

- Main Bot G Prime paper resumes scanning instead of sitting in
  `bot_g.kill_switch_active`.
- This does not authorize any live size increase, live parameter change, or
  broader strategy acceptance.
- Live Bot G remains governed by its tiny-live caps and by the separate VPS
  preflight gate.

**Rollback trigger:** If paper Prime collection adds noise without a clear
research use, restore the default `BOT_G_MIN_ROLLING_ROI_PCT=100` or retire
the lane.

## ADR-118: Reduce Bot G Prime live per-entry size while preserving the live probe

**Date:** 2026-05-07
**Status:** accepted

**Context:** The cumulative project notes and recent Becker validations show
that the Bot G taker edge is probably flawed or at least weaker than the
initial paper result implied. the operator wants to keep the live probe running for
now in case the strategy enters a better win cluster, but reduce real-money
exposure while that uncertainty remains.

**Decision:** Reduce `bot_g_prime_live` fixed entry size from `$5` to `$3`
on the active VPS live unit. Keep all other live parameters unchanged:
observed `3.5c-5.5c` entry band, one-tick live transfer bidding capped at
`5.5c`, `20` live entries/day, `$100` daily gross notional cap, `10` max
open positions, `$200` live wallet reference, BTC/ETH/SOL universe, and
direct a small EU VPS.

**Rationale:** Lowering per-entry risk preserves the chance to observe a
positive cluster while reducing downside from a thesis that has accumulated
negative validation evidence. Keeping every non-size parameter unchanged
avoids turning this into a new strategy variant.

**Consequences:**

- Future live Bot G entries target about `$3` notional instead of `$5`.
- Daily gross notional cap remains `$100`, so the cap is now less likely to
  bind before the `20` entries/day cap.
- Historical live fills before this ADR remain at the sizes originally
  submitted and are not restated.

**Rollback trigger:** Restore `$5` only after the operator explicitly accepts the
risk again or after post-change live evidence justifies increasing the tiny
probe size.

## ADR-119: Close NegRisk basket arb track at $200 solo-operator scale

**Date:** 2026-05-07
**Status:** accepted

**Context:** Session 196 surfaced arXiv 2508.03474 (IMDEA, AFT 2025)
documenting `$29M` of `$39.6M` total Polymarket arb extracted Apr
2024-Apr 2025 from NegRisk basket rebalancing alone (`73%` of total) at
`29×` capital efficiency vs binary arb. Top arber `$496/trade × 4,049
trades`, per-trade size compatible with `$200` wallet. Built v1 naive
scanner (`scripts/polymarket_negrisk_scanner.py`): for every negRisk
event with `≥3` active markets, sum bestAsk_YES across active markets,
flag if `sum + n × 200 bps < $1.00`. Naive scanner flagged `7`
opportunities including `Nobel Peace Prize Winner 2026` (`+0.139` per
share), `"How to Make a Killing" Rotten Tomatoes` (`+0.916`), `UEFA
Champions League Most Red Cards` (`+0.373`).

**Verification (2026-05-07 same-session):** Built
`scripts/polymarket_negrisk_exhaustiveness.py` to fetch full event
detail for each of the 7 flags. Findings:

- `6/7` events have an explicit field/other market (e.g. `Will any
  other person or organization win the Nobel Peace Prize`, `Will
  another candidate win`) with gamma signature `bestAsk=$1.00,
  bestBid=$0, spread=$1, volume=0, liquidity=0` — i.e. zero order book
  on the residual-probability leg. The naive scanner excluded this
  because the field market is `active=False`. Including it pushes sum
  to `$1.04-$1.46` (no arb).
- `1/7` (`How to Make a Killing`) has cumulative-threshold structure
  (`≥56`, `≥58`, `≥59`, `≥60`) — markets are not mutually exclusive
  (a score of `65` makes all four resolve YES). negRisk flag is
  misleading.

Updated scanner in-place to v2 with three exhaustiveness gates: (a)
cumulative-threshold filter, (b) field-market detection across all
markets in event (active + closed + archived) covering `any other /
someone else / not listed above / another candidate`, (c) field-market
liquidity check. v2 across `1,425` qualifying events: `0` real arbs,
`252` events with illiquid-field illusory naive-arb, `6` cumulative-
threshold non-baskets, `1` near-arb at `-4%` (MLS `Min vs Col` `3-way
W/L/D` correctly priced).

**Decision:** Close the NegRisk basket arb research track at $200 solo
scale. No bot, service, paper unit, live unit, dashboard surface, cap,
wallet, or order path was modified during this research. Bot G stays
exactly as it is. The scanner code remains in `scripts/` for future
reference but is not wired into any service.

**Rationale:**

1. Zero real arbs at gamma snapshot cadence after applying correct
   exhaustiveness gates. The naive `~0.5%` flag rate was an artifact of
   incomplete exhaustiveness, not an edge.
2. The dominant pattern (252 events) requires either WebSocket-tier
   infra or providing liquidity to field markets. The first is out of
   scope; the second is market making, not arb, and requires capital
   plus a risk model we don't have.
3. The IMDEA `$29M` figure reflects ephemeral windows closing in `<1s`
   (faster than gamma's `~1s` aggregation cadence) and windows where
   field markets briefly become liquid. Both gated by infra and capital
   beyond $200 scale.
4. The 1 surviving near-arb (MLS `3-way W/L/D`) is correctly priced
   with no edge after `200 bps × 3` fees.
5. Per `CLAUDE.md` operator directive, the bot strategy roster is full
   (`B/C/D/E/F` paper, `G` operational, `A` archived). Adding a NegRisk
   track at $200 with negative expected edge violates the operator
   guidance of data collection over speculation.

**Consequences:**

- No new bot, service, paper unit, dashboard surface, cap, wallet, or
  order path created.
- `OQ-084` resolved (closed).
- Closure synthesis at `docs/reports/polymarket-negrisk-closure-2026-
  05-07.md`. v1 / audit / v2 artefacts retained for reproducibility.
- `scripts/polymarket_negrisk_scanner.py` retained as v2-correct
  reference. Not invoked by any service.

**Reopen trigger:** This ADR may be revisited if any of the following
changes:

- WebSocket CLOB book streaming wired into a sub-100ms scanner.
- Atomic basket execution via the `neg-risk-ctf-adapter` contract
  becomes available in a wrapper we can call.
- Operator approves a market-making lane with capital sized for field-
  market liquidity provision (out of current scope).
- An MLS-style `≥3-way` exhaustive-without-field event surfaces with
  fees structurally below `200 bps × N` (e.g. via builder code
  rebates).

## ADR-120: Split Bot D into archived longshot-fade (paper) and live range-fade (live_probe); push kill date

**Date:** 2026-05-07
**Status:** accepted

**Context:** Bot D was deployed Apr 2026 with the longshot-fade thesis
(temperature tails over-priced; fade them by buying NO at high prices
or selling YES at low prices). Per CLAUDE.md kill date `2026-05-31`,
archive if `net realised edge < 2.5%/position after 1.25% RT fees on
≥15 resolved positions`. Read-only audit of the bot LXC container `main.db` on
`2026-05-07` revealed the `bot_d` paper lane has `84` resolved positions
with **headline +27% edge net of modelled fees**, but **the entire
edge is concentrated in a single 35× outlier** — Lagos `28°C` YES
bought at `$0.028` on `2026-04-20`, sold at `$1.00` on `2026-04-21`,
`+$1,735` PnL on `$50` cost. Excluding that one trade: edge is
`-20.9%`. Excluding top-5 wins: `-35.4%`.

Separately, the `bot_d_live_probe` lane has `12` resolved positions
with `91.7%` hit rate and `+28.4%` net edge after fees (`+$0.99`/
position median). Audit revealed live_probe is running a **different
strategy** — range-fade on temperature-range markets (`Will the
highest temp in NYC be between X-Y°F`) buying NO at `$0.65-0.91`. The
`91.7%` hit rate is structurally explained by narrow ranges rarely
hitting actual temperatures.

**Decision:** Split Bot D into two named lanes for clarity, with
different status:

1. `bot_d` (paper, longshot-fade) — **archive thesis**. The 84-position
   sample cannot validate edge above noise when one trade contributes
   >100% of P&L. Move paper positions to
   `positions_archive_botd_longshot_<timestamp>` table. Maintain
   `BOT_D_ENTRY_HALT=true` for the paper lane (already set).
2. `bot_d_live_probe` (live, range-fade) — **keep running** at current
   `$3` entry size per ADR-118. Push kill date from `2026-05-31` to
   `2026-06-30` to allow sample to grow to `30` closed positions.

**Rationale:** Bot A's failure was high-hit-rate small-wins eaten by
rare large losses. Bot D paper is the inverse — low-hit-rate small-
losses with rare massive wins. Both profiles are unable to validate
edge at the position counts attainable in 1-2 month windows because
variance dominates the mean. The live_probe range-fade has a
structurally-explained hit rate and tight per-position distribution
(min `-$0.91`, max `+$1.75`), which is validatable with order-of-30
samples.

**Consequences:**

- Paper longshot-fade thesis closed for purposes of edge validation.
- Live_probe range-fade continues. Sample target `30` closed positions
  by `2026-06-30`.
- All non-size, non-strategy parameters unchanged.
- No new bot, service, paper unit, dashboard surface, cap, wallet, or
  order path created.
- Open paper positions (`11` open at this snapshot) and live_probe
  open positions (`11` open) continue to resolution.
- The `1` paper position at `$25` cost (id=`808`, NO at `$0.682` on
  cond `2161898`) is left to resolve naturally, not force-closed.

**Rollback trigger:** If live_probe hit rate drops below `70%` on the
next `18` closes (taking sample to `30`), archive entire Bot D track.
If hit rate stays `≥80%` with positive per-position net at `n=30`,
propose ADR-121 to graduate to standard `$5` entry with broader market
universe (raise the daily cap, allow longer lookups, add Atlanta /
Phoenix / Boston cities currently at half-weight).

**OQ-058 / OQ-067 / OQ-071 / OQ-073 / OQ-075 / OQ-077** all flagged
in dormant-ideas sweep for re-read post-30-closes; hold until
sample threshold met.

**Reports:**
- `docs/reports/bot-d-post-mortem-2026-05-07.md` — full audit
- `docs/reports/dormant-ideas-sweep-2026-05-07.md` — frontier ranking

## ADR-121: Builder-code rebate harvest BLOCKED at current bot configuration

**Date:** 2026-05-07
**Status:** accepted

**Context:** `dormant-ideas-sweep-2026-05-07.md` ranked builder-code rebate
harvest as punchlist #3 ("ADR-048 already plumbed, no consumer, harvest-
only, ~1 session"). Grok edge-hunt session corroborated with X-handle
intel (`@appledog_xyz`, `@0xsolvix` posting $16-30/day rebate
screenshots). Audit performed `2026-05-07` (this session, read-only).

**Findings:**

1. ADR-048 builder-code wiring is correct: `POLYMARKET_BUILDER_CODE`
   set in production env (`0x08ef...9d4c`), `core/clob_v2.py` attaches
   it to every V2 order at line 462, `core/fees.py` rebate accounting
   path defaults `include_in_ev=False` per the V2 docs ("discretionary
   pool distribution, not guaranteed per-fill").
2. **Our bots place marketable limit orders that fill as taker.**
   Sampled `10` recent `bot_d_live_probe` fills: every one records a
   POSITIVE `fee_usd` (taker fee), zero negative-fee/rebate trades.
   Math check on weather feeRate=`0.05` × `p` × `(1-p)` × `5` shares
   matches recorded fees exactly — confirms taker classification.
3. On-chain Blockscout query on `HOT_WALLET_ADDRESS` for the audit
   window `2026-04-28` → `2026-05-07` shows zero token transfers,
   `is_contract: true`, `has_token_transfers: false`. Wallet is a
   Polymarket-managed proxy stub; the actual trading proxy was not
   identified (didn't chase the derivation since the trade-flow
   analysis already confirmed no rebates are landing).
4. Even if rebates landed, our volume is `~100-500×` smaller than
   `@appledog_xyz` / `@0xsolvix`. Max theoretical rebate at our
   volume: `~$0.07/day`. Not material.

**The mis-categorization:** the dormant-ideas sweep ranked this
"harvest-only" because the code is plumbed. But the code is plumbed
for a *flow shape we don't generate*. To earn rebates we'd need a
maker-flow bot, which is on the `CLAUDE.md` out-of-scope list
("Market-making / rebate farming bot"). This is a strategy change,
not a config flip.

**Decision:**

1. **Keep builder code attached** to all V2 orders (no-op when taker
   but free to have).
2. **Keep `include_in_ev=False`** in `core/fees.py`. Default is
   correct.
3. **Mark builder-code rebate harvest as BLOCKED** in
   `docs/open-questions.md` (OQ-041 Q4 / equivalent). Status is
   "blocked-by-scope", not "waiting-for-data".
4. **Update dormant-ideas-sweep punchlist** — re-classify item #3
   from "harvest-only" to "blocked, requires strategy change".
5. No new service, bot, code path, or env change.

**Rationale:** Dormant-ideas sweep was over-optimistic. Audit
confirms the harvest path requires either (a) operator approves a
maker-flow bot (currently out-of-scope in CLAUDE.md), or (b) Polymarket
changes its rebate distribution model from "maker only" to "any
builder-code-attributed flow". Neither is plausible without explicit
operator direction.

**Reopen trigger:**

- Operator explicitly requests a maker-flow / rebate-farming bot
  (would require lifting the `CLAUDE.md` out-of-scope entry first).
- One of the existing bots is refactored to post-and-wait flow as part
  of an unrelated change.
- Polymarket announces builder-code attribution being rebatable
  independent of taker/maker classification.

**Reports:**
- `docs/reports/builder-code-rebate-audit-2026-05-07.md` — full audit
- `docs/reports/dormant-ideas-sweep-2026-05-07.md` — re-ranked source

## ADR-122: Keep recorder infrastructure running indefinitely

**Date:** 2026-05-07
**Status:** accepted

**Context:** Bot G's taker edge now looks structurally weak, but the recorder
and replay infrastructure has repeatedly produced useful evidence: paper/live
divergence, CEX-state replays, maker-side validation, current-regime checks,
and future strategy search inputs. the operator explicitly chose to keep all recorders
going indefinitely because an edge may surface later from broader tape.

**Decision:**

1. Keep active data-only recorders and shared telemetry lanes running
   indefinitely where they are stable and inexpensive enough to operate.
2. Treat recorder output as research infrastructure, not as authorization for
   any live strategy change.
3. Preserve bounded replay, outcome labels, CEX/Polymarket event tape, and
   health/heartbeat telemetry as first-class project assets.
4. Manage retention through storage/backup/health monitoring rather than
   stopping recorders because the current trading thesis failed.
5. Any recorder that starts threatening host health, storage, secrets hygiene,
   or live-bot stability can be throttled, rotated, or archived by a follow-up
   ADR.

**Rationale:** The project has repeatedly avoided expensive mistakes because
historic tape existed. The data has option value even when a specific bot is
retired. Keeping recorders live separates "stop trading a bad strategy" from
"stop learning from the market."

**Consequences:**

- Bot G can remain a small live data probe at the current `$3` posture while
  recorders continue to gather broader tape.
- Recorder uptime and storage monitoring become part of the active operating
  model.
- No retired trading bot is revived by this ADR.
- No paper/live service, cap, wallet, or order path changes are authorized.

**Rollback trigger:** Storage pressure, recorder corruption, host instability,
or data quality falling below research value. In that case, propose a
retention/rotation ADR rather than silently disabling collection.

**Reports:**
- `docs/reports/bot-g-multi-model-deep-analysis-2026-05-07.md`

## ADR-123: Accept Strategy E (TTR-Windowed Cheap-YES Hold-to-Resolution) as paper-only with empirical-edge basis from WANGZJ 5-year backtest

**Date:** 2026-05-07
**Status:** accepted (paper-only)

**Context:** Operator asked whether Polymarket weather cheap-YES has a
buy-low-hold-to-resolution edge ("crazy weather spikes" thesis). Operator
clarified `$5k` wallet ceiling (raised from `$200`). SII-WANGZJ HuggingFace
dataset (`568M` trades, 5+ years, `18,151` closed weather markets with
clean YES/NO resolution) confirmed locally cached on the bot LXC container. Used to
run calibration test:

- Universe-level cheap-YES (entry `≤15c`, all TTR, all cities):
  `263,498` trades, **`-7.2%` EV per `$1`** — confirms bear case at
  universe level. Bot A walk-forward weather slice (`-3.96%` mean edge)
  replicates.
- **Conditional slice with empirical edge:** TTR `6-12h` × price
  `3-10c` × positive-EV city filter yields `+30.6%` net ROI on
  `14,697` trades, edge `+3.19pp`, Wilson 95% CI excludes null.
- Sweet-spot cell: TTR 6-12h × 5-10c band: `13,471` trades, realized
  `9.20%` vs implied `7.22%`, Wilson lower bound EV/$ = `+20.8%`.
- Outlier dependence is severe: only `3.6%` of markets profitable;
  top-1 market = `+$2,798` (Shanghai 19°C Mar 27, exactly the
  "crazy spike" pattern). Top-5 removal in unfiltered slice
  flips to `-1.7%`. City filter improves robustness: positive-EV
  cities top-5 removed = `+9.64%`.
- Cities WHITELIST: Hong Kong, Shenzhen, Wellington, Tokyo, New York,
  Ankara, Madrid, Shanghai, Seoul, London, Lucknow, Tel Aviv.
- Cities BLACKLIST: Beijing (`0/626` wins, structurally suspicious),
  Munich, Paris, Toronto, Singapore, Atlanta, Dallas, Miami, Seattle.

The strategy-adversary subagent's prior DEAD verdict was based on
(a) bear case at universe level, (b) lack of forecast tape,
(c) sample-starvation with `n=30`. Findings (a) confirmed at universe
level only; conditional slice has `n=14,697` and doesn't need forecast
tape (TTR-windowing alone produces edge). Adversary verdict is
overturned for the conditional slice specifically.

**Decision:** Accept Strategy E (revised TTR-windowed spec) as
**paper-only** for forward validation. Build conditions:

1. **No live trading.** This ADR authorizes paper-only deployment.
   Live operation requires a separate ADR after `≥200` paper closes
   confirm forward edge.
2. **Separate `bot_id`** = `bot_d_spike` so this strategy's P&L stays
   accountably separate from existing Bot D NO-side range-fade.
3. **Separate systemd unit** `polymarket-bot-d-spike.service` (when
   built). Existing Bot D services unchanged.
4. **Entry rules (empirically-derived from WANGZJ):**
   - YES side, price `3-10c`
   - Time-to-resolution `6-12h` ONLY
   - Cities: WHITELIST positive-EV only (12 cities listed above)
   - No forecast trigger required (TTR-windowing alone is the edge;
     forecast persistence is a future refinement)
5. **Sizing:** `$1-3` per position, hard cap 50 concurrent positions,
   hard cap `$200` total deployed in this strategy at any time
   (well under the `$5k` wallet ceiling).
6. **Hold to resolution.** Never intraday-exit (Strategy A failed
   for that reason).
7. **Kill criterion:**
   - Either `200` closed paper positions OR `90` days, whichever first
   - If realized ROI < `+5%` (significantly below historical `+30%`,
     accounts for forward-sample noise) → archive
   - Hit rate is reported as a diagnostic against the historical `3.6%`
     baseline, not used as an automatic archive gate

**Rationale:**

1. The empirical edge in the conditional slice is statistically
   significant (Wilson CI excludes null), is replicable on multiple
   sub-cuts, and is structurally consistent with the operator's
   "crazy spike" intuition.
2. Paper-only deployment costs operator `$0` financial risk; only
   risk is operator-time on a strategy that may not validate forward
   (2025-2026 monthly trend showed slight decay vs 2024).
3. Forward validation closes the gap between historical-replay and
   live-microstructure (replay assumes trade prints are executable
   bids; forward will reveal whether bid/ask depth matches WANGZJ's
   trade tape).

**Consequences:**

- New paper bot lane added to fleet; existing Bot D lanes unchanged.
- No order paths, caps, wallets, dashboards, or services modified
  outside the new lane.
- `core/fees.py` rebate semantics unchanged.
- Bot G stays as-is per operator standing instruction.

**Reopen / promote trigger:**

- 200 paper closed positions completed → calibration check vs
  WANGZJ baseline. If realized ROI > `+5%` and edge has not decayed
  below Wilson lower bound, propose ADR-N+1 for tiny-live deployment
  at `$3` per position (matching ADR-118 size discipline).
- If forward calibration confirms edge, consider building forecast
  persistence (`bot_d_forecasts` table) as Strategy E2 refinement.

**Reports:**
- `docs/reports/wangzj-cheap-yes-weather-calibration-2026-05-07.md`
- `docs/reports/cheap-yes-repricing-edge-test-2026-05-07.md` (prior
  Strategy A intraday-exit test, rejected separately)

## ADR-124: Back up VPS state DBs now; require controlled recorder rollover before freeing VPS recorder space

**Date:** 2026-05-07
**Status:** accepted

**Context:** The the VPS provider VPS disk reached about `30%` used shortly after the
VPS migration, driven primarily by
`/home/operator/longshot-research/data/bot_e_recorder_vps_canary.db`
(`~9.2GB`). the homelab hypervisor has ample archive space on `<bulk-storage>/`
(`~2.9T` free). The operator asked whether data should be pulled back to
the homelab hypervisor as backup and then removed from the VPS.

**Decision:**

1. Install a the homelab hypervisor-side pull backup for small VPS state DBs immediately.
   the homelab hypervisor pulls over Tailscale from `root@192.0.2.1` into
   `<bulk-storage>/`.
2. Back up `bot_g_vps_main.db` and `main.db` every 6 hours via
   `longshot-vps-pull-backup.timer`.
3. Treat a backup run as valid only after SQLite online snapshot,
   table-count comparison, `PRAGMA quick_check`, SHA256 recording, and
   zstd verification pass.
4. Do not prune or delete the hot VPS recorder DB yet.
5. Freeing recorder space requires a follow-up controlled recorder
   rollover/sharding or maintenance-window backup plan. Blind live copy is
   rejected.

**Rationale:** The live/state DBs are small and can be backed up safely
without touching services. The recorder DB is a large hot WAL-mode SQLite
database with continuous writes. The safe SQLite `.backup` path stalled under
active writes, and a raw DB/WAL/SHM hot copy failed verification with
`database disk image is malformed`. That is enough evidence that deleting or
pruning recorder data after a blind copy would be unsafe.

**Consequences:**

- `bot_g_vps_main.db` and `main.db` now have verified the homelab hypervisor-side backups.
- The current VPS disk-growth risk is reduced for critical state but not yet
  solved for the high-volume recorder tape.
- OQ-053 remains open for recorder rollover, sharding, integrity checks, and
  retention.
- No live trading service, wallet, CLOB auth, the VPN provider config, or recorder
  service is changed by this ADR.

**Rollback trigger:** If the timer causes load, SSH failures, or backup
corruption, disable `longshot-vps-pull-backup.timer` and keep the latest
verified manifest under `<bulk-storage>/`.

## ADR-125: Clarify Strategy E paper-build gates and deploy first lane on the VPS

**Date:** 2026-05-07
**Status:** accepted

**Context:** Pre-build review of
`docs/strategy-e-paper-bot-build-handoff-2026-05-07.md` found several
implementation traps:

- The handoff's Section 9 suggested a soft TTR overlap, while ADR-123
  requires TTR `6-12h` only.
- The handoff and ADR-123 listed archive if hit rate `<4%`, but the
  historical baseline in the same evidence packet is about `3.6%`.
  A true `3.6%` hit-rate strategy has a high chance of printing below
  `4%` over only `200` closes, so this would reject baseline behavior.
- Bot D's existing parser registry does not include all Strategy E
  whitelist cities, and Bot D's executor contains SELL/take-profit
  behavior that Strategy E forbids.
- OQ-080 already allows paper-only VPS lanes, while blocking live order
  placement, wallet auth movement, and Bot D live relocation.

**Decision:** Amend the Strategy E build spec as follows:

1. Keep the Strategy E entry window hard: TTR `6-12h` only. No `5-13h`
   grace band without a later ADR amendment.
2. Treat hit rate as a diagnostic against the historical `3.6%` baseline.
   The paper archive gate at `200` closes remains realized ROI `<+5%`,
   plus any rule violation, accidental non-paper behavior, or operator
   decision. Do not auto-archive solely because hit rate is below `4%`.
3. Implement `bot_d_spike` as a separate module and executor. Do not copy
   Bot D's edge-decay, stale-order, or take-profit exit loops.
4. Use a dedicated Strategy E city parser/normalizer so Shenzhen,
   Wellington, Ankara, Madrid, Tel Aviv, and `New York`/`NYC` are handled
   consistently.
5. Entry pricing must come from the CLOB book: YES best ask, best bid,
   spread, and ask-depth. Gamma `outcomePrices`/last-trade marks are not
   sufficient for entry.
6. Deploy the first forward-validation lane on `vps-host`
   as paper-only against the VPS-local `data/main.db`, with
   `POLYMARKET_ENV=paper` and `ClobWrapperV2(..., paper_override=True)`.
   the bot container Bot D and Bot D live-probe services remain unchanged.

**Consequences:**

- `bot_d_spike` is VPS-hosted and excluded from the bot container watchdog halt/cap
  control, like the existing VPS paper lanes.
- VPS status/reporting should include the new service so the lane is not
  a silent sidecar.
- Promotion to live still requires a new ADR and explicit operator
  approval after forward validation.

## ADR-126: Deploy passive wallet observer for 245 retail-tier wallets (Polygon CTF V2 + NegRisk V2)

**Date:** 2026-05-07
**Status:** accepted (paper-only / read-only)

**Context:** Operator question "if it works, can we copy the trades?"
required a forward-validation step before any copy-trade decision.
WANGZJ retail-tier mining (Session 212) identified `245` wallets
(`97` Tier A human + `148` Tier B unknown-but-profitable) as
candidates for forward observation. Without 30-day forward data we
cannot distinguish "still profitable today" from "retrospectively
lucky in 2024." Building a copy bot before that data exists would
repeat the Bot A failure mode (historical signal, no forward
validation).

**Decision:** Deploy a passive observer service on a small EU VPS
VPS that subscribes to Polygon CTF V2 + NegRisk V2 OrderFilled events
and records every fill where the maker or taker matches our 245-wallet
whitelist. This is **read-only and paper-zero-risk**: no transactions
are signed, no orders placed, no operator wallets touched. Pure
on-chain observation pipeline.

**Implementation summary:**

- Module: `bots/wallet_observer/` (5 files, ~600 lines)
  - `whitelist.py` — loads `data/retail_wallets_xref_2026-05-07.csv`,
    filters to `INCLUDED_TIERS={A_human_profitable, B_unknown_profitable}`
  - `schema.py` — separate SQLite DB at `data/wallet_observer.db`
    (per Bot E recorder pattern; isolates write-heavy event capture
    from main strategy DB)
  - `collector.py` — Polygon RPC poller; decodes V2 OrderFilled with
    explicit `side` field (uint8, 0=BUY/1=SELL from maker POV);
    handles POA middleware for block timestamps
  - `__main__.py` — main loop, signal handlers, run-tracking
  - `config.py` — env-driven config
- Service: `polymarket-wallet-observer.service` on VPS,
  `polymarket-wallet-observer-daily-report.timer` (06:30 UTC daily)
- Daily report: `scripts/wallet_observer_daily_report.py` — MD + JSON
  with per-tier breakdown, top-25 active wallets, side distribution,
  health check
- Tests: `tests/test_wallet_observer.py` — 18 tests pass on VPS
  Python 3.12; covers whitelist loading, schema init, V2 log
  decoding, side derivation, collector state persistence

**Critical V2 protocol detail discovered during build:**

Polymarket V2 (deployed Apr 28 2026) uses NEW exchange contracts:
- `CTF_EXCHANGE_V2 = 0xE111180000d2663C0091e4f400237545B87B996B`
- `NEG_RISK_CTF_EXCHANGE_V2 = 0xe2222d279d744050d28e00520010520000310F59`

V1 addresses are deprecated and emit no OrderFilled events. The V2
event signature changed: explicit `side` field (uint8), single
`tokenId` (not maker/taker pair), 6-decimal amounts for both legs.
`core/config.py` still has V1 addresses; `core/polymarket_v2.py`
has V2 addresses available. `bots/wallet_observer/config.py`
hardcodes V2 to avoid coupling.

**Decision constraints (per CLAUDE.md):**

1. **Not copy-trading.** This module is a feature/telemetry primitive.
   Copy-trading verified sharps remains on the kill-list.
2. **Not signing transactions.** Pure read via `eth_getLogs`.
3. **Not modifying any other bot.** Bot G, Bot D, Bot D-Spike
   continue unchanged.
4. **Storage cap.** SQLite WAL on a separate `wallet_observer.db`;
   audit estimate ~5-15 MB/day. VPS has ~58 GB free; 30-day capacity
   is fine.

**What this enables:**

After 30 days of forward-observation data:
1. **Validate** which Tier A/B wallets are still profitable forward
   (vs retrospectively lucky)
2. **Compute** capture rate by category (sports / politics / weather)
3. **Decide** whether to propose a paper-copy bot in a strict subset
   (Tier B niche specialists with proven forward edge)
4. **Toxic-flow filter** for existing bots: skip entries when Tier C
   bots dominate the book (already enabled via `core/wallet_labels.py`)

**Reopen / promote trigger:**

After ≥30 days of forward observation:
- If Tier A+B forward edge holds at >+10% ROI on ≥500 fills:
  propose ADR-N+1 for paper-copy bot in tight Tier B subset
- If forward edge is negative or flat: archive the lane; the data
  is still valuable as a feature column for other bots
- If observer detects a wallet that historically traded ≥100/day
  but has zero observed activity in 30 days: prune from whitelist

**Consequences:**

- New service running on VPS continuously; passive observation only
- New SQLite DB (~5-15 MB/day expected growth)
- Daily report at 06:30 UTC via systemd timer
- Bot G, Bot D, Bot D-Spike, all paper bots unchanged
- 245 wallets being observed; ~10-30% of them active in any given hour
  per smoke-test (10/245 active in first 7 minutes of capture)

**Reports:**
- `docs/wallet-observer-feature-2026-05-07.md` — full feature documentation
- `docs/reports/retail-wallet-pnl-mining-2026-05-07.md` — source data

## ADR-127: Tune Bot D-Spike to validation-plus paper settings after first-day capacity check

**Date:** 2026-05-08
**Status:** accepted (paper-only)

**Context:** Bot D-Spike's first overnight run placed `1` paper entry
at `2026-05-08 00:55 UTC` (Hong Kong `27C`, ask `0.068`, about
`11.08h` to resolution). The follow-up capacity check found that the
lane is working, but current market supply is sparse under the exact
ADR-123/ADR-125 operating slice. At `2026-05-08 06:32 UTC`, the
deployed scanner parsed `22` weather markets; canonical settings
produced `0` eligible candidates, with `15` rejected for
`ttr_outside_6_12` and `7` for city exclusion. Aggressive scout
profiles also produced `0` eligible entries at that exact minute
because the in-window whitelisted books were either high-probability,
empty-bid, or too far out.

**Decision:** Keep Bot D-Spike paper-only and keep the hard `6h-12h`
time-to-resolution thesis window, but tune the live paper service to a
validation-plus entry profile:

- Entry YES ask band: `1c-15c` instead of `3c-10c`
- TTR: unchanged hard `6h-12h`
- Whitelist/blacklist: unchanged
- Hold to resolution: unchanged
- Position size: unchanged `$2`
- Deployed cap: unchanged `$200`
- Concurrent cap: unchanged `50`
- Daily entry cap: `40` instead of `20`
- Minimum top ask depth: `25` shares instead of `50`
- Maximum spread: `3c` instead of `2c`

**Rationale:** Widening the price band and book-quality gates increases
paper observation density without abandoning the core empirical
hypothesis: positive-EV weather cities, cheap YES, same-day
resolution-window entry, and hold-to-resolution exit. Widening TTR to
`0h-36h` would force more paper fills when supply appears, but it would
no longer validate the same backtested Strategy E mechanism. The
operator explicitly asked to get the lane trading more; validation-plus
is the narrowest paper-only adjustment that respects the thesis.

**Alternatives considered:**

- Keep canonical `3c-10c`, `50` shares, `2c` spread: rejected because
  the first-day tape showed too little capacity for timely forward
  learning.
- Scout mode (`0h-36h`, `1c-15c`, looser depth/spread): rejected for
  now because it changes the question from edge validation to capacity
  discovery.
- Add blacklisted/unknown cities: rejected; city filter is the main
  empirical protection against the universe-level negative ROI slice.

**Consequences:**

- Forward tape is now labelled validation-plus, not the exact
  `3c-10c` ADR-123 slice.
- Promotion to live still requires a new ADR and explicit operator
  approval.
- Dashboard and active operating model must display `1c-15c`, hard
  `6h-12h`, and `40` daily cap so operator surfaces match the deployed
  service.

## ADR-128: Lower Bot G paper take-profit probe to 50c and keep late-cheap collecting

**Date:** 2026-05-08
**Status:** accepted (paper-only)

**Context:** Bot G's live tiny probe remains structurally weak. The
2026-05-08 VPS status check showed `bot_g_prime_live` at `25/25`
resolved with `0` wins, `-$63.43`, and `-100%` ROI in the latest
7-day daily-probe report. The paper take-profit lane was still using
the original `70c` synthetic exit from ADR-101 and had produced no
profitable take-profit exits (`0/43`, `-$176.22`). the operator observed a live
position that briefly marked around `50c` before resolving against the
entry and asked whether lowering the paper take-profit threshold would
be useful. The same status check found `bot_g_prime_late_cheap` active
but asleep on the rolling-ROI kill switch after `100` closed paper
trades and `-$342.87`.

**Decision:**

1. Keep `bot_g_prime_live` unchanged at the ADR-118 `$3` tiny-live
   posture: BTC/ETH/SOL, `3.5c-5.5c`, 60s window, one-tick transfer
   bid, `20` entries/day, `$100` daily gross, `10` max open, and no
   the VPN provider dependency on the VPS.
2. Lower only the paper take-profit lane's synthetic exit threshold:
   `BOT_G_PAPER_TAKE_PROFIT_PRICE=0.50` instead of `0.70`.
3. Keep the take-profit timing window unchanged at final `25s` to `8s`.
4. Keep the take-profit lane paper-only. No live sell router, live
   CLOB sell path, live size change, or wallet change is authorized.
5. Set `BOT_G_MIN_ROLLING_ROI_PCT=-100` only on
   `bot_g_prime_late_cheap` so the paper feature continues collecting
   bounded forward samples even after poor rolling ROI.

**Rationale:** A `70c` threshold is too sparse for the current evidence
question: whether mid-tail markups can be captured before the near-close
longshot collapses. A `50c` paper exit directly tests the event the operator saw
without touching real funds. Keeping late-cheap running is a data
collection choice, not a promotion signal; its current results are poor,
but the paper lane is cheap and useful for regime detection and negative
evidence.

**Alternatives considered:**

- Add a live take-profit sell router now: rejected because ADR-101
  requires paper proof first, and live sell execution introduces latency,
  queue-position, partial-fill, and accounting risk.
- Lower live entry size again or halt live Bot G: rejected for this ADR
  because the operator's standing instruction is to keep the `$3` live probe
  running for data while risk is capped.
- Keep late-cheap killed: rejected because the operator explicitly wants
  recorders and paper research surfaces to keep gathering data where they
  are stable.

**Consequences:**

- Future `bot_g_prime_take_profit` paper rows can exit at `50c` if the
  recorder best bid reaches the threshold in the final `25s` to `8s`.
- Synthetic paper exits remain optimistic because they assume best-bid
  fillability.
- `bot_g_prime_late_cheap` will no longer sleep merely because its
  realised ROI is below the old live-candidate floor.
- No real-money Bot G parameter changes are made by this ADR.

**Rollback trigger:** If the 50c paper take-profit lane creates noisy or
misleading reports, restore `BOT_G_PAPER_TAKE_PROFIT_PRICE=0.70` or stop
only `polymarket-bot-g-prime-take-profit.service`. If late-cheap creates
host load, dashboard noise, or no research value after the next review,
restore its rolling ROI floor or disable only the late-cheap paper unit.

## ADR-129: Block expensive Bot D NO entries without source agreement and large bucket distance

**Date:** 2026-05-08
**Status:** accepted

**Context:** Bot D tiny-live produced several high-priced `NO` losers on
1°F weather buckets. A 2026-05-08 audit of live positions with
`avg_price >= 0.50` and mark `<=0.01` found five expensive failures:
Atlanta 80-81°F May 6 `NO` at `67c`, Seattle <=61°F May 6 `NO` at
`83.4c`, NYC low 56-57°F May 6 `NO` at `79c`, Denver 38-39°F May 6
`NO` at `61c`, and Seattle 62-63°F May 7 `NO` at `91c`. Four came from
the Open-Meteo multi-model lane and one from the GribStream NBM lane,
so the issue is not simply loss of one forecast provider. The shared
failure pattern is buying expensive `NO` on narrow buckets while
forecast uncertainty was still roughly `3-4.5°F`.

**Decision:**

1. Add an `expensive_no_guard` to Bot D entry execution.
2. Default the guarded class to `BUY_NO` entries with limit price
   `>= 0.60`.
3. Require at least `2` agreeing non-NWS API sources with max gap
   `<= 2.0°F`.
4. Require the forecast mean to be at least `max(4.0°F, 2.0 ×
   forecast_std_f)` away from the bucket or threshold.
5. Return structured skip reasons:
   `expensive_no_guard:source_agreement` and
   `expensive_no_guard:distance`.
6. Keep the guard config-driven:
   `BOT_D_EXPENSIVE_NO_GUARD_ENABLED`,
   `BOT_D_EXPENSIVE_NO_GUARD_MIN_PRICE`,
   `BOT_D_EXPENSIVE_NO_MIN_API_AGREEMENT`,
   `BOT_D_EXPENSIVE_NO_MAX_API_GAP_F`,
   `BOT_D_EXPENSIVE_NO_MIN_DISTANCE_F`, and
   `BOT_D_EXPENSIVE_NO_MIN_DISTANCE_STD_MULT`.

**Rationale:** A `60c-90c` `NO` position appears safe but has poor
loss asymmetry: a single station-level miss into a 1°F bucket wipes the
stake. Requiring independent source agreement and a large distance from
the bucket prevents single-source GribStream/NBM trades and uncertain
Open-Meteo multi-model trades from consuming live risk in this fragile
price band.

**Consequences:**

- Bot D will trade fewer expensive `NO` positions.
- Cheap `YES` research and lower-priced `NO` entries are unaffected.
- High-priced `NO` entries can still occur when multiple sources agree
  and the forecast is far enough from the bucket.
- Skip histograms will show whether the guard is the new capacity
  bottleneck.

**Rollback trigger:** If the guard blocks nearly all Bot D live flow and
the skipped expensive-`NO` paper/shadow sample later shows positive
resolved ROI after fees, relax `BOT_D_EXPENSIVE_NO_GUARD_MIN_PRICE` or
disable `BOT_D_EXPENSIVE_NO_GUARD_ENABLED` with an explicit follow-up ADR.

## ADR-130: Automate safe zero-value standard wallet redemptions on the VPS

**Date:** 2026-05-08
**Status:** accepted

**Context:** The hot wallet repeatedly accumulates resolved standard CTF
positions that have `redeemable=true`, `negativeRisk=false`, and
`currentValue=$0`. These are losing ERC-1155 balances that keep cluttering
the Polymarket Active view until `ConditionalTokens.redeemPositions()` burns
them. Manual sweeps have now been done several times, including a 17-row VPS
sweep on 2026-05-08. the operator explicitly asked for this future cleanup to be
fully automatic.

**Decision:**

1. Enable a VPS systemd timer,
   `polymarket-redeem-zero-value-vps.timer`, to run daily.
2. The timer invokes `polymarket-redeem-zero-value-vps.service`, which runs
   `scripts/redeem_resolved_positions.py --execute --yes`.
3. Scope the automation to the script's default safe filter only:
   standard CTF positions, `redeemable=true`, `negativeRisk=false`,
   `currentValue=$0`, known USDC.e/pUSD collateral, non-zero ERC-1155
   balance, and successful preflight `redeemPositions()` simulation.
4. Add `--standard-zero-value-only` so unattended runs refuse
   `--condition-id` and `--include-nonzero-current-value`.
5. Add execution caps used by the timer:
   `--max-candidates 50`, `--max-total-gas 5000000`, and
   `--max-gas-per-tx 350000`.
6. Use the existing VPS signer handoff only:
   `POLYMARKET_PASSPHRASE_PATH=/run/polymarket/passphrase` and
   `Requires=polymarket-passphrase.service`.
7. Keep negative-risk, non-zero-current-value winners, condition-targeted
   redemptions, Ledger treasury actions, wrapping/unwrapping, and any sell
   order path outside this automation.

**Rationale:** Burning zero-value standard losing shares is wallet hygiene,
not a strategy decision. It returns no market value, but it clears stale
positions and reduces manual maintenance. The safety risk is accidental scope
creep, so the automation is deliberately narrower than the full redemption
helper and has candidate/gas caps.

**Consequences:**

- Standard zero-value resolved positions should disappear automatically after
  the daily VPS timer runs.
- Any valuable winner row still requires a separate explicit approval path or
  follow-up ADR.
- Negative-risk adapter burns remain manual until a separate adapter-safe
  automation is designed.
- If the wallet suddenly has more than `50` candidates or abnormal gas, the
  service fails closed and leaves positions untouched.

## ADR-131: Automate Bot D zero-value negative-risk redemption cleanup

**Date:** 2026-05-08
**Status:** accepted

**Context:** Bot D live weather range markets are negative-risk positions.
After resolution, losing shares can remain visible in the Polymarket Active
view with `redeemable=true`, `negativeRisk=true`, and `currentValue=$0`.
The standard zero-value redemption automation in ADR-130 deliberately skips
negative-risk rows, so Bot D losing weather positions still required manual
`NegRiskAdapter.redeemPositions(conditionId, amounts)` cleanup and manual
ledger closure.

**Decision:**

1. Extend `scripts/redeem_resolved_positions.py` with an explicit
   `--include-negative-risk-zero-value` mode.
2. Keep negative-risk cleanup opt-in and zero-value-only. The script will not
   redeem non-zero-current-value winners in this mode.
3. For unattended Bot D use, require `--bot-id bot_d_live_probe` plus
   `--only-local-open-positions`, so only token IDs matching open live Bot D
   ledger positions are eligible.
4. Use `NegRiskAdapter.redeemPositions(conditionId, amounts)` for
   negative-risk rows, with exactly one amount populated according to
   Polymarket's `outcomeIndex`.
5. After a successful negative-risk zero-value redemption, optionally write a
   zero-price `SELL` fill to the local ledger via `--account-local-fills` so
   realised P&L and open-position counts reflect the resolved loss.
6. Add the bot container systemd units
   `polymarket-bot-d-negrisk-zero-redeem.service` and
   `polymarket-bot-d-negrisk-zero-redeem.timer`. The timer runs every `30`
   minutes when enabled and fails closed above `25` candidates,
   `4,000,000` total gas, or `500,000` gas per transaction.

**Rationale:** This is wallet hygiene and ledger reconciliation, not a new
trading strategy. The risk is accidental redemption of valuable or unrelated
wallet rows, so the automation requires Polymarket's zero-current-value flag,
negative-risk redeemability, adapter simulation, an ERC-1155 wallet balance,
and a matching open `bot_d_live_probe` position.

**Consequences:**

- Bot D losing resolved weather rows should no longer clutter the Active
  view or stay open in the dashboard once the timer is enabled.
- The standard ADR-130 sweep remains unchanged and still ignores
  negative-risk markets.
- Winner redemption, non-zero-current-value rows, Ledger treasury actions,
  wrapping/unwrapping, and any market sell order path remain outside this
  automation.
- If negative-risk adapter approvals are missing or gas/candidate caps are
  exceeded, the service fails closed and leaves positions untouched.

**Rollback trigger:** Disable the timer with
`systemctl disable --now polymarket-redeem-zero-value-vps.timer` if the
script emits unexpected candidates, gas caps trip repeatedly, Polymarket Data
API semantics change, or any redemption touches a row outside the standard
zero-current-value scope.

---

## ADR-132: Crypto fair-value microstructure and post-cost audit gates the verdict, not a model swap

**Date:** 2026-05-08
**Status:** accepted

**Context:** A 2026-05-08 literature scan (four parallel research agents)
flagged three concerns about the live `crypto_probability_gap_paper` and
`crypto_brownian_fv_paper` lanes deployed in Session 150:

1. The 10-second σ sampling step in `bots/crypto_fair_value/discovery.py`
   may be biased upward by microstructure noise.
2. The published prediction-market literature (Akey et al. 2025; Bartlett &
   O'Hara 2026; Le 2026) suggests short-horizon liquidity-takers are
   structurally on the losing side; the 72-hour CEX-proxy gross edge may
   not survive realistic adverse-selection costs.
3. Cutting-edge alternative models — rough volatility, HAR-RV, Kou
   jump-diffusion, logit-space jump-diffusion — could in principle replace
   the GBM closed form and improve calibration.

A read-only audit
(`scripts/research/crypto_fv_microstructure_and_cost_audit.py`,
`docs/reports/crypto-fv-cost-and-microstructure-audit-2026-05-08.md`) tests
these against the live `bot_e_recorder.db` over a 72-hour window
(`2026-05-05T10:19Z → 2026-05-08T10:19Z`, 418 5 m markets, 6,062 simulated
$5 paper fills).

**Decision:**

1. Do **not** change the σ estimator in
   `bots/crypto_fair_value/discovery.py`. The audit shows the
   `σ_per_step ∝ √step` Brownian scaling holds within ~5% across
   BTC/ETH/SOL on 72 h of CEX trades. No microstructure-noise bias
   detectable at 10 s sampling.
2. Do **not** replace the GBM closed form. Bitcoin is empirically
   monofractal/Hurst≈0.49 at 5 min (Drozdz 2024) and rough volatility
   structurally fails on Bitcoin (Habibi et al. 2025, arXiv:2507.00575).
   Replacing the process buys ~0% calibration improvement.
3. Do **not** add HAR-RV (wrong horizon — designed for daily forecasts).
4. Treat the post-cost audit as **encouraging but not authorising**. CEX-
   proxy gross edge (`prob_gap +40.2%` ROI, `brownian_fv +32.9%` ROI)
   clears the all-in cost wedge (`10–13%` of gross) by ~4×. Ex-largest-two
   ROI (`+39.5%` and `+32.4%`) shows the edge is not jackpot-driven.
5. Live discussion remains gated on OQ-078 settlement-label evidence. The
   audit changes the prior on the bots from "structurally negative-EV" back
   to "edge plausible if Chainlink agrees with the proxy"; it does not
   replace the OQ-078 acceptance criteria.

**Consequences:**

- Session 150 bots stay running paper-only, unchanged.
- The audit script is committed under `scripts/research/` and is intended
  to be re-run weekly as a regression check on the simulated edge.
- A separate follow-up (audit.M2 from the 2026-05-06 Session 150 audit)
  remains open: the live bots see `missing_book` on most scans and have
  recorded only one fill each since deploy. That is a coverage problem,
  not a math problem, and is tracked in OQ-078 progress.
- Future refinements deferred:
  - Logit-space jump-diffusion inversion (Dalen 2026, arXiv 2510.15205) is
    revisited only after settlement-label evidence is in.
  - `confseq` betting-CS replacement of OQ-078's fixed-N gate
    (Waudby-Smith & Ramdas 2024) is recommended in the audit but not
    accepted in this ADR; tracked separately.

**Rollback trigger:** If a follow-up weekly run of the audit script reports
post-full ROI below `+10%` on a 7-day rolling window, open a new ADR before
deciding to keep the bots running. If a Chainlink-settlement label backfill
shows the CEX proxy is biased high by more than `15%`, treat the audit
result as inadmissible and re-evaluate.

---

## ADR-133: Strategy E2 short-TTR weather lane — lift near-resolution scalping kill-list line for weather only, paper-only

**Date:** 2026-05-08
**Status:** accepted

**Context:** The 2026-05-08 WANGZJ V2 re-validation (Test C in
`docs/reports/findings-revalidation-all-tests-2026-05-08.md`) found that the
`<6h × weather × cheap-YES (3-10c)` slice survives the same outlier-robustness
check that authorised Strategy E (Bot D-Spike) under ADR-123 and ADR-125:

| TTR | category | n | as-is ROI | top-5 robust | top-25 robust | verdict |
|---|---|---:|---:|---:|---:|---|
| 6-12h | weather | 35,931 | +40.1% | +16.2% | -30.4% | ROBUST (Strategy E baseline) |
| **<6h** | **weather** | **40,496** | **+36.1%** | **+11.1%** | **-29.7%** | **ROBUST** |
| 12-24h | weather | 54,731 | +5.8% | -14.4% | -46.0% | fragile |

Both robust slices share the same outlier-tail dependence (top-25 negative)
but the body of the distribution is positive. `<6h × weather` is the only
other cheap-YES slice in the 568M-trade WANGZJ corpus that meets the same
top-5-robust bar.

CLAUDE.md `Out-of-scope` contains: `Near-resolution scalping / HFT
strategies`. `<6h` TTR is by any definition near-resolution. Bot G operates
in 5/15-min crypto markets — grandfathered, not a precedent for weather.
This ADR is the surgical exception needed to act on the empirical evidence
without re-opening the broader near-resolution prohibition.

The full spec is at
`docs/strategy-e2-short-ttr-weather-spec-2026-05-08.md`.

**Decision:**

1. Lift CLAUDE.md "Near-resolution scalping / HFT strategies" entry **for
   weather temperature-bucket markets only**, paper-only, conditional on:
   1. The build follows Option B from the spec (separate `bot_d_spike_short`
      lane, not a widening of `bot_d_spike`'s TTR window).
   2. Kill conditions match the spec: archive at 200 closes OR 90 days,
      whichever first; archive if realized ROI < +5%; archive if hit rate
      < 4%; at the 200-close gate, top-5-robust ROI must remain positive.
   3. No live promotion without a separate ADR after the 200-close
      validation.
2. Authorise build of `bots/bot_d_spike_short/` as a clean clone of
   `bots/bot_d_spike/` with TTR window `[0, 6)` hours, same city whitelist,
   same `0.03-0.10` price band, same hold-to-resolution, sized at $1-3 per
   position with a $200 deployed cap, 50 concurrent positions, and a
   raised daily-entry cap (because <6h positions resolve fast and slot
   turnover is higher) — initial cap `30`.
3. Deploy as a separate paper lane (`bot_id = bot_d_spike_short`) on the
   `the-vps` VPS with its own systemd unit
   `polymarket-bot-d-spike-short-vps.service`. Do not touch the existing
   `polymarket-bot-d-spike-vps.service`.
4. Daily report adapts `scripts/bot_d_spike_daily_report.py` style to read
   `bot_id='bot_d_spike_short'`, separate from the 6-12h lane so attribution
   stays clean.
5. The general "near-resolution scalping" prohibition stays for crypto
   (except Bot G's grandfathered scope), sports, politics, awards, and all
   other categories. Bot G's existing 5/15-min crypto operation is
   unchanged.

**Distinguishing characteristics from ADR-033 (Bot A archive) and the
broader kill-list line:**

- Empirical: 40,496 V2 trades show the same robustness profile that
  authorised Strategy E (which has +16% top-5 robust on 35,931 trades).
- Scoped: weather temperature-bucket markets only; not a general lift.
- Paper-only: the existing Strategy E paper lane has not yet validated
  forward; this lane runs alongside it without competing for the same TTR
  window or capital.

**Consequences:**

- A new paper bot lane `bot_d_spike_short` runs on the VPS, sharing the
  weather city whitelist and price band with `bot_d_spike` but in the 0-6h
  TTR window.
- Daily entry cap is `30` (vs. `20` for the 6-12h lane) because positions
  resolve faster.
- If `<6h × weather` forward-validates and `6-12h × weather` does too, the
  combined Strategy E2 lane could legitimately scale to $5-15K/year at $5k
  cap.
- If `<6h × weather` forward-fails but `6-12h × weather` succeeds, this
  confirms Strategy E's TTR boundary is meaningful (operator's empirical
  edge is specifically "last few hours" not generally "near-resolution").
- CLAUDE.md kill-list line updated in the same session this ADR lands so
  the rule and the deployed code are consistent.

**Rollback trigger:** Disable
`polymarket-bot-d-spike-short-vps.service` if any of:

- Realized ROI on closed positions drops below `+5%` after `≥30` closes.
- Hit rate drops below `4%` after `≥30` closes.
- Top-5-robust ROI on closed positions goes non-positive at the 200-close
  audit gate.
- Operator observes the lane front-running or competing for fills with the
  6-12h `bot_d_spike` lane (city/price overlap should not occur because the
  TTR windows don't overlap, but flag immediately if it does).

If disabled, the existing `bot_d_spike` 6-12h lane continues unchanged.

---

## ADR-134: Maker-flow paper bot (Bot H) — top-2 cell filter, wide recorder, paper-only

**Date:** 2026-05-08
**Status:** accepted

**Context:** The 2026-05-08 robustness probe
(`docs/reports/track1-maker-flow-robustness-probe-2026-05-08.md`) tested
the cell-filtered Track 1 maker-flow simulation under three orthogonal
audits: top-N market exclusion (excl-top-1, top-5, top-25), fill-rate
sensitivity (5/10/15%), and toxicity-weight sensitivity (1×/2×/4×). The
results split the original "top cells" into clear PASS / FAIL groups:

| cell | as-is ROI | excl-top-5 (worst combo) | verdict |
|---|---:|---:|---|
| politics 30-40c | +73.6% | -90.9% | FAIL — 5-market mirage |
| **politics 0-10c** | **+57.1%** | **+41.1%** | **PASS** |
| **sports 10-20c** | **+79.1%** | **+47.2%** | **PASS** |
| awards 0-10c | +49.7% | -87.9% | FAIL |
| politics 40-50c | +48.5% | -66.7% | FAIL |
| crypto 0-10c | +13.1% | +2.9% | MARGINAL |
| _other 0-10c | +12.9% | -10.3% | FAIL |

The biggest absolute-dollars cell (politics 30-40c, +$168K NET on $229K
cost in the original blended sim) is a 5-market-out-of-902 mirage — same
shape as the killed sports/politics cheap-YES BUYs from Test C. But
politics 0-10c and sports 10-20c are genuinely robust: positive at every
sensitivity combo, broad sample (3,587 unique markets combined),
conservative excl-top-5 ROI of +45.7% on $136K cost basis.

Operator approved (2026-05-08, Session 246) building a paper-only
maker-flow lane targeting these two cells, with the explicit requirement
that the recorder capture **all data needed to re-test other economics
later** (counterfactual cell mixes, alternative AS-proxy windows,
real-vs-simulated fill-rate validation).

CLAUDE.md `Out-of-scope` contains: `Market-making / rebate farming bot`.
This entry must be partially lifted to authorise the build. The general
prohibition stays for any cells, categories, or strategies outside this
ADR's narrow scope.

The full spec is at
`docs/reports/track1-maker-flow-robustness-probe-2026-05-08.md`.

**Decision:**

1. Lift CLAUDE.md "Market-making / rebate farming bot" entry **for the
   following narrow scope only**, paper-only, conditional on the build
   matching this ADR:
   1. Active quote cells: **politics 0-10c** and **sports 10-20c only**.
      Skip every other cell (including politics 30-40c which the probe
      killed).
   2. Hold-to-resolution exit. No intraday unwind.
   3. AS-loss tracking from day 1 — per-fill toxicity labelled at 5-min,
      15-min, 60-min, and at-resolution horizons.
   4. Builder-code rebate harvesting via the existing V2 fee-share path
      (`sports/politics 25%` per `core/config.FEE_RATE_BY_CATEGORY_BPS`).
   5. No live promotion without a separate ADR after the 200-close
      validation gate.
2. Authorise build of `bots/bot_h_maker_v2/` as a new module (not a clone
   of bot_d_spike — different shape, requires WSS quote management). The
   module ships in two phases:
   - **Phase 1 (this session):** wide recorder. Subscribe to politics and
     sports CLOB books; persist book snapshots and trade observations to
     a dedicated `data/maker_recorder.db`. NO quote placement yet.
     Start collecting data immediately so Phase 2 has weeks of real
     evidence by the time it ships.
   - **Phase 2 (subsequent sessions):** quote engine + paper-fill
     simulator. Quotes posted only on the active cells; paper fills
     logged when actual taker BUYs hit our quoted bid; AS-loss per fill
     tracked across horizons.
3. **Wide recorder coverage** (key operator requirement): the recorder
   captures markets and trades across **all politics + sports + awards +
   crypto cells in the 0c-50c range**, not just the active quote cells.
   This lets us:
   - Re-run the maker-flow simulator on real V2 forward data when enough
     accumulates (vs WANGZJ historical only).
   - Test the AS-proxy at alternative horizons (5-min may be more
     accurate than 15-min for fast-moving informed flow; we'll have data
     to check).
   - Counterfactual analysis: "what if we'd quoted on cell X" with real
     book state at the time.
   - Validate (or invalidate) the killed-cell verdicts on forward data.
4. Deploy the recorder phase as a separate paper lane on
   `the-vps` VPS with its own systemd unit
   `polymarket-bot-h-maker-v2-recorder-vps.service`. Do not touch any
   existing service.
5. Storage budget: dedicated SQLite DB at
   `data/maker_recorder.db`, sized expectation `<5 GB/month` based on
   politics+sports market count and trade volume. Operator approves a
   rollover policy if it exceeds 10 GB before 90 days.

   **AMENDED 2026-05-08 (Session 256):** observed disk growth at
   `~720-865 MB/day` projected the original `10 GB / 90 days` budget
   to fail in `~14 days`. Diagnosis (per Session 255 daily report):
   `~95%` of WSS event volume is broadcast about NON-subscribed
   markets (Polymarket WSS sends `book` / `price_change` /
   `last_trade_price` / `best_bid_ask` events for many markets we did
   not request). Two changes resolve this:

   - **Plan B (raise budget):** new budget is **30 GB** instead of
     10 GB. a small EU VPS
     fits comfortably. Daily report's
     `DISK_BUDGET_BYTES` constant updated accordingly.
   - **Plan D (write-time filter):** `bots/bot_h_maker_v2/capture.py`
     now drops `book` / `price_change` / `last_trade_price` /
     `best_bid_ask` events whose `asset_id` is not in
     `state.token_to_condition` (the gamma-discovered subscription
     set). `new_market`, `reconnect`, `disconnect`, and `heartbeat`
     events are always kept regardless of subscription state.
     Estimated `~95%` volume reduction once redeployed; combined with
     the 30 GB budget this gives the recorder roughly `>1 year` of
     headroom at observed event rates.

   Rollback trigger updated: disable the recorder if disk usage
   exceeds **30 GB** before 90 days (was 10 GB), OR if the filter
   drop rate falls below `90%` of inbound volume (which would
   indicate either a subscription scope change or a filter bug).

**Distinguishing characteristics:**

- Empirical: 3,587 unique markets across politics 0-10c + sports 10-20c,
  +45.7% conservative excl-top-5 ROI, robust across 5 sensitivity combos.
- Scoped: top-2 cells only; recorder captures wider for analysis but
  quote engine narrow.
- Paper-only: no live CLOB writes in either phase.
- Phased: Phase 1 (recorder) ships this session for early data
  collection; Phase 2 (quote engine) is gated on operator approval after
  reviewing recorder output.

**Consequences:**

- A new paper bot module `bot_h_maker_v2` runs Phase 1 (recorder) on the
  VPS starting this session.
- Storage on `the-vps` grows by an estimated 2-5 GB/month from
  recorder writes.
- Phase 2 build (quote engine, paper-fill simulator, AS tracker) is a
  follow-on of 3-4 sessions.
- Live promotion remains blocked until a separate ADR after Phase 2
  produces 200 closes with kill-trigger metrics passing.
- The cell-filtered ROI projection (`+45.7%` conservative on $136K
  simulated cost; $15-25K/yr at $5k cap realistic) is the empirical
  target the bot must approach in forward paper performance.

**Rollback trigger:** Disable
`polymarket-bot-h-maker-v2-recorder-vps.service` (or the future Phase 2
lane) if any of:

- Disk usage from `data/maker_recorder.db` exceeds 10 GB before 90 days
  AND no clean rollover plan is in place.
- Phase 2 paper closes show realised ROI below `+20%` after `≥30` closes
  (vs simulation `+45%`).
- AS-loss exceeds `+10%` of cost basis as a sustained ratio over 200
  closes (rebate stops covering it).
- Top-5-robust ROI on closed positions goes non-positive at the 200-close
  audit gate.
- Operator detects the lane interfering with `bot_d_spike` /
  `bot_d_spike_short` / Bot G live operation.

If disabled, the existing paper lanes (bot_d_spike, bot_d_spike_short,
wallet observer) continue unchanged.

## ADR-135: Emergency-pause Bot G Prime Live after live-shaped cohorts fail

**Date:** 2026-05-08
**Status:** accepted

**Context:**

The operator flagged an urgent discrepancy: dashboard showed `bot_g_prime`
paper at `+$356.99` while `bot_g_prime_live` showed about `-$181.50` realised
cash P&L. A read-only split review showed the green paper card is not the right
live comparator:

- `bot_g_prime` is the legacy/main paper lane with 4c-8c history and outlier
  wins. Its current 168h report is `105` orders, `105` fills, `105` resolved,
  `10` wins, `+$228.9629`, `+62.17%` ROI, but only `+3.9%` after removing
  the largest two wins.
- `bot_g_prime_shadow`, the live-shaped paper mirror, is `57` orders, `57`
  fills, `55` resolved, `1` win, `-$183.2149`, `-85.45%` ROI, and `-100%`
  after removing the largest win.
- `bot_g_prime_take_profit` is `52` orders, `52` fills, `50` resolved,
  `0` wins, `-$203.9894`.
- `bot_g_prime_late_cheap` is `122` orders, `122` fills, `117` resolved,
  `1` win, `-$415.9219`.
- Live has `0` open orders and small open-position exposure at the pause check.

The 4c-8c paper lane's positive headline is concentrated in the 6.5c-8c bucket:
`25` resolved / `6` wins / `+$192.5398`; this is sparse jackpot behavior, not
a robust basis for immediate live promotion. The lower 3.5c-5.5c paper/live
mirror rows are negative in forward/live-shaped data.

**Decision:**

1. Stop and disable `polymarket-bot-g-prime-live.service` on
   `vps-host` immediately.
2. Keep Bot G paper lanes and recorders running for data collection.
3. Do not restart Bot G live at 3.5c-5.5c or switch it to 4c-8c without a
   separate operator-approved restart ADR based on fresh evidence.
4. Treat `bot_g_prime` headline P&L as historical/research context, not the
   live-readiness comparator. Live-readiness must compare against
   live-shaped paper cohorts and outlier-trimmed results.
5. Existing live open positions may resolve naturally. Do not place live SELL
   exits or redemptions from this ADR alone.

**Consequences:**

- Bot G live places no new real-money BUY orders while disabled.
- Dashboard will show Bot G live inactive after the VPS status bridge refreshes.
- Bot G research data collection continues without risking additional live
  entry losses.
- Restart requires an explicit new decision with a concrete parameter set and
  forward evidence.

**Rollback / restart condition:**

A future ADR may restart Bot G live only if a live-shaped paper cohort passes
minimum robustness gates: positive outlier-trimmed ROI, non-trivial closed
sample, and no single-bucket jackpot concentration driving the result.

## ADR-136: Resume Bot G Prime Live as $1 data-gathering micro-probe

**Date:** 2026-05-08
**Status:** accepted

**Context:**

ADR-135 emergency-paused Bot G Prime Live after the live-shaped evidence failed:
the live-shaped paper mirror and the live account were both materially negative,
while the green paper Prime headline was driven by sparse 6.5c-8c jackpot wins.
After reviewing that risk, the operator explicitly chose to bring live back for
data collection only, at `$1` per trade.

The restart goal is live execution and outcome data, not a claim that Bot G's
edge is repaired or ready to scale. The paper lanes and recorders continue to
run indefinitely so future market-regime or time-of-day effects can be tested.

**Decision:**

1. Resume `polymarket-bot-g-prime-live.service` on `vps-host`.
2. Set `BOT_G_FIXED_TRADE_USD=1` in both canonical live unit files:
   - `systemd/polymarket-bot-g-prime-live.service`
   - `systemd/polymarket-bot-g-prime-live-vps.service`
3. Keep every other Bot G Prime Live parameter unchanged:
   - 3.5c-5.5c entry band.
   - 60s final entry window.
   - BTC/ETH/SOL live symbols.
   - `$200` live wallet cap.
   - `$100` live daily gross cap.
   - 20 live daily entries.
   - 10 live max concurrent positions.
4. Do not switch live to 4c-8c under this ADR.
5. Treat this as a live data-gathering micro-probe. Scaling or strategy
   promotion still requires a separate ADR with fresh evidence.

**Consequences:**

- Bot G Prime Live may place real-money BUY orders again, but each entry is
  capped at `$1`.
- Expected drawdown per losing trade is much lower than the prior `$3` setting,
  allowing continued observation while limiting cash burn.
- ADR-135's diagnosis remains valid: live-shaped cohorts are negative and the
  historical paper headline is not the live-readiness comparator.
- Dashboard/runtime telemetry must show `env=live`, `dry_run=False`, and
  `fixed_trade_usd=1` after deployment.

**Rollback trigger:**

Disable `polymarket-bot-g-prime-live.service` again if any of:

- Runtime telemetry diverges from the approved live state (`fixed_trade_usd=1`,
  `dry_run=False`, `effective_paper=False`).
- Unexpected live orders, unexplained position changes, or CLOB auth problems
  appear.
- Operator decides the data value no longer justifies live losses.
- A fresh paper/live-shaped audit shows continued losses with no useful
  diagnostic signal.

## ADR-137: Wallet-tag forward validation window — 7 days, dual-timer observer + resolution backfill

**Date:** 2026-05-08
**Status:** accepted

**Context:**

The 2026-05-08 wallet-tag Murphy decomposition surfaced the first
decision-grade math-found edge candidate in the entire research cycle:
PolyVerify `bot_score < 30` cohort, +10.7pp edge, 95% CI [+4.4%,
+184.8%] on 25,092 recent WANGZJ trades, with both halves of the
60-wallet cohort (one high-volume wallet alone, 59 other wallets
combined) passing the gate independently.

A passive forward-validation observer was approved and deployed earlier
the same day (Session 249 changelog, OQ-099 acceptance section). The
initial draft used a 30-day forward window mirroring the WANGZJ
baseline window — operator pushed back: "30 days is too long, max 7
days, make adjustments based on this."

The 7-day-window decision affects three coupled parameters and was
therefore promoted to its own ADR so a future session does not silently
drift them:

1. The cadence of the trades observer (15 min vs original 30 min).
2. The need for a separate resolution-backfill loop (Polymarket Gamma
   API, every 6h) that the original 30-day plan did not include.
3. The gate-threshold recalibration in
   `scripts/research/wallet_observer_report.py` — `n ≥ 200` settled
   trades for a verdict, with a third `INSUFFICIENT` state added to
   separate "wait for more data" from "edge failed".

**Decision:**

1. Forward-validation window is **7 days**, not 30. The 60-wallet
   cohort produced ~278 trades/day in the WANGZJ historical panel;
   7 days is sufficient to accumulate ≥ 200 settled trades for the
   cohort-level gate.
2. Trades observer cadence is `OnUnitActiveSec=15min` to halve the
   miss-rate on ttr<1h markets within the 7-day window.
3. Resolution backfill (`scripts/research/wallet_observer_resolutions.py`)
   runs every 6h on a separate timer
   (`polymarket-wallet-observer-resolutions.{service,timer}`) with
   `--max-age-days 14` (covers the 7-day forward window plus a buffer
   for late-settling markets), `--max-markets 500` per run.
4. Forward-gate verdict thresholds:
   - `INSUFFICIENT` if `n < 200` settled wallet trades.
   - `PASS` if `n ≥ 200` AND `resolution > 0.001` AND
     `top_2_concentration < 50%` AND `roi_ci_95_lower > 0`.
   - `FAIL` otherwise.
5. First report-eligible date: **2026-05-15**.
6. Both observer services remain read-only HTTP-poll. No wallet keys,
   no order placement, no bot code modified.

**Consequences:**

- Forward validation can complete in 1 week instead of 1 month,
  unblocking the bot-feature ADR (or kill decision) earlier.
- The 15-min trades cadence makes ~96 polls/day vs 48 — small additive
  load on the Polymarket Data API and the bot container (each tick is ~1 minute
  of HTTP-bound work for 106 wallets).
- The 6h resolution cadence makes 4 polls/day. Gamma rate limit not
  hit in the smoke test (260/500 markets fetched, 13 s wall clock).
- The `INSUFFICIENT` verdict gives a third path: if at T+7 the cohort
  has < 200 settled trades, the operator decides "extend the window"
  vs "accept low cohort throughput, move on" rather than being forced
  into a binary PASS/FAIL on a too-small sample.

**Rollback / extension condition:**

If on 2026-05-15 the cohort has fewer than 200 settled trades, a
future ADR may extend the window to 14 days. If the gate FAILs on a
≥ 200 sample, the wallet-tag edge is treated as historical artifact;
disable both observer timers and archive the data.

**Cross-refs:** ADR-126 (passive wallet observer scaffolding),
OQ-099 (forward-validation gate), Session 249 changelog (deployment
verification + same-day follow-up),
`docs/reports/wallet-tag-edge-finding-2026-05-08.md` (consolidated
finding).

## ADR-138: Final-evaluation hides for archived cohort and Bot G regime-monitor framing

**Date:** 2026-05-09
**Status:** accepted

**Context:** The 2026-05-09 archived-bots-and-recorders final
evaluation
(`docs/reports/archived-and-recorder-final-evaluation-2026-05-09.md`)
swept every archived bot, every parked lane, and every recorder
against fresh the bot container + VPS evidence. No newly surfaced edge cleared
the priority-alert protocol; the only decision-grade math-found
candidate (PolyVerify wallet-tag cohort, ADR-137) is already in
active forward-validation through 2026-05-15. The pass produced
three small registry/truth-surface adjustments that needed to be
recorded so they do not silently drift in a future session.

**Decision:**

1. Confirm current-dashboard hide for the entire archived/parked cohort:
   `bot_a`, `bot_a_shadow`, `bot_b`, `bot_b_shadow`, `bot_c`,
   `bot_f`, `bot_f_mirror`, `bot_g`, `bot_g_jackpot`, `bot_g_scalp`.
   No current runtime restart path for any of them. Code, ledger rows, and
   historical events stay in the repo and DB for audit. Bot B's separate
   future spin-off path remains governed by ADR-072 and is not reactivated
   by this decision.
2. Promote `bot_f` registry status from `sensor` to `archived`.
   The `polymarket-bot-f-mirror.service` unit is not running on
   the bot container or VPS, and the wallet-flow research role is now covered
   by `wallet_observer` (ADR-126/137) and `bot_h_maker_v2` (ADR-134).
   The historical crowd-flow `mirror_signals` rows remain in the
   database as research evidence, and OQ-059 may still mine that dataset
   for fillability-gated same-side momentum. The retired Bot F executor
   and default-dashboard identity are dead.
3. Tag the three Bot G Prime paper-only probes
   (`bot_g_prime_shadow`, `bot_g_prime_late_cheap`,
   `bot_g_prime_take_profit`) in the registry description as the
   ADR-135 live-shaped regime-monitor cohort. Their headline P&L is
   negative on the live-shaped sample (mirror `1 win / 55 resolved`,
   `-100%` ex-largest-win; late-cheap `1 win / 117 resolved`;
   take-profit `0 wins / 50 resolved`); they keep running for paper
   regime-change monitoring, not as live-readiness evidence. They
   stay hidden from the default operator surface.
4. Confirm the four active recorders stay visible and continue:
   `polymarket-bot-e-recorder.service` (the bot container, ADR-122 indefinite),
   `longshot-crypto-recorder-vps-paper-feed.service` (VPS, BTC/ETH/
   SOL/XRP/DOGE context), `polymarket-bot-h-maker-v2-recorder-vps.
   service` (VPS, ADR-134 Phase 1, on track to hit the 1M pm_events
   acceptance gate inside ~4 days at observed event rate), and
   `polymarket-wallet-observer.service` (VPS, ADR-137 7-day forward
   gate, first report 2026-05-15).
5. No bot is added to the default 4-card fleet header. No new
   recorder is restarted. Bot G live remains under ADR-135/ADR-136
   as a `$1` data-gathering micro-probe; Bot H stays Phase 1
   recorder-only under ADR-134.

**Consequences:**

- `bot_f` row moves from inventory group "Recorder" to "Archived" in
  the dashboard inventory table because the inventory grouping is
  driven by `registry_status`. No code change to the dashboard layer.
- The three Bot G paper probe descriptions now explain why they keep
  running — operators reviewing the inventory will not mistake them
  for live-readiness evidence.
- `bot_b` and `bot_b_shadow` keep `paper`/`shadow` registry status
  because the cap-membership test contract pins `bot_b in
  cap_member_bot_ids()` while bot_b still holds 1 OPEN position. They
  remain halted and hidden; a future cleanup ADR can demote them to
  `paused` alongside the spin-off plan.

**Rollback / reopen condition:**

A future ADR may reopen any archived lane only with new robust
evidence (positive ex-largest-win and ex-largest-two-wins ROI on a
non-trivial closed cohort) and explicit operator approval. Recorder
or Bot H status changes still require the relevant ADR-134 / ADR-122
gates to clear.

## ADR-139: Archive crypto fair-value paper strategies and retain recorder infrastructure

**Date:** 2026-05-09
**Status:** accepted

**Context:** The final pre-archive review
(`docs/reports/crypto-fv-final-review-before-archive-2026-05-09.md`)
audited `crypto_probability_gap_paper` and
`crypto_brownian_fv_paper` against the the bot container dashboard bridge and the
latest pulled VPS paper ledger backup
(`<bulk-storage>/`). Both
paper lanes were still `vps:active` at the the bot container bridge check
(`2026-05-09T14:55:43Z`), but the forward paper results failed
OQ-078's keep gate.

Probability Gap had `145` signals, `145` 1c-stressed simulated
fills, `144` closed positions, `71` wins, `-$104.00` fee-adjusted
P&L on `$720` closed stake, `-14.4%` net ROI, `-17.1%`
ex-largest-win ROI, and `-19.7%` ex-largest-two ROI. Brownian FV
had `198` signals, `198` 1c-stressed simulated fills, `196` closed,
`103` wins, `-$100.80` fee-adjusted P&L on `$980` closed stake,
`-10.3%` net ROI, `-12.5%` ex-largest-win ROI, and `-13.9%`
ex-largest-two ROI. Positive slices were either underpowered,
winner-sensitive, or contradicted by a losing parent lane.

**Decision:**

1. Archive `crypto_probability_gap_paper` and
   `crypto_brownian_fv_paper` as active/paper strategy lanes.
   Their `bot_id`s stay stable, code and historical ledgers remain
   available for audit, and no live trading authorization exists.
2. Hide the Crypto FV strategy surfaces from the active dashboard:
   remove the FV card from the default Recorders tab, remove both
   services from active systemd health accounting, and remove the
   `/api/crypto-fair-value` dashboard route.
3. Retain the shared crypto recorder infrastructure. ADR-122 and
   ADR-081 still apply: the the bot container Bot E recorder and VPS crypto
   recorder feed remain data infrastructure for Bot G replay,
   symbol/time/liquidity analysis, XRP/DOGE record-only context, and
   future research.
4. Do not stop or restart any service as part of this ADR. The paper
   strategy services should be disabled/stopped only through a
   separate operator ops action; recorder services continue unchanged.

**Rationale:** Both paper strategy lanes fail on current forward
paper after fees, 1c adverse fill stress, ex-largest-win, and
ex-largest-two robustness. Continuing to surface them as active
paper strategies creates dashboard clutter and distracts from higher
priority Bot D, Bot G, wallet-observer, and Bot H work. The raw
recorder tape, however, remains valuable and healthy; archiving a
failed strategy is not evidence for stopping shared data collection.

**Consequences:**

- `core/bot_registry.py` moves both Crypto FV paper lanes to
  `archived`.
- `active_systemd_units()` no longer includes the two Crypto FV paper
  service names, so active dashboard service health does not depend on
  archived paper-lane services.
- The dashboard Recorders tab keeps recorder diagnostics and no
  longer fetches or renders the Crypto FV paper panel by default.
- OQ-078 is resolved as "archive current paper lanes"; any future
  crypto fair-value revival requires a new OQ/ADR and new evidence.

**Rollback / reopen condition:** A future ADR may re-open a crypto
fair-value strategy only with new settlement-label evidence that
passes fees, latency/fillability, 1c/2c stress, ex-largest-win,
ex-largest-two, and a non-trivial symbol/time forward sample. A
recorder-health problem should be handled under ADR-122/OQ-053, not
by re-opening these paper strategies.

## ADR-140: Retire Bot G late-cheap and take-profit paper lanes after final review

**Date:** 2026-05-09
**Status:** accepted

**Context:**

The 2026-05-09 Bot G family final review
(`docs/reports/bot-g-final-review-2026-05-09.md`) audited every
active Bot G Prime lane against fees, 1c-stress, ex-largest-win,
ex-largest-two, top-k/outlier trim, negative controls, fillability,
and no-lookahead. Two paper lanes were singled out for retirement:

- `bot_g_prime_late_cheap` (paper, `1c-3c`, 30s window, BTC/ETH/SOL):
  152 closed / 1 win / -$560.71 / **-86.4% ROI** all-time on VPS.
  ex-largest -$646.02 (worse). The lane's earlier ADR-128 collection
  posture explicitly required a -100% rolling ROI floor; that floor
  has been violated. Thesis (1c-3c near-close near-fresh-clock
  dislocation) is falsified at decisive sample.
- `bot_g_prime_take_profit` (paper, `3.5c-5.5c` entries with synthetic
  50c TP exit inside the final 25s-8s window): 65 closed / 1 win /
  -$184.15 / **-67.5% ROI**. ex-largest -$269.30 (worse). Critically,
  the take-profit replay
  (`docs/reports/bot-g-take-profit-replay-2026-05-08.json`) shows
  **0 of 26 positions ever hit even the 50c threshold; 0 actual TP
  events fired** across both 50c and 70c thresholds. The synthetic
  exit is unreachable in the recorder data; the thesis is decisively
  falsified.

Both lanes were already hidden from the default operator dashboard
under ADR-138's regime-monitor framing, and Session 274 ADR-138
recorded them as ADR-135 regime-monitor only. The 2026-05-09 final
review confirms the underlying theses are dead, not merely
underperforming pending more data.

ADR-128 (lower paper take-profit probe to 50c and keep late-cheap
collecting) is the authoritative "keep collecting" decision. It
becomes superseded for both lanes by this ADR.

**Decision:**

1. Stop and disable on VPS:
   - `polymarket-bot-g-prime-late-cheap.service`
   - `polymarket-bot-g-prime-take-profit.service`
2. `core/bot_registry.py`: `paper_tuning` → `archived` for
   `bot_g_prime_late_cheap` and `bot_g_prime_take_profit`. Tighten
   descriptions to record the falsification reason and date.
3. Update `docs/active-operating-model-2026-05-02.md`:
   remove both lanes from "Shared Data Infrastructure" and add to
   "Archived Active Surfaces" with the ADR-140 reference.
4. Mark this ADR as superseding ADR-128's "keep collecting" intent
   for these two lanes. (ADR-128's `bot_g_prime` 4-8c paper guidance
   continues to apply to the surviving paper lanes; only the two
   archived lanes are superseded here.)
5. Ledger rows in the bot container main DB and VPS `bot_g_vps_main.db` are
   preserved for audit; no DB rows are deleted.

**Consequences:**

- Frees the VPS CPU/memory footprint of two services.
- Simplifies the operator surface; the four-card fleet header
  already excluded these lanes, but inventory now correctly groups
  them under archived.
- Does not affect Bot G Prime live `$1` probe (ADR-136), Bot G Prime
  paper 4-8c (`bot_g_prime`), or Bot G Prime live-mirror paper
  shadow (`bot_g_prime_shadow`, kept as ADR-135 regime monitor).
- Does not affect shared crypto recorder (ADR-122 indefinite).
- Does not affect any live order path or wallet posture.

**Rollback:** A future ADR may revive either lane only with new
evidence proving the underlying thesis. For late-cheap, that means a
robust positive forward sample at 1c-3c that survives ex-largest-2
trimming. For take-profit, that means recorder evidence that paper
positions actually reach the synthetic 50c exit threshold at a
non-trivial frequency — the current 0/26 finding is the binding
falsification.

**Cross-refs:** ADR-128 (superseded for these two lanes only),
ADR-135 (emergency-pause regime-monitor framing), ADR-136
(`$1` live data probe, unchanged), ADR-138 (Session 274 hides),
ADR-139 (Session 283 crypto FV archive, unchanged),
OQ-051 / OQ-063 / OQ-094 (resolved 2026-05-09),
`docs/reports/bot-g-final-review-2026-05-09.md`,
`docs/reports/bot-g-take-profit-replay-2026-05-08.json`.

## ADR-141: Accelerate read-only evidence cadence for strategy resource ranking

**Date:** 2026-05-09
**Status:** accepted

**Context:**

The 2026-05-09 strategy ranking refresh
(`docs/reports/strategy-ranking-and-data-roadmap-2026-05-09.md`) ranked
near-term resource allocation by profit, ROI, and speed of resolution. The
binding bottleneck was not a missing thesis; it was slow evidence cadence on
the highest-value proof loops:

- the bot container wallet-tag forward gate was collecting and resolving slowly enough
  that the next clear decision risked waiting on timer cadence rather than
  market outcomes.
- VPS Bot H Maker V2 had enough raw recorder events to justify frequent
  replay, but not enough replayable closed trips; resolution backfill and
  replay cadence were slower than needed for OQ-100.
- VPS wallet observer reports were daily even though the collector was
  already producing high-volume fills.
- Bot D live had repeated sub-`$1` CLOB rejections caused by fixed-share
  sizing on very cheap prices; this wastes evidence opportunities but the
  live service itself should not be restarted without an explicit live-path
  deployment decision.

**Decision:**

1. Accelerate the bot container wallet-tag forward evidence:
   - `polymarket-wallet-tag-forward.timer`: `15m` -> `5m`.
   - `polymarket-wallet-tag-forward-resolutions.timer`: `6h` -> `2h`.
   - Add hourly `polymarket-wallet-tag-forward-report.timer`.
2. Accelerate VPS read-only proof loops:
   - Bot H resolution backfill timer: `6h` -> `2h`.
   - Bot H resolution recheck throttle: `4h` -> `2h`.
   - Bot H recorder replay timer: daily -> every `4h`.
   - VPS wallet-observer report timer: daily -> every `6h`.
3. Add a local Bot D live min-notional guard with default
   `BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=$1.00`, so future live deployments can
   block impossible sub-`$1` orders before CLOB submission.
4. Do not loosen strategy filters, increase live size, change bankroll/caps,
   or restart live trading services under this ADR.

**Consequences:**

- Wallet-tag and Bot H gates move from daily-ish evidence updates to
  same-day proof loops.
- Operator reports should show whether new data is decisive within hours
  rather than waiting for the next daily report.
- Extra API/database load is bounded by existing small candidate sets and
  read-only/reporting services.
- Live trading behavior remains unchanged until a separate explicit
  deployment/restart decision applies the Bot D guard.

**Rollback:**

Restore the prior timer cadences from the backups taken under:

- the bot container: `/home/bot/polymarket-bot/backups/codex-20260509-fast-evidence/`
- VPS: `/home/operator/longshot-research/backups/codex-20260509-fast-evidence/`

Then run `systemctl daemon-reload` and restart the affected timers. The Bot D
min-notional guard can be disabled by setting
`BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=0`, but the preferred rollback is to leave
the guard in code and avoid deploying/restarting the live service until
approved.

**Cross-refs:** ADR-134 (Bot H Maker V2 recorder gate), ADR-137
(wallet-tag forward gate), OQ-099 (wallet-tag forward proof), OQ-100
(Bot H Phase 2 gate), `docs/reports/strategy-ranking-and-data-roadmap-2026-05-09.md`.

## ADR-142: Promote three confirmation lanes to paper-only status

**Date:** 2026-05-09
**Status:** accepted

**Context:**

After the strategy ranking refresh and the accelerated evidence cadence, the
operator asked which candidate edges should be turned into paper traders to
further confirm strategy. The strongest immediate paper-confirmation candidates
are:

- Bot D source/tier/city confirmation: live probe is positive but underpowered
  (`31` closed / `23` wins / `+$12.73`, ex-largest-two ROI `+7.44%`) and needs
  a clean source-sliced paper comparator.
- Persistence Paper (I): already running on the bot container as a daily paper/replay lane,
  with `69` entries / `59` wins / `+15.85%` post-fee ROI, Cell A `32/50`, Cell
  B `37/50`.
- Bot F same-side crowd momentum: historical PASS cells at 1800s show
  `n=117-380` and net edge `+4.16c` to `+10.92c`, but the report correctly
  warned that public prints are not executable quotes and SELL signals are not
  directly tradable without inventory.

The next three candidates are worth noting but not promoting immediately:
WC/negRisk basket paper monitor, wallet-tag feature shadow, and Bot H Maker V2
quote paper. Each has an external gate or timing blocker.

**Decision:**

1. Promote `bot_d_source_shadow` to paper tuning:
   - New service: `polymarket-bot-d-source-shadow.service`.
   - Reuses the Bot D weather engine with `BOT_D_ID_OVERRIDE=bot_d_source_shadow`.
   - Forces `BOT_D_ENV=paper` and `POLYMARKET_ENV=paper` after loading `.env`.
   - Mirrors the live-probe weather settings but writes under a separate bot ID.
2. Keep and canonicalize Persistence Paper (I):
   - Add `polymarket-persistence-paper.{service,timer}` to the repo so the
     deployed the bot container daily paper/replay lane is represented locally.
   - Continue the existing first gate: `50` entries in each cell, then
     outlier, fee, slippage, and negative-control review.
3. Promote Bot F same-side momentum to paper tuning:
   - New script: `scripts/bot_f_momentum_paper.py`.
   - New timer: `polymarket-bot-f-momentum-paper.timer` every `5m`.
   - Reads Bot F `mirror_signals`, accepts only BUY-side executable signals
     matching the strongest 1800s PASS cells, writes
     `data/bot_f_momentum_paper.db`, and closes entries from public trade
     prints after 1800s.
   - It does not construct a CLOB client, load a wallet key, or place orders.
4. Note the next-three promotion queue in
   `docs/reports/paper-promotion-queue-2026-05-09.md`:
   WC/negRisk paper monitor, wallet-tag feature shadow, and Bot H Maker V2
   quote paper.

**Consequences:**

- Paper confirmation now focuses resources on the fastest defensible proof
  loops instead of resurrecting dead strategy families.
- Bot F is intentionally BUY-only for the first paper ledger. SELL same-side
  signals remain a research statistic, not an executable paper trade, because
  the fleet does not have inventory to sell.
- Bot D source-shadow can produce duplicate paper exposure on markets that
  Bot D paper/live also sees; this is acceptable because it is a separate
  paper-only bot ID and is used for attribution, not fleet exposure.
- No live wallet setting, bankroll, cap, strategy threshold, or real-money
  order path changes under this ADR.

**Rollback:**

Stop and disable:

- `polymarket-bot-d-source-shadow.service`
- `polymarket-bot-f-momentum-paper.timer`
- `polymarket-bot-f-momentum-paper.service`

Leave Persistence Paper (I) unchanged unless its own halt rule fires or a
future ADR disables it. The Bot F momentum paper DB can be archived without
touching Bot F `bot_f.db`.

**Cross-refs:** ADR-141 (accelerated evidence cadence), OQ-067 (Bot D live
transfer proof), OQ-059 (Bot F same-side momentum), OQ-099 (wallet-tag gate),
OQ-100 (Bot H Maker V2 gate), `docs/reports/paper-promotion-queue-2026-05-09.md`,
`docs/reports/bot-f-crowd-momentum-ev-2026-05-08.md`.

## ADR-143: Start the next three paper confirmation lanes before their proof gates clear

**Date:** 2026-05-09
**Status:** accepted

**Context:**

After ADR-142, the operator asked to proceed with the three "promote soon"
lanes as paper traders too:

- WC / negRisk basket paper monitor before the 2026-06-11 tournament window.
- Wallet-tag feature shadow even though OQ-099 has not yet reached
  `>=200` settled/scored BUYs or flipped positive.
- Bot H Maker V2 quote paper even though OQ-100 still requires `100`
  replayable trips and target-cell robustness.

The key distinction is "collect paper evidence now" versus "claim the edge is
ready." These lanes can run without keys, live CLOB orders, or bankroll impact.
They should not loosen live promotion gates.

**Decision:**

1. Promote WC / negRisk basket monitoring to paper tuning:
   - New bot ID: `wc_negrisk_basket_paper`.
   - New script: `scripts/wc_negrisk_basket_paper.py`.
   - New timer: `polymarket-wc-negrisk-basket-paper.timer` every `5m`.
   - Writes `data/wc_negrisk_basket_paper.db` and reports under
     `data/reports/wc_negrisk_basket_paper/`.
   - Records projection-only basket edge; realised P&L remains unset until a
     settlement closer is added.
2. Promote wallet-tag feature shadow to paper tuning:
   - New bot ID: `wallet_tag_feature_shadow`.
   - New script: `scripts/wallet_tag_feature_shadow.py`.
   - New timer: `polymarket-wallet-tag-feature-shadow.timer` hourly.
   - Reads `data/wallet_tag_forward.db`, writes
     `data/wallet_tag_feature_shadow.db`, and computes post-fee P&L only for
     strict/proxy-settled BUY rows.
   - This remains feature evidence, not copy-trading.
3. Promote Bot H Maker V2 quote paper to paper tuning:
   - New bot ID: `bot_h_maker_v2_quote_paper`.
   - New script: `scripts/bot_h_maker_v2_quote_paper.py`.
   - New VPS timer: `polymarket-bot-h-maker-v2-quote-paper-vps.timer` every
     `5m`.
   - Writes paper quote/fill tables in `data/maker_recorder.db`.
   - Does not construct a CLOB client, load wallet keys, or place orders.

**Consequences:**

- Resource allocation moves faster because all six candidate lanes now have
  forward paper evidence surfaces instead of waiting for manual review windows.
- OQ-099 and OQ-100 gates are not waived. Their decision gates remain binding
  before any feature plumbing, live order, or bankroll change.
- The first WC/negRisk row is projection-first; do not quote it as realised
  P&L until settlement support closes baskets.
- Bot H quote paper is intentionally a static quote simulator from recorder
  prints, not a live market maker.

**Rollback:**

Stop and disable:

- `polymarket-wc-negrisk-basket-paper.timer`
- `polymarket-wallet-tag-feature-shadow.timer`
- `polymarket-bot-h-maker-v2-quote-paper-vps.timer`

The generated SQLite ledgers can be archived without touching recorder DBs
except for Bot H's paper tables inside `maker_recorder.db`; those tables are
namespaced as `maker_quotes`, `maker_paper_fills`, and
`maker_quote_paper_run_log`.

**Cross-refs:** ADR-142 (first three paper promotions), OQ-099 (wallet-tag
gate), OQ-100 (Bot H Maker V2 gate), WC/negRisk research reports,
`docs/reports/paper-promotion-queue-2026-05-09.md`.

## ADR-144: Reserve the VPS for latency-dependent runtimes and back it up to the homelab hypervisor

**Date:** 2026-05-10
**Status:** accepted

**Context:**

The Helsinki VPS has a small root disk (`75G`, `57%` used during the
2026-05-10 audit) and already carries one large hot recorder DB:
`/home/operator/longshot-research/data/bot_e_recorder_vps_canary.db`
at `27.6GB`. The fleet also has the bot container/the homelab hypervisor storage with much larger
available capacity: bulk storage on `hypervisor-host` has `2.8T` free, the bot container has a dedicated
`100G` recorder mount and `200G` external-data mount, and the dashboard is
already the bot container-local.

The existing VPS pull backup protects only `bot_g_vps_main.db` and
`main.db` every 6 hours. It does not yet protect `maker_recorder.db`,
`wallet_observer.db`, deployed systemd unit metadata, or the large hot
crypto recorder DB.

**Decision:**

1. VPS placement policy:
   - Keep latency-dependent live traders on VPS.
   - Keep latency-dependent paper traders on VPS while their gates are active.
   - Keep only minimal VPS status/canary pieces needed by the bot container dashboard.
   - Move non-live-critical recorders, batch reports, label/resolution
     backfills, dashboards, large DBs, and non-latency paper simulations to
     the bot container/the homelab hypervisor after operator-approved migration.
2. Backup policy:
   - the homelab hypervisor `<bulk-storage>/` is the canonical VPS backup target.
   - Use SQLite-consistent backups: VPS-side `sqlite3 ".backup"` or
     `VACUUM INTO` to a staging snapshot, then rsync, table-count comparison,
     `PRAGMA quick_check`, SHA256 recording, and `zstd` verification.
   - Exclude `.env`, `.env.*`, unencrypted keys, passphrases, `.venv`, caches,
     temporary backup staging, and nonessential logs.
   - Expand backups to include `maker_recorder.db`, `wallet_observer.db`,
     systemd unit files, and key reports before any migration.
3. Disk policy:
   - VPS disk warning at `70%`.
   - Urgent operator action at `80%`.
   - Archive/migration/deletion action before `90%`.
4. No service moves, stops, live trading restarts, or live order-path changes
   are authorized by this ADR alone. Implementation still requires explicit
   operator approval, especially for the recorder rollover and any
   wallet-touching service.

**Consequences:**

- The VPS remains focused on Bot G live/paper, Bot D-Spike paper lanes, the
  feed pieces they need, passphrase support, and the status bridge.
- Bot H recorder/quote/replay/backfill and wallet observer are now formally
  migration candidates for the bot container.
- The largest unresolved risk is the hot crypto recorder DB on VPS. Prior
  evidence from ADR-124 showed blind hot copy is unsafe; it needs a controlled
  rollover, sharding, or maintenance-window backup before pruning.
- The audit report becomes the canonical migration plan:
  an internal role-audit report (not exported).

**Rollback:**

This ADR changes policy and documentation only. If a future implementation
causes load, backup corruption, or dashboard regressions, disable the new
backup timer or revert the affected unit migration, then restore from the
latest verified manifest under `<bulk-storage>/`.

**Cross-refs:** ADR-124 (initial VPS state DB backups), ADR-134 (Bot H Maker
V2 recorder), ADR-136 (Bot G live data probe), ADR-143 (Bot H quote paper),
OQ-053 (recorder storage/integrity), OQ-080 (VPS split-hosting pilot), OQ-102
(operator approval for migration sequence),
an internal role-audit report (not exported).

## ADR-145: Migrate Bot H Maker V2 and Wallet Observer from VPS to the bot container

**Date:** 2026-05-10
**Status:** accepted

**Context:**

ADR-144 classified the Helsinki VPS as a latency-dependent runtime host, not a
general recorder/reporting host. The operator approved proceeding with the
audit recommendations, with two hard requirements: double-check every finding
and preserve all recorder and paper-trader history during any move.

**Decision:**

1. Move these non-live-critical VPS workloads to the bot container:
   - `polymarket-bot-h-maker-v2-recorder.service`
   - `polymarket-bot-h-maker-v2-quote-paper.{service,timer}`
   - `polymarket-bot-h-maker-v2-resolution-backfill.{service,timer}`
   - `polymarket-bot-h-maker-v2-daily-replay.{service,timer}`
   - `polymarket-wallet-observer.service`
   - `polymarket-wallet-observer-daily-report.{service,timer}`
2. Preserve DB continuity through a final quiesced VPS backup before cutover:
   `<bulk-storage>/`.
3. Restore the final snapshots to the bot container and verify `PRAGMA quick_check` and
   key table counts before starting the bot container units.
4. Preserve the prior the bot container legacy Wallet Observer DB separately at
   `/home/bot/polymarket-bot/data/migration_backups/20260510T085720Z-final-move/wallet_observer_legacy_observed_trades.db`
   because it uses a legacy schema that should not be blindly merged into the
   newer VPS `wallet_observed_fills` schema.
5. Disable the matching VPS Bot H and Wallet Observer units only after the bot container
   units, reports, and dashboard rows verify healthy.
6. Do not move or restart Bot G live/paper, Bot G shadow, Bot D-Spike lanes,
   the crypto paper feed, live passphrase support, live redemption, or any live
   order path under this ADR.

**Verification:**

- `maker_recorder.db` restored to the bot container with `heartbeats=4220`,
  `maker_paper_fills=16`, `maker_quote_paper_run_log=153`,
  `maker_quotes=38`, `markets=106`, and `pm_events=1270465`.
- `wallet_observer.db` restored to the bot container with `collector_state=2`,
  `observer_runs=4`, and `wallet_observed_fills=186408`.
- the bot container Bot H recorder, Bot H quote paper, Bot H backfill, Wallet Observer,
  and Wallet Observer daily report smoke checks succeeded.
- Dashboard `/api/overview` reports Bot H recorder, Bot H quote paper, and
  Wallet Observer with `data_source=the bot container`.

**Consequences:**

- VPS root usage remains around `57%` after the move and staging cleanup.
- the bot container now owns Bot H and Wallet Observer growth.
- Bot H quote/fill history remains in `maker_recorder.db`; Wallet Observer
  fill history remains in `wallet_observer.db`.
- OQ-102 remains open for the large `bot_e_recorder_vps_canary.db`, disk
  threshold dashboarding, non-latency report moves, and wallet-touching
  redemption placement.

**Rollback:**

Stop the bot container units, restore the final VPS snapshots from
`<bulk-storage>/`, then re-enable the
disabled VPS units. Avoid split-brain by running only one writer for each DB
unless a future shadow mode is explicitly labelled and approved.

**Cross-refs:** ADR-144, OQ-053, OQ-080, OQ-102,
an internal role-audit report (not exported).

## ADR-146: Post-migration backup hardening and the bot container-side pull pipeline

**Date:** 2026-05-10
**Status:** accepted

**Context:**

Opus audited the ADR-145 migration in Session 307 and found that, while the
cutover itself was clean (counts and `quick_check` matched, no split-brain,
dashboard `data_source=the bot container` correct), the migration left two HIGH and
several lower-severity gaps:

1. The VPS-pull backup default still listed `maker_recorder.db` and
   `wallet_observer.db`. After cutover those VPS files are frozen and the
   backup wastes bandwidth and disk on stale data while pretending to be
   protective.
2. The new authoritative copies of `maker_recorder.db` and
   `wallet_observer.db` on the bot container had no SQLite-consistent backup pipeline.
   Their only protection was the daily LXC `vzdump` snapshot
   (`maxfiles 3`), which is a live-file snapshot and not a `.backup`-API
   call. The rolling VPS-pull archives still on bulk storage only contained the
   frozen-at-cutover bytes.
3. The ADR-144 retention policy of "14 hot + daily/weekly rollups" was not
   actually implemented; `vps_pull_backup.py` does a chronological prune to
   the last 14 runs.
4. The dashboard's the bot container-local-vs-VPS fallback resolved silently if the
   local DB was missing while the unit was active — a future misconfig
   would not alert.
5. `bot_e_recorder_vps_canary.db` (27.6 GB on a 75 G disk) remained the
   biggest unresolved disk risk and had no design doc capturing the
   options.
6. The preserved legacy `wallet_observer_legacy_observed_trades.db` had no
   disposition plan.

**Decision:**

1. **VPS-pull defaults.** Drop `maker_recorder.db` and `wallet_observer.db`,
   and the `maker_flow_replay/` and `wallet_observer/` reports, from the
   `vps_pull_backup.py` defaults and the deployed
   `longshot-vps-pull-backup.service`. The pull pipeline is for
   write-active VPS state only.
2. **the bot container-side pull pipeline.** Add `scripts/bot-host_pull_backup.py` plus
   `longshot-the bot container-pull-backup.{service,timer}` (daily). The script runs on
   the the homelab hypervisor, uses `pct exec` and `pct pull` to take a SQLite
   `.backup`-consistent snapshot inside the bot container, copies it out, and verifies
   counts + `PRAGMA quick_check` + SHA256 + `zstd -t` exactly like the VPS
   pipeline. Output: `<bulk-storage>/ bot container/<run>/` with
   `--keep-runs 14`.
3. **One-off retired-snapshot archive.** Capture the frozen VPS copies of
   `maker_recorder.db` and `wallet_observer.db` once into
   `<bulk-storage>/` with a manifest. After
   archive verifies, delete the frozen copies from the VPS data dir to
   reclaim ~2 GB and prevent operator confusion about the source of truth.
4. **Retention reconcile.** Update the role-audit doc to describe the
   actual rolling-14-runs behaviour rather than the unimplemented
   "14 hot + daily/weekly rollups" prose. Tiered retention is deferred
   until a concrete need emerges.
5. **Dashboard guard.** `query_bot_h` and `query_wallet_observer` now emit
   `data_source_warning` when a the bot container unit is locally `active` but the
   local DB is missing.
6. **Bot E recorder canary.** Capture the rollover/sharding/feed-move
   options as a design doc. No implementation authorized — the design's
   recommended sequence (one-off maintenance backup, feature-flagged
   rollover, supervised first rollover) is operator-approved one step at a
   time.
7. **Legacy wallet DB.** Default disposition: keep until 2026-08-10, then
   operator reviews. No automatic cleanup. No in-place mutation; if the
   older schema is ever needed, an explicit transform script handles it.

**Verification:**

- `pytest tests/dashboard` includes new tests asserting the bot container-source
  preference and the missing-local-DB warning for both Bot H and Wallet
  Observer; existing VPS-fallback tests still pass.
- `longshot-vps-pull-backup.service` next run on the the homelab hypervisor backs up
  only `bot_g_vps_main.db` and `main.db`; manifest counts match the running
  VPS DBs.
- `longshot-the bot container-pull-backup.service` first run captures
  `maker_recorder.db` and `wallet_observer.db` from the bot container into
  `<bulk-storage>/ bot container/<run>/` with `quick_check=ok` for both.
- `<bulk-storage>/` contains the final
  frozen-state archive plus manifest before VPS deletion.

**Consequences:**

- Backup priority is now correctly inverted: the bot container authoritative copies are
  protected daily, VPS keeps protecting only its remaining live state DBs.
- VPS root drops from `58%` used to roughly `55%` after the ~2 GB reclaim,
  buying a few weeks of headroom on the way to the `bot_e_recorder` canary
  decision.
- The dashboard now fails loud (warning string in payload) instead of
  silently falling back if the the bot container local DB ever goes missing.
- OQ-102 tracks remaining open items: the `bot_e_recorder_vps_canary.db`
  decision, dashboard disk thresholds, the wallet redemption timer, and
  the remaining non-latency report moves.

**Rollback:**

This ADR is additive on the dashboard and backup planes:

- Re-add the dropped DBs/reports to `longshot-vps-pull-backup.service` if a
  reason emerges.
- Stop and disable `longshot-the bot container-pull-backup.timer`; the daily the homelab hypervisor
  `vzdump` snapshot remains a safety net.
- Restore the deleted frozen VPS DBs from
  `<bulk-storage>/` if needed (they will be
  identical to the cutover snapshots in
  `20260510T085720Z-final-move/`).

**Cross-refs:** ADR-124, ADR-134, ADR-137, ADR-143, ADR-144, ADR-145,
OQ-053, OQ-080, OQ-100, OQ-102,
`docs/bot-e-recorder-vps-canary-rollover-design-2026-05-10.md`,
an internal role-audit report (not exported).

## ADR-147: Move Bot D live probe from fixed five-share sizing to an evidence-gated ladder

**Date:** 2026-05-10
**Status:** accepted

**Context:**

the operator approved rolling out the recommendation from
`docs/reports/bot-d-live-sizing-analysis-2026-05-10.md`. The read-only the bot container
snapshot at `2026-05-10T13:13:28Z` found `35` closed `bot_d_live_probe`
weather lots and `8` open lots. The fixed `5`-share live sample was profitable
(`+$13.3067` on `$109.5201` cost, `+12.15% ROI`), but the realised edge was
not evenly distributed:

- `>=50c` entries: `28` closed, `23` wins, `+10.23% ROI`.
- `<10c` entries: `4` closed, `1` win, `+349.00% ROI`.
- `20-50c` entries: `3` closed, `1` win, `-17.08% ROI`.
- NOAA NBM and multi-model were positive; GribStream-primary was negative.
- Tier `B` carried the edge; Tier `C`, Seattle, and Denver were negative.

A blind "lower price means bigger size" rule would scale weak cheap Seattle /
Tier `C` losers. A gated ladder scales only the slices that currently carry
the live edge.

**Decision:**

1. Add `BOT_D_LIVE_SIZING_MODE=evidence_gated` for the live probe. The old
   fixed-share path remains available as `fixed`.
2. Keep `BOT_D_LIVE_FIXED_SHARES=5` as the fallback size.
3. In evidence-gated live mode, scale only entries where:
   - setup tier is `B`,
   - forecast source is `noaa_nbm` or `multi_model`,
   - city is not Seattle or Denver.
4. Approved ladder:
   - `<10c`: `30` shares, with enough shares to clear the live minimum
     notional if the price is very low, capped by max dynamic shares.
   - `10-20c`: `20` shares.
   - `20-50c`: `5` shares.
   - `>=50c`: `10` shares.
5. Set `BOT_D_LIVE_MAX_DYNAMIC_SHARES=40` to bound accidental ultra-cheap
   sizing.
6. Raise `BOT_D_LIVE_MAX_ORDER_USD` from `$5.25` to `$10` so `10` shares at
   `80-90c` can actually pass the live notional cap.
7. Keep `BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=100`,
   `BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD=150`, and
   `BOT_D_LIVE_MAX_CONCURRENT_POSITIONS=20` unchanged.

**Verification:**

- Unit tests cover the fixed mode, high-price `10`-share scale-up, cheap
  `30`-share scale-up, and no scale-up for GribStream-primary, Seattle, or
  the `20-50c` band.
- Deployment requires compiling `bots/bot_d_weather`, running the focused
  Bot D executor tests, installing the updated systemd unit on the bot container, and
  restarting only `polymarket-bot-d-live.service`.

**Consequences:**

- Bot D live risk increases per selected entry, but daily gross and open
  exposure caps remain unchanged, so the total daily envelope does not expand.
- The live probe collects better transfer data on whether low-price winners
  and high-probability NO trades should carry more capital.
- Tier `C`, Seattle, Denver, GribStream-primary, and `20-50c` entries remain
  small until their realised slices improve.

**Rollback:**

Set `BOT_D_LIVE_SIZING_MODE=fixed` and `BOT_D_LIVE_MAX_ORDER_USD=5.25`, then
restart `polymarket-bot-d-live.service`. No DB migration is involved.

**Cross-refs:** ADR-084, ADR-087, ADR-103, ADR-142, OQ-067,
`docs/reports/bot-d-live-sizing-analysis-2026-05-10.md`.

## ADR-148: Add Bot D cheap-YES collection lane and remove internal live min-notional gate

**Date:** 2026-05-10
**Status:** accepted

**Context:**

After ADR-147, Bot D live was healthy but placed no new orders. A read-only
post-rollout check found `58` live entry attempts and no cap pressure. The
main recurring live-below-min candidate was a Seattle cheap YES around
`4.2-4.3c`, forecast source `noaa_nbm`, with `api_agreement_count=2`. ADR-147
intentionally did not scale Seattle or Tier `C`, so the order stayed at
`5` shares and was blocked by `BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=$1.00`.

the operator explicitly approved buying that Seattle-style cheap YES and asked to
remove the internal `$1` minimum to collect more live data.

**Decision:**

1. Add a cheap-YES collection lane inside `BOT_D_LIVE_SIZING_MODE=evidence_gated`.
2. Any live candidate with:
   - side `BUY_YES`,
   - entry price `<10c`,
   - forecast source `noaa_nbm` or `multi_model`,
   - `api_agreement_count >= 2`,
   receives at least `20` shares even if it is Seattle or Tier `C`.
   If `20` shares would be below the CLOB's `$1` marketable-BUY floor, size is
   lifted to the smallest share count that clears `$1`, capped by
   `BOT_D_LIVE_MAX_DYNAMIC_SHARES=40`.
3. Keep the stronger ADR-147 ladder unchanged for Tier `B` high-quality
   entries (`<10c=30`, `10-20c=20`, `20-50c=5`, `>=50c=10`).
4. Set `BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=0` in the live unit so the local
   guard does not hide cheap YES candidates. Cheap YES sizing still lifts to
   the CLOB `$1` marketable-BUY floor when possible.
5. Keep `BOT_D_LIVE_MAX_ORDER_USD=10`, daily gross `$100`, open exposure
   `$150`, concurrent positions `20`, and max dynamic shares `40` unchanged.

**Verification:**

- Added a regression test for the Seattle-style cheap YES case:
  NOAA NBM, `BUY_YES`, price around `4.3c`, two-source agreement, and
  automatic sizing to `23.26` shares / `$1.00`.
- Local `tests/bot_d_weather` passed (`121 passed`).

**Consequences:**

- Bot D should now attempt cheap YES collection trades that were previously
  blocked locally and should avoid predictable exchange rejects below `$1`.
- Expected single-order notional on the observed Seattle pattern is roughly
  `$1.00`, so the risk increase is small, but the hit rate of this lane is
  unproven and must be reviewed separately.
- This deliberately trades more often for data collection, not because the
  Seattle/Tier `C` slice has already proven profitable.

**Rollback:**

Set `BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=1.00` and remove or disable the
cheap-YES collection branch, then restart `polymarket-bot-d-live.service`.

**Cross-refs:** ADR-141, ADR-147, OQ-067.

## ADR-149: Retune Bot G Prime Live to $1 6.5c-8c ETH/SOL high-tail probe

**Date:** 2026-05-10
**Status:** accepted

**Context:**

the operator approved the recommendation from
`docs/reports/bot-g-paper-live-reconciliation-and-live-adjustment-2026-05-10.md`.
The read-only reconciliation found that the bot container dashboard data lagged the latest
VPS ledger (`127` `bot_g_prime` orders on the bot container versus `158` in the latest
the homelab hypervisor VPS backup), so the bot container had to be backfilled before changing the live
posture.

The fresher VPS ledger changed the read from "paper is only noise" to "one
small high-tail paper slice deserves a controlled live probe":

- `bot_g_prime` paper: `157` resolved / `13` wins / `+$277.01` / `+48.0%`
  ROI, but only `+6.5%` ROI after removing the two largest wins.
- `bot_g_prime_live`: `68` resolved / `1` win / `-$88.73` / `-81.6%` ROI;
  ex-largest and ex-largest-two both `-100%`.
- `5.5c-6.5c` paper is negative (`38` resolved / `1` win / `-62.8%` ROI), so
  a broad `4c-8c` live expansion would add a bad band.
- `6.5c-8c` paper is the only price band that survives top-two trimming:
  `36` resolved / `7` wins / `+$182.30` / `+134.3%` ROI / `+39.3%`
  ex-top-two.
- BTC is not live-worthwhile: latest live BTC is `34` resolved / `0` wins /
  `-100%`.
- Best labelled high-tail paper slice is ETH NO: `9` resolved / `3` wins /
  `+345.5%` ROI / `+9.4%` ex-top-two.

**Decision:**

1. Backfill the bot container Bot G rows from the latest the homelab hypervisor VPS backup before using
   the dashboard as the Bot G decision surface.
2. Replace the current `bot_g_prime_live` `$1`, `3.5c-5.5c`,
   BTC/ETH/SOL live probe with a narrower high-tail live probe:
   - `BOT_G_FIXED_TRADE_USD=1`.
   - `BOT_G_MIN_ENTRY_PRICE=0.065`.
   - `BOT_G_MAX_ENTRY_PRICE=0.08`.
   - `BOT_G_PRIME_ENTRY_SECONDS=45`.
   - `BOT_G_ENTRY_SECONDS_BEFORE_RES=45`.
   - `BOT_G_ALLOWED_SYMBOLS=ETH,SOL`.
3. Keep existing live risk caps unchanged:
   - `$200` live wallet reference.
   - `$100` live daily gross notional cap.
   - `20` live daily entries.
   - `10` max concurrent live positions.
   - `5s` fresh pre-submit clock guard.
4. Add a paper-only high-tail investigation lane,
   `bot_g_prime_high_tail`, with `$1`, `6.5c-8c`, `45s`, and
   BTC/ETH/SOL/XRP/DOGE. This keeps XRP/DOGE paper-only while measuring
   whether ETH/SOL remain better than BTC in the high-tail slice.
5. Keep the broader `bot_g_prime` `4c-8c` paper lane running.
6. Do not add XRP or DOGE to live.
7. Do not scale Bot G above `$1` per entry under this ADR.

**Implementation guard:**

`bot_g_prime_live` runtime validation must accept only either:

- the legacy ADR-136 `3.5c-5.5c` profile, retained for rollback, or
- the ADR-149 high-tail profile: `6.5c-8c`, `<=45s`, ETH/SOL only, and
  `<= $1` fixed entries.

Any other Bot G live price/symbol/window drift must fail startup validation.

**Consequences:**

- Live Bot G continues collecting real execution data, but in the only paper
  band that currently survives a top-two-win trim.
- BTC is removed from live, reducing exposure to the worst live symbol.
- XRP/DOGE remain paper-only research symbols.
- The new paper high-tail lane gives a clean comparator for the live profile
  and a broader symbol monitor without changing live eligibility.
- ADR-135's no-scale diagnosis remains active. This ADR authorizes only a
  minimum-size data probe, not promotion.

**Rollback:**

Set `bot_g_prime_live` back to the ADR-136 profile (`3.5c-5.5c`, `60s`,
BTC/ETH/SOL, `$1`) or stop `polymarket-bot-g-prime-live.service`. Disable
`polymarket-bot-g-prime-high-tail.service` to stop the paper investigation
lane. No DB migration is required to roll back runtime parameters.

**Cross-refs:** ADR-135, ADR-136, ADR-140, OQ-063, OQ-080,
`docs/reports/bot-g-paper-live-reconciliation-and-live-adjustment-2026-05-10.md`.

## ADR-150: Archive Bot G live dashboard history at the ADR-149 epoch boundary

**Date:** 2026-05-10
**Status:** accepted

**Context:**

ADR-149 changed Bot G Prime Live from the legacy `$1`, `3.5c-5.5c`,
BTC/ETH/SOL probe into a materially different `$1`, `6.5c-8c`, `45s`,
ETH/SOL-only high-tail probe. Showing lifetime `bot_g_prime_live` losses as
the headline dashboard metric would obscure whether the new profile is
working. Deleting or rewriting the old trade rows would break audit,
reconciliation, and research history.

At the ADR-149 service restart, the VPS live ledger had no open
`bot_g_prime_live` orders or positions, making a clean dashboard epoch split
safe.

**Decision:**

1. Keep all raw `orders`, `trades`, `positions`, and `events` rows unchanged.
2. Define the current Bot G live dashboard epoch as:
   - ID: `bot_g_prime_live_adr149_2026_05_10`.
   - Start: `2026-05-10T16:28:10+00:00`.
   - Profile: `$1`, `6.5c-8c`, `45s`, ETH/SOL.
3. Dashboard headline metrics for `bot_g_prime_live` must use only rows at or
   after that epoch start.
4. Pre-epoch live rows remain visible as archived legacy history, not as the
   current strategy headline.
5. The split is a read-model/dashboard accounting boundary only. It does not
   create a new live bot id, change wallet accounting, change CLOB behavior,
   change caps, or mutate historical rows.

**Verification:**

After deployment, the bot container `/api/bot-g` reported:

- current live epoch `bot_g_prime_live_adr149_2026_05_10`;
- current live P&L `$0.00`;
- current live orders `0`;
- current live fills `0`;
- archived legacy live P&L `-$99.91` across `73` old live orders.

**Consequences:**

- the operator can now read the dashboard as "is the ADR-149 high-tail probe working
  from here?" without legacy losses drowning the answer.
- Lifetime history remains available for audit and research.
- Any future material Bot G live retune should create a new dashboard epoch
  rather than resetting or deleting historical rows.

**Rollback:**

Remove the Bot G live epoch override from the dashboard/VPS node-status read
model. No database migration is involved.

**Cross-refs:** ADR-135, ADR-149, OQ-063.

---

## ADR-151: Wallet-tag sports/esports feature filter — lift near-resolution kill-list line for wallet-quality signal only, paper-only

**Date:** 2026-05-10
**Status:** accepted

**Context:**

The wallet-tag forward validation (ADR-137, 7-day window) found that the
low-bot-score cohort (`botScore < 30`, 60 wallets) fails the forward gate
when taken as a whole (+0.9pp edge, 95% CI includes negative). However, a
subset of 7 wallets with forward edge >= +10pp passes decisively:

| Cohort | n | Hit | Implied | Edge | 95% CI ROI | Verdict |
|---|---|---|---|---|---|---|
| All 14 wallets with >=5 closed trades | 588 | 66.7% | 65.7% | +0.9pp | (-43.3%, +5.4%) | FAIL |
| Top 7 wallets (edge >= +10pp) | 147 | 72.1% | 54.8% | **+17.3pp** | **(+24.2%, +65.7%)** | **PASS** |
| Top 7 × esports | 42 | 85.7% | 60.0% | **+25.7pp** | **(+39.2%, +103.6%)** | **PASS** |
| Top 7 × soccer | 97 | 64.9% | 50.0% | **+14.9pp** | **(+18.2%, +43.4%)** | **PASS** |
| Top 7 × sports mid-range (30-70c) | 86 | 72.1% | 48.9% | **+23.2pp** | **(+36.9%, +121.2%)** | **PASS** |

These 7 wallets trade **same-day sports and esports markets** exclusively.
Their average time-to-resolution is under 24 hours, with the majority
resolving within hours of trade. This is "near-resolution" by any definition.

CLAUDE.md `Out-of-scope` contains: `Near-resolution scalping / HFT
strategies`. The general prohibition stays for crypto (except Bot G's
grandfathered scope), politics, awards, and all other categories.
ADR-133 created a surgical exception for weather temperature-bucket markets.
This ADR is the analogous exception for sports/esports, but scoped even
more narrowly: it is not a general sports near-resolution lift, but a
**wallet-quality feature** that existing bots can use as a candidate filter.

The evidence is that these specific wallets have demonstrated skill in
same-day sports pricing. The edge is not in "being fast" — the observer polls
every 15 minutes. The edge is in **wallet selection**: these wallets
consistently buy mispriced sports tokens at 30-70c implied, and they win at
72% vs 49% implied.

**Decision:**

1. Lift CLAUDE.md "Near-resolution scalping / HFT strategies" entry **for
   sports/esports markets only**, and **only when used as a wallet-quality
   feature filter** (not as a general sports scalping bot), paper-only,
   conditional on:
   1. The wallet list is exactly the 7-wallet PASS cohort identified in
      this ADR, or a future ADR-approved superset.
   2. The feature is implemented as a `wallet_tag_filter` boolean on
      candidate markets, not as a standalone copy-trading bot.
   3. No position is opened solely because a target wallet bought; the
      wallet signal is one input among existing Bot G/Bot D filters.
   4. Price band is restricted to 30-70c where the forward edge is
      strongest (+23.2pp, n=86).
   5. Category is restricted to sports/esports (esports + soccer +
      sports_other). Non-sports trades from these wallets are ignored.
2. Authorise build of `wallet_tag_sports_filter` as a feature module in
   `core/wallet_tag_filter.py`, loaded by Bot G paper executor and/or
   Bot D-Spike short TTR executor as an optional candidate gate.
3. Deploy as a paper-only lane. No live promotion without a separate ADR
   after 200 closed trades with 95% CI lower > +10%.
4. Kill conditions:
   - Archive if forward edge on the 7-wallet sports cohort drops below
     +5pp after >=50 closed trades.
   - Archive if top-2 PnL concentration exceeds 40%.
   - Archive if strict settlement gate shows materially different results
     from proxy settlement (tracked in OQ-103).
5. The general "near-resolution scalping" prohibition stays for all other
   categories and for any non-wallet-filter sports strategy.

**Distinguishing characteristics from ADR-133 (weather) and ADR-134 (Bot H):**

- Not a standalone bot. It is a feature/filter input to existing bots.
- Not general sports scalping. The edge is wallet-specific, not category-specific.
- 15-minute observer latency means the edge is not speed-dependent; it is
  information-dependent (these wallets know something about same-day sports
  pricing that the market does not).

**Consequences:**

- A new `wallet_tag_sports_filter` boolean is available in Bot G and Bot D
  paper candidate pipelines.
- The 7-wallet list is hardcoded in the filter module and version-controlled.
- Sports/esports markets that match the filter criteria get a boost in
  candidate scoring, but still must pass all other existing gates (price
  band, liquidity, fee model, etc.).
- If the filter succeeds forward, a future ADR can promote it to live
  trading on Bot G or Bot D.

**Rollback trigger:**

Disable `wallet_tag_sports_filter` in paper config if any of:

- Forward edge on 7-wallet sports cohort drops below +5pp after >=50 closes.
- Top-2 PnL concentration exceeds 40%.
- Strict settlement backfill shows edge < +5pp on >=30 strict-settled trades.
- Any of the 7 wallets is flagged by PolyVerify as `likely_automated=true`
  in a future scrape (their current botScore is 14-24, well below 30).

**Cross-refs:** ADR-133, ADR-137, ADR-149, OQ-103,
`docs/reports/wallet-tag-edge-finding-2026-05-08.md`.

---

## ADR-152: Lower Bot G Prime Live min-entry guard from 6.5c to 6c

**Date:** 2026-05-10
**Status:** accepted

**Context:**

ADR-149 set the Bot G Prime Live guard to `6.5c-8c` based on the
`docs/reports/bot-g-paper-live-reconciliation-and-live-adjustment-2026-05-10.md`
analysis. The report found `6.5c-8c` was the only paper band that survived
top-two trimming (+39.3% ex-top-two). However, the live probe with
`min_price=0.065` produced zero trades in the first 5 hours of operation
because no candidate in the final 45s window had a price at or above 6.5c.

The paper DB price distribution showed 40 historical BUY trades at 0.06
and 20 at 0.08. Today the paper bot placed 6 trades at 0.06 and 3 at 0.08,
while the live probe (min=0.065) placed zero. The 0.06 price is the
second-most-common historical entry and sits within the evidence-backed
band, not the toxic 4c-5c zone that produced -80% live ROI.

**Decision:**

Lower the `bot_g_prime_live` minimum entry price guard from `0.065` to
`0.06` in `bots/bot_g_longshot/config.py`. All other ADR-149 parameters
remain unchanged:

- `max_price=0.08`
- `entry_seconds=45`
- `symbols=ETH,SOL`
- `trade_size=$1`

**Rationale:**

1. 0.06 is within the paper evidence band (40 historical trades) and
   produced 6 paper entries today.
2. 0.065 is too selective -- it excludes the 0.06 trades that are part of
   the positive paper sample.
3. 0.04 would re-introduce the 4c-5c band that was decisively negative in
   live (-59% to -100% across sub-bands).
4. The change is the smallest possible delta to increase throughput
   without dragging the live probe into a proven-losing band.

**Consequences:**

- Expected throughput increases from ~0/day to potentially 1-3/day based
  on paper shadow behavior.
- The 6c-7c sub-band is untested in live; it may perform worse than the
  6.5c-8c sub-band.
- If live results at 6c-8c are still negative after 20 additional closed
  positions, the probe should be halted per ADR-149 kill criteria.

**Rollback:**

Revert `bots/bot_g_longshot/config.py` guard back to `0.065` and restart
`polymarket-bot-g-prime-live.service`.

**Cross-refs:** ADR-149,
`docs/reports/bot-g-paper-live-reconciliation-and-live-adjustment-2026-05-10.md`.

---

## ADR-153: Bot K — Sports Taker (market-open) paper lane

**Date:** 2026-05-11
**Status:** accepted

**Context:**

The Becker public dataset replay (`scripts/research/becker_sports_taker_replay.py`)
validated a market-open taker edge on sports markets in the 10-20c band. On
1,245 resolved trades (first on-chain fill per market, fixed-$5 normalization):
- Win rate: 81.7%
- Net ROI: +506%
- Every sub-category and every league segment positive.
- Weakest segment: esports (+357% on 114 trades, 66.7% WR).

The operator explicitly approved building a paper bot for this edge and named
it Bot K. This is a new strategy family (`market_open_taker`) — distinct
from Bot J's `wallet_filter` near-resolution strategy.

**Decision:**

Build `bots/bot_k_sports_taker/` — a paper-only bot that:
1. Polls `data/maker_recorder.db` (Bot H recorder) every 60s.
2. Scans `markets` for sports category with `initial_yes_price` in [0.10, 0.20].
3. Looks up the first `best_bid_ask` tick within 5 minutes of `discovered_at_ms`.
4. Records a paper YES buy at `ask + 0.01` (one tick above best ask).
5. Fixed $5 notional per trade, 10 max daily entries, 20 max concurrent.
6. 5-minute cooldown per `condition_id` to prevent duplicate entries.
7. Records Order, Trade, Position in the main bot DB.
8. `PAPER_ONLY = True`; live mode forbidden without a new ADR.

Systemd unit: `polymarket-bot-k-sports-taker-paper.service`.
Registry entry added to `core/bot_registry.py`.

**Rationale:**

1. The Becker replay is the largest resolved-sample validation in the repo
   (1,245 trades, 19.5k resolved sports markets).
2. The first-fill proxy has survivorship bias (markets with zero on-chain
   trades excluded), but the cross-segment consistency suggests a real signal.
3. Paper-only deployment lets us collect forward evidence on actual Bot H
   recorder markets as they resolve, closing the loop on the Becker proxy.
4. No CLOB client, no wallet keys, no live orders — safe to deploy
   immediately on the bot container.

**Consequences:**

- Adds a third active paper lane alongside Bot J (wallet filter) and Bot D
  (weather fade).
- Daily cap of 10 entries limits DB growth even if sports market discovery
  spikes.
- The esports segment is the weakest (+357% but 66.7% WR vs 81.7% overall).
  Future tuning may consider esports-specific filters.

**Rollback:**

Stop `polymarket-bot-k-sports-taker-paper.service` and set registry status
from `paper_tuning` to `archived`.

**Cross-refs:** ADR-134 (Bot H Maker V2 recorder), ADR-151 (Bot J wallet filter),
`docs/reports/becker-sports-taker-replay-2026-05-11.md`.

---

## ADR-154: Bot D live order hygiene — block invalid forecast values and exchange-subfloor orders

**Date:** 2026-05-11
**Status:** accepted

**Context:**

Bot D live telemetry after the Phase B city/source expansion showed repeated
failed CLOB entry attempts for low-price weather markets. The failures were
not cap breaches; they were exchange rejections such as marketable BUY notional
below `$1.00`. At least one rejected lane carried `forecast_mean_f=NaN` from a
fallback source snapshot. ADR-148 intentionally set
`BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD=0` so the cheap-YES collection lane could
collect tiny live evidence, but the exchange still enforces a marketable-BUY
floor.

**Decision:**

1. Bot D entry placement now rejects non-finite numeric inputs before sizing:
   probabilities, edge values, forecast mean/std, market price, API agreement
   gap, and size multiplier.
2. Bot D live BUY placement now refuses orders below the observed `$1.00`
   marketable-BUY notional floor even when the local operator min-notional env
   is `0`.
3. ADR-148's cheap-YES collection lane remains valid: qualifying cheap YES
   trades (`BUY_YES`, `<10c`, `noaa_nbm`/`multi_model`,
   `api_agreement_count>=2`) still auto-lift to the `$1.00` floor when the
   dynamic-share cap allows it.
4. Weak low-price slices that do not qualify for the cheap-YES collection lane
   are blocked instead of being submitted and rejected by CLOB.
5. Dashboard Bot D live caps are read from the live systemd unit environment
   rather than dashboard-process defaults, so the UI reflects the actual live
   risk packet.

**Rationale:**

This is a hygiene change, not a new edge. It reduces noisy failed order
attempts, prevents NaN data from touching the live placement path, and keeps
the observed exchange floor explicit in code while preserving the approved
cheap-YES evidence lane.

**Consequences:**

- Some sub-dollar GribStream-primary or otherwise weak low-price candidates
  will be skipped locally with `live_below_exchange_min_notional`.
- The live bot should produce fewer `invalid amount for a marketable BUY`
  exchange errors.
- The dashboard should no longer show stale Bot D live max-position caps when
  the live service is configured differently from the dashboard service.

**Rollback:**

Do not roll back the finite-number guard. If the exchange min-notional behavior
changes, lower `EXCHANGE_MARKETABLE_BUY_MIN_NOTIONAL_USD` in
`bots/bot_d_weather/executor.py` after confirming with live CLOB behavior.

**Cross-refs:** ADR-147, ADR-148, OQ-067, OQ-075,
`docs/phased-audit-rollout-2026-05-10.md`.

---

## ADR-155: VPS-hosted live bots get a local watchdog scope

**Date:** 2026-05-12
**Status:** accepted

**Context:**

Kimi K2.6's 2026-05-10 code audit found that the bot container correctly excludes
VPS-hosted bots from its local watchdog checks, but no equivalent VPS watchdog
scope existed for `bot_g_prime_live`. That left two gaps: aggregate live
exposure checks did not include the VPS live Bot G lane on the host that can
see its DB, and a kill-switch on the bot container could not cancel VPS-hosted open
orders.

The operator confirmed Bot G live remains the `$1`, `6c-8c`, `45s`,
ETH/SOL high-tail data probe.

**Decision:**

1. Keep the bot container watchdog scope local to the bot container-hosted bots.
2. Add an explicit `LONGSHOT_WATCHDOG_HOST_ROLE=vps` mode so the same watchdog
   code can run on the VPS and include VPS-hosted bots such as
   `bot_g_prime_live` in live-cap and cancel coverage.
3. Add `systemd/polymarket-watchdog-vps.service` as the VPS-local watchdog
   unit template, using the VPS Bot G DB and keystore/passphrase paths.
4. Keep `bot_g_prime_live` at `$1`, `6c-8c`, `45s`, ETH/SOL. Update active
   systemd/dashboard/Bot G surfaces to match the 6c lower guard.

**Rationale:**

the bot container should not halt or cancel a VPS bot based on the bot container-local network and DB
state. The safer split is host-local watchdog authority: the bot container covers the bot container
bots, and the VPS covers VPS bots using the same halt/cancel machinery.

**Consequences:**

- `polymarket-watchdog-vps.service` was deployed and enabled on
  `vps-host` via the the homelab hypervisor hop on 2026-05-12.
- The repo now has regression tests that assert the bot container excludes
  `bot_g_prime_live`, while VPS role includes it in live-cap coverage.
- No live order placement, wallet transfer, or parameter size increase is
  authorized by this ADR.

**Rollback:**

Disable `polymarket-watchdog-vps.service` and remove
`LONGSHOT_WATCHDOG_HOST_ROLE=vps` from the unit. the bot container watchdog behavior
remains unchanged.

**Cross-refs:** ADR-115, ADR-149, ADR-152, OQ-106,
`docs/reports/kimi-code-audit-2026-05-10.md`.

---

## ADR-156: Bot D blocks high-confidence NO when the forecast mean is inside the YES bucket

**Date:** 2026-05-12
**Status:** accepted

**Context:**

Bot D live bought `NO` at `89.6c` for the NYC May 11 `60-61F` high-temperature
bucket. The trade lost close to the full stake. The entry payload showed the
forecast mean was `60.0F`, inside the bounded YES bucket, while the decision
path treated the YES probability as near-zero and bought the expensive NO.

The operator wants the bot tightened without eliminating useful sub-80c NO
trades or changing the current evidence-gated share sizing.

**Decision:**

1. Keep evidence-gated live share sizing unchanged.
2. Raise the expensive-NO source/distance guard trigger from `60c` to `80c`.
   Sub-80c NO trades remain available under the normal edge rules.
3. Add a strategy-layer and executor-layer block:
   `BUY_NO` is not allowed when the forecast mean is inside a bounded YES
   bucket.
4. Stop intraday METAR/source extrema from hard-zeroing bounded bucket
   probabilities. Hard observed constraints remain available only for
   one-sided threshold markets.

**Rationale:**

Buying a bounded bucket NO above 80c has asymmetric loss: the bot risks nearly
the full order for small upside. If the model's own mean is inside the YES
bucket, the trade should not be treated as a high-confidence fade regardless
of intraday source telemetry.

**Consequences:**

- Bot D will take fewer expensive bounded-bucket NO trades.
- Sub-80c NO trades are not globally capped by this ADR.
- Intraday station/source data remains useful telemetry, but it no longer
  forces bounded bucket probabilities to 0%/100% before settlement-source
  reliability is proven.
- the bot container has the patched code, but `polymarket-bot-d-live.service` needs the
  tmpfs keystore passphrase restored before it can restart.

**Rollback:**

Do not roll back the mean-inside-bucket block without a resolved replay showing
that expensive bounded-bucket NO trades remain profitable after this failure
class. If throughput is too low, lower only
`BOT_D_EXPENSIVE_NO_GUARD_MIN_PRICE` after reviewing live/paper resolved
samples.

**Cross-refs:** ADR-147, ADR-148, ADR-154, OQ-067.

---

## ADR-157: Fleet-cap live/paper filtering uses registry status before env fallbacks

**Date:** 2026-05-12
**Status:** accepted

**Context:**

After the operator restored the the bot container hot-wallet tmpfs passphrase, Bot D live started
cleanly but rejected otherwise valid entries with `fleet_cap_breach`. The
reported live fleet exposure was about `$1005` against a live cap near `$190`,
even though the live probe's actual exposure was far lower.

The root cause was fleet-cap mode filtering. `_bot_is_paper()` could treat
paper or archived bots as live when process-level environment fallbacks such
as `POLYMARKET_ENV=live` or shared `BOT_D_ENV=live` were present. The
mode-filtered snapshot also considered all known bot ids instead of only
fleet-cap member ids, allowing stale archived evidence rows to starve live
capacity.

**Decision:**

1. Use `core.bot_registry.REGISTRY` as the source of truth for paper/live bot
   status before falling back to environment variables.
2. Treat registry status `live` as live, and `archived`, `paper`,
   `paper_tuning`, `paused`, `shadow`, and `sensor` as non-live for
   live-mode fleet caps.
3. Use `cap_member_bot_ids()` for `mode="live"` and `mode="paper"` fleet-cap
   snapshots. Keep combined/all-bot reports broad.

**Rationale:**

Fleet caps are a real-money safety perimeter. They must count the live bots
that can place live orders, not stale paper rows or archived evidence from
retired services. Registry status is the canonical bot identity layer and is
less fragile than shared process environment fallbacks.

**Consequences:**

- Bot D live can trade again without paper Bot D or archived services
  consuming live-probe cap.
- Regression tests now cover live mode ignoring shared `BOT_D_ENV` and
  paper-only exposure.
- After deploy, `bot_d_live_probe` placed live order
  `0xF00D000000000000000000000000000000000003f5afdcf039b26271fd469926` on
  2026-05-12.

**Rollback:**

Do not return to env-first fleet-cap classification. If a bot's status is
wrong, fix the registry entry or add an explicit registry override; live caps
should not depend on broad process env defaults.

**Cross-refs:** ADR-023, ADR-084, ADR-087, ADR-156, OQ-067.

---

## ADR-158: Raise Bot D live capacity and replace expensive-NO distance with tier/edge gate

**Date:** 2026-05-13
**Status:** accepted

**Context:**

Bot D live has enough early realised evidence to keep collecting faster:
the latest snapshot before this change showed `54` closed live groups,
`37` wins, `17` losses, `+$35.39` realised P&L, and about `+20.17%` closed
ROI since activation. Since the May 10 city/sizing rollout, the live probe
showed `17` closed groups, `12` wins, `5` losses, `+$25.25` realised P&L,
and about `+40.28%` ROI.

Two current open/pending markets also highlighted the remaining weak class:
expensive bounded-bucket `BUY_NO` entries around `80c+` where the setup is
only C-tier or the forecast is too close to the YES bucket. Chicago May 13
`58-59F` was entered at `88c` from NOAA NBM with only about `7.7c` net edge,
C-tier classification, and roughly `1F` margin from the bucket. That class
should not consume high per-trade risk unless the model edge is stronger.

the operator explicitly approved raising Bot D live collection limits to `$200` open
exposure and `$150` daily gross while keeping trade sizing unchanged.

**Decision:**

1. Raise Bot D live probe caps:
   - `BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD=200`.
   - `BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=150`.
2. Keep the current evidence-gated sizing ladder unchanged.
3. Keep the expensive-NO guard active at `80c+`, but replace the prior
   volatility-scaled distance requirement with a simpler live rule:
   - require at least `2F` distance from the bounded YES bucket,
   - require existing independent API/source agreement,
   - and for C-tier setups require at least `12c` absolute net edge.

**Rationale:**

The cap increase buys more live evidence without increasing per-order size.
The revised expensive-NO rule targets the specific weak pattern from the
recent losses while avoiding a blanket cap on all expensive NO trades. Strong
B-tier/A-tier trades and cheaper trades remain available; weak C-tier
high-priced NO trades need a larger edge before risking nearly the full
order.

**Consequences:**

- Bot D can carry more simultaneous live evidence before hitting capacity.
- The daily collection ceiling rises, so operator review should use daily
  gross plus realised P&L together rather than assuming fewer trades.
- High-priced C-tier NO trades with weak edge are blocked with
  `expensive_no_guard:tier_c_edge`.
- This does not enable NWS fallback live entries, alter verified-city rules,
  increase the `$10` max order notional, or change the evidence-gated share
  ladder.

**Rollback:**

If realised ROI deteriorates after at least `20` new resolved live groups
post-ADR-158, return the caps to `$150` exposure / `$100` daily gross and
review the expensive-NO reject log before loosening the guard. Do not scale
per-trade shares further until the post-change source/tier slice remains
positive after largest-win exclusion.

**Cross-refs:** ADR-147, ADR-148, ADR-154, ADR-156, OQ-067.

---

## ADR-159: Add Bot L as a paper-only BTC 5m complete-set convergence lane

**Date:** 2026-05-13
**Status:** accepted

**Context:**

the operator asked why the public `xuanxuan008` wallet appears to earn large profits
on BTC 5-minute Polymarket markets while Bot G live does not. Public
Polymarket Data API activity showed the wallet buying both Up and Down inside
the same BTC 5-minute markets and using MERGE events, which is structurally
different from Bot G's one-sided cheap-tail holder model.

The shared crypto recorder already captures the BTC 5-minute tape needed to
test this mechanism. A first-pass recorder probe found repeated paired
top-of-book moments where YES+NO ask summed below parity or YES+NO bid summed
above parity.

**Decision:**

1. Do not change live Bot G in response to the tweet.
2. Add a separate paper-only Bot L lane for BTC 5-minute complete-set
   convergence research.
3. Bot L reads only the shared crypto recorder DB and writes simulated
   opportunities to `bot_l_complete_set_paper.db`.
4. Bot L has no CLOB client, no wallet keys, no live order path, and no fleet
   cap inclusion.
5. The initial paper model records:
   - BUY complete-set signals when YES ask + NO ask is below the raw gate,
   - SELL complete-set signals when YES bid + NO bid is above the raw gate,
   - executable flags after a configurable round-trip slippage haircut.

**Rationale:**

Complete-set convergence has different mechanics, risk, and execution
requirements from Bot G. Keeping it separate prevents a promising but
unproven execution idea from contaminating the live Bot G decision surface.
The paper lane can measure opportunity frequency, haircut survival, and
forward robustness before any live proposal.

**Consequences:**

- VPS runs `polymarket-bot-l-complete-set-paper-vps.timer` every minute.
- Bot L appears in registry/status metadata as `bot_l_complete_set`.
- The first 24h backfill wrote `154` signals across `30` BTC 5-minute
  markets; `45` survived a 1c round-trip haircut.
- No real-money settings, wallet paths, CLOB auth, or Bot G live parameters
  changed.

**Rollback:**

Disable `polymarket-bot-l-complete-set-paper-vps.timer` and remove
`data/bot_l_complete_set_paper.db`. Because the lane is paper-only and writes
to an isolated DB, rollback does not affect Bot G, Bot D, the recorder, or
wallet state.

**Cross-refs:** OQ-111, ADR-149, ADR-152,
`docs/reports/xuanxuan-btc-5m-strategy-analysis-2026-05-13.md`.

---

## ADR-160: Add Bot D Station Lock as a paper-only late station-certainty lane

**Date:** 2026-05-13
**Status:** accepted

**Context:**

Bot D live has shown that near-resolution weather markets can move sharply
once exact station evidence becomes visible, especially when retail is still
anchored to model forecasts or stale display data. the operator asked for a separate
paper lane to test whether hard station-day certainty can be harvested before
Polymarket fully reprices, without changing the live Bot D probe.

The relevant edge is settlement-oracle certainty, not better medium-range
forecasting: use the resolving station observation, classify whether the
bucket outcome is already known or locked after local day completion, then
measure whether the market price still offers enough edge.

**Decision:**

1. Add `bot_d_station_lock` as a Bot D umbrella lane with status
   `paper_tuning`.
2. Run it as `polymarket-bot-d-station-lock.service` on the bot container.
3. Keep it paper-only: no CLOB client, no wallet key, no live order path, no
   live Bot D caps/sizing/city changes, and no fleet cap inclusion.
4. Record synthetic paper evidence as Event rows:
   `bot_d.station_lock.candidate`, `bot_d.station_lock.entry_attempt`,
   `bot_d.station_lock.paper_fill`, and `bot_d.station_lock.resolution`.
5. Fail closed on WU station mutation risk and rounding disagreement.
6. Require forward evidence in OQ-112 before any live proposal.

**Rationale:**

Station Lock tests a different mechanism from the main Weather Fade live
probe. Keeping it as a separate paper lane prevents settlement-oracle
experiments from contaminating the live Bot D decision path while still
collecting actionable evidence on candidate frequency, correctness, lag, and
paper P&L.

**Consequences:**

- the bot container runs a new paper-only service every scan interval.
- The lane writes to the shared Event table under bot id
  `bot_d_station_lock`; it does not create real Orders or Positions.
- The service command forces `BOT_D_ENV=paper` and `POLYMARKET_ENV=paper` at
  process launch so a global live `.env` cannot promote the lane.
- Existing `bot_d_live_probe` and `bot_d` services remain separate.
- The first deployed scan on 2026-05-13 saw `6` weather candidates and wrote
  `0` entries / `6` skips.

**Rollback:**

Disable `polymarket-bot-d-station-lock.service`. Because the lane is
paper-only and writes synthetic Event rows, rollback does not touch live Bot D
orders, wallet state, or trading caps.

**Cross-refs:** OQ-112,
`docs/bot-d-late-station-certainty-handoff-2026-05-13.md`.

## ADR-162: Bot D live scale-up + premium-tier NO sizing + distance-gate restore

**Date:** 2026-05-14
**Status:** accepted

**Context:**

Bot D Live Probe is the only consistently positive real-money lane in the
fleet: `54` closed groups, `37W/17L` (`68.5%` WR), `+$35.39` realised
(`+20.17%` ROI lifetime), and `12W/5L` / `+40.28%` ROI on the `17` closes
since the 2026-05-10 city/source rollout. On 2026-05-13, however, two
narrow-bucket `BUY_NO` entries (Chicago 58-59F May 13 and Atlanta 80-81F
May 13) lost the full stake — the structural tail of a NO-side narrow-band
fade where the temperature does land in the 1F bucket and NO redeems at $0.

ADR-158 raised the daily gross / open-exposure caps on 2026-05-13 but did
not change per-entry sizing, so the downside per high-priced NO miss
remained at `~$8-9`. Session 356 also loosened the expensive-NO distance
gate (`4.0F → 2.0F`, std-multiple disabled) and added a tier-C edge gate.
The distance loosening makes A/B-tier high-premium NO entries on narrow
buckets more permissive, which is the same trade class that produced the
2026-05-13 loss day.

Operator approved a combined change: scale the live envelope `2x`, but
**simultaneously** introduce a premium-tier sizing ladder that caps the
per-entry stake on high-priced `BUY_NO` trades, and **restore** the
Session 356 distance gate to its pre-loosening defaults.

**Decision:**

1. Raise Bot D live caps to:
   - `BOT_D_LIVE_WALLET_USD = 400`
   - `BOT_D_BANKROLL_USD = 400`
   - `BOT_D_INITIAL_USD = 400`
   - `BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD = 300`
   - `BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD = 400`
   - `BOT_D_LIVE_MAX_ORDER_USD = 15`
   - `BOT_D_LIVE_MAX_DYNAMIC_SHARES = 60`
   - `BOT_D_LIVE_FIXED_SHARES = 15` (= ladder `<0.60` base tier)
   - `BOT_D_LIVE_MAX_CONCURRENT_POSITIONS = 50` (unchanged)
2. Introduce a premium-tier NO sizing ladder driven by limit price on
   `BUY_NO` entries when `BOT_D_LIVE_SIZING_MODE=evidence_gated`:

   | Limit price band | Shares (env var) |
   |---|---:|
   | `< 0.60` | `BOT_D_LIVE_FIXED_SHARES` (`15`) |
   | `[0.60, 0.75)` | `BOT_D_LIVE_NO_SHARES_MID` (`10`) |
   | `[0.75, 0.85)` | `BOT_D_LIVE_NO_SHARES_HIGH` (`6`) |
   | `[0.85, 0.95)` | `BOT_D_LIVE_NO_SHARES_VERY_HIGH` (`3` config, clamped to `5` by exchange floor) |
   | `>= 0.95` | hard skip with reason `no_premium_hard_skip` |

   Implementation:
   - New config knobs `BOT_D_LIVE_NO_SHARES_MID/HIGH/VERY_HIGH` and
     `BOT_D_LIVE_NO_PREMIUM_HARD_SKIP` in `bots/bot_d_weather/config.py`.
   - New static guard `BotDExecutor._no_premium_hard_skip_reason` called
     from `try_enter` after the expensive-NO guard.
   - New `no_ladder` branch in `_live_size_shares` for
     `decision.side == "BUY_NO"` and `evidence_gated` sizing.
   - The exchange-side `MIN_POLYMARKET_SHARES = 5` clamp still applies at
     the end of `_live_size_shares`, so the `VERY_HIGH` tier runtime size
     is `5` until that floor is lowered separately. Config keeps `3` to
     record operator intent.
3. Restore the expensive-NO guard distance gate to its pre-Session-356
   defaults:
   - `BOT_D_EXPENSIVE_NO_MIN_DISTANCE_F = 4.0`
   - `BOT_D_EXPENSIVE_NO_MIN_DISTANCE_STD_MULT = 2.0`

   The Session 356 tier-C edge gate (`BOT_D_EXPENSIVE_NO_TIER_C_MIN_EDGE
   = 0.12`) is retained — it remains useful as a secondary block for
   weak C-tier setups even when the distance gate is restored.
4. Wallet top-up of approximately `$200` from treasury to the hot wallet
   must occur before service restart so the hot wallet has at least `$400`
   funded. This is an operator-only action.

**Rationale:**

Per-entry loss caps are the load-bearing safety net for a NO-side narrow-band
fade: the strategy's structural tail is "the bucket hits" → full stake
loss. Capping the high-premium per-entry stake at roughly `$3-5` instead of
`$8-9` halves the worst-case daily loss when one or two narrow buckets
land. The hard skip at `>= 0.95` removes the worst risk/reward sub-band
entirely (payoff `<= 5c` vs `100%` downside is structurally negative-EV
without a separate edge claim).

The distance-gate restore reverses Session 356's loosening. ADR-158's
tier-C edge gate (kept) protects weak C-tier setups; the restored
distance gate protects A/B-tier setups against the same narrow-bucket
landing risk that produced the 2026-05-13 losses.

The simultaneous scale-up is permissible only because of the ladder. The
two changes go together; the ladder reduces per-entry tail without
reducing trade volume, so the strategy continues to earn under the new
larger envelope.

**Consequences:**

- Bot D live daily turnover capacity doubles (`$150` → `$300`).
- Worst-case per-entry loss in the `0.85-0.95` NO band drops from
  `~$8.50-$9.50` to `~$4.25-$4.75` (subject to the exchange clamp).
- The `>= 0.95` NO band is fully excluded.
- A/B-tier narrow-bucket NO entries near the forecast mean are now blocked
  by the restored distance gate (`max(4.0F, 2*sigma)`).
- Pre-existing tier-C protection from ADR-158 is preserved.
- The two narrow-bucket structural losses observed 2026-05-13 cannot recur
  with the same magnitude even at the new larger envelope.

**Verification:**

- `bots/bot_d_weather/config.py`: added 4 new ladder knobs; restored
  distance-gate defaults.
- `bots/bot_d_weather/executor.py`: new `_no_premium_hard_skip_reason`
  static guard wired into `try_enter` after the expensive-NO guard; new
  `no_ladder` branch in `_live_size_shares`.
- `tests/bot_d_weather/test_executor.py`: 5 new tests covering the four
  ladder bands plus the hard-skip; pre-existing tier-C test adjusted to
  exercise the tier-C edge gate under the restored distance gate
  (`forecast_mean_f` moved from `62.0` to `72.0`).
- Full Bot D test suite: `163 passed` locally (was `130 passed` before
  Session 356; net `+33` includes Codex's prior additions and the new
  ladder tests).
- `systemd/polymarket-bot-d-live.service`: env block updated to the new
  caps + ladder vars + restored distance-gate defaults.

**Rollback:**

Revert `systemd/polymarket-bot-d-live.service` to the ADR-158 envelope
and disable the new ladder knobs in `bots/bot_d_weather/config.py`. Code
in `executor.py` defaults the ladder to a pass-through when knobs are at
exchange-floor values, so a full code revert is not strictly required —
env-only rollback is sufficient and reversible.

**Cross-refs:** ADR-156, ADR-158, OQ-067,
`docs/fleet-review-session-2026-05-14.md`.

## ADR-161: Bot K paper filters to near-term sports markets before live-probe review

**Date:** 2026-05-14
**Status:** accepted

**Context:**

Bot K's Becker replay showed a large historical sports-taker edge, but
OQ-114 records the survivorship-bias caveat and the first forward paper
sample problem: the the bot container lane wrote only `5` paper entries by 2026-05-14,
all far-dated futures. That forward sample cannot answer the near-term live
probe question because settlement will not arrive on an operator-useful
timeline.

The 2026-05-14 faster fleet review lowered evidence gates for tiny live
probe consideration, but not fund-safety gates. For Bot K, the relevant next
evidence is not a larger all-futures sample; it is whether near-term market
open sports entries exist and resolve with acceptable forward behavior.

**Decision:**

Bot K paper now filters recorder-discovered sports markets to
`MAX_TIME_TO_RESOLUTION_HOURS = 168.0` when the recorder provides
`markets.end_date_ts`. Far-dated futures are skipped before first-tick
selection. If `end_date_ts` is absent from a test or legacy recorder schema,
the filter does not block the row.

Implementation:

- `bots/bot_k_sports_taker/config.py` adds
  `MAX_TIME_TO_RESOLUTION_HOURS = 168.0`.
- `bots/bot_k_sports_taker/executor.py` detects the optional
  `end_date_ts` column, normalizes seconds/milliseconds, and filters out
  markets with non-positive or `>168h` time to resolution.
- `tests/test_bot_k_sports_taker.py` covers far-future exclusion.

**Rationale:**

The paper lane needs fast forward closes before any tiny-live proposal. A
near-term time-to-resolution filter is the smallest change that aligns the
paper evidence with OQ-114 without touching wallets, CLOB live order paths,
bankroll, caps, deployed services, or recorder infrastructure.

**Consequences:**

- Bot K will stop sampling long-dated sports futures when deployed.
- The paper sample should resolve quickly enough to support or reject a tiny
  live probe packet.
- The Becker `+506%` replay remains historical context only; it is not a
  forward expectation.
- Any Bot K live probe still requires a separate ADR and explicit the operator
  approval before trading.

**Verification:**

- `.venv/bin/python -m pytest tests/test_bot_k_sports_taker.py tests/test_bot_j_nr_wallet.py tests/test_bot_d_station_lock_report.py -q`
  — `8 passed`.
- Focused Ruff over Bot K/Bot J/Station Lock touched files — clean.

**Rollback:**

Set `MAX_TIME_TO_RESOLUTION_HOURS` high enough to include futures or revert
the Bot K config/executor diff. Paper DB rows already written remain
preserved for audit.

**Cross-refs:** ADR-153, OQ-114.

---

## ADR-163: Adopt fast tiny-live probe doctrine while preserving fund safety

**Date:** 2026-05-14
**Status:** accepted

**Context:**

the operator changed the operating posture after the fleet review returned no
conservative go-live candidates. The existing ADR/OQ stack had become too
slow for the desired learning rate: many lanes were blocked on 30-day paper
windows, large forward samples, strict concentration gates, full resolved ROI
proof, or every open empirical question closing before real-money evidence.

That caution reduced downside, but it also delayed the fastest way to answer
live-only questions: fill quality, slippage, queue position, settlement
transfer, real cap behavior, and whether paper candidates survive actual CLOB
execution.

**Decision:**

Adopt a fast tiny-live probe doctrine:

1. A strategy lane may become a **Live Probe Candidate** before conservative
   full go-live evidence clears if it has plausible edge, asymmetric payoff,
   high learning value, and a tightly capped maximum loss.
2. The following evidence gates may be lowered or waived for a tiny live
   probe:
   - 30-day paper duration.
   - Large forward sample requirements.
   - Fully resolved ROI proof.
   - Strict top-1/top-3 concentration limits.
   - All-symbol/all-city robustness.
   - Every related open question being closed first.
3. The following gates are **not** lowered:
   - Explicit the operator approval before live orders or live-service enablement.
   - Wallet, keystore, passphrase, private-key, treasury, and bankroll
     boundaries.
   - Per-order, daily-gross, open-exposure, and concurrent-position caps.
   - Fleet-cap accounting, watchdog coverage, reconciliation, and kill
     switches.
   - Secret scans and no-secret-in-repo rules.
   - ADR record for any live-probe activation, cap increase, or scale-up.
4. Each tiny live probe packet must state:
   - exact bot id and market universe,
   - entry/exit rules,
   - max order size,
   - daily gross cap,
   - open exposure cap,
   - max concurrent positions,
   - maximum possible loss for the probe window,
   - kill conditions,
   - rollback path,
   - monitoring checks,
   - missing evidence the probe is intended to answer,
   - exact approval wording required from the operator.
5. A tiny live probe is paid research, not production trading. Passing a
   tiny live probe does not imply scaling; scaling needs a later ADR.

**Rationale:**

The project needs faster feedback, but the correct risk to increase is
strategy risk, not fund-control risk. Small capped real-money probes can
answer questions that paper cannot answer, while keeping worst-case loss
known and reversible. This doctrine prevents evidence gates from becoming
indefinite blockers while preserving the safety rails that stop accidental
or uncontrolled losses.

**Consequences:**

- OQs that previously blocked all live activity should be reread as blocking
  scaling unless they describe a fund-safety, wallet, reconciliation, or
  legal/geographic constraint.
- Paper-only ADRs may still stand for current runtime state, but they no
  longer block a separate tiny-live proposal when this ADR's packet
  requirements are met.
- Future fleet reviews should rank **Live Probe Candidates**, not only
  conservative **Go-Live Candidates**.
- High-risk/high-reward lanes can advance faster, but only with explicit
  caps, max-loss math, rollback, and the operator approval.

**Supersedes / amends:**

This ADR partially supersedes the conservative evidence posture in ADR-008,
ADR-045, ADR-069, ADR-073, ADR-080, ADR-082, ADR-123, ADR-125, ADR-133,
ADR-134, ADR-151, ADR-153, ADR-159, ADR-160, ADR-161, and ADR-162 where
those decisions block tiny live probes only because paper evidence is
incomplete. It does not
supersede any wallet, key-management, watchdog, fleet-cap, reconciliation,
secret-handling, VPN/geography, or explicit-approval safety decision.

**Rollback:**

Supersede this ADR if tiny live probes create uncontrolled losses, repeated
rule violations, reconciliation gaps, or operator burden beyond the expected
learning value. Existing live probes continue only under their own ADR caps
and kill switches.

**Cross-refs:** OQ-086, OQ-097, OQ-100, OQ-111, OQ-112, OQ-113, OQ-114.

## ADR-164: Prepare tiny live-probe readiness packets without enabling live trading

**Date:** 2026-05-14
**Status:** accepted

**Context:**

ADR-163 permits faster tiny live probes when the learning value is high and
fund-safety rails stay intact. The first three candidate lanes are:

1. Bot D Station Lock.
2. Bot D-Spike 6-12h.
3. Bot L Complete-Set BUY/MERGE only.

Bot I Persistence is explicitly out of scope for this work because Opus is
handling it separately. None of the three lanes has operator approval to
trade live in this session.

**Decision:**

Prepare repo-local readiness artifacts only:

- Add a shared order-path-neutral readiness layer in `core/tiny_live_probe.py`
  for immutable cap specs, dry-run/live guards, kill-gate evaluation, and
  approval packets.
- Add lane specs for:
  - Bot D Station Lock: hard-lock only, `$5` max order, `$20` daily gross,
    `$25` open exposure, `5` concurrent positions.
  - Bot D-Spike: 6-12h TTR whitelist-only cheap-YES, `$2` max order, `$10`
    daily gross, `$20` open exposure, `10` concurrent positions.
  - Bot L Complete-Set: BUY/MERGE only, `$1` bundle gross, `$10` daily gross,
    `$20` open exposure, `2` concurrent bundles, `$0.25` gas cap, mandatory
    same-asset depth join.
- Keep all readiness checks dry-run and operator-blocked. Readiness code must
  not create a CLOB client, read wallet material, or submit an order.
- Add read-only readiness reporting via `scripts/tiny_live_probe_readiness.py`
  and the read-only report unit
  `systemd/polymarket-tiny-live-probe-readiness.service`.
- Lower existing paper service cap defaults where they were looser than the
  requested tiny-live envelopes so paper collection now mirrors the proposed
  probe risk envelope more closely.

**Rationale:**

This creates the activation packet and testable safety rails while preserving
the highest-risk boundary: live order placement remains impossible from these
new readiness artifacts. A later activation ADR can wire the actual live
executor path only after the operator approves the exact caps and kill switches.

**Consequences:**

- Bot D Station Lock, Bot D-Spike, and Bot L now have exact approval wording,
  max-loss math, rollback paths, and automated dry-run guard checks.
- Bot L explicitly excludes live SELL/SPLIT; only BUY/MERGE is prepared.
- Bot D-Spike paper defaults are stricter (`10` max open, `$20` deployed,
  `$10` daily gross, `5` daily entries) than the previous paper-cap posture.
- No live services were enabled, no deployment was performed, no production
  services were restarted, and no wallet/keystore/passphrase/private-key path
  was touched.

**Verification:**

Run:

```bash
.venv/bin/python -m pytest tests/test_tiny_live_probe_readiness.py tests/test_bot_d_spike.py tests/bot_d_weather/test_station_lock.py tests/test_bot_l_complete_set.py -q
.venv/bin/python -m ruff check core/tiny_live_probe.py bots/bot_d_weather/station_lock.py bots/bot_d_spike/config.py bots/bot_d_spike/executor.py bots/bot_l_complete_set/live_probe.py scripts/tiny_live_probe_readiness.py tests/test_tiny_live_probe_readiness.py
```

**Rollback:**

Remove the readiness specs/report and restore the prior paper service cap
defaults. Since no live service is enabled by this ADR, rollback is repo-only.

**Cross-refs:** ADR-123, ADR-125, ADR-159, ADR-160, ADR-163, OQ-111, OQ-112.

## ADR-165: Operator approves three tiny live probes and dashboard live status

**Date:** 2026-05-14
**Status:** accepted

**Context:**

ADR-164 prepared the readiness packets and exact approval questions for:

1. Bot D Station Lock.
2. Bot D-Spike 6-12h.
3. Bot L Complete-Set BUY/MERGE only.

the operator then approved all three and asked for the dashboard to reflect that the
lanes are now live.

**Decision:**

Accept operator approval for the three tiny live probes and update dashboard
metadata so the active fleet surfaces them as live probes:

- `bot_d_station_lock` becomes `status="live"`,
  `display_name="Weather Station Lock Live Probe (D)"`,
  `include_in_cap=True`, and stays dashboard-visible.
- `bot_d_spike` becomes `status="live"`,
  `display_name="Weather Spike Live Probe (D)"`,
  `include_in_cap=True`, and becomes dashboard-visible.
- `bot_l_complete_set` becomes `status="live"`,
  `display_name="BTC Complete-Set Live Probe (L)"`,
  `include_in_cap=True`, and becomes dashboard-visible.
- The Bot D dashboard detail view now labels D-Spike as live, keeps
  D-Spike-Short as paper, and labels Station Lock as a live probe.

The approved caps remain exactly the ADR-164 packet:

| Lane | Max order/bundle | Daily gross | Open exposure | Concurrent | Kill floor |
|---|---:|---:|---:|---:|---|
| Bot D Station Lock | `$5` | `$20` | `$25` | `5` | any mismatch, `2` hard-lock losses, P&L `<= -$10`, stale station data, live/reconcile anomaly |
| Bot D-Spike 6-12h | `$2` | `$10` | `$20` | `10` | rule violation, `5` consecutive resolved losses, P&L `<= -$8`, CLOB/auth/reconcile fault, Bot D exposure overlap |
| Bot L BUY/MERGE | `$1` | `$10` | `$20` | `2` | unhedged leg `>$2`, net realised `<= -$3` after gas, depth/merge/stuck-inventory/reconcile anomaly |

**Execution boundary in this commit:**

This ADR records approval and dashboard state only. It does not deploy code,
enable a service, restart production, touch wallet/keystore/passphrase/private
key material, transfer funds, or place live orders.

**Rationale:**

The operator explicitly accepted the risk envelope. The dashboard should now
show the lanes in the live-probe group so operating reviews no longer treat
them as only paper candidates. Runtime enablement is still a separate
operational step because it touches production services and, for actual
orders, wallet-funded execution.

**Consequences:**

- Dashboard inventory classifies all three lanes as `Live`.
- Fleet-cap membership includes the three probe bot IDs.
- Existing paper evidence remains useful as the comparison baseline.
- Bot L live scope is still BUY/MERGE only; SELL/SPLIT is not approved.
- Bot I remains out of scope.

**Rollback:**

If the operator reverses approval or a live probe hits a kill switch, set the relevant
registry entry back to `paper_tuning`, remove it from dashboard-visible live
surfaces, keep paper evidence collection running where useful, and log the
rollback in `CHANGELOG.md`, `MEMORY.md`, and the relevant OQ.

**Cross-refs:** ADR-163, ADR-164, OQ-086, OQ-111, OQ-112.

## ADR-166: Add Bot D report-only live-position validation with raw station exit signals

**Date:** 2026-05-14
**Status:** accepted

**Context:**

Bot D live already had partial SELL support: take-profit exits, stale-exit
cancellation, and edge-decay / edge-flip exits use real CLOB SELL orders in
live mode. The gap was defensive open-position validation: raw
settlement-station data could prove or strongly threaten a position after
entry, but that raw data was recorded as telemetry only and was not classified
against each open position.

**Decision:**

Add a Bot D open-position validator that reviews every open Bot D position
during the existing position-review scan and emits `bot_d.position_validation`
events with one of `HOLD`, `WATCH`, `SELL_RECOMMENDED`, or `SELL_NOW`.

The validator uses the current position token book, entry cost,
mark-to-market loss, hours-to-end, current forecast edge when available,
latest `bot_d.source_snapshot` raw station bucket state, and existing pending
SELL orders. It adds configurable stop-loss settings, but the default does
not sell on price alone; it requires invalidating fresh data or edge evidence
for defensive sell recommendations.

**Live-order boundary:**

Report-only mode is the default. Live auto-sell is disabled unless
`BOT_D_POSITION_AUTO_SELL_ENABLED=true` is explicitly set. If enabled later,
it reuses the existing `_exit_position()` live SELL path; there is no second
CLOB sell router.

**Consequences:**

- Bot D now records per-position defensive validation evidence even when the
  market is no longer in the normal entry-decision set.
- Raw station data can classify NO positions as threatened when the station
  metric moves into or locks the YES bucket, and YES positions as invalidated
  when the bucket is already/locked NO.
- Price-only stop loss remains opt-in, preventing panic sells from stale or
  thin marks without source evidence.
- Enabling live auto-sell still requires explicit operator approval, service
  deployment, and runbook/dashboard review.
- Report-only deployment to the bot LXC container is allowed under this ADR; it does not
  authorize validator-driven live auto-sell.
- Auto-sell enablement should be reconsidered only after at least 30
  validation events, including at least 10 `SELL_RECOMMENDED` or `SELL_NOW`
  cases across a full weather week, with positive replay evidence after
  spread/slippage and no false `SELL_NOW` exits on eventual winners.

**Rollback:**

Set `BOT_D_POSITION_VALIDATION_ENABLED=false` to stop reporting. Keep
`BOT_D_POSITION_AUTO_SELL_ENABLED=false` to guarantee no validator-driven live
SELL orders. Existing take-profit and edge-collapse exits are unaffected.

**Cross-refs:** ADR-046, ADR-099, ADR-105, ADR-162, OQ-052, OQ-067.

## ADR-167: Promote Austin KAUS and align Bot D NWS-outlier probe with live edge floor

**Date:** 2026-05-14
**Status:** accepted

**Context:**

Bot D live scans on 2026-05-14 showed no recent new BUY entries because
active weather market supply was thin and one current candidate, Austin
2026-05-15, was dropped by the verified-settlement live lane. The live Gamma
rules for `highest-temperature-in-austin-on-may-15-2026-76-77f` explicitly
state that settlement uses the highest temperature at the Austin-Bergstrom
International Airport Station via Wunderground KAUS:
`https://www.wunderground.com/history/daily/us/tx/austin/KAUS`.

The same no-entry check showed repeated `nws_disagrees` skips. Bot D already
has ADR-107's NWS-outlier probe, which only bypasses the NWS veto when at
least two non-NWS API/model sources agree within 2.0F and the NWS gap is at
most 6.0F. The live entry edge floor is 7%, but the outlier-probe floor was
still 8%, so some otherwise live-shaped 7-8% entries could be blocked even
when the multi-source panel agreed.

**Decision:**

1. Promote Austin to verified live settlement coverage:
   `SettlementSpec("KAUS", 30.1975, -97.6664, "KAUS", verified=True,
   verification_status="verified")`.
2. Set `BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE=0.07` in Bot D live, paper, and
   source-shadow systemd units so the outlier-probe threshold matches the
   live entry floor.
3. Keep the stricter source-agreement requirements unchanged:
   `BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F=2.0`,
   `BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F=6.0`, and at least two agreeing
   non-NWS sources.
4. Keep expensive-NO protections unchanged, including source agreement,
   distance-from-bucket, premium-tier sizing, and the 95c hard skip.

**Consequences:**

- Austin markets can enter the same verified-city live lane as other
  airport-settled US cities once all ordinary Bot D gates pass.
- A candidate blocked only by NWS disagreement can now trade at 7-8% edge
  only if the non-NWS source panel agrees tightly enough to classify NWS as
  the outlier.
- The change should increase live data collection without allowing
  single-source forecasts, NWS fallback entries, or near-bucket expensive NO
  trades.

**Rollback:**

Set Austin back to `verification_status="shadow"` / `verified=False` if a
future market rule changes away from KAUS or Wunderground. Set
`BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE=0.08` in the Bot D units if the 7-8% outlier
lane produces poor realised fills.

**Cross-refs:** ADR-091, ADR-107, ADR-129, ADR-162, OQ-067.

## ADR-168: Keep the bot container root disk for code and config; bulk data on mounted storage

**Date:** 2026-05-14
**Status:** accepted

**Context:**

During a Bot D deploy on 2026-05-14, the bot container's root filesystem reached 100%
usage. The root cause was bulky operational data under
`/home/bot/polymarket-bot/data`: old backup/snapshot directories plus large
SQLite databases and sidecars still lived on `/`, while mounted the bot container data
volumes had ample free space:

- `/home/bot/polymarket-bot/data/external`: 200G mounted storage.
- `/home/bot/polymarket-bot/data/recorder`: 100G mounted storage.

Root-disk exhaustion interrupted deploys and caused transient service failures
when DB symlink targets were temporarily wrong. The fleet should not rely on
manual cleanup of `/` for normal operation.

**Decision:**

1. Treat the bot container root as code/config/runtime-only storage.
2. Store bulky operational data on mounted storage:
   - backups and snapshots under
     `/home/bot/polymarket-bot/data/external/root-disk-relief-20260514/`;
   - large SQLite databases and WAL/SHM sidecars under
     `/home/bot/polymarket-bot/data/external/live-dbs-20260514/`.
3. Preserve existing service paths by leaving absolute symlinks at the
   original `data/*` paths.
4. Add a daily the bot container storage health timer that checks root, external, recorder,
   and broken data symlinks.
5. Cap journald on the bot container so system logs cannot silently consume root storage.

**Consequences:**

- Existing services continue using the same DB paths while the underlying data
  lives on mounted storage.
- Root disk recovered from full to approximately 7% used after migration.
- Storage pressure becomes a visible systemd health issue before it can block
  deploys.
- Services using `ProtectSystem=strict` may need explicit read-only or
  read-write access to the mounted target, not only the symlink path.

**Rollback:**

Stop trading/recorder services, copy the symlink targets back under
`/home/bot/polymarket-bot/data`, replace symlinks with regular files, reload
affected systemd units, and restart services. Disable
`polymarket-storage-health.timer` only if an equivalent storage monitor is
installed.

**Cross-refs:** ADR-047, ADR-116, ADR-157, OQ-053.

## ADR-169: Promote Beijing ZBAA into Bot D verified weather coverage

**Date:** 2026-05-15
**Status:** accepted

**Context:**

On 2026-05-15 Bot D live was active but not placing new weather trades. The
binding issue was not capacity: the stale live-position ledger had already
been repaired and local Bot D live open positions matched the wallet-active
posture. Recent live scans kept only one verified market, Dallas, and skipped
it as `below_threshold`.

At the same time, live discovery logged:
`bot_d.discovery.unknown_city city='Beijing'`. Gamma's active
daily-temperature feed had Beijing markets for 2026-05-15 and 2026-05-16. The
event rules explicitly state that settlement uses the highest temperature at
the Beijing Capital International Airport Station in Celsius, via Wunderground
ZBAA:
`https://www.wunderground.com/history/daily/cn/beijing/ZBAA`.

**Decision:**

1. Add Beijing to Bot D's city registry using Beijing Capital International
   Airport coordinates.
2. Add verified settlement coverage:
   `SettlementSpec("ZBAA", 40.0799, 116.6031, "ZBAA", unit="C",
   verified=True, verification_status="verified")`.
3. Keep existing non-US live guardrails unchanged. Beijing can be evaluated
   only through the same verified-settlement, international-live, source
   agreement, NWS-fallback block, edge, liquidity, sizing, and cap gates as the
   other verified international cities.

**Consequences:**

- Beijing markets no longer fall through `resolve_city()` as unknown.
- Bot D can score Beijing when live Gamma lists its temperature markets.
- Trade count can improve on days when US verified-city market supply is thin,
  but Beijing still needs the same live source/data agreement as other
  non-US cities before any order can be placed.

**Rollback:**

Set Beijing back to `verified=False` / `verification_status="shadow"` or
remove the `SettlementSpec` if future market rules change away from ZBAA or
Wunderground.

**Cross-refs:** ADR-114, ADR-129, ADR-162, ADR-167, OQ-067.

## ADR-171: Harden the bot container systemd sandboxes for external DB symlink targets

**Date:** 2026-05-15
**Status:** accepted

**Context:**

ADR-168 moved bulky the bot container DBs under
`/home/bot/polymarket-bot/data/external/live-dbs-20260514/` and preserved
the old `data/*.db` paths as symlinks. The 2026-05-15 fleet audit found two
storage-sandbox regressions:

- `polymarket-wallet-tag-strict-monitor.service` failed with
  `sqlite3.OperationalError: unable to open database file`.
- `polymarket-wallet-observer.service` was active and collecting fills, but
  it wrote a new DB fork under `data/data/external/live-dbs-20260514/` while
  the daily report read the canonical `data/external/live-dbs-20260514/`
  target, making the report falsely say the observer was stale.

**Decision:**

1. Add explicit `/home/bot/polymarket-bot/data/external` access to the bot container
   systemd units that read or write storage-moved DB symlink targets.
2. Extend `scripts/bot-host_storage_health.py` to fail if any DB appears under
   accidental nested `data/data/external/**`, because that indicates a service
   is writing a fork rather than the canonical DB.
3. Treat wallet-tag strict-monitor gate-open exit `1` as a successful
   observation result in the repo-local unit so `systemctl --failed` remains
   reserved for actual operational failure.
4. Treat the host repair as an operator-approved deploy/restart item. the operator
   approved deployment on 2026-05-15, and the the bot container units plus storage-health
   script were deployed in the same session.

**Consequences:**

- Patched units can read/write the canonical DB targets after the ADR-168
  storage move.
- The storage health timer can catch accidental DB forks before reports or
  dashboards silently read stale data.
- The existing the bot container nested Wallet Observer DB was reconciled into the
  canonical DB (`489155` -> `500189` fills; `11034` unique rows inserted;
  `quick_check=ok`). Remaining nested fork DBs were archived, not deleted,
  under `data/reconcile-backups/20260515T093007/nested-external-unmerged/`
  for later table-specific reconciliation.

**Rollback:**

Remove the added external-path allowances and nested-fork check only if DBs
are moved back under root-local `data/` regular files.

**Cross-refs:** ADR-168, OQ-053, OQ-099, OQ-115.

## ADR-172: Activate approved D-Spike, Station Lock, and Bot L live-probe runtimes

**Date:** 2026-05-15
**Status:** accepted
**Risk level 2026-05-18:** R2 tiny-live where still active; no scale without
lane-specific OQ evidence and a new ADR.

**Context:** ADR-165 and ADR-170 approved tiny live probes for Bot D-Spike,
Bot D Station Lock, and Bot L BUY/MERGE, but the first 2026-05-15 review left
them blocked by paper-only runtime code. the operator then explicitly approved
deployment. The safety requirement is to move faster on capped learning
without relaxing wallet safety, per-bot caps, kill switches, reconciliation,
secret handling, or approval controls.

**Decision:**

1. Activate Bot D-Spike on the VPS as `bot_d_spike` live probe with
   `BOT_D_SPIKE_PAPER_ONLY=false`, `$2` max order, `$10` daily gross,
   `$20` open exposure, `10` max concurrent positions, and the existing
   Strategy E `6h-12h` / `1c-15c` cheap-YES gates.
2. Activate Bot D Station Lock on the bot container as `bot_d_station_lock` live probe
   with `BOT_D_STATION_LOCK_PAPER_ONLY=false`, `$5` max order, `$20` daily
   gross, `$25` open exposure, and `5` max concurrent positions.
3. Activate a Bot L BUY-bundle live-probe timer on the VPS under the already
   approved `$1` bundle / `$10` daily gross / `$20` open exposure caps, but
   hard-block order placement when the `$1` bundle would create fewer than
   the exchange's `5` minimum shares. Do not exceed the approved cap to force
   fills.
4. Keep Bot L MERGE execution, SELL, and SPLIT unapproved until a later
   explicit on-chain transaction path and stuck-inventory recovery path exist.
5. Deploy `core/tiny_live_probe.py` to both hosts before starting live-probe
   services; host copies were stale relative to the repo.

**Rationale:** D-Spike and Station Lock are weather lanes with bounded
single-order and daily-loss exposure, enough paper evidence to justify
learning, and a clear rollback path. Bot L's complete-set idea needs real
execution evidence, but the approved `$1` cap conflicts with the exchange
minimum in normal pricing. Blocking those orders is the correct fund-safety
outcome until the operator approves a higher minimum viable bundle size.

**Consequences:**

- `polymarket-bot-d-spike.service` is disabled on the VPS and replaced by
  `polymarket-bot-d-spike-live-probe-vps.service`.
- `polymarket-bot-d-station-lock.service` is disabled on the bot container and replaced
  by `polymarket-bot-d-station-lock-live-probe.service`.
- `polymarket-bot-l-complete-set-live-probe-vps.timer` runs one-shot passes;
  the first confirmed pass returned `below_exchange_min_shares` at `$1.0000`
  gross and `1.0309` shares, placing no order.
- OQ-086 and OQ-112 remain scale gates, not activation blockers. OQ-111
  remains open for merge execution, minimum viable cap, gas, and stuck
  inventory.
- No treasury action is authorized by this ADR.

**Rollback trigger:** Any CLOB/auth/reconcile fault, cap breach, stale-order
fault, unexpected fill outside a known order, unexplained position change, or
kill-switch breach should stop only the affected live-probe unit and restore
the prior paper unit where applicable. Bot L can be rolled back by disabling
only its live-probe timer.

## ADR-174: Add Bot D maker live probe under a separate capped ledger

**Date:** 2026-05-15
**Status:** accepted
**Risk level 2026-05-18:** R2 tiny-live allowed at current caps only.

**Context:**

Bot D's taker lane has produced useful live weather evidence, but recent
activity stalled when taker gates, depth, and source checks left few markets
worth crossing. the operator approved building a spin-off maker lane directly live,
skipping a paper proof gate, to test whether non-crossing weather quotes can
increase fills, lower fees/slippage, and improve ROI while keeping the same
fund-safety envelope.

The approved packet:

- separate bot id and ledger: `bot_d_maker_live_probe`;
- `$200` wallet posture;
- `$5` minimum intended quote notional;
- `$10` maximum order notional;
- `$100` daily gross cap;
- `$100` open exposure cap;
- verified Bot D cities only;
- maker/non-crossing BUY quotes only;
- stale quotes cancelled after roughly `3` minutes;
- no NWS-fallback, stale-forecast, unverified-settlement, halt, or fleet-cap
  bypass.

**Decision:**

Add `bot_d_maker_live_probe` as a separate live registered bot and systemd
unit. The lane may place only non-crossing BUY GTC maker quotes, reconcile
live fills under its own bot id, cancel stale maker quotes, and expose its
own dashboard caps/P&L. It must not share the `bot_d_live_probe` bot id,
orders, positions, caps, or watchdog mode key.

Sizing treats the dollar packet as the hard risk/evidence unit. The normal
target is `5-10` shares depending on quote price, but cheap quotes can exceed
`10` shares only as needed to meet the `$5` minimum and never above the `$10`
order cap.

**Guardrails:**

- `POLYMARKET_ENV=live`, `BOT_D_MAKER_ENV=live`,
  `BOT_D_MAKER_LIVE_AUTHORIZED=true`, and
  `BOT_D_MAKER_LIVE_APPROVED_AT` are required.
- `BOT_D_MAKER_ID_OVERRIDE` must resolve to `bot_d_maker_live_probe`.
- Emergency halt and per-bot halt block new maker quotes.
- Fleet-cap failure blocks new maker quotes.
- Forecast age above `BOT_D_MAKER_MAX_FORECAST_AGE_SEC` blocks quotes.
- `forecast_source="nws_fallback"` blocks quotes.
- Orders without an exchange order id are rejected rather than recorded as
  trackable live exposure.
- The watchdog routes `bot_d_maker_live_probe` through `BOT_D_MAKER_ENV`,
  not shared Bot D paper env vars.

**Consequences:**

- The taker weather lane remains unchanged.
- The maker lane's first review gate is empirical: compare fills, cancels,
  realised P&L, adverse selection, quote ageing, and taker-vs-maker outcome
  after `10` maker fills, `25` maker quotes, or `48` hours of runtime,
  whichever comes first.
- This ADR authorizes the build and tiny-live service under the packet above;
  any later cap/size increase needs a new operator approval checkpoint.

**Rollback trigger:**

Disable `polymarket-bot-d-maker-live.service` and cancel open
`bot_d_maker_live_probe` orders through the approved watchdog/emergency path
if any untracked fill, duplicate quote loop, stale quote older than the
configured limit, cap breach, fleet-cap breach, CLOB auth fault, or
unexpected cross-book/taker fill is observed.

**Cross-refs:** ADR-163, ADR-170, OQ-067, OQ-116.

## ADR-173: Raise Bot L live-probe bundle cap to exchange-minimum viable size

**Date:** 2026-05-15
**Status:** accepted

**Context:** ADR-172 deployed the approved Bot L live-probe timer at the
original `$1` bundle cap. The first confirmed live-probe passes all returned
`below_exchange_min_shares`: at complete-set prices around `0.97`, a `$1`
bundle produced only `1.0309` shares, below the exchange `5`-share minimum.
the operator explicitly approved adjusting Bot L caps so it can trade.

**Decision:**

1. Raise Bot L's max BUY bundle gross from `$1` to `$5`, the smallest round
   cap that can satisfy the `5`-share minimum under normal complete-set
   pricing.
2. Keep the daily gross cap at `$10`, limiting the probe to at most two
   max-size bundles per UTC day.
3. Keep the open exposure cap at `$20`.
4. Keep scope to BUY-both-legs only. MERGE, SELL, and SPLIT remain unapproved
   until a later explicit transaction and stuck-inventory path is implemented.
5. Harden the runner so a YES-leg success followed by a NO-leg rejection is
   immediately cancellation-attempted, written to the canonical orders table,
   and logged as `bot_l.complete_set.bundle_incomplete`.
6. Require a fresh executable signal (`<=120s`) and a live book check on both
   token IDs before submitting either leg.

**Rationale:** A `$1` cap cannot produce live execution evidence because it is
below exchange minimum size. `$5` is the minimum practical learning size while
still preserving a tight daily cap and open-exposure cap. The incomplete-leg
accounting fix is required before increasing size because untracked one-leg
inventory is the main operational risk in this lane.

**Consequences:**

- The VPS live-probe service uses `--max-bundle-usd 5` and
  `--max-signal-age-ms 120000`.
- Bot L can now place real BUY-bundle orders when the latest executable paper
  signal remains eligible and the daily/open caps are available.
- OQ-111 remains open for MERGE, gas, stuck-inventory recovery, concentration,
  and scale evidence.

**Rollback trigger:** Disable `polymarket-bot-l-complete-set-live-probe-vps.timer`
if either leg rejects unexpectedly, a cap check fails, an order is placed
without a canonical DB row, reconciliation reports unknown fills, or any
stuck one-leg exposure appears.

## ADR-170: Next aggressive live-probe packet prioritizes capped learning over old sample gates

**Date:** 2026-05-15
**Status:** accepted
**Risk level 2026-05-18:** R2 doctrine only for tightly capped live probes;
R3/R4 applies immediately when accounting, ROI, or wallet ownership becomes
unclear.

**Context:**

the operator requested a faster, higher-risk review of all live bots, paper bots, and
recorders. The current host audit found a useful split:

- Fund-safety controls are still load-bearing and remain unchanged.
- Some old sample-size gates are now slowing learning more than reducing
  meaningful capped downside.
- Runtime state does not fully match dashboard labels: Bot D-Spike, Bot D
  Station Lock, and Bot L Complete-Set are approved/dashboard-visible as live
  probes, but current host services still run paper/timer implementations.
- Bot G Prime Live is the wrong place to increase size: latest live reports
  show negative realised ROI.
- Bot D live is the best existing candidate for a cap increase because it has
  real live fills, reconciliation, source telemetry, and report-only position
  validation.

**Decision:**

Adopt the ranked packet in
`docs/reports/aggressive-live-expansion-review-2026-05-15.md`:

1. Prioritize a Bot D live cap bump for faster weather learning, subject to
   explicit the operator approval and no loosening of source, settlement,
   reconciliation, wallet, or kill-switch controls.
2. Treat Bot D-Spike 6-12h, Bot D Station Lock, and Bot L BUY/MERGE as the
   next operational live-probe activations because their old paper gates now
   block scale only, not tightly capped live learning.
3. Keep Bot G Prime Live at `$1` or pause it; do not increase Bot G size while
   the latest live ROI remains materially negative.
4. Keep Bot I Persistence Live running at current caps until it records real
   live entries.
5. Keep Bot K, Bot J, wallet-tag, Bot H Maker V2, and WC negRisk in
   paper/recorder mode until their lane-specific implementation blockers are
   cleared.

**Fund-safety invariants preserved:**

- No live orders without explicit the operator approval.
- No live config change, deployment, service restart, wallet touch, keystore
  read, passphrase action, or treasury action without explicit approval.
- Per-order, daily gross, open exposure, concurrent position, wallet floor,
  fleet-cap, watchdog, reconciliation, and kill-switch controls remain
  mandatory.
- Any runtime activation or cap increase still needs an operator approval
  checkpoint and post-change health check.

**Consequences:**

- Conservative duration/sample gates in OQ-086, OQ-111, and OQ-112 are scale
  gates, not activation blockers, for the already-prepared tiny live probes.
- Bot G size-up is explicitly rejected under the current evidence.
- The active operating model must distinguish dashboard approval from actual
  runtime live order placement for the three approved-but-not-operationally-
  enabled probes.
- A repo-local systemd fix for the wallet-tag strict monitor is accepted, but
  deployment to the bot container required explicit approval and was completed on
  2026-05-15.
- the operator approved Bot D-Spike, Station Lock, and Bot L activation on
  2026-05-15, but activation is now blocked by missing live executor code, not
  by sample-size approval gates. Do not fake-enable these by changing systemd
  env alone.

**Rollback:**

Supersede this ADR if a tiny live probe creates untracked fills, cap breach,
wallet/fleet accounting mismatch, repeated rule violations, or operator burden
greater than the learning value. Rollback means stop the relevant live-probe
service, cancel open live orders only through the approved emergency path,
leave the paper lane running where useful, and log the event in `CHANGELOG.md`,
`MEMORY.md`, and the relevant OQ.

**Cross-refs:** ADR-163, ADR-164, ADR-165, ADR-168, OQ-067, OQ-086, OQ-111,
OQ-112, OQ-113, OQ-114, OQ-115.

## ADR-175: Block ended/near-ended Bot D weather entries and cap cheap late maker YES quotes

**Date:** 2026-05-15
**Status:** accepted

**Context:**

A live Polymarket position showed `165.4` YES shares on the NYC May 15
70-71F high-temperature bucket even though the local market row's `end_date`
was already in the past. Audit confirmed both Bot D taker live probe and Bot D
maker live probe bought the same condition after the stored end time because
Bot D only rejected markets whose lockup was too long; it did not reject
markets with `hours_to_end <= 0` or a small positive time-to-end. The maker
probe also treated the `$5` minimum notional as the hard floor for very cheap
YES quotes, turning a 3-4c quote into a much larger share count than intended
for a late, high-variance experiment.

**Decision:**

1. Bot D taker and paper candidate filters must reject markets whose
   `end_date` has passed with reason `market_ended`.
2. Bot D taker and paper candidate filters must reject markets closer than
   `BOT_D_MIN_ENTRY_HOURS_TO_END` to end, default `2` hours, with reason
   `too_close_to_end`.
3. Bot D maker live must apply its own positive time-to-end floor,
   `BOT_D_MAKER_MIN_ENTRY_HOURS_TO_END`, default `3` hours, before quoting.
4. Bot D maker live must cap cheap YES quote notional separately from the
   normal `$5` minimum: if a BUY_YES quote is below
   `BOT_D_MAKER_CHEAP_YES_PRICE` (default `0.05`) or inside
   `BOT_D_MAKER_LATE_YES_HOURS_TO_END` (default `6` hours), the maker max
   notional is capped at `$2` by default.
5. This does not disable the maker-vs-taker overlap experiment. It only keeps
   ended, near-ended, and ultra-cheap late YES quotes from creating oversized
   exposure.

**Consequences:**

- Stale Gamma/end-date rows can no longer be bought by either Bot D live lane.
- Cheap YES maker quotes remain possible for evidence collection, but their
  default dollar exposure is smaller than normal maker quotes.
- The existing Bot D source, settlement, API-agreement, expensive-NO, wallet,
  daily gross, open exposure, and watchdog controls remain unchanged.
- The May 15 NYC 70-71F issue is treated as a gate bug plus maker sizing bug,
  not as evidence that the weather model itself intended a large late risk.

**Rollback:**

Rollback requires an explicit new ADR because it would re-open ended or
near-ended market entry risk. The safe rollback for any operational issue is
service-level: stop `polymarket-bot-d-live.service` and/or
`polymarket-bot-d-maker-live.service`, cancel open live orders through the
approved emergency path, and leave paper/report-only lanes running.

**Cross-refs:** ADR-148, ADR-162, ADR-166, ADR-174, OQ-067, OQ-116.

## ADR-176: Block Cell C $1 maker live probe until the exchange minimum is explicitly authorized

**Date:** 2026-05-16
**Status:** accepted

**Context:**

The 2026-05-16 07:11 UTC maker-vs-taker comparator and refreshed cumulative
Cell C report moved the Cell C maker candidate to `69/69/69` with `-0.90%`
ROI and `$-0.60` net P&L. That clears the S7 `n>=50` sample trigger but lands
inside the Z5 borderline band (`-1% <= ROI <= +1%`). The operator goal says
borderline Cell C should use a
`$1/trade` live probe instead of the normal `$5/trade` packet.

The live Bot I persistence executor currently converts stake to shares through
the same exchange-floor helper used elsewhere in the fleet: `MIN_POLYMARKET_SHARES`
defaults to `5`, and `stake_to_shares` clamps order size up to that floor. For
Cell C's `0.95-0.99` high-side price band, a valid 5-share BUY requires roughly
`$4.75-$4.95` notional before fees/rebates. Deploying a nominal `$1/trade`
Cell C live probe through that helper would therefore place a minimum-exchange
order close to `$5`, breaching the goal's H6 operator-override gate. Lowering
the share count would be rejected or skipped by `core.clob_v2`, which also
skips live orders below 5 shares.

**Decision:**

1. Treat the Cell C S7 gate as **borderline**, not a `$5/trade` pass.
2. Accept only the `$1/trade` Cell C maker live-probe intent for this evidence
   state.
3. Do **not** deploy or start a Cell C live service while the `$1/trade` cap
   is non-executable at the exchange's 5-share minimum.
4. Keep `bot_i_cell_c_maker` running as the paper-shadow evidence lane and
   keep the existing Bot I live taker executor unchanged.
5. Open OQ-118 for the operator decision: either explicitly raise the
   borderline Cell C cap to the minimum executable notional, approximately
   `$5/trade` in the 95-99c band, or reject/defer the Cell C live probe.

**Consequences:**

- No live order path, wallet posture, keystore, VPN, or shared-wallet cap was
  changed by this ADR.
- The S7 evidence result is recorded, but live deployment is blocked by H6
  until the operator explicitly authorizes the minimum executable cap or rejects the
  probe.
- ADR-131 remains the existing Bot D negative-risk cleanup ADR; the maker
  conversion goal uses ADR-176 for this Cell C decision because existing ADRs
  are immutable and cannot be renumbered.
- S5/S6 monitoring continues for Bot G, Bot I maker shadows, and crypto FV
  review-only rows.

**Rollback:**

No runtime rollback is required because no Cell C live service was deployed and
no live order was placed. If this ADR is superseded, the replacement ADR must
name the exact Cell C per-trade cap, daily gross cap, open-exposure cap, kill
date, service unit, and post-switch monitoring window before any service start.

**Cross-refs:** OQ-117, OQ-118.

## ADR-178: Activate crypto FV maker tiny-live probes on the bot container

**Date:** 2026-05-16
**Status:** accepted
**Risk level 2026-05-18:** R3 paused live by ADR-181 after live drawdown and
wallet/accounting gaps.

**Context:**

the operator explicitly approved taking both crypto FV maker lanes live on
2026-05-16 after reviewing the history-derived caps from ADR-177. The approval
covered `crypto_probability_gap_live_maker` and
`crypto_brownian_fv_live_maker` with the prepared tiny-live cap packet, and
asked for a `1-2h` monitor to ensure trading behaved as expected.

**Decision:**

1. Deploy and start both FV live-maker services on the bot container:
   `polymarket-crypto-prob-gap-live-maker.service` and
   `polymarket-crypto-brownian-fv-live-maker.service`.
2. Use the ADR-177 caps unchanged: probability-gap `$5` max order, `$250`
   daily gross, `$100` open exposure, and `20` concurrent positions; Brownian
   `$5` max order, `$300` daily gross, `$120` open exposure, and `24`
   concurrent positions.
3. Keep the existing paper-maker services running as the comparison/control
   evidence stream.
4. Run a the bot container monitor for the activation window at
   `data/reports/crypto_fv_live_monitor/activation-20260516T1306Z.jsonl`.
5. After early SQLite write collisions during concurrent fill reconciliation,
   keep the services live but reduce collision risk by adding SQLite
   `busy_timeout` and staggering live scan intervals to `9s` probability-gap
   and `13s` Brownian.

**Consequences:**

- Both FV maker lanes now use real wallet funds and must be treated as live
  services, not paper-only candidates.
- Initial live fills confirmed known-order accounting and tiny exposure:
  probability-gap had six live fills and about `$18.81` open cost by
  13:10 UTC; Brownian had four live fills and about `$14.22` open cost by
  13:10 UTC.
- The first activation window found two early DB lock restarts before the
  busy-timeout/stagger patch. The services were restarted cleanly after the
  patch and showed no new traceback through the 13:15 UTC post-restart check.

**Rollback:**

Stop the affected service with `systemctl stop`, cancel open live maker orders
through the approved emergency path if exposure must be flattened, leave the
paper-maker controls running, and record the reason plus any live order ids in
`CHANGELOG.md` and `MEMORY.md`.

**Cross-refs:** ADR-139, ADR-177, OQ-117, OQ-120.

## ADR-177: Prepare crypto FV maker tiny-live probes behind explicit approval

**Date:** 2026-05-16
**Status:** accepted

**Context:**

The crypto FV maker shadows crossed a meaningful early profitability threshold
on the bot container after the 2026-05-15 maker comparator fix. The 2026-05-16 morning
snapshot showed both maker lanes active for roughly 20 hours with positive
realised paper P&L: probability-gap maker around `216` closed markets,
`+$155.41`, and `+14.4%` ROI; Brownian maker around `264` closed markets,
`+$173.15`, and `+13.1%` ROI. The maker-vs-taker daily report also showed
the archived taker baselines remained negative while maker shadows were
positive.

The evidence is strong enough to prepare a capped real-wallet probe, but not
strong enough to silently override ADR-139's archive decision or convert the
existing paper runner into a live bot. The existing
`bots.crypto_fair_value` runner deliberately remains paper-only and rejects
live wallet envs.

**Decision:**

1. Keep the existing crypto FV paper/shadow runner paper-only.
2. Add separate approval-gated live-maker executors for:
   `crypto_probability_gap_live_maker` and
   `crypto_brownian_fv_live_maker`.
3. Default each live-maker unit to blocked mode. A live service must not open
   live wallet/client paths unless all live approval flags are set.
4. Use history-derived initial caps unless superseded by a new ADR:
   probability-gap uses `$5` max order, `$250` daily gross, `$100` open
   exposure, and `20` concurrent positions; Brownian uses `$5` max order,
   `$300` daily gross, `$120` open exposure, and `24` concurrent positions.
   These caps are based on the the bot container paper-maker distribution through
   2026-05-16 11:26 UTC: peak hourly gross was `$90` / `$115`, and peak open
   exposure was `$100` / `$120`.
5. Submit only exchange-enforced post-only maker quotes below the current best
   ask, require at least `2.5c` maker edge after the quote discount, reconcile
   only known live orders, and write every submitted live quote to the canonical
   `orders` table before relying on watchdog/dashboard surfaces.
6. Operator approval is still required before deploying, enabling, or starting
   either live unit on the bot container.

**Consequences:**

- Crypto FV maker live promotion becomes an explicit tiny-live probe packet,
  not a quiet mutation of the paper services.
- Registry, watchdog, and dashboard inventory now know the two live-maker bot
  ids before activation.
- The default systemd files are safe to commit because they exit blocked until
  `POLYMARKET_ENV=live`, the lane-specific live env, authorization, and an
  approval date are all present.
- Paper-maker monitoring continues unchanged and remains the primary evidence
  stream until activation is explicitly approved.

**Rollback:**

Before activation, rollback is deleting or ignoring the two live-maker units
and keeping paper shadows running. After activation, stop the specific live
maker service, cancel open live orders only through the approved emergency
path, keep the paper-maker shadows running, and log the rollback in
`CHANGELOG.md`, `MEMORY.md`, and any affected OQ.

**Cross-refs:** ADR-108, ADR-132, ADR-139, OQ-117, OQ-120.

## ADR-179: Add Bot D Ensemble Ladder as a paper-only adjacent YES basket lane

**Date:** 2026-05-16
**Status:** accepted

**Context:**

The operator reviewed a public weather-bot write-up claiming positive ROI from
a station-exact, three-model, adjacent-bucket YES ladder. The useful pieces are
not the same as Bot D's existing live strategy. Bot D's current live and paper
lanes evaluate one bucket at a time, enforce one bet per city/date/temp event,
and generally treat ensemble disagreement as a risk signal. The proposed
ladder intentionally buys two or three adjacent YES buckets for one event,
accepting that most legs lose if the winning cheap leg pays for the basket.

Bot D already handles the article's most important correction for verified
cities: forecast coordinates come from settlement-station `SettlementSpec`
entries such as KLGA, KORD, KDAL, KATL, KMIA, RJTT, EGLC, and LFPB rather than
generic city centers. What remains untested is the distinct event-level basket
math.

**Decision:**

1. Add a separate paper-only bot id, `bot_d_ensemble_ladder`.
2. The lane writes only Event rows:
   `bot_d_ensemble_ladder.plan` and
   `bot_d_ensemble_ladder.scan_summary`.
3. The lane must not import or construct a CLOB client and must not write
   Order, Trade, or Position rows.
4. The initial planner uses station-exact ICON/GFS/ECMWF deterministic
   forecasts, an `18h-30h` time-to-end window, closest-pair consensus within
   `1.0C`, max model spread `3.0C`, and adjacent YES-bin baskets.
5. Initial basket filters mirror the article's conservative start point:
   each leg `1c-45c`, total YES price `<=95c`, and `$2` nominal stake per leg.
6. `bias_correction=true` is logged as a shadow Open-Meteo request parameter
   only; it must not be treated as proven edge until OQ-122 compares realised
   output with and without it.
7. The current Bot D live/taker/maker lanes keep their one-bet-per-event rule
   and existing guardrails unchanged.

**Consequences:**

- Ensemble disagreement can now be studied as a basket opportunity without
  weakening the live probe's existing risk controls.
- Paper P&L must be judged at the event-basket level, not per leg.
- Hong Kong, Singapore, Seoul, and other uncertain-station cities remain out
  unless their settlement station is verified and enabled by a future ADR.
- Any live version requires a new ADR, explicit the operator approval, a capped packet,
  and OQ-122 evidence.

**Rollback:**

Disable or ignore `polymarket-bot-d-ensemble-ladder.service` and keep the
Event rows as research evidence. No live order cancellation, wallet action, or
position reconciliation is required because this lane has no live path.

**Cross-refs:** ADR-052, ADR-104, ADR-147, ADR-175, OQ-074, OQ-103, OQ-122.

## ADR-180: Auto-wrap residual USDC.e to pUSD on the bot container

**Date:** 2026-05-16
**Status:** accepted
**Risk level 2026-05-18:** R4 wallet maintenance path. Allowed only within
the narrow approved USDC.e -> pUSD wrap scope; no order placement or treasury
movement.

**Context:**

Polymarket winner redemptions and legacy collateral paths can still leave the
hot wallet holding USDC.e. V2 live bots spend pUSD, so residual USDC.e is not
usable trading cash for the current live maker services. On 2026-05-16, after
FV live-maker caps were expanded, the wallet had only about `$2.95` pUSD while
holding `136.965771` USDC.e. the bot container live-maker logs then showed repeated CLOB
rejects of the form `not enough balance / allowance`, even though the wallet
had enough value in the wrong token.

the operator explicitly approved converting USDC.e to pUSD and setting up automatic
conversion.

**Decision:**

1. Keep `scripts/wrap_usdce_to_pusd.py` as the canonical USDC.e -> pUSD
   conversion path.
2. Add `polymarket-wrap-usdce-to-pusd.service` plus
   `polymarket-wrap-usdce-to-pusd.timer` on the bot container.
3. The timer runs every `5` minutes, wraps the full residual USDC.e balance,
   and exits cleanly if the balance is zero.
4. The timer uses the existing hot-wallet keystore and passphrase paths from
   `/home/bot/polymarket-bot/.env`; no private key or passphrase is written to
   disk or logged.
5. The helper logs masked wallet addresses by default.

**Consequences:**

- Future winner redemptions that return USDC.e should be usable by the bots
  within one timer cycle.
- The timer is a live wallet-maintenance path, not a trading strategy path. It
  must stay narrow: no order placement, no redemption sweep, no treasury
  transfer, and no unwrap path.
- pUSD exhaustion can still happen if live bot caps consume all available
  wallet cash into open positions; this timer only fixes wrong-token cash, not
  bankroll sizing.

**Rollback:**

Disable the timer with
`systemctl disable --now polymarket-wrap-usdce-to-pusd.timer`. Manual wrapping
can still be run with `scripts/wrap_usdce_to_pusd.py --all --execute --yes`
after a dry run.

**Cross-refs:** OQ-121, ADR-178.

## ADR-181: Pause Bot I live and keep only Bot D live during loss reassessment

**Date:** 2026-05-17
**Status:** accepted
**Risk level 2026-05-18:** R3 paused live for Bot I and both crypto FV live
makers; R2 remains only for Bot D live lanes.

**Context:**

After FV Brownian live and FV probability-gap live were stopped, the operator still
observed live account activity and asked to identify the separate accounting
issue, stop it, and return to paper on everything apart from Bot D. the bot container
inspection found `polymarket-bot-i-persistence-live.service` was still live
and writes to `/home/bot/polymarket-bot/data/persistence_live.db`, not the
shared `data/main.db`. This explains why some real wallet crypto activity did
not appear in the FV/main DB accounting.

The Bot I local DB also produced bad realised P&L: it showed `30` live entries,
`$150.00` stake, and `-$139.095` local realised P&L, but Polymarket Data API
matching on `29` Bot I condition IDs found `$141.458618` buys, `$119.991160`
redeems, and true wallet-level Bot I P&L of `-$21.467458` (`-15.18%` ROI).
Several redeemed winners were incorrectly marked as losses locally.

Current wallet Data API positions also include weather rows that do not match
`main.db` orders, trades, positions, or events, and Bot D journals around their
trade times show no matching placement. Whole-wallet accounting therefore
needs a Data API ownership backfill before any non-Bot-D live restart.

**Decision:**

1. Disable and stop `polymarket-bot-i-persistence-live.service`.
2. Keep FV Brownian live and FV probability-gap live stopped/disabled.
3. Keep only Bot D live services active during the reassessment:
   `polymarket-bot-d-live.service`,
   `polymarket-bot-d-maker-live.service`, and
   `polymarket-bot-d-station-lock-live-probe.service`.
4. Keep paper services active so evidence collection continues.
5. Do not restart Bot I or FV live services until a wallet Data API
   backfill/audit classifies every buy/redeem into `main.db`,
   `persistence_live.db`, manual/unowned, or ignored accounting buckets.

**Consequences:**

- Non-Bot-D real-money exposure stops while the drawdown and accounting gap are
  reassessed.
- Bot I's local P&L is not trusted for live decisions until repaired.
- `main.db` is not treated as whole-wallet truth; dashboard accounting must
  surface wallet-unowned rows or reconcile them explicitly.

**Rollback:**

Re-enabling Bot I or either FV live service requires a new explicit the operator
approval after OQ-123 is resolved and the live dashboard can show wallet-level
ownership/P&L.

**Cross-refs:** ADR-178, ADR-180, OQ-121, OQ-123.

## ADR-182: Wallet Data API dry-run backfill job + dashboard truth surface (OQ-123 foundation)

**Date:** 2026-05-18
**Status:** accepted
**Owner:** Grok (overnight impl per SPEC) / operator for gated deploy

**Context:**
OQ-123 identified that `main.db` + `persistence_live.db` diverge from hot-wallet Data API truth (unowned weather rows, Bot I redeem misclass, stale G-prime live rows, rebates). Dashboard P&L and any restart decision are untrustworthy until reconciled. Session 450 delivered the read-only reporter; overnight work completes the canonical `wallet_data_api_backfill.py` (classes + classifier + fixtures + tests), dashboard fields (reconciliation_status, freshness helper, explicit labels), model + migration skeleton, and all docs/tests. All strictly dry-run / read-only; no --execute, no live services touched.

**Decision:**
1. Evolve the reconciliation tooling into `scripts/wallet_data_api_backfill.py` as the authoritative (default --dry-run) entry point with `WalletDataApiClient`, `ReconciliationClassifier`, `ReconciliationReporter`.
2. Add `WalletReconciliation` model + Alembic skeleton (write path remains fully gated behind confirmation env + future ADR).
3. Extend dashboard `runtime_queries` with per-row `reconciliation_status`/`wallet_realised_pnl_usd`/`unresolved_exposure` + reusable `_freshness_for_live_row` (stale_7d/30d for live registry rows with old last_fill).
4. Harden Bot I guard test coverage (narrow --live-bot-i-report path only).
5. Formalize maker paper experiments + profitability ranking using the 2026-05-18 verified numbers (D live +31.06 first).
6. Update OQ-123, active model, CHANGELOG, MEMORY, decisions-log with this ADR.
7. All changes additive, behind dry-run defaults; the bot container verification read-only only.

**Consequences:**
- Unblocks trust in future ROI numbers and any paused-lane restart after operator reviews the dry-run report on real the bot container data.
- Dashboard now explicitly labels "local-ledger only" vs pending wallet-reconciled.
- Stale live rows (G prime example) surface as degraded without changing systemd state.
- Zero new live risk; rollback = git revert + DROP TABLE (if ever created).

**Rollback:**
Git revert the overnight commit(s). DROP TABLE IF EXISTS wallet_reconciliations (safe, no production data loss). Restore prior runtime_queries on the bot container. The dry-run reporter remains useful standalone.

**Cross-refs:** SPEC 2026-05-18, OQ-123, ADR-181, docs/GROK_OVERNIGHT_* files, wallet_data_api_backfill.py + tests.

## ADR-183: Halt all live services while keeping paper and recorders alive

**Date:** 2026-05-19
**Status:** accepted
**Owner:** the operator / Codex

**Context:**

the operator requested a full live shutdown because Bot G live was not justifying
continued real-money probing and the wider live fleet needed a clean pause
while Grok's reconciliation/dashboard work is reviewed. The intent is not to
stop research: paper traders and recorders remain running so the project keeps
collecting data.

**Decision:**

1. Stop and disable all live trading and live wallet-action units on the bot container and
   the VPS.
2. Set halt flags for live bot ids on both hosts with reason
   `operator_halt_2026-05-19_all_live_services_off`.
3. Verify both live wallets have `0` exchange-resting CLOB orders using the
   emergency cancel-all dry-run path.
4. Keep paper traders, paper timers, dashboards, watchdogs, wallet observers,
   and recorders running.
5. Mark live registry rows as `paused` while retaining dashboard visibility and
   cap inclusion for residual exposure/accounting.
6. Do not restart any live unit without a new explicit the operator approval and a new
   ADR that references OQ-123 and OQ-124.

**Consequences:**

- Bot G live is off; all other real-money bot services are also off.
- Existing live positions may remain as residual wallet exposure until they
  resolve or are handled by a separate approved closeout/redeem workflow.
- Paper and recorder evidence collection continues uninterrupted.
- Dashboard/live inventory should show paused/inactive live services instead
  of mistaking active paper timers for active live probes.

**Rollback:**

Re-enabling any live service requires a fresh operator command, wallet/order
preflight, reconciled dashboard state, and a follow-up ADR. Do not use the
previous live service enablement as standing approval.

**Cross-refs:** ADR-181, ADR-182, OQ-123, OQ-124.

## ADR-184: External trading frameworks stay out of live runtime; QuantStats allowed only as optional offline analytics

**Date:** 2026-05-24
**Status:** accepted
**Owner:** Codex / the operator for any future implementation approval

**Context:**

the operator asked whether five popular external trading repos could be added to
benefit Longshot code quality, profitability, or ROI:
`freqtrade/freqtrade`, `hummingbot/hummingbot`,
`AI4Finance-Foundation/FinRL`, `nautechsystems/nautilus_trader`, and
`ranaroussi/quantstats`.

The review checked current online metadata/public docs, shallow local snapshots
of each repo's relevant code, and the Longshot codebase. Longshot already has
Polymarket-specific CLOB execution, passive execution policy, ROI reports,
maker/taker reporting, fleet registry, optional ML research scripts, and
SQLite/systemd operational glue. The active fleet is also halted under
ADR-183 pending OQ-123/OQ-124 restart blockers.

**Decision:**

1. Do not add `freqtrade`, `hummingbot`, `FinRL`, or `nautilus_trader` as
   Longshot live runtime dependencies.
2. Allow `quantstats` only as a future optional offline analytics/reporting
   dependency, behind an explicit optional extra and a read-only adapter from
   Longshot closed PnL/equity curves to period returns.
3. Keep Longshot's existing trade-level gates canonical: sample size, fees,
   ex-largest ROI, concentration, fillability, wallet reconciliation, and OQ
   blockers.
4. Do not let QuantStats period-based win-rate or profit-factor metrics replace
   Longshot's trade-level win-rate/profit-factor calculations.
5. Treat `nautilus_trader` only as a future isolated read-only sandbox
   candidate after OQ-123/OQ-124 are closed. Any runtime migration requires a
   new ADR and explicit operator approval.

**Consequences:**

- No new live trading framework enters the halted fleet.
- Profitability work remains focused on Polymarket-specific evidence,
  settlement truth, accounting truth, and recorder-backed replay rather than
  importing adjacent CEX/MM/RL machinery.
- `quantstats` can still improve operator decision quality by standardizing
  drawdown, return-series, monthly-return, Monte Carlo, and risk-of-ruin
  reporting if a small adapter proves value.
- `nautilus_trader` remains strategically interesting because of its
  Polymarket adapter and research/live parity, but it is not a drop-in fit for
  the current Python 3.11, SQLite, systemd, and py-clob-client-v2 stack.

**Rollback:**

If a future implementation adds `quantstats` and the reports are not useful,
remove the optional dependency, remove the report script, and keep existing ROI
reports as canonical. Any future Nautilus experiment must remain isolated
until a separate ADR approves broader adoption.

**Cross-refs:** ADR-183, OQ-123, OQ-124,
`docs/reports/external-trading-repo-fit-review-2026-05-24.md`.

## ADR-186: Add Wallet-Tag Elite Cap Paper as a capped paper-only lane

**Date:** 2026-05-26
**Status:** accepted
**Owner:** Codex / the operator for any runtime deployment or live promotion approval

**Context:**
The 2026-05-26 Wallet-Tag audit found that the broad
`wallet_tag_feature_shadow` ledger is profitable overall, but its whale-sized
notional is not directly transferable to a `$137` operator wallet. A recent
cutdown to the four strongest profitable wallet suffixes produced a much
better transfer candidate on paper:

1. Combined robust 7-day cut: about `$480,681` closed cost, `+$108,082`
   realised P&L, `+22.49%` ROI, and `+17.66%` ROI after removing the largest
   win.
2. The source wallets remain external observed wallets. The evidence is
   useful only if it survives tiny-wallet constraints, latency, settlement
   labels, and concentration checks.
3. Direct broad copy-trading remains blocked by OQ-099 and the project scope
   kill-list. Any live order path requires a new ADR and explicit the operator
   approval.

**Decision:**
Add `wallet_tag_elite_cap_paper` as a separate `paper_tuning` lane and
dashboard row named `Wallet-Tag Elite Cap Paper`.

The lane:

1. Reuses `scripts/wallet_tag_feature_shadow.py`.
2. Filters to the four audited 2026-05-26 profitable wallet suffixes.
3. Writes a separate ledger at `data/wallet_tag_elite_cap_paper.db`.
4. Uses `$1` max entry cost, `$15` max open exposure, and one entry per
   wallet/market.
5. Has no CLOB client, no wallet key path, no live order placement, and no
   funds movement.

**Rationale:**
The broad Wallet-Tag shadow should keep running as evidence, but it is too
large and whale-shaped to answer the operator's real question: whether the edge
survives at tiny-wallet size. A capped companion paper lane tests the exact
transfer constraint without changing live posture or replacing the original
shadow.

**Consequences:**

- The dashboard gains `Wallet-Tag Elite Cap Paper` with capped synthetic P&L.
- OQ-126 records the empirical promotion gate.
- OQ-099 remains binding before any wallet-tag feature plumbing into Bot D,
  Bot G, or other strategies.
- Any live packet remains blocked by OQ-123/OQ-124, OQ-126, a new ADR, and
  explicit the operator approval.

**Rollback:**
Disable the paper timer/service and archive
`data/wallet_tag_elite_cap_paper.db` if the capped lane fails its OQ-126 gate.
Keep the original `wallet_tag_feature_shadow` ledger unless OQ-099 separately
fails.

**Cross-refs:** ADR-143, ADR-185, OQ-099, OQ-123, OQ-124, OQ-126.

## ADR-188: Recover the bot container Bot E recorder by bulk offload and hard disk guard

**Date:** 2026-06-03
**Status:** accepted
**Owner:** Codex executed after explicit the operator approval

**Context:**
the bot container Bot E recorder failed again after the dedicated recorder mount filled.
The watchdog alert reported recorder heartbeat staleness and
`RECORDER PERMANENTLY FAILED`; host checks confirmed
`/home/bot/polymarket-bot/data/recorder` on the bot container `mp1` was `250G / 100%`
with about `27M` free. Journals showed recorder bulk queue drops, systemd
watchdog timeouts, and start-limit exhaustion. Dashboard static content still
served, but `/api/overview` timed out because runtime queries touched the
oversized recorder state.

ADR-168 and the 2026-05-24 resize bought temporary headroom but did not create
a retention/rollover system. the operator explicitly approved all fixes, including
offloading data to other server storage and hardening recurrence prevention.

**Decision:**
1. Recover the bot container without touching live trading, wallets, funds, or order paths:
   - Expand the bot container recorder mount `mp1` from `250G` to `300G`.
   - Stop only the affected Bot E recorder and dashboard during the active DB
     move.
   - Move the failed oversized Bot E DB set out of the active hot path under
     `data/recorder/bot_e_recorder_20260602T185637Z_failed_full.pending_offload/`.
   - Restart Bot E with a fresh active `bot_e_recorder.db`.
2. Add bulk storage for failed recorder segments:
   - Mount the homelab hypervisor `<bulk-storage>/ bot container` into the bot container at
     `/home/bot/polymarket-bot/data/recorder_archive`.
   - Offload the failed DB set with a low-priority background rsync service
     using `--remove-source-files` after successful copy.
3. Harden recorder storage:
   - Change `polymarket-storage-health.timer` from daily to hourly.
   - Tighten recorder storage critical threshold to `>90%` used or
     `<=20GB` free.
   - Add `polymarket-recorder-storage-guard.{service,timer}` every 15 minutes.
     On critical disk pressure it stops only
     `polymarket-bot-e-recorder.service`.
   - Add the same guard as `ExecStartPre=` on
     `polymarket-bot-e-recorder.service`, so the recorder cannot restart into
     a critical mount.
4. Fix the read-only wallet-tag report sandbox while clearing failed units:
   - Add the real external wallet-tag DB target to
     `polymarket-wallet-tag-forward-report.service` `ReadOnlyPaths`.

**Verification:**

- the bot container Bot E recorder restarted active with a fresh small active DB and fresh
  writer metrics.
- the bot container dashboard restarted active and `/api/overview` returned HTTP 200.
- the bot container storage-health timer and recorder-storage-guard timer are active.
- `polymarket-recorder-storage-guard.service` reported no criticals at about
  `82.73%` used and `51.82GB` free after the resize.
- `polymarket-wallet-tag-forward-report.service` reran successfully and wrote
  new forward report artifacts.
- the bot container `systemctl --failed` returned `0` failed units.
- VPS health check showed `longshot-crypto-recorder-vps-paper-feed.service`
  active, node-status service active, `0` failed units, root disk `74%` used,
  and recorder writer queue at `0` drops.

**Consequences:**

- A recorder disk-fill condition now degrades by stopping the Bot E recorder
  before it can exhaust the mount and destabilize the dashboard.
- Historical recorder tape is preserved on bulk archive storage instead of
  deleted.
- OQ-053 remains open: this is an emergency recovery and guardrail, not a full
  recorder rollover, retention, compression, or integrity-check design.
- The live-halt posture from ADR-183 remains unchanged.

**Rollback:**
If the guard misfires, inspect disk state first:

```bash
df -h /home/bot/polymarket-bot/data/recorder
systemctl status polymarket-recorder-storage-guard.service
journalctl -u polymarket-recorder-storage-guard.service -n 100 --no-pager
```

Then disable only the guard timer if confirmed false-positive:

```bash
sudo systemctl disable --now polymarket-recorder-storage-guard.timer
sudo systemctl reset-failed polymarket-bot-e-recorder.service
sudo systemctl restart polymarket-bot-e-recorder.service
```

Do not move archived DBs back into the hot recorder path unless there is a
separate maintenance-window integrity plan.

**Cross-refs:** ADR-168, ADR-171, ADR-183, OQ-053.

## ADR-189: Grok Build 2026-06-07 verify/harden (OQ-053 P0 guard+offload+health + OQ-123 P1 backfill + hygiene + doc updates)

**Date:** 2026-06-07
**Status:** accepted
**Owner:** Grok Build executed (read-only/dry + doc+stage); the operator for any follow-on host re-runs or OQ close.

**Context:**
Resuming on overhaul/2026-05-30-cleanup post Phase 0 + S465 recovery (ADR-188). Live fully paused (ADR-183/187). P0 priority: verify/harden new the bot container recorder storage guard (scripts/bot-host_recorder_storage_guard.py + units + ExecStartPre in bot-e-recorder.service + 15m timer + stop *only* e-recorder) + health (bot-host_storage_health.py hourly + 90%/20GB + forks) + offload (ad-hoc). P1: measurable on wallet Data API backfill (scripts/wallet_data_api_backfill.py dry default, classify vs main+persistence, dashboard accounting gap). P2 Bot D paper evidence, P3 OQ-109 ghosts. All constraints: no live/wallet/order/funds, ssh hypervisor-host timed out (env), used .venv/.subagent/terminal empirical + code pins + pre-snapshot (git status untracked guard), 15 focused tests, secret clean. Per AGENTS.md (direct, numbers, pin file:line, pre-mut snapshot, update MEMORY/CHANGELOG/ADR/OQ every session, no dead links).

**Decision:**
1. Accept current S465/ADR-188 state as verified (code matches spec at guard.py:42-52 (critical calc + conditional stop), bot-e-recorder.service:33 (ExecStartPre no-stop), systemd units timers, health.py:21-25/74-80; tests pass; VPS empirical active/fresh/0 failed; the bot container via docs/subagent).
2. Stage the 3 untracked recovery files (guard.py + .service/.timer) for resumable tree (pre-snapshot taken).
3. No logic harden needed (tests cover, only stops e-recorder, thresholds match, no wallet paths); OQ-053 remains open (per ADR-188:9777 "this is an emergency recovery and guardrail, not a full recorder rollover...").
4. P1: tooling confirmed (backfill.py:261-282 parser dry/overrides/gated-execute, 111-183 classifier token match + "unowned"/rebate/redeem status, 192-249 reporter summary owned/unowned/zero/rebates); dry runs executed (net reset 0s + fixture); gaps noted (classify bot heuristic weak, needs host re-run + unowned review; residual vs OQ-124); dashboard accounting object present at runtime_queries.py:2972-2982 (verbatim per fix: "OQ-123 pending — local DB(s) only until ... backfill table populated"; per-row at 1736 "local_only"; pending values per ADR-182 design until pop+review+join); deliver findings + OQ progress, no code extension (smallest, no risk). (Corrected post-review from "no full accounting ... (65-69)".)
5. P2/P3: located artifacts; ghost count 31/17; update relevant OQs (053/123/124/125/109/100/067/122/086/097) with 2026-06-07 progress/owner/evidence (run-spec numbers qualified); no new services.
6. Create this ADR-189; update MEMORY (top + prior), CHANGELOG (new top entry), open-questions.md (progress appends + header); no other files.
7. All changes pass focused tests (15/15), secret scan (0), ruff on touched py where applicable; git status reviewed post-stage.

**Verification (run-specific, pinned):**
- Tests: .venv/bin/python -m pytest ...test_bot-host_storage_health.py ...test_wallet_data_api_backfill.py ...test_wallet_reconcile_dryrun.py : 15 passed.
- Secret: python3 scripts/repo_secret_scan.py clean.
- Empirical: VPS ssh: 93% root, recorder active, 0 failed, db mtime current 54GB+747MB wal, qsize=0 drops (subagent + direct); the bot container ssh all timeout; backfill dry: WARNING reset, summary 0s, "dry_run_complete" (backfill.py:337); local guard/health sims rc match (2 on critical, stop only w/flag); bot_d main.db 0 (dev); subagent /tmp/storage-verify-the bot container-vps-20260603.md + oq123 one.
- Pins: ADR-188:9734-9751 (decision 1-4 verbatim), 9777-9778 (OQ-053 open), guard.py:16-17/47-49, health.py:74-80, open-questions.md:4219 (15m guard), bot_registry.py:102-109 (bot_d paper), 157-169 (ensemble), runtime_queries.py:2972-2982 (accounting object verbatim + 1732-1743 per-row recon), 85 (_freshness), backfill.py:140-174 (classify), 291 (execute gate). (Corrected post-review from 65-69.)
- Pre-mut: git status captured (M 4docs+health+3sys, ?? 3 recovery); git add done.
- Post: staged A for recovery; docs edits; no dead links (cross checked in updates); 0 live paths touched ever.

**Consequences:**
- OQ-053/123/109/ Bot D gates remain open with fresh evidence (run-spec); no close.
- Tree now tracks the guard (resumable).
- New ADR-189 per rules; cross-refs ADR-188/183/187, OQ-053/123/124/125/109/100/067/122.
- Live-halt (ADR-183) + paper trim (187) + storage (188) posture unchanged.

**Rollback:**
Revert docs edits (git checkout -- MEMORY.md CHANGELOG.md docs/decisions-log.md docs/open-questions.md); git reset HEAD -- the 3 staged recovery (if want untracked again, but not recommended); no host change possible from this.

**Cross-refs:** ADR-188, ADR-183, ADR-187, OQ-053, OQ-123, OQ-124, OQ-125, OQ-109, OQ-100, docs/reports/project-overhaul-plan-2026-05-30.md, /tmp/storage-verify-the bot container-vps-20260603.md, /tmp/oq123-progress-audit-20260603.md (subagents), MEMORY/CHANGELOG this session.

## ADR-190: Handoff to Claude Fable-5 for creative MAX profitability research (current bots DEAD / weather intermittent)

**Date:** 2026-06-07
**Status:** accepted
**Owner:** the operator (directive); Claude (Fable 5 via router) executes research; Grok Build prepared context + prompt.

**Context:**
Post S465 storage recovery (ADR-188) + S466 Grok Build verify (P0 guard code+empirical match, P1 OQ-123 tooling + review fix for accounting surface accuracy at runtime_queries.py:2972-2982, P2 Bot D paper location, P3 OQ-109 31/17 ghosts). All non-weather lanes DEAD/archived per ADR-187 (G variants, F, J/K, spike-short, WC, crypto FV paper). Bot D (only prior positive live evidence per S462 +11%+ on tiny probe) intermittent per operator (small forward samples, 0 wins on E/E2 spikes per strategy-e2 Murphy -24% CI fail +0 wins, outlier dependence per bot-d-full-review-audit 2026-05-09 ex-largest negative paper). OQs 123/124/053/125/067/122/100 still block P&L trust or scale. Data moat rich (large recorder, wallet/maker observers, reports, backtests) but no current lane at scale. Directive: use Fable 5 (creative/long-context model via ~/.claude/scripts/model_call.py or models.yaml) for deep, empirical, creative exploration of new edges/ideas for MAX profitability (not just tune current dead lanes).

**Decision:**
1. Create and deliver self-contained handoff prompt (docs/prompts/claude-fable5-max-profitability-creative-edges-2026-06-07.md) incorporating full context from >20 tool calls (canonical files, reports, bot_d code, DB stats, historical numbers, constraints from AGENTS/Claude.md/active-model/ADRs/OQs).
2. Instruct Claude (Fable 5): get creative (propose hybrids e.g. weather + wallet_tag profitable suffixes, maker in weather cheap, persistence revival, new cheap tails with recorder features + Becker, synthetic forecast error injection for robustness, ensemble + dispute risk, data moat expansion with new free sources + harness); always empirical (replays/backtests on existing recorder/main.db/wallet_tag/maker data first, forward paper validation); respect pause (paper/research only; no live/wallet without new ADR + explicit approval); solo scale (tiny $1-2 entries, small daily gross/open caps, hard kills); unblock OQs first (esp 123 for accounting truth before any P&L claim); output structured (3-5 prioritized ideas with backtest plan, risk sizing for ~$150 wallet, data moat contribution, new OQ/ADR drafts, kill gates, why MAX vs current intermittent/DEAD).
3. Update MEMORY/CHANGELOG with handoff closeoff (S466 summary + state + prompt location). No code changes beyond closeout hygiene.
4. All per non-neg: no live, privacy (local or public docs only), dates/ADRs/OQs/MEM/CHLOG, secret clean, git reviewed.

**Verification (run-specific):**
- >20 tool calls executed (reads of MEMORY/CHANGELOG/active/OQ/decisions/reports (bot-d-full, strategy-e2, live-services, external-fit, overhaul), bot_d_weather/*.py (strategy/executor/config/ensemble/weather_fetcher/labels/discovery), core/bot_registry, AGENTS/Claude.md, existing prompts; greps for weather/ROI/edge/OQs; run_terminal for secret/git/DB sizes/tables (bot_e 462M, main 136K, wallet_observer 32M; trades/positions/events/markets tables); fable discovery (configs/router greps); list_dir reports + bot_d_weather).
- Prompt created with rich excerpts (active-model tables, ADR-183/187/188/189 verbatim, OQ-123/053/067/122 numbers, historical +11% live probe / -24% E2 / ex-outlier negatives, data assets).
- Closeout: MEMORY/CHANGELOG/ADR-190 (this), OQs touched (handoff note), secret 0, git M + A reviewed.
- No live/wallet/funds; read-only research posture.

**Consequences:**
- Shifts from maintenance/verify (S465/466) to creative max-profit sprint while paused.
- OQ-123/124 remain first gate for any future live consideration; new ideas must propose how they advance data moat or unblock.
- Fable 5 (strong synthesis model) suited for idea generation + cross-report synthesis; pair with fast models for code/DB probes per routing.

**Rollback:**
git checkout -- MEMORY.md CHANGELOG.md docs/decisions-log.md docs/open-questions.md; rm docs/prompts/claude-fable5-max-profitability-creative-edges-2026-06-07.md if needed.

**Cross-refs:** ADR-189 (S466), 188/187/183, OQ-123/124/053/067/122/100/109/125, docs/prompts/claude-fable5-... prompt, MEMORY/CHANGELOG 2026-06-07 handoff, active-operating-model, all bot_d reports + recorder stats.

## ADR-187: Execute approved paper-lane pause/archive packet

**Date:** 2026-05-26
**Status:** accepted
**Owner:** Codex executed after explicit the operator approval

**Context:**
After the 2026-05-26 fleet profitability audit and Grok comparison, the operator
approved the recommended pause/archive packet for unprofitable, falsified, or
evidence-blocked paper lanes. The live fleet was already halted under ADR-183;
this decision does not restart or touch any live order path.

**Decision:**
Stop and disable the approved paper-only services/timers:

1. the bot container:
   - `polymarket-bot-f-momentum-paper.timer`
   - `polymarket-wc-negrisk-basket-paper.timer`
   - `polymarket-bot-g-prime-live-maker-paper.service`
   - `polymarket-bot-g-prime-shadow-maker-paper.service`
   - `polymarket-bot-g-prime-high-tail-maker-paper.service`
   - `polymarket-bot-j-nr-wallet-paper.service`
   - `polymarket-bot-k-sports-taker-paper.service`
2. VPS:
   - `polymarket-bot-g-prime-shadow.service`
   - `polymarket-bot-g-prime-high-tail.service`
   - `polymarket-bot-d-spike-short-vps.service`
   - `polymarket-bot-d-spike-daily-report-vps.timer`

Archive the falsified/dead lanes in the local registry:
`bot_f_momentum_paper`, `wc_negrisk_basket_paper`,
`bot_d_spike_short`, `bot_g_prime_shadow`, `bot_g_prime_high_tail`, and the
stopped Bot G maker shadows. Mark `bot_j_nr_wallet` and
`bot_k_sports_taker` as paused because their issue is unresolved forward
sample quality rather than a fully falsified thesis.

**Verification:**

- Targeted the bot container units reported inactive/disabled after the stop.
- Targeted VPS units reported inactive/disabled after the stop.
- the bot container Bot E recorder, Bot H maker recorder, Wallet Observer, dashboard,
  watchdog, and wallet-tag forward/resolution timers remained active.
- VPS crypto recorder remained active.
- Both hosts reported `0` failed systemd units.

**Consequences:**

- Dashboard/systemd active inventory no longer treats the stopped lanes as
  current active paper research.
- Historical DB rows remain preserved for audit and replay.
- Re-enabling any archived lane requires a fresh thesis, a new ADR, and
  explicit the operator approval if it changes runtime posture.

**Rollback:**
For a mistakenly stopped unit, run:

```bash
sudo systemctl enable --now <unit-or-timer>
sudo systemctl status <unit-or-timer>
```

Use the the bot container path through `pct exec <ctid> --` from `hypervisor-host` for the bot container units; use
`sudo systemctl` on `the-vps` for VPS units.

**Cross-refs:** ADR-183, ADR-185, ADR-186, OQ-113, OQ-114, OQ-123, OQ-124.

## ADR-185: Complete fleet-wide audit and unprofitable lanes shutdown

**Date:** 2026-05-26
**Status:** accepted
**Owner:** Codex / the operator for implementation approval

**Context:**
A comprehensive fleet-wide audit of all live, paper, and recorder lanes was completed. The live hot wallet holds approximately $151.47 pUSD and $16.15 in resolved weather positions, totaling $167.62, with all live trading currently paused under ADR-183. The audit evaluated realised P&L, ROI on resolved capital, open exposure, fills, sample size, largest-win concentration, live-transfer realism, paper fill credibility, and current market conditions.

The audit found:
1. Only the Weather Fade (Bot D) family has demonstrated positive live realized P&L and ROI (+$31.06 realized, 11.07% ROI on 95 closed groups).
2. All other live/paused lanes (Bot G Prime Live, Bot I, FV live makers) are deeply negative or suffer from toxic adverse selection and execution issues.
3. Multiple paper research lanes (Crowd Momentum F, G Late Cheap, G Take Profit, WC negRisk Basket, Weather Spike Short) have either failed their gates, had their core theses falsified at decisive sample sizes, or are running in structurally dead arbitrage corners (e.g. negRisk basket arb which is now 100% fee-gated or illiquid).

**Decision:**
1. Formally retire and shut down the following unprofitable or falsified paper/research lanes:
   - `bot_f_momentum_paper` (Crowd Momentum F): 0 entries after 1,519 runs.
   - `bot_g_prime_late_cheap` (Late Cheap G): -86.4% ROI, thesis falsified.
   - `bot_g_prime_take_profit` (Take Profit G): -67.5% ROI, TP never hit (0/26 in replay).
   - `wc_negrisk_basket_paper` (negRisk Basket): 0 real arbs after cumulative-threshold and field gates.
   - `bot_d_spike_short` (Spike Short paper): negative performance, ex-outlier ROI is negative.
2. Stop and disable the corresponding systemd services/timers on the bot container and VPS.
3. Keep the shared data recorders (Bot E Crypto Recorder, VPS Crypto Feed, Bot H Maker Recorder, Wallet Observer) active as R0 data-only infrastructure.
4. Keep the high-quality weather paper benchmarks (`bot_d`, `bot_d_source_shadow`, `bot_g_prime` / shadow regime monitors, `bot_i_persistence` paper) running for ongoing research.
5. All live trading remains paused. Any future restart of a tiny-live probe (such as a tightly capped `$1` Weather Fade D packet) is strictly gated by the resolution of OQ-123 (wallet backfill/accounting reconciliation) and a new explicit the operator approval.

**Consequences:**
- De-clutters the systemd service inventory and reduces CPU/memory footprint.
- Formally archives five falsified or dead-thesis lanes in `core/bot_registry.py` and the active operating model.
- Prevents future capital allocations or operational overhead on unprofitable corners.
- Rollback: Re-enable timers or services if a new ADR proposes a fresh, robust thesis with backtest proof.

**Cross-refs:** ADR-183, ADR-181, OQ-067, OQ-086, OQ-097, OQ-119, OQ-123.

## ADR-191: Full reassessment 2026-07 verdict: C1 primary, C2 runner-up

**Date:** 2026-07-20
**Status:** accepted
**Owner:** Grok report writer (Session 468); the operator for any live or capital change

**Context:**
Director-led Polymarket full reassessment (2026-07). Analysis complete in an evidence pack compiled 2026-07-20. Prior fleet posture: live halt (ADR-183), paper archive of falsified lanes (ADR-185/187), Bot I paused during loss reassessment (ADR-181), Bot A archived after walk-forward failure (ADR-033), crypto FV archived (ADR-139). Only positive live P&L ever recorded is Bot D weather range-fade. Session constraints: the bot container offline (no SSH), old the VPS provider VPS decommissioned (Session 466), Polymarket geo-blocked from UK machines, no code/runtime mutation in this write session.

**Decision:**
1. **PRIMARY research path = C1 sports mid-band NO-fade** (buy NO when sports YES is 55–75c, 6–78h pre-close). Research-first only: WANGZJ multi-month replay with locked sports taxonomy and fee-exact P&L before any paper lane. Local re-verification cited in pack: n=573, hit 57.4% vs 63.5c implied, NO-fade ROI +5.32% post-fee (orig +9.22%), bootstrap 95% CI [-4.73%, +15.64%] (crosses zero).
2. **RUNNER-UP = C2 weather range-fade NO restart (Bot D).** Sole positive live evidence: +$31.06 / +11.07% ROI / 95 closed groups. Restart path gated on closing OQ-123/124 accounting. No live without explicit the operator approval.
3. Rank C4 (elite cheap-tail co-sign) as filter-only; C3 as autopsy-only under ADR-192; C5 blocked under ADR-193; C6 infra under ADR-194.
4. 30/60/90 roadmap sized to $2k research/ops; any live step requires the operator approval, new ADR, and $137 current funding note.
5. Canonical write-up: `docs/reports/full-reassessment-2026-07.md`.

**Consequences:**
- Resource allocation shifts from dead taker-tail and maker-live lanes to C1 multi-month sports validation plus C2 accounting unblock.
- Paper/live registration of C1 still requires a future ADR after OQ-127-class gates PASS.
- ADR-183 live halt unchanged.

**Rollback:**
Supersede with a new ADR if WANGZJ FAIL archives C1 or if the operator redirects capital priority.

**Cross-refs:** ADR-033, ADR-139, ADR-176, ADR-181, ADR-183, ADR-185, ADR-187, ADR-192, ADR-193, ADR-194, OQ-123, OQ-124, OQ-127, OQ-128, OQ-129, OQ-130, docs/reports/full-reassessment-2026-07.md, docs/reports/strategy-ranking-and-data-roadmap-2026-05-09.md, docs/reports/creative-edge-mining-2026-06-09.md.

## ADR-192: C3 stale-quote-mirage presumption + pre-registered permanent kill

**Date:** 2026-07-20
**Status:** accepted
**Owner:** Research (Claude/Codex autopsy); the operator if any reopen beyond research is proposed

**Context:**
Canary tape (58G, 2026-05-13→07-05) last-minutes calibration shows large mid-gaps at T-1min when CEX is ≥10bps beyond strike (PM 0.76–0.79 vs realized 1.00, +17–24pp on n=26+15; pack also +23.7pp n=26 at 10–20bps and +20.6pp n=15 at ≥20bps). Latency medians (520ms) do not prove fillability. 357/1271 windows processed; 509 skipped dead books (selection bias). Near-resolution crypto scalping is on the project kill-list / out-of-scope posture historically.

**Decision:**
1. Treat the fresh C3 calibration gap as a **stale-quote mirage presumption** until a **fill-conditioned** replay on the existing canary tape proves executability.
2. C3 is **research autopsy only**. It does **not** reopen the near-resolution kill-list line.
3. **Pre-registered permanent kill:** if fill-conditioned ROI **≤ 0** on **n ≥ 200** executable windows, archive C3 permanently (no paper, no live, no kill-list reopen).
4. Autopsy ownership and acceptance criteria tracked in OQ-131.

**Consequences:**
- Prevents promoting mid-only gaps into a paper or live lane.
- Forces the same fill-conditioned honesty standard that killed naive maker paper optimism (see ADR-193).

**Rollback:**
Only a new ADR after a documented fill-conditioned PASS with executable n≥200 and the operator approval could reopen research scope; still would not auto-authorise live.

**Cross-refs:** ADR-033, ADR-139, ADR-183, ADR-185, ADR-187, ADR-191, OQ-131, docs/reports/full-reassessment-2026-07.md.

## ADR-193: C5 maker reopen blocked behind fill-conditioned replay gate

**Date:** 2026-07-20
**Status:** accepted
**Owner:** Research; the operator for any future live maker packet

**Context:**
Maker paper historically printed +10–15% class optimism while live maker probes lost money twice (-$63.25, -$104.05). Canary fill reality on 202k+ prints: at-touch 61–83% by asset (BTC 83.2%), trade-through only 1.2–4.0% — adverse-selection fills explain the paper/live gap. Prior controls already blocked under-sized maker live (ADR-176) and archived crypto FV maker/taker paths (ADR-139); fleet shutdowns in ADR-185/187.

**Decision:**
1. **C5 maker lanes remain rejected for now** — no new maker paper promotion and no maker live.
2. **Reopen research only** if a fill-conditioned replay on recorded tape **reproduces the live loss class** and then isolates a cell with executable positive after adverse-selection conditioning.
3. Live maker remains separately gated by the operator + new ADR even after any research PASS (ADR-183 still applies).
4. This gate is stronger than paper ROI alone; paper +10–15% is insufficient evidence.

**Consequences:**
- Stops re-opening maker lanes on paper optimism.
- Aligns maker policy with C3 fill-conditioned discipline.

**Rollback:**
New ADR after fill-conditioned PASS evidence is written into a dated report and the operator approves the research reopen scope.

**Cross-refs:** ADR-139, ADR-176, ADR-183, ADR-185, ADR-187, ADR-191, docs/reports/full-reassessment-2026-07.md.

## ADR-194: Approve small the VPS provider VPS (~EUR 5–8/mo) for recorder + calibration harvester

**Date:** 2026-07-20
**Status:** accepted
**Owner:** the operator provisions; implementers deploy recorder/harvester only

**Context:**
Session 466 decommissioned the prior the VPS provider VPS after capturing the 58G canary recorder to the local workstation. the bot container is offline this reassessment. Polymarket endpoints are geo-blocked from reachable UK machines. C1 sports validation and OQ-129 calibration harvest need a continuous, cheap sample factory outside the UK geo-block. This is infrastructure, not an edge (candidate C6).

**Decision:**
1. **Approve** a new small the VPS provider VPS at approximately **EUR 5–8/mo** (low CPU acceptable).
2. Allowed roles only: **recorder** + **daily calibration-tape harvester** (sample factory for C1; honest re-test bench for C3/C4).
3. **Not approved** on this ADR: live order placement, wallet automation, keystore deploy, or any bypass of ADR-183.
4. Retention/storage for large tapes remains governed by OQ-053 and new OQ-133 (canary.db policy); VPS must not disk-fill without guards.

**Consequences:**
- Restores post-466 data-plane optionality at low monthly cost.
- Unblocks remote harvest needed for multi-month C1 proof under geo-block.

**Rollback:**
Cancel the VPS in the the VPS provider console if unused for 30 days or if cost exceeds value; capture data first (Session 466 pattern).

**Cross-refs:** ADR-183, ADR-188, ADR-191, OQ-053, OQ-129, OQ-133, docs/reports/full-reassessment-2026-07.md, CHANGELOG Session 466.

---

The decision log ends with the 2026-07 full reassessment (ADR-191..194).
The project was retired and open-sourced as this repository shortly after.
