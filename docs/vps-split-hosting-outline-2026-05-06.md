# VPS Split-Hosting Outline

**Date:** 2026-05-06
**Host:** the VPS provider `vps-host`
**Tailnet IP:** `192.0.2.1`
**Status:** Paper-only VPS offload active. No live order placement moved.

## Goal

Reduce CPU pressure on the homelab hypervisor the bot LXC container by moving low-risk, paper-only, and
latency-sensitive runtime loops to the Helsinki VPS while preserving the bot container as
the canonical live-control host until observability, rollback, and safety gates
are proven.

## Completed

1. Provisioned a small EU VPS.
2. Recovered SSH and added laptop/the local workstation access.
3. Installed Tailscale and verified private reachability from laptop,
   the homelab hypervisor, and the bot container.
4. Added read-only VPS node status reporter:
   `/home/operator/longshot-research/data/reports/vps_node/latest.json`.
5. Added private Tailscale-only HTTP status bridge:
   `http://192.0.2.1:8091/latest.json`.
6. Wired the bot container dashboard to consume VPS status.
7. Reboot-tested the VPS and verified SSH/Tailscale/status services return.
8. Rebuilt minimal UFW:
   - default deny inbound
   - default allow outbound
   - public `22/tcp` retained as setup fallback
   - inbound `tailscale0` allowed
9. Added persistent VPS paper telemetry feed:
   `longshot-crypto-recorder-vps-paper-feed.service`.
10. Moved these paper-only services from the bot container to the VPS:
   - `polymarket-crypto-prob-gap-paper.service`
   - `polymarket-crypto-brownian-fv-paper.service`
11. Stopped and disabled the matching the bot container paper services.
12. Updated the bot container dashboard so moved paper services show as `vps:active`.
13. Added VPS-local crypto fair-value scan summaries to the dashboard.
14. Added the bot container-vs-VPS recorder comparison metrics:
   - heartbeat age
   - PM event rate
   - CEX trade rate
   - active subscriptions
   - gap count
   - DB size and row counts
15. Moved these Bot G paper-only services from the bot container to the VPS:
   - `polymarket-bot-g-prime.service`
   - `polymarket-bot-g-prime-shadow.service`
   - `polymarket-bot-g-prime-late-cheap.service`
   - `polymarket-bot-g-prime-take-profit.service`
16. Created dedicated VPS Bot G paper ledger:
   `/home/operator/longshot-research/data/bot_g_vps_main.db`.
17. Stopped and disabled the matching the bot container paper Bot G services.
18. Updated the bot container dashboard so moved Bot G paper services show as `vps:active`
   and use VPS ledger summaries.

## Current Soak

The VPS shadow/paper recorder and paper crypto fair-value lanes are running in
parallel with the the bot container production recorder.

Current live checks at setup time:

| Metric | the bot container | VPS |
|---|---:|---:|
| Recorder gaps | `0` | `0` |
| Active subscriptions | `4` | `4` |
| PM events/min | `1419.9` | `821.0` |
| CEX trades/min | `2896.5` | `5110.8` |
| Heartbeat age | `0.9s` | `9.9s` |

Crypto fair-value dashboard lanes now report:

| Lane | Source | Scan summaries | Markets seen | Signals |
|---|---|---:|---:|---:|
| `crypto_probability_gap_paper` | VPS | `162` | `289` | `0` |
| `crypto_brownian_fv_paper` | VPS | `162` | `289` | `0` |

A thread follow-up monitor is active as `vps-recorder-soak-check` for roughly
12h and 24h soak checks.

## Bot G Paper VPS Cutover

Cutover time: 2026-05-06.

| Lane | Source | Service state | Runtime state |
|---|---|---|---|
| `bot_g_prime` | VPS | `vps:active` | `paper`, `dry_run=True` |
| `bot_g_prime_shadow` | VPS | `vps:active` | `paper`, `dry_run=True` |
| `bot_g_prime_late_cheap` | VPS | `vps:active` | `paper`, `dry_run=True` |
| `bot_g_prime_take_profit` | VPS | `vps:active` | `paper`, `dry_run=True` |
| `bot_g_prime_live` | the bot container | `active` | live probe remains local |

The VPS Bot G ledger was cloned from the bot container as a slim paper-only subset:

| Table | Rows |
|---|---:|
| `orders` | `167` |
| `positions` | `167` |
| `trades` | `329` |
| `events` | `2,919` |

The four moved units use:

- `POLYMARKET_ENV=paper`
- `BOT_G_ENV=paper`
- `BOT_G_DRY_RUN=true`
- `POLYMARKET_DB_PATH=/home/operator/longshot-research/data/bot_g_vps_main.db`
- `BOT_G_RECORDER_DB_PATH=/home/operator/longshot-research/data/bot_e_recorder_vps_canary.db`

## Still On the bot container

1. Production crypto recorder:
   `polymarket-bot-e-recorder.service`.
2. Bot G live service:
   - `polymarket-bot-g-prime-live.service`
3. Bot D services:
   - `polymarket-bot-d.service`
   - `polymarket-bot-d-live.service`
4. Dashboard, watchdog, Telegram notifier, wallet/CLOB auth, keystore and
   passphrase handling, the VPN provider posture.

## Next Candidates

1. Monitor the moved Bot G paper lanes for 12-24h.
2. Compare the bot container load relief, VPS CPU/RAM, Bot G runtime freshness, recorder
   parity, and dashboard alignment.
3. Decide whether the VPS paper recorder should remain canonical for moved
   Bot G paper lanes or whether any lane should roll back to the bot container.
4. Keep `bot_g_prime_live` and all real-money order placement blocked until a
   future ADR explicitly accepts live relocation.

## Hard Blocks

Do not move or modify these without explicit future approval and a new ADR:

1. `bot_g_prime_live`.
2. Wallet/CLOB auth material.
3. Keystore or passphrase files.
4. Any real-money order-placement path.
5. the VPN provider/geofence posture for live trading.
6. Production recorder writes becoming VPS-canonical.
