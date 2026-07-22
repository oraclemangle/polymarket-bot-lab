from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from bots.wallet_observer.schema import init_db
from scripts.wallet_observer_settlement_join import (
    fetch_gamma_markets_by_tokens,
    labelled_fill_count,
    run_join,
    upsert_market,
)


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self._payload


class FakeClient:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url: str, *, params: object, timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        payload = self.payloads.pop(0) if self.payloads else []
        return FakeResponse(payload)

    def close(self) -> None:
        self.closed = True


def _insert_fill(con: sqlite3.Connection, token_id: str) -> None:
    con.execute(
        """
        INSERT INTO wallet_observed_fills (
            tx_hash, log_index, block_number, block_ts, exchange,
            order_hash, maker_address, taker_address, side_raw, token_id,
            maker_amount_filled, taker_amount_filled, fee_raw, builder_code,
            metadata, observed_address, observed_role, tier, user_name,
            pv_rank, side, price, size_shares, inserted_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "0x" + "11" * 32,
            1,
            100,
            1_770_000_000,
            "CTF",
            "0x" + "22" * 32,
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            1,
            token_id,
            "100000000",
            "5000000",
            "0",
            "0x" + "00" * 32,
            "0x" + "00" * 32,
            "0x2222222222222222222222222222222222222222",
            "taker",
            "A_human_profitable",
            "Example",
            1,
            "BUY",
            0.05,
            100.0,
            1_770_000_001,
        ),
    )


def test_fetch_gamma_markets_by_tokens_uses_repeated_snake_case_param() -> None:
    client = FakeClient([[{"id": "1"}]])
    rows = fetch_gamma_markets_by_tokens(
        client, ["tok-a", "tok-b"], chunk_size=25, rate_limit_sec=0
    )

    assert rows == [{"id": "1"}]
    params = client.calls[0]["params"]
    assert ("clob_token_ids", "tok-a") in params
    assert ("clob_token_ids", "tok-b") in params
    assert ("limit", "2") in params


def test_upsert_market_labels_non_yes_no_binary_by_outcome_index(tmp_path: Path) -> None:
    con = init_db(tmp_path / "wallet.db")
    _insert_fill(con, "tok-down")

    n_tokens = upsert_market(
        con,
        {
            "id": "gamma-1",
            "conditionId": "cid-1",
            "question": "Will X go up or down?",
            "endDate": "2026-05-01T00:00:00Z",
            "closed": True,
            "outcomes": '["Up", "Down"]',
            "clobTokenIds": '["tok-up", "tok-down"]',
            "outcomePrices": '["0", "1"]',
        },
        now_s=1_770_000_100,
    )

    assert n_tokens == 2
    row = con.execute(
        """
        SELECT mt.outcome, mt.outcome_index, mr.winning_outcome_index,
               mr.settled, mr.settlement_method
        FROM wallet_market_tokens mt
        JOIN wallet_market_resolutions mr ON mr.condition_id = mt.condition_id
        WHERE mt.token_id = 'tok-down'
        """
    ).fetchone()
    assert row == ("Down", 1, 1, 1, "strict_closed_exact_outcome")
    assert labelled_fill_count(con) == 1


def test_run_join_maps_tokens_and_counts_labelled_fills(tmp_path: Path) -> None:
    db = tmp_path / "wallet.db"
    con = init_db(db)
    _insert_fill(con, "tok-yes")
    con.close()
    client = FakeClient(
        [
            [
                {
                    "id": "gamma-2",
                    "conditionId": "cid-2",
                    "question": "Will Y happen?",
                    "endDate": "2026-05-01T00:00:00Z",
                    "closed": True,
                    "outcomes": '["Yes", "No"]',
                    "clobTokenIds": '["tok-yes", "tok-no"]',
                    "outcomePrices": '["1", "0"]',
                }
            ],
            [],
        ]
    )

    stats = run_join(
        db_path=db,
        max_tokens=10,
        max_markets=10,
        chunk_size=10,
        rate_limit_sec=0,
        http_client=client,
    )

    assert stats.unmapped_tokens == 1
    assert stats.token_market_rows == 1
    assert stats.token_rows_upserted == 2
    assert stats.newly_settled == 1
    assert stats.labelled_fills == 1
