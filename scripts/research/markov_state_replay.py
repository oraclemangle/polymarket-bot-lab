"""Offline Markov-state replay helpers for recorder and bot research.

This module is intentionally research-only. It estimates transition matrices
from observed state sequences and reports sparse-count warnings so we do not
turn tiny samples into live trading rules.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class TransitionEstimate:
    states: tuple[str, ...]
    counts: list[list[int]]
    matrix: list[list[float]]
    row_counts: list[int]
    sparse_rows: list[str]
    sparse_cells: list[dict[str, Any]]
    alpha: float
    min_row_count: int
    min_cell_count: int


@dataclass(frozen=True)
class WalkForwardForecast:
    index: int
    current_state: str
    next_state: str | None
    probabilities: dict[str, float]
    sparse_rows: list[str]
    sparse_cells: list[dict[str, Any]]


def _clean_sequence(sequence: Iterable[str | None]) -> list[str]:
    return [str(state) for state in sequence if state not in (None, "")]


def infer_states(sequence: Iterable[str | None]) -> tuple[str, ...]:
    """Return stable sorted state labels from an observed sequence."""
    return tuple(sorted(set(_clean_sequence(sequence))))


def estimate_transition_matrix(
    sequence: Sequence[str | None],
    *,
    states: Sequence[str] | None = None,
    alpha: float = 0.0,
    min_row_count: int = 30,
    min_cell_count: int = 20,
) -> TransitionEstimate:
    """Estimate a discrete-time transition matrix from an observed sequence.

    ``alpha`` applies symmetric additive smoothing. Keep it at 0 for raw MLE;
    use a small value such as 1.0 when a sparse row would otherwise create a
    fake 100% transition.
    """
    observed = _clean_sequence(sequence)
    state_labels = tuple(states) if states is not None else infer_states(observed)
    if not state_labels:
        return TransitionEstimate((), [], [], [], [], [], alpha, min_row_count, min_cell_count)
    index = {state: i for i, state in enumerate(state_labels)}
    n = len(state_labels)
    counts = np.zeros((n, n), dtype=int)
    for current, nxt in pairwise(observed):
        if current not in index or nxt not in index:
            continue
        counts[index[current], index[nxt]] += 1

    row_counts = counts.sum(axis=1)
    smoothed = counts.astype(float) + float(alpha)
    row_denoms = smoothed.sum(axis=1)
    matrix = np.zeros((n, n), dtype=float)
    for i, denom in enumerate(row_denoms):
        if denom > 0:
            matrix[i] = smoothed[i] / denom

    sparse_rows = [
        state_labels[i]
        for i, total in enumerate(row_counts.tolist())
        if int(total) < min_row_count
    ]
    sparse_cells: list[dict[str, Any]] = []
    for i, source in enumerate(state_labels):
        for j, target in enumerate(state_labels):
            count = int(counts[i, j])
            if count < min_cell_count:
                sparse_cells.append({
                    "from": source,
                    "to": target,
                    "count": count,
                    "min_count": min_cell_count,
                })
    return TransitionEstimate(
        states=state_labels,
        counts=counts.astype(int).tolist(),
        matrix=matrix.tolist(),
        row_counts=[int(x) for x in row_counts.tolist()],
        sparse_rows=sparse_rows,
        sparse_cells=sparse_cells,
        alpha=float(alpha),
        min_row_count=min_row_count,
        min_cell_count=min_cell_count,
    )


def multi_step_transition(matrix: Sequence[Sequence[float]], n_steps: int) -> list[list[float]]:
    if n_steps < 0:
        raise ValueError("n_steps must be >= 0")
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError("transition matrix must be square")
    return np.linalg.matrix_power(arr, n_steps).tolist()


def stationary_distribution(matrix: Sequence[Sequence[float]]) -> list[float]:
    """Solve pi P = pi with sum(pi)=1. Falls back to uniform if singular."""
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError("transition matrix must be square")
    n = arr.shape[0]
    if n == 0:
        return []
    a = arr.T - np.eye(n)
    a[-1] = 1.0
    b = np.zeros(n)
    b[-1] = 1.0
    try:
        pi = np.linalg.solve(a, b)
    except np.linalg.LinAlgError:
        return (np.ones(n) / n).tolist()
    pi = np.clip(pi, 0.0, 1.0)
    total = float(pi.sum())
    if total <= 0:
        return (np.ones(n) / n).tolist()
    return (pi / total).tolist()


def forecast_next(
    estimate: TransitionEstimate,
    *,
    current_state: str,
    n_steps: int = 1,
) -> dict[str, float]:
    if current_state not in estimate.states:
        raise ValueError(f"unknown current_state: {current_state}")
    idx = estimate.states.index(current_state)
    powered = multi_step_transition(estimate.matrix, n_steps)
    return {
        state: float(powered[idx][j])
        for j, state in enumerate(estimate.states)
    }


def walk_forward_forecasts(
    sequence: Sequence[str | None],
    *,
    lookback: int,
    states: Sequence[str] | None = None,
    alpha: float = 1.0,
    min_row_count: int = 30,
    min_cell_count: int = 20,
) -> list[WalkForwardForecast]:
    observed = _clean_sequence(sequence)
    if lookback < 2:
        raise ValueError("lookback must be >= 2")
    if len(observed) <= lookback:
        return []
    state_labels = tuple(states) if states is not None else infer_states(observed)
    out: list[WalkForwardForecast] = []
    for i in range(lookback, len(observed)):
        history = observed[i - lookback:i]
        current = observed[i]
        nxt = observed[i + 1] if i + 1 < len(observed) else None
        estimate = estimate_transition_matrix(
            history,
            states=state_labels,
            alpha=alpha,
            min_row_count=min_row_count,
            min_cell_count=min_cell_count,
        )
        probs = forecast_next(estimate, current_state=current)
        out.append(WalkForwardForecast(
            index=i,
            current_state=current,
            next_state=nxt,
            probabilities=probs,
            sparse_rows=estimate.sparse_rows,
            sparse_cells=estimate.sparse_cells,
        ))
    return out


def expected_value_by_next_state(
    probabilities: Mapping[str, float],
    ev_by_state: Mapping[str, float],
) -> float:
    return sum(float(probabilities.get(state, 0.0)) * float(ev) for state, ev in ev_by_state.items())


def bot_g_micro_state(row: Mapping[str, Any]) -> str:
    """Compact state label for Bot G daily-probe rows."""
    price = str(row.get("price_point_bucket") or row.get("entry_price_bucket") or "price_unknown")
    cex = str(row.get("cex_tag") or "cex_unknown")
    vol = str(row.get("volatility_regime") or "vol_unknown")
    session = str(row.get("session_bucket") or "session_unknown")
    return f"price={price}|cex={cex}|vol={vol}|session={session}"


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("rows", "orders", "live_rows", "all_rows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, dict)]
    raise ValueError(f"no row list found in {path}")


def run_json_state_replay(
    *,
    path: Path,
    state_fields: Sequence[str] | None,
    lookback: int,
    alpha: float,
) -> dict[str, Any]:
    rows = load_json_rows(path)
    if state_fields:
        sequence = [
            "|".join(f"{field}={row.get(field, 'unknown')}" for field in state_fields)
            for row in rows
        ]
    else:
        sequence = [bot_g_micro_state(row) for row in rows]
    estimate = estimate_transition_matrix(sequence, alpha=alpha)
    forecasts = walk_forward_forecasts(
        sequence,
        lookback=lookback,
        states=estimate.states,
        alpha=alpha,
    )
    return {
        "input_path": str(path),
        "n_rows": len(rows),
        "n_states": len(estimate.states),
        "states": list(estimate.states),
        "transition_counts": estimate.counts,
        "transition_matrix": estimate.matrix,
        "stationary_distribution": stationary_distribution(estimate.matrix),
        "sparse_rows": estimate.sparse_rows,
        "sparse_cell_count": len(estimate.sparse_cells),
        "walk_forward_count": len(forecasts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--state-fields", default="")
    parser.add_argument("--lookback", type=int, default=50)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    fields = tuple(f.strip() for f in args.state_fields.split(",") if f.strip())
    report = run_json_state_replay(
        path=args.input_json,
        state_fields=fields or None,
        lookback=args.lookback,
        alpha=args.alpha,
    )
    rendered = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
