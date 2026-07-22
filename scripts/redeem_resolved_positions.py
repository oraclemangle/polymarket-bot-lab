#!/usr/bin/env python3
"""Redeem resolved Polymarket positions that are still shown as active.

Default mode is read-only:

  1. Fetch open positions from Polymarket's data-api.
  2. Keep only standard, resolved, redeemable, zero-current-value rows by default.
  3. Verify the ERC-1155 balance on Polygon.
  4. Simulate `redeemPositions()` and estimate gas.

Execution requires `--execute --yes`. The script deliberately skips negative
risk markets and non-zero-current-value positions so weather/winner rows are
not swept by accident unless a specific condition id is supplied with
`--include-nonzero-current-value`.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from core.config import get_settings
from core.db import Event, Position, get_session_factory
from core.keystore import Keystore
from core.polymarket_v2 import (
    BYTES32_ZERO,
    CONDITIONAL_TOKENS,
    NEG_RISK_ADAPTER,
    POLYGON_CHAIN_ID,
    PUSD_TOKEN_PROXY,
    USDC_E,
    USDC_E_DECIMALS,
)
from core.portfolio import Portfolio

DATA_API = "https://data-api.polymarket.com"
DEFAULT_RPC = "https://polygon-bor.publicnode.com"

ERC1155_CTF_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}, {"name": "id", "type": "uint256"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}, {"name": "operator", "type": "address"}],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSet", "type": "uint256"},
        ],
        "name": "getCollectionId",
        "outputs": [{"name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "collectionId", "type": "bytes32"},
        ],
        "name": "getPositionId",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

NEG_RISK_ADAPTER_ABI = [
    {
        "inputs": [
            {"name": "_conditionId", "type": "bytes32"},
            {"name": "_amounts", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


@dataclass(frozen=True)
class RedeemCandidate:
    title: str
    condition_id: str
    token_id: str
    outcome: str
    outcome_index: int
    size: Decimal
    current_value: Decimal
    collateral: str
    balance_raw: int
    gas_estimate: int
    negative_risk: bool = False
    local_bot_id: str | None = None
    local_position_id: int | None = None
    local_condition_id: str | None = None
    local_size: Decimal | None = None

    @property
    def display_size(self) -> Decimal:
        return Decimal(self.balance_raw) / (Decimal(10) ** USDC_E_DECIMALS)

    def neg_risk_amounts(self) -> list[int]:
        amounts = [0, 0]
        if self.outcome_index not in (0, 1):
            raise ValueError(f"unsupported neg-risk outcome_index={self.outcome_index}")
        amounts[self.outcome_index] = self.balance_raw
        return amounts


def _fmt_addr(addr: str, show_full: bool) -> str:
    if show_full or not addr:
        return addr
    return f"{addr[:6]}...{addr[-4:]}"


def _fmt_usd(raw: int) -> str:
    return f"{Decimal(raw) / Decimal(10) ** USDC_E_DECIMALS:.6f}"


def _gas_fees(w3: Web3) -> tuple[int, int]:
    latest = w3.eth.get_block("latest")
    base = latest.get("baseFeePerGas", 0)
    priority = w3.to_wei(50, "gwei")
    max_fee = max(int(base * 2) + priority, w3.to_wei(150, "gwei"))
    max_fee = min(max_fee, w3.to_wei(500, "gwei"))
    return max_fee, priority


def _send_tx(w3: Web3, acct: Any, tx: dict[str, Any], label: str) -> str:
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[{label}] tx sent: {h.hex()} - waiting for receipt...")
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    if rcpt.status != 1:
        raise RuntimeError(f"{label} reverted: {h.hex()}")
    print(f"[{label}] mined block={rcpt.blockNumber}")
    return h.hex()


def _fetch_open_positions(wallet: str, limit: int) -> list[dict[str, Any]]:
    with httpx.Client(timeout=20.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
        r = client.get(f"{DATA_API}/positions", params={"user": wallet, "limit": limit})
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"unexpected positions payload: {type(data).__name__}")
    return data


def _collateral_for_asset(ctf: Any, position: dict[str, Any]) -> str | None:
    index_set = 1 if int(position["outcomeIndex"]) == 0 else 2
    collection_id = ctf.functions.getCollectionId(
        BYTES32_ZERO,
        position["conditionId"],
        index_set,
    ).call()
    for collateral in (USDC_E, PUSD_TOKEN_PROXY):
        pos_id = ctf.functions.getPositionId(
            Web3.to_checksum_address(collateral),
            collection_id,
        ).call()
        if str(pos_id) == str(position["asset"]):
            return collateral
    return None


def _local_open_positions(bot_id: str | None) -> dict[str, Position]:
    if not bot_id:
        return {}
    sessions = get_session_factory()
    with sessions() as session:
        rows = list(session.scalars(
            select(Position).where(
                Position.bot_id == bot_id,
                Position.status == "OPEN",
            )
        ))
        # Copy SQLAlchemy instances while still attached; caller only reads scalar attrs.
        return {str(row.token_id): row for row in rows}


def _notify_redemption_summary(
    results: list[tuple["RedeemCandidate", str | None, str | None]],
) -> None:
    if not results:
        return
    try:
        from core.notify import send as notify_send
    except Exception:
        return
    ok_rows = [(c, h) for c, h, err in results if h]
    fail_rows = [(c, err) for c, h, err in results if not h]
    total_value = sum((c.current_value for c, _ in ok_rows), Decimal("0"))
    lines = [f"redeem sweep: {len(ok_rows)} ok, {len(fail_rows)} fail, ${total_value:.2f} payout"]
    for c, h in ok_rows[:5]:
        title = c.title[:50]
        lines.append(f"  + ${c.current_value:.2f} {title} {h[:10]}…")
    if len(ok_rows) > 5:
        lines.append(f"  + (+{len(ok_rows) - 5} more)")
    for c, err in fail_rows[:3]:
        lines.append(f"  ! {c.title[:50]}: {(err or '')[:60]}")
    severity = "warn" if fail_rows else "info"
    try:
        notify_send(severity, "\n".join(lines))
    except Exception:
        pass


def _neg_risk_redeem_fn(adapter: Any, position: dict[str, Any], balance_raw: int) -> Any:
    amounts = [0, 0]
    outcome_index = int(position["outcomeIndex"])
    if outcome_index not in (0, 1):
        raise ValueError(f"unsupported neg-risk outcome_index={outcome_index}")
    amounts[outcome_index] = int(balance_raw)
    return adapter.functions.redeemPositions(position["conditionId"], amounts)


def _discover_candidates(
    w3: Web3,
    wallet: str,
    limit: int,
    *,
    condition_id: str | None = None,
    include_nonzero_current_value: bool = False,
    include_negative_risk_zero_value: bool = False,
    include_negative_risk_nonzero_value: bool = False,
    bot_id: str | None = None,
    only_local_open_positions: bool = False,
) -> tuple[list[RedeemCandidate], list[dict[str, Any]]]:
    ctf = w3.eth.contract(address=Web3.to_checksum_address(CONDITIONAL_TOKENS), abi=ERC1155_CTF_ABI)
    adapter = w3.eth.contract(address=Web3.to_checksum_address(NEG_RISK_ADAPTER), abi=NEG_RISK_ADAPTER_ABI)
    positions = _fetch_open_positions(wallet, limit)
    candidates: list[RedeemCandidate] = []
    condition_filter = condition_id.lower() if condition_id else None
    local_positions = _local_open_positions(bot_id)

    for position in positions:
        pos_condition_id = str(position.get("conditionId") or "")
        if condition_filter and pos_condition_id.lower() != condition_filter:
            continue
        if not position.get("redeemable"):
            continue
        current_value = Decimal(str(position.get("currentValue") or "0"))
        if current_value != Decimal("0") and not include_nonzero_current_value:
            continue

        token_id = str(position["asset"])
        local_pos = local_positions.get(token_id)
        if only_local_open_positions and local_pos is None:
            continue

        is_negative_risk = bool(position.get("negativeRisk"))
        if is_negative_risk:
            if current_value == Decimal("0"):
                if not include_negative_risk_zero_value:
                    continue
            else:
                if not include_negative_risk_nonzero_value:
                    continue
            if not ctf.functions.isApprovedForAll(
                Web3.to_checksum_address(wallet),
                Web3.to_checksum_address(NEG_RISK_ADAPTER),
            ).call():
                title = position.get("title") or position.get("market") or "unknown"
                print(f"[skip] negative-risk adapter not approved title={title[:72]}")
                continue
            balance_raw = ctf.functions.balanceOf(
                Web3.to_checksum_address(wallet),
                int(token_id),
            ).call()
            if balance_raw == 0:
                continue
            fn = _neg_risk_redeem_fn(adapter, position, int(balance_raw))
            fn.call({"from": Web3.to_checksum_address(wallet)})
            gas_estimate = fn.estimate_gas({"from": Web3.to_checksum_address(wallet)})
            candidates.append(
                RedeemCandidate(
                    title=str(position.get("title") or position.get("market") or "unknown"),
                    condition_id=str(position["conditionId"]),
                    token_id=token_id,
                    outcome=str(position.get("outcome") or "?"),
                    outcome_index=int(position["outcomeIndex"]),
                    size=Decimal(str(position.get("size") or "0")),
                    current_value=current_value,
                    collateral=NEG_RISK_ADAPTER,
                    balance_raw=int(balance_raw),
                    gas_estimate=int(gas_estimate),
                    negative_risk=True,
                    local_bot_id=bot_id if local_pos is not None else None,
                    local_position_id=int(local_pos.id) if local_pos is not None else None,
                    local_condition_id=str(local_pos.condition_id) if local_pos is not None else None,
                    local_size=Decimal(str(local_pos.size)) if local_pos is not None else None,
                )
            )
            continue

        collateral = _collateral_for_asset(ctf, position)
        if collateral is None:
            title = position.get("title") or position.get("market") or "unknown"
            print(f"[skip] unknown collateral token title={title[:72]}")
            continue

        balance_raw = ctf.functions.balanceOf(
            Web3.to_checksum_address(wallet),
            int(token_id),
        ).call()
        if balance_raw == 0:
            continue

        fn = ctf.functions.redeemPositions(
            Web3.to_checksum_address(collateral),
            BYTES32_ZERO,
            position["conditionId"],
            [1, 2],
        )
        fn.call({"from": Web3.to_checksum_address(wallet)})
        gas_estimate = fn.estimate_gas({"from": Web3.to_checksum_address(wallet)})
        candidates.append(
            RedeemCandidate(
                title=str(position.get("title") or position.get("market") or "unknown"),
                condition_id=str(position["conditionId"]),
                token_id=token_id,
                outcome=str(position.get("outcome") or "?"),
                outcome_index=int(position["outcomeIndex"]),
                size=Decimal(str(position.get("size") or "0")),
                current_value=current_value,
                collateral=collateral,
                balance_raw=int(balance_raw),
                gas_estimate=int(gas_estimate),
                local_bot_id=bot_id if local_pos is not None else None,
                local_position_id=int(local_pos.id) if local_pos is not None else None,
                local_condition_id=str(local_pos.condition_id) if local_pos is not None else None,
                local_size=Decimal(str(local_pos.size)) if local_pos is not None else None,
            )
        )

    return candidates, positions


def _record_local_redeem_fill(candidate: RedeemCandidate, tx_hash: str) -> None:
    if not candidate.local_bot_id or not candidate.local_condition_id:
        return
    size = candidate.local_size or candidate.size
    trade_id = f"negrisk-zero-redeem:{tx_hash}:{candidate.token_id}"
    filled_at = datetime.now(UTC)
    sessions = get_session_factory()
    Portfolio(sessions).on_fill(
        bot_id=candidate.local_bot_id,
        trade_id=trade_id,
        order_id=None,
        condition_id=candidate.local_condition_id,
        token_id=candidate.token_id,
        side="SELL",
        price=Decimal("0"),
        size=size,
        fee_usd=Decimal("0"),
        filled_at=filled_at,
    )
    with sessions() as session:
        session.add(Event(
            bot_id=candidate.local_bot_id,
            event_type="portfolio.negrisk_zero_redeem",
            severity="info",
            message=f"zero-value negative-risk position redeemed: {candidate.title[:120]}",
            payload={
                "tx_hash": tx_hash,
                "position_id": candidate.local_position_id,
                "token_id": candidate.token_id,
                "condition_id": candidate.condition_id,
                "local_condition_id": candidate.local_condition_id,
                "outcome": candidate.outcome,
                "size": str(size),
                "current_value_usd": str(candidate.current_value),
            },
        ))
        session.commit()


def _record_local_redeem(candidate: RedeemCandidate, tx_hash: str) -> None:
    if candidate.local_position_id is None:
        return
    sessions = get_session_factory()
    Portfolio(sessions).on_redeem(candidate.local_position_id, candidate.current_value)
    with sessions() as session:
        session.add(Event(
            bot_id=candidate.local_bot_id,
            event_type="portfolio.redeem_tx",
            severity="info",
            message=f"position {candidate.local_position_id} redeemed on-chain",
            payload={
                "tx_hash": tx_hash,
                "position_id": candidate.local_position_id,
                "token_id": candidate.token_id,
                "condition_id": candidate.condition_id,
                "local_condition_id": candidate.local_condition_id,
                "outcome": candidate.outcome,
                "size": str(candidate.local_size or candidate.size),
                "current_value_usd": str(candidate.current_value),
                "negative_risk": candidate.negative_risk,
            },
        ))
        session.commit()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Redeem resolved Polymarket positions.")
    p.add_argument("--wallet", default=os.environ.get("POLYMARKET_WALLET"))
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--rpc", default=os.environ.get("POLYGON_RPC", DEFAULT_RPC))
    p.add_argument(
        "--condition-id",
        help="Restrict redemption to one exact condition id.",
    )
    p.add_argument(
        "--include-nonzero-current-value",
        action="store_true",
        help=(
            "Allow redeeming winner/non-zero-value rows. Requires --condition-id "
            "so a broad sweep cannot redeem valuable positions by accident."
        ),
    )
    p.add_argument("--execute", action="store_true", help="Submit on-chain transactions.")
    p.add_argument("--yes", action="store_true", help="Skip interactive confirmation.")
    p.add_argument("--show-full-address", action="store_true")
    p.add_argument(
        "--standard-zero-value-only",
        action="store_true",
        help=(
            "Automation guard: refuse any condition-id or non-zero-value scope. "
            "This keeps broad unattended runs limited to the default standard, "
            "non-negative-risk, zero-current-value sweep."
        ),
    )
    p.add_argument(
        "--include-negative-risk-zero-value",
        action="store_true",
        help=(
            "Also redeem negative-risk positions with currentValue=0 via the "
            "NegRiskAdapter. Safe unattended use should combine this with "
            "--bot-id and --only-local-open-positions."
        ),
    )
    p.add_argument(
        "--include-negative-risk-nonzero-value",
        action="store_true",
        help=(
            "Allow redeeming negative-risk winner rows (currentValue>0) via the "
            "NegRiskAdapter. Requires --condition-id so a broad sweep cannot "
            "redeem valuable neg-risk positions by accident."
        ),
    )
    p.add_argument(
        "--bot-id",
        help="Bot ledger id used for local OPEN-position matching/accounting.",
    )
    p.add_argument(
        "--only-local-open-positions",
        action="store_true",
        help=(
            "Only consider wallet rows whose token_id matches an OPEN local "
            "Position for --bot-id."
        ),
    )
    p.add_argument(
        "--account-local-fills",
        action="store_true",
        help=(
            "After a successful negative-risk zero-value redemption, write a "
            "zero-price SELL fill to the local bot ledger."
        ),
    )
    p.add_argument(
        "--account-local-redeems",
        action="store_true",
        help=(
            "After a successful redemption, mark matching --bot-id local OPEN "
            "positions as REDEEMED using the wallet currentValue as payout."
        ),
    )
    p.add_argument(
        "--max-candidates",
        type=int,
        help="Refuse execution if more than this many candidates are discovered.",
    )
    p.add_argument(
        "--max-total-gas",
        type=int,
        help="Refuse execution if total estimated gas exceeds this value.",
    )
    p.add_argument(
        "--max-gas-per-tx",
        type=int,
        help="Refuse execution if any single redemption gas estimate exceeds this value.",
    )
    p.add_argument(
        "--auto-redeem-winners",
        action="store_true",
        help=(
            "Sweep mode: auto-redeem ALL redeemable rows in the wallet "
            "(zero-value losers + winners across both standard CTF and "
            "NegRiskAdapter). Bypasses the per-market --condition-id gate. "
            "Pair with --max-candidates / --max-total-gas / --max-gas-per-tx "
            "for unattended use, and --notify-telegram for visibility."
        ),
    )
    p.add_argument(
        "--notify-telegram",
        action="store_true",
        help=(
            "Post a one-line summary to Telegram on completion (uses "
            "core.notify.send). No-op if notify is unconfigured."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.auto_redeem_winners:
        if args.condition_id:
            print(
                "--auto-redeem-winners cannot be combined with --condition-id.",
                file=sys.stderr,
            )
            return 2
        if args.standard_zero_value_only:
            print(
                "--auto-redeem-winners cannot be combined with --standard-zero-value-only.",
                file=sys.stderr,
            )
            return 2
        args.include_nonzero_current_value = True
        args.include_negative_risk_zero_value = True
        args.include_negative_risk_nonzero_value = True
    if args.include_nonzero_current_value and not args.condition_id and not args.auto_redeem_winners:
        print(
            "--include-nonzero-current-value requires --condition-id.",
            file=sys.stderr,
        )
        return 2
    if args.include_negative_risk_nonzero_value and not args.condition_id and not args.auto_redeem_winners:
        print(
            "--include-negative-risk-nonzero-value requires --condition-id.",
            file=sys.stderr,
        )
        return 2
    if args.standard_zero_value_only and (args.condition_id or args.include_nonzero_current_value):
        print(
            "--standard-zero-value-only cannot be combined with --condition-id "
            "or --include-nonzero-current-value.",
            file=sys.stderr,
        )
        return 2
    if args.standard_zero_value_only and args.include_negative_risk_zero_value:
        print(
            "--standard-zero-value-only cannot be combined with "
            "--include-negative-risk-zero-value.",
            file=sys.stderr,
        )
        return 2
    if args.standard_zero_value_only and args.include_negative_risk_nonzero_value:
        print(
            "--standard-zero-value-only cannot be combined with "
            "--include-negative-risk-nonzero-value.",
            file=sys.stderr,
        )
        return 2
    if args.only_local_open_positions and not args.bot_id:
        print("--only-local-open-positions requires --bot-id.", file=sys.stderr)
        return 2
    if args.account_local_fills and not args.bot_id:
        print("--account-local-fills requires --bot-id.", file=sys.stderr)
        return 2
    if args.account_local_redeems and not args.bot_id:
        print("--account-local-redeems requires --bot-id.", file=sys.stderr)
        return 2

    w3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": 20}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected() or w3.eth.chain_id != POLYGON_CHAIN_ID:
        print("RPC is not connected to Polygon mainnet.", file=sys.stderr)
        return 2

    ks: Keystore | None = None
    acct = None
    wallet = args.wallet
    if args.execute or not wallet:
        try:
            ks = Keystore.load_from_settings(get_settings())
            acct = ks.signer()
        except Exception as e:
            print(f"keystore load failed: {e}", file=sys.stderr)
            return 3
        if wallet and wallet.lower() != acct.address.lower():
            print("wallet does not match signer; refusing to execute.", file=sys.stderr)
            return 4
        wallet = acct.address

    if not wallet:
        print("wallet required for dry run when keystore is unavailable.", file=sys.stderr)
        return 5

    try:
        owner = Web3.to_checksum_address(wallet)
        candidates, positions = _discover_candidates(
            w3,
            owner,
            args.limit,
            condition_id=args.condition_id,
            include_nonzero_current_value=args.include_nonzero_current_value,
            include_negative_risk_zero_value=args.include_negative_risk_zero_value,
            include_negative_risk_nonzero_value=args.include_negative_risk_nonzero_value,
            bot_id=args.bot_id,
            only_local_open_positions=args.only_local_open_positions,
        )

        print(f"[wallet] {_fmt_addr(owner, args.show_full_address)}")
        if args.auto_redeem_winners:
            scope = "auto-sweep: all redeemables (zero-value + winners, standard + neg-risk)"
        else:
            scope = args.condition_id or "zero-current-value standard positions"
            if args.include_negative_risk_zero_value:
                scope = "zero-current-value standard + negative-risk positions"
        if args.only_local_open_positions:
            scope += f" matching local bot_id={args.bot_id}"
        print(f"[scope] {scope}")
        print(f"[positions] open={len(positions)} redeemable_candidates={len(candidates)}")
        if not candidates:
            print("[done] nothing to redeem.")
            return 0

        gas_total = sum(c.gas_estimate for c in candidates)
        print(f"[plan] tx_count={len(candidates)} gas_estimate_total={gas_total}")
        for idx, c in enumerate(candidates, start=1):
            if c.negative_risk:
                collateral_label = "NegRiskAdapter"
            else:
                collateral_label = "USDC.e" if c.collateral.lower() == USDC_E.lower() else "pUSD"
            local_label = (
                f" | local_position={c.local_position_id}"
                if c.local_position_id is not None
                else ""
            )
            print(
                f"{idx:02d}. {c.title[:76]} | {c.outcome} | shares={c.display_size:.6f} "
                f"| current_value=${c.current_value} | collateral={collateral_label} "
                f"| gas~{c.gas_estimate}{local_label}"
            )

        if not args.execute:
            print("\n=== DRY RUN. Re-run with --execute --yes to submit redemption txs. ===")
            return 0

        if args.max_candidates is not None and len(candidates) > args.max_candidates:
            print(
                f"candidate cap exceeded: {len(candidates)} > {args.max_candidates}",
                file=sys.stderr,
            )
            return 7
        if args.max_total_gas is not None and gas_total > args.max_total_gas:
            print(
                f"total gas cap exceeded: {gas_total} > {args.max_total_gas}",
                file=sys.stderr,
            )
            return 7
        if args.max_gas_per_tx is not None:
            high_gas = [c for c in candidates if c.gas_estimate > args.max_gas_per_tx]
            if high_gas:
                print(
                    "per-tx gas cap exceeded: "
                    f"{max(c.gas_estimate for c in high_gas)} > {args.max_gas_per_tx}",
                    file=sys.stderr,
                )
                return 7

        if acct is None:
            print("execute mode requires signer.", file=sys.stderr)
            return 6
        if not args.yes:
            resp = input(
                f"About to redeem {len(candidates)} resolved positions. "
                "Type 'REDEEM' to proceed: "
            ).strip()
            if resp != "REDEEM":
                print("aborted.")
                return 1

        ctf = w3.eth.contract(
            address=Web3.to_checksum_address(CONDITIONAL_TOKENS),
            abi=ERC1155_CTF_ABI,
        )
        adapter = w3.eth.contract(
            address=Web3.to_checksum_address(NEG_RISK_ADAPTER),
            abi=NEG_RISK_ADAPTER_ABI,
        )
        nonce = w3.eth.get_transaction_count(owner, "latest")
        max_fee, priority = _gas_fees(w3)
        results: list[tuple[RedeemCandidate, str | None, str | None]] = []
        for idx, c in enumerate(candidates, start=1):
            if c.negative_risk:
                fn = adapter.functions.redeemPositions(
                    c.condition_id,
                    c.neg_risk_amounts(),
                )
            else:
                fn = ctf.functions.redeemPositions(
                    Web3.to_checksum_address(c.collateral),
                    BYTES32_ZERO,
                    c.condition_id,
                    [1, 2],
                )
            tx = fn.build_transaction(
                {
                    "from": owner,
                    "nonce": nonce,
                    "chainId": POLYGON_CHAIN_ID,
                    "gas": int(c.gas_estimate * 1.35),
                    "maxFeePerGas": max_fee,
                    "maxPriorityFeePerGas": priority,
                }
            )
            try:
                tx_hash = _send_tx(w3, acct, tx, f"redeem-{idx:02d}")
                results.append((c, tx_hash, None))
                if args.account_local_redeems:
                    _record_local_redeem(c, tx_hash)
                if c.negative_risk and args.account_local_fills:
                    _record_local_redeem_fill(c, tx_hash)
            except Exception as e:
                results.append((c, None, str(e)))
                print(f"[redeem-{idx:02d}] FAILED: {e}", file=sys.stderr)
            nonce += 1

        if args.notify_telegram:
            _notify_redemption_summary(results)

        print("[done] redemption sweep submitted.")
        fail = sum(1 for _, h, _ in results if not h)
        return 0 if fail == 0 else 8
    finally:
        if ks is not None:
            ks.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
