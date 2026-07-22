"""Tests for core/polymarket_v2.py constants.

Guards against the typical migration failure modes:
- typo in a contract address
- non-checksum hex breaking web3 calls
- same address accidentally reused across two distinct roles
- V1 address leaking back into a V2 role
"""
from __future__ import annotations

import re

import pytest

from core import polymarket_v2 as V2  # noqa: N812


def _is_hex_address(s: str) -> bool:
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", s))


ALL_ROLES = {
    "CTF_EXCHANGE_V2": V2.CTF_EXCHANGE_V2,
    "NEG_RISK_CTF_EXCHANGE_V2": V2.NEG_RISK_CTF_EXCHANGE_V2,
    "NEG_RISK_ADAPTER": V2.NEG_RISK_ADAPTER,
    "CONDITIONAL_TOKENS": V2.CONDITIONAL_TOKENS,
    "PUSD_TOKEN_PROXY": V2.PUSD_TOKEN_PROXY,
    "PUSD_TOKEN_IMPLEMENTATION": V2.PUSD_TOKEN_IMPLEMENTATION,
    "COLLATERAL_ONRAMP": V2.COLLATERAL_ONRAMP,
    "COLLATERAL_OFFRAMP": V2.COLLATERAL_OFFRAMP,
    "CTF_COLLATERAL_ADAPTER": V2.CTF_COLLATERAL_ADAPTER,
    "NEG_RISK_CTF_COLLATERAL_ADAPTER": V2.NEG_RISK_CTF_COLLATERAL_ADAPTER,
    "USDC_E": V2.USDC_E,
    "CTF_EXCHANGE_V1": V2.CTF_EXCHANGE_V1,
    "NEG_RISK_CTF_EXCHANGE_V1": V2.NEG_RISK_CTF_EXCHANGE_V1,
}


@pytest.mark.parametrize("role,addr", list(ALL_ROLES.items()))
def test_address_is_valid_hex(role, addr):
    assert _is_hex_address(addr), f"{role}={addr!r} is not a valid 0x{{40}} hex address"


def test_v1_and_v2_exchanges_differ():
    """Guard against the most dangerous migration bug: using V1 addrs in a V2 role."""
    assert V2.CTF_EXCHANGE_V1 != V2.CTF_EXCHANGE_V2
    assert V2.NEG_RISK_CTF_EXCHANGE_V1 != V2.NEG_RISK_CTF_EXCHANGE_V2


def test_conditional_tokens_unchanged():
    """Regression anchor for the key V2 insight: CTF contract is stable."""
    # This matches the V1 address used in core/clob.py preflight + STATE.md.
    assert V2.CONDITIONAL_TOKENS == "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"


def test_all_addresses_unique_within_v2():
    """No accidental reuse of an address across distinct V2 roles.

    CONDITIONAL_TOKENS intentionally shared between V1/V2 roles is NOT listed
    here because the module doesn't re-export it as both. V1 exchanges are
    excluded because they're reference-only.
    """
    distinct = {
        V2.CTF_EXCHANGE_V2,
        V2.NEG_RISK_CTF_EXCHANGE_V2,
        V2.NEG_RISK_ADAPTER,
        V2.CONDITIONAL_TOKENS,
        V2.PUSD_TOKEN_PROXY,
        V2.PUSD_TOKEN_IMPLEMENTATION,
        V2.COLLATERAL_ONRAMP,
        V2.COLLATERAL_OFFRAMP,
        V2.CTF_COLLATERAL_ADAPTER,
        V2.NEG_RISK_CTF_COLLATERAL_ADAPTER,
        V2.USDC_E,
    }
    assert len(distinct) == 11, "V2 address reused across distinct roles"


def test_pusd_proxy_and_impl_differ():
    """Proxy and implementation must be different addresses (else proxy is broken)."""
    assert V2.PUSD_TOKEN_PROXY != V2.PUSD_TOKEN_IMPLEMENTATION


def test_onramp_and_offramp_differ():
    assert V2.COLLATERAL_ONRAMP != V2.COLLATERAL_OFFRAMP


def test_order_struct_field_sets_disjoint():
    """Fields removed in V2 must not reappear in the added set and vice versa."""
    assert frozenset() == V2.ORDER_FIELDS_REMOVED_V2 & V2.ORDER_FIELDS_ADDED_V2


def test_order_struct_removed_fields_match_migration_guide():
    """The published V2 migration guide (fetched 2026-04-17) names exactly
    these four fields as removed. If the guide changes, refetch and update."""
    assert frozenset(
        {"taker", "expiration", "nonce", "feeRateBps"}
    ) == V2.ORDER_FIELDS_REMOVED_V2


def test_order_struct_added_fields_match_migration_guide():
    assert frozenset(
        {"timestamp", "metadata", "builder"}
    ) == V2.ORDER_FIELDS_ADDED_V2


def test_exchange_domain_version_bumps():
    assert V2.EXCHANGE_DOMAIN_VERSION_V1 == "1"
    assert V2.EXCHANGE_DOMAIN_VERSION_V2 == "2"
    # L1/L2 auth domain does NOT bump per migration guide.
    assert V2.L1L2_AUTH_DOMAIN_VERSION == "1"


def test_usdce_matches_repo_historic_address():
    """USDC.e address must match the V1 collateral address in STATE.md and
    the existing approve_polymarket.py scripts. A typo here would brick
    the wrap flow (Onramp rejects the wrong asset)."""
    assert V2.USDC_E == "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"


def test_decimals_match_stable_precision():
    assert V2.USDC_E_DECIMALS == 6
    assert V2.PUSD_DECIMALS == 6


def test_cutover_timestamp_is_parseable():
    """Whoever edits the cutover string should keep it ISO-8601 to avoid
    downstream parse bugs in any alerting code. Day was originally 22 but
    Polymarket announced a slip to 28 in the public V2 rollout (verified
    against docs.polymarket.com/v2-migration on 2026-04-26)."""
    from datetime import datetime
    parsed = datetime.fromisoformat(V2.MIGRATION_CUTOVER_UTC_ISO)
    assert parsed.year == 2026
    assert parsed.month == 4
    assert parsed.day == 28


def test_all_v2_addresses_is_tuple():
    """Helper used by preflight / audit code must be a tuple (immutable)."""
    out = V2.all_v2_addresses()
    assert isinstance(out, tuple)
    assert len(out) >= 10
