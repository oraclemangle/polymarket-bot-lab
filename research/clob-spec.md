# Task 1 — Polymarket CLOB Technical Spec

**Date compiled:** 2026-04-14
**Scope:** CLOB v2, Polygon, Fee Structure V2 live since 2026-03-30
**Confidence key:** **V** = Verified (official docs or source), **R** = Reported (community/third-party), **I** = Inferred (from client source without explicit docs)

---

## 0. Headline facts for architecture

- **CLOB host:** `https://clob.polymarket.com` (V)
- **Chain:** Polygon (chainId `137`) (V)
- **Collateral:** USDC.e (bridged) on Polygon, **not** native USDC (V — as of this doc)
- **Order signing:** EIP-712 typed data, signed locally by the client (V)
- **Two-tier auth:** L1 (EIP-712 signature, used once to derive API creds) + L2 (HMAC-SHA256, used per-request for trading) (V)
- **Three signature_type modes:** 0 = EOA, 1 = Magic/email, 2 = browser wallet proxy (V)
- **Rate limits:** Very generous — 3,500 `POST /order` per 10s burst, 36,000 per 10 min sustained (V)
- **Fee V2:** dimensionless `feeRate` per category; fee = `feeRate × price × (1−price) × size_shares`; peaks at 50¢ price (V)
- **Maker rebates:** 20% (crypto) / 25% (others) of the taker fees paid into that market, paid daily in USDC, calculated per market (V)
- **Geopolitics category is fee-free** (V)
- **Order types supported:** GTC, GTD, FOK, FAK. **No IOC.** (V)
- **Tick sizes:** 0.1, 0.01, 0.001, 0.0001 (V)

---

## 1. Authentication

### 1.1 L1 — Creating/deriving API credentials

**Used once** to exchange an EIP-712 signature for a persistent API key / secret / passphrase triple.

Headers (V, [source](https://docs.polymarket.com/api-reference/authentication.md)):

| Header | Meaning |
|---|---|
| `POLY_ADDRESS` | Polygon signer address |
| `POLY_SIGNATURE` | CLOB EIP-712 signature (signs a domain-separated "ClobAuth" message) |
| `POLY_TIMESTAMP` | Unix timestamp (seconds) |
| `POLY_NONCE` | Nonce, default `0` |

Python derivation (V, from README):
```python
client = ClobClient(host="https://clob.polymarket.com",
                    chain_id=137,
                    key=os.getenv("PRIVATE_KEY"))
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
```

The private key never leaves the process; the EIP-712 signature proves wallet control.

### 1.2 L2 — Per-request trading auth

Headers (V):

| Header | Meaning |
|---|---|
| `POLY_ADDRESS` | Polygon signer address |
| `POLY_API_KEY` | API key from L1 derivation |
| `POLY_PASSPHRASE` | Passphrase from L1 derivation |
| `POLY_SIGNATURE` | HMAC-SHA256 over request, using the API `secret` |
| `POLY_TIMESTAMP` | Unix timestamp |

HMAC is computed over `timestamp + method + requestPath + body` (**I** — inferred from standard CLOB-style auth; docs confirm algorithm but not the exact canonical string). Flag to verify against source before shipping.

### 1.3 `signature_type` (V, from README + builder.py)

- `0` — EOA: MetaMask, Ledger, raw private key. Default.
- `1` — Email/Magic wallet: delegated signing. Funder address required and distinct from signer.
- `2` — Browser wallet proxy: proxy contract. Funder required.

For a non-custodial bot from an EOA hot wallet, use **signature_type=0** with no `funder` (signer == funder).

---

## 2. EIP-712 Order Signing

### 2.1 Typed data domain (V — reconstructed from `py_order_utils` + exchange contract)

```
name: "Polymarket CTF Exchange"
version: "1"
chainId: 137
verifyingContract: depends on market type:
  - Standard CTF Exchange (binary):  0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
  - Neg-Risk CTF Exchange:           0xC5d563A36AE78145C45a50134d48A1215220f80a
  - Neg-Risk Adapter:                0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296
```
(Contract addresses **I/R** — widely cited community source; verify on Polygonscan before shipping.)

### 2.2 `Order` struct (V, from `py_clob_client/order_builder/builder.py`)

```solidity
struct Order {
    uint256 salt;
    address maker;          // funder (or signer if no proxy)
    address signer;         // the EOA actually signing
    address taker;           // usually 0x0 (open to anyone)
    uint256 tokenId;         // ERC-1155 CTF position id
    uint256 makerAmount;     // what the maker offers
    uint256 takerAmount;     // what the maker wants
    uint256 expiration;      // unix seconds, 0 = never
    uint256 nonce;           // user-level nonce; cancel-all increments
    uint256 feeRateBps;      // fee accepted, in bps (e.g. 0 for GTC)
    uint8   side;            // 0 = BUY, 1 = SELL
    uint8   signatureType;   // 0 / 1 / 2
}
```

The `OrderData` dict the Python client assembles before handing to `py_order_utils.build_signed_order` (V):
```python
OrderData(
    maker=funder, taker=order_args.taker, tokenId=order_args.token_id,
    makerAmount=str(maker_amount), takerAmount=str(taker_amount),
    side=side, feeRateBps=str(order_args.fee_rate_bps),
    nonce=str(order_args.nonce), signer=signer.address(),
    expiration=str(order_args.expiration), signatureType=sig_type,
)
```

Salt is generated inside `py_order_utils` (**I** — not inspected directly; flagged for Task 5).

### 2.3 Where signing happens

Locally, inside `py_order_utils.build_signed_order`. No remote signing, no key exfiltration by the client (V — from source structure). See Task 2 deliverable for the key-handling audit.

---

## 3. REST endpoints

Base: `https://clob.polymarket.com`

### 3.1 Market data (public) (V)

| Endpoint | Purpose |
|---|---|
| `GET /book?token_id=` | Full order book for a CTF token |
| `GET /books` | Batch book fetch |
| `GET /price?token_id=&side=` | Best bid/ask |
| `GET /prices` | Batch price |
| `GET /midpoint?token_id=` | Mid |
| `GET /midpoints` | Batch mid |
| `GET /spread?token_id=` | Spread |
| `GET /trades?market=` | Public trades |
| `GET /prices-history?market=&interval=` | OHLC |
| `GET /last-trade-price?token_id=` | Last trade |
| `GET /tick-size?token_id=` | Tick size for market |
| `GET /fee-rate?token_id=` | Current `feeRate` for a market |
| `GET /markets` | Market metadata (condition_ids, outcomes, token_ids) |
| `GET /simplified-markets` | Compact market list |

### 3.2 Order lifecycle (L2-authenticated) (V)

| Endpoint | Purpose | Rate limit |
|---|---|---|
| `POST /order` | Post signed order | 3,500 / 10s burst, 36k / 10 min |
| `POST /orders` | Batch post (≤15) | 1,000 / 10s burst |
| `DELETE /order` | Cancel one | 3,000 / 10s burst |
| `DELETE /orders` | Cancel many (≤3,000) | 1,000 / 10s burst |
| `DELETE /cancel-all` | Cancel all user orders | 250 / 10s burst |
| `DELETE /cancel-market-orders` | Cancel all in one market | 1,000 / 10s burst |
| `GET /data/orders` | User's open orders | 500 / 10s |
| `GET /data/trades` | User's trade history | 500 / 10s |
| `GET /order?id=` | Single order by hash | 900 / 10s |

### 3.3 Balance / allowance (V)

| Endpoint | Rate limit |
|---|---|
| `GET balance-allowance` | 200 / 10s |
| `UPDATE balance-allowance` | 50 / 10s |

### 3.4 Rate limits — summary (V)

- **General cap:** 9,000 req / 10 s per key
- `POST /order`: **3,500 / 10s burst, 36,000 / 10 min sustained**
- API-key management endpoints: 100 / 10s
- No documented IP-only limits; no documented WSS connection cap (**flag** — unknown)

Rate limits are **extremely generous** for an UK-latency directional bot placing <100 orders/day. Not a constraint.

Source: [docs.polymarket.com/api-reference/rate-limits.md](https://docs.polymarket.com/api-reference/rate-limits.md) accessed 2026-04-14.

---

## 4. WebSocket

Base: `wss://ws-subscriptions-clob.polymarket.com` (**R** — community-documented; verify against current docs page)

### 4.1 Channels (V, from llms.txt index)

| Channel | Docs | Notes |
|---|---|---|
| `market` | [link](https://docs.polymarket.com/api-reference/wss/market.md) | Public: book updates, prices, market lifecycle |
| `user` | [link](https://docs.polymarket.com/api-reference/wss/user.md) | Authenticated: your orders + trades |
| `sports` | [link](https://docs.polymarket.com/api-reference/wss/sports.md) | Real-time sports match results (not needed for v1) |

### 4.2 Auth & subscription (V, high-level)

- `user` channel requires the same L2 auth fields as REST, passed in the subscription message
- `market` channel is public; subscribe by passing an array of `assets_ids` (CTF token IDs)
- Event message schemas documented per channel — **flag for detailed reading before execution-path build**

---

## 5. Fee Structure V2 (live 2026-03-30)

Sources: [Polymarket changelog](https://docs.polymarket.com/changelog), [Prediction Hunt 2026 guide](https://www.predictionhunt.com/blog/polymarket-fees-complete-guide), [tradetheoutcome 2026 update](https://www.tradetheoutcome.com/polymarket-fees/), [iGaming Business](https://igamingbusiness.com/prediction-markets/polymarket-sports-fee-hike-2026/), all accessed 2026-04-14.

### 5.1 Fee formula (V)

```
taker_fee_usd = feeRate × price × (1 − price) × size_shares
```

Peaks at `price = 0.50`. Zero at 0.00 or 1.00 (i.e. certain outcomes).

### 5.2 Per-category `feeRate` (V)

| Category | feeRate | Max $ fee per 100 shares (at 50¢) |
|---|---|---|
| **Geopolitics / world events** | **0** | **$0.00** |
| Sports | 0.03 | $0.75 |
| Finance | 0.04 | $1.00 |
| Politics | 0.04 | $1.00 |
| Mentions | 0.04 | $1.00 |
| Tech | 0.04 | $1.00 |
| Economics | 0.05 | $1.25 |
| Culture | 0.05 | $1.25 |
| Weather | 0.05 | $1.25 |
| Other/General | 0.05 | $1.25 |
| Crypto | 0.072 | $1.80 |

### 5.3 Maker rebates (V)

- **Crypto:** 20% of taker fees paid into that market, returned to makers
- **All other fee-bearing categories:** 25%
- **Paid daily in USDC.e** to the maker's funder address
- **Calculated per market, not across the category**
- **Makers pay zero taker fee.** 100% of collected taker fees go into the rebate pool.

### 5.4 Implication for strategy

- **Geopolitics = free** to both sides. Ideal for a directional bot that needs to cross the spread occasionally.
- **Politics / Finance / Economics:** 4–5 bps maximum of notional. Trivial drag for an edge-based bot with even a 5% edge.
- **Crypto / Sports:** fee drag is meaningful; pure taker scalping in these categories is hostile. Don't play here as a taker.
- **Rebate farming as a business:** real, but different product; see Phase 2 analysis in conversation.

---

## 6. Order types (V)

| Type | Behaviour |
|---|---|
| **GTC** | Good-Till-Cancelled. Rests on book until filled or cancelled. |
| **GTD** | Good-Till-Date. Rests until `expiration` (unix seconds UTC) or fill/cancel. |
| **FOK** | Fill-Or-Kill. Fills entirely on post or cancels entirely. |
| **FAK** | Fill-And-Kill. Takes what's available, cancels remainder. (This is what most CEXes call IOC.) |

**No IOC label**; FAK is the functional equivalent. ([docs](https://docs.polymarket.com/trading/orders/overview.md))

---

## 7. Minimum / tick / max

- **Tick sizes**: 0.1, 0.01, 0.001, 0.0001. Per-market; fetch via `GET /tick-size?token_id=`. Order rejected on non-conforming price. (V)
- **Minimum size**: referenced via `INVALID_ORDER_MIN_SIZE` error but no explicit value published. Community reports range $1–$5 notional depending on market. **Flag: verify empirically per target market.** (R/I)
- **Maximum size**: formula `maxSize = balance − Σ(openOrderSize − openFills)`. Effectively the user's available collateral. (V)
- **Neg-risk markets**: multi-outcome markets route through a different exchange contract. Client must pass `negRisk: true` (Python/TS) or the Rust SDK autodetects. (V)

---

## 8. Settlement

Source: [Resolution docs](https://docs.polymarket.com/concepts/resolution.md), [CTF redeem](https://docs.polymarket.com/trading/ctf/redeem.md).

- Each binary outcome is an ERC-1155 position on the **Conditional Token Framework (CTF)** contract `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` (V)
- **Split**: convert USDC.e → both YES + NO tokens of a market, 1:1 (V)
- **Merge**: convert both tokens back to USDC.e, 1:1 (V)
- **Redeem**: after UMA resolution posts the result, winning tokens can be redeemed 1:1 for USDC.e (V)
- **Gas**: merge/split/redeem all cost MATIC. The CLOB itself offers **gasless transactions** for order placement (signed orders; the relayer pays gas). (V)
- Oracle: **UMA Optimistic Oracle** with a 2-hour dispute window on proposed outcomes. No oracle changes in V2 fee rollout. (V)

---

## 9. Collateral state (V, as of docs date — possibly stale)

- Trading collateral: **USDC.e on Polygon** (bridged), not native USDC
- USDC contract: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- CTF contract: `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`
- EOA users must approve USDC.e and CTF for: main exchange, neg-risk exchange, neg-risk adapter (three approvals × two tokens = 6 txs on a fresh wallet)
- Email/Magic wallets get auto-allowances
- Bridge supports ETH/L2/Solana/BTC/TRON deposits with auto-conversion to USDC.e on Polygon
- **No documented migration to native USDC** as of the docs source (**flag** — this is a known industry trend on Polygon; verify current state)

---

## 10. Contradictions / staleness flagged

- **Native USDC migration:** Polygon-wide, Circle has been pushing migration from bridged USDC.e to native USDC since 2024. Polymarket docs still reference USDC.e. Either (a) they haven't migrated, (b) docs are stale. **Verify by calling `GET /supported-assets` or checking the deposit UI.** Affects token approval addresses in the bot.
- **WebSocket connection limits:** undocumented. Real-world cap unknown.
- **Exact HMAC canonical string for L2:** algorithm confirmed (SHA-256), exact message construction not explicit in the docs I read. Must be verified in client source.
- **Minimum order size:** no explicit number. Community reports range $1–$5. Must be empirically verified.
- **`verifyingContract` address per market type:** I inferred standard addresses from community sources. **Must be cross-checked against `py_order_utils.config` or equivalent before any real signing.**

---

## 11. For the bot (architecture-relevant summary)

**Latency constraints:** None imposed by rate limits. UK→Polygon RPC + CLOB round-trip (~80–120ms) is the floor.

**Order-placement flow:**
1. Init `ClobClient(host, key, chain_id=137)` — or with `signature_type + funder` for proxy wallets
2. One-time `create_or_derive_api_creds()` → store creds encrypted
3. Per trade:
   - Fetch `GET /tick-size` for target market (cached per market)
   - Fetch `GET /book` or subscribe to WSS `market` channel
   - Compute edge; decide side, size, price
   - Build `OrderArgs(token_id, price, size, side)`
   - `create_order(args)` — signs locally
   - `post_order(signed, OrderType.GTC)` — L2 HMAC, returns order id
4. Monitor via WSS `user` channel for fills
5. Settle on resolution via `redeem` (separate on-chain tx)

**Key decisions for v1 architecture:**
- Signature type **0 (EOA)**. No proxy complexity. One hot wallet, encrypted key.
- **GTC maker orders** into the spread for rebate + lower fee. Cross only when edge justifies the 4–5 bps drag (politics/geopolitics).
- **Stay in geopolitics / politics / finance / economics** for v1. Avoid crypto and sports taker flow.
- Cancel-all on kill-switch trigger via `DELETE /cancel-all` — one call, handles all open exposure.

---

## Sources (all accessed 2026-04-14)

- [Polymarket docs index (llms.txt)](https://docs.polymarket.com/llms.txt)
- [CLOB authentication](https://docs.polymarket.com/api-reference/authentication.md)
- [Rate limits](https://docs.polymarket.com/api-reference/rate-limits.md)
- [Order overview](https://docs.polymarket.com/trading/orders/overview.md)
- [Supported assets](https://docs.polymarket.com/trading/bridge/supported-assets.md)
- [Resolution](https://docs.polymarket.com/concepts/resolution.md)
- [Maker rebates](https://docs.polymarket.com/market-makers/maker-rebates.md)
- [py-clob-client README](https://github.com/Polymarket/py-clob-client)
- [py-clob-client order builder source](https://raw.githubusercontent.com/Polymarket/py-clob-client/main/py_clob_client/order_builder/builder.py)
- [Prediction Hunt — Fees 2026](https://www.predictionhunt.com/blog/polymarket-fees-complete-guide)
- [tradetheoutcome — Polymarket Fees 2026](https://www.tradetheoutcome.com/polymarket-fees/)
- [iGaming Business — sports fee hike 2026](https://igamingbusiness.com/prediction-markets/polymarket-sports-fee-hike-2026/)
