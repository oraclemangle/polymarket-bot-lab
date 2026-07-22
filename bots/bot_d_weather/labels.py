"""Analysis-only labels for Bot D candidate/event reporting.

These helpers are deliberately pure and defensive. They are used for audit
payloads and offline reports only; label failures must never affect entry
decisions.
"""

from __future__ import annotations

from typing import Any


def to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def edge(payload: dict[str, Any]) -> float | None:
    value = to_float(payload.get("net_edge"))
    if value is not None:
        return value
    model = to_float(payload.get("gfs_probability") or payload.get("model_probability"))
    market = to_float(payload.get("market_probability"))
    if model is None or market is None:
        return None
    return model - market


def forecast_source(payload: dict[str, Any]) -> str:
    return str(payload.get("forecast_source") or "unknown")


def is_ensemble_source(source: str) -> bool:
    source_l = source.lower()
    return any(key in source_l for key in ("multi", "ensemble", "openmeteo", "gfs_ecmwf"))


def skip_reason_code(reason: str | None) -> str:
    text = (reason or "").strip()
    if not text:
        return "unknown"
    if text.startswith("nws_disagrees"):
        return "nws_disagrees"
    if text.startswith("ensemble_shape_disagrees"):
        return "ensemble_shape_disagrees"
    if "below threshold" in text:
        return "below_threshold"
    if text.startswith("observed_") or "; net_edge" in text:
        return "observed_constraint"
    if text.startswith("nws_override"):
        return "nws_override_entry"
    if text.startswith("model ") or " model " in text:
        return "entry_signal"
    return text.split()[0][:80]


def distance_from_threshold_f(payload: dict[str, Any]) -> float | None:
    mean = to_float(payload.get("forecast_mean_f"))
    low = to_float(payload.get("bucket_low_f"))
    high = to_float(payload.get("bucket_high_f"))
    if mean is None:
        return None
    edges = [v for v in (low, high) if v is not None]
    if not edges:
        return None
    return round(min(abs(mean - v) for v in edges), 2)


def bucket_width_f(payload: dict[str, Any]) -> float | None:
    low = to_float(payload.get("bucket_low_f"))
    high = to_float(payload.get("bucket_high_f"))
    if low is None or high is None:
        return None
    return abs(high - low)


def nws_threshold(payload: dict[str, Any], floor_f: float | None) -> float | None:
    if floor_f is None:
        return None
    disagreement = to_float(payload.get("nws_disagreement_f"))
    if disagreement is None:
        return None
    width = bucket_width_f(payload)
    base = (width * 0.5) if width is not None else 0.0
    return max(float(floor_f), base)


def would_clear_nws(payload: dict[str, Any], floor_f: float | None) -> bool:
    event_type = str(payload.get("_event_type") or "")
    if event_type == "bot_d.forecast_entry":
        return True
    e = edge(payload)
    if e is None or abs(e) < 0.10:
        return False
    if floor_f is None:
        return True
    disagreement = to_float(payload.get("nws_disagreement_f"))
    threshold = nws_threshold(payload, floor_f)
    if disagreement is None or threshold is None:
        return False
    return disagreement <= threshold + 1e-9


def nws_lane(payload: dict[str, Any]) -> str:
    if str(payload.get("_event_type") or "") == "bot_d.forecast_entry":
        return "entry"
    if to_float(payload.get("nws_disagreement_f")) is None:
        return "no_nws_context"
    if would_clear_nws(payload, 3.0):
        return "would_clear_3f"
    if would_clear_nws(payload, 4.0):
        return "would_clear_4f_only"
    if would_clear_nws(payload, None):
        return "nws_off_only"
    return "blocked_or_low_edge"


def setup_tier(payload: dict[str, Any]) -> tuple[str, str]:
    e = edge(payload)
    abs_edge = abs(e) if e is not None else 0.0
    verified = to_bool(payload.get("settlement_verified"))
    source = forecast_source(payload)
    ensemble = is_ensemble_source(source)
    clears_3f = would_clear_nws(payload, 3.0)
    entry = str(payload.get("_event_type")) == "bot_d.forecast_entry"
    reasons: list[str] = []

    if not verified:
        reasons.append("settlement_not_verified")
    if not ensemble:
        reasons.append(f"forecast_source={source}")
    if abs_edge < 0.10:
        reasons.append("edge_lt_10pct")
    if not clears_3f:
        reasons.append("blocked_by_3f_nws_lane")

    if verified and abs_edge >= 0.15 and ensemble and (entry or clears_3f):
        return "A", "verified, ensemble source, >=15pct edge, clears 3F lane"
    if verified and abs_edge >= 0.10 and (ensemble or clears_3f):
        return "B", "verified and >=10pct edge, but missing one A-tier property"
    return "C", ", ".join(reasons) or "insufficient candidate evidence"


def depth_lane(payload: dict[str, Any]) -> str:
    depth = to_float(payload.get("depth_usd"))
    if depth is None:
        return "unknown"
    if depth >= 50:
        return "depth_gte_50"
    if depth >= 25:
        return "depth_25_to_50"
    return "weak_depth_lt_25"


def enrich_payload(payload: dict[str, Any], *, reason: str | None = None) -> dict[str, Any]:
    """Return analysis labels derived from an audit payload."""
    tier, tier_reason = setup_tier(payload)
    dist = distance_from_threshold_f(payload)
    station = payload.get("settlement_station")
    obs_station = payload.get("observation_station")
    source_confident = bool(station) and to_bool(payload.get("settlement_verified"))
    labels = {
        "skip_reason_code": skip_reason_code(reason or str(payload.get("reason") or "")),
        "setup_tier": tier,
        "setup_tier_reason": tier_reason,
        "source_confident": source_confident,
        "exact_station_match": bool(station and obs_station and station == obs_station),
        "distance_from_threshold_f": dist,
        "near_threshold": bool(dist is not None and dist <= 2.0),
        "nws_lane": nws_lane(payload),
        "depth_lane": depth_lane(payload),
    }
    if "wave_count" in payload or "regime" in payload:
        labels["wave_supported"] = (
            str(payload.get("regime") or "").lower() == "wave"
            or int(payload.get("wave_count") or 0) > 1
        )
    return labels
