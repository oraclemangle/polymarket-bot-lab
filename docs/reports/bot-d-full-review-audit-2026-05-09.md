# Bot D Full Weather-Family Review Audit

**Date:** 2026-05-09
**Scope:** `bot_d`, `bot_d_live_probe`, `bot_d_spike`, `bot_d_spike_short`
**Mode:** Read-only audit plus dashboard/status truth and telemetry-label fixes. No trading services restarted, no order placed, no live cap/size/city/threshold changed.

## Executive Verdict

**Bot D live probe is still the best near-term weather/live candidate.** It has `70` live trade rows, `30` closed matched live trade groups, `22/30` wins, `+$11.24` realised live P&L, `+11.68%` ROI on matched closed cost, and `+7.44%` ROI after removing the two largest wins. That clears the "is this real live plumbing?" hurdle, but it is not a full live-readiness pass because the sample is tiny-dollar, the source-lag/resolution-label panel is incomplete, and the NWS-outlier probe has only `6/10` required entries.

**Do not scale yet.** The next profit/ROI/speed action is evidence discipline, not a size bump: keep the `5` share live probe running, fix dashboard truth, let `bot_d.forecast_resolution` labels accumulate, and review the next `30-50` closed live positions by source/tier/NWS-outlier flag.

**Follow-up after top-3 actions:** the bot container and VPS dashboard/status truth are now fixed, and the source-resolution label gap is no longer zero. The one-shot backfill wrote `87` `bot_d.forecast_resolution` labels for `bot_d` and `87` for `bot_d_live_probe`. Current `/api/bot-d` now shows live probe `+$12.73` realised P&L, `31` closed groups, `23` wins, `6` open positions, `0` open orders; Spike `-$10.00` on `5` closed with `7` open; Spike Short `-$8.00` on `4` closed with `2` open.

**Follow-up after approved telemetry restart:** Restarted only
`polymarket-bot-d.service`, `polymarket-bot-d-live.service`, and
`polymarket-dashboard.service` to pick up telemetry/dashboard code. Services
returned active. First post-restart scan logged `1` new
`bot_d.forecast_resolution` label per Weather Fade process and the new
`bot_d.gribstream_call` events. No live cap, size, city, threshold, or source
ordering was changed.

## Lane Status

| Lane | Service | Status | Mode | Current P&L | Orders | Fills / trades | Closed | Open pos | Latest activity | Gate | Verdict |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| `bot_d` | `polymarket-bot-d.service` | active, not halted | paper | dashboard epoch `+$64.96`; DB all-time matched `+$1,197.38` | `120` DB total; `32` dashboard epoch | `167` DB trades; `15` dashboard fills | `75` matched trade groups / `76` closed positions | `4` positions, `$94.16` cost; `16` open paper orders | last trade `2026-05-09 14:15 UTC`; latest scan `14:42 UTC` | blocked by outlier robustness and stale paper state | paper evidence only; not live-proof |
| `bot_d_live_probe` | `polymarket-bot-d-live.service` | active, not halted | live tiny probe | `+$11.24` realised dashboard; matched closed `+$11.24`; cash P&L `-$9.33` due open cost | `71` total | `70` live trade rows; `13` in 24h | `30` matched closed groups; `31` closed positions | `6` positions, `$19.58` cost; `0` open orders | last buy `2026-05-09 14:13 UTC`; last TP sell `2026-05-09 01:04 UTC` | 30 closed achieved; NWS-outlier `6/10`; source labels `0` | continue tiny live; no scale yet |
| `bot_d_spike` | `polymarket-bot-d-spike.service` on VPS | active, not halted | paper Strategy E | `-$10.00` realised paper | `12` | `17` trade rows | `5` closed, `0` wins | `7`, `$14.00` cost | last entry `2026-05-09 04:50 UTC` | `5/200` closes, `0/90` days complete | sample useful but currently negative; keep paper-only |
| `bot_d_spike_short` | `polymarket-bot-d-spike-short-vps.service` on VPS | active, not halted | paper Strategy E2 | `-$8.00` realised paper | `6` | `10` trade rows | `4` closed, `0` wins | `2`, `$4.00` cost | latest close `2026-05-09 15:14 UTC` | `4/200` closes, `0/90` days complete | sample useful but currently negative; keep paper-only |

## P&L Separation

| Lane | Realised / paper basis | Open mark basis | Key caution |
|---|---:|---:|---|
| `bot_d` | dashboard epoch `+$64.96`; all-time matched `+$1,197.38` | `$94.16` open cost plus `16` open paper orders | All-time profit is dominated by one Lagos outlier. Ex-largest-one ROI is `-21.77%`; ex-largest-two ROI is `-30.28%`. |
| `bot_d_live_probe` | `+$11.24` realised live; `+11.68%` closed ROI | `$19.58` open cost; cash P&L `-$9.33` because open buys are not settled | Dashboard now correctly shows realised live P&L, not open-cost drawdown. |
| `bot_d_spike` | `-$10.00`, `-100%` on `5` closed | `$14.00` open cost | Longshot YES strategy expects many losses; current sample is too small to reject, but there is no forward proof yet. |
| `bot_d_spike_short` | `-$8.00`, `-100%` on `4` closed | `$4.00` open cost | Same as above; no forward proof yet. |

## Evidence / Edge

| Lane | Edge thesis | Evidence strength | Best supporting evidence | Weak / contradicted evidence | Robustness checks | Data gap | Decision |
|---|---|---|---|---|---|---|---|
| `bot_d_live_probe` | Buy NO on narrow station-resolved ranges when source stack and market odds disagree. | **B** | `31` matched closed live groups, `23` wins, `+$12.73` realised P&L. `87` source-resolution labels now exist for source/tier slicing. | Small dollar sample; `42` `place_failed:PolyApiException` attempts in the earlier audit window; `6` open positions unresolved; NWS-outlier entries still below the `10` target. | Earlier ex-largest-one `+9.35%`; ex-largest-two `+7.44%`; no dashboard ledger pollution found. | Source-visible lag fields still null; GribStream credit telemetry still absent. | Continue tiny live unchanged. Re-audit at `50-60` closed live groups or after NWS-outlier reaches `10`. |
| `bot_d` paper Weather Fade | Paper shadow of Weather Fade / station-v1 lane. | **D** for live proof | Aligned data stack with live: GribStream enabled, NOAA NBM enabled, NWS fallback blocked, API-agreement probe enabled. Latest scan fresh and active. `87` source-resolution labels now exist. | All-time paper profit fails outlier robustness; `16` stale paper open orders; paper sizing `$25` order chunks is not comparable to 5-share live. | All-time ROI `+47.46%`, but ex-largest-one `-21.77%`, ex-largest-two `-30.28%`. | Paper/live order mechanics differ. | Keep as a shadow/comparison lane, but do not use paper P&L to justify live scaling. Clean stale paper state separately. |
| `bot_d_spike` Strategy E | 6h-12h cheap-YES weather buckets in positive-EV cities. | **C/D** | Historical WANGZJ slice was promising; forward bot now fills real paper markets: `12` entries, TTR `7.15-12.00h`, cities Shanghai/HK/Seoul/Ankara/NYC. | Forward closed sample is `0/5`, `-$10`; no winner captured yet. | Gates and city/TTR/price filters are obeyed; no live writes. | Needs `200` closed or `90` days; current `5/200`. | Keep paper-only; do not tune on first-day losses. |
| `bot_d_spike_short` Strategy E2 | 0h-6h cheap-YES weather buckets in same city universe. | **C/D** | Forward bot fills the intended short window: `6` entries, TTR `1.79-5.59h`, cities London/Madrid. | Forward closed sample is `0/4`, `-$8`; current sample is too London-heavy. | No overlap violation seen; no live writes. | Needs `200` closed or `90` days; current `4/200`. | Keep paper-only; review after at least `30` closes, hard decision at `200`/`90d`. |

## Source, Station, Rounding, Freshness

- Station anchoring is correct for the active Weather Fade lanes: current payloads show exact station matches such as `NYC -> KLGA`, `Chicago -> KORD`, `Miami -> KMIA`, `London -> EGLC`, with `settlement_source=wunderground`, `settlement_rounding=nearest_int`, and `settlement_verified=true`.
- Latest Weather Fade scans are fresh. At `2026-05-09 14:42 UTC`, paper had `17` raw / `11` kept / `11` evaluated; live had `17` raw / `11` kept / `11` evaluated. Both had `missing_forecasts=0`.
- Current forecast source mix is mostly NOAA NBM with sparse GribStream: latest live scan had `forecast_sources={"gribstream_nbm": 1, "noaa_nbm": 10}`. Live entries all-time split: `multi_model=24`, `noaa_nbm=17`, `gribstream_nbm=4`.
- NWS fallback remains blocked in live. Recent live attempt skip reasons include `238` `nws_fallback_entry_blocked`; no live forecast-entry source was `nws_fallback`.
- The source monitor works but is incomplete for final settlement lag. `bot_d.source_snapshot` rows exist (`1,606` live snapshots in 24h), but `source_visible_timestamp` and `source_lag_seconds` are still null in sampled rows.
- Weather resolution joins are now working for completed recent source snapshots: `bot_d.forecast_resolution` count is `87` for `bot_d` and `87` for `bot_d_live_probe` after the 2026-05-09 backfill. Ongoing emission still needs the trading services to pick up the deployed entrypoint on their next approved restart.
- GribStream call-credit telemetry is now in the DB/dashboard. First
  post-restart scan logged combined paper+live usage of `8` HTTP calls
  (`4` live, `4` paper), `0` errors, `254` returned rows, and `10` date
  forecasts across Chicago, London, Miami, and NYC.

## First Source/Tier Review

This is diagnostic only: `44` live forecast-entry conditions, `87` source
labels, and `31` closed trade lots is not enough for a size increase.

| Slice | Entries | Labelled | Closed | Wins | P&L | ROI | Read |
|---|---:|---:|---:|---:|---:|---:|---|
| `multi_model` | `24` | `7` | `16` | `11` | `+$5.84` | `+12.16%` | positive, still best-proven source |
| `noaa_nbm` | `16` | `9` | `10` | `8` | `+$7.48` | `+23.88%` | positive so far |
| `gribstream_nbm` | `4` | `1` | `4` | `3` | `-$1.72` | `-10.34%` | watch item; too small to disable |
| Tier `A` | `12` | `3` | `8` | `6` | `+$0.16` | `+0.54%` | roughly flat |
| Tier `B` | `27` | `12` | `19` | `16` | `+$16.44` | `+26.56%` | currently carrying the edge |
| Tier `C` | `5` | `2` | `3` | `0` | `-$5.00` | `-100.31%` | avoid loosening into C-tier until proven |
| NYC | `13` | `1` | `9` | `8` | `+$11.62` | `+42.32%` | strongest city so far |
| Seattle | `10` | `5` | `7` | `3` | `-$6.40` | `-30.21%` | main weak city cluster |
| NWS-outlier probe | `6` | `2` | `5` | `3` | `+$0.27` | `+1.93%` | positive but weaker than normal lane |

Decision from this review: keep live probe at `5` shares; do not loosen into
C-tier or scale GribStream entries. The next profitable action is to collect
another `20-30` closed live lots and then repeat this split.

## Dashboard Truth

Checked `/api/bot-d` and `/api/overview` on the bot container.

What is true now:
- `/api/overview` separates live (`bot_d_live_probe`) from paper (`bot_d`, `bot_d_spike`, `bot_d_spike_short`).
- `/api/bot-d.live_probe.simple.pnl_usd` is realised live P&L and includes `pnl_note="realised live P&L"`.
- `/api/bot-d.live_probe.simple.cash_pnl_usd` remains available and shows open-buy cash drag separately.

What I fixed locally:
- `spike.simple` and `spike_short.simple` were service-correct but metric-wrong: nested `simple` still showed the bot container zeros while top-level and `/api/overview` used VPS truth. The API now maps VPS orders/fills/open positions/realised paper P&L into the nested `simple` block too.
- Source Edge was showing live-probe station snapshots at the top level without a visible lane label. The API now also exposes the same block under `live_probe.source_edge`, and the Bot D tab subtitle includes the source-edge `bot_id`.
- The VPS status bridge itself also under-reported Spike realised P&L as `$0.00`. A local patch now computes closed matched paper P&L by `condition_id` inside `scripts/vps_node_status.py`.

Deploy status:
- the bot container dashboard API/UI patch was deployed and `polymarket-dashboard.service` was restarted; the dashboard service returned `active`.
- VPS `scripts/vps_node_status.py` was deployed through PVE as a jump host and `data/reports/vps_node/latest.json` was regenerated. `/api/bot-d` now reports Spike realised paper P&L correctly: Spike `-$10.00` on `5` closed; Spike Short `-$8.00` on `4` closed.

## Gate Progress

| Gate | Current | Required | Read |
|---|---:|---:|---|
| Live probe closed matched groups | `30` | initial `20`, next review `50-60` | first proof achieved; still small-dollar |
| Live probe ex-top-two ROI | `+7.44%` | positive | passes current robustness read |
| Live NWS-outlier entries | `6` | `10` | still collecting |
| Live open positions | `6` | cap `20` | far below cap |
| Live open exposure | `$19.58` | cap `$150` | far below cap |
| Live daily gross | latest dashboard cap was well below `$100`; recent trades `13` in 24h | cap `$100` | not cap-bound |
| Paper Weather Fade outlier robustness | `-30.28%` ex-top-two | positive before live inference | fails |
| Strategy E closes | `5` | `200` or `90d` | 2.5% complete |
| Strategy E2 closes | `4` | `200` or `90d` | 2.0% complete |
| Forecast-resolution labels | `87` paper / `87` live probe | at least one station/lead bucket `>=30` labels | initial label gate unblocked; source-lag still blocked |
| Source-lag telemetry | null visible lag | populated lag rows | source-lag edge blocked |

## Next Actions

| Priority | Action | Lane | Why | Expected benefit | Time to resolve | Risk | Approval needed? |
|---:|---|---|---|---|---|---|---|
| 1 | Deploy the dashboard truth patch and restart only `polymarket-dashboard.service`. | dashboard | Removes misleading spike nested-zero metrics and labels source-edge lane. | Operator sees correct live/paper/VPS truth. | 10 min | Low; dashboard only | No trading approval needed |
| 2 | Deploy VPS status bridge P&L fix when VPS SSH is reachable, then regenerate `data/reports/vps_node/latest.json`. | dashboard / VPS status | Spike realised P&L is currently stale-zero in the bridge JSON. | Corrects `/api/bot-d` and `/api/overview` realised P&L for Spike lanes. | 10 min once reachable | Low; read-only status script | No |
| 3 | Keep `bot_d_live_probe` at 5 shares until `50-60` closed groups, then rerun source/tier/outlier ROI report. | live probe | B-tier is strong, but GribStream and Seattle are weak in tiny samples. | Decides whether 10-share bump is justified by realised data. | 3-10 days | Low | Yes for any later size bump |
| 4 | Add a live min-notional pre-check for very cheap fixed-share orders. | live probe | Restart exposed repeated CLOB rejects at `5` shares × `4.2c` = `$0.21`, below CLOB's marketable-buy minimum. | Reduces noisy failed API calls and makes rejection telemetry cleaner. | 1 session | Low; blocks impossible orders only | No strategy approval if implemented as exchange-min guard |
| 5 | Add final-source/Wunderground lag poller. | Weather Fade | Source-lag edge is the most relevant weather moat but not measured yet. | Tests late-day finalization edge directly. | 1-3 sessions | Medium scraper fragility | No live-trading approval |
| 6 | Add final-source/Wunderground lag poller. | Weather Fade | Source-lag edge is the most relevant weather moat but not measured yet. | Tests late-day finalization edge directly. | 1-3 sessions | Medium scraper fragility | No live-trading approval |
| 7 | Let Spike and Spike-Short run unchanged to `30` closes before any tactical review. | spike lanes | First closes are losses, but longshot YES strategy is high variance. | Avoids overfitting the first day. | days-weeks | Low paper-only | No |
| 8 | Clean stale `bot_d` paper open orders separately. | paper Weather Fade | `16` stale paper orders pollute readiness/reporting. | Cleaner paper dashboard and readiness report. | 30 min | Low paper-only | No |

Completed follow-up:
- Action 1 completed on the bot container.
- Action 2 completed on VPS via PVE jump host.
- Action 5 initial blocker fixed: recent completed source snapshots now
  backfill source-resolution labels. The first source/tier split is included
  above; next step is sample accumulation, not a trading-parameter change.
- GribStream telemetry action completed and visible in `/api/bot-d`.

## Commands And Queries Used

- the bot container services: `systemctl is-active polymarket-bot-d.service polymarket-bot-d-live.service polymarket-dashboard.service`; `systemctl list-units '*bot-d*'`; `systemctl list-timers '*bot-d*'`.
- VPS services: `systemctl --type=service --all | grep -E 'bot-d|spike|weather'`; `systemctl list-timers '*bot-d*'`.
- Dashboard APIs: `curl http://127.0.0.1:8090/api/bot-d`; `curl http://127.0.0.1:8090/api/overview`.
- the bot container DB read-only-style ORM queries over `Order`, `Trade`, `Position`, `Event`, `HaltFlag` grouped by `bot_id`.
- VPS DB ORM queries over `Order`, `Trade`, `Position`, `Event`, `HaltFlag` for `bot_d_spike` and `bot_d_spike_short`.
- Systemd unit inspection: `systemctl cat polymarket-bot-d.service`, `polymarket-bot-d-live.service`, redemption timer/service, `polymarket-bot-d-spike.service`, and `polymarket-bot-d-spike-short-vps.service`.
- Existing reports reviewed: `bot-d-post-mortem-2026-05-07.md`, `wangzj-cheap-yes-weather-calibration-2026-05-07.md`, `strategy-e2-weather-cheap-yes-2026-05-08.md`, `bot-d-emos-shadow-benchmark-2026-05-08.md`, `bot-d-emos-nws-observation-join-2026-05-08.md`, and `bot-d-spike-deployment-audit-2026-05-07.md`.

## Bottom Line

`bot_d_live_probe` is working and profitable on realised live micro-size data. It is **not ready to scale** until source/tier/outlier evidence is separated and the open-resolution sample grows. The two spike bots are doing their job as paper data collectors, but the forward samples are currently negative and tiny. The main paper Weather Fade lane is useful as a shadow, not as proof, because its historical P&L is contradicted by outlier removal.

## Verification

- `./.venv/bin/python -m pytest -q tests/test_bot_d_spike.py tests/test_bot_d_spike_report.py tests/test_bot_registry.py tests/dashboard/test_dashboard.py` -> `39 passed`.
- `./.venv/bin/python -m py_compile dashboard/runtime_queries.py scripts/vps_node_status.py` -> passed.
- `node --check dashboard/static/app.js` -> passed.
- `./.venv/bin/python scripts/repo_secret_scan.py` -> passed.
- `git diff --check` -> passed.
- the bot container post-dashboard deploy health: `polymarket-bot-d.service`, `polymarket-bot-d-live.service`, and `polymarket-dashboard.service` all returned `active`.
