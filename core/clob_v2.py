"""CLOB client wrapper — V2 variant (Polymarket cutover 2026-04-28 11:00 UTC).

Parallel implementation of `core/clob.py`'s `ClobWrapper`, built against
`py-clob-client-v2==1.0.0`. Public surface is identical so the bots' call
sites need no changes on cutover day.

Usage pattern on 2026-04-28 afternoon:

    # Before:
    from core.clob import ClobWrapper
    # After:
    from core.clob_v2 import ClobWrapperV2 as ClobWrapper

One import line per bot `__main__.py`. Everything else stays.

Differences vs V1 (all internal, not exposed to callers):

  1. Imports — `py_clob_client_v2` instead of `py_clob_client`.
  2. Auth derivation — `client.create_or_derive_api_key()` (V2) vs
     `client.create_or_derive_api_creds()` (V1). Same L1/L2 logic.
  3. Order placement — V2 merges V1's `create_order()` + `post_order()`
     into `create_and_post_order(order_args, options, order_type)`.
     V2 adds a mandatory `PartialCreateOrderOptions(neg_risk, tick_size)`
     argument.
  4. Method renames — `get_orders` → `get_open_orders`; `get_trades`
     shape unchanged.
  5. Contract addresses — read from `core.polymarket_v2` instead of
     `py_clob_client.config.get_contract_config`.

Known untested-before-cutover paths:
  - Live `create_and_post_order` return-dict shape against the real V2
    endpoint. We handle both `order_id`/`orderID` keys and known status
    strings; anything unexpected logs and returns status="UNKNOWN".
  - `get_open_orders` / `get_trades` return-dict shapes. Same defensive
    handling.
  - `neg_risk` lookup — we default to False and cache per token_id.
    The canonical source is `markets.is_neg_risk` in the DB, which the
    bots populate via ingest. If a token_id isn't found in the DB,
    we route through py-clob-client-v2's `get_neg_risk(token_id)`
    helper which queries the exchange.

All V2 exchange addresses are pinned in `core/polymarket_v2.py` and
asserted by `tests/test_polymarket_v2_constants.py`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Re-use the V1 module's dataclasses + rate limiter + preflight scaffolding.
# Only the client-call sites change.
from core.clob import (
    ClobAuthError,
    ClobError,
    ClobNotReadyError,
    OrderBook,
    OrderRecord,
    OrderResponse,
    OrderType,
    Side,
    TokenBucket,
    TradeRecord,
    _PreflightStatus,
)
from core.config import (
    RATE_LIMIT_GENERAL_PER_10S,
    RATE_LIMIT_POST_ORDER_PER_10S,
    get_settings,
)
from core.polymarket_v2 import (
    BYTES32_ZERO,
    CLOB_MAIN_ENDPOINT,
    POLYGON_CHAIN_ID,
)

if TYPE_CHECKING:
    from core.keystore import Keystore

log = logging.getLogger(__name__)


def _trade_order_id(raw_trade: dict[str, Any]) -> str | None:
    """Return the order id from known V2 trade payload shapes.

    V2 live trade payloads may identify our order as ``order_id`` on some
    clients, ``taker_order_id`` when our submitted order crossed the book, or
    inside ``maker_orders`` when our resting order was hit. Returning one of
    these is required for Bot G's known-order live reconciler.
    """
    for key in ("order_id", "orderID", "taker_order_id", "takerOrderId"):
        value = raw_trade.get(key)
        if value:
            return str(value)
    maker_orders = raw_trade.get("maker_orders") or raw_trade.get("makerOrders") or []
    if isinstance(maker_orders, list) and maker_orders:
        first = maker_orders[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("order_id", "orderID", "id"):
                value = first.get(key)
                if value:
                    return str(value)
    return None


def _first_present(raw: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        value = raw.get(key)
        if value is not None and value != "":
            return value
    return None


def _open_order_remaining_size(raw_order: dict[str, Any]) -> Decimal:
    """Return remaining open size from known V2 order payload shapes."""
    explicit_remaining = _first_present(
        raw_order,
        (
            "size",
            "size_left",
            "sizeLeft",
            "remaining_size",
            "remainingSize",
            "size_remaining",
            "sizeRemaining",
        ),
    )
    if explicit_remaining is not None:
        try:
            return Decimal(str(explicit_remaining))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    original = _first_present(raw_order, ("original_size", "originalSize"))
    matched = _first_present(raw_order, ("size_matched", "sizeMatched"))
    try:
        if original is not None and matched is not None:
            remaining = Decimal(str(original)) - Decimal(str(matched))
            return max(remaining, Decimal("0"))
        if original is not None:
            return Decimal(str(original))
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return Decimal("0")


class ClobWrapperV2:
    """V2 public interface. Same surface as `core.clob.ClobWrapper`."""

    def __init__(
        self,
        keystore: Keystore | None,
        chain_id: int | None = None,
        host: str | None = None,
        paper_override: bool = False,
        builder_code: str | None = None,
    ):
        self.keystore = keystore
        self.chain_id = chain_id or get_settings().chain_id or POLYGON_CHAIN_ID
        # Post-cutover the main endpoint serves V2; we default to it rather
        # than the transitional clob-v2.polymarket.com hostname so the
        # cutover moment doesn't require a config change.
        self.host = host or get_settings().polymarket_host or CLOB_MAIN_ENDPOINT
        self.preflight = _PreflightStatus()
        # 2026-04-22 GLM-5.1 review A4 — paper_override is a read-only
        # property so no imported wrapper can flip it at runtime.
        self._paper_override = bool(paper_override)

        # builderCode (bytes32) for V2 builder-fee attribution. Resolution:
        #   1. Explicit ctor arg → use it.
        #   2. ``POLYMARKET_BUILDER_CODE`` env / Settings → use that.
        #   3. Fall back to ``BYTES32_ZERO`` (no attribution; orders post fine).
        # Per polymarket.com/v2-migration the field is a public identifier
        # not a secret, but the operator must still grab their personal
        # value from the settings UI. We treat it like other env-driven
        # settings: never log, never commit.
        self._builder_code = self._resolve_builder_code(builder_code)

        # Lazily constructed py_clob_client_v2.ClobClient.
        self._client: Any = None

        # Per-token caches populated by get_tick_size / neg-risk lookups.
        # V2's create_and_post_order demands both up-front. Caching prevents
        # an extra HTTP round-trip per order.
        self._tick_cache: dict[str, Decimal] = {}
        self._neg_risk_cache: dict[str, bool] = {}

        self._general_bucket = TokenBucket(int(RATE_LIMIT_GENERAL_PER_10S * 0.80), 10.0)
        self._order_bucket = TokenBucket(int(RATE_LIMIT_POST_ORDER_PER_10S * 0.80), 10.0)

        self._paper_callback: Callable[[dict], dict] | None = None

    @property
    def paper_override(self) -> bool:
        return self._paper_override

    @paper_override.setter
    def paper_override(self, value: bool) -> None:
        raise PermissionError(
            "ClobWrapperV2.paper_override is read-only after construction. "
            "Create a new wrapper instead of flipping the attribute. "
            "Added 2026-04-22 per GLM-5.1 fleet review A4.",
        )

    def _effective_paper(self) -> bool:
        return self.paper_override or not get_settings().is_live()

    @staticmethod
    def _resolve_builder_code(explicit: str | None) -> str:
        """Resolve the bytes32 builder code to use on every order.

        Validation: Polymarket accepts any 0x-prefixed 32-byte hex string.
        We normalise to lowercase. An invalid value falls back to
        BYTES32_ZERO with a one-shot WARNING — better to post un-attributed
        than to fail every order.
        """
        if explicit is not None:
            value = explicit
        else:
            value = (get_settings().polymarket_builder_code or "").strip()
        if not value:
            return BYTES32_ZERO
        # Normalise: ensure 0x-prefixed, 64 hex chars after the prefix.
        v = value.lower()
        if not v.startswith("0x"):
            v = "0x" + v
        body = v[2:]
        if len(body) != 64 or any(c not in "0123456789abcdef" for c in body):
            log.warning(
                "clob_v2.builder_code.invalid len=%d using_zero",
                len(body),
            )
            return BYTES32_ZERO
        return v

    @property
    def builder_code(self) -> str:
        """Effective builderCode (read-only); BYTES32_ZERO if unset."""
        return self._builder_code

    # --- Preflight gate (identical semantics to V1) ---
    def mark_preflight_done(self, hmac: bool, addrs: bool, collateral: bool) -> None:
        self.preflight.hmac_verified = hmac
        self.preflight.contract_addrs_verified = addrs
        self.preflight.collateral_verified = collateral
        log.info(
            "clob_v2.preflight.updated",
            extra={"hmac": hmac, "addrs": addrs, "collateral": collateral},
        )

    def load_preflight_from_db(self) -> bool:
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
                "V2 CLOB live path blocked: preflight incomplete "
                f"(hmac={self.preflight.hmac_verified}, "
                f"addrs={self.preflight.contract_addrs_verified}, "
                f"collateral={self.preflight.collateral_verified}). "
                "Re-run scripts/preflight_check.py --commit --live post-cutover."
            )

    # --- Lazy client construction (V2 imports) ---
    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if self.keystore is None:
            raise ClobAuthError("V2 live client requires a Keystore")
        try:
            from py_clob_client_v2 import (
                ApiCreds,  # noqa: F401  # type: ignore
                ClobClient,  # type: ignore
            )
        except ImportError as e:
            raise ClobError(
                "py-clob-client-v2 not installed. Install: "
                "`pip install py-clob-client-v2==1.0.0`"
            ) from e

        signer = self.keystore.signer()
        settings = get_settings()
        client_kwargs: dict[str, Any] = {
            "host": self.host,
            "chain_id": self.chain_id,
            "key": signer.key.hex(),
        }
        if settings.polymarket_signature_type is not None:
            client_kwargs["signature_type"] = settings.polymarket_signature_type
        funder = (settings.polymarket_funder_address or "").strip()
        if funder:
            client_kwargs["funder"] = funder
        client = ClobClient(**client_kwargs)
        # `create_or_derive_api_key()` tries POST /auth/api-key first and
        # only then falls back to GET /auth/derive-api-key. Cloudflare blocks
        # the create path in production, so go straight to the stable derive
        # path and avoid a scary but harmless startup error.
        creds = client.derive_api_key()
        client.set_api_creds(creds)
        self._client = client
        return client

    # --- Market data (public) ---
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
        cached = self._tick_cache.get(token_id)
        if cached is not None:
            return cached
        self._general_bucket.acquire()
        url = f"{self.host}/tick-size"
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url, params={"token_id": token_id})
            r.raise_for_status()
            tick = Decimal(str(r.json().get("minimum_tick_size", "0.01")))
        self._tick_cache[token_id] = tick
        return tick

    @retry(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.HTTPError,)),
        reraise=True,
    )
    def get_clob_market_info(self, condition_id: str) -> dict:
        """V2 single-call market metadata. Returns the raw response dict.

        V2 introduced ``getClobMarketInfo`` to avoid the V1 pattern of one
        round-trip per parameter (tick size, fee rate, min order size).
        Per the V2 docs the response shape is::

            {"mts", "mos", "fd": {"r", "e", "to"}, "t", "rfqe"}

        where ``mts`` = min tick size, ``mos`` = min order size, ``fd``
        = fee data (``r`` rate, ``e`` exponent, ``to`` taker-only flag),
        ``t`` = token list, ``rfqe`` = RFQ-eligible. Endpoint verified
        against https://docs.polymarket.com/api-reference/markets/get-clob-market-info
        and py-clob-client-v2 1.0.0 on 2026-04-28.

        Returns the dict as-is so callers can pick fields without a
        normalised data class hiding API drift. ``get_tick_size`` and
        ``_get_neg_risk`` remain as separate cached helpers; this method
        is for callers that need fees + tick + min-size at once.
        """
        self._general_bucket.acquire()
        url = f"{self.host}/clob-markets/{condition_id}"
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
        if not isinstance(data, dict):
            log.warning(
                "clob_v2.get_clob_market_info.unexpected_shape "
                "condition_id=%s type=%s",
                condition_id, type(data).__name__,
            )
            return {}
        return data

    def _get_neg_risk(self, token_id: str) -> bool:
        """V2 requires neg_risk in the order options. Source of truth:
        - Live: V2 client's `get_neg_risk(token_id)` (one RPC per new market).
        - Paper/fallback: `markets.is_neg_risk` column from the ingest pipeline.
        Both paths cache in memory.
        """
        cached = self._neg_risk_cache.get(token_id)
        if cached is not None:
            return cached
        if not self._effective_paper():
            try:
                client = self._get_client()
                nr = bool(client.get_neg_risk(token_id))
                self._neg_risk_cache[token_id] = nr
                return nr
            except Exception as e:
                log.warning("clob_v2.neg_risk.live_lookup_failed token=%s err=%s",
                            token_id, str(e)[:200])
        try:
            from sqlalchemy import select

            from core.db import Market, get_session_factory

            with get_session_factory()() as s:
                market = s.scalars(
                    select(Market).where(
                        (Market.yes_token_id == token_id) | (Market.no_token_id == token_id)
                    )
                ).first()
            if market is not None and market.is_neg_risk is not None:
                self._neg_risk_cache[token_id] = bool(market.is_neg_risk)
                return self._neg_risk_cache[token_id]
        except Exception as e:  # Fallback to exchange lookup.
            log.debug("clob_v2.neg_risk.db_lookup_failed err=%s", str(e)[:200])
        try:
            client = self._get_client()
            nr = bool(client.get_neg_risk(token_id))
        except Exception as e:
            log.warning("clob_v2.neg_risk.fallback_failed token=%s err=%s",
                        token_id, str(e)[:200])
            nr = False
        self._neg_risk_cache[token_id] = nr
        return nr

    # --- Orders (authenticated) ---
    def place_limit(
        self,
        token_id: str,
        price: Decimal,
        size: Decimal,
        side: Side,
        order_type: OrderType = OrderType.GTC,
        post_only: bool = False,
    ) -> OrderResponse:
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

        self._guard_live()

        # Polymarket CLOB rejects orders with size < 5.
        if Decimal(order_dict["size"]) < Decimal("5"):
            log.info("clob_v2.skip.below_min_size", extra=order_dict)
            return OrderResponse(order_id="", status="SKIPPED_MIN_SIZE", raw=order_dict)

        return self._place_limit_live(order_dict, post_only=post_only)

    @retry(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((httpx.ConnectTimeout,)),
        reraise=True,
    )
    def _place_limit_live(self, order_dict: dict, *, post_only: bool = False) -> OrderResponse:
        """V2 live order: create_and_post_order with OrderArgs +
        PartialCreateOrderOptions(neg_risk, tick_size) + order_type."""
        from py_clob_client_v2 import OrderArgs, PartialCreateOrderOptions  # type: ignore

        client = self._get_client()
        args = OrderArgs(
            token_id=order_dict["token_id"],
            price=float(order_dict["price"]),
            size=float(order_dict["size"]),
            side=order_dict["side"],
            builder_code=self._builder_code,
        )
        tick = str(self.get_tick_size(order_dict["token_id"]))
        neg_risk = self._get_neg_risk(order_dict["token_id"])
        options = PartialCreateOrderOptions(neg_risk=neg_risk, tick_size=tick)
        resp = client.create_and_post_order(
            order_args=args,
            options=options,
            order_type=order_dict["order_type"],
            post_only=post_only,
        )
        # Defensive: V2 response shape not yet observed against live endpoint.
        # Handle multiple known key patterns.
        if not isinstance(resp, dict):
            resp = {"raw": str(resp)}
        order_id = (
            resp.get("order_id")
            or resp.get("orderID")
            or resp.get("id")
            or ""
        )
        status = str(resp.get("status") or ("OPEN" if order_id else "UNKNOWN"))
        return OrderResponse(order_id=str(order_id), status=status, raw=resp)

    def _paper_fill(self, order_dict: dict) -> OrderResponse:
        """Paper-mode: same semantics as V1. Network never touched."""
        import uuid

        oid = f"paper-{uuid.uuid4().hex[:12]}"
        log.info("clob_v2.paper.place", extra={"order_id": oid, **order_dict})
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
            log.info("clob_v2.paper.cancel", extra={"order_id": order_id})
            return True
        client = self._get_client()
        from py_clob_client_v2 import OrderPayload  # type: ignore

        resp = client.cancel_order(OrderPayload(orderID=order_id))
        if isinstance(resp, dict):
            return bool(resp.get("canceled", False))
        return bool(resp)

    def cancel_all(self, market_id: str | None = None) -> int:
        self._guard_live()
        if self._effective_paper():
            log.info("clob_v2.paper.cancel_all", extra={"market_id": market_id})
            return 0
        client = self._get_client()
        from py_clob_client_v2 import OrderMarketCancelParams  # type: ignore

        resp = (
            client.cancel_all()
            if market_id is None
            else client.cancel_market_orders(OrderMarketCancelParams(market=market_id))
        )
        if not isinstance(resp, dict):
            return 0
        canceled = resp.get("canceled", 0)
        if isinstance(canceled, list):
            return len(canceled)
        try:
            return int(canceled)
        except (TypeError, ValueError):
            return 0

    def get_user_orders(self, market_id: str | None = None) -> list[OrderRecord]:
        """V1 name preserved for caller compatibility. V2 method is get_open_orders."""
        if self._effective_paper():
            return []
        client = self._get_client()
        if market_id is not None:
            from py_clob_client_v2 import OpenOrderParams  # type: ignore

            raw = client.get_open_orders(OpenOrderParams(market=market_id))
        else:
            raw = client.get_open_orders()
        out: list[OrderRecord] = []
        for o in raw or []:
            out.append(OrderRecord(
                order_id=str(o.get("id") or o.get("order_id") or ""),
                token_id=str(o.get("asset_id") or o.get("token_id") or ""),
                side=Side(o.get("side", "BUY")),
                price=Decimal(str(o.get("price", "0"))),
                size=_open_order_remaining_size(o),
                status=str(o.get("status", "")),
            ))
        return out

    def get_user_trades(self, since: float | None = None) -> list[TradeRecord]:
        """V1 name preserved for caller compatibility. V2 method is get_trades.

        Fee computation uses `core/fees.py` canonical parabolic formula via
        category lookup — see ADR-038 / GLM-5.1 review A3. The raw
        `fee_rate_bps` field from the trade response is ignored because
        (a) its units are ambiguous (bps vs 10000-scaled fraction) and
        (b) the old flat `bps x price x size / 10000` formula was missing
        the (1-p) factor, overcharging by factor 1/(1-p).
        """
        if self._effective_paper():
            return []
        client = self._get_client()
        raw = client.get_trades()
        out: list[TradeRecord] = []
        from sqlalchemy import select

        from core.db import Market, get_session_factory
        from core.fees import fee_for_fill
        sf = get_session_factory()
        cat_cache: dict[str, str] = {}

        def category_for_token(session, token_id: str) -> str:
            category = cat_cache.get(token_id)
            if category is None and token_id:
                m = session.scalars(
                    select(Market).where(
                        (Market.yes_token_id == token_id)
                        | (Market.no_token_id == token_id)
                    )
                ).first()
                category = (m.category if m else "") or ""
                cat_cache[token_id] = category
            return category or ""

        def fill_fee(session, *, token_id: str, price: Decimal, size: Decimal,
                     is_maker: bool) -> Decimal:
            category = category_for_token(session, token_id)
            if category:
                return fee_for_fill(
                    price=price,
                    size_shares=size,
                    category=category,
                    is_maker=is_maker,
                ).gross_fee
            log.warning(
                "clob_v2.fee.unknown_category token_id=%s using_crypto_peak",
                token_id[:16],
            )
            if is_maker:
                return Decimal("0")
            return Decimal("0.0720") * price * (Decimal("1") - price) * size

        maker_address = (
            getattr(self.keystore, "address", "") if self.keystore is not None else ""
        ).lower()
        with sf() as s:
            for t in raw or []:
                ts = float(t.get("match_time", 0) or 0)
                if since is not None and ts <= since:
                    continue
                maker_rows = []
                for maker_order in t.get("maker_orders") or t.get("makerOrders") or []:
                    if not isinstance(maker_order, dict):
                        continue
                    if (
                        maker_address
                        and str(maker_order.get("maker_address") or "").lower()
                        == maker_address
                    ):
                        maker_rows.append(maker_order)
                if maker_rows:
                    for idx, maker_order in enumerate(maker_rows):
                        token_id = str(
                            maker_order.get("asset_id")
                            or maker_order.get("token_id")
                            or ""
                        )
                        price = Decimal(str(maker_order["price"]))
                        size = Decimal(str(
                            maker_order.get("matched_amount")
                            or maker_order.get("size")
                            or "0"
                        ))
                        out.append(
                            TradeRecord(
                                trade_id=f"{t['id']}:maker:{idx}",
                                order_id=str(
                                    maker_order.get("order_id")
                                    or maker_order.get("orderID")
                                    or ""
                                ) or None,
                                token_id=token_id,
                                side=Side(maker_order["side"]),
                                price=price,
                                size=size,
                                fee_usd=fill_fee(
                                    s,
                                    token_id=token_id,
                                    price=price,
                                    size=size,
                                    is_maker=True,
                                ),
                                filled_at=ts,
                                market_id=str(t["market"]) if t.get("market") else None,
                            )
                        )
                    continue
                token_id = str(t.get("asset_id") or t.get("token_id") or "")
                price = Decimal(str(t["price"]))
                size = Decimal(str(t["size"]))
                fee = fill_fee(
                    s,
                    token_id=token_id,
                    price=price,
                    size=size,
                    is_maker=False,
                )
                out.append(
                    TradeRecord(
                        trade_id=str(t["id"]),
                        order_id=_trade_order_id(t),
                        token_id=token_id,
                        side=Side(t["side"]),
                        price=price,
                        size=size,
                        fee_usd=fee,
                        filled_at=ts,
                        market_id=str(t["market"]) if t.get("market") else None,
                    )
                )
        return out
