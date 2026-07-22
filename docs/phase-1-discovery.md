# Phase 1 — Discovery Audit

**Date:** 2026-04-14
**Status:** Superseded by later phases on strategy choice; retained for the context of the discovery findings.

---

## Purpose

Answer: what exists already, what's exploitable, what's legally/operationally feasible for a UK solo operator building a Polymarket trading bot. Do not write code. Do not pick a strategy yet.

---

## 1. External scorer (audit summary)

Phase 1 audited an externally calibrated dispute-risk scorer (Oraclemangle, a separate closed product — see https://oraclemangle.com). Its model, calibration corpus, pipeline internals, and performance figures are proprietary to that product and are not restated here.

**What a Polymarket bot can consume (API-level only):**
- Dispute-risk / resolution-prediction scores as probability inputs
- This repo's own Kelly sizer and risk layer built on those scores
- Liquidity checks and Gamma API market metadata (public Polymarket surfaces)

**Must build for a bot (this repo / operator infra):**
- CLOB order submission (L1/L2 auth, EIP-712 signing)
- Wallet/signer integration
- Settlement listener
- Position tracker + P&L
- Risk management + kill switches

The external scorer's runtime health, DB state, scrapers, and internal modules are outside this repo's scope; treat it as a closed dependency.

---

## 2. Legal / regulatory flags (for UK-based UK resident)

- **Polymarket geo-restriction**: UK explicitly blocked (confirmed later in Phase 2.5, `research/tos-eligibility.md`). Same block applies to the CLOB API per docs FAQ.
- **Canonical ToS** page renders empty HTML. Operative contract text unreadable from primary source.
- **UK tax treatment** of prediction-market PnL: three plausible HMRC positions (CGT on cryptoasset disposal, miscellaneous income, trade income + NI). Gambling treatment unlikely for a systematic bot. Specific advisor question: *"Does HMRC treat Polymarket ERC-1155 conditional-token PnL as CGT cryptoasset disposal, miscellaneous income, trade, or gambling for a UK-resident individual running an automated bot on an offshore venue?"*
- **offshore-worker's Earnings Deduction** does NOT cover PnL here — SED is employment income from qualifying sea service only.
- **Running a bot** (vs manual trading) pushes HMRC characterisation toward "trade."

---

## 3. Technical flags

- **CLOB architecture**: hybrid off-chain match + Polygon settlement via CTF Exchange.
- **Gas**: trivial (<$0.01 per op), but MATIC buffer + USDC.e approvals required.
- **Latency from UK**: 30–80ms to Polygon RPC. **Cannot compete on speed.** Must be edge-based, not speed-based.
- **Oracle tail risk**: UMA DVM disputes rare but expensive (full bond loss). 2025 Ukraine minerals case (~$7M allegedly manipulated) is the benchmark.
- **Fee Structure V2** (confirmed live 2026-03-30 in Phase 2 intel): geopolitics fee=0, politics/finance/economics ≤5 bps, crypto 7.2 bps, sports 3–7.5 bps. Maker rebates 20–25%.

---

## 4. Strategy realism (for solo LLM-edged operator)

**Realistic:**
- Ambiguous-resolution markets (external dispute-risk scorer thesis; see https://oraclemangle.com)
- Long-tail / low-liquidity narrative-driven markets
- Pre-resolution drift trades (3–14 days out)
- Cross-venue divergence (Polymarket / Kalshi / Manifold) — caveat: Manifold matcher broken, Kalshi KYC hostile

**Not realistic:**
- Binary sports/news speed trades (colocated MMs own these)
- Crypto price markets (HFT + perp-market arb dominate)
- Close-to-resolution election trades (headline latency game)

---

## 5. Operational flags

- **Key management**: Ledger for treasury, encrypted keystore for a dedicated hot wallet capped at the active-trading bankroll. Never >N days of expected capital on the hot wallet.
- **Kill switches**: max per-trade (% bankroll), max open exposure, max daily drawdown (auto-halt), unrecognised-market blacklist, price-staleness halt, oracle-in-dispute auto-halt.
- **Offline tolerance**: bot MUST run on the homelab hypervisor, not the local workstation. Mac sleeps, offshore work rotations are weeks long, satellite internet drops. Build assuming the operator is unreachable for 14 days. Kill switches fail closed.

---

## 6. Known unknowns flagged to user (now resolved)

Asked in Phase 1; resolved in Phases 2 / 2.5 / 3:

| Question | Resolved in | Answer |
|---|---|---|
| Current Polymarket ToS + UK geo-block | Phase 2.5 `tos-eligibility.md` | UK explicit block; ToS page empty |
| Current CLOB docs | Phase 2.5 `clob-spec.md` | Full spec captured |
| `py-clob-client` working example | Phase 2.5 `order-placement-reference.md` | Written, safe |
| Bot bankroll | Phase 3 (working assumption) | £5k pending user confirm |
| External scorer readiness | Phase 2.5 audit | Dependency health checked; treat as closed product (https://oraclemangle.com) |
| Sample external-scorer output shape | Phase 2.5 audit | API response shape reviewed for client integration |
| Tax advisor position | Phase 3 (working assumption) | (c) build + advise in parallel pending confirm |
| CLOB outages / UMA post-mortems | Phase 2 intel | Ukraine minerals 2025 remains benchmark |

---

## 7. What Phase 1 did NOT decide

- Which strategy to build
- Whether to couple to the external scorer (Oraclemangle — https://oraclemangle.com)
- Infrastructure choices
- Build sequence

All decided in Phase 3 (`docs/architecture-decision.md`).
