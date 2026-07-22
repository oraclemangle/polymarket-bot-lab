# External Watch List

**Updated:** 2026-05-07

X handles, blogs, GitHub repos, and on-chain wallets worth periodic monitoring for Polymarket-specific intel. Read-only — no engagement, no DMs, no following from operator-linked accounts.

---

## X handles (Polymarket-specific)

### Tier 1 — verified non-shill, post on-chain evidence

| handle | what they post | last verified |
|---|---|:-:|
| [@appledog_xyz](https://x.com/appledog_xyz) | Daily maker-rebate + LP P&L screenshots; concrete numbers ($16-30/day class). Active V2 builder-code harvester. | 2026-05-07 |
| [@0xsolvix](https://x.com/0xsolvix) | Daily LP-farming + maker-rebate breakdowns ("+$16.24 maker rebate +$16.33 LP rewards" pattern). Notes whale-pool dilution issues. | 2026-05-07 |
| [@InternDonut](https://x.com/InternDonut) | AI-assisted geopolitics mispricing scans with watchlist + conviction levels. Non-shill format. | 2026-05-07 |

### Why we watch them, not follow them

These accounts post operationally useful intel but the strategies they describe (LP / maker-flow / geopolitics research) are either out-of-scope per `CLAUDE.md` (market-making) or require operator scope expansion (geopolitics). We don't replicate; we monitor for new venue mechanics or strategy mutations.

---

## Wallets to track

### High-volume retail-tier candidates (Grok-surfaced 2026-05-07, all were whale-tier)

| wallet | label | all-time PnL | category | note |
|---|---|---:|---|---|
| `0x9d84...1344` | ImJustKen | +$5.6M | multi (sports/politics) | 18,602 positions, ~$1.1M net worth |
| `0xee00...cea1` | S-Works | +$14.4M | multi | 9,392 positions |
| `0x1496...a429` | gmpm | +$13M | multi | 1,036 positions; ~$254K net |
| `0x2005...75ea` | RN1 | +$24.8M | multi | 108k+ positions (extreme volume) |
| `0x204f...5e14` | swisstony | +$50.1M | multi | 164k+ positions (extreme) |

**Status:** all whale-tier. No replicable retail playbook visible. Tracking for post-V2 strategy mutations only.

### Internally-surfaced (Becker / PolyVerify cross-ref)

| wallet | label | note |
|---|---|---|
| `0x4bFb41d5B3...` | crypto sweeper | 580K fills; settlement-sweep at scale; killed by Opus on fees + concentration |
| `0x9b97...5e12` | tweet's settlement-sweep wallet | PolyVerify rank 385, bot=True |
| `0xBA264376d6...` | 2nd crypto sweeper | PolyVerify rank 446, bot=True |

---

## GitHub / docs

| target | what to check |
|---|---|
| [Polymarket developer docs changelogs](https://docs.polymarket.com/) | V2 fee-schedule updates, builder-code mechanics changes |
| `polymarket/clob-client` releases on GitHub | Breaking changes that affect our `py-clob-client-v2` integration |
| `polymarket/clob-contracts` | Proxy/factory contract changes; `neg-risk-ctf-adapter` updates |
| `UMAprotocol/protocol` | Optimistic Oracle changes affecting market resolution |
| `JKorf/Polymarket.Net` | CLOB V2 REST/WebSocket/local-order-book behavior to compare against `core/clob_v2.py`; reference only, no runtime adoption |
| `pmxt-dev/pmxt` | Polymarket API/websocket/wallet watcher changes; reference only, no TypeScript runtime adoption |
| `evan-kolberg/prediction-market-backtesting` | Replay-realism patterns: latency, queue position, PMXT missing-hour handling, fee/rebate modeling |
| `ent0n29/polybot` | Order-lifecycle/data-quality telemetry ideas; do not import Java/Spring stack or maker strategy |
| arXiv `cs.CR` + `q-fin.TR` searches monthly | New empirical Polymarket research (latest: arXiv 2508.03474 IMDEA, AFT 2025) |

---

## On-chain monitors

Not currently running. Possible future targets:

- Builder-code redistribution events from Polymarket fee-share contracts (need contract address — not in repo yet)
- pUSD <-> USDC.e flow imbalances during V2 migration windows
- UMA dispute escalations on negRisk markets (early-warning for resolution-mechanic plays)

---

## Update protocol

This file is read-only intel; do not commit secrets, do not link to
operator accounts, do not respond/engage. Add entries here when
external sources surface verifiable signal. Remove entries when
they go shill / get banned / stop posting concrete numbers.
