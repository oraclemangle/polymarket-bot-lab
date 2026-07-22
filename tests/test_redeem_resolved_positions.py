from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import scripts.redeem_resolved_positions as redeem
from core.db import Event, Position, Trade, get_session_factory
from core.polymarket_v2 import POLYGON_CHAIN_ID, USDC_E


def test_standard_zero_value_guard_rejects_targeted_scope(capsys):
    code = redeem.main([
        "--standard-zero-value-only",
        "--condition-id",
        "0xabc",
    ])

    assert code == 2
    assert "--standard-zero-value-only cannot be combined" in capsys.readouterr().err


def test_standard_zero_value_guard_rejects_negative_risk_scope(capsys):
    code = redeem.main([
        "--standard-zero-value-only",
        "--include-negative-risk-zero-value",
    ])

    assert code == 2
    assert "--standard-zero-value-only cannot be combined" in capsys.readouterr().err


def test_local_position_filter_requires_bot_id(capsys):
    code = redeem.main(["--only-local-open-positions"])

    assert code == 2
    assert "--only-local-open-positions requires --bot-id" in capsys.readouterr().err


def test_negative_risk_amount_vector_uses_outcome_index():
    candidate = redeem.RedeemCandidate(
        title="Weather",
        condition_id="0xcondition",
        token_id="123",
        outcome="No",
        outcome_index=1,
        size=Decimal("5"),
        current_value=Decimal("0"),
        collateral="adapter",
        balance_raw=5_000_000,
        gas_estimate=80_000,
        negative_risk=True,
    )

    assert candidate.neg_risk_amounts() == [0, 5_000_000]


def test_local_negative_risk_accounting_closes_position(tmp_db, monkeypatch):
    from core import portfolio

    monkeypatch.setattr(portfolio, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))
    sessions = get_session_factory()
    with sessions() as session:
        pos = Position(
            bot_id="bot_d_live_probe",
            condition_id="2161889",
            token_id="tok_yes",
            side="YES",
            size=Decimal("5"),
            avg_price=Decimal("0.06"),
            cost_basis_usd=Decimal("0.30"),
            status="OPEN",
        )
        session.add(pos)
        session.commit()
        position_id = pos.id

    candidate = redeem.RedeemCandidate(
        title="Will the highest temperature in New York City be between 66-67F?",
        condition_id="0xabc",
        token_id="tok_yes",
        outcome="Yes",
        outcome_index=0,
        size=Decimal("5"),
        current_value=Decimal("0"),
        collateral="adapter",
        balance_raw=5_000_000,
        gas_estimate=80_000,
        negative_risk=True,
        local_bot_id="bot_d_live_probe",
        local_position_id=position_id,
        local_condition_id="2161889",
        local_size=Decimal("5"),
    )

    redeem._record_local_redeem_fill(candidate, "0xhash")

    with sessions() as session:
        pos = session.get(Position, position_id)
        trade = session.get(Trade, "negrisk-zero-redeem:0xhash:tok_yes")
        event = session.query(Event).filter_by(event_type="portfolio.negrisk_zero_redeem").one()

    assert pos is not None
    assert pos.status == "CLOSED"
    assert pos.size == Decimal("0E-8")
    assert trade is not None
    assert trade.side == "SELL"
    assert trade.price == Decimal("0E-8")
    assert event.payload["token_id"] == "tok_yes"


def test_local_redeem_accounting_marks_position_redeemed(tmp_db):
    sessions = get_session_factory()
    with sessions() as session:
        pos = Position(
            bot_id="crypto_probability_gap_live_maker",
            condition_id="cid",
            token_id="tok_yes",
            side="YES",
            size=Decimal("5"),
            avg_price=Decimal("0.40"),
            cost_basis_usd=Decimal("2.00"),
            status="OPEN",
        )
        session.add(pos)
        session.commit()
        position_id = pos.id

    candidate = redeem.RedeemCandidate(
        title="Crypto test",
        condition_id="0xabc",
        token_id="tok_yes",
        outcome="Yes",
        outcome_index=0,
        size=Decimal("5"),
        current_value=Decimal("5.00"),
        collateral=USDC_E,
        balance_raw=5_000_000,
        gas_estimate=100_000,
        local_bot_id="crypto_probability_gap_live_maker",
        local_position_id=position_id,
        local_condition_id="cid",
        local_size=Decimal("5"),
    )

    redeem._record_local_redeem(candidate, "0xhash")

    with sessions() as session:
        pos = session.get(Position, position_id)
        redeem_event = session.query(Event).filter_by(event_type="portfolio.redeem").one()
        tx_event = session.query(Event).filter_by(event_type="portfolio.redeem_tx").one()

    assert pos is not None
    assert pos.status == "REDEEMED"
    assert redeem_event.payload["usdc_received"] == "5.00"
    assert redeem_event.payload["realised_usd"] == "3.00000000"
    assert tx_event.payload["tx_hash"] == "0xhash"


def test_execute_refuses_candidate_cap_before_sending(monkeypatch, capsys):
    sent = {"called": False}

    class FakeWeb3:
        class HTTPProvider:
            def __init__(self, *_args, **_kwargs):
                pass

        def __init__(self, _provider):
            self.middleware_onion = SimpleNamespace(inject=lambda *_a, **_k: None)
            self.eth = SimpleNamespace(chain_id=POLYGON_CHAIN_ID)

        def is_connected(self):
            return True

        @staticmethod
        def to_checksum_address(addr):
            return addr

    class FakeKeystore:
        @classmethod
        def load_from_settings(cls, _settings):
            return cls()

        def signer(self):
            return SimpleNamespace(address="0x1111111111111111111111111111111111111111")

        def close(self):
            pass

    def fake_discover(*_args, **_kwargs):
        candidate = redeem.RedeemCandidate(
            title="Bitcoin Up or Down",
            condition_id="0xcondition",
            token_id="123",
            outcome="Up",
            outcome_index=0,
            size=Decimal("60"),
            current_value=Decimal("0"),
            collateral=USDC_E,
            balance_raw=60_000_000,
            gas_estimate=80_000,
        )
        return [candidate], [{}]

    def fake_send(*_args, **_kwargs):
        sent["called"] = True
        raise AssertionError("should not send tx when cap fails")

    monkeypatch.setattr(redeem, "Web3", FakeWeb3)
    monkeypatch.setattr(redeem, "Keystore", FakeKeystore)
    monkeypatch.setattr(redeem, "_discover_candidates", fake_discover)
    monkeypatch.setattr(redeem, "_send_tx", fake_send)

    code = redeem.main([
        "--execute",
        "--yes",
        "--standard-zero-value-only",
        "--max-candidates",
        "0",
    ])

    captured = capsys.readouterr()
    assert code == 7
    assert "candidate cap exceeded" in captured.err
    assert sent["called"] is False
