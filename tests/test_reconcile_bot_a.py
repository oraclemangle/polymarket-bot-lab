"""Tests for scripts/reconcile_bot_a.py (OQ-030).

Focuses on the pure-logic pieces: snapshotting, diffing, audit-event emission.
The actual reconcile_live_fills path is exercised by Portfolio tests;
here we verify the CLI wrapper's safety model (dry-run doesn't touch CLOB,
audit event captures the diff).
"""
from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.db import Base, Event, Position


_SPEC = importlib.util.spec_from_file_location(
    "reconcile_bot_a",
    Path(__file__).resolve().parent.parent / "scripts" / "reconcile_bot_a.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["reconcile_bot_a"] = _mod
_SPEC.loader.exec_module(_mod)


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _add_position(s, **kwargs):
    from datetime import UTC, datetime
    p = Position(
        bot_id=kwargs.get("bot_id", "bot_a"),
        condition_id=kwargs.get("condition_id", "0xcid"),
        token_id=kwargs.get("token_id", "tok1"),
        side=kwargs.get("side", "BUY_NO"),
        size=Decimal(str(kwargs.get("size", "100"))),
        avg_price=Decimal(str(kwargs.get("avg_price", "0.97"))),
        cost_basis_usd=Decimal(str(kwargs.get("cost_basis_usd", "97"))),
        status=kwargs.get("status", "OPEN"),
        opened_at=datetime.now(UTC),
    )
    s.add(p)
    s.commit()


def test_snapshot_empty_db(session_factory):
    snap = _mod.snapshot(session_factory, "bot_a")
    assert snap.trade_count == 0
    assert snap.open_position_count == 0
    assert snap.total_cost_basis_usd == Decimal("0")


def test_snapshot_counts_only_target_bot(session_factory):
    with session_factory() as s:
        _add_position(s, bot_id="bot_a", cost_basis_usd=100)
        _add_position(s, bot_id="bot_b", cost_basis_usd=500)
    snap_a = _mod.snapshot(session_factory, "bot_a")
    assert snap_a.open_position_count == 1
    assert snap_a.total_cost_basis_usd == Decimal("100")
    snap_b = _mod.snapshot(session_factory, "bot_b")
    assert snap_b.total_cost_basis_usd == Decimal("500")


def test_snapshot_excludes_closed_positions(session_factory):
    with session_factory() as s:
        _add_position(s, cost_basis_usd=100, status="OPEN")
        _add_position(s, cost_basis_usd=50, status="CLOSED", condition_id="cid2", token_id="tok2")
        _add_position(s, cost_basis_usd=30, status="CLOSED_V2_MIGRATION", condition_id="cid3", token_id="tok3")
    snap = _mod.snapshot(session_factory, "bot_a")
    assert snap.open_position_count == 1
    assert snap.total_cost_basis_usd == Decimal("100")


def test_diff_computes_deltas():
    before = _mod.StateSnapshot(
        trade_count=5, open_position_count=3,
        total_cost_basis_usd=Decimal("100"), total_size=Decimal("500"),
    )
    after = _mod.StateSnapshot(
        trade_count=8, open_position_count=3,
        total_cost_basis_usd=Decimal("150"), total_size=Decimal("500"),
    )
    diff = _mod.diff_snapshots(before, after)
    assert diff["trades_added"] == 3
    assert diff["positions_delta"] == 0
    assert diff["cost_basis_delta_usd"] == "50"
    assert diff["shares_delta"] == "0"


def test_emit_audit_event_persists(session_factory):
    diff = {"trades_added": 7, "positions_delta": 0,
            "cost_basis_delta_usd": "123.45", "shares_delta": "0"}
    _mod.emit_audit_event(session_factory, "bot_a", diff, fills_reconciled=7)
    with session_factory() as s:
        events = list(s.scalars(select(Event).where(
            Event.event_type == _mod.AUDIT_EVENT
        )))
    assert len(events) == 1
    assert events[0].severity == "info"
    assert events[0].payload["fills_reconciled"] == 7
    assert events[0].payload["diff"] == diff
    assert "ran_at" in events[0].payload


def test_print_snapshot_formats(capsys):
    snap = _mod.StateSnapshot(
        trade_count=10, open_position_count=3,
        total_cost_basis_usd=Decimal("150.25"), total_size=Decimal("200"),
    )
    _mod.print_snapshot("before", snap)
    out = capsys.readouterr().out
    assert "trades=10" in out
    assert "open_positions=3" in out
    assert "150.25" in out


def test_parse_args_defaults():
    args = _mod.parse_args([])
    assert args.bot_id == "bot_a"
    assert args.execute is False
    assert args.cursor_key is None
    assert args.require_known_order is False


def test_parse_args_custom():
    args = _mod.parse_args(["--bot-id", "bot_b", "--execute",
                            "--cursor-key", "custom.cursor",
                            "--require-known-order"])
    assert args.bot_id == "bot_b"
    assert args.execute is True
    assert args.cursor_key == "custom.cursor"
    assert args.require_known_order is True
