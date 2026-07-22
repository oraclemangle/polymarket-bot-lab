from __future__ import annotations


def test_bot_f_mirror_uses_variant_env_key():
    from bots.watchdog_daemon import _bot_env_is_paper, _env_keys_for_bot

    assert _env_keys_for_bot("bot_f_mirror") == ("BOT_F_MIRROR_ENV", "BOT_F_ENV")
    assert _bot_env_is_paper(
        "bot_f_mirror",
        environ={"BOT_F_MIRROR_ENV": "paper"},
        global_live=True,
    ) is True
    assert _bot_env_is_paper(
        "bot_f_mirror",
        environ={"BOT_F_MIRROR_ENV": "live"},
        global_live=False,
    ) is False


def test_bot_g_variants_use_specific_env_keys():
    from bots.watchdog_daemon import _bot_env_is_paper, _env_keys_for_bot

    for bot_id in ("bot_g", "bot_g_jackpot", "bot_g_scalp"):
        assert _env_keys_for_bot(bot_id) == ("BOT_G_ENV",)
        assert _bot_env_is_paper(
            bot_id,
            environ={"BOT_G_ENV": "paper"},
            global_live=True,
        ) is True
    assert _env_keys_for_bot("bot_g_prime") == ("BOT_G_PRIME_ENV",)
    assert _bot_env_is_paper(
        "bot_g_prime",
        environ={"BOT_G_ENV": "live", "BOT_G_PRIME_ENV": "paper"},
        global_live=True,
    ) is True
    assert _env_keys_for_bot("bot_g_prime_live") == ("BOT_G_PRIME_LIVE_ENV",)
    assert _bot_env_is_paper(
        "bot_g_prime_live",
        environ={"BOT_G_ENV": "paper"},
        global_live=True,
    ) is False


def test_bot_d_live_probe_ignores_shared_bot_d_env_for_cancel_routing():
    from bots.watchdog_daemon import _bot_env_is_paper, _env_keys_for_bot

    assert _env_keys_for_bot("bot_d_live_probe") == ("BOT_D_LIVE_PROBE_ENV",)
    assert _bot_env_is_paper(
        "bot_d_live_probe",
        environ={"BOT_D_ENV": "paper"},
        global_live=True,
    ) is False
    assert _bot_env_is_paper(
        "bot_d_live_probe",
        environ={"BOT_D_LIVE_PROBE_ENV": "paper"},
        global_live=True,
    ) is True


def test_bot_d_maker_live_probe_uses_dedicated_env_for_cancel_routing():
    from bots.watchdog_daemon import _bot_env_is_paper, _env_keys_for_bot

    assert _env_keys_for_bot("bot_d_maker_live_probe") == ("BOT_D_MAKER_ENV",)
    assert _bot_env_is_paper(
        "bot_d_maker_live_probe",
        environ={"BOT_D_ENV": "paper"},
        global_live=True,
    ) is False
    assert _bot_env_is_paper(
        "bot_d_maker_live_probe",
        environ={"BOT_D_MAKER_ENV": "paper"},
        global_live=True,
    ) is True


def test_registry_default_prevents_global_live_from_flipping_paper_bots():
    from bots.watchdog_daemon import _bot_env_is_paper

    assert _bot_env_is_paper("bot_c", environ={}, global_live=True) is True
    assert _bot_env_is_paper("bot_d", environ={}, global_live=True) is True
    assert _bot_env_is_paper("bot_e", environ={}, global_live=True) is True
    assert _bot_env_is_paper("bot_g_prime", environ={}, global_live=True) is True
    assert _bot_env_is_paper("bot_g_prime_live", environ={}, global_live=True) is False


def test_explicit_prime_live_env_overrides_registry_default():
    from bots.watchdog_daemon import _bot_env_is_paper

    assert _bot_env_is_paper(
        "bot_g_prime_live",
        environ={"BOT_G_PRIME_LIVE_ENV": "paper"},
        global_live=True,
    ) is True


def test_explicit_live_env_overrides_registry_default():
    from bots.watchdog_daemon import _bot_env_is_paper

    assert _bot_env_is_paper(
        "bot_d",
        environ={"BOT_D_ENV": "live"},
        global_live=False,
    ) is False
