from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from core.db import (
    Book,
    Event,
    HaltFlag,
    Market,
    Order,
    PnlSnapshot,
    Position,
    Score,
    Trade,
    get_session_factory,
)


def seed_dashboard_db() -> None:
    session_factory = get_session_factory()
    now = datetime.now(UTC)
    with session_factory() as session:
        session.add_all(
            [
                Market(
                    condition_id="mkt-a",
                    category="geopolitics",
                    question="Will Bot A tail market miss resolution?",
                    fee_rate_bps=0,
                    yes_token_id="yes-a",
                    no_token_id="no-a",
                    volume_24h_usd=Decimal("20000"),
                    yes_price=Decimal("0.04"),
                    end_date=now + timedelta(days=45),
                    last_updated=now,
                ),
                Market(
                    condition_id="mkt-b",
                    category="politics",
                    question="Will Bot B signal market resolve YES?",
                    fee_rate_bps=40,
                    yes_token_id="yes-b",
                    no_token_id="no-b",
                    volume_24h_usd=Decimal("50000"),
                    yes_price=Decimal("0.55"),
                    end_date=now + timedelta(days=30),
                    last_updated=now,
                ),
                Book(
                    token_id="yes-a",
                    snapshot_at=now,
                    bids=[[0.03, 5000]],
                    asks=[[0.04, 5000]],
                ),
                Book(
                    token_id="no-a",
                    snapshot_at=now,
                    bids=[[0.95, 5000]],
                    asks=[[0.96, 1000]],
                ),
                Book(
                    token_id="yes-b",
                    snapshot_at=now,
                    bids=[[0.53, 5000]],
                    asks=[[0.55, 5000]],
                ),
                Book(
                    token_id="no-b",
                    snapshot_at=now,
                    bids=[[0.44, 5000]],
                    asks=[[0.45, 5000]],
                ),
                Score(
                    condition_id="mkt-b",
                    scored_at=now,
                    dispute_risk=Decimal("0.10"),
                    claude_pick="YES",
                    claude_confidence=Decimal("0.90"),
                    claude_implied_prob=Decimal("0.75"),
                    resolution_prediction="YES",
                    model_version="test",
                ),
                Order(
                    order_id="ord-a",
                    bot_id="bot_a",
                    condition_id="mkt-a",
                    token_id="no-a",
                    side="BUY",
                    price=Decimal("0.96"),
                    size=Decimal("30"),
                    status="OPEN",
                    placed_at=now,
                    last_updated=now,
                ),
                Order(
                    order_id="ord-b",
                    bot_id="bot_b",
                    condition_id="mkt-b",
                    token_id="yes-b",
                    side="BUY",
                    price=Decimal("0.55"),
                    size=Decimal("25"),
                    status="FILLED",
                    placed_at=now - timedelta(minutes=5),
                    last_updated=now,
                ),
                Trade(
                    trade_id="trd-b-buy",
                    bot_id="bot_b",
                    order_id="ord-b",
                    condition_id="mkt-b",
                    token_id="yes-b",
                    side="BUY",
                    price=Decimal("0.45"),
                    size=Decimal("10"),
                    fee_usd=Decimal("0"),
                    filled_at=now - timedelta(days=2),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("3.60"),
                ),
                Trade(
                    trade_id="trd-b-sell",
                    bot_id="bot_b",
                    order_id="ord-b",
                    condition_id="mkt-b",
                    token_id="yes-b",
                    side="SELL",
                    price=Decimal("0.60"),
                    size=Decimal("10"),
                    fee_usd=Decimal("0"),
                    filled_at=now - timedelta(days=1),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("4.80"),
                ),
                Position(
                    bot_id="bot_a",
                    condition_id="mkt-a",
                    token_id="no-a",
                    side="NO",
                    size=Decimal("30"),
                    avg_price=Decimal("0.96"),
                    cost_basis_usd=Decimal("28.80"),
                    status="OPEN",
                    opened_at=now,
                ),
                Position(
                    bot_id="bot_b",
                    condition_id="mkt-b",
                    token_id="yes-b",
                    side="YES",
                    size=Decimal("25"),
                    avg_price=Decimal("0.55"),
                    cost_basis_usd=Decimal("13.75"),
                    status="OPEN",
                    opened_at=now,
                ),
                Event(
                    bot_id="bot_a",
                    event_type="bot_a.tick",
                    severity="warn",
                    message="Book aged past threshold",
                    payload={"age_s": 301},
                    created_at=now,
                ),
                Event(
                    bot_id="bot_b",
                    event_type="watchdog.kill",
                    severity="kill",
                    message="Aggregate exposure breached cap",
                    payload={"cap": 1000},
                    created_at=now - timedelta(minutes=2),
                ),
                Event(
                    bot_id="crypto_probability_gap_paper",
                    event_type="crypto_fair_value.signal",
                    severity="info",
                    message="probability gap UP signal",
                    payload={
                        "strategy": "probability_gap",
                        "condition_id": "crypto-cond-1",
                        "symbol": "BTC",
                        "duration_minutes": 5,
                        "side": "UP",
                        "token_id": "crypto-yes-1",
                        "ask_price": "0.40",
                        "model_probability_up": 0.53,
                        "model_edge": "0.13",
                        "pm_mid_up": "0.39",
                        "effective_spread": "0.02",
                        "top_depth_usd": "80",
                        "seconds_left": 60,
                        "decision_ms": int(now.timestamp() * 1000),
                        "cex_move_60s": 0.001,
                        "question": "Bitcoin Up or Down - test",
                        "main_fill_track": "paper_taker_stressed_1c",
                        "lead_bucket": "45s-120s",
                        "probability_bucket": "50-60%",
                        "ask_bucket": "40-45c",
                        "fill_tracks": [
                            {
                                "fill_track": "paper_taker_top",
                                "filled": True,
                                "entry_price": "0.40000000",
                                "size": "12.50000000",
                                "fee_usd": "0.21600000",
                                "stake_usd": "5",
                            },
                            {
                                "fill_track": "paper_taker_stressed_1c",
                                "filled": True,
                                "entry_price": "0.41000000",
                                "size": "12.19512195",
                                "fee_usd": "0.21240000",
                                "stake_usd": "5",
                            },
                            {
                                "fill_track": "paper_taker_stressed_2c",
                                "filled": True,
                                "entry_price": "0.42000000",
                                "size": "11.90476190",
                                "fee_usd": "0.20880000",
                                "stake_usd": "5",
                            },
                        ],
                    },
                    created_at=now,
                ),
                Event(
                    bot_id="crypto_probability_gap_paper",
                    event_type="portfolio.paper_resolve",
                    severity="info",
                    message="crypto paper settled",
                    payload={
                        "condition_id": "crypto-cond-1",
                        "token_id": "crypto-yes-1",
                        "settle_price": "1",
                    },
                    created_at=now + timedelta(minutes=5),
                ),
                Order(
                    order_id="cfv-order-1",
                    bot_id="crypto_probability_gap_paper",
                    condition_id="crypto-cond-1",
                    token_id="crypto-yes-1",
                    side="BUY",
                    price=Decimal("0.41"),
                    size=Decimal("12.19512195"),
                    status="FILLED",
                    order_type="PAPER_TAKER_STRESSED_1C",
                    placed_at=now,
                    last_updated=now,
                ),
                Trade(
                    trade_id="paper-fill-cfv-order-1",
                    bot_id="crypto_probability_gap_paper",
                    order_id="cfv-order-1",
                    condition_id="crypto-cond-1",
                    token_id="crypto-yes-1",
                    side="BUY",
                    price=Decimal("0.41"),
                    size=Decimal("12.19512195"),
                    fee_usd=Decimal("0.2124"),
                    filled_at=now,
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("4.00"),
                ),
                Trade(
                    trade_id="paper-resolve-cfv-1",
                    bot_id="crypto_probability_gap_paper",
                    order_id=None,
                    condition_id="crypto-cond-1",
                    token_id="crypto-yes-1",
                    side="SELL",
                    price=Decimal("1"),
                    size=Decimal("12.19512195"),
                    fee_usd=Decimal("0"),
                    filled_at=now + timedelta(minutes=5),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("9.75"),
                ),
                HaltFlag(
                    bot_id="bot_b",
                    halted=1,
                    reason="aggregate exposure breached",
                    set_at=now,
                ),
                HaltFlag(
                    bot_id="bot_a",
                    halted=0,
                    reason="",
                    set_at=now,
                ),
                PnlSnapshot(
                    bot_id="bot_a",
                    snapshot_date=date.today() - timedelta(days=1),
                    realised_usd=Decimal("5"),
                    unrealised_usd=Decimal("1"),
                    open_exposure_usd=Decimal("25"),
                    drawdown_pct=Decimal("0.10"),
                ),
                PnlSnapshot(
                    bot_id="bot_a",
                    snapshot_date=date.today(),
                    realised_usd=Decimal("7"),
                    unrealised_usd=Decimal("2"),
                    open_exposure_usd=Decimal("28"),
                    drawdown_pct=Decimal("0.08"),
                ),
                PnlSnapshot(
                    bot_id="bot_b",
                    snapshot_date=date.today() - timedelta(days=1),
                    realised_usd=Decimal("2"),
                    unrealised_usd=Decimal("1"),
                    open_exposure_usd=Decimal("14"),
                    drawdown_pct=Decimal("0.04"),
                ),
                PnlSnapshot(
                    bot_id="bot_b",
                    snapshot_date=date.today(),
                    realised_usd=Decimal("3"),
                    unrealised_usd=Decimal("2"),
                    open_exposure_usd=Decimal("16"),
                    drawdown_pct=Decimal("0.03"),
                ),
            ]
        )
        session.commit()


def seed_bot_c_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE pyth_ticks_recent (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              endpoint TEXT NOT NULL,
              ts_ms INTEGER NOT NULL,
              feed_id INTEGER NOT NULL,
              price NUMERIC,
              bid NUMERIC,
              ask NUMERIC
            );
            CREATE TABLE pyth_bars_pro (
              ts TEXT NOT NULL,
              feed_id INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              open NUMERIC NOT NULL,
              high NUMERIC NOT NULL,
              low NUMERIC NOT NULL,
              close NUMERIC NOT NULL,
              bid NUMERIC,
              ask NUMERIC,
              confidence NUMERIC,
              publisher_count INTEGER,
              market_session TEXT,
              tick_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE pyth_bars_hermes (
              ts TEXT NOT NULL,
              feed_id INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              open NUMERIC NOT NULL,
              high NUMERIC NOT NULL,
              low NUMERIC NOT NULL,
              close NUMERIC NOT NULL,
              bid NUMERIC,
              ask NUMERIC,
              confidence NUMERIC,
              publisher_count INTEGER,
              market_session TEXT,
              tick_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE bot_c_decisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              decided_at TEXT NOT NULL,
              gamma_id TEXT NOT NULL,
              slug TEXT NOT NULL,
              question TEXT NOT NULL,
              symbol TEXT NOT NULL,
              direction TEXT NOT NULL,
              strike_low NUMERIC,
              strike_high NUMERIC,
              resolution_date TEXT NOT NULL,
              spot_price NUMERIC NOT NULL,
              annualised_vol NUMERIC NOT NULL,
              hours_to_resolution NUMERIC NOT NULL,
              model_p_yes NUMERIC NOT NULL,
              market_p_yes NUMERIC NOT NULL,
              edge NUMERIC NOT NULL,
              side TEXT NOT NULL,
              reason TEXT NOT NULL,
              yes_token_id TEXT NOT NULL,
              no_token_id TEXT NOT NULL,
              volume_24h_usd NUMERIC
            );
            """
        )
        now = datetime.now(UTC)
        conn.execute(
            "INSERT INTO pyth_ticks_recent(endpoint, ts_ms, feed_id, price, bid, ask) VALUES (?, ?, ?, ?, ?, ?)",
            ("pro", int(now.timestamp() * 1000), 1, 3200.0, 3199.5, 3200.5),
        )
        for minutes, close in ((10, 3190.0), (5, 3205.0), (0, 3200.0)):
            ts = (now - timedelta(minutes=minutes)).replace(microsecond=0).isoformat()
            conn.execute(
                "INSERT INTO pyth_bars_pro(ts, feed_id, symbol, open, high, low, close, bid, ask, confidence, publisher_count, market_session, tick_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, 1, "ETHUSD", close - 2, close + 1, close - 3, close, close - 0.5, close + 0.5, 0.2, 16, "open", 8),
            )
        conn.execute(
            "INSERT INTO bot_c_decisions(decided_at, gamma_id, slug, question, symbol, direction, strike_low, strike_high, resolution_date, spot_price, annualised_vol, hours_to_resolution, model_p_yes, market_p_yes, edge, side, reason, yes_token_id, no_token_id, volume_24h_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                now.isoformat(),
                "gamma-1",
                "eth-above-3200",
                "Will ETH close above 3200?",
                "ETHUSD",
                "above",
                3200.0,
                None,
                (now + timedelta(hours=18)).isoformat(),
                3200.0,
                0.45,
                18.0,
                0.61,
                0.48,
                0.13,
                "BUY_YES",
                "positive edge",
                "yes-eth",
                "no-eth",
                125000.0,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def running_dashboard(monkeypatch, bot_c_db: Path):
    from dashboard import runtime_queries, server

    runtime_queries._balance_cache["ts"] = 0.0
    runtime_queries._balance_cache["value"] = None
    monkeypatch.setenv("BOT_C_DB_PATH", str(bot_c_db))
    # Audit C23 removed the hardcoded wallet default; provide one explicitly here.
    monkeypatch.setenv("POLYMARKET_WALLET", "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    monkeypatch.setattr(
        runtime_queries,
        "_fetch_balances_uncached",
        lambda: {"pol": "31.8300", "usdce": "812.44", "fetched_at": datetime.now(UTC).isoformat()},
    )
    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {
            "polymarket-bot-c": "failed",
            "polymarket-bot-d": "active",
            "polymarket-bot-e-recorder": "active",
            "polymarket-bot-g-prime": "active",
            "polymarket-bot-g-prime-live": "active",
            "polymarket-bot-g-prime-shadow": "active",
            "polymarket-bot-g-prime-late-cheap": "active",
            "polymarket-bot-g-lead-bucket-roi-report": "timer:active",
            "polymarket-bot-d-spike": "vps:active",
            "polymarket-bot-d-spike-short-vps": "vps:active",
            "polymarket-bot-h-maker-v2-recorder": "active",
            "polymarket-wallet-observer": "active",
            "polymarket-crypto-prob-gap-paper": "active",
            "polymarket-crypto-brownian-fv-paper": "inactive",
        },
    )

    app = server.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{app.server_port}"
    finally:
        app.shutdown()
        app.server_close()
        thread.join(timeout=2)


def read_json(base_url: str, path: str) -> dict:
    with urlopen(f"{base_url}{path}") as response:
        return json.loads(response.read().decode("utf-8"))


def read_text(base_url: str, path: str) -> str:
    with urlopen(f"{base_url}{path}") as response:
        return response.read().decode("utf-8")


@pytest.fixture
def dashboard_server(tmp_db, tmp_path, monkeypatch):
    seed_dashboard_db()
    bot_c_db = tmp_path / "bot_c.db"
    seed_bot_c_db(bot_c_db)
    with running_dashboard(monkeypatch, bot_c_db) as base_url:
        yield base_url


def test_dashboard_shell_serves_tabs_and_safe_assets(dashboard_server):
    html = read_text(dashboard_server, "/")
    js = read_text(dashboard_server, "/app.js")

    # Cockpit shell loads with the redesigned tab labels.
    assert "Overview" in html
    # No archived/parked/retired bot identities in the operator surface.
    assert "Tail Fade (A)" not in html
    assert "Whale Sensor (F)" not in html
    assert "LLM Directional (B)" not in html
    assert "Pyth Directional (C)" not in html
    # Active drilldown tabs.
    assert ">Weather D<" in html
    assert ">Longshot G<" in html
    assert ">Wallets<" in html
    assert ">Orders<" in html
    assert ">Events<" in html
    # The Recorders tab was removed in the cockpit cleanup — recorder health
    # is summarised on the Overview's Active Recorders table.
    assert ">Recorders<" not in html
    assert ">Crypto FV Paper<" not in html
    assert ">Crypto Recorder (E)<" not in html
    assert ">Maker Recorder (H)<" not in html
    # Safety: no auto-refresh redirects, module-loaded JS only.
    assert '<meta http-equiv="refresh"' not in html
    assert 'type="module" src="/app.js"' in html
    # JS has the severity classifier and avoids innerHTML.
    assert "SEVERITY_CLASS" in js
    assert "warn" in js and "kill" in js
    assert "innerHTML" not in js
    # Archived bots have no API surface.
    assert "/api/bot-a" not in js
    assert "/api/bot-b" not in js
    assert "/api/bot-c" not in js
    assert "/api/bot-f" not in js
    # Active drilldown endpoints. /api/bot-e and /api/bot-h still exist
    # server-side for scripts/reports, but the dashboard does not fetch
    # them anymore (recorder health is on Overview's Active Recorders).
    assert "/api/bot-d" in js
    assert "/api/bot-g" in js
    assert "/api/wallet-observer" in js
    assert "/api/crypto-fair-value" not in js
    # Bot E / Bot H endpoints exist server-side but the dashboard no
    # longer fetches them; they are referenced only in a comment.
    assert "Bot E" in js or "/api/bot-e" not in js  # comment-only allowed
    assert "Bot H" in js or "/api/bot-h" not in js  # comment-only allowed


def test_dashboard_cockpit_revert_sentinels(dashboard_server):
    """Regression guard against the pre-cockpit dashboard sneaking back.

    The 2026-05-10 cockpit redesign (commit 4f066bd) replaced the legacy
    7-tab "Trading Performance" layout with the Bloomberg-style operator
    cockpit. Subsequent feature branches (notably bot-i-live-promotion in
    2026-05-14 commit 89f93aa) were authored against the pre-cockpit layout
    and silently re-introduced "Persistence Live (I)", "Crypto Fair Value",
    "Orders & Positions", and "Events & Health" tabs when merged or rsynced.

    This test guards both files: any reappearance of the legacy DOM markers
    or tab labels fails CI before a deploy. If the cockpit is being
    intentionally retired, update this test in the same commit.
    """
    html = read_text(dashboard_server, "/")
    js = read_text(dashboard_server, "/app.js")

    # Cockpit DOM markers must be present.
    assert 'class="rail"' in html, "Cockpit status rail missing from index.html"
    assert "POLYMARKET COCKPIT" in html
    assert 'id="rail-cells"' in html
    assert "DO NOT REVERT" in html, (
        "Sentinel comment was stripped from index.html. If you intentionally "
        "rewrote the dashboard shell, update this test in the same commit."
    )
    assert "DO NOT REVERT" in js, (
        "Sentinel comment was stripped from app.js. Same rule as above."
    )

    # Legacy pre-cockpit markers must NOT be present.
    assert "Trading Performance" not in html, (
        "Pre-cockpit <h1>Trading Performance</h1> regressed into index.html. "
        "See the sentinel comment at the top of index.html."
    )
    assert "Polymarket operator dashboard" not in html, (
        "Pre-cockpit eyebrow 'Polymarket operator dashboard' regressed."
    )
    assert 'class="topbar"' not in html, "Pre-cockpit .topbar header regressed."
    assert 'class="mode-pill"' not in html, "Pre-cockpit .mode-pill regressed."

    # Legacy tab labels must NOT appear in the rendered HTML.
    forbidden_tabs = (
        ">Persistence Live (I)<",
        ">Crypto Fair Value<",
        ">Orders &amp; Positions<",
        ">Events &amp; Health<",
        ">Weather Fade (D)<",
        ">Longshot Prime (G)<",
    )
    for marker in forbidden_tabs:
        assert marker not in html, (
            f"Legacy tab label {marker!r} regressed in index.html. "
            "Cockpit uses short labels (Weather D, Longshot G, etc.) and "
            "surfaces bot I / J / K / L / crypto FV as inventory rows on "
            "Overview — never as separate tabs."
        )


def test_overview_endpoint_contract(dashboard_server):
    payload = read_json(dashboard_server, "/api/overview")

    assert payload["mode"] == "paper"
    assert payload["wallet"]["display"].startswith("0x5359")
    assert payload["wallet"]["full"] is None
    assert payload["services_summary"] == {"active": 12, "degraded": 2}
    assert payload["event_severity_7d"]["warn"] == 1
    assert payload["event_severity_7d"]["kill"] == 1
    assert payload["project_history"] == []
    assert payload["balances"] == {}
    assert payload["performance"]["total_pnl_usd"] == pytest.approx(0.0)
    assert payload["performance"]["paper_amount_usd"] == pytest.approx(0.0)
    assert payload["performance"]["trades"] == 0
    # Risk strip is a structured cockpit summary: lists of degraded
    # services / active halts plus an active-row count. Active services
    # in the test fixture are healthy so both lists are empty.
    assert payload["risk"]["degraded_services"] == []
    assert payload["risk"]["active_halts"] == []
    assert payload["risk"]["active_count"] == len(payload["bot_inventory"])
    # Priority alerts surface starts empty; only future ADRs append rows.
    assert payload["priority_alerts"] == []
    assert payload["open_positions"] == []
    assert payload["fleet_epoch"]["id"] == "fleet_epoch_2026_04_30"
    assert payload["vps_node"] == {"configured": False, "ok": False, "status": "not_configured"}
    assert "bot_inventory" in payload
    inventory_ids = {bot["bot_id"] for bot in payload["bot_inventory"]}
    assert "bot_e" in inventory_ids
    assert "bot_h_maker_v2" in inventory_ids
    assert "wallet_observer" in inventory_ids
    assert "crypto_probability_gap_paper" not in inventory_ids
    assert "crypto_brownian_fv_paper" not in inventory_ids
    assert "bot_a" not in inventory_ids
    assert "bot_b" not in inventory_ids
    assert "bot_b_shadow" not in inventory_ids
    assert "bot_f" not in inventory_ids
    assert "bot_f_mirror" not in inventory_ids
    assert {bot["bot_id"] for bot in payload["fleet_bots"]} == {
        "bot_d",
        "bot_d_live_probe",
        "bot_d_maker_live_probe",
        "bot_d_spike",
        "bot_d_station_lock",
        "bot_i_persistence_live",
        "wallet_tag_elite_cap_paper",
        "bot_j_nr_wallet",
        "bot_k_sports_taker",
        "bot_g_prime_live",
        "bot_g_prime",
        "bot_l_complete_set",
        "crypto_probability_gap_live_maker",
        "crypto_brownian_fv_live_maker",
    }
    assert "bot_e" not in {bot["bot_id"] for bot in payload["fleet_bots"]}
    assert "bot_a" not in {bot["bot_id"] for bot in payload["fleet_bots"]}
    assert "bot_b" not in {bot["bot_id"] for bot in payload["fleet_bots"]}
    assert "bot_b_shadow" not in {bot["bot_id"] for bot in payload["fleet_bots"]}
    assert "bot_f_mirror" not in {bot["bot_id"] for bot in payload["fleet_bots"]}


def test_overview_includes_configured_vps_node_status(tmp_db, tmp_path, monkeypatch):
    seed_dashboard_db()
    bot_c_db = tmp_path / "bot_c.db"
    seed_bot_c_db(bot_c_db)
    status_path = tmp_path / "vps_node_latest.json"
    status_path.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "node": {"hostname": "vps-host", "root": "/home/operator/longshot-research"},
        "disk": {"used_pct": 4.8, "free_bytes": 73127272448},
        "tailscale": {
            "ipv4": "192.0.2.1",
            "status": {"BackendState": "Running"},
        },
        "services": {
            "ssh.service": {"active": "active", "enabled": "enabled"},
            "ssh.socket": {"active": "active", "enabled": "enabled"},
            "tailscaled.service": {"active": "active", "enabled": "enabled"},
            "longshot-vps-node-status.timer": {"active": "active", "enabled": "enabled"},
            "polymarket-bot-d-spike.service": {"active": "active", "enabled": "enabled"},
            "polymarket-bot-d-spike-daily-report-vps.timer": {"active": "active", "enabled": "enabled"},
        },
        "databases": {
            "recorder_canary": {
                "counts": {
                    "pm_events": 230888,
                    "cex_trades": 513179,
                    "gaps": 0,
                },
            },
        },
        "bot_d_spike": {
            "bot_id": "bot_d_spike",
            "orders": {"total_orders": 3, "open_orders": 1, "paper_open_orders": 1},
            "trades": {"filled_trades_count": 2, "settlement_fills_count": 1},
            "open_positions": 1,
            "open_cost_basis_usd": 1.5,
            "recent_entries": [],
        },
    }))
    monkeypatch.setenv("VPS_NODE_STATUS_PATH", str(status_path))

    with running_dashboard(monkeypatch, bot_c_db) as base_url:
        payload = read_json(base_url, "/api/overview")

    assert payload["vps_node"]["configured"] is True
    assert payload["vps_node"]["ok"] is True
    assert payload["vps_node"]["status"] == "healthy"
    assert payload["vps_node"]["tailscale"] == {"state": "Running", "ipv4": "192.0.2.1"}
    assert payload["vps_node"]["databases"]["recorder_canary"]["counts"]["pm_events"] == 230888
    assert payload["vps_node"]["services"]["polymarket-bot-d-spike.service"]["active"] == "active"
    assert payload["vps_node"]["bot_d_spike"]["orders"]["total_orders"] == 3


def test_bot_d_endpoint_uses_vps_bot_d_spike_summary(tmp_db, tmp_path, monkeypatch):
    seed_dashboard_db()
    status_path = tmp_path / "vps_node_latest.json"
    status_path.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "node": {"hostname": "vps-host", "root": "/home/operator/longshot-research"},
        "disk": {"used_pct": 5.0, "free_bytes": 70000000000},
        "tailscale": {
            "ipv4": "192.0.2.1",
            "status": {"BackendState": "Running"},
        },
        "services": {
            "ssh.service": {"active": "active", "enabled": "enabled"},
            "ssh.socket": {"active": "active", "enabled": "enabled"},
            "tailscaled.service": {"active": "active", "enabled": "enabled"},
            "longshot-vps-node-status.timer": {"active": "active", "enabled": "enabled"},
            "polymarket-bot-d-spike.service": {"active": "active", "enabled": "enabled"},
            "polymarket-bot-d-spike-daily-report-vps.timer": {"active": "active", "enabled": "enabled"},
        },
        "databases": {},
        "bot_d_spike": {
            "bot_id": "bot_d_spike",
            "orders": {
                "total_orders": 4,
                "open_orders": 1,
                "paper_open_orders": 1,
                "reserved_notional_usd": 2.0,
            },
            "trades": {
                "filled_trades_count": 3,
                "trade_rows_count": 4,
                "paper_fills_count": 3,
                "settlement_fills_count": 1,
                "realised_pnl_usd": 0.5,
                "recent_trades": [],
            },
            "open_positions": 1,
            "open_cost_basis_usd": 1.5,
            "recent_entries": [
                {
                    "created_at": "2026-05-07T17:20:00+00:00",
                    "city": "Shenzhen",
                    "bucket": "28C_or_above",
                    "best_ask": "0.05",
                    "hours_to_resolution": "8.5",
                }
            ],
        },
    }))
    monkeypatch.setenv("VPS_NODE_STATUS_PATH", str(status_path))

    from dashboard import runtime_queries

    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {
            "polymarket-bot-d": "active",
            "polymarket-bot-d-live": "active",
            "polymarket-bot-d-spike": "vps:active",
        },
    )

    payload = runtime_queries.query_bot_d()

    assert payload["spike"]["data_source"] == "vps"
    assert payload["spike"]["simple"]["services"]["polymarket-bot-d-spike"] == "vps:active"
    assert payload["spike"]["simple"]["pnl_usd"] == 0.5
    assert payload["spike"]["simple"]["fills"] == 3
    assert payload["spike"]["simple"]["settlement_fills"] == 1
    assert payload["spike"]["simple"]["open_positions"] == 1
    assert payload["spike"]["simple"]["open_position_cost_usd"] == 1.5
    assert payload["spike"]["order_metrics"]["total_orders"] == 4
    assert payload["spike"]["trade_metrics"]["filled_trades_count"] == 3
    assert payload["spike"]["open_positions"] == 1
    assert payload["spike"]["recent_entries"][0]["city"] == "Shenzhen"
    assert payload["spike"]["validation"]["paper_only"] is False
    assert payload["spike"]["validation"]["tiny_live_probe"] is True
    assert payload["spike"]["entry_band"] == "1c-15c"
    assert payload["spike"]["ttr_window"] == "6h-12h"
    assert payload["spike"]["daily_entry_cap"] == 5
    assert payload["spike"]["daily_gross_cap_usd"] == 10


def test_bot_d_endpoint_includes_spike_short_block(tmp_db, tmp_path, monkeypatch):
    seed_dashboard_db()
    status_path = tmp_path / "vps_node_latest.json"
    status_path.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "node": {"hostname": "vps-host", "root": "/home/operator/longshot-research"},
        "disk": {"used_pct": 5.0, "free_bytes": 70000000000},
        "tailscale": {
            "ipv4": "192.0.2.1",
            "status": {"BackendState": "Running"},
        },
        "services": {
            "ssh.service": {"active": "active", "enabled": "enabled"},
            "ssh.socket": {"active": "active", "enabled": "enabled"},
            "tailscaled.service": {"active": "active", "enabled": "enabled"},
            "longshot-vps-node-status.timer": {"active": "active", "enabled": "enabled"},
            "polymarket-bot-d-spike-short-vps.service": {"active": "active", "enabled": "enabled"},
        },
        "databases": {},
        "bot_d_spike_short": {
            "bot_id": "bot_d_spike_short",
            "orders": {
                "total_orders": 7,
                "open_orders": 2,
                "paper_open_orders": 2,
                "reserved_notional_usd": 4.0,
            },
            "trades": {
                "filled_trades_count": 5,
                "trade_rows_count": 6,
                "paper_fills_count": 5,
                "settlement_fills_count": 2,
                "realised_pnl_usd": 1.25,
                "recent_trades": [],
            },
            "open_positions": 2,
            "open_cost_basis_usd": 4.0,
            "recent_entries": [
                {
                    "created_at": "2026-05-08T20:01:00+00:00",
                    "city": "Hong Kong",
                    "bucket": "30C_or_above",
                    "best_ask": "0.06",
                    "hours_to_resolution": "2.5",
                }
            ],
        },
    }))
    monkeypatch.setenv("VPS_NODE_STATUS_PATH", str(status_path))

    from dashboard import runtime_queries

    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {
            "polymarket-bot-d": "active",
            "polymarket-bot-d-live": "active",
            "polymarket-bot-d-spike-short-vps": "vps:active",
        },
    )

    payload = runtime_queries.query_bot_d()

    assert "spike_short" in payload
    assert payload["spike_short"]["bot_id"] == "bot_d_spike_short"
    assert payload["spike_short"]["data_source"] == "vps"
    assert payload["spike_short"]["strategy"] == "Strategy E2"
    assert payload["spike_short"]["entry_band"] == "1c-15c"
    assert payload["spike_short"]["ttr_window"] == "0h-6h"
    assert payload["spike_short"]["daily_entry_cap"] == 30
    assert payload["spike_short"]["validation"]["paper_only"] is True
    assert payload["spike_short"]["simple"]["pnl_usd"] == 1.25
    assert payload["spike_short"]["simple"]["fills"] == 5
    assert payload["spike_short"]["simple"]["settlement_fills"] == 2
    assert payload["spike_short"]["simple"]["open_positions"] == 2
    assert payload["spike_short"]["simple"]["open_position_cost_usd"] == 4.0
    assert payload["spike_short"]["order_metrics"]["total_orders"] == 7
    assert payload["spike_short"]["trade_metrics"]["filled_trades_count"] == 5
    assert payload["spike_short"]["open_positions"] == 2
    assert payload["spike_short"]["recent_entries"][0]["city"] == "Hong Kong"


def test_bot_g_uses_vps_summary_when_paper_service_is_remote(tmp_db, tmp_path, monkeypatch):
    seed_dashboard_db()
    status_path = tmp_path / "vps_node_latest.json"
    status_path.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "node": {"hostname": "vps-host", "root": "/home/operator/longshot-research"},
        "disk": {"used_pct": 4.9, "free_bytes": 73127272448},
        "tailscale": {
            "ipv4": "192.0.2.1",
            "status": {"BackendState": "Running"},
        },
        "services": {
            "ssh.service": {"active": "active", "enabled": "enabled"},
            "ssh.socket": {"active": "active", "enabled": "enabled"},
            "tailscaled.service": {"active": "active", "enabled": "enabled"},
            "longshot-vps-node-status.timer": {"active": "active", "enabled": "enabled"},
            "polymarket-bot-g-prime.service": {"active": "active", "enabled": "enabled"},
            "polymarket-bot-g-prime-shadow.service": {"active": "active", "enabled": "enabled"},
        },
        "databases": {},
        "bot_g": {
            "bot_ids": [
                "bot_g_prime",
                "bot_g_prime_shadow",
                "bot_g_prime_late_cheap",
                "bot_g_prime_take_profit",
            ],
            "order_metrics": {
                "bot_g_prime": {"total_orders": 101, "open_orders": 2, "paper_open_orders": 2},
                "bot_g_prime_shadow": {"total_orders": 12, "open_orders": 0},
            },
            "trade_metrics": {
                "bot_g_prime": {
                    "entry_cost_usd": 30.0,
                    "closed_trades": 3,
                    "wins": 1,
                    "filled_trades_count": 200,
                    "trade_rows_count": 202,
                    "paper_fills_count": 200,
                    "live_fills_count": 0,
                    "settlement_fills_count": 2,
                    "realised_pnl_usd": 12.34,
                    "recent_trades": [],
                },
                "bot_g_prime_shadow": {
                    "entry_cost_usd": 2.0,
                    "closed_trades": 2,
                    "wins": 1,
                    "filled_trades_count": 24,
                    "trade_rows_count": 24,
                    "paper_fills_count": 24,
                    "live_fills_count": 0,
                    "settlement_fills_count": 0,
                    "realised_pnl_usd": 0,
                    "recent_trades": [],
                },
            },
            "paper_pnl": {
                "bot_g_prime": {
                    "capital_deployed": 7.5,
                    "max_profit": 92.5,
                    "max_loss": 7.5,
                    "open_count": 2,
                    "avg_entry": 0.075,
                },
            },
            "runtime_state": {
                "bot_g_prime": {
                    "available": True,
                    "source": "vps_trader_event",
                    "bot_env": "paper",
                    "bot_dry_run": True,
                    "global_polymarket_env": "paper",
                    "effective_paper": True,
                },
            },
            "recent_orders": {
                "bot_g_prime": [{"order_id": "paper-vps-1", "bot_id": "bot_g_prime"}],
            },
            "positions_open": {
                "bot_g_prime": [{"condition_id": "cond-vps", "bot_id": "bot_g_prime"}],
            },
        },
    }))
    monkeypatch.setenv("VPS_NODE_STATUS_PATH", str(status_path))

    from dashboard import runtime_queries

    payload = runtime_queries.query_bot_g()

    assert payload["trader"]["data_source"] == "vps"
    assert payload["trader"]["order_metrics"]["total_orders"] == 101
    assert payload["trader"]["trade_metrics"]["filled_trades_count"] == 200
    assert payload["trader"]["runtime_state"]["source"] == "vps_trader_event"
    assert payload["trader"]["orders_recent"][0]["order_id"] == "paper-vps-1"
    assert payload["fleet_bots"][1]["data_source"] == "vps"
    assert payload["fleet_bots"][1]["trades"] == 101
    assert payload["fleet_bots"][1]["pnl_usd"] == 12.34
    assert payload["lead_bucket_report"]["data_source"] == "vps_status"
    prime_row = next(row for row in payload["lead_bucket_report"]["rows"] if row["bot_id"] == "bot_g_prime")
    assert prime_row["orders"] == 101
    assert prime_row["resolved"] == 3
    assert prime_row["roi_pct"] == 41.13
    shadow = next(row for row in payload["research_shadows"] if row["bot_id"] == "bot_g_prime_shadow")
    assert shadow["simple"]["services"]["polymarket-bot-g-prime-shadow"] == "vps:active"
    assert shadow["data_source"] == "vps"
    assert shadow["simple"]["trades"] == 12
    assert shadow["trade_metrics"]["filled_trades_count"] == 24


def test_event_severity_counts_fails_soft_on_sqlite_io_error(monkeypatch):
    from dashboard import runtime_queries

    @contextmanager
    def broken_db():
        raise sqlite3.OperationalError("disk I/O error")
        yield  # pragma: no cover

    monkeypatch.setattr(runtime_queries, "_db", broken_db)

    assert runtime_queries._event_severity_counts() == {"info": 0, "warn": 0, "kill": 0}


def test_bot_endpoints_include_candidate_and_position_data(dashboard_server):
    bot_g = read_json(dashboard_server, "/api/bot-g")

    with pytest.raises(HTTPError) as bot_a_error:
        read_json(dashboard_server, "/api/bot-a")
    assert bot_a_error.value.code == 404
    with pytest.raises(HTTPError) as bot_b_error:
        read_json(dashboard_server, "/api/bot-b")
    assert bot_b_error.value.code == 404
    with pytest.raises(HTTPError) as bot_f_error:
        read_json(dashboard_server, "/api/bot-f")
    assert bot_f_error.value.code == 404
    with pytest.raises(HTTPError) as crypto_error:
        read_json(dashboard_server, "/api/crypto-fair-value")
    assert crypto_error.value.code == 404

    assert {bot["bot_id"] for bot in bot_g["fleet_bots"]} == {
        "bot_g_prime",
        "bot_g_prime_live",
    }
    live_bot = next(bot for bot in bot_g["fleet_bots"] if bot["bot_id"] == "bot_g_prime_live")
    assert live_bot["status"] == "active"
    assert live_bot["label"] == "Longshot Prime Live (G)"
    assert "pnl_note" in bot_g["fleet_bots"][0]
    assert bot_g["paper_validation"]["collection_band"] == "4c-8c"
    assert bot_g["paper_validation"]["positive_signal_band"] == "4c-5c"
    assert bot_g["trader"]["live_probe"]["status"] == "paper_observing"
    assert bot_g["trader"]["live_probe"]["approval_required"] is True
    assert bot_g["trader"]["live_probe"]["does_not_authorize_live"] is True
    assert bot_g["trader"]["live_probe"]["proposed_live_wallet_usd"] == 200.0
    assert bot_g["trader"]["live_probe"]["proposed_starting_trade_usd"] == 1.0
    assert bot_g["trader"]["live_probe"]["proposed_starting_trade_wallet_pct"] == 0.5
    assert bot_g["live_trader"]["live_probe"]["proposed_daily_entry_cap"] == 20
    assert bot_g["trader"]["live_probe"]["proposed_gross_notional_cap_usd"] == 100.0
    assert bot_g["trader"]["live_probe"]["proposed_gross_notional_wallet_pct"] == 50.0
    assert bot_g["trader"]["live_probe"]["proposed_max_open_positions"] == 10
    assert bot_g["trader"]["live_probe"]["proposed_max_open_notional_usd"] == 10.0
    assert bot_g["trader"]["live_probe"]["proposed_max_open_wallet_pct"] == 5.0
    assert bot_g["trader"]["live_probe"]["live_probe_active"] is False
    assert bot_g["live_probe"] == bot_g["live_trader"]["live_probe"]
    assert {shadow["bot_id"] for shadow in bot_g["research_shadows"]} == {
        "bot_g_prime_live_maker",
        "bot_g_prime_maker",
        "bot_g_prime_shadow",
        "bot_g_prime_high_tail",
        "bot_g_prime_late_cheap",
        "bot_g_prime_take_profit",
    }
    assert bot_g["lead_bucket_report"]["available"] is False
    assert {row["bot_id"] for row in bot_g["lead_bucket_report"]["rows"]} == {
        "bot_g_prime_live",
        "bot_g_prime_live_maker",
        "bot_g_prime",
        "bot_g_prime_maker",
        "bot_g_prime_shadow",
        "bot_g_prime_high_tail",
        "bot_g_prime_late_cheap",
        "bot_g_prime_take_profit",
    }
    assert {bot["bot_id"] for bot in bot_g["archived_variants"]} == {
        "bot_g",
        "bot_g_jackpot",
        "bot_g_scalp",
    }


def test_bot_g_live_summary_separates_orders_fills_and_settlements(dashboard_server):
    # ADR-149 resets Bot G live dashboard metrics at 2026-05-10 16:28 UTC.
    # Keep this synthetic sample wholly inside the active epoch.
    now = datetime(2026, 5, 10, 17, 30, tzinfo=UTC)
    with get_session_factory()() as session:
        session.add_all(
            [
                Order(
                    order_id=f"live-order-{idx}",
                    bot_id="bot_g_prime_live",
                    condition_id=f"mkt-live-{idx}",
                    token_id=f"token-live-{idx}",
                    side="BUY",
                    price=Decimal("0.04"),
                    size=Decimal("25"),
                    status="FILLED",
                    placed_at=now - timedelta(minutes=idx),
                    last_updated=now - timedelta(minutes=idx),
                )
                for idx in range(4)
            ]
            + [
                Order(
                    order_id=f"closed-order-{idx}",
                    bot_id="bot_g_prime_live",
                    condition_id=f"mkt-closed-{idx}",
                    token_id=f"token-closed-{idx}",
                    side="BUY",
                    price=Decimal("0.04"),
                    size=Decimal("25"),
                    status="EXCHANGE_CLOSED",
                    placed_at=now - timedelta(minutes=10 + idx),
                    last_updated=now - timedelta(minutes=10 + idx),
                )
                for idx in range(2)
            ]
            + [
                Trade(
                    trade_id=f"live-fill-{idx}",
                    bot_id="bot_g_prime_live",
                    order_id=f"live-order-{idx}",
                    condition_id=f"mkt-live-{idx}",
                    token_id=f"token-live-{idx}",
                    side="BUY",
                    price=Decimal("0.04"),
                    size=Decimal("25"),
                    fee_usd=Decimal("0"),
                    filled_at=now - timedelta(minutes=idx),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("0.80"),
                )
                for idx in range(4)
            ]
            + [
                Trade(
                    trade_id=f"paper-resolve-{idx}",
                    bot_id="bot_g_prime_live",
                    order_id=None,
                    condition_id=f"mkt-live-{idx}",
                    token_id=f"token-live-{idx}",
                    side="SELL",
                    price=Decimal("0"),
                    size=Decimal("25"),
                    fee_usd=Decimal("0"),
                    filled_at=now - timedelta(minutes=20 + idx),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("0"),
                )
                for idx in range(3)
            ]
            + [
                Position(
                    bot_id="bot_g_prime_live",
                    condition_id="mkt-open-live",
                    token_id="token-open-live",
                    side="YES",
                    size=Decimal("100"),
                    avg_price=Decimal("0.04"),
                    cost_basis_usd=Decimal("4.00"),
                    status="OPEN",
                    opened_at=now,
                )
            ]
        )
        session.commit()

    bot_g = read_json(dashboard_server, "/api/bot-g")
    live_bot = next(bot for bot in bot_g["fleet_bots"] if bot["bot_id"] == "bot_g_prime_live")

    assert live_bot["trades"] == 6
    assert live_bot["fills"] == 4
    assert live_bot["settlement_fills"] == 3
    assert live_bot["trade_rows"] == 7
    assert live_bot["open_positions"] == 1
    assert live_bot["open_position_cost_usd"] == 4.0
    assert bot_g["live_trader"]["trade_metrics"]["filled_trades_count"] == 4
    assert bot_g["live_trader"]["trade_metrics"]["settlement_fills_count"] == 3
    assert bot_g["live_trader"]["trade_metrics"]["trade_rows_count"] == 7


def test_bot_d_endpoint_includes_paper_epoch(dashboard_server):
    with get_session_factory()() as session:
        now = datetime.now(UTC)
        session.add_all(
            [
                Trade(
                    trade_id="paper-fill-bot-d",
                    bot_id="bot_d",
                    order_id=None,
                    condition_id="mkt-d",
                    token_id="yes-d",
                    side="BUY",
                    price=Decimal("0.20"),
                    size=Decimal("25"),
                    fee_usd=Decimal("0"),
                    filled_at=now - timedelta(minutes=30),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("4.00"),
                ),
                Order(
                    order_id="live-buy-order",
                    bot_id="bot_d_live_probe",
                    condition_id="mkt-d-closed-live",
                    token_id="yes-d-closed-live",
                    side="BUY",
                    price=Decimal("0.50"),
                    size=Decimal("5"),
                    status="FILLED",
                    placed_at=now - timedelta(minutes=21),
                    last_updated=now - timedelta(minutes=20),
                ),
                Order(
                    order_id="live-sell-order",
                    bot_id="bot_d_live_probe",
                    condition_id="mkt-d-closed-live",
                    token_id="yes-d-closed-live",
                    side="SELL",
                    price=Decimal("0.70"),
                    size=Decimal("5"),
                    status="FILLED",
                    placed_at=now - timedelta(minutes=6),
                    last_updated=now - timedelta(minutes=5),
                ),
                Trade(
                    trade_id="live-buy-bot-d",
                    bot_id="bot_d_live_probe",
                    order_id="live-buy-order",
                    condition_id="mkt-d-closed-live",
                    token_id="yes-d-closed-live",
                    side="BUY",
                    price=Decimal("0.50"),
                    size=Decimal("5"),
                    fee_usd=Decimal("0"),
                    filled_at=now - timedelta(minutes=20),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("2.00"),
                ),
                Trade(
                    trade_id="live-sell-bot-d",
                    bot_id="bot_d_live_probe",
                    order_id="live-sell-order",
                    condition_id="mkt-d-closed-live",
                    token_id="yes-d-closed-live",
                    side="SELL",
                    price=Decimal("0.70"),
                    size=Decimal("5"),
                    fee_usd=Decimal("0"),
                    filled_at=now - timedelta(minutes=5),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("2.80"),
                ),
                Order(
                    order_id="live-probe-open",
                    bot_id="bot_d_live_probe",
                    condition_id="mkt-d-live",
                    token_id="yes-d-live",
                    side="BUY",
                    price=Decimal("0.50"),
                    size=Decimal("5"),
                    status="OPEN",
                    placed_at=now - timedelta(minutes=10),
                    last_updated=now - timedelta(minutes=10),
                ),
                Order(
                    order_id="maker-open",
                    bot_id="bot_d_maker_live_probe",
                    condition_id="mkt-d-maker",
                    token_id="no-d-maker",
                    side="BUY",
                    price=Decimal("0.50"),
                    size=Decimal("10"),
                    status="OPEN",
                    placed_at=now - timedelta(minutes=8),
                    last_updated=now - timedelta(minutes=8),
                ),
            ]
        )
        session.commit()

    bot_d = read_json(dashboard_server, "/api/bot-d")
    epoch = bot_d["paper_epoch"]
    entry_policy = bot_d["readiness"]["entry_policy"]

    assert epoch["id"] == "station_v1_2026_04_29"
    assert epoch["start"].startswith("2026-04-29T19:10:00")
    assert bot_d["readiness"]["readiness"]["wallet_priority"] is True
    assert bot_d["readiness"]["readiness"]["live_ready"] is False
    assert entry_policy["depth_gate_enabled"] is True
    assert entry_policy["min_entry_depth_usd"] == 25.0
    assert entry_policy["require_wave_for_entry"] is True
    assert isinstance(entry_policy["live_authorized"], bool)
    assert entry_policy["allow_nws_fallback_entry"] is False
    assert bot_d["recent_trades"][0]["trade_id"] == "paper-fill-bot-d"
    assert bot_d["recent_trades"][0]["execution_mode"] == "paper"
    assert "paper_pnl" not in bot_d["live_probe"]
    assert bot_d["live_probe"]["open_orders_pnl"]["capital_deployed"] == 2.5
    assert bot_d["live_probe"]["open_orders_pnl"]["open_count"] == 1
    assert bot_d["live_probe"]["caps"]["daily_gross_usd"] == 8.5
    assert bot_d["live_probe"]["caps"]["daily_limit_usd"] > 0
    assert bot_d["live_probe"]["caps"]["filled_plus_resting_exposure_usd"] == 2.5
    assert bot_d["live_probe"]["caps"]["open_exposure_limit_usd"] > 0
    assert bot_d["live_probe"]["order_metrics"]["live_open_orders"] == 1
    assert bot_d["live_probe"]["simple"]["pnl_usd"] == 1.0
    assert bot_d["live_probe"]["simple"]["realised_pnl_usd"] == 1.0
    assert bot_d["live_probe"]["simple"]["pnl_note"] == "realised live P&L"
    assert bot_d["live_probe"]["trade_metrics"]["realised_pnl_usd"] == 1.0
    assert "paper_pnl" not in bot_d["maker_live"]
    assert bot_d["maker_live"]["bot_id"] == "bot_d_maker_live_probe"
    assert bot_d["maker_live"]["quote_policy"]["maker_only"] is True
    assert bot_d["maker_live"]["quote_policy"]["activation_adr"] == "ADR-174"
    assert bot_d["maker_live"]["open_orders_pnl"]["capital_deployed"] == 5.0
    assert bot_d["maker_live"]["open_orders_pnl"]["open_count"] == 1
    assert bot_d["maker_live"]["caps"]["daily_gross_usd"] == 5.0
    assert bot_d["maker_live"]["caps"]["daily_limit_usd"] == 100.0
    assert bot_d["maker_live"]["caps"]["filled_plus_resting_exposure_usd"] == 5.0
    assert bot_d["maker_live"]["caps"]["open_exposure_limit_usd"] == 100.0
    assert bot_d["maker_live"]["order_metrics"]["live_open_orders"] == 1
    assert bot_d["source_edge"]["bot_id"] == "bot_d_live_probe"
    assert bot_d["live_probe"]["source_edge"]["bot_id"] == "bot_d_live_probe"
    assert epoch["paper_pnl"]["open_count"] == 0
    assert epoch["order_metrics"]["total_orders"] == 0
    assert epoch["trade_metrics"]["filled_trades_count"] == 1


def test_dashboard_js_routes_bot_d_to_weather_panel(dashboard_server):
    """The Bot D drilldown is dispatched correctly and the slim cockpit
    surface still renders the operator-essential weather lanes (live
    probe + spike + spike-short paper lanes + resolved P&L). Older
    debug surfaces (gribstream, station coverage, scan summary, NWS
    fallback) were stripped from the cockpit and now live in
    scripts/bot_d_readiness_report.py."""
    js = read_text(dashboard_server, "/app.js")

    assert 'if (tab === "bot-d")' in js
    assert "panel.append(botDPanels(payload));" in js
    assert "panel.append(botGPanels(payload));" in js
    assert "Bot D Live Probe" in js
    assert "Weather Cheap-YES Paper Lanes" in js
    assert "Resolved P&L" in js
    # Confirm the verbose debug panels have been retired from the cockpit.
    assert "Live-Candidate Gates" not in js
    assert "GribStream Usage" not in js
    assert "Station Coverage" not in js
    assert "Latest Scan" not in js
    assert "NWS Fallback" not in js


def test_orders_events_bot_c_and_legacy_state_contracts(dashboard_server):
    orders = read_json(dashboard_server, "/api/orders")
    events = read_json(dashboard_server, "/api/events")
    bot_c = read_json(dashboard_server, "/api/bot-c")
    legacy = read_json(dashboard_server, "/api/state")

    assert orders["orders"] == []
    assert orders["status_counts"] == {}
    assert "bot_a" not in orders["open_position_counts"]
    assert "bot_b" not in orders["open_position_counts"]
    assert orders["open_positions"] == []
    assert orders["recent_trades"] == []
    assert orders["trade_metrics"]["sell_fills_count"] == 0

    assert events["severity_counts"]["warn"] == 1
    assert events["severity_counts"]["kill"] == 1
    assert {row["severity"] for row in events["events"]} == {"info", "warn", "kill"}

    assert bot_c["bot_id"] == "bot_c"
    assert bot_c["simple"]["label"] == "bot_c"

    assert legacy["wallet"].endswith("14cd")
    assert "bot_c" in legacy
    assert "bot_f" not in legacy
    assert legacy["bot_c"]["simple"]["label"] == "bot_c"


def test_query_bot_h_uses_vps_summary_when_recorder_is_remote(tmp_db, tmp_path, monkeypatch):
    """Bot H Maker V2 query should adopt the VPS-reported recorder counts
    when the service state is `vps:active` AND the bridge has a non-empty
    `bot_h_maker_v2` field. Falls back to empty otherwise so the dashboard
    never silently invents data."""
    seed_dashboard_db()
    status_path = tmp_path / "vps_node_latest.json"
    status_path.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "node": {"hostname": "vps-host", "root": "/home/operator/longshot-research"},
        "disk": {"used_pct": 6.0, "free_bytes": 60000000000},
        "tailscale": {"ipv4": "192.0.2.1", "status": {"BackendState": "Running"}},
        "services": {
            "ssh.service": {"active": "active", "enabled": "enabled"},
            "ssh.socket": {"active": "active", "enabled": "enabled"},
            "tailscaled.service": {"active": "active", "enabled": "enabled"},
            "longshot-vps-node-status.timer": {"active": "active", "enabled": "enabled"},
            "polymarket-bot-h-maker-v2-recorder-vps.service": {
                "active": "active", "enabled": "enabled",
            },
        },
        "databases": {},
        "bot_h_maker_v2": {
            "bot_id": "bot_h_maker_v2",
            "size_bytes": 156 * 1024 * 1024,
            "counts": {"markets": 320, "pm_events": 4_500_000, "heartbeats": 2880},
            "active_markets": 290,
            "events_24h_total": 320_000,
            "events_24h_by_type": {"book": 180_000, "price_change": 110_000, "last_trade_price": 30_000},
            "events_24h_by_category": {"politics": 200_000, "sports": 80_000, "crypto": 30_000, "awards": 10_000},
            "markets_by_category": {"politics": 150, "sports": 90, "crypto": 30, "awards": 20},
            "events_per_min_5m": 222.4,
            "last_event_age_sec": 12.3,
            "heartbeat": {"count_24h": 2880, "last_age_sec": 21.0, "longest_gap_sec": 35.0},
            "data_quality": {
                "event_gaps": {"count": 1, "longest_gap_sec": 180.0},
                "top_of_book": {"fresh_token_count": 8, "active_token_count": 10},
            },
        },
    }))
    monkeypatch.setenv("VPS_NODE_STATUS_PATH", str(status_path))

    from dashboard import runtime_queries

    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {"polymarket-bot-h-maker-v2-recorder-vps": "vps:active"},
    )

    payload = runtime_queries.query_bot_h()

    assert payload["bot_id"] == "bot_h_maker_v2"
    assert payload["data_source"] == "vps"
    assert payload["mode"] == "paper"
    assert payload["phase"] == "1_recorder"
    assert payload["vps_configured"] is True
    cell_labels = {c["label"] for c in payload["active_quote_cells"]}
    assert cell_labels == {"politics_0_10c", "sports_10_20c"}
    assert "weather" not in payload["recorder_filter"]["categories"]
    rec = payload["recorder"]
    assert rec["active_markets"] == 290
    assert rec["events_24h_total"] == 320_000
    assert rec["events_24h_by_category"]["politics"] == 200_000
    assert rec["heartbeat"]["last_age_sec"] == 21.0
    assert rec["last_event_age_sec"] == 12.3
    assert rec["data_quality"]["event_gaps"]["count"] == 1


def test_query_bot_h_falls_back_when_vps_bridge_unreported(tmp_db, monkeypatch):
    """When the VPS status bridge is not configured, query_bot_h should
    return an empty `recorder` dict and `data_source=the bot container` rather than
    raising or fabricating numbers."""
    seed_dashboard_db()
    monkeypatch.delenv("VPS_NODE_STATUS_PATH", raising=False)
    monkeypatch.delenv("VPS_NODE_STATUS_URL", raising=False)
    from dashboard import runtime_queries

    monkeypatch.setattr(runtime_queries, "service_states", lambda: {})

    payload = runtime_queries.query_bot_h()
    assert payload["bot_id"] == "bot_h_maker_v2"
    assert payload["data_source"] == "the bot container"
    assert payload["recorder"] == {}
    assert payload["vps_configured"] is False


def test_query_bot_h_prefers_bot_host_local_summary(tmp_db, monkeypatch):
    """After ADR-145 the dashboard reads Bot H from the bot container-local
    `maker_recorder.db`. When the local summary reports `exists=True`,
    `query_bot_h` should report `data_source=the bot container` even if the VPS bridge
    also has data. No `data_source_warning` is expected on the happy path."""
    seed_dashboard_db()
    monkeypatch.delenv("VPS_NODE_STATUS_PATH", raising=False)
    monkeypatch.delenv("VPS_NODE_STATUS_URL", raising=False)
    from dashboard import runtime_queries

    fake_local = {
        "exists": True,
        "size_bytes": 1_858_224_128,
        "counts": {"markets": 106, "pm_events": 1_296_053, "heartbeats": 4283},
        "active_markets": 106,
        "events_24h_total": 25_588,
        "events_24h_by_type": {"book": 18_000, "price_change": 6_000, "last_trade_price": 1_500},
        "events_24h_by_category": {"politics": 9_000, "sports": 7_500, "crypto": 7_000, "awards": 2_088},
        "markets_by_category": {"politics": 40, "sports": 30, "crypto": 24, "awards": 12},
        "events_per_min_5m": 17.8,
        "last_event_age_sec": 1.5,
        "heartbeat": {"count_24h": 63, "last_age_sec": 28.0, "longest_gap_sec": 35.0},
        "data_quality": {
            "event_gaps": {"count": 0, "longest_gap_sec": 0.0},
            "top_of_book": {"fresh_token_count": 12, "active_token_count": 12},
        },
    }
    monkeypatch.setattr(
        runtime_queries, "_local_bot_h_maker_v2_summary", lambda: fake_local
    )
    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {"polymarket-bot-h-maker-v2-recorder": "active"},
    )

    payload = runtime_queries.query_bot_h()

    assert payload["bot_id"] == "bot_h_maker_v2"
    assert payload["data_source"] == "the bot container"
    assert payload["data_source_warning"] is None
    assert payload["recorder"]["counts"]["pm_events"] == 1_296_053
    assert payload["recorder"]["active_markets"] == 106
    assert payload["recorder"]["data_quality"]["top_of_book"]["fresh_token_count"] == 12


def test_query_bot_h_warns_when_bot_host_unit_active_but_local_db_missing(
    tmp_db, monkeypatch
):
    """If the bot container unit is `active` but the local DB summary reports
    `exists=False`, surface `data_source_warning` so a misconfigured env
    doesn't silently flip the source label."""
    seed_dashboard_db()
    monkeypatch.delenv("VPS_NODE_STATUS_PATH", raising=False)
    monkeypatch.delenv("VPS_NODE_STATUS_URL", raising=False)
    from dashboard import runtime_queries

    monkeypatch.setattr(
        runtime_queries, "_local_bot_h_maker_v2_summary", lambda: {"exists": False}
    )
    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {"polymarket-bot-h-maker-v2-recorder": "active"},
    )

    payload = runtime_queries.query_bot_h()

    warning = payload["data_source_warning"]
    assert warning is not None
    assert "polymarket-bot-h-maker-v2-recorder" in warning
    assert "missing" in warning.lower()


def test_query_wallet_observer_prefers_bot_host_local_summary(tmp_db, monkeypatch):
    """Mirror of the Bot H test for wallet observer."""
    seed_dashboard_db()
    monkeypatch.delenv("VPS_NODE_STATUS_PATH", raising=False)
    monkeypatch.delenv("VPS_NODE_STATUS_URL", raising=False)
    from dashboard import runtime_queries

    fake_local = {
        "exists": True,
        "size_bytes": 180_350_976,
        "headline": {
            "total_fills": 187_673,
            "fills_24h": 1_265,
            "fills_7d": 6_000,
            "distinct_wallets_24h": 41,
            "first_fill_ts": 1_715_000_000,
            "last_fill_ts": 1_715_400_000,
            "last_fill_age_sec": 95,
        },
    }
    monkeypatch.setattr(
        runtime_queries, "_local_wallet_observer_summary", lambda: fake_local
    )
    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {"polymarket-wallet-observer": "active"},
    )

    payload = runtime_queries.query_wallet_observer()

    assert payload["bot_id"] == "wallet_observer"
    assert payload["data_source"] == "the bot container"
    assert payload["data_source_warning"] is None
    assert payload["summary"]["headline"]["total_fills"] == 187_673


def test_query_wallet_observer_warns_when_bot_host_unit_active_but_local_db_missing(
    tmp_db, monkeypatch
):
    seed_dashboard_db()
    monkeypatch.delenv("VPS_NODE_STATUS_PATH", raising=False)
    monkeypatch.delenv("VPS_NODE_STATUS_URL", raising=False)
    from dashboard import runtime_queries

    monkeypatch.setattr(
        runtime_queries, "_local_wallet_observer_summary", lambda: {"exists": False}
    )
    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {"polymarket-wallet-observer": "active"},
    )

    payload = runtime_queries.query_wallet_observer()

    warning = payload["data_source_warning"]
    assert warning is not None
    assert "polymarket-wallet-observer" in warning
    assert "missing" in warning.lower()


def test_query_wallet_observer_uses_vps_summary(tmp_db, tmp_path, monkeypatch):
    seed_dashboard_db()
    status_path = tmp_path / "vps_node_latest.json"
    status_path.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "node": {"hostname": "vps-host", "root": "/home/operator/longshot-research"},
        "disk": {"used_pct": 5.5, "free_bytes": 65000000000},
        "tailscale": {"ipv4": "192.0.2.1", "status": {"BackendState": "Running"}},
        "services": {
            "ssh.service": {"active": "active", "enabled": "enabled"},
            "ssh.socket": {"active": "active", "enabled": "enabled"},
            "tailscaled.service": {"active": "active", "enabled": "enabled"},
            "longshot-vps-node-status.timer": {"active": "active", "enabled": "enabled"},
            "polymarket-wallet-observer.service": {"active": "active", "enabled": "enabled"},
        },
        "databases": {},
        "wallet_observer": {
            "bot_id": "wallet_observer",
            "size_bytes": 72 * 1024 * 1024,
            "headline": {
                "total_fills": 17_930,
                "fills_24h": 425,
                "fills_7d": 3_180,
                "distinct_wallets_24h": 38,
                "first_fill_ts": 1_715_000_000,
                "last_fill_ts": 1_715_400_000,
                "last_fill_age_sec": 200,
            },
            "tier_24h": [
                {"tier": "A_human_profitable", "n_fills": 280, "n_wallets": 22, "n_buys": 150, "n_sells": 130},
                {"tier": "B_unknown_profitable", "n_fills": 145, "n_wallets": 16, "n_buys": 75, "n_sells": 70},
            ],
            "side_24h": [
                {"side": "BUY", "n": 225, "avg_price": 0.43},
                {"side": "SELL", "n": 200, "avg_price": 0.39},
            ],
            "collector_state": [
                {"exchange": "CTF", "last_block": 75_321_010, "last_updated": 1_715_400_010},
                {"exchange": "NegRiskCTF", "last_block": 75_321_009, "last_updated": 1_715_400_005},
            ],
            "latest_run": {
                "run_id": 12,
                "started_at": 1_715_300_000,
                "stopped_at": None,
                "n_fills": 425,
                "n_polls": 13_000,
                "last_block": 75_321_010,
            },
        },
    }))
    monkeypatch.setenv("VPS_NODE_STATUS_PATH", str(status_path))

    from dashboard import runtime_queries

    monkeypatch.setattr(
        runtime_queries,
        "service_states",
        lambda: {"polymarket-wallet-observer": "vps:active"},
    )

    payload = runtime_queries.query_wallet_observer()

    assert payload["bot_id"] == "wallet_observer"
    assert payload["mode"] == "passive"
    assert payload["wallet_count"] == 245
    assert payload["data_source"] == "vps"
    assert payload["vps_configured"] is True
    summary = payload["summary"]
    assert summary["headline"]["total_fills"] == 17_930
    assert summary["headline"]["distinct_wallets_24h"] == 38
    tier_names = [t["tier"] for t in summary["tier_24h"]]
    assert "A_human_profitable" in tier_names
    assert "B_unknown_profitable" in tier_names
    assert any(s["side"] == "BUY" for s in summary["side_24h"])
    assert {row["exchange"] for row in summary["collector_state"]} == {"CTF", "NegRiskCTF"}
    assert summary["latest_run"]["run_id"] == 12


def test_server_routes_include_bot_h_and_wallet_observer():
    """ROUTES table should expose the two new endpoints; regression guard
    so future refactors don't drop them."""
    from dashboard.server import ROUTES

    assert "/api/bot-h" in ROUTES
    assert "/api/wallet-observer" in ROUTES


def test_cockpit_overview_only_surfaces_active_lanes(dashboard_server):
    """Bloomberg-cockpit redesign contract: /api/overview must expose only
    active-class rows in `bot_inventory` (Live / Paper / Recorder). All
    archived, parked, halted-by-design, and inactive identities stay out
    of the operator surface."""
    payload = read_json(dashboard_server, "/api/overview")
    inventory = payload["bot_inventory"]

    # Every visible row belongs to an active group.
    groups = {row["group"] for row in inventory}
    assert groups <= {"Live", "Paper", "Recorder"}

    # Sanity: dead identities never re-appear via the cockpit.
    forbidden_ids = {
        "bot_a", "bot_a_shadow",
        "bot_b", "bot_b_shadow",
        "bot_c",
        "bot_f", "bot_f_mirror", "bot_f_paper_mirror",
        "bot_g", "bot_g_jackpot", "bot_g_scalp",
    }
    assert not any(row["bot_id"] in forbidden_ids for row in inventory)

    # No row carries `halted=True`; halted lanes belong off the cockpit.
    assert not any(row.get("halted") for row in inventory)


def test_cockpit_inventory_exposes_time_to_decision(dashboard_server):
    payload = read_json(dashboard_server, "/api/overview")
    by_id = {row["bot_id"]: row for row in payload["bot_inventory"]}

    assert by_id["wallet_observer"]["time_to_decision"] == "6 days (2026-05-15)"
    assert by_id["bot_h_maker_v2"]["time_to_decision"] == "~24h to OQ-100 trip"
    assert by_id["bot_g_prime_live"]["time_to_decision"] == "operator decision pending"


def test_cockpit_live_inventory_separates_redeemed_pnl_from_exposure(
    tmp_db,
    tmp_path,
    monkeypatch,
):
    seed_dashboard_db()
    bot_c_db = tmp_path / "bot_c.db"
    seed_bot_c_db(bot_c_db)
    now = datetime.now(UTC)
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add_all(
            [
                Order(
                    order_id="live-fv-filled",
                    bot_id="crypto_probability_gap_live_maker",
                    condition_id="live-cond-win",
                    token_id="live-token-win",
                    side="BUY",
                    price=Decimal("0.50"),
                    size=Decimal("10"),
                    status="FILLED",
                    placed_at=now - timedelta(minutes=10),
                    last_updated=now - timedelta(minutes=9),
                ),
                Order(
                    order_id="live-fv-open-order",
                    bot_id="crypto_probability_gap_live_maker",
                    condition_id="live-cond-open-order",
                    token_id="live-token-open-order",
                    side="BUY",
                    price=Decimal("0.20"),
                    size=Decimal("20"),
                    status="OPEN",
                    placed_at=now - timedelta(minutes=2),
                    last_updated=now - timedelta(minutes=2),
                ),
                Trade(
                    trade_id="live-fv-buy",
                    bot_id="crypto_probability_gap_live_maker",
                    order_id="live-fv-filled",
                    condition_id="live-cond-win",
                    token_id="live-token-win",
                    side="BUY",
                    price=Decimal("0.50"),
                    size=Decimal("10"),
                    fee_usd=Decimal("0.10"),
                    filled_at=now - timedelta(minutes=9),
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("4.00"),
                ),
                Position(
                    bot_id="crypto_probability_gap_live_maker",
                    condition_id="live-cond-win",
                    token_id="live-token-win",
                    side="YES",
                    size=Decimal("10"),
                    avg_price=Decimal("0.50"),
                    cost_basis_usd=Decimal("5.00"),
                    status="REDEEMED",
                    opened_at=now - timedelta(minutes=9),
                    closed_at=now,
                ),
                Position(
                    bot_id="crypto_probability_gap_live_maker",
                    condition_id="live-cond-open",
                    token_id="live-token-open",
                    side="YES",
                    size=Decimal("10"),
                    avg_price=Decimal("0.30"),
                    cost_basis_usd=Decimal("3.00"),
                    status="OPEN",
                    opened_at=now - timedelta(minutes=1),
                ),
                Event(
                    bot_id="crypto_probability_gap_live_maker",
                    event_type="portfolio.redeem",
                    severity="info",
                    message="position redeemed",
                    payload={
                        "usdc_received": "12.00",
                        "cost_basis": "5.00",
                        "realised_usd": "7.00",
                    },
                    created_at=now,
                ),
            ]
        )
        session.commit()

    with running_dashboard(monkeypatch, bot_c_db) as base_url:
        from dashboard import runtime_queries

        monkeypatch.setattr(
            runtime_queries,
            "service_states",
            lambda: {
                "polymarket-crypto-prob-gap-live-maker": "active",
            },
        )
        payload = read_json(base_url, "/api/overview")

    row = next(
        bot
        for bot in payload["bot_inventory"]
        if bot["bot_id"] == "crypto_probability_gap_live_maker"
    )
    assert row["pnl_kind"] == "realised_clob"
    assert row["pnl_usd"] == pytest.approx(6.90)
    assert row["realised_pnl_usd"] == pytest.approx(6.90)
    assert row["roi_pct"] == pytest.approx(138.0)
    assert row["realised_cost_usd"] == pytest.approx(5.0)
    assert row["redeemed_cost_usd"] == pytest.approx(5.0)
    assert row["redeemed_payout_usd"] == pytest.approx(12.0)
    assert row["redeemed_positions"] == 1
    assert row["closed_positions"] == 1
    assert row["open_positions"] == 1
    assert row["open_position_cost_usd"] == pytest.approx(3.0)
    assert row["open_order_notional_usd"] == pytest.approx(4.0)
    assert row["exposure_usd"] == pytest.approx(7.0)
    assert row["registry_status"] == "paused"
    assert row["pnl_note"] == (
        "paused live lane; realised live P&L retained for postmortem; "
        "exposure shown separately"
    )


def test_cockpit_priority_alerts_surface_is_explicit(dashboard_server):
    """Priority Review surface must be explicit: empty list when no edge
    is active, never missing or null. ADR-138 keeps the wallet-tag forward
    gate (OQ-099, ADR-137) outside this surface until 2026-05-15."""
    payload = read_json(dashboard_server, "/api/overview")
    assert "priority_alerts" in payload
    assert payload["priority_alerts"] == []


def test_cockpit_risk_summary_filters_to_active_lanes(dashboard_server):
    """Risk strip must only include degraded services that map to active
    inventory rows and halts on bots considered active. Halts on archived
    bots (bot_a, bot_b, bot_c, bot_e) must not contribute."""
    payload = read_json(dashboard_server, "/api/overview")
    risk = payload["risk"]
    assert "degraded_services" in risk
    assert "active_halts" in risk
    assert "active_count" in risk

    trading_ids = {
        row["bot_id"]
        for row in payload["bot_inventory"]
        if row.get("group") in {"Live", "Paper"}
    }
    for halt in risk["active_halts"]:
        assert halt["bot_id"] in trading_ids, (
            f"Risk strip surfaced halt for non-trading lane: {halt['bot_id']}"
        )

    # Stale halts on archived bots and on Recorder lanes (the
    # 2026-05-05 bot_e halt is a legacy trading-bot row and must not
    # show on the Risk strip even though the recorder is visible).
    forbidden = {"bot_a", "bot_b", "bot_c", "bot_e", "bot_f"}
    halt_ids = {h["bot_id"] for h in risk["active_halts"]}
    assert halt_ids.isdisjoint(forbidden)
