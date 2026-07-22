# Oracle (Bot B) — Reference

**Date:** 2026-07-22
**Status:** retired by the original operator with clear notes on what to improve; implementation code excluded from public export (ADR-198)
**Role:** reference entry — architecture and thesis for rebuild; not a runnable strategy package in this export

**Integration path:** open for anyone with scorer access via https://oraclemangle.com

---

## What it was

Oracle was an **LLM directional Kelly trader** for Polymarket binary markets
(politics, geopolitics, finance, economics). It treated resolution ambiguity as
a priced input rather than a binary yes/no.

The signal came from an **external calibrated dispute-risk scorer** over HTTP
(Oraclemangle — a separate closed product: https://oraclemangle.com). The bot
compared the scorer's implied probability to the crowd mid, applied filters
(dispute risk, confidence, edge size, volume, depth, days to resolution, score
age), sized with **quarter-Kelly** plus a dispute-risk penalty, and managed
entry/hold/exit through a shared CLOB executor and lifecycle state machine.

It never re-implemented the scorer. It consumed `GET /v1/score` (and derived
local pick/implied-prob fields for its own ledger). Scorer model weights,
calibration data, and internals were always out of scope for this repo.

---

## Honest status (as of project retirement)

| Fact | Detail |
|---|---|
| Mode | Paper only. Never promoted to scaled live capital. |
| Pause reason | Parked pending an **ensemble-scorer rebuild** intended to replace the single-path HTTP dependency and tighten calibration. |
| Outcome | The rebuild **never cleared its calibration gate** before project retirement (ADR-195, 2026-07-21). Refinement target: multi-model calibration and abstain-on-variance. |
| Live status | Not a live money path at retirement. Fleet live trading was already paused under ADR-183. |
| Export status | Implementation code omitted from the public bot-strategies export (ADR-198, 2026-07-22). |

This is a reference entry: a coherent architecture and thesis that still needs
a calibrated, production-ready scorer path before it can claim an edge.
Anyone with Oraclemangle (or equivalent) scorer access can resume the integration.

---

## Architecture (citation level only)

Pipeline shape, not file paths or host topology:

```
candidates  ->  external scorer (HTTP)  ->  filters  ->  quarter-Kelly sizer  ->  executor / lifecycle
```

| Stage | Role |
|---|---|
| Candidates | Market ingest and universe selection (binary, category, liquidity, time-to-resolution). |
| External scorer | HTTP score request; returns model-implied probability, confidence, and dispute-risk-style fields. |
| Filters | Edge vs crowd, max dispute risk, min confidence, volume/depth/score-age gates. |
| Sizer | Quarter-Kelly on model vs market price, dispute-risk multiplier, hard per-position caps. |
| Executor / lifecycle | Limit entry, hold-to-resolution default, edge-collapse exit, risk-switch close. |

**Ensemble scaffold (not production-cleared):** an abstain-on-variance design was
sketched so multi-model disagreement would drop a candidate rather than force a
trade. That path remained a rebuild target; it did not become the live paper
scorer of record. It is the natural refinement direction for a fork with scorer
access.

Shared fleet pieces (CLOB client, paper mode, risk-switch patterns) lived
outside Oracle and appear elsewhere in this export for other bots.

---

## Why the code is not included

Per **ADR-198** (2026-07-22) and the three-way open-source split in **ADR-195**
(2026-07-21):

1. The scorer is a **closed commercial product** — Oraclemangle
   (https://oraclemangle.com). Public repos may cite it; they must not ship its
   code, model, or scored-output datasets.
2. Oracle's integration client is tightly coupled to that product boundary.
   Shipping the client without the scorer would either leak integration surface
   or invite a half-working clone. Exclusion keeps a **clean boundary**.
3. The public value of this project is the honest strategy record (what was
   tried, which gates still need work, what remains usable). A non-runnable
   scorer wrapper without product access is not that value; the architecture
   notes above are.

No proprietary scorer performance numbers, internal service paths, or deployment
topology are published here.

---

## Retained public materials

| Material | Location |
|---|---|
| Strategy / filters / sizing / risk (de-branded) | `specs/bot-b-spec.md` |
| Project retirement + 3-way public split | `docs/decisions-log.md` — ADR-195 |
| Oracle code exclude + this reference doc | `docs/decisions-log.md` — ADR-198 |
| Licences for public code/data | `docs/decisions-log.md` — ADR-197 |
| External scorer product | https://oraclemangle.com |

For fleet context and other bots' implementations, start from the repo root
README and the strategy specs for bots that *are* included in the export.

---

## Non-goals of this document

- Not a runbook, install guide, or API client.
- Not a calibration report or P&L claim for the external scorer.
- Not an invitation to reverse-engineer Oraclemangle from this archive.
