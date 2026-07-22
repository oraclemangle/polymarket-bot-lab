from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta


def test_latest_book_state_rejects_stale_book(tmp_path):
    from bots.bot_e_recorder.schema import init_db
    from bots.crypto_fair_value.discovery import latest_book_state
    from bots.crypto_fair_value.model import MarketMeta

    db_path = tmp_path / "recorder.db"
    conn = init_db(db_path)
    now = datetime.now(UTC)
    now_ms = int(now.timestamp() * 1000)
    stale_ms = int((now - timedelta(seconds=10)).timestamp() * 1000)
    meta = MarketMeta(
        condition_id="cond-stale",
        question="Bitcoin Up or Down - test",
        end_ms=now_ms + 60_000,
        start_ms=now_ms - 240_000,
        symbol="BTC",
        duration_minutes=5,
        yes_token_id="yes-stale",
        no_token_id="no-stale",
    )
    payload = json.dumps({
        "bids": [{"price": "0.48", "size": "100"}],
        "asks": [{"price": "0.52", "size": "100"}],
    })
    conn.execute(
        "INSERT INTO pm_events(received_at_ms, subscription_id, event_type, asset_id, condition_id, payload_json) VALUES (?, 's', 'book', ?, ?, ?)",
        (stale_ms, meta.yes_token_id, meta.condition_id, payload),
    )
    conn.execute(
        "INSERT INTO pm_events(received_at_ms, subscription_id, event_type, asset_id, condition_id, payload_json) VALUES (?, 's', 'book', ?, ?, ?)",
        (stale_ms, meta.no_token_id, meta.condition_id, payload),
    )
    conn.commit()
    assert latest_book_state(conn, meta, now_ms=now_ms, max_age_sec=5) is None
    conn.close()
