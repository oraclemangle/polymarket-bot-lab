"""Weather edge calculator — Gaussian CDF of ensemble forecast vs Polymarket price.

Core logic ported from little-rocky's edge_calculator.py. Key improvements:
- Supports both high and low temperature markets
- Computes adjusted sigma = sqrt(ensemble_spread^2 + city_rmse^2) for robustness
- Enforces one-bet-per-event: only the highest-edge range per (city, date)
- Fee netting from Bot C's strategy.py
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

from bots.bot_d_weather import config as bot_d_config
from bots.bot_d_weather.config import (
    BOT_D_EDGE_THRESHOLD,
    CITIES,
    apply_settlement_value,
    effective_rmse_f,
)
from bots.bot_d_weather.discovery import WeatherMarket
from bots.bot_d_weather.weather_fetcher import ForecastResult
from core.fees import taker_fee_per_share as _core_taker_fee_per_share

log = logging.getLogger(__name__)


_SKEWNORM_FALLBACK_WARNED = False


def _emit_skewnorm_fallback_event(exc: Exception) -> None:
    try:
        from core.db import Event, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            s.add(Event(
                bot_id=bot_d_config.BOT_D_BOT_ID,
                event_type="bot_d.skewnorm_fallback",
                severity="warn",
                message="Bot D skew-normal CDF fell back to Gaussian",
                payload={"error": f"{type(exc).__name__}: {exc}"},
            ))
            s.commit()
    except Exception as event_exc:
        log.debug("bot_d.skewnorm_fallback_event_failed err=%s", event_exc)


def _skewnorm_cdf(x: float, mean: float, std: float, skew: float) -> float:
    """Skew-normal CDF (scipy). Falls back to Gaussian on any import error.

    K2.6 audit 2026-04-21 (bug #6A): silent DEBUG fallback let scipy
    import failures degrade the model to a thinner-tailed Gaussian
    without the operator noticing, which would systematically *overbet*
    tail markets. Now logs WARNING once per process so prod drift is
    surfaced, and still once per-call at DEBUG for full traceability.
    """
    global _SKEWNORM_FALLBACK_WARNED
    try:
        from scipy.stats import skewnorm
        return float(skewnorm.cdf(x, skew, loc=mean, scale=std))
    except Exception as exc:
        if not _SKEWNORM_FALLBACK_WARNED:
            log.warning(
                "bot_d.skewnorm_fallback err=%s — model degraded to pure "
                "Gaussian; tail markets will be mispriced until scipy is "
                "restored",
                exc,
            )
            _emit_skewnorm_fallback_event(exc)
            _SKEWNORM_FALLBACK_WARNED = True
        else:
            log.debug("bot_d.skewnorm_fallback err=%s", exc)
        return float(_normal_cdf(x, mean, std))


def _range_probability_with_shape(
    mean: float, std: float,
    low: float | None, high: float | None,
    *, temp_type: str,
) -> float:
    """P(low <= X <= high) using skew-normal (if enabled) or Gaussian.

    Temp_type selects the skew parameter: "high" → positive (fatter upper
    tail), "low" → negative (fatter lower tail). Unknown types fall back
    to Gaussian.
    """
    if std <= 0:
        std = 0.01
    if low is None and high is None:
        return 0.5
    if bot_d_config.BOT_D_USE_SKEW_NORMAL and temp_type in ("high", "low"):
        skew = (
            bot_d_config.BOT_D_SKEW_HIGH if temp_type == "high"
            else bot_d_config.BOT_D_SKEW_LOW
        )

        def cdf(x: float) -> float:
            return _skewnorm_cdf(x, mean, std, skew)
    else:

        def cdf(x: float) -> float:
            return _normal_cdf(x, mean, std)
    if low is None:
        return float(cdf(high))
    if high is None:
        return float(1.0 - cdf(low))
    return float(cdf(high) - cdf(low))


def _polymarket_taker_fee(p: float) -> float:
    """Parabolic taker fee for Bot D (weather), returned as USDC PER SHARE.

    Delegates to `core.fees.taker_fee_per_share`. For weather
    (feeRate=0.05), peak = $0.0125/share at p=0.5. Callers must
    multiply by SHARES to get USDC fee on the fill (do NOT multiply by
    notional — that was the bug fixed 2026-04-22 per Codex fleet review).
    """
    p_clamped = max(0.001, min(0.999, p))
    return float(_core_taker_fee_per_share(p_clamped, "weather"))


def _normal_cdf(x: float, mean: float, std: float) -> float:
    """Normal CDF: P(X ≤ x) for X ~ N(mean, std)."""
    z = (x - mean) / (std * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


def range_probability(
    mean: float, std: float,
    low: float | None, high: float | None,
) -> float:
    """P(low ≤ X ≤ high) for X ~ Normal(mean, std).

    low=None → below high (P(X ≤ high))
    high=None → above low (P(X ≥ low))
    """
    if std <= 0:
        std = 0.01
    if low is None and high is None:
        return 0.5
    if low is None:
        return float(_normal_cdf(high, mean, std))
    if high is None:
        return float(1.0 - _normal_cdf(low, mean, std))
    return float(_normal_cdf(high, mean, std) - _normal_cdf(low, mean, std))


def empirical_bucket_probability(
    city: str,
    member_values_f: tuple[float, ...],
    low: float | None,
    high: float | None,
) -> float | None:
    """Estimate bucket probability by counting rounded ensemble members.

    Market ranges are stored in Fahrenheit. The settlement helper applies any
    city-native rounding first, then converts back to Fahrenheit before bucket
    comparison.
    """
    if not member_values_f:
        return None
    hits = 0
    for raw in member_values_f:
        settled = apply_settlement_value(city, raw)
        if low is not None and settled < low:
            continue
        if high is not None and settled > high:
            continue
        hits += 1
    return hits / len(member_values_f)


def _observed_settlement_probability(
    market: WeatherMarket,
    forecast: ForecastResult,
) -> tuple[float, str] | None:
    """Hard probability constraints from intraday station observations."""
    if market.temp_type == "high" and forecast.metar_max_so_far_f is not None:
        observed = apply_settlement_value(market.city, forecast.metar_max_so_far_f)
        if (
            market.range_low_f is None
            and market.range_high_f is not None
            and observed > market.range_high_f
        ):
            return 0.0, f"observed_high_exceeds_bucket (settled={observed:.1f})"
        if (
            market.range_low_f is not None
            and market.range_high_f is None
            and observed >= market.range_low_f
        ):
            return 1.0, f"observed_high_reached_threshold (settled={observed:.1f})"
    if market.temp_type == "low" and forecast.metar_min_so_far_f is not None:
        observed = apply_settlement_value(market.city, forecast.metar_min_so_far_f)
        if (
            market.range_low_f is not None
            and market.range_high_f is None
            and observed < market.range_low_f
        ):
            return 0.0, f"observed_low_below_bucket (settled={observed:.1f})"
        if (
            market.range_low_f is None
            and market.range_high_f is not None
            and observed <= market.range_high_f
        ):
            return 1.0, f"observed_low_reached_threshold (settled={observed:.1f})"
    return None


@dataclass(frozen=True)
class WeatherEdgeDecision:
    market: WeatherMarket
    gfs_probability: float
    market_probability: float
    gross_edge: float
    net_edge: float
    edge: float  # alias for net_edge (compat)
    side: str  # "BUY_YES" | "BUY_NO" | "SKIP"
    reason: str
    forecast_mean_f: float
    forecast_std_f: float
    ensemble_count: int
    decided_at: datetime
    forecast_source: str | None = None
    forecast_fetched_at: datetime | None = None
    forecast_model_timestamp: str | None = None
    api_highs_f: tuple[tuple[str, float], ...] = ()
    api_lows_f: tuple[tuple[str, float], ...] = ()
    nws_gap_f: float | None = None
    api_agreement_count: int = 0
    api_agreement_max_gap_f: float | None = None
    nws_outlier_probe: bool = False
    empirical_probability: float | None = None
    probability_disagreement: float | None = None
    settlement_constraint: str | None = None
    regime: str = "unclassified"  # "wave" | "isolated" | "unclassified"
    wave_key: str | None = None
    wave_count: int = 1
    size_multiplier: Decimal = Decimal("1.00")


def _best_api_agreement(
    values: tuple[tuple[str, float], ...],
    *,
    max_gap_f: float,
) -> tuple[int, float | None]:
    """Return the largest non-NWS source cluster within the allowed gap."""
    clean = sorted(
        ((name, float(value)) for name, value in values if math.isfinite(float(value))),
        key=lambda item: item[1],
    )
    if len(clean) < 2:
        return len(clean), None
    best_count = 1
    best_gap: float | None = None
    for start in range(len(clean)):
        low = clean[start][1]
        for end in range(start, len(clean)):
            gap = clean[end][1] - low
            if gap > max_gap_f:
                break
            count = end - start + 1
            if count > best_count or (
                count == best_count and (best_gap is None or gap < best_gap)
            ):
                best_count = count
                best_gap = gap
    return best_count, best_gap


def evaluate_weather_market(
    market: WeatherMarket,
    forecast: ForecastResult,
    *,
    edge_threshold: float = BOT_D_EDGE_THRESHOLD,
) -> WeatherEdgeDecision:
    """Compute edge for one weather market using Gaussian CDF."""
    now = datetime.now(UTC)

    # Pick the right mean/std based on high vs low
    if market.temp_type == "high":
        mean = forecast.mean_high_f
        raw_std = forecast.std_high_f
    else:
        mean = forecast.mean_low_f
        raw_std = forecast.std_low_f

    # Audit fix #2: METAR real-time adjustment for same-day markets.
    # If we have a fresh airport observation (<120 min old) and it's for
    # today's high-temperature market, the observed temp is a FLOOR on the
    # daily high. If METAR already exceeds the ensemble mean, shift the
    # mean upward — the high can only go higher from here.
    if (
        forecast.metar_temp_f is not None
        and forecast.metar_age_minutes is not None
        and forecast.metar_age_minutes < 120
        and market.temp_type == "high"
        and forecast.metar_temp_f > mean
    ):
        # Phase 3 audit 2026-04-17 (GLM-5.1 Q13): apply urban-heat-island
        # offset. METAR is airport temperature; city-core high can run
        # 1-2 deg F warmer. CityConfig.urban_heat_island_f carries the delta.
        city_cfg_for_uhi = CITIES.get(market.city)
        uhi = city_cfg_for_uhi.urban_heat_island_f if city_cfg_for_uhi else 0.0
        new_mean = forecast.metar_temp_f + uhi
        log.debug(
            "metar+uhi adjustment %s: mean %.1f -> %.1f (metar=%.1f, uhi=+%.1f, age=%.0fmin)",
            market.city, mean, new_mean, forecast.metar_temp_f, uhi,
            forecast.metar_age_minutes,
        )
        mean = new_mean

    # Combine ensemble spread with city RMSE for a more robust sigma.
    # Audit 2026-04-17 (GLM-5.1/Codex P1): RMSE is seasonal. A Jan forecast
    # in NYC is about 2x less accurate than a July forecast. Use the month of
    # the market's resolution date rather than the city's annual average.
    city_cfg = CITIES.get(market.city)
    if city_cfg is not None:
        try:
            month = datetime.strptime(market.date, "%Y-%m-%d").month
        except Exception:
            month = now.month
        rmse = effective_rmse_f(city_cfg, month)
    else:
        rmse = 2.5
    adjusted_std = math.sqrt(raw_std ** 2 + rmse ** 2)

    # Compute GFS probability for this temperature range.
    # Audit 2026-04-17 (GLM-5.1 Q10 / Gemini / Codex P1): use skew-normal
    # for extreme-temp markets. Fatter upper tail for "high" markets,
    # fatter lower tail for "low". Config-gated; falls back to Gaussian.
    cdf_prob = _range_probability_with_shape(
        mean=mean,
        std=adjusted_std,
        low=market.range_low_f,
        high=market.range_high_f,
        temp_type=market.temp_type,
    )
    gfs_prob = cdf_prob

    member_values = (
        forecast.member_highs_f
        if market.temp_type == "high"
        else forecast.member_lows_f
    )
    empirical_prob = None
    if len(member_values) >= bot_d_config.BOT_D_EMPIRICAL_MIN_MEMBERS:
        empirical_prob = empirical_bucket_probability(
            market.city,
            member_values,
            market.range_low_f,
            market.range_high_f,
        )
    probability_disagreement = (
        abs(empirical_prob - cdf_prob) if empirical_prob is not None else None
    )

    settlement_constraint = None
    observed_constraint = _observed_settlement_probability(market, forecast)
    if observed_constraint is not None:
        gfs_prob, settlement_constraint = observed_constraint

    gfs_prob = max(0.001, min(0.999, gfs_prob))

    market_p = float(market.yes_price) if market.yes_price is not None else 0.5
    gross_edge = gfs_prob - market_p

    # Fee netting — per-share cost basis.
    #
    # 2026-04-22 fix (Codex fleet review Section A #7): official
    # Polymarket fee is `size x baseRate x p x (1-p)` USDC per fill.
    # `_polymarket_taker_fee(p)` now returns USDC per share directly,
    # so no `x entry_price` multiplication is needed. Prior code
    # understated fees by factor `entry_price` (50% at p=0.5, 95% at
    # p=0.05) because the old helper labelled its output as a
    # fraction-of-notional when it was actually the per-share rate.
    if gross_edge > 0:
        # BUY_YES: we pay taker fee on YES at entry_price = market_p.
        fee_per_share = _polymarket_taker_fee(market_p)
    elif gross_edge < 0:
        # BUY_NO: we pay taker fee on NO at entry_price = 1 - market_p.
        fee_per_share = _polymarket_taker_fee(1.0 - market_p)
    else:
        fee_per_share = 0.0
    # Defensive clamp (Gemini 3.1 Pro audit 2026-04-19 F-001): if fees ever
    # exceed the absolute gross edge, the naive subtraction/addition flips
    # the sign of net_edge. Mathematically harmless today (max
    # fee_per_share = 0.018 << threshold 0.10), but `max/min 0` makes
    # the logic robust to any future fee-schedule change that increases
    # peak rates above the threshold.
    if gross_edge > 0:
        net_edge = max(0.0, gross_edge - fee_per_share)
    elif gross_edge < 0:
        net_edge = min(0.0, gross_edge + fee_per_share)
    else:
        net_edge = 0.0

    # Upgrade 5 + audit fix #4: NWS second-opinion filter, scaled by bucket width.
    # Small buckets need a floor; wide buckets scale by width. The floor is
    # env-driven so the tiny-live probe can collect transfer data without
    # removing the independent NWS guard entirely.
    bucket_width = 1.0
    if market.range_low_f is not None and market.range_high_f is not None:
        bucket_width = max(1.0, market.range_high_f - market.range_low_f)
    nws_veto_threshold = max(bot_d_config.BOT_D_NWS_VETO_MIN_THRESHOLD_F, bucket_width * 0.5)

    nws_disagrees = False
    nws_val: float | None = None
    nws_gap: float | None = None
    has_independent_nws = forecast.source != "nws_fallback"
    if (
        has_independent_nws
        and settlement_constraint is None
        and market.temp_type == "high"
        and forecast.nws_high_f is not None
    ):
        nws_val = forecast.nws_high_f
        nws_gap = abs(mean - nws_val)
        if nws_gap > nws_veto_threshold:
            nws_disagrees = True
    elif (
        has_independent_nws
        and settlement_constraint is None
        and market.temp_type == "low"
        and forecast.nws_low_f is not None
    ):
        nws_val = forecast.nws_low_f
        nws_gap = abs(mean - nws_val)
        if nws_gap > nws_veto_threshold:
            nws_disagrees = True

    override_nws_veto = (
        bot_d_config.BOT_D_ENV == "paper"
        and bot_d_config.BOT_D_NWS_VETO_OVERRIDE_ENABLED
        and abs(net_edge) >= bot_d_config.BOT_D_NWS_VETO_OVERRIDE_MIN_EDGE
    )
    api_values = forecast.api_highs_f if market.temp_type == "high" else forecast.api_lows_f
    api_agreement_count, api_agreement_max_gap = _best_api_agreement(
        api_values,
        max_gap_f=bot_d_config.BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F,
    )
    nws_outlier_probe = (
        bot_d_config.BOT_D_NWS_OUTLIER_PROBE_ENABLED
        and nws_disagrees
        and forecast.source != "nws_fallback"
        and abs(net_edge) >= bot_d_config.BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE
        and nws_gap is not None
        and nws_gap <= bot_d_config.BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F
        and api_agreement_count >= 2
        and api_agreement_max_gap is not None
        and api_agreement_max_gap <= bot_d_config.BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F
    )

    if nws_disagrees and not override_nws_veto and not nws_outlier_probe:
        side = "SKIP"
        reason = (
            f"nws_disagrees (mean={mean:.1f} vs nws={nws_val:.1f}, "
            f"threshold={nws_veto_threshold:.1f})"
        )
    elif (
        settlement_constraint is None
        and probability_disagreement is not None
        and probability_disagreement > bot_d_config.BOT_D_EMPIRICAL_DISAGREE_THRESHOLD
    ):
        side = "SKIP"
        reason = (
            "ensemble_shape_disagrees "
            f"(cdf={cdf_prob:.3f}, empirical={empirical_prob:.3f}, "
            f"delta={probability_disagreement:.3f})"
        )
    elif abs(net_edge) < edge_threshold:
        side = "SKIP"
        prefix = f"{settlement_constraint}; " if settlement_constraint else ""
        reason = f"{prefix}net_edge |{net_edge:+.3f}| below threshold {edge_threshold}"
    elif net_edge > 0:
        side = "BUY_YES"
        prefix = f"{settlement_constraint}; " if settlement_constraint else ""
        if nws_outlier_probe:
            veto_prefix = (
                "nws_outlier_probe; "
                f"api_agree={api_agreement_count}/{len(api_values)} "
                f"gap={api_agreement_max_gap:.1f}; "
            )
        else:
            veto_prefix = "nws_override; " if nws_disagrees else ""
        reason = (
            f"{prefix}{veto_prefix}model {gfs_prob:.3f} > market {market_p:.3f} "
            f"(net {net_edge:+.3f})"
        )
    else:
        side = "BUY_NO"
        prefix = f"{settlement_constraint}; " if settlement_constraint else ""
        if nws_outlier_probe:
            veto_prefix = (
                "nws_outlier_probe; "
                f"api_agree={api_agreement_count}/{len(api_values)} "
                f"gap={api_agreement_max_gap:.1f}; "
            )
        else:
            veto_prefix = "nws_override; " if nws_disagrees else ""
        reason = (
            f"{prefix}{veto_prefix}model {gfs_prob:.3f} < market {market_p:.3f} "
            f"(net {net_edge:+.3f})"
        )

    if (
        side == "BUY_NO"
        and bot_d_config.BOT_D_BLOCK_BUY_NO_MEAN_INSIDE_BUCKET
        and market.range_low_f is not None
        and market.range_high_f is not None
        and market.range_low_f <= mean <= market.range_high_f
    ):
        side = "SKIP"
        reason = (
            "buy_no_mean_inside_yes_bucket; "
            f"mean={mean:.1f} bucket={market.range_low_f:.1f}-{market.range_high_f:.1f}"
        )

    return WeatherEdgeDecision(
        market=market,
        gfs_probability=gfs_prob,
        market_probability=market_p,
        gross_edge=gross_edge,
        net_edge=net_edge,
        edge=net_edge,
        side=side,
        reason=reason,
        forecast_mean_f=mean,
        forecast_std_f=adjusted_std,
        ensemble_count=forecast.ensemble_count,
        decided_at=now,
        forecast_source=forecast.source,
        forecast_fetched_at=forecast.fetched_at,
        forecast_model_timestamp=forecast.model_timestamp,
        api_highs_f=forecast.api_highs_f,
        api_lows_f=forecast.api_lows_f,
        nws_gap_f=nws_gap,
        api_agreement_count=api_agreement_count,
        api_agreement_max_gap_f=api_agreement_max_gap,
        nws_outlier_probe=nws_outlier_probe,
        empirical_probability=empirical_prob,
        probability_disagreement=probability_disagreement,
        settlement_constraint=settlement_constraint,
    )


def apply_one_bet_per_event(
    decisions: list[WeatherEdgeDecision],
) -> list[WeatherEdgeDecision]:
    """Enforce ONE BET PER EVENT: group by (city, date, temp_type), keep highest |net_edge|.

    This is the MOST CRITICAL rule for weather bots. Each event
    (e.g., NYC April 17 daily high) has 10-15 temperature ranges. Only ONE
    can win — the rest all lose. Betting on multiple ranges in the same event
    guarantees losses (3-4 losing $50 bets overwhelm 1 winning $50 bet).
    """
    best: dict[tuple[str, str, str], WeatherEdgeDecision] = {}
    for d in decisions:
        if d.side == "SKIP":
            continue
        key = (d.market.city, d.market.date, d.market.temp_type)
        if key not in best or abs(d.net_edge) > abs(best[key].net_edge):
            best[key] = d
    return list(best.values())


def apply_wave_regime_sizing(
    decisions: list[WeatherEdgeDecision],
    *,
    enabled: bool | None = None,
    min_markets: int | None = None,
    isolated_size_factor: Decimal | None = None,
    wave_size_factor: Decimal | None = None,
    require_wave: bool | None = None,
) -> list[WeatherEdgeDecision]:
    """Annotate Bot D decisions as wave or isolated regimes.

    The profitable hypothesis for Bot D is not "all weather tails are cheap".
    Prior audits found the apparent edge clustered in cohort/wave events:
    multiple same-day, same-temperature-type markets all mispriced in the
    same direction. This helper keeps full sizing for those waves and reduces
    isolated-tail size so paper/live probes do not dominate bleed.

    Call this after ``apply_one_bet_per_event`` so a city/date/temp event can
    contribute at most one signal to the wave count.
    """
    if enabled is None:
        enabled = bot_d_config.BOT_D_WAVE_FILTER_ENABLED
    if not enabled:
        return decisions

    min_markets = min_markets or bot_d_config.BOT_D_WAVE_MIN_MARKETS
    isolated_size_factor = (
        isolated_size_factor
        if isolated_size_factor is not None
        else bot_d_config.BOT_D_ISOLATED_SIZE_FACTOR
    )
    wave_size_factor = (
        wave_size_factor
        if wave_size_factor is not None
        else bot_d_config.BOT_D_WAVE_SIZE_FACTOR
    )
    require_wave = (
        require_wave
        if require_wave is not None
        else bot_d_config.BOT_D_REQUIRE_WAVE_FOR_ENTRY
    )

    groups: dict[tuple[str, str, str], list[WeatherEdgeDecision]] = {}
    for d in decisions:
        if d.side == "SKIP":
            continue
        key = (d.market.date, d.market.temp_type, d.side)
        groups.setdefault(key, []).append(d)

    out: list[WeatherEdgeDecision] = []
    for d in decisions:
        key = (d.market.date, d.market.temp_type, d.side)
        count = len(groups.get(key, []))
        wave_key = ":".join(key)
        if count >= min_markets:
            out.append(
                replace(
                    d,
                    regime="wave",
                    wave_key=wave_key,
                    wave_count=count,
                    size_multiplier=wave_size_factor,
                )
            )
        elif not require_wave:
            out.append(
                replace(
                    d,
                    regime="isolated",
                    wave_key=wave_key,
                    wave_count=count,
                    size_multiplier=isolated_size_factor,
                )
            )
    return out
