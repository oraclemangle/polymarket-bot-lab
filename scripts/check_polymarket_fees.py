"""Polymarket fee-schedule sentinel.

Audit 2026-04-17 Phase 3 (Bot A §What I would change). Bot A's entire
positive-EV math depends on geopolitics category carrying a 0% taker fee.
Polymarket has already restructured fees twice since 2025; a quiet change
would silently convert Bot A from positive-EV to negative-EV overnight.

This script:
1. Fetches the Polymarket fees documentation URL(s).
2. Parses the current per-category taker fee rates.
3. Compares against the baseline in `core/fees.TAKER_FEE_RATE_BY_CATEGORY`.
4. If geopolitics != 0 OR any other category drifts by more than ±0.005,
   emits a structured log line AND sets the repo-wide emergency halt.
5. Exits 0 on no-drift, 2 on drift detected (so systemd timers can act).

Intended to run daily via a systemd timer on the bot host.

Usage:
    python -m scripts.check_polymarket_fees           # default: halt on drift
    python -m scripts.check_polymarket_fees --dry-run # log only, don't halt
    python -m scripts.check_polymarket_fees --source FILE  # read snapshot from file

Network access is optional — the script gracefully handles offline runs
(exits 0 with a warning). Never hard-fails on HTTP errors, since a stale
doc page should not silently wedge trading.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional

from core.fees import TAKER_FEE_RATE_BY_CATEGORY

log = logging.getLogger("check_polymarket_fees")

DOCS_URL = "https://docs.polymarket.com/trading/fees"
# Tolerance before we emergency-halt. Drifts < this are logged but don't halt.
DRIFT_TOLERANCE = Decimal("0.005")

# Category alias map — Polymarket docs sometimes write "Geopolitics / World
# Events" or similar. Map normalised names back to our config keys.
CATEGORY_ALIASES = {
    "geopolitics": ["geopolitics", "world events", "world event"],
    "crypto": ["crypto", "cryptocurrency"],
    "economics": ["economics"],
    "mentions": ["mentions"],
    "culture": ["culture"],
    "weather": ["weather"],
    "finance": ["finance"],
    "politics": ["politics"],
    "tech": ["tech", "technology"],
    "sports": ["sports"],
}


def _fetch_docs(url: str, timeout_s: float = 10.0) -> str | None:
    """Best-effort fetch. Returns None on any network error."""
    try:
        import httpx
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.text
    except Exception as exc:
        log.warning("fee_check.fetch_failed url=%s err=%s", url, exc)
        return None


_FEE_RATE_PATTERN = re.compile(
    r"(?P<cat>[A-Za-z /]+?)\s*[:\-]\s*(?P<bps>\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


def parse_fee_schedule(html_or_text: str) -> dict[str, Decimal]:
    """Extract a {category: taker_rate} dict from the docs page.

    Matches patterns like "Crypto: 1.80%" or "Geopolitics - 0%" and
    normalizes category names to lowercase. **Returns the PEAK taker rate**
    (what the docs usually publish), which equals `feeRate × 0.25` under
    the parabolic model. Caller converts as needed.
    """
    out: dict[str, Decimal] = {}
    for match in _FEE_RATE_PATTERN.finditer(html_or_text):
        cat = match.group("cat").strip().lower()
        bps = Decimal(match.group("bps")) / Decimal("100")
        # Match against alias list.
        for canonical, aliases in CATEGORY_ALIASES.items():
            if any(a in cat for a in aliases):
                # Keep the first match we see per category.
                out.setdefault(canonical, bps)
                break
    return out


def compare_against_baseline(
    observed_peaks: dict[str, Decimal],
) -> tuple[list[str], bool]:
    """Compare observed peak rates against our baseline `feeRate × 0.25`.

    Returns (drift_messages, should_halt_bot_a).
    Halts Bot A if:
      - geopolitics peak > 0 (ANY fee on geopolitics kills Bot A's EV)
      - any other category drifts by more than DRIFT_TOLERANCE
    """
    drifts: list[str] = []
    halt = False
    for cat, baseline_fee_rate in TAKER_FEE_RATE_BY_CATEGORY.items():
        baseline_peak = baseline_fee_rate * Decimal("0.25")
        observed = observed_peaks.get(cat)
        if observed is None:
            continue  # missing from doc page — treat as no-signal
        # Geopolitics special case: any non-zero is a halt.
        if cat == "geopolitics" and observed > Decimal("0"):
            drifts.append(
                f"CRITICAL: geopolitics peak={observed} (was {baseline_peak}). "
                f"Bot A EV thesis depends on geopolitics = 0."
            )
            halt = True
            continue
        delta = observed - baseline_peak
        if abs(delta) > DRIFT_TOLERANCE:
            drifts.append(
                f"{cat}: observed peak={observed}, baseline peak={baseline_peak}, "
                f"delta={delta:+}"
            )
            halt = True
    return drifts, halt


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(description="Polymarket fee-schedule sentinel")
    p.add_argument("--dry-run", action="store_true", help="log drift but don't set emergency halt")
    p.add_argument("--source", help="read docs HTML from a file instead of HTTP")
    p.add_argument("--json", action="store_true", help="emit JSON on stdout")
    args = p.parse_args(argv)

    if args.source:
        text: Optional[str] = Path(args.source).read_text()
    else:
        text = _fetch_docs(DOCS_URL)
    if not text:
        log.warning("fee_check.no_source_available exit=0")
        if args.json:
            json.dump({"status": "no_source", "halted": False}, sys.stdout)
        return 0

    observed = parse_fee_schedule(text)
    drifts, should_halt = compare_against_baseline(observed)

    if args.json:
        json.dump(
            {
                "status": "drift" if drifts else "ok",
                "observed": {k: str(v) for k, v in observed.items()},
                "drifts": drifts,
                "halted": bool(should_halt and not args.dry_run),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")

    if drifts:
        for msg in drifts:
            log.warning("fee_check.drift %s", msg)
        if should_halt and not args.dry_run:
            try:
                from core.emergency_halt import set_emergency_halt
                reason = "fee_schedule_drift: " + "; ".join(drifts)[:400]
                set_emergency_halt(reason)
                log.warning("fee_check.emergency_halt_set")
            except Exception as exc:
                log.error("fee_check.halt_set_failed err=%s", exc)
                return 1
        return 2

    log.info("fee_check.ok %d categories observed match baseline", len(observed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
