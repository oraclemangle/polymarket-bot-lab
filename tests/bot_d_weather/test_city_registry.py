"""Bot D city-registry safety checks."""

from bots.bot_d_weather.config import (
    CITIES,
    SETTLEMENT_SPECS,
    is_live_eligible,
    verification_status,
)


def test_2026_05_11_candidate_cities_are_shadow_only():
    for city in ("Wuhan", "Guangzhou", "Karachi", "Panama City", "Ankara"):
        assert city in CITIES
        spec = SETTLEMENT_SPECS[city]
        assert spec.station is None
        assert spec.verified is False
        assert verification_status(city) == "candidate"
        assert is_live_eligible(city) is False


def test_austin_is_live_eligible_after_rules_verification():
    spec = SETTLEMENT_SPECS["Austin"]
    assert spec.station == "KAUS"
    assert spec.obs_station == "KAUS"
    assert spec.verified is True
    assert verification_status("Austin") == "verified"
    assert is_live_eligible("Austin") is True


def test_beijing_is_live_eligible_after_rules_verification():
    spec = SETTLEMENT_SPECS["Beijing"]
    assert spec.station == "ZBAA"
    assert spec.obs_station == "ZBAA"
    assert spec.unit == "C"
    assert spec.verified is True
    assert verification_status("Beijing") == "verified"
    assert is_live_eligible("Beijing") is True
