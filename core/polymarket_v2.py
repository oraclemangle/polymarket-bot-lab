"""Polymarket V2 exchange constants (effective 2026-04-28 11:00 UTC).

Sources
-------
- https://docs.polymarket.com/v2-migration
- https://docs.polymarket.com/resources/contracts
- https://docs.polymarket.com/concepts/pusd

Fetched 2026-04-17, re-verified 2026-04-26 against Polymarket's V2 docs.
The originally-anticipated 2026-04-22 cutover slipped to 2026-04-28 in
the public announcement. V1 addresses retained for audit + during-
migration reference.

Migration semantics
-------------------
- **Conditional Tokens contract is UNCHANGED between V1 and V2** — YES/NO
  share ERC-1155 balances persist through the cutover. What changes is
  which exchange can match orders on those shares and what token acts as
  collateral in the settlement flow.
- **USDC.e remains on Polygon.** V2 wraps it 1:1 into pUSD via the
  CollateralOnramp. Unwrap is symmetric via the CollateralOfframp. Neither
  direction charges a fee per the docs (verify pre-launch). API-only
  callers must invoke ``CollateralOnramp.wrap()`` programmatically; the
  Polymarket UI handles this with one click for web users.
- **V1 exchange addresses stop matching orders after 11:00 UTC 2026-04-28.**
  Open orders are wiped during the maintenance window (~1h downtime).
  Do not deploy new bot code that references V1 exchange addresses after
  that instant.
- **EIP-712 domain version bumps from "1" to "2"** for the Exchange domain
  only. The L1/L2 ClobAuth domain stays at version "1" — getting this
  wrong silently invalidates auth signatures. py-clob-client-v2 handles
  the distinction internally.
- **Builder attribution moved on-chain.** The V1 ``HMAC headers + builder-
  signing-sdk`` flow is removed. V2 carries a single ``builderCode``
  (bytes32) field in the signed Order struct. Operator obtains this from
  Polymarket's settings UI; we plumb it via the ``POLYMARKET_BUILDER_CODE``
  env var into ``ClobWrapperV2``. Empty / unset → ``BYTES32_ZERO``
  (no attribution; orders still post fine).

All Polygon mainnet (chain_id=137). Checksum-encoded.
"""

from __future__ import annotations

POLYGON_CHAIN_ID = 137

# --- V2 Trading contracts -------------------------------------------------

CTF_EXCHANGE_V2 = "0xE111180000d2663C0091e4f400237545B87B996B"
NEG_RISK_CTF_EXCHANGE_V2 = "0xe2222d279d744050d28e00520010520000310F59"

# py-clob-client-v2 signs some neg-risk orders through this adapter, and the
# CLOB validates pUSD allowance against it before accepting the order.
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

# --- Unchanged from V1 (CTF ERC-1155 contract) ----------------------------

CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# --- Collateral infrastructure --------------------------------------------

PUSD_TOKEN_PROXY = "0xF00D000000000000000000000000000000000014"
PUSD_TOKEN_IMPLEMENTATION = "0xF00D000000000000000000000000000000000015"
COLLATERAL_ONRAMP = "0xF00D000000000000000000000000000000000016"
COLLATERAL_OFFRAMP = "0xF00D000000000000000000000000000000000017"
CTF_COLLATERAL_ADAPTER = "0xADa100874d00e3331D00F2007a9c336a65009718"
NEG_RISK_CTF_COLLATERAL_ADAPTER = "0xAdA200001000ef00D07553cEE7006808F895c6F1"

# --- USDC.e (bridged USDC on Polygon; unchanged) --------------------------

USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_E_DECIMALS = 6

# --- pUSD (same decimal semantics as USDC.e) ------------------------------

PUSD_DECIMALS = 6

# --- V1 exchanges (retained for audit; stop matching post-2026-04-22 11:00 UTC)

CTF_EXCHANGE_V1 = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_CTF_EXCHANGE_V1 = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

# --- EIP-712 domain versions ---------------------------------------------

EXCHANGE_DOMAIN_VERSION_V1 = "1"
EXCHANGE_DOMAIN_VERSION_V2 = "2"
L1L2_AUTH_DOMAIN_VERSION = "1"  # Unchanged across V1/V2.

# --- Endpoints ------------------------------------------------------------

CLOB_V2_ENDPOINT_TESTING = "https://clob-v2.polymarket.com"
CLOB_MAIN_ENDPOINT = "https://clob.polymarket.com"  # points to V2 after cutover

# --- Migration timestamp --------------------------------------------------

MIGRATION_CUTOVER_UTC_ISO = "2026-04-28T11:00:00+00:00"

# --- Builder attribution (V2) --------------------------------------------

# bytes32 default for builderCode and metadata fields. Used when the
# operator hasn't set ``POLYMARKET_BUILDER_CODE`` — the order still
# posts, just without builder-fee attribution. Polymarket accepts any
# valid bytes32 here, including all-zero.
BYTES32_ZERO: str = "0x" + "0" * 64


# --- Order-struct changes (for py-clob-client-v2 integration) -------------

ORDER_FIELDS_REMOVED_V2: frozenset[str] = frozenset(
    {"taker", "expiration", "nonce", "feeRateBps"}
)
ORDER_FIELDS_ADDED_V2: frozenset[str] = frozenset(
    {"timestamp", "metadata", "builder"}
)


# --- Sanity ---------------------------------------------------------------

_ALL_V2_ADDRESSES = (
    CTF_EXCHANGE_V2,
    NEG_RISK_CTF_EXCHANGE_V2,
    CONDITIONAL_TOKENS,
    PUSD_TOKEN_PROXY,
    PUSD_TOKEN_IMPLEMENTATION,
    COLLATERAL_ONRAMP,
    COLLATERAL_OFFRAMP,
    NEG_RISK_ADAPTER,
    CTF_COLLATERAL_ADAPTER,
    NEG_RISK_CTF_COLLATERAL_ADAPTER,
    USDC_E,
    CTF_EXCHANGE_V1,
    NEG_RISK_CTF_EXCHANGE_V1,
)


def all_v2_addresses() -> tuple[str, ...]:
    """Return the full list of V2-relevant addresses for auditing / preflight."""
    return _ALL_V2_ADDRESSES
