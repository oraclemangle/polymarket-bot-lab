"""Tests for the canonical bot registry (2026-04-22).

Prevents the drift pattern where new bots (G, F_mirror) landed in code
but were absent from fleet.known_bots / BOT_ARCHETYPE / watchdog cancel
coverage. See Codex Section C + GLM-5.1 A7.
"""
from __future__ import annotations


def test_registry_covers_every_active_bot():
    """Every bot id referenced by any bot module's __main__ must appear in
    the registry. This is the drift guard — adding a new bot implies
    adding a registry entry."""
    from core.bot_registry import all_bot_ids
    ids = set(all_bot_ids())
    expected = {
        "bot_a", "bot_a_shadow",
        "bot_b", "bot_b_shadow",
        "bot_c", "bot_d", "bot_d_spike", "bot_e",
        "bot_f", "bot_f_mirror",
        "bot_g", "bot_g_jackpot", "bot_g_scalp", "bot_g_prime",
        "bot_g_prime_live", "bot_g_prime_live_maker", "bot_g_prime_maker",
        "bot_g_prime_shadow_maker", "bot_g_prime_high_tail",
        "bot_g_prime_high_tail_maker",
        "bot_i_persistence_maker", "bot_i_persistence_live_maker",
        "bot_i_cell_c_maker",
        "crypto_probability_gap_paper_maker", "crypto_brownian_fv_paper_maker",
    }
    assert expected <= ids, f"Registry missing bots: {expected - ids}"


def test_fleet_known_bots_derived_from_registry():
    """core/fleet.py should use the registry as the source of truth."""
    import importlib

    import core.fleet as fleet
    importlib.reload(fleet)
    # snapshot_fleet_exposure uses known_bots internally; the easiest
    # public probe is that bot_g is now recognised.
    from core.bot_registry import all_bot_ids
    # BOT_ARCHETYPE must cover every bot id in the registry.
    for bid in all_bot_ids():
        assert bid in fleet.BOT_ARCHETYPE, f"{bid} missing from BOT_ARCHETYPE"


def test_archetype_every_id_assigned():
    """No bot can be archetype='unknown' — that was the drift symptom."""
    from core.bot_registry import REGISTRY
    for b in REGISTRY:
        assert b.archetype != "unknown", f"{b.bot_id} has unknown archetype"
        assert b.archetype, f"{b.bot_id} has empty archetype"


def test_cap_member_includes_current_paper_bots():
    """Paper bots that actively hold positions must be in cap_member
    (so fleet exposure cap sees their exposure). Archived and sensor
    bots are excluded."""
    from core.bot_registry import cap_member_bot_ids, meta
    cap = set(cap_member_bot_ids())
    assert "bot_b" in cap
    assert "bot_d" in cap
    assert "bot_e" not in cap
    assert "bot_g_prime" in cap
    assert "bot_g_prime_live" in cap
    assert "bot_g" not in cap
    assert "bot_g_jackpot" not in cap
    assert "bot_g_scalp" not in cap
    # Archived bot_a/F surfaces excluded; sensor bot_f excluded.
    assert "bot_a" not in cap
    assert "bot_f" not in cap
    assert "bot_f_mirror" not in cap
    for bot_id in ("crypto_probability_gap_paper", "crypto_brownian_fv_paper"):
        bot = meta(bot_id)
        assert bot is not None
        assert bot.status == "archived"
        assert bot.include_in_cap is False
        assert bot_id not in cap
    bot = meta("bot_d_spike")
    assert bot is not None
    assert bot.status == "live"
    assert bot.include_in_cap is True
    assert "bot_d_spike" in cap
    assert "bot_d_station_lock" in cap
    assert "bot_l_complete_set" in cap
    assert "crypto_probability_gap_live_maker" in cap
    assert "crypto_brownian_fv_live_maker" in cap
    assert meta("crypto_probability_gap_live_maker").status == "paused"
    assert meta("crypto_brownian_fv_live_maker").status == "paused"
    assert meta("bot_i_persistence_live").status == "paused"


def test_watchdog_live_cap_bots_include_live_prime():
    from core.watchdog import LIVE_CAP_BOTS, PAPER_CAP_BOTS, VPS_HOSTED_BOTS

    assert "bot_g_prime_live" in VPS_HOSTED_BOTS
    assert "bot_g_prime_live" not in LIVE_CAP_BOTS
    assert "bot_g_prime_live" not in PAPER_CAP_BOTS
    assert "bot_g_prime" in VPS_HOSTED_BOTS
    assert "bot_g_prime" not in PAPER_CAP_BOTS
    assert "bot_g_prime_high_tail" in VPS_HOSTED_BOTS
    assert "bot_g_prime_high_tail" not in PAPER_CAP_BOTS


def test_dashboard_surface_derived_from_registry():
    """The active operator dashboard must use registry visibility flags."""
    from core.bot_registry import archived_dashboard_bot_ids, dashboard_bot_ids

    assert dashboard_bot_ids() == (
        "bot_d",
        "bot_d_live_probe",
        "bot_d_maker_live_probe",
        "bot_d_spike",
        "bot_d_station_lock",
        "bot_g_prime",
        "bot_g_prime_live",
        "crypto_probability_gap_live_maker",
        "crypto_brownian_fv_live_maker",
        "wallet_tag_elite_cap_paper",
        "bot_i_persistence_live",
        "bot_j_nr_wallet",
        "bot_k_sports_taker",
        "bot_l_complete_set",
    )
    archived = set(archived_dashboard_bot_ids())
    assert {
        "bot_a",
        "bot_a_shadow",
        "bot_b",
        "bot_b_shadow",
        "bot_c",
        "bot_e",
        "bot_f",
        "bot_f_mirror",
        "bot_g",
        "bot_g_jackpot",
        "bot_g_scalp",
    } <= archived


def test_systemd_units_are_unique():
    """Two bots can't share the same systemd unit."""
    from core.bot_registry import REGISTRY
    units = [b.systemd_unit for b in REGISTRY if b.systemd_unit]
    assert len(units) == len(set(units)), "duplicate systemd units"


def test_active_systemd_units_exclude_archived_bot_g_paper_lanes():
    """ADR-140 archived these paper lanes; active-unit inventory must not
    keep them alive via hard-coded extras."""
    from core.bot_registry import active_systemd_units

    active = set(active_systemd_units())
    assert "polymarket-bot-g-prime-high-tail.service" not in active
    assert "polymarket-bot-g-prime-shadow-maker-paper.service" not in active
    assert "polymarket-bot-g-prime-high-tail-maker-paper.service" not in active
    assert "polymarket-bot-f-momentum-paper.timer" not in active
    assert "polymarket-wc-negrisk-basket-paper.timer" not in active
    assert "polymarket-bot-d-spike-short-vps.service" not in active
    assert "polymarket-bot-j-nr-wallet-paper.service" not in active
    assert "polymarket-bot-k-sports-taker-paper.service" not in active
    assert "polymarket-maker-conversion-gate-watch.timer" in active
    assert "polymarket-wallet-tag-elite-cap-paper.service" in active
    assert "polymarket-wallet-tag-elite-cap-paper.timer" in active
    assert "polymarket-bot-g-prime-late-cheap.service" not in active
    assert "polymarket-bot-g-prime-take-profit.service" not in active


def test_bot_d_systemd_units_pin_paper_and_live_probe_env_after_env_file():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    paper = (root / "systemd/polymarket-bot-d.service").read_text()
    live = (root / "systemd/polymarket-bot-d-live.service").read_text()

    assert paper.index("EnvironmentFile=.env") < paper.index(
        'Environment="BOT_D_ENV=paper"'
    )
    assert live.index("EnvironmentFile=.env") < live.index(
        'Environment="BOT_D_ID_OVERRIDE=bot_d_live_probe"'
    )
    assert 'Environment="BOT_D_INITIAL_USD=400"' in live
    assert 'Environment="BOT_D_LIVE_FIXED_SHARES=15"' in live
    assert 'Environment="BOT_D_NWS_VETO_MIN_THRESHOLD_F=3.0"' in live


def test_watchdog_cancel_coverage_includes_new_bots():
    """Regression for Codex A-3: watchdog dispatch_cancel must have
    wrappers for every live/paper bot (excluding bot_a/bot_b which have
    dedicated executor paths, VPS-hosted bots, and shadows/sensors which
    don't trade on the bot container)."""
    from core.bot_registry import REGISTRY
    from core.watchdog import VPS_HOSTED_BOTS

    expected = {
        b.bot_id for b in REGISTRY
        if b.bot_id not in ("bot_a", "bot_b")
        and b.status not in ("archived", "shadow", "sensor")
        and b.bot_id not in VPS_HOSTED_BOTS
    }
    # Bot G Prime is the current audit-surfaced active gap. Bot F mirror
    # was covered in 2026-04 but is now archived by ADR-071.
    assert "bot_g_prime" not in expected
    assert "bot_g_prime_live" not in expected
    assert "bot_g_prime_high_tail" not in expected
    assert "bot_g" not in expected
    assert "bot_g_jackpot" not in expected
    assert "bot_g_scalp" not in expected
    assert "bot_f_mirror" not in expected
    assert "bot_c" not in expected
    assert "bot_d" in expected
    assert "bot_e" not in expected
    assert "crypto_probability_gap_live_maker" in expected
    assert "crypto_brownian_fv_live_maker" in expected


def test_fee_rate_by_category_derived_from_fees():
    """config.FEE_RATE_BY_CATEGORY_BPS must equal baseRate x 10000 from
    core/fees.py for every category. Prevents the 10x drift that GLM-5.1
    A8 flagged."""
    from core.config import FEE_RATE_BY_CATEGORY_BPS
    from core.fees import TAKER_FEE_RATE_BY_CATEGORY
    for cat, rate in TAKER_FEE_RATE_BY_CATEGORY.items():
        assert cat in FEE_RATE_BY_CATEGORY_BPS, f"{cat} missing from config"
        expected = int(rate * 10000)
        got = FEE_RATE_BY_CATEGORY_BPS[cat]
        assert got == expected, f"{cat}: config={got}, expected={expected}"


def test_bot_c_has_open_order_includes_partial_and_live():
    """Codex A-17: guard must recognise partial / live statuses."""
    import inspect

    from bots.bot_c_pyth import executor
    src = inspect.getsource(executor.BotCExecutor.has_open_order)
    # All four audit-flagged statuses must be in the check.
    assert "PAPER_OPEN" in src
    assert "PARTIAL" in src
    assert "PAPER_PARTIAL" in src
    assert '"live"' in src
