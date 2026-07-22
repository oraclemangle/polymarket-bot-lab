"""CLOB client wrapper.

Thin facade around py-clob-client exposing only the surface the bots use.
Adds tenacity-based retry, a local token-bucket rate limiter at 80% of
published CLOB limits (per research/clob-spec.md §3.4), and structured
error types.

Never logs the private key or API secret. Structured logs redact.

Blocked from live use until:
- OQ-006 (HMAC canonical string verified against py_clob_client source)
- OQ-007 (verifyingContract addresses cross-checked against py_order_utils)
- OQ-008 (USDC.e vs native USDC resolved empirically)

Until then, all public methods route through `_guard_live()` which raises
`ClobNotReadyError` when the env is 'live' but the above checks have not
been marked done.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import (
    RATE_LIMIT_GENERAL_PER_10S,
    RATE_LIMIT_POST_ORDER_PER_10S,
    get_settings,
)

if TYPE_CHECKING:
    from core.keystore import Keystore

log = logging.getLogger(__name__)


# --- Error types ---
class ClobError(RuntimeError):
    """Base for all CLOB wrapper errors."""


class ClobNotReadyError(ClobError):
    """Raised when a live order path is invoked before preflight checks pass."""


class ClobAuthError(ClobError):
    """Signing, API-creds, or HMAC failure."""


class ClobRateLimitError(ClobError):
    """Local or remote rate limit exceeded."""


# --- Order primitives (deliberately stable API; not leaking py-clob-client types) ---
class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    GTC = "GTC"
    GTD = "GTD"
    FOK = "FOK"
    FAK = "FAK"


@dataclass(frozen=True)
class OrderBook:
    token_id: str
    bids: list[tuple[Decimal, Decimal]]  # sorted desc by price
    asks: list[tuple[Decimal, Decimal]]  # sorted asc by price
    timestamp: float

    def best_bid(self) -> Decimal | None:
        return self.bids[0][0] if self.bids else None

    def best_ask(self) -> Decimal | None:
        return self.asks[0][0] if self.asks else None

    def midpoint(self) -> Decimal | None:
        bb, ba = self.best_bid(), self.best_ask()
        if bb is None or ba is None:
            return None
        return (bb + ba) / 2


@dataclass(frozen=True)
class OrderResponse:
    order_id: str
    status: str
    raw: dict


@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    token_id: str
    side: Side
    price: Decimal
    size: Decimal
    status: str


@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    order_id: str | None
    token_id: str
    side: Side
    price: Decimal
    size: Decimal
    fee_usd: Decimal
    filled_at: float
    market_id: str | None = None  # CLOB "market" field = condition_id


# --- Rate limiter ---
class TokenBucket:
    """Simple token-bucket limiter (thread-safe).

    Used at 80% of published CLOB limits — we do NOT want to probe the remote
    limit in production.
    """

    def __init__(self, capacity: int, refill_period_seconds: float):
        self.capacity = capacity
        self.tokens: float = float(capacity)
        self.refill_rate = capacity / refill_period_seconds  # tokens/sec
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, n: int = 1, blocking: bool = True, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                if elapsed > 0:
                    self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                    self.last_refill = now
                if self.tokens >= n:
                    self.tokens -= n
                    return True
                needed = n - self.tokens
                wait_seconds = needed / self.refill_rate
            if not blocking:
                return False
            if time.monotonic() + wait_seconds > deadline:
                return False
            time.sleep(min(wait_seconds, 0.25))


# --- Wrapper ---
@dataclass
class _PreflightStatus:
    hmac_verified: bool = False
    contract_addrs_verified: bool = False
    collateral_verified: bool = False

    def all_ok(self) -> bool:
        return all((self.hmac_verified, self.contract_addrs_verified, self.collateral_verified))


class ClobWrapper:
    """Public interface the bots consume.

    Live path requires preflight to be marked complete via `mark_preflight_done`
    (typically once, at daemon startup, after the Week-1 verification scripts
    have run and written a sentinel file).  In paper mode all order methods
    route to `_paper_fill`.
    """

    def __init__(
        self,
        keystore: "Keystore | None",
        chain_id: int | None = None,
        host: str | None = None,
        paper_override: bool = False,
    ):
        self.keystore = keystore
        self.chain_id = chain_id or get_settings().chain_id
        self.host = host or get_settings().polymarket_host
        self.preflight = _PreflightStatus()
        # When True, force paper-mode routing regardless of global Settings.
        # This lets a single bot (e.g. Bot C) run in paper while the rest of
        # the stack runs live.  Never blocks live callers: if paper_override
        # is False and is_live() is True, behaviour is unchanged.
        #
        # 2026-04-22 GLM-5.1 review A4: expose as read-only property so no
        # imported wrapper can flip `paper_override = False` at runtime and
        # turn a paper bot live. Construct a new ClobWrapper instead.
        self._paper_override = bool(paper_override)

        # Live client is constructed lazily on first live call so tests
        # (and paper mode) never need the py-clob-client import.
        self._client: Any = None

        # 80% of published limits (per spec §3.4).
        self._general_bucket = TokenBucket(int(RATE_LIMIT_GENERAL_PER_10S * 0.80), 10.0)
        self._order_bucket = TokenBucket(int(RATE_LIMIT_POST_ORDER_PER_10S * 0.80), 10.0)

        # Injected by tests; real paper mode records orders to DB.
        self._paper_callback: Callable[[dict], dict] | None = None

    @property
    def paper_override(self) -> bool:
        return self._paper_override

    @paper_override.setter
    def paper_override(self, value: bool) -> None:
        raise PermissionError(
            "ClobWrapper.paper_override is read-only after construction. "
            "Create a new ClobWrapper(paper_override=...) instead of "
            "flipping the attribute on an existing instance. "
            "Added 2026-04-22 per GLM-5.1 fleet review A4 as real-money "
            "safety against any code path that could silently turn a "
            "paper bot live.",
        )

    def _effective_paper(self) -> bool:
        """True when this wrapper should short-circuit to paper-fill."""
        return self.paper_override or not get_settings().is_live()

    # --- Preflight gate ---
    def mark_preflight_done(self, hmac: bool, addrs: bool, collateral: bool) -> None:
        self.preflight.hmac_verified = hmac
        self.preflight.contract_addrs_verified = addrs
        self.preflight.collateral_verified = collateral
        log.info(
            "clob.preflight.updated",
            extra={"hmac": hmac, "addrs": addrs, "collateral": collateral},
        )

    def load_preflight_from_db(self) -> bool:
        """Read the latest `preflight.verified` event from the DB and flip
        preflight ON if found.  Bots call this once on startup so that running
        `scripts/preflight_check.py --commit` is all the operator needs to do
        to unblock the live path.
        """
        from sqlalchemy import select

        from core.db import Event, get_session_factory

        with get_session_factory()() as s:
            latest = s.scalars(
                select(Event)
                .where(Event.event_type.in_(("preflight.verified", "preflight.failed")))
                .order_by(Event.created_at.desc())
            ).first()
        if latest and latest.event_type == "preflight.verified":
            self.mark_preflight_done(True, True, True)
            return True
        return False

    def _guard_live(self) -> None:
        if not self._effective_paper() and not self.preflight.all_ok():
            raise ClobNotReadyError(
                "CLOB live path blocked: preflight incomplete "
                f"(hmac={self.preflight.hmac_verified}, "
                f"addrs={self.preflight.contract_addrs_verified}, "
                f"collateral={self.preflight.collateral_verified}). "
                "See docs/open-questions.md OQ-006/007/008."
            )

    # --- Lazy client construction ---
    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if self.keystore is None:
            raise ClobAuthError("live client requires a Keystore")
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds  # noqa: F401
        except ImportError as e:
            raise ClobError("py-clob-client not installed") from e

        signer = self.keystore.signer()
        client = ClobClient(host=self.host, key=signer.key.hex(), chain_id=self.chain_id)
        # L1 derivation (creates or fetches API creds from the key).
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        self._client = client
        return client

    # --- Market data (public; no auth needed) ---
    @retry(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPError)),
        reraise=True,
    )
    def get_book(self, token_id: str) -> OrderBook:
        self._general_bucket.acquire()
        url = f"{self.host}/book"
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url, params={"token_id": token_id})
            r.raise_for_status()
            data = r.json()
        bids = [(Decimal(str(b["price"])), Decimal(str(b["size"]))) for b in data.get("bids", [])]
        asks = [(Decimal(str(a["price"])), Decimal(str(a["size"]))) for a in data.get("asks", [])]
        # CLOB returns bids asc, asks desc in some responses; normalise.
        bids.sort(key=lambda p: p[0], reverse=True)
        asks.sort(key=lambda p: p[0])
        return OrderBook(token_id=token_id, bids=bids, asks=asks, timestamp=time.time())

    def get_midpoint(self, token_id: str) -> Decimal | None:
        return self.get_book(token_id).midpoint()

    @retry(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.HTTPError,)),
        reraise=True,
    )
    def get_tick_size(self, token_id: str) -> Decimal:
        """Returns minimum price increment for a market."""
        self._general_bucket.acquire()
        url = f"{self.host}/tick-size"
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url, params={"token_id": token_id})
            r.raise_for_status()
            return Decimal(str(r.json().get("minimum_tick_size", "0.01")))

    # --- Orders (authenticated) ---
    def place_limit(
        self,
        token_id: str,
        price: Decimal,
        size: Decimal,
        side: Side,
        order_type: OrderType = OrderType.GTC,
    ) -> OrderResponse:
        self._guard_live()
        self._order_bucket.acquire()

        order_dict = {
            "token_id": token_id,
            "price": str(price),
            "size": str(size),
            "side": side.value,
            "order_type": order_type.value,
        }

        if self._effective_paper():
            return self._paper_fill(order_dict)

        # Polymarket CLOB rejects orders with size < 5 (HTTP 400). Skip
        # gracefully rather than let the exception propagate and crash the daemon.
        if Decimal(order_dict["size"]) < Decimal("5"):
            log.info("clob.skip.below_min_size", extra=order_dict)
            return OrderResponse(order_id="", status="SKIPPED_MIN_SIZE", raw=order_dict)

        return self._place_limit_live(order_dict)

    # Idempotency: we ONLY retry on ConnectTimeout. A ReadTimeout means the
    # request reached the server; the order may have been placed. Retrying
    # that would duplicate a real-money order. Callers that hit a
    # ReadTimeout must reconcile via get_user_orders before re-submitting.
    @retry(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((httpx.ConnectTimeout,)),
        reraise=True,
    )
    def _place_limit_live(self, order_dict: dict) -> OrderResponse:
        """Live order path.  Only reached when is_live() + preflight done."""
        from py_clob_client.clob_types import OrderArgs

        client = self._get_client()
        args = OrderArgs(
            token_id=order_dict["token_id"],
            price=float(order_dict["price"]),
            size=float(order_dict["size"]),
            side=order_dict["side"],
        )
        signed = client.create_order(args)
        resp = client.post_order(signed, orderType=order_dict["order_type"])
        return OrderResponse(
            order_id=str(resp.get("orderID") or resp.get("order_id") or ""),
            status=str(resp.get("status", "UNKNOWN")),
            raw=resp,
        )

    def _paper_fill(self, order_dict: dict) -> OrderResponse:
        """Paper-mode: generate a synthetic order id and record, don't touch the network.

        A higher layer (portfolio + test harness) translates these into
        simulated fills based on the next book snapshot.
        """
        import uuid

        oid = f"paper-{uuid.uuid4().hex[:12]}"
        log.info("clob.paper.place", extra={"order_id": oid, **order_dict})
        if self._paper_callback is not None:
            self._paper_callback({**order_dict, "order_id": oid})
        return OrderResponse(order_id=oid, status="PAPER_OPEN", raw=order_dict)

    @retry(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.HTTPError,)),
        reraise=True,
    )
    def cancel_order(self, order_id: str) -> bool:
        self._guard_live()
        self._order_bucket.acquire()
        if self._effective_paper() or order_id.startswith("paper-"):
            log.info("clob.paper.cancel", extra={"order_id": order_id})
            return True
        client = self._get_client()
        resp = client.cancel(order_id=order_id)
        return bool(resp.get("canceled", False))

    def cancel_all(self, market_id: str | None = None) -> int:
        self._guard_live()
        if self._effective_paper():
            log.info("clob.paper.cancel_all", extra={"market_id": market_id})
            return 0
        client = self._get_client()
        resp = client.cancel_all() if market_id is None else client.cancel_market_orders(market_id)
        # 2026-04-17: Polymarket cancel-all returns {"canceled": [order_id, ...]}
        # not a count. Handle both shapes defensively so future API changes
        # don't crash the watchdog.
        canceled = resp.get("canceled", 0) if isinstance(resp, dict) else 0
        if isinstance(canceled, list):
            return len(canceled)
        try:
            return int(canceled)
        except (TypeError, ValueError):
            return 0

    def get_user_orders(self, market_id: str | None = None) -> list[OrderRecord]:
        if self._effective_paper():
            return []
        client = self._get_client()
        raw = client.get_orders() if market_id is None else client.get_orders(market=market_id)
        return [
            OrderRecord(
                order_id=str(o["id"]),
                token_id=str(o["asset_id"]),
                side=Side(o["side"]),
                price=Decimal(str(o["price"])),
                size=Decimal(str(o["size"])),
                status=str(o["status"]),
            )
            for o in raw
        ]

    def get_user_trades(self, since: float | None = None) -> list[TradeRecord]:
        if self._effective_paper():
            return []
        client = self._get_client()
        raw = client.get_trades()
        out: list[TradeRecord] = []
        # Resolve token_id → category once per call via a brief DB session.
        # Category drives the canonical parabolic fee formula from
        # core/fees.py. See ADR-038 (2026-04-22) + GLM-5.1 review A3 for
        # why the old `fee_rate_bps × price × size / 10000` flat formula
        # was wrong (missing the (1-p) factor and ambiguous units).
        from sqlalchemy import select
        from core.fees import fee_for_fill
        from core.db import Market, get_session_factory
        sf = get_session_factory()
        cat_cache: dict[str, str] = {}
        with sf() as s:
            for t in raw:
                ts = float(t.get("match_time", 0))
                if since is not None and ts < since:
                    continue
                token_id = str(t["asset_id"])
                price = Decimal(str(t["price"]))
                size = Decimal(str(t["size"]))
                category = cat_cache.get(token_id)
                if category is None:
                    # Look up Market by yes/no token.
                    m = s.scalars(
                        select(Market).where(
                            (Market.yes_token_id == token_id)
                            | (Market.no_token_id == token_id)
                        )
                    ).first()
                    category = (m.category if m else "") or ""
                    cat_cache[token_id] = category
                if category:
                    fb = fee_for_fill(
                        price=price,
                        size_shares=size,
                        category=category,
                        is_maker=False,  # live /trades path is taker fills
                    )
                    fee_usd = fb.gross_fee
                else:
                    # Conservative fallback when category is unknown: charge
                    # the repo-wide peak rate so we don't silently under-
                    # charge. crypto peak 0.0720 × p × (1-p) × size.
                    fee_usd = (
                        Decimal("0.0720") * price * (Decimal("1") - price) * size
                    )
                    log.warning(
                        "clob.fee.unknown_category token_id=%s using_crypto_peak",
                        token_id[:16],
                    )
                out.append(
                    TradeRecord(
                        trade_id=str(t["id"]),
                        order_id=str(t.get("order_id")) if t.get("order_id") else None,
                        token_id=token_id,
                        side=Side(t["side"]),
                        price=price,
                        size=size,
                        fee_usd=fee_usd,
                        filled_at=ts,
                        market_id=str(t["market"]) if t.get("market") else None,
                    )
                )
        return out
