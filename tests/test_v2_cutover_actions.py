from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from core.db import Event, Order, get_session_factory
from core.polymarket_v2 import (
    CONDITIONAL_TOKENS,
    CTF_EXCHANGE_V2,
    NEG_RISK_CTF_EXCHANGE_V2,
    PUSD_TOKEN_PROXY,
)


def _add_order(session, order_id: str, *, status: str, placed_at: datetime) -> None:
    session.add(
        Order(
            order_id=order_id,
            bot_id="bot_x",
            condition_id="cid",
            token_id="tok",
            side="BUY",
            price=Decimal("0.50"),
            size=Decimal("10"),
            status=status,
            order_type="GTC",
            placed_at=placed_at,
        )
    )


def test_approve_polymarket_targets_v2_contracts():
    from scripts import approve_polymarket as mod

    assert mod.PUSD_TOKEN_PROXY == PUSD_TOKEN_PROXY
    assert mod.CTF_EXCHANGE_V2 == CTF_EXCHANGE_V2
    assert mod.NEG_RISK_CTF_EXCHANGE_V2 == NEG_RISK_CTF_EXCHANGE_V2
    assert mod.CONDITIONAL_TOKENS == CONDITIONAL_TOKENS

    src = Path(mod.__file__).read_text()
    assert "py_clob_client.config" not in src
    assert "USDC.e.approve" not in src


def test_mark_cutover_cancelled_orders_dry_run_is_readonly(tmp_db):
    from scripts import mark_cutover_cancelled_orders as mod

    sf = get_session_factory()
    cutover = datetime(2026, 4, 28, 11, 0, tzinfo=UTC)
    with sf() as s:
        _add_order(s, "live-before", status="OPEN", placed_at=datetime(2026, 4, 28, 10, 0, tzinfo=UTC))
        s.commit()

    assert mod.main(["--cutover-utc", cutover.isoformat()]) == 0

    with sf() as s:
        order = s.get(Order, "live-before")
        assert order.status == "OPEN"
        assert s.query(Event).count() == 0


def test_mark_cutover_cancelled_orders_only_marks_v1_live_rows(tmp_db):
    from scripts import mark_cutover_cancelled_orders as mod

    sf = get_session_factory()
    cutover = datetime(2026, 4, 28, 11, 0, tzinfo=UTC)
    with sf() as s:
        _add_order(s, "live-before", status="OPEN", placed_at=datetime(2026, 4, 28, 10, 0, tzinfo=UTC))
        _add_order(s, "partial-before", status="PARTIAL", placed_at=datetime(2026, 4, 28, 10, 30, tzinfo=UTC))
        _add_order(s, "paper-before", status="PAPER_OPEN", placed_at=datetime(2026, 4, 28, 10, 0, tzinfo=UTC))
        _add_order(s, "paper-abc", status="OPEN", placed_at=datetime(2026, 4, 28, 10, 0, tzinfo=UTC))
        _add_order(s, "live-after", status="OPEN", placed_at=datetime(2026, 4, 28, 12, 0, tzinfo=UTC))
        _add_order(s, "filled-before", status="FILLED", placed_at=datetime(2026, 4, 28, 10, 0, tzinfo=UTC))
        s.commit()

    assert mod.main(["--execute", "--cutover-utc", cutover.isoformat()]) == 0

    with sf() as s:
        assert s.get(Order, "live-before").status == "CANCELLED_CUTOVER"
        assert s.get(Order, "partial-before").status == "CANCELLED_CUTOVER"
        assert s.get(Order, "paper-before").status == "PAPER_OPEN"
        assert s.get(Order, "paper-abc").status == "OPEN"
        assert s.get(Order, "live-after").status == "OPEN"
        assert s.get(Order, "filled-before").status == "FILLED"
        events = list(s.query(Event).order_by(Event.id))
        assert len(events) == 3
        assert events[-1].event_type == "orders.cutover_cancelled.summary"
        assert events[-1].payload["count"] == 2
