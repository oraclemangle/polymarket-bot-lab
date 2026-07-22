# Wallet Observer — Feature Documentation

**Created:** 2026-05-07
**Authority:** ADR-126
**Status:** running on `the-vps` VPS, 30-day forward-observation period started

---

## What this is

A passive Polygon RPC poller that subscribes to Polymarket V2 CTF
Exchange + NegRisk Exchange `OrderFilled` events, filters by a curated
whitelist of 245 retail-tier wallets (Tier A + B from WANGZJ mining),
and records every matching fill to a SQLite DB.

**Not copy-trading.** Pure read-only observation. No transactions,
no signing, no operator wallet involvement. The data feeds three
downstream uses:

1. Forward-validation of "are these wallets still profitable in 2026?"
2. Counterparty composition logging for existing bots' adverse-selection
   diagnosis
3. Future paper-copy spec (after 30-day forward edge confirmed)

## Quick reference

| item | value |
|---|---|
| Service | `polymarket-wallet-observer.service` |
| Host | a small EU VPS
| Database | `/home/operator/longshot-research/data/wallet_observer.db` |
| Schema | `bots/wallet_observer/schema.py` (separate from main.db) |
| Wallets observed | 245 (97 Tier A + 148 Tier B) |
| Source whitelist | `data/retail_wallets_xref_2026-05-07.csv` |
| RPC | `https://polygon-bor.publicnode.com` (configurable via env) |
| Poll interval | 30 seconds |
| Daily report | 06:30 UTC via systemd timer |
| Started | 2026-05-07 ~20:34 UTC |

## Architecture

```
┌─────────────────────────────────┐
│ Polygon RPC (publicnode)        │
│ https://polygon-bor.publicnode  │
└──────────────┬──────────────────┘
               │ eth_getLogs every 30s
               │ filter: V2 OrderFilled topic
               ▼
┌─────────────────────────────────┐
│ wallet_observer/__main__.py     │
│  • signal handlers              │
│  • run lifecycle tracking       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ collector.py                    │
│  • POA middleware for block ts  │
│  • decode_log() — V2 layout     │
│  • derive_observed_side()       │
│  • whitelist lookup (lru_cached)│
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ schema.py                       │
│  • wallet_observed_fills (PK    │
│    on tx_hash + log_index)      │
│  • collector_state (resumable)  │
│  • observer_runs (liveness)     │
└──────────────┬──────────────────┘
               │
               ▼
        wallet_observer.db
        (separate from main.db)
```

## V2 OrderFilled event layout

Discovered during build; documented for future maintenance:

```solidity
event OrderFilled(
    bytes32 indexed orderHash,         // topics[1]
    address indexed maker,             // topics[2]
    address indexed taker,             // topics[3]
    uint8 side,                        // data[0..32]   0=BUY, 1=SELL (maker POV)
    uint256 tokenId,                   // data[32..64]  share token (single ID, not pair)
    uint256 makerAmountFilled,         // data[64..96]  6-decimal
    uint256 takerAmountFilled,         // data[96..128] 6-decimal
    uint256 fee,                       // data[128..160]
    bytes32 builder,                   // data[160..192] builder code attribution
    bytes32 metadata                   // data[192..224]
)
```

Topic0: `0xF00D00000000000000000000000000000000000562980ba90b1a89f2ea84d8ee`

V1 V2 differences (V1 deprecated 2026-04-28):
- V1 had separate `makerAssetId` + `takerAssetId` (one was 0=USDC); V2 has single `tokenId`
- V1 inferred side from asset IDs; V2 has explicit `side` field
- V1 amounts inconsistent decimals; V2 standard 6-decimal

## Side derivation

```
side=0 (maker BUY):
  - maker provided USDC, received shares
  - makerAmount = USDC raw (6-decimal)
  - takerAmount = shares raw (6-decimal)
  - Maker side label: BUY
  - Taker side label: SELL
  - Price = makerAmount / takerAmount

side=1 (maker SELL):
  - maker provided shares, received USDC
  - makerAmount = shares raw (6-decimal)
  - takerAmount = USDC raw (6-decimal)
  - Maker side label: SELL
  - Taker side label: BUY
  - Price = takerAmount / makerAmount
```

Both legs are 6-decimal in V2, so the scale cancels in the price ratio.
A fill at 5 USDC for 100 shares prints as `5_000_000` and `100_000_000`
respectively.

## Daily report

Run manually:
```bash
ssh the-vps "cd /home/operator/longshot-research && \
  /home/operator/longshot-research/.venv/bin/python \
  scripts/wallet_observer_daily_report.py"
```

Output: `data/reports/wallet_observer/latest.md` + `latest.json`

The report shows:
- Headline counts (24h, 7d, all-time)
- Per-tier activity breakdown
- Top 25 most-active observed wallets in 24h
- Side distribution
- Collector state per exchange
- Service run history
- Health check (last fill age)

## Smoke-test results

First production capture (2026-05-07 ~20:24-20:30 UTC):

- **510 fills** captured in **200 blocks** (~7 minutes of activity)
- **10 distinct wallets** active out of 245 (4% activity in 7-min window)
- Tier A: 503 fills / 8 wallets / 397 BUYs / 106 SELLs
- Tier B: 7 fills / 2 wallets / 2 BUYs / 5 SELLs
- Top wallets: swisstony (`0x204f72f35326...`), RN1 (`0x2005d16a84ce...`)
- Price range observed: $0.012 to $0.99 (full 1c-99c range)

Implies steady-state: **~10K-50K fills/day** captured.

## Operational guards

| guard | mechanism |
|---|---|
| Service halt | `WALLET_OBSERVER_HALT=true` env → scans but skips writes |
| Restart on crash | `Restart=always` `RestartSec=10` |
| File-system isolation | `ProtectSystem=strict` + explicit `ReadWritePaths` |
| No privilege escalation | `NoNewPrivileges=true` |
| No network egress beyond RPC | `ProtectHome=read-only` (data dir is RW exception) |
| RPC failover | none yet — operator change to private RPC if rate-limited |

## Known limitations

1. **Public RPC may rate-limit.** `polygon-bor.publicnode.com` is free
   and worked through smoke-test, but heavy traffic could hit limits.
   If logs show `Web3RPCError` repeatedly, switch to Alchemy/Quicknode
   via `WALLET_OBSERVER_POLYGON_RPC_URL` env override.
2. **PolyVerify static labels.** Wallet labels reflect 2026-05-06
   snapshot. A wallet flagged "human" then may be running automation
   now. Refresh quarterly.
3. **WANGZJ data is historical.** The 245 wallets' historical PnL
   reflects 2021-2026 cumulative; some may have stopped trading.
   Forward observation will reveal which ones.
4. **Asset-id semantics.** V2 uses 6-decimal for both shares and USDC.
   If Polymarket changes this, side derivation will silently produce
   wrong prices. Sanity check: max observed price clamped to 1.5
   (anything higher is treated as price=None).
5. **No real-time alerting.** Daily report is the only current
   visibility. Add dashboard panel or alert when meaningful.

## Tests

`tests/test_wallet_observer.py` — 18 tests pass on VPS Python 3.12 in 0.87s.

Coverage:
- Whitelist tier filtering (default A+B, custom tiers, case-insensitive)
- Schema init + idempotency + uniqueness constraint
- V2 log decoder (parses, rejects wrong topic0, rejects unknown contract)
- Side derivation for V2 (side=0 maker BUY, side=1 maker SELL, unknown
  for non-observed wallets)
- Collector state persistence

Smoke tests against live RPC done manually during build.

## Files added

- `bots/wallet_observer/__init__.py`
- `bots/wallet_observer/__main__.py` (102 lines)
- `bots/wallet_observer/config.py` (60 lines)
- `bots/wallet_observer/whitelist.py` (130 lines)
- `bots/wallet_observer/schema.py` (90 lines)
- `bots/wallet_observer/collector.py` (270 lines)
- `tests/test_wallet_observer.py` (260 lines, 18 tests)
- `scripts/wallet_observer_daily_report.py` (180 lines)
- `systemd/polymarket-wallet-observer.service`
- `systemd/polymarket-wallet-observer-daily-report.service`
- `systemd/polymarket-wallet-observer-daily-report.timer`

Total: ~1,300 lines new code + tests + service files.

## Files unchanged

- All bot services, all order paths, all caps, all wallets
- Bot D-Spike Strategy E paper unit (running on same VPS)
- Bot G live probe (running on the VPS provider)
- All paper bots
- `core/wallet_labels.py` (works in tandem; PolyVerify lookup)
- `core/retail_wallet_pnl.py` (works in tandem; WANGZJ tier data)

## What happens next

**Next 24h:** observer accumulates first day of fills. Run daily report
manually after 24h to verify volume + identify any wallets gone cold.

**Next 7d:** monitor that the service stays up, that fills are being
recorded, and that the 245 wallets are mostly active (allow attrition
of e.g. ~10-20%).

**Next 30d:** at 30-day mark, run forward-validation:
- For each whitelisted wallet, compute realized PnL on resolved markets
  in the observation window
- Compare to historical WANGZJ baseline
- Flag wallets where forward edge ≥ historical
- Flag wallets where forward edge ≤ 0 (may have changed strategy)
- Compute capture-rate analysis: at what latency budget could a
  hypothetical paper-copy bot have captured what fraction of these
  wallets' edge?

**After 30d:** decide whether to propose a paper-copy bot. Constraints:
- Tier B niche specialists (slow trades, concentrated bets) most likely
  copyable
- Tier A generalists (high frequency, market-neutral) likely
  uncopyable due to latency
- Any copy bot proposal requires lifting the CLAUDE.md kill-list entry
  via a new ADR

## Related docs

- `docs/reports/retail-wallet-pnl-mining-2026-05-07.md` — source data
- `docs/wallet-labels-feature-2026-05-07.md` — companion PolyVerify lookup
- `docs/decisions-log.md` ADR-126 — authority for this build
- `docs/state-of-the-fleet-2026-05-07.md` — broader fleet context
