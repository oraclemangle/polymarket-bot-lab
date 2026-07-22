# CLOB Preflight Verification — 2026-04-15

Resolves `docs/open-questions.md` OQ-006, OQ-007, OQ-008.

Method: read `py_clob_client` source from the pinned venv install, cross-check
against `core/config.py` constants, reproduce HMAC canonical string locally.

All three checks green via `scripts/preflight_check.py`.

---

## OQ-006 — HMAC canonical string format

**Source:** `.venv/lib/python3.11/site-packages/py_clob_client/signing/hmac.py`

```python
def build_hmac_signature(secret, timestamp, method, requestPath, body=None):
    base64_secret = base64.urlsafe_b64decode(secret)
    message = str(timestamp) + str(method) + str(requestPath)
    if body:
        message += str(body).replace("'", '"')
    h = hmac.new(base64_secret, bytes(message, "utf-8"), hashlib.sha256)
    return base64.urlsafe_b64encode(h.digest()).decode("utf-8")
```

**Key points:**
- Secret is stored base64-urlsafe-encoded; decode before use as HMAC key.
- Canonical string is `timestamp + method + path [+ body]` with **no separators**.
- Body serialisation is Python's `str(dict)` with `'` → `"` — this matches
  the Go/TypeScript JSON `{"k":"v"}` form (dict repr uses single quotes).
  Do NOT pre-JSON-serialise with `json.dumps`; pass the raw dict.
- Signature is SHA-256, base64-urlsafe-encoded.

Our `scripts/preflight_check.py::check_hmac()` reconstructs the same signature
independently and compares byte-for-byte. Green.

---

## OQ-007 — Exchange contract addresses

**Source:** `.venv/lib/python3.11/site-packages/py_clob_client/config.py::get_contract_config()`

**Polygon mainnet (chain_id=137):**

| Contract | Address |
|---|---|
| CTF Exchange | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` |
| Neg-Risk CTF Exchange | `0xC5d563A36AE78145C45a50134d48A1215220f80a` |
| Collateral (USDC.e) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |
| Conditional Tokens | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |

**Amoy testnet (chain_id=80002):**

| Contract | Address |
|---|---|
| CTF Exchange | `0xF00D000000000000000000000000000000000011` |
| Neg-Risk CTF Exchange | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` |
| Collateral | `0xF00D000000000000000000000000000000000012` |
| Conditional Tokens | `0xF00D000000000000000000000000000000000013` |

**Drift caught in Session 2:** `core/config.py` previously had a
`NEG_RISK_ADAPTER_ADDRESS` constant equal to the Amoy Neg-Risk Exchange,
which isn't what the name suggested. py-clob-client exposes no separate
"adapter" — only `exchange`, `collateral`, `conditional_tokens`. Renamed
and added the missing `CONDITIONAL_TOKENS_ADDRESS` + Amoy equivalents.

**Note on `py_order_utils`:** inspected at `.venv/lib/python3.11/site-packages/py_order_utils/`
— it contains no contract addresses; they flow in through py-clob-client's
`get_contract_config()` at order-building time. So the source of truth is
py-clob-client's config.py alone.

---

## OQ-008 — Collateral: USDC.e vs native USDC

**Source:** same py_clob_client config on chain 137: `0x2791Bca1...` (USDC.e).

Polymarket docs were correct. Circle's 2024 migration to native USDC
(`0x3c499c...`) on Polygon has NOT reached Polymarket; the bridged USDC.e
remains the collateral. Do not approve or deposit native USDC — funds will
not register.

Optional belt-and-braces: `python scripts/preflight_check.py --live`
additionally fetches `/supported-assets` and verifies the address is listed.
Not run by default (requires network).

---

## What this unblocks

- `ClobWrapper._guard_live()` can be flipped by calling `mark_preflight_done(True, True, True)`
  after `preflight_check.py --commit` writes the sentinel event.
- `scripts/dry_run_order.py` marks these three flags inline for Amoy runs.
- Week-2 Bot A can now be built against a CLOB path that has no unresolved
  auth/contract questions.

## If the pinned py-clob-client version changes

Re-run `python scripts/preflight_check.py`. If any of the three checks go
red, do NOT bump the version in production until the discrepancy is
understood and the relevant `Literal[...]` constants in `core/config.py`
updated.
