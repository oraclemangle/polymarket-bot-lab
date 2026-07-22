# Fleet Review Session — 2026-05-14

**Session:** 366 (continues from Session 360-365 lane work on the main
working tree).
**Worktree:** `claude/jolly-curran-48e3f9` (Persistence-era HEAD); canonical
state is **main + uncommitted edits** to `core/bot_registry.py`.
**Scope:** review every bot, paper trader, recorder, sensor, and spin-off
candidate; produce next-steps; do whatever can be done now safely; persist
chat-history-on-file.
**Posture:** read-only validation, doc-only writes. No service restarts,
no live orders, no wallet/env/keystore/passphrase touches, no live-cap
changes.

---

## 1. What was reviewed

Read end-to-end (canonical sources on main):

- `AGENTS.md`, `MEMORY.md` head, `CHANGELOG.md` (Sessions 299-365).
- `core/bot_registry.py` HEAD + the **uncommitted main working-tree edits**
  that add Bot H/I/J/K/L, wallet observer, source-shadow, spike-short,
  high-tail, momentum-paper, wc-negrisk-basket, wallet-tag-feature-shadow.
- `docs/active-operating-model-2026-05-02.md` (still useful but two lanes
  short — see §5).
- `docs/decisions-log.md` headers ADR-130 through ADR-159; key bodies
  ADR-135, ADR-137, ADR-139, ADR-140, ADR-142, ADR-143, ADR-145, ADR-149,
  ADR-150, ADR-153, ADR-154, ADR-155, ADR-158, ADR-159.
- `docs/open-questions.md` index + bodies for OQ-067, OQ-086, OQ-097,
  OQ-099, OQ-100, OQ-102, OQ-111, OQ-112.
- `bots/bot_j_nr_wallet/executor.py` — direct verification of audit P0a
  and P2 claims against the current code.
- Selected reports under `docs/reports/`.

Recent claims explicitly **re-validated** rather than trusted:

- Bot D live realised P&L (sessions 354/356/358 numbers).
- Bot G live ledger split at the ADR-149/150 epoch boundary.
- Persistence (Bot I) bootstrap vs forward divergence.
- Bot J audit P0a/P2 findings — both already fixed in current code.
- Bot K +506% Becker number — confirmed as a survivorship-biased replay,
  not forward expectation.
- Bot L 24h backfill — confirmed +$1.9665 simulated executable; OQ-111
  audit already documents depth-validation gaps.

## 2. Top-5 executive actions (from the review)

| Rank | Lane | Action | Why now |
|---:|---|---|---|
| 1 | `bot_d_live_probe` | Keep live; **do NOT raise size further** until OQ-067 transfer proof clears | +$35.39 / +20.17% ROI on 54 closes; ADR-158 just raised caps today |
| 2 | `bot_g_prime_live` (ADR-149 epoch) | Continue $1 high-tail probe at 6c-8c ETH/SOL; no scale | Live ledger empty since 2026-05-10 epoch reset |
| 3 | `bot_i_persistence` | Continue paper to first n=50/cell gate (~12d Cell A, ~8d Cell B); honour -5% halt at n>=100 | Bootstrap +15.85% post-fee ROI; post-V2 forward weaker |
| 4 | `bot_j_nr_wallet` | Fix P0b settlement gate + P1 concentration risk before more paper data is consumed | 64%/89% of edge from one wallet; t-stat 1.76 |
| 5 | Bot H / Wallet Observer / Bot L | Recorder hygiene only; **no new builds for ~14 days** | Existing paper lanes need attention budget, not more lanes |

Full fleet table, per-lane notes, P&L caveats, and per-host follow-up
queries are recorded in the chat transcript for this session and should
not be duplicated here.

## 3. Actions taken this session (read-only and docs-only)

### 3a. Verified Bot J audit findings against current code

**Result:** Two of the audit's P0/P2 items are already fixed in
`bots/bot_j_nr_wallet/executor.py`. No edit was made.

- P0a — dead `after` variable: `run_once()` already calls
  `_qualifying_trades(con, after_ingested_at=after)` at line 277. The
  audit's "lines 247-248" referred to an earlier file state.
- P2 — silent YES default: `_token_side()` at lines 167-176 already
  returns `None` and logs `bot_j.unknown_token_side` when `outcome` is
  unparseable; the caller at line 197 skips the entry instead of
  defaulting to YES.

This is what "double-check everything before acting" caught — the
audit-driven one-line fix would have been a no-op.

### 3b. Captured remaining Bot J audit gaps as `OQ-113`

Added [`OQ-113`](open-questions.md#oq-113-bot-j-audit-remediation-gate-claude--empirical)
to `docs/open-questions.md`. Bundles the still-open audit items:

- P0b — strict-settlement gate unreachable (`0 / 1,619` proxy-settled
  markets fire the `settled=1` query; threshold of `50` will never
  trigger).
- P1 — daily entry cap (`10/day` samples `~15%` of qualifying conditions;
  operator decision whether to raise to `20/day`).
- P1 — signal concentration (one wallet at `64%/89%` of entries/edge;
  needs leave-one-out edge check at `n>=200`).
- P2 — sports keyword over-matching (`4.3%` FP rate today, fragile).
- P3 — hardcoded fee assumption + GBP rate `0.79`.
- Investigate — `65%` NULL-question gap on qualifying cohort trades.

OQ-113 explicitly records the **already-cleared P0a/P2 items** to avoid
future re-audits chasing already-resolved findings.

### 3c. Captured Bot K survivorship-bias gap as `OQ-114`

Added [`OQ-114`](open-questions.md#oq-114-bot-k-near-term-forward-sample-gate-empirical)
to `docs/open-questions.md`. The Becker replay's `+506%` ROI is
survivorship-biased (first on-chain fill per market — markets with zero
fills excluded). Bot K's first `4` paper entries are all far-dated
2026 World Cup / NBA Finals futures, so forward resolution will not
materialise in usable time without scope changes.

OQ-114 sets the near-term forward-sample gate: `n_near_term >= 50` closes
with `time_to_resolution_hours < 168` at entry, forward WR >= `60%`,
forward net ROI >= `+20%` after fees, cross-league spread, esports
sub-segment WR >= `60%`, and forward ROI ex-largest-`5` still positive.

### 3d. Bot L not given a new OQ — already covered

Originally planned `OQ-115` for Bot L depth/queue/slippage haircut gate.
**Skipped after re-reading `OQ-111`**: the Bot L OQ already specifies
the full haircut/concentration/depth/symbol-control set. Session 363/364
have already implemented several of the audit next-actions (crossed-book
rejection, BUY/SELL P&L split, daily report, 9-combo sensitivity sweep).
A new OQ would have duplicated open work.

### 3e. Session header bumped

`docs/open-questions.md` header now reads:

```
**Last updated:** 2026-05-14 — Session 366 added Bot J audit-remediation
gate (OQ-113) and Bot K near-term forward-sample gate (OQ-114).
```

Quick Index "active count" raised from `78` to `80`.

## 4. What was deliberately NOT touched

- **No git commit.** The main working tree carries a large uncommitted
  diff (registry expansion, dashboard, scripts, tests) plus today's
  Session 365 edits to `MEMORY.md` / `CHANGELOG.md` / `docs/open-questions.md`
  / Bot L scripts. Bundling all of that under a fleet-review commit would
  be a wider scope than this session and pending operator decision per
  CLAUDE.md decision-authority rules.
- **No service restarts.**
- **No live wallet, cap, threshold, city, source, or strategy-gate
  changes.**
- **No edits to `MEMORY.md` or `CHANGELOG.md`** in this pass — Session 365
  was already mid-flight on those files. This summary doc is the
  chat-history-on-file the operator asked for; the standard MEMORY/CHANGELOG
  entry for Session 366 is left for the operator (or next claude-mem
  closeout pass) to write atomically with whatever else is being
  committed.
- **No commit of other people's work.** I will not stage and commit
  Sessions 354-365 changes that I did not produce.

## 5. Backlog discovered but not actioned (small follow-ups)

These were noticed during the review and are flagged for a future
session, not silently fixed:

1. **`docs/active-operating-model-2026-05-02.md` is out of date** — it
   does not list `bot_j_nr_wallet`, `bot_k_sports_taker`,
   `bot_l_complete_set`, or `wallet_observer`, and the Weather Fade Live
   Probe row still shows pre-ADR-158 caps (`$5` shares / `$50` daily
   gross / `$50` open exposure). Refresh to `$3` per ADR-118 size, the
   `$150` daily gross / `$200` open exposure from ADR-158, and add the
   missing four lanes.
2. **Duplicate `OQ-103`** — both "Bot D Polymarket settlement
   rounding/floor rule verification" and "Strict settlement backfill bias
   check for wallet-tag sports cohort" use the same number. Pre-existing
   inconsistency; renumber one in a future closeout pass.
3. **Bot K discovery filter** — adding a
   `time_to_resolution_hours <= 168` ceiling to
   `bots/bot_k_sports_taker/executor.py` would make Bot K immediately
   capable of producing near-term forward closes. Held back here because
   it is a strategy-touching change and OQ-114 wants the operator to
   pick between "add TTR ceiling" vs "relax `initial_yes_price` band".
4. **`bot_f_momentum_paper` 30-day kill clock.** Service has been live
   since ADR-142 (2026-05-09) and has placed `0` entries since deploy.
   30-day kill is approaching; either loosen the PASS-cell filter once
   or retire the timer.
5. **Bot D paper resolution path** — Session 354 cleared `16` stale
   `PAPER_OPEN` orders but the `4` past-end open paper positions remain
   open due to the token/status mismatch in the paper-resolution
   reconciler. This affects the +$89.36 realised vs $449.16 open ratio
   on `bot_d` paper.

## 6. Where to pick this up

Next-session entry point, in order:

1. Read this doc + `docs/open-questions.md` OQ-113 / OQ-114.
2. Decide P1 daily-cap raise for Bot J (operator-only call).
3. Either implement Bot J P0b settlement-gate redesign (Claude) or
   accept it stays paused until the wallet-tag strict-settlement
   backfill-bias OQ produces a designed path.
4. Either add the Bot K TTR ceiling or relax the price band (operator
   picks).
5. Refresh `docs/active-operating-model-2026-05-02.md` (mechanical:
   four new lane rows + Bot D live cap update + dashboard rule
   already covers the new rows).
6. Decide whether to bundle the uncommitted Sessions 354-365 +
   Session 366 edits into one commit (operator approval per CLAUDE.md
   commit-cadence rules).
7. Monitor Bot D live (next 20 closes under new caps) and Bot G
   high-tail probe (any fills under the ADR-149 epoch).

## 7. P&L caveats locked in writing

These are the easy-to-misquote numbers — keep them flagged:

- **Bot G Prime paper `+$282.95` collapses to `+6.5%` ROI ex-top-two.**
- **Wallet-Tag Feature Shadow `-$54k` / `+$13k` numbers are synthetic
  shadow** mirroring watched-wallet stake sizes — not operator capital.
  Dashboard tags them `synthetic_shadow`.
- **Bot K `+506%` Becker ROI uses survivorship-biased first-fill-per-market
  proxy + fixed-`$5` normalization.** Not a forward expectation.
- **Bot J `+23.2%` mean return is concentrated** in one wallet
  (`0x397e4f...`); p-value `~0.08`.
- **Bot I Persistence bootstrap `+15.85%` is stronger than post-V2
  forward**; gates must be allowed to reject.
- **Bot L `+$1.9665` (now `+$3.1252` / `+$2.4860` after Session 363-364
  audit work) is simulated executable on a flat haircut**, with
  concentration (`top-1` `15-24%`, `top-3` `29-46%`) and depth
  validation still open per OQ-111.
- **Bot G Prime Live current epoch starts at `$0`/`0` fills**; do not
  read pre-2026-05-10 archive into the new probe.
- **Bot D Live `+$35.39 / +20.17%` is pre-ADR-158 cap raise** which
  happened today. Forward evidence must be re-measured under the new
  envelope.

---

**End of session 366 summary.**
