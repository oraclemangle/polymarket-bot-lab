"""Wallet whitelist loader — reads the WANGZJ xref CSV and exposes O(1)
lookup of observed addresses by tier."""
from __future__ import annotations

import csv
import functools
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from bots.wallet_observer import config as cfg

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WhitelistedWallet:
    address: str  # lowercase 0x...
    tier: str  # A_human_profitable | B_unknown_profitable | C_automated_profitable | untiered
    user_name: str
    pv_rank: int | None
    historical_net_pnl: float
    historical_roi_pct: float
    historical_n_buys: int
    historical_winrate: float


class Whitelist:
    """Read-only mapping of address → WhitelistedWallet. Case-insensitive.

    Default-constructed via :func:`load_default` includes only the tiers
    listed in :data:`config.INCLUDED_TIERS`.
    """

    def __init__(self, by_address: dict[str, WhitelistedWallet]) -> None:
        self._by_address = by_address

    def __len__(self) -> int:
        return len(self._by_address)

    def __iter__(self):
        return iter(self._by_address.values())

    @classmethod
    def load(
        cls,
        path: Path | str = cfg.WHITELIST_CSV,
        *,
        included_tiers: Iterable[str] | None = None,
    ) -> "Whitelist":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Wallet xref CSV not found: {p}")
        included = set(included_tiers) if included_tiers else cfg.INCLUDED_TIERS
        out: dict[str, WhitelistedWallet] = {}
        with p.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                tier = (row.get("tier") or "").strip()
                if tier not in included:
                    continue
                address = (row.get("wallet") or "").strip().lower()
                if not address.startswith("0x"):
                    continue

                def _int(key: str) -> int | None:
                    v = row.get(key)
                    if v in (None, ""):
                        return None
                    try:
                        return int(float(v))
                    except (TypeError, ValueError):
                        return None

                def _float(key: str) -> float:
                    v = row.get(key) or 0
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return 0.0

                out[address] = WhitelistedWallet(
                    address=address,
                    tier=tier,
                    user_name=(row.get("user_name") or "").strip(),
                    pv_rank=_int("pv_rank"),
                    historical_net_pnl=_float("net_pnl"),
                    historical_roi_pct=_float("roi_pct"),
                    historical_n_buys=_int("n_buys") or 0,
                    historical_winrate=_float("winrate"),
                )
        log.info(
            "wallet_observer.whitelist.loaded n=%d tiers=%s source=%s",
            len(out), sorted(included), p,
        )
        return cls(out)

    def is_observed(self, address: str) -> bool:
        if not address:
            return False
        return address.lower() in self._by_address

    def lookup(self, address: str) -> WhitelistedWallet | None:
        if not address:
            return None
        return self._by_address.get(address.lower())

    def addresses(self) -> set[str]:
        """Return a set of all whitelisted addresses, lowercase 0x prefix."""
        return set(self._by_address)

    def by_tier(self, tier: str) -> list[WhitelistedWallet]:
        return [w for w in self._by_address.values() if w.tier == tier]

    def tier_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for w in self._by_address.values():
            counts[w.tier] = counts.get(w.tier, 0) + 1
        return counts


@functools.lru_cache(maxsize=1)
def load_default() -> Whitelist:
    """Singleton — load whitelist from default CSV with default tier filter."""
    return Whitelist.load()
