#!/usr/bin/env python3
"""Read-only Polymarket API endpoint contract probe.

Validates the public endpoints we depend on across Gamma, Data API, CLOB,
LB-API, and CLOB WebSocket URL construction. This is intentionally a smoke
test, not a trading tool: it never authenticates, never places orders, and
never mutates local state.

Usage:
  uv run python scripts/polymarket_api_endpoint_probe.py --json
  uv run python scripts/polymarket_api_endpoint_probe.py --wallet 0x... --condition-id 0x...
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

import httpx


GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
LB_API = "https://lb-api.polymarket.com"
CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws"


@dataclass(frozen=True)
class ProbeResult:
    name: str
    url: str
    status: str
    http_status: int | None = None
    detail: str = ""


def _ok_shape(data: Any, *, expected: str) -> bool:
    if expected == "list":
        return isinstance(data, list)
    if expected == "dict":
        return isinstance(data, dict)
    if expected == "list_or_dict":
        return isinstance(data, (list, dict))
    if expected == "any":
        return True
    return True


def _probe_json(
    client: httpx.Client,
    *,
    name: str,
    url: str,
    params: dict[str, Any] | None = None,
    expected: str = "list_or_dict",
) -> ProbeResult:
    try:
        resp = client.get(url, params=params)
    except Exception as exc:
        return ProbeResult(name=name, url=url, status="fail", detail=str(exc))
    if resp.status_code >= 400:
        return ProbeResult(
            name=name,
            url=str(resp.url),
            status="fail",
            http_status=resp.status_code,
            detail=resp.text[:200],
        )
    try:
        data = resp.json()
    except Exception as exc:
        return ProbeResult(
            name=name,
            url=str(resp.url),
            status="fail",
            http_status=resp.status_code,
            detail=f"invalid json: {exc}",
        )
    if not _ok_shape(data, expected=expected):
        return ProbeResult(
            name=name,
            url=str(resp.url),
            status="fail",
            http_status=resp.status_code,
            detail=f"unexpected shape {type(data).__name__}, expected {expected}",
        )
    count = len(data) if isinstance(data, (list, dict)) else 0
    return ProbeResult(
        name=name,
        url=str(resp.url),
        status="ok",
        http_status=resp.status_code,
        detail=f"{type(data).__name__} len={count}",
    )


def _skip(name: str, url: str, reason: str) -> ProbeResult:
    return ProbeResult(name=name, url=url, status="skip", detail=reason)


def run_probes(
    *,
    wallet: str | None = None,
    condition_id: str | None = None,
    event_slug: str = "highest-temperature-in-nyc-on-may-20-2026",
    timeout: float = 20.0,
) -> list[ProbeResult]:
    headers = {"User-Agent": "longshot-polymarket-api-probe/0.1"}
    results: list[ProbeResult] = []
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        results.extend([
            _probe_json(
                client,
                name="gamma.markets",
                url=f"{GAMMA_API}/markets",
                params={"limit": 10, "offset": 0},
                expected="list",
            ),
            _probe_json(
                client,
                name="gamma.markets_keyset",
                url=f"{GAMMA_API}/markets/keyset",
                params={"limit": 10},
                expected="dict",
            ),
            _probe_json(
                client,
                name="gamma.public_search_q",
                url=f"{GAMMA_API}/public-search",
                params={"q": "weather"},
                expected="dict",
            ),
            _probe_json(
                client,
                name="gamma.events_slug",
                url=f"{GAMMA_API}/events/slug/{event_slug}",
                expected="dict",
            ),
            _probe_json(
                client,
                name="gamma.tags",
                url=f"{GAMMA_API}/tags",
                expected="list",
            ),
            _probe_json(client, name="clob.time", url=f"{CLOB_API}/time", expected="any"),
        ])

        if condition_id:
            results.extend([
                _probe_json(
                    client,
                    name="gamma.markets_condition_id",
                    url=f"{GAMMA_API}/markets",
                    params={"conditionId": condition_id},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="clob.markets_condition_id",
                    url=f"{CLOB_API}/markets/{condition_id}",
                    expected="dict",
                ),
                _probe_json(
                    client,
                    name="data.market_positions",
                    url=f"{DATA_API}/v1/market-positions",
                    params={"market": condition_id},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="data.market_trades",
                    url=f"{DATA_API}/trades",
                    params={"market": condition_id, "limit": 10},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="data.open_interest",
                    url=f"{DATA_API}/oi",
                    params={"market": condition_id},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="data.holders",
                    url=f"{DATA_API}/holders",
                    params={"market": condition_id, "limit": 10},
                    expected="list_or_dict",
                ),
            ])
        else:
            results.extend([
                _skip("gamma.markets_condition_id", f"{GAMMA_API}/markets", "pass --condition-id"),
                _skip("clob.markets_condition_id", f"{CLOB_API}/markets/{{conditionId}}", "pass --condition-id"),
                _skip("data.market_positions", f"{DATA_API}/v1/market-positions", "pass --condition-id"),
                _skip("data.market_trades", f"{DATA_API}/trades", "pass --condition-id"),
                _skip("data.open_interest", f"{DATA_API}/oi", "pass --condition-id"),
                _skip("data.holders", f"{DATA_API}/holders", "pass --condition-id"),
            ])

        if wallet:
            results.extend([
                _probe_json(
                    client,
                    name="data.positions",
                    url=f"{DATA_API}/positions",
                    params={"user": wallet, "limit": 10},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="data.closed_positions",
                    url=f"{DATA_API}/closed-positions",
                    params={"user": wallet, "limit": 10},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="data.activity",
                    url=f"{DATA_API}/activity",
                    params={"user": wallet, "limit": 10},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="data.user_trades",
                    url=f"{DATA_API}/trades",
                    params={"user": wallet, "limit": 10},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="data.value",
                    url=f"{DATA_API}/value",
                    params={"user": wallet},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="lb.profit_all",
                    url=f"{LB_API}/profit",
                    params={"window": "all", "address": wallet},
                    expected="list_or_dict",
                ),
                _probe_json(
                    client,
                    name="lb.profit_1d",
                    url=f"{LB_API}/profit",
                    params={"window": "1d", "address": wallet},
                    expected="list_or_dict",
                ),
            ])
        else:
            results.extend([
                _skip("data.positions", f"{DATA_API}/positions", "pass --wallet"),
                _skip("data.closed_positions", f"{DATA_API}/closed-positions", "pass --wallet"),
                _skip("data.activity", f"{DATA_API}/activity", "pass --wallet"),
                _skip("data.user_trades", f"{DATA_API}/trades", "pass --wallet"),
                _skip("data.value", f"{DATA_API}/value", "pass --wallet"),
                _skip("lb.profit_all", f"{LB_API}/profit", "pass --wallet"),
                _skip("lb.profit_1d", f"{LB_API}/profit", "pass --wallet"),
            ])

    results.extend([
        ProbeResult("ws.market_url", f"{CLOB_WS}/market", "ok", detail="url constructed"),
        ProbeResult("ws.user_url", f"{CLOB_WS}/user", "skip", detail="requires auth"),
    ])
    return results


def _render_text(results: list[ProbeResult]) -> str:
    lines = ["Polymarket API endpoint probe", ""]
    for r in results:
        code = f" HTTP {r.http_status}" if r.http_status is not None else ""
        lines.append(f"- {r.status.upper():4} {r.name}{code}: {r.detail}")
    ok = sum(1 for r in results if r.status == "ok")
    fail = sum(1 for r in results if r.status == "fail")
    skip = sum(1 for r in results if r.status == "skip")
    lines.append("")
    lines.append(f"Summary: ok={ok} fail={fail} skip={skip}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wallet", help="Optional public wallet address for Data/LB probes")
    parser.add_argument("--condition-id", help="Optional conditionId for market-specific probes")
    parser.add_argument(
        "--event-slug",
        default="highest-temperature-in-nyc-on-may-20-2026",
        help="Gamma event slug to probe",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run_probes(
        wallet=args.wallet,
        condition_id=args.condition_id,
        event_slug=args.event_slug,
        timeout=args.timeout,
    )
    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2, sort_keys=True))
    else:
        print(_render_text(results))
    return 1 if any(r.status == "fail" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
