"""Notify tests — stub HTTP."""

from __future__ import annotations

import logging
import json

import core.notify as notify
from core.notify import Listener, TelegramClient


def test_httpx_info_logging_is_suppressed():
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
    assert notify.log.name == "core.notify"


def test_send_with_no_config_returns_false():
    client = TelegramClient(token="", allowed_chat_ids=[])
    assert not client.send("info", "hi")


def test_send_calls_api(monkeypatch):
    client = TelegramClient(token="tok", allowed_chat_ids=[42])

    class FakeResp:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):
            assert "tok" in url
            assert json["chat_id"] == 42
            assert "[kill]" in json["text"]
            return FakeResp()

    monkeypatch.setattr("httpx.Client", lambda *a, **k: FakeClient())
    assert client.send("kill", "boom")


def test_listener_ignores_unknown_chat_id(tmp_db):
    client = TelegramClient(token="tok", allowed_chat_ids=[42])
    listener = Listener(client=client)
    listener._handle_update({"message": {"chat": {"id": 99}, "text": "/status"}})


def test_listener_status_summary(tmp_db):
    from core.db import HaltFlag, get_session_factory

    session_factory = get_session_factory()
    with session_factory() as s:
        s.add(HaltFlag(bot_id="bot_e", halted=1, reason="test"))
        s.commit()

    sent = []
    client = TelegramClient(token="tok", allowed_chat_ids=[42])
    client.send = lambda sev, msg: sent.append((sev, msg)) or True
    listener = Listener(client=client)
    listener._handle_update({"message": {"chat": {"id": 42}, "text": "/status"}})
    assert sent and "HALTED" in sent[0][1]
    assert "bot_e:" in sent[0][1]
    assert "reason=test" in sent[0][1]


def test_listener_botg_summary_reads_latest_report(tmp_path):
    report = tmp_path / "bot_g_latest.json"
    report.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-05T11:24:06+00:00",
                "cutoff": "2026-04-28T11:24:06+00:00",
                "overall": {
                    "bot_g_prime_live": {
                        "n_orders": 36,
                        "n_fills": 31,
                        "n_resolved": 31,
                        "won": 0,
                        "realized_pnl_usd": -71.33,
                        "roi_pct": -100.0,
                        "roi_ex_largest_two_pct": -100.0,
                    },
                    "bot_g_prime_late_cheap": {
                        "n_orders": 2,
                        "n_fills": 2,
                        "n_resolved": 1,
                        "won": 1,
                        "realized_pnl_usd": 95.0,
                        "roi_pct": 1900.0,
                        "roi_ex_largest_two_pct": None,
                    },
                },
            }
        )
    )
    sent = []
    client = TelegramClient(token="tok", allowed_chat_ids=[42])
    client.send = lambda sev, msg: sent.append((sev, msg)) or True
    listener = Listener(client=client, bot_g_report_path=report)

    listener._handle_update({"message": {"chat": {"id": 42}, "text": "/botg"}})

    assert sent
    assert "Bot G lead-bucket report" in sent[0][1]
    assert "Live: orders=36 fills=31 resolved=31 wins=0" in sent[0][1]
    assert "Late cheap: orders=2 fills=2 resolved=1 wins=1" in sent[0][1]
    assert "No live parameter changes" in sent[0][1]


def test_listener_unhalt_dispatch(tmp_db):
    calls = []
    client = TelegramClient(token="tok", allowed_chat_ids=[42])
    client.send = lambda sev, msg: calls.append(("send", sev, msg)) or True

    def unhalt(bot_id: str, reason: str) -> bool:
        calls.append(("unhalt", bot_id, reason))
        return True

    listener = Listener(client=client, unhalt_handler=unhalt)
    # Audit C8: two-step flow. First call stages confirmation (no unhalt yet).
    listener._handle_update({"message": {"chat": {"id": 42}, "text": "/unhalt bot_b"}})
    assert not any(c[0] == "unhalt" for c in calls)
    assert any(c[0] == "send" and "confirm" in c[2].lower() for c in calls)
    # Second call with `confirm` actually dispatches.
    listener._handle_update(
        {"message": {"chat": {"id": 42}, "text": "/unhalt bot_b confirm"}}
    )
    assert any(c[0] == "unhalt" and c[1] == "bot_b" for c in calls)
    assert any(c[0] == "send" for c in calls)


def test_listener_unhalt_accepts_paper_fleet_bot(tmp_db):
    calls = []
    client = TelegramClient(token="tok", allowed_chat_ids=[42])
    client.send = lambda sev, msg: calls.append(("send", sev, msg)) or True

    def unhalt(bot_id: str, reason: str) -> bool:
        calls.append(("unhalt", bot_id, reason))
        return True

    listener = Listener(client=client, unhalt_handler=unhalt)
    listener._handle_update({"message": {"chat": {"id": 42}, "text": "/unhalt bot_d"}})
    listener._handle_update(
        {"message": {"chat": {"id": 42}, "text": "/unhalt bot_d confirm"}}
    )

    assert any(c[0] == "unhalt" and c[1] == "bot_d" for c in calls)
