"""Polymarket V2 OrderFilled event collector.

Polls the Polygon RPC for `OrderFilled` events on the two V2 exchange
contracts (CTF V2 + NegRiskCTF V2). Decodes each log; if the maker or
taker is in our whitelist, writes a row to `wallet_observed_fills`.

Pure observation: never sends transactions, never holds keys.

V2 event layout (Apr 28 2026 deploy):

    event OrderFilled(
        bytes32 indexed orderHash,        // topics[1]
        address indexed maker,            // topics[2]
        address indexed taker,            // topics[3]
        uint8 side,                       // data[0..32]   0=BUY, 1=SELL (maker POV)
        uint256 tokenId,                  // data[32..64]
        uint256 makerAmountFilled,        // data[64..96]
        uint256 takerAmountFilled,        // data[96..128]
        uint256 fee,                      // data[128..160]
        bytes32 builder,                  // data[160..192]
        bytes32 metadata                  // data[192..224]
    )

The `side` field indicates the MAKER's intent: 0 = maker placed a BUY
order; 1 = maker placed a SELL order. The taker is opposite.

For a maker BUY order that fills (side=0): maker spent USDC, got shares.
For a maker SELL order (side=1): maker spent shares, got USDC.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from web3 import Web3
from web3.exceptions import Web3RPCError

from bots.wallet_observer import config as cfg
from bots.wallet_observer.schema import init_db
from bots.wallet_observer.whitelist import Whitelist, WhitelistedWallet

log = logging.getLogger(__name__)

# USDC on Polygon has 6 decimals. CTF asset balances are 1:1 with shares
# (no decimals — uint amount is shares).
USDC_DECIMALS = 6
USDC_SCALE = Decimal(10) ** USDC_DECIMALS

EXCHANGE_TO_ADDRESS = {
    "CTF": cfg.CTF_EXCHANGE_ADDRESS.lower(),
    "NegRiskCTF": cfg.NEG_RISK_CTF_EXCHANGE_ADDRESS.lower(),
}
ADDRESS_TO_EXCHANGE = {v: k for k, v in EXCHANGE_TO_ADDRESS.items()}


@dataclass
class DecodedFill:
    """A decoded V2 OrderFilled event. All addresses lowercase 0x.

    V2 ABI (verified from Blockscout 2026-05-07):
      orderHash, maker, taker (indexed),
      side (uint8), tokenId (uint256),
      makerAmountFilled (uint256), takerAmountFilled (uint256),
      fee (uint256), builder (bytes32), metadata (bytes32)

    side=0: maker is BUYER (provided USDC, received shares)
    side=1: maker is SELLER (provided shares, received USDC)

    All amounts are in 6-decimal format (matching USDC).
    For a BUY (side=0): maker amount is USDC, taker amount is shares
    For a SELL (side=1): maker amount is shares, taker amount is USDC
    """
    tx_hash: str
    log_index: int
    block_number: int
    block_ts: int | None
    exchange: str
    order_hash: str
    maker_address: str
    taker_address: str
    side_raw: int  # 0=BUY, 1=SELL (maker's perspective)
    token_id: str  # decimal string (uint256)
    maker_amount_filled: str
    taker_amount_filled: str
    fee_raw: str  # uint256 fee
    builder_code: str  # bytes32 hex
    metadata: str  # bytes32 hex

    def derive_observed_side(
        self, observed_address: str
    ) -> tuple[str, str | None, float | None, float | None]:
        """Return (role, side_label, price, size_shares) from the
        observed wallet's perspective.

        V2 layout: side is explicit; both amounts are 6-decimal.

        For side=0 (maker BUY):
          maker_amount = USDC raw     taker_amount = shares raw
          maker side_label = BUY      taker side_label = SELL

        For side=1 (maker SELL):
          maker_amount = shares raw   taker_amount = USDC raw
          maker side_label = SELL     taker side_label = BUY

        Price = USDC dollars / shares. Both legs are 6-decimal so the
        scale cancels in the ratio.
        """
        observed = observed_address.lower()

        try:
            maker_amt = Decimal(self.maker_amount_filled)
            taker_amt = Decimal(self.taker_amount_filled)
        except Exception:
            return ("unknown", None, None, None)

        if maker_amt == 0 or taker_amt == 0:
            return ("unknown", None, None, None)

        if self.side_raw == 0:
            # Maker BUY: maker_amt = USDC, taker_amt = shares
            usdc_raw = maker_amt
            shares_raw = taker_amt
            maker_side, taker_side = "BUY", "SELL"
        elif self.side_raw == 1:
            # Maker SELL: maker_amt = shares, taker_amt = USDC
            shares_raw = maker_amt
            usdc_raw = taker_amt
            maker_side, taker_side = "SELL", "BUY"
        else:
            return ("unknown", None, None, None)

        # Both legs are 6-decimal in V2; the scale cancels in price ratio.
        price = float(usdc_raw / shares_raw)
        if price <= 0 or price > 1.5:
            price = None

        # Show shares in 6-decimal-adjusted units (the human-readable amount)
        shares_decimal = float(shares_raw / Decimal(USDC_SCALE))

        if observed == self.maker_address.lower():
            return ("maker", maker_side, price, shares_decimal)
        if observed == self.taker_address.lower():
            return ("taker", taker_side, price, shares_decimal)
        return ("unknown", None, None, None)


def _decode_address(topic_hex: str) -> str:
    """Indexed address topic → lowercase 0x... string. Topics are 32-byte
    left-padded for addresses (right-aligned in the 32 bytes)."""
    # topic_hex is like "0x000...000aabbcc..." (66 chars total including 0x)
    h = topic_hex[2:] if topic_hex.startswith("0x") else topic_hex
    return "0x" + h[-40:].lower()


def _decode_uint256(slot: bytes) -> int:
    return int.from_bytes(slot, "big", signed=False)


def decode_log(log_entry: dict) -> DecodedFill | None:
    """Decode a single eth_getLogs entry into a DecodedFill, or None if
    the log doesn't match OrderFilled signature.
    """
    topics = log_entry.get("topics") or []
    if not topics:
        return None
    topic0 = topics[0]
    if hasattr(topic0, "hex"):
        topic0 = topic0.hex()
    if not topic0.startswith("0x"):
        topic0 = "0x" + topic0
    if topic0.lower() != cfg.ORDER_FILLED_TOPIC0.lower():
        return None
    if len(topics) < 4:
        return None

    contract_addr = (log_entry.get("address") or "").lower()
    exchange = ADDRESS_TO_EXCHANGE.get(contract_addr)
    if exchange is None:
        return None

    order_hash = topics[1]
    if hasattr(order_hash, "hex"):
        order_hash = order_hash.hex()
    if not order_hash.startswith("0x"):
        order_hash = "0x" + order_hash

    maker_topic = topics[2]
    if hasattr(maker_topic, "hex"):
        maker_topic = maker_topic.hex()
    taker_topic = topics[3]
    if hasattr(taker_topic, "hex"):
        taker_topic = taker_topic.hex()

    maker = _decode_address(maker_topic if maker_topic.startswith("0x") else "0x" + maker_topic)
    taker = _decode_address(taker_topic if taker_topic.startswith("0x") else "0x" + taker_topic)

    data = log_entry.get("data")
    if hasattr(data, "hex"):
        data = "0x" + data.hex()
    if not isinstance(data, str):
        return None
    raw = bytes.fromhex(data[2:] if data.startswith("0x") else data)
    # V2 layout: 7 unindexed fields × 32 bytes = 224 bytes
    if len(raw) < 7 * 32:
        return None
    side_raw = _decode_uint256(raw[0:32])
    token_id = _decode_uint256(raw[32:64])
    maker_amount = _decode_uint256(raw[64:96])
    taker_amount = _decode_uint256(raw[96:128])
    fee = _decode_uint256(raw[128:160])
    builder_code = "0x" + raw[160:192].hex()
    metadata = "0x" + raw[192:224].hex()

    tx_hash = log_entry.get("transactionHash") or ""
    if hasattr(tx_hash, "hex"):
        tx_hash = tx_hash.hex()
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash

    return DecodedFill(
        tx_hash=tx_hash,
        log_index=int(log_entry.get("logIndex") or 0),
        block_number=int(log_entry.get("blockNumber") or 0),
        block_ts=0,
        exchange=exchange,
        order_hash=order_hash,
        maker_address=maker,
        taker_address=taker,
        side_raw=side_raw,
        token_id=str(token_id),
        maker_amount_filled=str(maker_amount),
        taker_amount_filled=str(taker_amount),
        fee_raw=str(fee),
        builder_code=builder_code,
        metadata=metadata,
    )


def write_fill(
    con: sqlite3.Connection,
    fill: DecodedFill,
    *,
    observed: WhitelistedWallet,
    role: str,
    side: str | None,
    price: float | None,
    size_shares: float | None,
) -> None:
    con.execute(
        """
        INSERT OR IGNORE INTO wallet_observed_fills (
            tx_hash, log_index, block_number, block_ts, exchange,
            order_hash, maker_address, taker_address,
            side_raw, token_id,
            maker_amount_filled, taker_amount_filled, fee_raw,
            builder_code, metadata,
            observed_address, observed_role, tier, user_name, pv_rank,
            side, price, size_shares, inserted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fill.tx_hash, fill.log_index, fill.block_number, fill.block_ts, fill.exchange,
            fill.order_hash, fill.maker_address, fill.taker_address,
            fill.side_raw, fill.token_id,
            fill.maker_amount_filled, fill.taker_amount_filled, fill.fee_raw,
            fill.builder_code, fill.metadata,
            observed.address, role, observed.tier, observed.user_name, observed.pv_rank,
            side, price, size_shares, int(time.time()),
        ),
    )


class Collector:
    """Polygon RPC poller. Stateful — tracks last block per exchange in DB."""

    def __init__(
        self,
        *,
        whitelist: Whitelist,
        rpc_url: str = cfg.POLYGON_RPC_URL,
        db_path: Path | str = cfg.WALLET_OBSERVER_DB,
    ) -> None:
        self.whitelist = whitelist
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
        # Polygon is PoA — extraData field is longer than 32 bytes.
        # Inject the PoA middleware so eth_getBlock works.
        try:
            from web3.middleware import ExtraDataToPOAMiddleware  # web3.py 7.x
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        except ImportError:
            try:
                from web3.middleware import geth_poa_middleware  # legacy
                self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            except Exception as e:
                log.warning("wallet_observer.poa_middleware_unavailable err=%s", e)
        self.con = init_db(db_path)
        self.exchange_addresses = list(EXCHANGE_TO_ADDRESS.values())

    def is_connected(self) -> bool:
        try:
            return bool(self.w3.is_connected())
        except Exception:
            return False

    def latest_block(self) -> int:
        return int(self.w3.eth.block_number)

    def get_state(self, exchange: str) -> int | None:
        cur = self.con.execute(
            "SELECT last_block FROM collector_state WHERE chain='polygon' AND exchange=?",
            (exchange,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else None

    def set_state(self, exchange: str, last_block: int) -> None:
        self.con.execute(
            """
            INSERT INTO collector_state (chain, exchange, last_block, last_updated)
            VALUES ('polygon', ?, ?, ?)
            ON CONFLICT (chain, exchange) DO UPDATE
              SET last_block = excluded.last_block,
                  last_updated = excluded.last_updated
            """,
            (exchange, last_block, int(time.time())),
        )

    def fetch_logs_for_exchange(
        self, exchange: str, *, from_block: int, to_block: int
    ) -> list[dict] | None:
        addr = EXCHANGE_TO_ADDRESS[exchange]
        try:
            logs = self.w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": Web3.to_checksum_address(addr),
                "topics": [cfg.ORDER_FILLED_TOPIC0],
            })
            return list(logs)
        except Web3RPCError as e:
            log.warning(
                "wallet_observer.collector.rpc_error exchange=%s from=%d to=%d err=%s",
                exchange, from_block, to_block, e,
            )
            return None

    def fetch_block_timestamp(self, block_number: int, *, attempts: int = 3) -> int | None:
        for attempt in range(1, attempts + 1):
            try:
                blk = self.w3.eth.get_block(block_number)
                return int(blk["timestamp"])
            except Exception as e:
                if attempt == attempts:
                    log.warning(
                        "wallet_observer.block_ts_error block=%d attempts=%d err=%s",
                        block_number, attempts, e,
                    )
                    return None
                time.sleep(0.25 * attempt)
        return None

    def process_logs(
        self, exchange: str, logs: Iterable[dict], *, run_id: int | None = None,
    ) -> int:
        """Decode each log; persist if maker or taker is in whitelist.
        Returns number of fills written."""
        whitelist_addrs = self.whitelist.addresses()
        block_ts_cache: dict[int, int | None] = {}
        n_written = 0
        for raw in logs:
            fill = decode_log(dict(raw))
            if fill is None:
                continue
            # Match either side
            for candidate in (fill.maker_address, fill.taker_address):
                if candidate.lower() in whitelist_addrs:
                    observed = self.whitelist.lookup(candidate)
                    if observed is None:
                        continue
                    if fill.block_ts == 0:
                        if fill.block_number not in block_ts_cache:
                            block_ts_cache[fill.block_number] = self.fetch_block_timestamp(fill.block_number)
                        fill.block_ts = block_ts_cache[fill.block_number]
                    if fill.block_ts is None:
                        log.warning(
                            "wallet_observer.skip_no_block_ts exchange=%s block=%d tx=%s",
                            exchange, fill.block_number, fill.tx_hash[:14],
                        )
                        break
                    role, side, price, size_shares = fill.derive_observed_side(candidate)
                    if cfg.ENTRY_HALT:
                        log.info(
                            "wallet_observer.halt_skip exchange=%s observed=%s role=%s",
                            exchange, candidate[:14], role,
                        )
                        continue
                    write_fill(
                        self.con, fill,
                        observed=observed, role=role, side=side,
                        price=price, size_shares=size_shares,
                    )
                    n_written += 1
                    log.info(
                        "wallet_observer.fill exchange=%s blk=%d tx=%s observed=%s tier=%s role=%s side=%s price=%s",
                        exchange, fill.block_number, fill.tx_hash[:14],
                        candidate[:14], observed.tier, role, side, price,
                    )
                    break  # don't double-count if both sides are in whitelist
        return n_written

    def poll_once(
        self,
        *,
        max_range: int = cfg.MAX_BLOCK_RANGE_PER_POLL,
        initial_lookback: int = cfg.INITIAL_LOOKBACK_BLOCKS,
        finality_lag: int = cfg.FINALITY_LAG_BLOCKS,
        run_id: int | None = None,
    ) -> tuple[int, dict[str, int]]:
        """One polling cycle across both exchanges. Returns
        (fills_written_this_poll, {exchange: last_processed_block})."""
        latest = max(0, self.latest_block() - max(0, finality_lag))
        total_written = 0
        new_state: dict[str, int] = {}
        for exchange in EXCHANGE_TO_ADDRESS:
            last = self.get_state(exchange)
            if last is None:
                from_block = max(0, latest - initial_lookback)
            else:
                from_block = last + 1
            to_block = min(latest, from_block + max_range - 1)
            if to_block < from_block:
                new_state[exchange] = last or latest
                continue
            logs = self.fetch_logs_for_exchange(
                exchange, from_block=from_block, to_block=to_block,
            )
            if logs is None:
                if last is not None:
                    new_state[exchange] = last
                log.warning(
                    "wallet_observer.poll_skipped exchange=%s from=%d to=%d reason=rpc_error",
                    exchange, from_block, to_block,
                )
                continue
            log.info(
                "wallet_observer.poll exchange=%s from=%d to=%d n_logs=%d",
                exchange, from_block, to_block, len(logs),
            )
            written = self.process_logs(exchange, logs, run_id=run_id)
            total_written += written
            self.set_state(exchange, to_block)
            new_state[exchange] = to_block
        return total_written, new_state
