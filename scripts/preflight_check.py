#!/usr/bin/env python3
"""CLOB preflight verification.

Runs the three Week-1 blocker checks against the installed py-clob-client
and (optionally) the live CLOB /markets endpoint.  On pass, flips the
in-DB `preflight_ok` flag to unblock mainnet order paths.

Checks:
  OQ-006: HMAC canonical string format verified against py_clob_client source.
  OQ-007: Contract addresses verified against py_clob_client/config.py.
  OQ-008: Collateral pinned by py-clob-client matches cfg.USDC_E_ADDRESS.
          The pre-V2 /supported-assets endpoint was removed by Polymarket
          on ~2026-04-07 (now 404).  The --live probe falls back to
          GET /markets?limit=1 as a CLOB reachability check; if that
          200s and the installed client still pins USDC.e, OQ-008 passes.
          See ADR-017 (V2 migration posture).

Usage:
  python scripts/preflight_check.py             # read-only report
  python scripts/preflight_check.py --commit    # also write the OK flag
  python scripts/preflight_check.py --live      # also probe live CLOB
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from core import config as cfg
from core.db import Event, get_session_factory


def check_hmac() -> tuple[bool, str]:
    """Reproduce py-clob-client's HMAC and confirm it matches a known fixture."""
    from py_clob_client.signing.hmac import build_hmac_signature

    # Deterministic inputs.
    secret = base64.urlsafe_b64encode(b"test-secret-32-bytes-long-padding").decode()
    ts = "1700000000"
    method = "POST"
    path = "/order"
    body = {"k": "v"}  # replace('\'', '"') means dict repr form

    got = build_hmac_signature(secret, ts, method, path, body)

    # Reconstruct locally and compare.
    msg = ts + method + path + str(body).replace("'", '"')
    raw_secret = base64.urlsafe_b64decode(secret)
    h = hmac.new(raw_secret, msg.encode("utf-8"), hashlib.sha256)
    expected = base64.urlsafe_b64encode(h.digest()).decode("utf-8")

    ok = got == expected
    msg = (
        "HMAC canonical string: timestamp + method + path + str(body).replace(\"'\", '\"'); "
        "SHA-256; secret base64-urlsafe decoded; signature base64-urlsafe encoded."
    )
    return ok, msg if ok else f"{msg} — MISMATCH got={got} expected={expected}"


def check_addresses() -> tuple[bool, str]:
    """Cross-check our constants against py_clob_client's contract config.

    Post-cutover (2026-04-28 11:00 UTC) py_clob_client is uninstalled and
    this check fails on import. That's expected — the V2 path
    (``check_addresses_v2``) is the load-bearing check after cutover. We
    return a structured failure marker that ``main`` recognises as
    "post-cutover-acceptable" so a missing V1 SDK doesn't fail
    preflight overall.
    """
    try:
        from py_clob_client.config import get_contract_config
    except ImportError:
        return False, "V1_SDK_UNINSTALLED"

    mainnet = get_contract_config(137)
    ngr_mainnet = get_contract_config(137, neg_risk=True)
    amoy = get_contract_config(80002)

    pairs = [
        (mainnet.exchange, cfg.CTF_EXCHANGE_ADDRESS, "mainnet exchange"),
        (ngr_mainnet.exchange, cfg.NEG_RISK_CTF_EXCHANGE_ADDRESS, "mainnet neg-risk exchange"),
        (mainnet.collateral, cfg.USDC_E_ADDRESS, "mainnet collateral (USDC.e)"),
        (
            mainnet.conditional_tokens,
            cfg.CONDITIONAL_TOKENS_ADDRESS,
            "mainnet conditional tokens",
        ),
        (amoy.exchange, cfg.AMOY_CTF_EXCHANGE_ADDRESS, "amoy exchange"),
        (amoy.collateral, cfg.AMOY_COLLATERAL_ADDRESS, "amoy collateral"),
        (
            amoy.conditional_tokens,
            cfg.AMOY_CONDITIONAL_TOKENS_ADDRESS,
            "amoy conditional tokens",
        ),
    ]
    mismatches = [(got, want, label) for got, want, label in pairs if got.lower() != want.lower()]
    if mismatches:
        return False, "address mismatches: " + "; ".join(
            f"{label}: got {got} want {want}" for got, want, label in mismatches
        )
    return True, f"all {len(pairs)} V1 addresses match py_clob_client config"


# Canonical V2 contract addresses, transcribed from
# https://docs.polymarket.com/v2-migration on 2026-04-26. These are the
# load-bearing constants for the post-cutover preflight; if Polymarket
# changes any of them in a future migration, this check fails loud.
_CANONICAL_V2_ADDRESSES: tuple[tuple[str, str, str], ...] = (
    ("CTF_EXCHANGE_V2", "0xE111180000d2663C0091e4f400237545B87B996B", "V2 mainnet exchange"),
    ("NEG_RISK_CTF_EXCHANGE_V2", "0xe2222d279d744050d28e00520010520000310F59", "V2 neg-risk exchange"),
    ("CONDITIONAL_TOKENS", "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045", "CTF (unchanged)"),
    ("PUSD_TOKEN_PROXY", "0xF00D000000000000000000000000000000000014", "pUSD proxy"),
    ("COLLATERAL_ONRAMP", "0xF00D000000000000000000000000000000000016", "USDC.e → pUSD onramp"),
    ("COLLATERAL_OFFRAMP", "0xF00D000000000000000000000000000000000017", "pUSD → USDC.e offramp"),
    ("USDC_E", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "USDC.e (unchanged)"),
)


def check_addresses_v2() -> tuple[bool, str]:
    """Verify ``core/polymarket_v2`` constants against the canonical V2
    addresses transcribed from the official migration docs.

    This check runs without the V1 or V2 SDK — it's a pure constant
    sanity check. Required to pass post-cutover; running pre-cutover is
    free and catches transcription drift before it matters.
    """
    from core import polymarket_v2 as v2

    mismatches = []
    for attr, want, label in _CANONICAL_V2_ADDRESSES:
        got = getattr(v2, attr, None)
        if got is None:
            mismatches.append((attr, "<missing>", want, label))
            continue
        if got.lower() != want.lower():
            mismatches.append((attr, got, want, label))

    if mismatches:
        return False, "V2 address drift: " + "; ".join(
            f"{label} ({attr}): got {got} want {want}"
            for attr, got, want, label in mismatches
        )
    return True, (
        f"all {len(_CANONICAL_V2_ADDRESSES)} V2 addresses match canonical"
    )


def is_post_cutover() -> bool:
    """True if the current UTC clock is at or past
    ``MIGRATION_CUTOVER_UTC_ISO``. Drives whether V1 checks are required
    or merely informational."""
    from core.polymarket_v2 import MIGRATION_CUTOVER_UTC_ISO

    cutover = datetime.fromisoformat(MIGRATION_CUTOVER_UTC_ISO)
    now = datetime.now(cutover.tzinfo or UTC)
    return now >= cutover


def check_collateral_live(do_fetch: bool) -> tuple[bool, str]:
    """OQ-008: confirm pinned collateral still matches USDC_E_ADDRESS.

    Static check: py-clob-client's pinned `get_contract_config(137).collateral`
    must equal `cfg.USDC_E_ADDRESS`. Any drift here means we need to audit a
    new py-clob-client release before trading.

    Live check (--live): Polymarket removed `/supported-assets` around the V2
    rollout (2026-04-07, now 404). We fall back to `GET /markets?limit=1` as
    a CLOB reachability probe: if it returns a parseable market with the
    expected schema, the exchange is up and our client can talk to it. The
    authoritative collateral assertion still comes from the pinned client —
    we have no endpoint that exposes it directly today. See ADR-017.
    """
    from py_clob_client.config import get_contract_config

    pinned = get_contract_config(137).collateral.lower()
    if pinned != cfg.USDC_E_ADDRESS.lower():
        return False, f"collateral drift: py-clob-client says {pinned}"
    if not do_fetch:
        return True, f"collateral=USDC.e ({pinned}) per py-clob-client config (pinned version)"

    import httpx

    host = cfg.get_settings().polymarket_host
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{host}/markets", params={"limit": 1})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return False, f"live CLOB probe failed ({host}/markets): {e}"

    # py-clob-client returns either a list or {"data":[...]}; accept both.
    first = None
    if isinstance(data, list) and data:
        first = data[0]
    elif isinstance(data, dict):
        inner = data.get("data") or data.get("markets") or []
        if inner:
            first = inner[0]
    if not isinstance(first, dict) or "condition_id" not in first:
        return False, f"live /markets schema unexpected: {str(data)[:200]}"
    return True, (
        f"collateral=USDC.e ({pinned}) pinned by py-clob-client; "
        f"live {host}/markets reachable (sample condition_id={first['condition_id'][:10]}…)"
    )


def write_flag(ok: bool, summary: str) -> None:
    Session = get_session_factory()
    with Session() as s:
        s.add(
            Event(
                bot_id=None,
                event_type="preflight.verified" if ok else "preflight.failed",
                severity="info" if ok else "kill",
                message=summary,
                payload={"checked_at": datetime.now(UTC).isoformat()},
            )
        )
        s.commit()


def latest_preflight_ok() -> bool:
    Session = get_session_factory()
    with Session() as s:
        latest = s.scalars(
            select(Event)
            .where(Event.event_type.in_(("preflight.verified", "preflight.failed")))
            .order_by(Event.created_at.desc())
        ).first()
        return bool(latest and latest.event_type == "preflight.verified")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="write preflight.verified event")
    parser.add_argument("--live", action="store_true", help="additionally hit /supported-assets")
    args = parser.parse_args(argv)

    post_cutover = is_post_cutover()

    # V2 address check is required regardless of cutover status — pre-
    # cutover it catches transcription drift; post-cutover it's the
    # load-bearing live-graduation gate.
    v1_addr_ok, v1_addr_msg = check_addresses()
    v2_addr_ok, v2_addr_msg = check_addresses_v2()
    hmac_ok, hmac_msg = check_hmac() if not post_cutover else (
        True,
        "skipped (post-cutover; V1 HMAC flow is dead — V2 uses signed builderCode field)",
    )
    collateral_ok, collateral_msg = check_collateral_live(args.live) if not post_cutover else (
        True,
        "skipped (post-cutover; V1 SDK pin no longer authoritative — see V2 addresses)",
    )

    # V1 address failure is acceptable post-cutover (SDK uninstalled).
    if post_cutover and v1_addr_msg == "V1_SDK_UNINSTALLED":
        v1_addr_ok = True
        v1_addr_msg = "V1 SDK uninstalled (expected post-cutover)"

    checks = [
        ("OQ-006 HMAC", (hmac_ok, hmac_msg)),
        ("OQ-007 V1 addresses", (v1_addr_ok, v1_addr_msg)),
        ("V2 addresses (cutover gate)", (v2_addr_ok, v2_addr_msg)),
        ("OQ-008 collateral", (collateral_ok, collateral_msg)),
    ]

    print(f"  cutover phase: {'POST' if post_cutover else 'PRE'} 2026-04-28T11:00Z")
    all_ok = True
    for label, (ok, msg) in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}: {msg}")
        if not ok:
            all_ok = False

    if args.commit:
        write_flag(all_ok, "; ".join(f"{label}:{'ok' if ok else 'fail'}" for label, (ok, _) in checks))
        print(f"\nwrote preflight event (ok={all_ok})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
