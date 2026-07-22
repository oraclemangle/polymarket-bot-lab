# Crypto FV Final Review Before Archive

**Date:** 2026-05-09
**Scope:** `crypto_probability_gap_paper`, `crypto_brownian_fv_paper`, and the shared crypto recorder/data feed.
**Verdict:** Archive both paper strategy lanes. Keep the shared crypto recorder feed and recorder-derived research infrastructure.

## Executive Verdict

Both Crypto FV paper lanes fail the forward-paper robustness gate that OQ-078 set for keeping a lane active:

- `crypto_probability_gap_paper`: `145` signals, `145` simulated 1c-stressed fills, `144` closed, `71` wins, `-$104.00` net after fees on `$720` closed stake, `-14.4%` net ROI, `-17.1%` ex-largest-win ROI, `-19.7%` ex-largest-two ROI.
- `crypto_brownian_fv_paper`: `198` signals, `198` simulated 1c-stressed fills, `196` closed, `103` wins, `-$100.80` net after fees on `$980` closed stake, `-10.3%` net ROI, `-12.5%` ex-largest-win ROI, `-13.9%` ex-largest-two ROI.

The remaining positive slices are either small, contradicted by a broader losing parent slice, or disappear after removing one or two wins. No symbol/time/side slice is strong enough to justify continuing these as operator-facing paper strategies.

This does **not** kill the crypto recorder. The VPS crypto feed is still useful as raw BTC/ETH/SOL/XRP/DOGE context for Bot G, symbol/time/liquidity analysis, and future research. The archive decision applies to the fair-value strategy execution/surfaces, not to recorder/data infrastructure.

## Paper Lane Verdict Table

Latest direct VPS SSH and status-port probes from this Mac timed out, but the bot container dashboard bridge successfully read the VPS status at `2026-05-09T14:55:43Z`. Full ledger statistics use the latest pulled VPS backup, `<bulk-storage>/`.

| Lane | Service | Status | Current P&L | Signals | Orders | Fills | Closed | Open pos | Net ROI | Robustness | Verdict |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Crypto FV Probability Gap Paper | `polymarket-crypto-prob-gap-paper` | `vps:active` at 14:55Z bridge check | `-$104.00` 1c-stressed closed net; `-$90.99` top-of-book; `-$116.37` 2c-stressed | 145 | 145 | 145 buy fills / 144 settlement fills | 144 | bridge: 0; backup: 1 open, `$5.00` cost | `-14.4%` | Ex-largest `-17.1%`, ex-largest-two `-19.7%`; BTC 15m positive only before trimming; ETH/SOL negative | Archive |
| Crypto FV Brownian Paper | `polymarket-crypto-brownian-fv-paper` | `vps:active` at 14:55Z bridge check | `-$100.80` 1c-stressed closed net; `-$82.75` top-of-book; `-$117.98` 2c-stressed | 198 | 198 | 198 buy fills / 196 settlement fills | 196 | bridge: 0; backup: 2 open, `$10.00` cost | `-10.3%` | Ex-largest `-12.5%`, ex-largest-two `-13.9%`; 15m/BTC positive, but whole lane and 5m fail | Archive |

## Edge Survival Table

| Candidate slice | Lane | Sample | Net edge | Ex-largest | Ex-largest-two | Fillability | Data quality | Decision |
|---|---|---:|---:|---:|---:|---|---|---|
| All, 1c-stressed | Probability Gap | 144 closed | `-$104.00`, `-14.4%` | `-17.1%` | `-19.7%` | Signals fill in paper, but `26,058 / 41,598` scans missed book | Settlement via paper resolve; direct Chainlink label gate still absent | Fail |
| BTC 15m, 1c-stressed | Probability Gap | 23 closed | `+$7.08`, `+6.2%` | `-9.4%` | `-19.3%` | Avg depth `$84.84`, avg spread `1.08c` | Positive cell is winner-sensitive | Reject as survivor |
| BTC 15m 300s+, 1c-stressed | Probability Gap | 17 closed | `+$20.70`, `+24.3%` | `+4.1%` | `-8.9%` | Avg depth `$90.00`, avg spread `1.11c` | Ex-largest-two negative | Reject as survivor |
| BTC 5m 120s-300s, 1c-stressed | Probability Gap | 77 closed | `+$5.34`, `+1.4%` | `-3.5%` | `-5.8%` | Avg depth `$224.43`, avg spread `1.18c` | Below OQ-078 ROI floor, fails trim | Reject |
| All, 1c-stressed | Brownian | 196 closed | `-$100.80`, `-10.3%` | `-12.5%` | `-13.9%` | Signals fill in paper, but `24,799 / 41,617` scans missed book | Settlement via paper resolve; direct Chainlink label gate still absent | Fail |
| BTC 15m, 1c-stressed | Brownian | 29 closed | `+$39.98`, `+27.6%` | `+20.0%` | `+13.7%` | Avg depth `$91.02`, avg spread `1.23c` | Best cell, but sample is `29`, not `150`; broader lane loses | Do not keep active lane |
| Brownian 15m, all symbols | Brownian | 65 closed | `+$22.85`, `+7.0%` | `+3.4%` | `-0.4%` | Avg depth `$80.70`, avg spread `1.39c` | Ex-largest-two negative | Reject |
| Brownian ETH 5m DOWN 45s-120s | Brownian | 4 closed | `+$27.71`, `+138.5%` | `+44.5%` | `+37.5%` | Tiny sample | Too small; not a strategy path | Negative-evidence note only |
| Brownian SOL 15m UP | Brownian | 3 closed | `+$6.54`, `+43.6%` | `+33.5%` | `+17.9%` | Tiny sample | Too small; SOL overall `-30.9%` | Negative-evidence note only |

## Recorder/Data Retention Table

| Data source / recorder | Used by | Current health | Data value | Cost / clutter | Keep? | Modification |
|---|---|---|---|---|---|---|
| VPS crypto recorder paper feed | Bot G, crypto replay, symbol/time/liquidity research | Session 279: `21.03 GB`, `16.85M` PM events, `18.30M` CEX trades, `0` gaps, heartbeat `15.1s`, `2,425` ev/min | High: raw BTC/ETH/SOL/XRP/DOGE tape remains reusable | Storage growth; dashboard clutter if mixed with dead strategy P&L | Keep | Keep as recorder diagnostic only |
| the bot container Bot E recorder | Bot G replay, historical crypto research | Session 279: `77.30 GB`, `57.7M` PM events, `104.7M` CEX trades, `0` gaps | High historical tape; ADR-122 indefinite recorder infrastructure | Storage/backup pressure governed by OQ-053 | Keep | No change |
| XRP/DOGE record-only context | Bot G symbol-universe proof, future crypto research | Healthy as part of VPS feed per ADR-081 | Medium: context only; no scored FV entries | Low incremental clutter if labelled recorder-only | Keep | Keep record-only; no FV scoring |
| Recorder-derived FV features | Future research only | Code still usable; current strategy execution failed | Medium as negative evidence and possible offline feature source | High if surfaced as active strategy | Keep hidden | Do not expose as active dashboard lane |
| Crypto FV paper execution services | Historical paper strategy ledger | the bot container bridge saw both `vps:active` at 14:55Z | Low after failed forward paper | High operator clutter | Archive | Registry/dashboard hidden; do not restart or promote |

## Dashboard Cleanup Table

| Surface | Current label | Problem | Change if archived |
|---|---|---|---|
| Registry inventory rows | Crypto FV Probability Gap Paper / Crypto FV Brownian Paper | Paper lanes are losing and no longer operator-actionable | Set both registry statuses to `archived`; they drop from active inventory |
| Active service checks | `polymarket-crypto-prob-gap-paper`, `polymarket-crypto-brownian-fv-paper` | Archived services should not affect active dashboard health | Remove from `active_systemd_units()` extra set |
| Recorders tab | `Recorders & FV` | Conflates raw recorder infrastructure with dead FV strategy cards | Rename to `Recorders`; remove FV panel fetch/card |
| `/api/crypto-fair-value` | Crypto FV paper API | A routable dashboard endpoint keeps the archived strategy visible if queried directly | Remove the dashboard route and keep historical review in reports/docs |
| Recorder diagnostics | Crypto Recorder (E), Maker Recorder (H), Wallet Observer | Still useful active data infrastructure | Keep visible |

## Ops Execution 2026-05-09

Operator approval was given after the review verdict to perform the ops cleanup.

- the bot container dashboard state was verified after restart: `polymarket-dashboard.service` active, `/api/crypto-fair-value` returns `404`, `/api/overview` has `0` Crypto FV inventory rows, and `recorder_comparison` still reports local/VPS recorder diagnostics.
- VPS paper strategy services were stopped and disabled through the PVE jump host: `polymarket-crypto-prob-gap-paper.service` and `polymarket-crypto-brownian-fv-paper.service` now report `inactive` / `disabled` in `data/reports/vps_node/latest.json`.
- VPS recorder infrastructure was retained: `longshot-crypto-recorder-vps-paper-feed.service` reports `active` / `enabled`, and the the bot container overview still reports VPS recorder heartbeat age `15.5s` and `0` gaps after the stop.
- No real orders were placed, no wallet/cap/order path was touched, and no live trading bot was restarted. A separate `polymarket-bot-g-prime-live-vps.service` status check returned `inactive`; it was not changed in this pass.

## Notes By Audit Question

1. Service status: the bot container dashboard bridge saw both Crypto FV paper services as `vps:active` at `2026-05-09T14:55:43Z`; after the operator-approved ops cleanup, VPS status JSON generated at `2026-05-09T15:56:24Z` reports both services `inactive` / `disabled`.
2. P&L: main 1c-stressed closed net is `-$104.00` for probability gap and `-$100.80` for Brownian. Top-of-book and 2c-stressed tracks are also negative.
3. Counts: probability gap `145` signals/orders/buy fills, `144` closed; Brownian `198` signals/orders/buy fills, `196` closed.
4. Fill realism: paper signal fill rate is `100%` for generated signals, but scan-level book misses are high (`~62.6%` probability gap, `~59.6%` Brownian), so the live path is not a reliable scalable fill channel.
5. Robustness: both full lanes fail fees, 1c stress, ex-largest, and ex-largest-two. Brownian BTC 15m is the only non-tiny robust-looking slice, but it has `29` closed versus the `150` OQ-078 gate and does not rescue the broader lane.
6. Symbol/time: BTC is least bad; ETH/SOL do not rescue probability gap. Brownian ETH is barely positive overall (`+$2.42`, `+1.1%`) but fails ex-largest; SOL is negative (`-30.9%`). Brownian 15m is positive pre-trim but fails ex-largest-two across all symbols.
7. Actionable signal left: no active paper strategy. The data is useful negative evidence and may inform future offline research only.
8. Recorder: keep. ADR-122/ADR-081 still apply.
9. Services: do not place orders and do not restart live trading bots. Archive/hide happened in the review; stopping/disabling the two VPS paper strategy services was performed only after separate operator approval.
10. Dashboard: remove FV from default recorder tab and active inventory; keep recorder diagnostics.

## Exact Commands And Queries Used

```bash
sed -n '1,220p' docs/codex-crypto-fv-final-review-archive-handoff-2026-05-09.md
rg -n "OQ-066|OQ-072|OQ-078|crypto|Crypto|5m|15m|recorder|fillability|FV|fair-value" docs/open-questions.md
rg -n "ADR-081|ADR-122|ADR-132|crypto|Crypto|FV|fair-value|recorder|Brownian|Probability" docs/decisions-log.md
ssh -o BatchMode=yes -o ConnectTimeout=8 the-vps '... systemctl ...'  # timed out
curl -fsS --max-time 5 http://192.0.2.1:8091/latest.json  # timed out
ssh hypervisor-host 'pct exec <ctid> -- curl -fsS --max-time 15 http://127.0.0.1:8090/api/crypto-fair-value -o /tmp/crypto_fv_api.json'
ssh hypervisor-host 'zstd -dc <bulk-storage>/ > /tmp/crypto_fv_main.db'
scp -q hypervisor-host:/tmp/crypto_fv_main.db /tmp/crypto_fv_main_20260509T112143Z.db
./.venv/bin/python scripts/crypto_fair_value_paper_report.py --db /tmp/crypto_fv_main_20260509T112143Z.db --since '' --out-md /tmp/crypto_fv_full.md --out-json /tmp/crypto_fv_full.json
```

Custom read-only Python queries over `/tmp/crypto_fv_main_20260509T112143Z.db` computed per-entry net P&L from `crypto_fair_value.signal` fill tracks joined to `portfolio.paper_resolve` settlements, then grouped by bot, fill track, symbol, duration, side, lead bucket, ask bucket, and probability bucket.
