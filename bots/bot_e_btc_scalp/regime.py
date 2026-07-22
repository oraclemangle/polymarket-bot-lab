"""Bot E — regime classifier (binary hard-gate per ADR-022 / Codex C-R1).

v1 computes a single hard signal: `should_skip_due_to_chop(prices)`. No
tuning surface in v1; thresholds are hard-coded references to config defaults
(themselves env-overridable for operations, but NOT tuned during Phase 0d
calibration — calibration tunes only OBI threshold).

Inputs are a list of recent BTC closes. Units: raw USD from Chainlink or
whichever source the executor is using. Dimensions handled here:
  - choppiness ratio is unit-free (ratio of reversals)
  - trend strength is normalised to basis points of `closes[-1]` to avoid
    the v96-article dimensional bug (Grok G3)

Promoted to a tunable classifier in v1.1 ONLY if recorder data shows
choppiness alone is insufficient.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

log = logging.getLogger(__name__)

Regime = Literal["trending", "choppy", "unknown"]


@dataclass(frozen=True)
class RegimeSnapshot:
    regime: Regime
    choppiness: float          # 0 = pure trend, 1 = pure chaos
    dir_bps: float             # signed 10-min net move in bps
    n_samples: int


def choppiness_ratio(closes: list[float]) -> float:
    """Fraction of consecutive-bar direction reversals in the sequence.

    0.0 = every bar in the same direction (perfect trend)
    1.0 = every bar reverses (pure chop)
    Requires ≥3 closes. Raises on fewer.
    """
    if len(closes) < 3:
        raise ValueError(f"choppiness needs ≥3 closes, got {len(closes)}")
    signs = [1 if closes[i] > closes[i-1] else -1 for i in range(1, len(closes))]
    reversals = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
    return reversals / max(1, len(signs) - 1)


def dir_bps(closes: list[float]) -> float:
    """Net price change from `closes[0]` to `closes[-1]`, expressed in
    basis points of the LATEST price. Signed; positive = up.

    Grok G3: the v96 article's raw-USD threshold (`|dir_10m| > 30`) is
    dimensionally broken at BTC ~$85k. Normalising to bps eliminates the
    ambiguity.
    """
    if len(closes) < 2:
        return 0.0
    start, end = closes[0], closes[-1]
    if end == 0:
        return 0.0
    return (end - start) / end * 10_000


def classify(
    closes: list[float],
    *,
    choppiness_max: float,
    trend_min_bps: float,
) -> RegimeSnapshot:
    """Return the current regime. `trending` or `choppy` or `unknown`.

    `unknown` when insufficient samples. `choppy` when reversals exceed
    threshold. `trending` when choppiness is OK AND move magnitude exceeds
    the bps floor.

    In v1 the executor treats 'choppy' as a hard skip. 'trending' and
    'unknown' both fall through to OBI decisioning.
    """
    if len(closes) < 3:
        return RegimeSnapshot(
            regime="unknown", choppiness=1.0, dir_bps=0.0,
            n_samples=len(closes),
        )
    chop = choppiness_ratio(closes)
    d = dir_bps(closes)
    if chop > choppiness_max:
        return RegimeSnapshot(
            regime="choppy", choppiness=chop, dir_bps=d, n_samples=len(closes),
        )
    if abs(d) < trend_min_bps:
        # Choppiness passes but move is small — treat as 'unknown' so OBI
        # decisions still fire; we don't gate on trending.
        return RegimeSnapshot(
            regime="unknown", choppiness=chop, dir_bps=d, n_samples=len(closes),
        )
    return RegimeSnapshot(
        regime="trending", choppiness=chop, dir_bps=d, n_samples=len(closes),
    )


def should_skip_due_to_chop(
    closes: list[float],
    *,
    choppiness_max: float,
) -> bool:
    """One-call binary gate used by the signal module.

    True = skip. This is the ONLY regime signal that affects execution in v1.
    """
    if len(closes) < 3:
        return False  # Can't classify; don't block trading for lack of data
    return choppiness_ratio(closes) > choppiness_max
