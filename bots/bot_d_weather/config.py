"""Bot D configuration — weather temperature markets.

Cities are defined with forecast coordinates, timezone, RMSE, and settlement
metadata. Weather markets are settlement-station products, not generic city
center forecasts; the forecast coordinate should therefore match the station
Polymarket names in the market rules whenever verified.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
load_dotenv(ENV_PATH, override=False)


@dataclass(frozen=True)
class CityConfig:
    lat: float
    lon: float
    rmse_f: float  # annual-average historical RMSE in Fahrenheit (baseline)
    timezone: str
    aliases: tuple[str, ...]  # lowercase patterns that match this city in question text
    # Southern-hemisphere flag: if True, summer/winter months are flipped for
    # seasonal RMSE (Dec/Jan/Feb = summer, Jun/Jul/Aug = winter).
    southern_hemisphere: bool = False
    # Legacy field retained for compatibility. For verified Polymarket
    # airport-station markets this should stay 0: the airport observation is
    # the settlement anchor, not a proxy for an urban-core temperature.
    urban_heat_island_f: float = 0.0


@dataclass(frozen=True)
class SettlementSpec:
    """Settlement metadata for a Bot D city.

    `forecast_lat/lon` are the coordinates used for model pulls. They should
    point at the settlement station when rules identify one.
    """

    station: str | None
    forecast_lat: float
    forecast_lon: float
    obs_station: str | None = None
    source: str = "wunderground"
    rounding: str = "nearest_int"
    unit: str = "F"
    verified: bool = False
    notes: str = ""
    # Verification state machine (2026-05-10 expansion). Live entries still
    # require `verified=True`; `verification_status` adds reporting/dashboard
    # detail without a DB migration. Values:
    #   "unknown"   — city seen but no settlement work done
    #   "candidate" — coords + aliases present, no station/source proof
    #   "shadow"    — station guess present, settlement unproven
    #   "verified"  — station/source/rounding documented; live eligible
    #   "rejected"  — investigated and unsuitable
    verification_status: str = ""

    @property
    def status(self) -> str:
        if self.verification_status:
            return self.verification_status
        return "verified" if self.verified else "shadow"


# Comprehensive city registry — covers all Polymarket temperature markets
# observed as of April 2026. Add new cities as Polymarket launches them.
CITIES: dict[str, CityConfig] = {
    # --- US cities ---
    "NYC": CityConfig(40.7772, -73.8726, 2.5, "America/New_York",
                      ("new york city", "new york", "nyc", "manhattan")),
    "Chicago": CityConfig(41.9742, -87.9073, 2.8, "America/Chicago",
                          ("chicago",)),
    "Dallas": CityConfig(32.8471, -96.8518, 3.0, "America/Chicago",
                         ("dallas",)),
    "Atlanta": CityConfig(33.6407, -84.4277, 2.6, "America/New_York",
                          ("atlanta",)),
    "Miami": CityConfig(25.7959, -80.2870, 2.3, "America/New_York",
                        ("miami",)),
    "Houston": CityConfig(29.9844, -95.3414, 2.8, "America/Chicago",
                          ("houston",)),
    "Austin": CityConfig(30.1975, -97.6664, 2.9, "America/Chicago",
                         ("austin",)),
    "LA": CityConfig(33.9416, -118.4085, 3.0, "America/Los_Angeles",
                     ("los angeles", "la")),
    "Seattle": CityConfig(47.4502, -122.3088, 2.5, "America/Los_Angeles",
                          ("seattle",)),
    "SF": CityConfig(37.6213, -122.3790, 2.5, "America/Los_Angeles",
                     ("san francisco", "sf")),
    "Denver": CityConfig(39.7017, -104.7517, 3.5, "America/Denver",
                         ("denver",)),
    # --- International ---
    "London": CityConfig(51.5048, 0.0495, 2.0, "Europe/London",
                         ("london",)),
    "Tokyo": CityConfig(35.5494, 139.7798, 2.0, "Asia/Tokyo",
                        ("tokyo",)),
    "Seoul": CityConfig(37.5665, 126.9780, 2.2, "Asia/Seoul",
                        ("seoul",)),
    "Shanghai": CityConfig(31.1443, 121.8083, 2.3, "Asia/Shanghai",
                           ("shanghai",)),
    "Beijing": CityConfig(40.0799, 116.6031, 2.2, "Asia/Shanghai",
                          ("beijing",)),
    "Buenos Aires": CityConfig(-34.6037, -58.3816, 2.5, "America/Argentina/Buenos_Aires",
                               ("buenos aires",), southern_hemisphere=True),
    "Helsinki": CityConfig(60.1699, 24.9384, 2.5, "Europe/Helsinki",
                           ("helsinki",)),
    "Milan": CityConfig(45.4642, 9.1900, 2.2, "Europe/Rome",
                        ("milan",)),
    "Kuala Lumpur": CityConfig(3.1390, 101.6869, 1.5, "Asia/Kuala_Lumpur",
                               ("kuala lumpur",)),
    "Sydney": CityConfig(-33.8688, 151.2093, 2.5, "Australia/Sydney",
                         ("sydney",), southern_hemisphere=True),
    # K2.6 audit 2026-04-21 (bug #3): Lagos and Manila were previously
    # traded by Bot D (appearing in the historical Trade table) but were
    # absent from this registry, so current discovery silently skips
    # their markets. Added with reasonable defaults for tropical cities
    # (low RMSE because daily variance is narrower than temperate
    # latitudes; moderate UHI for dense urban cores).
    "Lagos": CityConfig(6.5244, 3.3792, 1.8, "Africa/Lagos",
                        ("lagos",), urban_heat_island_f=1.0),
    "Manila": CityConfig(14.5995, 120.9842, 1.5, "Asia/Manila",
                         ("manila",), urban_heat_island_f=1.5),
    # Discovered 2026-04-21 via the new unknown-city WARN log after
    # deploying Fix D. Active on Polymarket's weather tag feed.
    "Hong Kong": CityConfig(22.3193, 114.1694, 1.8, "Asia/Hong_Kong",
                            ("hong kong",), urban_heat_island_f=1.5),
    "Lucknow": CityConfig(26.8467, 80.9462, 2.5, "Asia/Kolkata",
                          ("lucknow",), urban_heat_island_f=1.0),
    # --- 2026-05-10 expansion candidates (shadow / paper-only) ----------------
    # Discovery gap: Polymarket has been issuing temperature markets for these
    # cities; previously they fell through resolve_city() and were logged as
    # unknown. Added with reasonable defaults so discovery resolves; settlement
    # station/source still requires verification before live eligibility.
    "Tel Aviv": CityConfig(32.0114, 34.8867, 2.0, "Asia/Jerusalem",
                           ("tel aviv",)),
    "Toronto": CityConfig(43.6777, -79.6248, 2.6, "America/Toronto",
                          ("toronto",)),
    "Madrid": CityConfig(40.4719, -3.5626, 2.5, "Europe/Madrid",
                         ("madrid",)),
    "Paris": CityConfig(49.0097, 2.5479, 2.2, "Europe/Paris",
                        ("paris",)),
    "Moscow": CityConfig(55.9728, 37.4147, 2.8, "Europe/Moscow",
                         ("moscow",)),
    "Istanbul": CityConfig(40.9769, 28.8146, 2.3, "Europe/Istanbul",
                           ("istanbul",)),
    "Cape Town": CityConfig(-33.9648, 18.6017, 2.0, "Africa/Johannesburg",
                            ("cape town",), southern_hemisphere=True),
    "Jakarta": CityConfig(-6.1256, 106.6559, 1.5, "Asia/Jakarta",
                          ("jakarta",), southern_hemisphere=True,
                          urban_heat_island_f=1.5),
    "Qingdao": CityConfig(36.2661, 120.3744, 2.0, "Asia/Shanghai",
                          ("qingdao",)),
    "Shenzhen": CityConfig(22.6394, 113.8108, 1.8, "Asia/Shanghai",
                           ("shenzhen",), urban_heat_island_f=1.5),
    "Taipei": CityConfig(25.0777, 121.2328, 1.8, "Asia/Taipei",
                         ("taipei",)),
    # 2026-05-11 discovery candidates. These appeared in live discovery as
    # unknown cities after the Phase B expansion. They remain shadow-only
    # until market rules identify the exact settlement source and station.
    "Wuhan": CityConfig(30.5928, 114.3055, 2.0, "Asia/Shanghai",
                        ("wuhan",)),
    "Guangzhou": CityConfig(23.1291, 113.2644, 1.8, "Asia/Shanghai",
                             ("guangzhou",)),
    "Karachi": CityConfig(24.8607, 67.0011, 1.8, "Asia/Karachi",
                          ("karachi",)),
    "Panama City": CityConfig(8.9824, -79.5199, 1.8, "America/Panama",
                              ("panama city",)),
    "Ankara": CityConfig(39.9334, 32.8597, 2.2, "Europe/Istanbul",
                         ("ankara",)),
}


SETTLEMENT_SPECS: dict[str, SettlementSpec] = {
    "NYC": SettlementSpec("KLGA", 40.7772, -73.8726, "KLGA", verified=True,
                          notes="LaGuardia Airport; verified by 2026-04-29 Grok rules check."),
    "Chicago": SettlementSpec("KORD", 41.9742, -87.9073, "KORD", verified=True),
    "Dallas": SettlementSpec("KDAL", 32.8471, -96.8518, "KDAL", verified=True,
                             notes="Dallas Love Field; replaces prior KDFW assumption."),
    "Atlanta": SettlementSpec("KATL", 33.6407, -84.4277, "KATL", verified=True),
    "Miami": SettlementSpec("KMIA", 25.7959, -80.2870, "KMIA", verified=True),
    "Houston": SettlementSpec("KIAH", 29.9844, -95.3414, "KIAH",
                              verification_status="shadow",
                              notes="George Bush Intercontinental plausible; rules check pending."),
    "Austin": SettlementSpec("KAUS", 30.1975, -97.6664, "KAUS", verified=True,
                             verification_status="verified",
                             notes="Austin-Bergstrom International Airport Station via Wunderground KAUS; verified from live Gamma rules on 2026-05-14."),
    "LA": SettlementSpec("KLAX", 33.9416, -118.4085, "KLAX",
                         verification_status="shadow",
                         notes="LAX plausible; downtown Los Angeles (KCQT) sometimes used by Polymarket — verify before live."),
    "Seattle": SettlementSpec("KSEA", 47.4502, -122.3088, "KSEA", verified=True),
    "SF": SettlementSpec("KSFO", 37.6213, -122.3790, "KSFO",
                         verification_status="shadow",
                         notes="SFO plausible; some forecasts use KOAK or downtown — verify before live."),
    "Denver": SettlementSpec("KBKF", 39.7017, -104.7517, "KBKF", verified=True,
                             notes="Buckley Space Force Base per 2026-04-29 rules check."),
    "London": SettlementSpec("EGLC", 51.5048, 0.0495, "EGLC", unit="C", verified=True),
    "Tokyo": SettlementSpec("RJTT", 35.5494, 139.7798, "RJTT", unit="C", verified=True),
    "Seoul": SettlementSpec("RKSI", 37.4691, 126.4505, "RKSI", unit="C",
                            verification_status="shadow",
                            notes="Incheon plausible; Polymarket may use Gimpo (RKSS) — verify."),
    "Shanghai": SettlementSpec("ZSPD", 31.1443, 121.8083, "ZSPD", unit="C", verified=True),
    "Beijing": SettlementSpec("ZBAA", 40.0799, 116.6031, "ZBAA", unit="C",
                              verified=True, verification_status="verified",
                              notes="Beijing Capital International Airport Station via Wunderground ZBAA; verified from live Gamma rules on 2026-05-15 (https://www.wunderground.com/history/daily/cn/beijing/ZBAA). Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Lucknow": SettlementSpec("VILK", 26.7606, 80.8893, "VILK", unit="C",
                              verification_status="shadow",
                              notes="Amausi plausible; verify settlement source before live."),
    # 2026-05-10 expansion candidates with no station yet (paper/shadow only).
    "Hong Kong": SettlementSpec(None, 22.3193, 114.1694, None, unit="C",
                                verification_status="candidate",
                                notes="Polymarket may settle off Hong Kong Observatory (HKO) or VHHH airport — verify."),
    "Manila": SettlementSpec("RPLL", 14.5086, 121.0194, "RPLL", unit="C",
                             verified=True, verification_status="verified",
                             notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Ninoy Aquino International Airport Station (RPLL/NAIA) per Wunderground. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Kuala Lumpur": SettlementSpec("WMKK", 2.7456, 101.7099, "WMKK", unit="C",
                                   verified=True, verification_status="verified",
                                   notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Kuala Lumpur Intl Airport Station (WMKK/KLIA) per Wunderground. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Lagos": SettlementSpec("DNMM", 6.5774, 3.3211, "DNMM", unit="C",
                            verified=True, verification_status="verified",
                            notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Murtala Muhammad International Airport Station (DNMM) per Wunderground. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Sydney": SettlementSpec(None, -33.9399, 151.1753, "YSSY", unit="C",
                             verification_status="shadow",
                             notes="Phase B: obs_station=YSSY (Kingsford Smith) for METAR. Settlement still unverified; live blocked by station=None. BoM Observatory Hill remains a possibility."),
    "Helsinki": SettlementSpec(None, 60.3172, 24.9633, "EFHK", unit="C",
                               verification_status="shadow",
                               notes="Phase B: obs_station=EFHK (Vantaa) for METAR. Settlement still unverified; live blocked by station=None."),
    "Buenos Aires": SettlementSpec("SAEZ", -34.5592, -58.4156, "SAEZ", unit="C",
                                   verified=True, verification_status="verified",
                                   notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Minister Pistarini Intl Airport Station (SAEZ/Ezeiza) per Wunderground (https://www.wunderground.com/history/daily/ar/ezeiza/SAEZ). NOT SABE/Aeroparque. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Milan": SettlementSpec("LIMC", 45.6306, 8.7281, "LIMC", unit="C",
                            verified=True, verification_status="verified",
                            notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Malpensa Intl Airport Station (LIMC) per Wunderground. NOT LIML/Linate. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Tel Aviv": SettlementSpec(None, 32.0114, 34.8867, "LLBG", unit="C",
                               verification_status="shadow",
                               notes="Phase B: obs_station=LLBG (Ben Gurion) for METAR. Settlement still unverified; live blocked by station=None."),
    "Toronto": SettlementSpec(None, 43.6777, -79.6248, "CYYZ", unit="C",
                              verification_status="shadow",
                              notes="Phase B: obs_station=CYYZ (Pearson) for METAR. Settlement still unverified; live blocked by station=None."),
    "Madrid": SettlementSpec("LEMD", 40.4719, -3.5626, "LEMD", unit="C",
                             verified=True, verification_status="verified",
                             notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Adolfo Suarez Madrid-Barajas Airport Station (LEMD) per Wunderground (https://www.wunderground.com/history/daily/es/madrid/LEMD). Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Paris": SettlementSpec("LFPB", 48.9694, 2.4414, "LFPB", unit="C",
                            verified=True, verification_status="verified",
                            notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Paris-Le Bourget Airport Station (LFPB) per Wunderground (https://www.wunderground.com/history/daily/fr/bonneuil-en-france/LFPB). NOT LFPG/CDG. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Moscow": SettlementSpec(None, 55.9728, 37.4147, None, unit="C",
                             verification_status="rejected",
                             notes="UUEE (Sheremetyevo) candidate but rejected: no reliable METAR/settlement source available for Russia; data-source caution."),
    "Istanbul": SettlementSpec(None, 40.9769, 28.8146, None, unit="C",
                               verification_status="candidate",
                               notes="LTFM (new IST) or LTBA (Atatürk) — verify."),
    "Cape Town": SettlementSpec(None, -33.9648, 18.6017, "FACT", unit="C",
                                verification_status="shadow",
                                notes="Phase B: obs_station=FACT (Cape Town Intl) for METAR. Southern-hemisphere city; settlement still unverified."),
    "Jakarta": SettlementSpec(None, -6.1256, 106.6559, None, unit="C",
                              verification_status="candidate",
                              notes="WIII (Soekarno-Hatta) candidate; tropical UHI uncertainty."),
    "Qingdao": SettlementSpec("ZSQD", 36.2661, 120.3744, "ZSQD", unit="C",
                              verified=True, verification_status="verified",
                              notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Qingdao Jiaodong International Airport Station (ZSQD) per Wunderground. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Shenzhen": SettlementSpec("ZGSZ", 22.6394, 113.8108, "ZGSZ", unit="C",
                               verified=True, verification_status="verified",
                               notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Shenzhen Bao'an International Airport Station (ZGSZ) per Wunderground. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Taipei": SettlementSpec("RCSS", 25.0697, 121.5519, "RCSS", unit="C",
                             verified=True, verification_status="verified",
                             notes="Phase B tiny-live approval 2026-05-10: Polymarket settles off Taipei Songshan Airport Station (RCSS) per Wunderground. NOT RCTP/Taoyuan. Non-US live still requires BOT_D_INTERNATIONAL_LIVE_ENABLED=true and two agreeing API/model sources."),
    "Wuhan": SettlementSpec(None, 30.5928, 114.3055, None, unit="C",
                            verification_status="candidate",
                            notes="Seen in live discovery on 2026-05-11. Settlement station/source unverified; live blocked."),
    "Guangzhou": SettlementSpec(None, 23.1291, 113.2644, None, unit="C",
                                verification_status="candidate",
                                notes="Seen in live discovery on 2026-05-11. Settlement station/source unverified; live blocked."),
    "Karachi": SettlementSpec(None, 24.8607, 67.0011, None, unit="C",
                              verification_status="candidate",
                              notes="Seen in live discovery on 2026-05-11. Settlement station/source unverified; live blocked."),
    "Panama City": SettlementSpec(None, 8.9824, -79.5199, None, unit="C",
                                  verification_status="candidate",
                                  notes="Seen in live discovery on 2026-05-11. Settlement station/source unverified; live blocked."),
    "Ankara": SettlementSpec(None, 39.9334, 32.8597, None, unit="C",
                             verification_status="candidate",
                             notes="Seen in live discovery on 2026-05-11. Settlement station/source unverified; live blocked."),
}


def is_live_eligible(city_key: str) -> bool:
    """True only when city has a verified settlement spec."""
    spec = SETTLEMENT_SPECS.get(city_key)
    return bool(spec and spec.verified and spec.station)


def verification_status(city_key: str) -> str:
    """Return one of: unknown, candidate, shadow, verified, rejected."""
    if city_key not in CITIES:
        return "unknown"
    spec = SETTLEMENT_SPECS.get(city_key)
    if spec is None:
        return "unknown"
    return spec.status


def forecast_coordinates(city_key: str) -> tuple[float, float]:
    """Return model-pull coordinates, preferring verified settlement station."""
    spec = SETTLEMENT_SPECS.get(city_key)
    if spec is not None:
        return spec.forecast_lat, spec.forecast_lon
    cfg = CITIES[city_key]
    return cfg.lat, cfg.lon


def observation_station(city_key: str) -> str | None:
    """Return the station ID used for intraday observations, if configured."""
    spec = SETTLEMENT_SPECS.get(city_key)
    if spec is not None:
        return spec.obs_station or spec.station
    return None


def settlement_coverage_rows() -> list[dict[str, object]]:
    """Return station/source coverage for active Bot D cities."""
    rows: list[dict[str, object]] = []
    for city_key in sorted(CITIES):
        cfg = CITIES[city_key]
        spec = SETTLEMENT_SPECS.get(city_key)
        rows.append(
            {
                "city": city_key,
                "station": spec.station if spec else None,
                "obs_station": (spec.obs_station or spec.station) if spec else None,
                "source": spec.source if spec else "city_center_fallback",
                "rounding": spec.rounding if spec else "nearest_int",
                "unit": spec.unit if spec else "F",
                "verified": bool(spec.verified) if spec else False,
                "verification_status": spec.status if spec else "unknown",
                "verification_notes": spec.notes if spec else "",
                "forecast_lat": spec.forecast_lat if spec else cfg.lat,
                "forecast_lon": spec.forecast_lon if spec else cfg.lon,
                "live_eligible": bool(spec and spec.verified and spec.station),
            }
        )
    return rows


def _f_to_c(fahrenheit: float) -> float:
    return (fahrenheit - 32.0) * 5.0 / 9.0


def _c_to_f(celsius: float) -> float:
    return celsius * 9.0 / 5.0 + 32.0


def _nearest_int_half_up(value: float) -> int:
    value = round(value, 6)
    if value >= 0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)


def settlement_value_for_rounding(
    city_key: str,
    raw_temp_f: float,
    rounding: str | None = None,
) -> float:
    """Apply a named settlement rounding rule and return Fahrenheit.

    Bot D normalizes market ranges to Fahrenheit. For Celsius-settled cities,
    round in Celsius first, then convert the settled value back to Fahrenheit
    for comparison with parsed market buckets.
    """
    spec = SETTLEMENT_SPECS.get(city_key)
    unit = (spec.unit if spec else "F").upper()
    selected_rounding = rounding or (spec.rounding if spec else "nearest_int")
    native = _f_to_c(raw_temp_f) if unit == "C" else raw_temp_f
    if selected_rounding in {"floor", "truncate"}:
        settled_native = math.floor(native)
    elif selected_rounding == "exact":
        settled_native = native
    else:
        settled_native = _nearest_int_half_up(native)
    return _c_to_f(float(settled_native)) if unit == "C" else float(settled_native)


def apply_settlement_value(city_key: str, raw_temp_f: float) -> float:
    """Apply the configured settlement rounding and return Fahrenheit."""
    return settlement_value_for_rounding(city_key, raw_temp_f)


# --- Seasonal RMSE adjustment (audit 2026-04-17, GLM-5.1/Codex P1) ---------
# Annual-average RMSE is systematically overconfident in winter (high vol)
# and underconfident in summer (stable patterns). Reviewer evidence:
#   summer: 1.5-2.0°F    (multiplier ~0.70)
#   winter: 3.0-4.0°F    (multiplier ~1.40)
#   spring/fall: 2.0-3.0°F (multiplier ~1.00)
# These multipliers are applied to the city's annual `rmse_f` to produce a
# month-adjusted RMSE. `BOT_D_RMSE_SEASONAL=true` (default) enables; set
# false to revert to annual-only.
_SEASONAL_RMSE_MULTIPLIER_NORTHERN: dict[int, float] = {
    1: 1.40, 2: 1.40, 3: 1.10,     # winter / early spring
    4: 1.00, 5: 0.90, 6: 0.75,     # spring / early summer
    7: 0.70, 8: 0.70, 9: 0.90,     # summer / early autumn
    10: 1.00, 11: 1.20, 12: 1.40,  # autumn / winter
}
_SEASONAL_RMSE_MULTIPLIER_SOUTHERN: dict[int, float] = {
    m: _SEASONAL_RMSE_MULTIPLIER_NORTHERN[((m + 5) % 12) + 1]
    for m in range(1, 13)
}


def seasonal_rmse_multiplier(month: int, southern_hemisphere: bool = False) -> float:
    """Return the seasonal multiplier for `rmse_f` given a 1-12 month."""
    if month < 1 or month > 12:
        return 1.0
    table = (
        _SEASONAL_RMSE_MULTIPLIER_SOUTHERN
        if southern_hemisphere
        else _SEASONAL_RMSE_MULTIPLIER_NORTHERN
    )
    return table[month]


def effective_rmse_f(city_cfg: CityConfig, month: int) -> float:
    """Return the seasonally-adjusted RMSE in °F for a city and month.

    Falls back to the annual baseline if BOT_D_RMSE_SEASONAL is false.
    """
    if not BOT_D_RMSE_SEASONAL:
        return city_cfg.rmse_f
    mult = seasonal_rmse_multiplier(month, city_cfg.southern_hemisphere)
    return city_cfg.rmse_f * mult


def resolve_city(text: str) -> str | None:
    """Match a city name from a Polymarket question to our registry.

    M-04 fix: match LONGEST alias first to prevent "la" matching inside
    "kuala lumpur", "atlanta", or "dallas". Aliases are sorted by length
    descending so "kuala lumpur" is tried before "la", "los angeles"
    before "la", etc.
    """
    text_lower = text.lower().strip()
    # Build a flat list of (alias, city_key) sorted by alias length DESC.
    # Longest match wins — "kuala lumpur" beats "la".
    candidates: list[tuple[str, str]] = []
    for city_key, cfg in CITIES.items():
        for alias in cfg.aliases:
            candidates.append((alias, city_key))
    candidates.sort(key=lambda x: len(x[0]), reverse=True)
    for alias, city_key in candidates:
        if alias in text_lower:
            return city_key
    return None


# --- Trading parameters (env-overridable) ------------------------------------

def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


# Seasonal RMSE mode (audit 2026-04-17 P1). Default enabled.
BOT_D_RMSE_SEASONAL = _env("BOT_D_RMSE_SEASONAL", "true").strip().lower() == "true"

# Skew-normal CDF for extreme-temp markets (audit 2026-04-17 P1).
# Gaussian underestimates upper-tail of daily high temperature. Enables
# scipy.stats.skewnorm with a fixed positive skew for high-temp markets
# (negative skew for low-temp). When disabled, keeps pure Gaussian.
BOT_D_USE_SKEW_NORMAL = _env("BOT_D_USE_SKEW_NORMAL", "true").strip().lower() == "true"
# Fixed skewness parameter (scipy `a` parameter). +ve = fatter upper tail.
BOT_D_SKEW_HIGH = float(_env("BOT_D_SKEW_HIGH", "2.0"))
BOT_D_SKEW_LOW = float(_env("BOT_D_SKEW_LOW", "-2.0"))

# Phase 3 audit 2026-04-17: raised from 0.08 to 0.10. The 8% floor was
# being hit by 70%+ buckets (all 11 paper positions), indicating edge
# measurement was dominated by the "fade the unlikely" subtype rather
# than genuine statistical edge. 10% is a tighter filter until measured
# win rate validates a lower threshold.
# NOTE: live service (polymarket-bot-d-live.service) overrides this to
# 0.07 for the tiny-live plumbing probe. Paper and live defaults diverge
# intentionally; do not "align" them without a resolved-sample ADR.
BOT_D_EDGE_THRESHOLD = float(_env("BOT_D_EDGE_THRESHOLD", "0.10"))
BOT_D_EMPIRICAL_DISAGREE_THRESHOLD = float(_env("BOT_D_EMPIRICAL_DISAGREE_THRESHOLD", "0.10"))
BOT_D_EMPIRICAL_MIN_MEMBERS = int(_env("BOT_D_EMPIRICAL_MIN_MEMBERS", "5"))
BOT_D_NWS_VETO_MIN_THRESHOLD_F = float(_env("BOT_D_NWS_VETO_MIN_THRESHOLD_F", "2.0"))
# Paper-only trade-flow probe: NWS veto remains the default, but strong
# model-vs-market edges can override the veto in paper so we can measure
# whether the NWS second opinion is filtering winners or saving us.
BOT_D_NWS_VETO_OVERRIDE_ENABLED = (
    _env("BOT_D_NWS_VETO_OVERRIDE_ENABLED", "true").strip().lower() == "true"
)
BOT_D_NWS_VETO_OVERRIDE_MIN_EDGE = float(_env("BOT_D_NWS_VETO_OVERRIDE_MIN_EDGE", "0.15"))
BOT_D_NWS_OUTLIER_PROBE_ENABLED = (
    _env("BOT_D_NWS_OUTLIER_PROBE_ENABLED", "false").strip().lower() == "true"
)
BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE = float(_env("BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE", "0.08"))
BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F = float(_env("BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F", "2.0"))
BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F = float(_env("BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F", "6.0"))

# Blacklist "exact X°F" narrow-bucket markets (audit 2026-04-17 Gemini).
# These are 1°F-wide buckets that function as thin-liquidity lotteries;
# the Gaussian / skew-normal model assigns near-zero probability and the
# edge math is dominated by model error, not real mispricing.
BOT_D_BLACKLIST_EXACT_TEMP = _env("BOT_D_BLACKLIST_EXACT_TEMP", "true").strip().lower() == "true"
BOT_D_PER_TRADE_USD = Decimal(_env("BOT_D_PER_TRADE_USD", "50"))
BOT_D_BANKROLL_USD = Decimal(_env("BOT_D_BANKROLL_USD", "500"))
BOT_D_MAX_CONCURRENT_POSITIONS = int(_env("BOT_D_MAX_CONCURRENT_POSITIONS", "10"))
BOT_D_SCAN_INTERVAL_S = float(_env("BOT_D_SCAN_INTERVAL_S", "300"))  # 5 minutes
BOT_D_MIN_VOLUME_24H_USD = Decimal(_env("BOT_D_MIN_VOLUME_24H_USD", "50"))
BOT_D_LIMIT_OFFSET = Decimal(_env("BOT_D_LIMIT_OFFSET", "0.00"))
BOT_D_KELLY_FRACTION = float(_env("BOT_D_KELLY_FRACTION", "0.15"))
BOT_D_ENTRY_HALT = _env("BOT_D_ENTRY_HALT", "false").strip().lower() == "true"
BOT_D_BOT_ID = _env("BOT_D_ID_OVERRIDE", "bot_d").strip() or "bot_d"
# Live entry authorization is intentionally separate from BOT_D_ENV and the
# global POLYMARKET_ENV. A live-mode process still refuses entries unless the
# operator has explicitly authorized the current readiness snapshot.
BOT_D_LIVE_AUTHORIZED = _env("BOT_D_LIVE_AUTHORIZED", "false").strip().lower() == "true"
BOT_D_LIVE_APPROVED_AT = _env("BOT_D_LIVE_APPROVED_AT", "").strip()
BOT_D_LIVE_PROBE_MODE = _env("BOT_D_LIVE_PROBE_MODE", "").strip().lower()
BOT_D_LIVE_WALLET_USD = Decimal(_env("BOT_D_LIVE_WALLET_USD", "200"))
BOT_D_LIVE_FIXED_SHARES = Decimal(_env("BOT_D_LIVE_FIXED_SHARES", "0"))
BOT_D_LIVE_SIZING_MODE = _env("BOT_D_LIVE_SIZING_MODE", "fixed").strip().lower()
BOT_D_LIVE_MAX_DYNAMIC_SHARES = Decimal(_env("BOT_D_LIVE_MAX_DYNAMIC_SHARES", "40"))
if BOT_D_LIVE_SIZING_MODE not in {"fixed", "evidence_gated"}:
    raise RuntimeError("BOT_D_LIVE_SIZING_MODE must be fixed or evidence_gated")
BOT_D_LIVE_MAX_ORDER_USD = Decimal(_env("BOT_D_LIVE_MAX_ORDER_USD", "4"))
BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD = Decimal(_env("BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD", "1.00"))
BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD = Decimal(
    _env("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "50")
)
BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD = Decimal(_env("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "50"))
BOT_D_LIVE_MAX_CONCURRENT_POSITIONS = int(_env("BOT_D_LIVE_MAX_CONCURRENT_POSITIONS", "10"))
if (
    BOT_D_LIVE_PROBE_MODE == "plumbing"
    and (
        _env("BOT_D_ENV", "paper").strip().lower() == "live"
        or _env("POLYMARKET_ENV", "paper").strip().lower() == "live"
    )
    and BOT_D_LIVE_SIZING_MODE == "fixed"
    and BOT_D_LIVE_FIXED_SHARES <= 0
):
    raise RuntimeError("BOT_D_LIVE_FIXED_SHARES must be > 0 for Bot D live plumbing mode")
# NWS-only fallback forecasts are useful for paper diagnostics, but they are
# not an independent model ensemble. Default to no entries from this source.
BOT_D_ALLOW_NWS_FALLBACK_ENTRY = (
    _env("BOT_D_ALLOW_NWS_FALLBACK_ENTRY", "false").strip().lower() == "true"
)
BOT_D_INTERNATIONAL_LIVE_ENABLED = (
    _env("BOT_D_INTERNATIONAL_LIVE_ENABLED", "false").strip().lower() == "true"
)
BOT_D_REQUIRE_INTERNATIONAL_API_AGREEMENT = (
    _env("BOT_D_REQUIRE_INTERNATIONAL_API_AGREEMENT", "true").strip().lower() == "true"
)
BOT_D_INTERNATIONAL_MIN_API_AGREEMENT = int(_env("BOT_D_INTERNATIONAL_MIN_API_AGREEMENT", "2"))
BOT_D_INTERNATIONAL_MAX_API_GAP_F = float(_env("BOT_D_INTERNATIONAL_MAX_API_GAP_F", "6.0"))
# Expensive-NO guard (2026-05-13, distance gate restored 2026-05-14 under
# ADR-160): an 80c+ NO on a 1F bucket can still lose the full stake when the
# forecast mean sits close to the bucket or when the setup is only C-tier.
# Require source agreement, distance from the bucket (4.0F or 2*sigma,
# whichever is larger), and a stronger model edge for weaker setup tiers.
# ADR-160 also bundles a premium-tier NO sizing ladder so the dollar loss on
# any single miss in the 0.85-0.95 band is capped well below the prior flat
# 10-share size.
BOT_D_EXPENSIVE_NO_GUARD_ENABLED = (
    _env("BOT_D_EXPENSIVE_NO_GUARD_ENABLED", "true").strip().lower() == "true"
)
BOT_D_EXPENSIVE_NO_GUARD_MIN_PRICE = Decimal(
    _env("BOT_D_EXPENSIVE_NO_GUARD_MIN_PRICE", "0.80")
)
BOT_D_BLOCK_BUY_NO_MEAN_INSIDE_BUCKET = (
    _env("BOT_D_BLOCK_BUY_NO_MEAN_INSIDE_BUCKET", "true").strip().lower() == "true"
)
BOT_D_EXPENSIVE_NO_MIN_API_AGREEMENT = int(
    _env("BOT_D_EXPENSIVE_NO_MIN_API_AGREEMENT", "2")
)
BOT_D_EXPENSIVE_NO_MAX_API_GAP_F = float(
    _env("BOT_D_EXPENSIVE_NO_MAX_API_GAP_F", "2.0")
)
BOT_D_EXPENSIVE_NO_MIN_DISTANCE_F = float(
    _env("BOT_D_EXPENSIVE_NO_MIN_DISTANCE_F", "4.0")
)
BOT_D_EXPENSIVE_NO_MIN_DISTANCE_STD_MULT = float(
    _env("BOT_D_EXPENSIVE_NO_MIN_DISTANCE_STD_MULT", "2.0")
)
BOT_D_EXPENSIVE_NO_TIER_C_MIN_EDGE = Decimal(
    _env("BOT_D_EXPENSIVE_NO_TIER_C_MIN_EDGE", "0.12")
)
# Premium-tier NO sizing ladder (ADR-160, 2026-05-14). BUY_NO entries get
# smaller share counts as the limit price rises, because the loss-on-miss is
# the full stake. Defaults are paired with `BOT_D_LIVE_FIXED_SHARES=15` as
# the `<0.60` base tier in `_live_size_shares`. The exchange-side
# `MIN_POLYMARKET_SHARES=5` floor still clamps the runtime size upward, so
# the `_VERY_HIGH=3` config value reflects intent and the runtime size will
# be `5` until the exchange floor is lowered separately.
BOT_D_LIVE_NO_SHARES_MID = Decimal(_env("BOT_D_LIVE_NO_SHARES_MID", "10"))
BOT_D_LIVE_NO_SHARES_HIGH = Decimal(_env("BOT_D_LIVE_NO_SHARES_HIGH", "6"))
BOT_D_LIVE_NO_SHARES_VERY_HIGH = Decimal(_env("BOT_D_LIVE_NO_SHARES_VERY_HIGH", "3"))
BOT_D_LIVE_NO_PREMIUM_HARD_SKIP = Decimal(_env("BOT_D_LIVE_NO_PREMIUM_HARD_SKIP", "0.95"))
# Live-shaped execution evidence: require visible ask-side capacity before a
# paper/live entry is allowed to count. This prevents synthetic paper fills
# from making thin markets look wallet-ready.
BOT_D_DEPTH_GATE_ENABLED = _env("BOT_D_DEPTH_GATE_ENABLED", "true").strip().lower() == "true"
BOT_D_MIN_ENTRY_DEPTH_USD = Decimal(_env("BOT_D_MIN_ENTRY_DEPTH_USD", "25"))
# Fast-ROI Bot D lane: avoid locking bankroll in longer weather holds while
# the daily subset is being proven for first wallet candidacy.
BOT_D_MAX_LOCKUP_HOURS = float(_env("BOT_D_MAX_LOCKUP_HOURS", "48"))
# Never enter already-ended or nearly-ended markets from stale Gamma rows. A
# small positive floor also prevents late-day weather markets from being bought
# after the forecast thesis can no longer be expressed safely.
BOT_D_MIN_ENTRY_HOURS_TO_END = float(_env("BOT_D_MIN_ENTRY_HOURS_TO_END", "2"))
BOT_D_REQUIRE_KNOWN_END_DATE = (
    _env("BOT_D_REQUIRE_KNOWN_END_DATE", "true").strip().lower() == "true"
)
BOT_D_REQUIRE_VERIFIED_SETTLEMENT = (
    _env("BOT_D_REQUIRE_VERIFIED_SETTLEMENT", "true").strip().lower() == "true"
)
BOT_D_PAPER_EXIT_SLIPPAGE_BPS = Decimal(_env("BOT_D_PAPER_EXIT_SLIPPAGE_BPS", "50"))
BOT_D_LIVE_EXIT_LIMIT_OFFSET = Decimal(_env("BOT_D_LIVE_EXIT_LIMIT_OFFSET", "0.005"))
BOT_D_EXIT_STALE_MIN = int(_env("BOT_D_EXIT_STALE_MIN", "10"))
BOT_D_TAKE_PROFIT_ENABLED = (
    _env("BOT_D_TAKE_PROFIT_ENABLED", "false").strip().lower() == "true"
)
BOT_D_TAKE_PROFIT_MIN_BID = Decimal(_env("BOT_D_TAKE_PROFIT_MIN_BID", "0.99"))
BOT_D_TAKE_PROFIT_LIMIT_OFFSET = Decimal(_env("BOT_D_TAKE_PROFIT_LIMIT_OFFSET", "0.001"))
BOT_D_TAKE_PROFIT_MIN_HOURS_TO_END = float(_env("BOT_D_TAKE_PROFIT_MIN_HOURS_TO_END", "0"))
BOT_D_POSITION_VALIDATION_ENABLED = (
    _env("BOT_D_POSITION_VALIDATION_ENABLED", "true").strip().lower() == "true"
)
BOT_D_POSITION_AUTO_SELL_ENABLED = (
    _env("BOT_D_POSITION_AUTO_SELL_ENABLED", "false").strip().lower() == "true"
)
BOT_D_POSITION_PRICE_ONLY_STOP_ENABLED = (
    _env("BOT_D_POSITION_PRICE_ONLY_STOP_ENABLED", "false").strip().lower() == "true"
)
BOT_D_POSITION_STOP_LOSS_PCT = Decimal(_env("BOT_D_POSITION_STOP_LOSS_PCT", "0.35"))
BOT_D_POSITION_RAW_WARN_DISTANCE_F = float(_env("BOT_D_POSITION_RAW_WARN_DISTANCE_F", "1.0"))
# Session 28 tactical sizing: keep tail-risk protection, but stop cutting
# the 2-5c weather subtype to only 30% of normal size. Defaults make 5c and
# cheaper tickets size at 60% of BOT_D_PER_TRADE_USD, then interpolate back
# to full size by 20c.
BOT_D_TAIL_CAP_FLOOR = Decimal(_env("BOT_D_TAIL_CAP_FLOOR", "0.60"))
BOT_D_TAIL_CAP_START = Decimal(_env("BOT_D_TAIL_CAP_START", "0.05"))
BOT_D_TAIL_CAP_END = Decimal(_env("BOT_D_TAIL_CAP_END", "0.20"))

# Session 32 wave-regime sizing: full-size entries only when multiple
# same-day/same-side weather tails are mispriced together. Isolated entries
# still run, but at reduced size so they collect data without dominating bleed.
BOT_D_WAVE_FILTER_ENABLED = _env("BOT_D_WAVE_FILTER_ENABLED", "true").strip().lower() == "true"
BOT_D_WAVE_MIN_MARKETS = int(_env("BOT_D_WAVE_MIN_MARKETS", "3"))
BOT_D_WAVE_SIZE_FACTOR = Decimal(_env("BOT_D_WAVE_SIZE_FACTOR", "1.00"))
BOT_D_ISOLATED_SIZE_FACTOR = Decimal(_env("BOT_D_ISOLATED_SIZE_FACTOR", "0.50"))
BOT_D_REQUIRE_WAVE_FOR_ENTRY = (
    _env("BOT_D_REQUIRE_WAVE_FOR_ENTRY", "true").strip().lower() == "true"
)

# Trading mode (independent of global POLYMARKET_ENV and Bot C's BOT_C_ENV).
BOT_D_ENV = _env("BOT_D_ENV", "paper").strip().lower()

# Paper-performance epoch. This does not delete legacy Bot D data; it gives
# dashboards and audit events a clean "station-fix model" cohort boundary.
BOT_D_PAPER_EPOCH_ID = _env("BOT_D_PAPER_EPOCH_ID", "station_v1_2026_04_29")
BOT_D_PAPER_EPOCH_START = _env("BOT_D_PAPER_EPOCH_START", "2026-04-29T19:10:00+00:00")
BOT_D_SOURCE_SNAPSHOT_ENABLED = (
    _env("BOT_D_SOURCE_SNAPSHOT_ENABLED", "true").strip().lower() == "true"
)
BOT_D_FINAL_SOURCE_POLL_ENABLED = (
    _env("BOT_D_FINAL_SOURCE_POLL_ENABLED", "true").strip().lower() == "true"
)
BOT_D_FINAL_SOURCE_CACHE_TTL_SEC = int(_env("BOT_D_FINAL_SOURCE_CACHE_TTL_SEC", "300"))
BOT_D_WEATHERCOM_API_KEY = _env("BOT_D_WEATHERCOM_API_KEY", "").strip()
BOT_D_TOMORROW_SHADOW_ENABLED = (
    _env("BOT_D_TOMORROW_SHADOW_ENABLED", "true").strip().lower() == "true"
)
BOT_D_TOMORROW_CACHE_TTL_SEC = int(_env("BOT_D_TOMORROW_CACHE_TTL_SEC", "3600"))
BOT_D_TOMORROW_TIMEOUT_SEC = float(_env("BOT_D_TOMORROW_TIMEOUT_SEC", "15"))
TOMORROW_API_KEY = _env("TOMORROW_API_KEY", "").strip()

# Open-Meteo endpoints
OPEN_METEO_ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TOMORROW_FORECAST_URL = "https://api.tomorrow.io/v4/weather/forecast"
