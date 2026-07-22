# Bot E recorder VPS canary — rollover and backup design

**Date:** 2026-05-10
**Status:** Draft for operator review (no implementation authorized).
**Owner:** the operator decides; Codex/Claude implement after explicit approval.
**Surfaced by:** Opus VPS-to-the bot container migration audit (Session 307), F-3.

## Problem

`bot_e_recorder_vps_canary.db` lives at
`/home/operator/longshot-research/data/bot_e_recorder_vps_canary.db` on the
Helsinki VPS. Today it is `27.6 GB` on a `75 G` root disk (`58%` used). It is
the price/book feed Bot G live and Bot G paper read every 2 s and during the
final-60 s window for live order timing. ADR-124 already established that a
blind hot copy of this file fails verification, so the existing
`vps_pull_backup` flow excludes it.

ADR-144 (Session 304) flagged three acceptable end-states for this DB: bound
hot window, shard/rollover, or move the feed to the bot container leaving only Bot G live
on the VPS. Session 306 migrated everything else but explicitly deferred this
decision because every option crosses the Bot G live latency loop.

## Constraints

| # | Constraint | Source |
|---|---|---|
| C1 | Bot G live and Bot G paper must keep reading the same DB shape they read today (queries against `pm_events`, `book_levels`, `crypto_*` tables). | Bot G VPS service definitions, `core/bot_g_*` |
| C2 | Cutover must not introduce >2 s of feed gap; Bot G's scan interval is 2 s. | ADR-128 latency budget, ADR-136 |
| C3 | No existing in-service rollover code path. The recorder does single-file appends. | `bots/bot_e_recorder/__main__.py`, `bots/bot_e_recorder/store.py` |
| C4 | Backup must produce a verifiable artifact. SQLite `.backup` over a 27.6 GB DB takes minutes and IO-stalls the writer. ADR-124 documented this. | ADR-124 |
| C5 | VPS root disk must stay below `70%` warn threshold on the way to a stable end state. | ADR-144 |
| C6 | Budget: under the operator-decision item in OQ-102, no workstation / VPS spend changes beyond what already exists. | OQ-102 |

## Options

### Option A — Bounded hot window with daily online backup

Keep the feed where it is, but add an in-service rollover so the hot DB stays
under a target size (e.g. `8 GB`). At a configured threshold the recorder
flushes and rotates: the live writer pivots to a new file
(`bot_e_recorder_vps_canary.<YYYYMMDD>.db`) and the previous file becomes
read-only and is pulled to the homelab hypervisor via SQLite `.backup` outside any final-60
s window.

| Dimension | Detail |
|---|---|
| Effort | Medium. Requires a rollover code path in `bot_e_recorder/store.py` plus a Bot G reader path that opens the latest hot file and a fallback list of older read-only shards. |
| Risk to Bot G live | Medium. Rollover must complete cleanly mid-flight without dropping subscriptions; one bad rollover loses 2-5 s of feed. |
| Disk impact (VPS) | Net neutral to slightly better. Hot file capped, but read-only shards still occupy space until they age out. |
| Backup quality | Good. Read-only shards back up cleanly over scp/rsync; the hot file uses online `.backup` like the other VPS DBs. |
| Reversibility | High. Rollover is a recorder-level change; revert by stopping rollover and letting the next file fill normally. |
| Open questions | (a) What threshold? (b) Bot G reader changes? (c) WAL handling around rollover? |

### Option B — Move the feed to the bot container, keep Bot G live on VPS, stream feed over Tailscale

the bot container already runs the shared crypto recorder at
`data/recorder/bot_e_recorder.db` on a dedicated `100 G` mount. The VPS
canary becomes redundant once Bot G live can read the the bot container recorder over
Tailscale.

| Dimension | Detail |
|---|---|
| Effort | High. Requires a low-latency read path from VPS to the bot container (replication or RPC) with `<2 s` lag for the final-60 s window. SQLite over the network is not viable; a thin protocol or Postgres replica would be needed. |
| Risk to Bot G live | High. If the link to the bot container wobbles, Bot G stops trading. the VPN provider VPN already adds a hop. |
| Disk impact (VPS) | Best — `27.6 GB` reclaimed entirely. |
| Backup quality | Best. the bot container recorder is on a `100 G` mount with longer retention, and its backups can move into the new `longshot-the bot container-pull-backup` flow. |
| Reversibility | Medium. Removing the VPS recorder is destructive; restore would need a fresh recorder warm-up. |
| Open questions | (a) Replication protocol? (b) Tailscale link reliability under final-60 s load? (c) How does Bot G fall back if the bot container is briefly unreachable? |

### Option C — Maintenance-window backup only, no rollover

Stop the recorder briefly during a low-activity window (e.g. weekend), take a
SQLite `.backup` of the full file, restart the recorder. No structural
change.

| Dimension | Detail |
|---|---|
| Effort | Lowest. A scripted stop-`.backup`-start, run weekly. |
| Risk to Bot G live | Bounded: feed gap during the window. If Bot G is paused at the same time, zero impact on trades. |
| Disk impact (VPS) | None — the file keeps growing. C5 stays unmet long-term. |
| Backup quality | Good for the artifact, but increasingly expensive per run (compress + ship `27.6 GB` then `30+ GB` then …). |
| Reversibility | Trivial. |
| Open questions | (a) Acceptable maintenance cadence? (b) Disk-fill failure mode timeline at current growth rate? |

## Recommendation

**Adopt A (bounded hot window) as the steady-state, do C (maintenance-window
backup) once now to capture today's state, and treat B as a longer-horizon
follow-up only if growth or reliability force it.**

Reasoning:

- C alone fails C5 — the disk warn threshold becomes a "when," not "if."
- B is the cleanest end state but requires real engineering on the live
  latency path, which OQ-102 explicitly fences off without operator approval.
- A combines a reasonable engineering effort with a backup pipeline that
  matches the existing VPS-pull contract (`.backup` API, count + quick_check
  + zstd + sha256, reusing `vps_pull_backup.py`). Once shards exist and the
  hot file is capped, Option B becomes a smaller delta later.

## Proposed sequence (requires explicit operator approval before any step)

| Step | What | Authorization needed | Notes |
|---|---|---|---|
| 1 | One-off maintenance-window full backup of today's `bot_e_recorder_vps_canary.db` to `<bulk-storage>/`. Stop recorder, `.backup`, restart. | Yes — touches Bot G feed (a few seconds gap during off-hours). | Captures the baseline so any later structural change is rollback-safe. |
| 2 | Add rollover code path in `bots/bot_e_recorder/store.py` behind a feature flag (default off). Add Bot G reader changes to enumerate `bot_e_recorder_vps_canary.*.db` files. | No (paper-only flag default off). | Code-only; no behavior change until enabled. |
| 3 | Enable rollover on a Sunday with operator present. Set threshold at `8 GB`. | Yes — first live rollover. | Watch Bot G heartbeat; abort and revert if heartbeat gap >5 s. |
| 4 | Extend `scripts/vps_pull_backup.py` to back up frozen shards (read-only, fast `.backup` works fine). Daily cadence. | No — backup-only, additive. | Shards age out via existing `prune_runs` logic. |
| 5 | After 4 weeks of stable rollover + backup, evaluate whether B is still attractive. | Yes — only if pursuing B. | Most likely "park" decision: Option A is sufficient. |

## Reject reasons captured up front

Per `docs/decisions-log.md` rejection-list discipline:

- Reject C as steady-state: violates C5.
- Reject B as the next step: violates "no live order-path change without
  explicit approval" (OQ-102) and engineering effort vastly exceeds the
  problem in front of us.
- Reject "do nothing": disk threshold timeline below.

## Disk timeline if no action

Current growth rate from role-audit measurement: roughly `1 GB/week` of
`pm_events` + `book_levels`. From `27.6 GB` to the `90%` action threshold is
`(0.90 × 75) − 41 = 26.5 GB` of remaining headroom. At `1 GB/week` that's
roughly **26 weeks** before the trip happens by recorder growth alone, but
the recorder is not the only writer — `main.db` and `bot_g_vps_main.db` also
grow. Plan as if action is needed inside **3-4 months** to be safe.

## What is NOT in this design

- Any change to live order placement.
- Any change to bankroll, position sizing, or kill-switch values.
- Any change to the VPN provider VPN posture.
- Any move of Bot G live off the VPS.
- Any data deletion.

Cross-refs: ADR-124, ADR-128, ADR-144, ADR-145, OQ-053, OQ-080, OQ-102,
an internal role-audit report (not exported).
