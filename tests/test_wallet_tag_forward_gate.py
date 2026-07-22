from __future__ import annotations

from pathlib import Path

from scripts.research.wallet_observer import init_db
from scripts.research.wallet_observer_report import load_observed_trades_with_outcomes
from scripts.research.wallet_observer_resolutions import (
    find_unresolved_markets,
    parse_args,
    upsert_market,
)


def _insert_observed_trade(
    con,
    *,
    wallet: str = "0xwallet",
    condition_id: str,
    timestamp_s: int,
    outcome: str,
    outcome_index: int,
    price: float = 0.25,
    token_amount: float = 10.0,
) -> None:
    con.execute(
        """
        INSERT INTO observed_trades (
            wallet, asset_id, timestamp_s, taker_direction, price,
            token_amount, condition_id, market_id, outcome, outcome_index,
            usd_amount, ingested_at
        )
        VALUES (?, ?, ?, 'BUY', ?, ?, ?, ?, ?, ?, ?, '2026-05-09T00:00:00+00:00')
        """,
        (
            wallet,
            f"asset-{condition_id}-{outcome_index}",
            timestamp_s,
            price,
            token_amount,
            condition_id,
            condition_id,
            outcome,
            outcome_index,
            price * token_amount,
        ),
    )
    con.commit()


def test_gamma_resolution_joins_observed_trades_by_condition_id(tmp_path: Path) -> None:
    con = init_db(tmp_path / "wallet_tag_forward.db")
    condition_id = "0xcondition"
    _insert_observed_trade(
        con,
        condition_id=condition_id,
        timestamp_s=1_777_000_000,
        outcome="Yes",
        outcome_index=0,
    )
    con.execute(
        """
        INSERT INTO observed_markets (
            market_id, condition_id, settled, updated_at
        )
        VALUES ('665374', ?, 0, '2026-05-09T00:00:00+00:00')
        """,
        (condition_id,),
    )
    con.commit()

    transitioned = upsert_market(
        con,
        {
            "id": "665374",
            "conditionId": condition_id,
            "closed": True,
            "outcomePrices": '["1", "0"]',
            "endDate": "2026-05-09T01:00:00Z",
            "question": "Test market",
        },
    )
    con.commit()

    assert transitioned is True
    rows = con.execute(
        "SELECT market_id, condition_id, settled, proxy_settled, yes_won "
        "FROM observed_markets"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "665374"
    assert rows[0][1] == condition_id
    assert rows[0][2] == 1
    assert rows[0][3] == 0
    assert rows[0][4] == 1

    scored = load_observed_trades_with_outcomes(con, fee_rate=0.0)
    assert len(scored) == 1
    assert scored[0]["condition_id"] == condition_id
    assert scored[0]["yes_won"] == 1
    assert scored[0]["pnl"] == 7.5


def test_forward_report_scores_yes_and_no_buys_by_token_side(tmp_path: Path) -> None:
    con = init_db(tmp_path / "wallet_tag_forward.db")
    cases = [
        ("cond-yes-win-yes-token", "Yes", 0, 1, 1),
        ("cond-yes-win-no-token", "No", 1, 1, 0),
        ("cond-no-win-yes-token", "Yes", 0, 0, 0),
        ("cond-no-win-no-token", "No", 1, 0, 1),
    ]
    for idx, (condition_id, outcome, outcome_index, market_yes_won, _expected_token_won) in enumerate(cases):
        _insert_observed_trade(
            con,
            condition_id=condition_id,
            timestamp_s=1_777_000_000 + idx,
            outcome=outcome,
            outcome_index=outcome_index,
            price=0.20,
            token_amount=5.0,
        )
        con.execute(
            """
            INSERT INTO observed_markets (
                market_id, condition_id, end_date_iso, settled, yes_won, updated_at
            )
            VALUES (?, ?, '2026-05-09T01:00:00Z', 1, ?, '2026-05-09T00:00:00+00:00')
            """,
            (condition_id, condition_id, market_yes_won),
        )
    con.commit()

    scored = load_observed_trades_with_outcomes(con, fee_rate=0.0)
    by_condition = {row["condition_id"]: row for row in scored}

    assert set(by_condition) == {case[0] for case in cases}
    for condition_id, _outcome, _outcome_index, market_yes_won, expected_token_won in cases:
        row = by_condition[condition_id]
        assert row["market_yes_won"] == market_yes_won
        assert row["yes_won"] == expected_token_won
        expected_pnl = (5.0 if expected_token_won else 0.0) - 1.0
        assert row["pnl"] == expected_pnl


def test_find_unresolved_skips_condition_with_any_settled_row(tmp_path: Path) -> None:
    con = init_db(tmp_path / "wallet_tag_forward.db")
    condition_id = "0xcondition"
    _insert_observed_trade(
        con,
        condition_id=condition_id,
        timestamp_s=1_777_000_000,
        outcome="Yes",
        outcome_index=0,
    )
    con.execute(
        """
        INSERT INTO observed_markets (
            market_id, condition_id, settled, updated_at
        )
        VALUES
            ('legacy-gamma-id', ?, 0, '2026-05-09T00:00:00+00:00'),
            (?, ?, 1, '2026-05-09T00:00:00+00:00')
        """,
        (condition_id, condition_id, condition_id),
    )
    con.commit()

    assert find_unresolved_markets(con, 10) == []


def test_proxy_settlement_scores_near_final_after_end_date(tmp_path: Path) -> None:
    con = init_db(tmp_path / "wallet_tag_forward.db")
    condition_id = "0xproxycondition"
    _insert_observed_trade(
        con,
        condition_id=condition_id,
        timestamp_s=1_777_000_000,
        outcome="No",
        outcome_index=1,
        price=0.20,
        token_amount=5.0,
    )

    transitioned = upsert_market(
        con,
        {
            "id": "665375",
            "conditionId": condition_id,
            "closed": False,
            "outcomePrices": '["0.0005", "0.9995"]',
            "endDate": "2026-05-08T01:00:00Z",
            "question": "Proxy market",
        },
    )
    con.commit()

    assert transitioned is True
    row = con.execute(
        "SELECT settled, proxy_settled, settlement_method, yes_won "
        "FROM observed_markets WHERE condition_id = ?",
        (condition_id,),
    ).fetchone()
    assert row["settled"] == 0
    assert row["proxy_settled"] == 1
    assert row["settlement_method"] == "proxy_near_final_after_end"
    assert row["yes_won"] == 0

    scored = load_observed_trades_with_outcomes(con, fee_rate=0.0)
    assert len(scored) == 1
    assert scored[0]["market_yes_won"] == 0
    assert scored[0]["yes_won"] == 1
    assert scored[0]["pnl"] == 4.0


def test_near_final_before_end_date_does_not_settle(tmp_path: Path) -> None:
    con = init_db(tmp_path / "wallet_tag_forward.db")
    condition_id = "0xfuturecondition"
    _insert_observed_trade(
        con,
        condition_id=condition_id,
        timestamp_s=1_777_000_000,
        outcome="Yes",
        outcome_index=0,
    )

    transitioned = upsert_market(
        con,
        {
            "id": "665376",
            "conditionId": condition_id,
            "closed": False,
            "outcomePrices": '["0.9995", "0.0005"]',
            "endDate": "2099-05-08T01:00:00Z",
        },
    )
    con.commit()

    assert transitioned is False
    assert load_observed_trades_with_outcomes(con, fee_rate=0.0) == []


def test_find_unresolved_skips_condition_with_proxy_settled_row(tmp_path: Path) -> None:
    con = init_db(tmp_path / "wallet_tag_forward.db")
    condition_id = "0xproxysettled"
    _insert_observed_trade(
        con,
        condition_id=condition_id,
        timestamp_s=1_777_000_000,
        outcome="Yes",
        outcome_index=0,
    )
    con.execute(
        """
        INSERT INTO observed_markets (
            market_id, condition_id, settled, proxy_settled, updated_at
        )
        VALUES (?, ?, 0, 1, '2026-05-09T00:00:00+00:00')
        """,
        (condition_id, condition_id),
    )
    con.commit()

    assert find_unresolved_markets(con, 10) == []


def test_resolution_backfill_default_age_window_is_30_days() -> None:
    assert parse_args([]).max_age_days == 30


def test_forward_report_uses_proxy_only_when_strict_sample_below_gate(tmp_path: Path) -> None:
    con = init_db(tmp_path / "wallet_tag_forward.db")
    for idx in range(200):
        condition_id = f"strict-{idx}"
        _insert_observed_trade(
            con,
            condition_id=condition_id,
            timestamp_s=1_777_000_000 + idx,
            outcome="Yes",
            outcome_index=0,
            price=0.20,
            token_amount=5.0,
        )
        con.execute(
            """
            INSERT INTO observed_markets (
                market_id, condition_id, settled, proxy_settled, yes_won, updated_at
            )
            VALUES (?, ?, 1, 0, 1, '2026-05-09T00:00:00+00:00')
            """,
            (condition_id, condition_id),
        )
    _insert_observed_trade(
        con,
        condition_id="proxy-extra",
        timestamp_s=1_777_001_000,
        outcome="Yes",
        outcome_index=0,
        price=0.20,
        token_amount=5.0,
    )
    con.execute(
        """
        INSERT INTO observed_markets (
            market_id, condition_id, settled, proxy_settled, yes_won, updated_at
        )
        VALUES ('proxy-extra', 'proxy-extra', 0, 1, 1, '2026-05-09T00:00:00+00:00')
        """
    )
    con.commit()

    scored = load_observed_trades_with_outcomes(con, fee_rate=0.0)

    assert len(scored) == 200
    assert {row["settlement_label_type"] for row in scored} == {"strict"}
