# Tiny Live-Probe Readiness Packet

**Date:** 2026-05-14
**Status:** operator-approved by ADR-165; deployment not performed

This packet prepares and records approval for three tiny live probes. It does
not enable live services, deploy to the bot container/VPS, place live orders, read wallet
material, touch keystores, restart production services, or alter bankroll.

the operator approval is recorded in ADR-165. Runtime deployment and live-service
enablement remain separate operational steps.

## Shared Safety Boundary

- Readiness code is in `core/tiny_live_probe.py`.
- Readiness reporting is in `scripts/tiny_live_probe_readiness.py`.
- The report is read-only and emits caps, kill switches, rollback, dry-run
  preflight status, and approval wording.
- `systemd/polymarket-tiny-live-probe-readiness.service` is a read-only
  report unit only.
- Existing paper services remain paper services.

## Bot D Station Lock

**Live-probe shape:** hard station-lock only.

| Parameter | Value |
|---|---:|
| Max order | `$5` |
| Daily gross cap | `$20` |
| Open exposure cap | `$25` |
| Max concurrent positions | `5` |
| Max loss while full | `$25` |

**Allowed actions:** `BUY_YES`, `BUY_NO`.

**Kill switches:**

- Any classifier/settlement mismatch.
- `2` hard-lock losses.
- Realised P&L `<= -$10`.
- Stale station data.
- Any live order or reconcile anomaly.

**Rollback:**

1. Stop and disable the live-probe service.
2. Leave the paper Station Lock service running for evidence collection.
3. Cancel unresolved live orders only through the existing approved emergency
   path.
4. Record the kill event in `CHANGELOG.md`, `MEMORY.md`, and OQ-112 before
   any restart.

**Approval question:**

the operator, approve enabling Bot D Station Lock as a tiny live probe with
hard-lock-only entries, max order `$5`, daily gross `$20`, open exposure
`$25`, max `5` concurrent positions, and the listed kill switches?

## Bot D-Spike 6-12h

**Live-probe shape:** 6-12h TTR only, positive-EV city whitelist, 1c-15c
cheap-YES band.

| Parameter | Value |
|---|---:|
| Max order | `$2` |
| Daily gross cap | `$10` |
| Open exposure cap | `$20` |
| Max concurrent positions | `10` |
| Max loss while full | `$20` |

**Allowed action:** `BUY_YES`.

**Kill switches:**

- Any rule violation.
- `5` consecutive resolved losses.
- Realised P&L `<= -$8`.
- CLOB/auth/reconcile fault.
- Overlap with other Bot D live exposure.

**Rollback:**

1. Stop and disable the Bot D-Spike live-probe service.
2. Keep the VPS paper Spike service available for comparison.
3. Cancel unresolved live orders only through the existing approved emergency
   path.
4. Record the kill event in `CHANGELOG.md`, `MEMORY.md`, and the Bot D-Spike
   open question.

**Approval question:**

the operator, approve enabling Bot D-Spike 6-12h as a tiny live probe with
whitelist-only 1c-15c `BUY_YES` entries, max order `$2`, daily gross `$10`,
open exposure `$20`, max `10` concurrent positions, and the listed kill
switches?

## Bot L Complete-Set

**Live-probe shape:** BUY/MERGE only. Do not build or enable SELL/SPLIT live
path.

| Parameter | Value |
|---|---:|
| Max bundle gross | `$1` |
| Daily gross cap | `$10` |
| Open exposure cap | `$20` |
| Max concurrent bundles | `2` |
| Gas cap | `$0.25` per bundle |
| Max loss while full | `$20` |

**Allowed actions:** `BUY_COMPLETE_SET`, `MERGE_COMPLETE_SET`.

**Required guards:**

- Depth-enforced same-asset book join.
- Both legs must pass the fresh-book depth check.
- No live SELL/SPLIT path.
- Bundle gas estimate must be `<= $0.25`.

**Kill switches:**

- Any unhedged leg `>$2`.
- Net realised `<= -$3` after gas.
- Depth join failure.
- Merge failure.
- Stuck inventory.
- Any atomicity or reconciliation anomaly.

**Rollback:**

1. Stop and disable the Bot L live-probe service.
2. Keep the Bot L paper timer running for depth-validated comparison.
3. Do not run a SELL/SPLIT path; merge or emergency-cancel through approved
   tooling only.
4. Record the kill event in `CHANGELOG.md`, `MEMORY.md`, and OQ-111 before
   any restart.

**Approval question:**

the operator, approve enabling Bot L Complete-Set as a BUY/MERGE-only tiny live probe
with depth-enforced same-asset book joins, max bundle gross `$1`, daily gross
`$10`, open exposure `$20`, max `2` concurrent bundles, gas cap `$0.25` per
bundle, and the listed kill switches?

## Deployment State

No deployment was performed. The repo now contains readiness specs, guard
tests, a read-only readiness report, and one read-only report systemd unit.
Dashboard metadata now treats the three lanes as live probes per ADR-165.
