# Task 5 — Parallel Model Verification Log

**Date:** 2026-04-14
**Tool:** `~/.claude/scripts/model_call.py`
**Privacy posture:** Only public-doc-derived drafts (CLOB spec, ToS brief, reference code) were routed to external models. No oraclemangle data, no private keys, no wallet addresses left the machine.

---

## Routing

| Draft | Model | Provider | Rationale |
|---|---|---|---|
| `clob-spec.md` | Kimi K2 (via Groq) | Groq — LPU, no training on prompts | Gemini first-choice but 429'd; Kimi K2 is strong adversarial reasoner |
| `tos-eligibility.md` | Llama 3.3 70B (Groq) | Groq | Fast fact-check against 2024–2025 baseline knowledge |
| `order-example.py` + `order-placement-reference.md` | Llama 3.3 70B (Groq) | Groq | Local-qwen35 was attempted but produced no output; swapped to Groq |

**Failure noted:** `gemini-2.5-flash` returned 429 rate-limit on first attempt. Retry skipped — Kimi K2 covered the same fact-check ground. `local-qwen35` (SSH to the local workstation) initially appeared to hang (0-byte output for several minutes) so Groq was swapped in. Qwen eventually completed and its output is summarised below — Groq finding set is retained as primary; Qwen adds useful operational detail.

### Qwen (local, the local workstation M1 Max) — late arrival

High-level verdict: **"cryptographically sound but operationally fragile."** Concurs with Groq on no critical key-leak paths. Adds operational recommendations:
- Wrap `post_order` in `tenacity` with `wait_exponential(0.5–8s)` + `retry_if_exception_type((PolyApiException, ConnectionError, TimeoutError))` — don't reinvent retry logic
- Stage rollout: Amoy (chainId 80002) → mainnet only after E2E on testnet passes
- Monitor 429 counts; if they're common, throttle at application layer rather than increasing retry budget
- Verify HMAC integrity by independently constructing the expected canonical string and comparing against client output before trusting auth end-to-end


---

## Findings — CLOB Spec (Kimi K2)

No factual errors or contradictions flagged. All findings were gaps already present in the deliverable or additional reasonable gaps:

**Confirmations (Kimi agreed with my own flags):**
- [MISSING] exact minimum order size value
- [MISSING] WebSocket connection-cap and per-IP limits
- [MISSING] exact HMAC canonical string format
- [STALE] collateral still listed as USDC.e; native-USDC migration status unclear
- [STALE] verifyingContract addresses inferred from community sources

- [MISSING] order-ID collision / reuse policy
- [MISSING] nonce overflow / wrap-around behaviour for long-running bots
- [MISSING] explicit error-code list (INSUFFICIENT_BALANCE, INVALID_PRICE_TICK, etc.)
- [MISSING] deposit/withdrawal automation flow
- [MISSING] funding-automation details for USDC.e bridge

**Verdict:** CLOB spec is directionally correct. Six additional gaps to verify empirically before production.

---

## Findings — ToS brief (Llama 3.3 70B)

Llama largely confirmed the research findings:

- UK explicit block: **consistent with prior knowledge** (pre-2024 baseline)
- Empty canonical ToS page: **flagged as a new development** worth noting — may indicate Polymarket is restructuring how they publish terms
- No separate API ToS: **consistent with prior knowledge**
- Official CLOB SDKs imply programmatic use is intended, yet terms governing it are **unclear**
- Geoblocking FAQ says orders from blocked regions will be rejected — **unclear whether this reliably applies to API calls** (since API bypasses the front-end click-through attestation)
- UKGC / FCA not explicitly cited by Polymarket but "likely relevant to the UK block"
- VPN prohibition likely applies to API use but not confirmed
- Polymarket US (QCX LLC, CFTC-regulated DCM) is separate from international (Adventure One QSS Inc.) — confirmed
- Definitions of "Restricted Persons" / "Prohibited Jurisdictions" not publicly pinned down — an inherent limitation of the empty-ToS problem
- Secondary sources (Datawallet, Trade the Outcome) may not be fully up-to-date — worth caveating

**Verdict:** ToS brief is accurate to the extent public information allows. The core uncertainty (what the operative clauses actually say, and whether API use constitutes acceptance) is an **irreducible legal ambiguity** that only counsel or direct correspondence with Polymarket can resolve.

---

## Findings — Reference code (Llama 3.3 70B)

No critical security vulnerabilities found. Flags raised were mostly defensive suggestions appropriate for production but out of scope for a reference script:

**Relevant flags:**
- [SECURITY] No explicit validation that `POLYMARKET_PK` env var is a valid 0x-prefixed Ethereum private key before use
- [BUG] `SIGNATURE_TYPE` env var not validated to one of 0/1/2
- [BUG] `build_l2_client` doesn't handle the case where `FUNDER` is set but `POLYMARKET_SIG_TYPE` is not
- [UNSAFE] Hardcoded price/size in the example — by design, but flag for anyone copy-pasting

**Noise (ignored):**
- "No rate limiting to prevent brute force" — not applicable; this is a client, not a server
- "No logging" — intentional (we don't want to log in a PK flow)
- Generic "no error handling" nits — reference script, not production

**Verdict:** The reference script is safe as written. The agent-authored deliverable correctly implements env-only key loading, does not log sensitive material, and guards mainnet writes behind commented-out calls with a hard abort unless `NETWORK=mainnet` is explicitly set. Small hardening (PK-format validation, sig_type enum check) is worth folding in when this becomes production code, not now.

---

## Cross-referenced confidence table

| Finding | Source 1 (my draft) | Source 2 (model) | Resolved? |
|---|---|---|---|
| Fee V2 math | Verified from Polymarket changelog | — | Yes |
| UK explicit block | Polymarket Help Center | Llama 3.3 confirms | Yes |
| CLOB host + chainId | py-clob-client source | — | Yes |
| L1/L2 auth headers | Polymarket docs | — | Yes |
| USDC.e (vs native USDC) | Polymarket docs | Kimi flags potential staleness | **Needs empirical verification** |
| verifyingContract addresses | Community | Kimi flags inference | **Needs empirical verification** |
| Min order size | Community ($1–$5) | Kimi agrees no published value | **Needs empirical verification** |
| HMAC canonical string | Inferred | Kimi flags undocumented | **Needs source read** |
| py-clob-client key handling | Task 2 direct source read | Llama flags minor hardening | Yes (plus hardening notes) |
| API terms for bots | Empty ToS page | Llama flags irreducible ambiguity | **Needs counsel** |

---

## Residual uncertainties after verification

1. **USDC.e vs native USDC** — resolve with a live `GET /supported-assets` call before wiring the deposit/approval flow.
2. **Exchange contract addresses** — cross-check against `py_order_utils/config.py` in the actual pip-installed package.
3. **Minimum order size** — resolve empirically by reading `INVALID_ORDER_MIN_SIZE` rejection from a dry-run tiny order.
4. **HMAC canonical string format** — resolve from `py_clob_client/signing/hmac.py` source.
5. **UK ToS acceptance via API** — counsel required; no model can answer this.

---

*Privacy check:* Confirmed no PII, no repo-specific content, no keys, and no wallet addresses were included in any of the external-model prompts above. The deliverables routed (CLOB spec, ToS summary, reference code) are entirely derived from public documentation and safe-by-design reference code.
