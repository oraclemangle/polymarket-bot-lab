# Polymarket CLOB — Order Placement Reference (`py-clob-client`)

**Researched:** 2026-04-14
**Upstream commit:** `Polymarket/py-clob-client` main branch, cloned to `/tmp/polymarket-research/py-clob-client`
**Companion reference script:** `research/order-example.py (path relative to repo root)`

Confidence is flagged per section. HIGH = read directly from upstream source. MEDIUM = cross-referenced from third-party repo or TS client. LOW = inferred.

---

## 1. Init Ceremony — `ClobClient(...)` [HIGH]

Source: `py_clob_client/client.py` lines 117–165.

```python
ClobClient(
    host,                       # e.g. "https://clob.polymarket.com"
    chain_id=137,               # 137 = Polygon mainnet, 80002 = Amoy testnet
    key=PRIVATE_KEY,            # hex-string EOA key; None = L0 read-only
    creds=ApiCreds(...),        # HMAC creds for L2; None = L1 only
    signature_type=0,           # 0=EOA, 1=email/Magic proxy, 2=browser proxy
    funder=None,                # address holding USDC for proxy wallets
    builder_config=None,        # optional Polymarket Builder program headers
    tick_size_ttl=300.0,        # seconds to cache per-token tick size
)
```

Three auth levels:
- **L0** (host only) — open endpoints: `get_ok`, `get_order_book`, `get_markets`, server time.
- **L1** (host + chain_id + key) — can derive API creds, sign orders, read open orders. Uses EIP-712 auth headers.
- **L2** (host + chain_id + key + creds) — can POST orders, cancel, heartbeat, notifications. Uses HMAC-SHA256 headers keyed by `api_secret`.

Canonical L2 bootstrap (from README and `examples/order.py`):

```python
client = ClobClient(HOST, key=PK, chain_id=CHAIN_ID, signature_type=1, funder=FUNDER)
client.set_api_creds(client.create_or_derive_api_creds())
```

`create_or_derive_api_creds()` tries `derive_api_key` first (idempotent) and falls back to `create_api_key` (client.py lines 253–300). Both are L1-auth POST calls signed with the private key; the key itself never leaves the machine.

---

## 2. Key-Handling Model — Every Touchpoint [HIGH]

Tracing the private key through the codebase:

| Step | File | What happens |
|---|---|---|
| Loaded from env | `examples/order.py` | `key = os.getenv("PK")` |
| Passed to `ClobClient.__init__` | `client.py:142` | `self.signer = Signer(key, chain_id) if key else None` |
| Stored on `Signer` | `signer.py:8` | `self.private_key = private_key` (plaintext attr); `self.account = Account.from_key(private_key)` — **eth-account derives pubkey locally** |
| Used to sign CLOB auth (L1) | `signing/eip712.py:28` | `signer.sign(auth_struct_hash)` → `Account._sign_hash(hash, private_key).signature.hex()` — **signing is 100% local** |
| Used to sign orders | `order_builder/builder.py:153` | `UtilsSigner(key=self.signer.private_key)` passes key into `py_order_utils` for EIP-712 order signing — **also 100% local** |
| Never transmitted | — | grep for `private_key` in outbound requests: only the `.address()` derivative and signatures go on the wire |

**The PK is held as a plaintext instance attribute (`self.signer.private_key`) for the lifetime of the client**, because `OrderBuilder.create_order` rebuilds a `UtilsSigner(key=...)` on every call (builder.py:150–154, 189–193). There is no zeroization, no OS keyring, no HSM path. If your process gets a `/proc/<pid>/mem` read or a core dump, the key is exposed. Treat the client process as sensitive.

**Recommendation:** run the trading process in an isolated container/VM; load PK via a secret manager (1Password CLI, `sops`, AWS Secrets Manager) into the env only at process start; never persist it to disk.

---

## 3. Security Audit Findings [HIGH]

| Check | Result |
|---|---|
| Private key logged? | **No.** `grep logger\|print\|logging client.py` finds only 4 log sites, none reference `self.signer.private_key`. API keys are logged at debug by `poly-market-maker` (third party), but upstream never logs either secret. |
| API secret logged? | **No** by upstream. (poly-market-maker logs `api_key` at debug, but not secret.) |
| Key transmitted over network? | **No.** All signing is local via `eth_account.Account._sign_hash`. Only EIP-712 signatures, EOA address, and HMAC digests go on the wire. |
| Hardware-wallet path? | **No.** `Signer` requires a raw hex private key. No abstraction for Ledger/Trezor, no signer interface. The TypeScript `clob-client` DOES accept a `viem WalletClient` (hardware-capable); Python does not. |
| EIP-712 location | **Local.** `signing/eip712.py` builds the struct hash with `poly_eip712_structs` + `eth_utils.keccak`; `signer.py` signs with `eth_account`. No "signer service" indirection. |
| HMAC location | **Local.** `signing/hmac.py:6-22` uses stdlib `hmac` + `hashlib.sha256`. |
| TLS pinning? | **No.** Uses `httpx.Client(http2=True)` (`http_helpers/helpers.py:19`) with default CA bundle. A host-file or CA-compromise MITM could observe orders (not keys, since signing is local) and potentially replay-block posts. Low practical risk; flagged for completeness. |
| Timing-safe HMAC compare? | N/A — this is the signing side. Server does the compare. |
| Body-signature determinism | Good: `post_order` uses `serialized_body` with `json.dumps(..., separators=(",", ":"), ensure_ascii=False)` and sends `content=data.encode("utf-8")` so the exact bytes signed are the exact bytes sent (`client.py:631-636`, `helpers.py:40-47`). This is the fix for the known HMAC-mismatch bug. |

---

## 4. Rate-Limit & Retry Logic [HIGH]

**There is NO retry logic and NO rate-limit backoff in `py-clob-client`.**

- `request()` in `http_helpers/helpers.py:37-65`: one attempt, raises `PolyApiException` on any non-200 or transport error.
- The TS `clob-client` constructor exposes a `retryOnError` option; the Python client does NOT (confirmed by absence in `ClobClient.__init__` signature and no `tenacity`/`backoff` import).
- Known issue (#143, July 2025): Cloudflare intermittently blocks `create_order` posts. Users must implement their own retry + 429/403 handling in the caller.

**Recommendation for our code:** wrap `post_order` / `create_and_post_order` in `tenacity.retry` with exponential backoff (e.g. 3 tries, 0.5→2→8s, retry on 429/5xx and `PolyApiException`). Do **not** retry idempotently on network errors after the POST has been transmitted — you could double-post. Prefer to retry only on pre-send failures or explicit 429/5xx responses.

---

## 5. Mainnet-Touching vs Pure Compute [HIGH]

Pure-compute (no network, no funds movement):
- `ClobClient(host)` construction
- `Signer` instantiation, `Account.from_key`
- `create_order(order_args)` — returns a `SignedOrder`; just EIP-712 locally
- `create_market_order(args)` — same, but `calculate_market_price` fetches the book first (network read, no state change)
- `get_order_book_hash`, tick-size cache lookups

Network-read (no state change):
- `get_ok`, `get_server_time`
- `get_order_book`, `get_order_books`, `get_midpoint`, `get_price(s)`, `get_spread(s)`, `get_last_trade_price(s)`
- `get_markets`, `get_simplified_markets`, `get_market`

Authenticated reads (L1 / L2, read-only but identifying):
- `get_api_keys`, `get_orders`, `get_trades`, `get_balance_allowance`, `is_order_scoring`, `get_notifications`

**Mainnet write (posts order or mutates state):**
- `create_api_key` — writes an API-key record server-side
- `post_order`, `post_orders` — **submits signed order to matching engine**
- `create_and_post_order` — convenience = `create_order` + `post_order`
- `cancel`, `cancel_orders`, `cancel_all`, `cancel_market_orders`
- `drop_notifications`, `update_balance_allowance`, `post_heartbeat`
- RFQ flow (`rfq_create_quote`, `rfq_accept_quote`, etc.)

**Note:** orders only hit the on-chain exchange when matched. Posting is an off-chain matching-engine write; cancel before match = no on-chain tx. Once matched, settlement is via the Polymarket exchange contract (address varies by `neg_risk` flag and chain, resolved in `config.get_contract_config`).

---

## 6. Third-Party Usage Cross-Reference [MEDIUM]

### Polymarket/poly-market-maker (`poly_market_maker/clob_api.py`)
- Two-stage init: L1 client to derive creds, then replace with L2 client.
- Uses `create_and_post_order(OrderArgs(...))` — single-call convenience.
- Cancel via `client.cancel(order_id)` and `client.cancel_all()`.
- **No retry logic.** Generic try/except logs and returns `None`.
- Logs `api_key` at debug level. PK is not logged.

### Polymarket/agents (`agents/application/trade.py`)
- Wraps client in a higher-level `Polymarket` adapter (in `agents/polymarket/polymarket.py`, not inspected in depth).
- Retry pattern is a recursive `self.one_best_trade()` call in a bare `except Exception` — dangerous (stack growth, infinite loop potential). Do not copy.

### amadeusprotocol/polymarket-trading-bot
- Repo 404'd on fetch; possibly renamed or private. Low priority cross-ref, skipped.

---

## 7. Python vs TypeScript Client — Key-Handling Deltas [MEDIUM]

| Aspect | `py-clob-client` | `clob-client` (TS) |
|---|---|---|
| Key input | Raw hex private key only | ethers `Wallet` OR viem `WalletClient` |
| Hardware wallet | Not supported | Supported via viem transport |
| Retry on error | None | `retryOnError` constructor option |
| Signer abstraction | `Signer` wraps `eth_account` directly | Abstracted behind wallet client interface |
| Signing location | Local | Local |

**Upshot:** if you need Ledger/Trezor or out-of-process signing, use the TS client or build a custom `Signer` subclass that forwards `sign(hash)` to a hardware backend. The Python `Signer` class is only ~20 lines; monkey-patching or subclassing is straightforward if you later need it.

---

## 8. Gotchas & Operational Notes [HIGH]

1. **Allowances must be set once per wallet** for USDC and conditional tokens against 3 exchange contracts (main, neg-risk, neg-risk adapter). See README §"Token Allowances". EOA wallets will get silent no-fills if this is skipped. Magic/email wallets get it auto-set server-side.
2. **Body serialization is load-bearing.** HMAC is computed over the exact JSON bytes sent. Upstream fixed an edge case by using `serialized_body` and sending `content=data.encode("utf-8")` instead of `json=data`. If you build requests manually, replicate this exactly.
3. **Tick-size validation happens client-side** via `price_valid(price, tick_size)` — invalid prices raise before network. Tick size is cached 300s per token.
4. **`neg_risk`** is resolved per-token via a server round-trip, cached. Affects which exchange contract is used for signing.
5. **Heartbeat cancel-all**: if you call `post_heartbeat` once and then stop, the server cancels all your orders after 10s. Don't start a heartbeat you're not committed to maintaining.
6. **Fee rate** is server-dictated per market; passing a non-matching `fee_rate_bps` raises.
7. **`create_or_derive_api_creds` order of operations**: the function tries `derive` first; if the wallet has no API key yet, it falls through to `create`. Both paths log errors but do NOT log the resulting creds (upstream).

---

## 9. Sources

- `Polymarket/py-clob-client` (HIGH) — cloned and read verbatim at `/tmp/polymarket-research/py-clob-client`
- `Polymarket/poly-market-maker/blob/main/poly_market_maker/clob_api.py` (MEDIUM) — fetched via raw.githubusercontent.com
- `Polymarket/agents/blob/main/agents/application/trade.py` (LOW — adapter-layer only)
- `Polymarket/clob-client` README (MEDIUM) — cross-ref for TS deltas
- `Polymarket/py-clob-client` Issue #143 (July 2025) — Cloudflare block on order creation

---

## 10. TL;DR for Implementation

```python
# 1. Load PK from env; never hardcode.
# 2. ClobClient(host, key=PK, chain_id=137, signature_type=1, funder=FUNDER)
# 3. client.set_api_creds(client.create_or_derive_api_creds())
# 4. signed = client.create_order(OrderArgs(token_id, price, size, BUY))
# 5. resp = client.post_order(signed, OrderType.GTC)
# 6. client.cancel(resp["orderID"]) when done.
# 7. Wrap steps 4–5 in tenacity retry (429/5xx/PolyApiException).
# 8. Set token allowances once per EOA (README §Token Allowances).
# 9. Start on Amoy (chain_id=80002), promote to 137 only after E2E testing.
```
