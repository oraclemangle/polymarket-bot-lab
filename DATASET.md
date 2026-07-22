# Companion dataset: polymarket-canary-tape

This repository (**polymarket-bot-lab**) holds the bot lab code, framework, and
strategy documentation. Market and tape data used in research are released
separately as **polymarket-canary-tape**.

| Field | Value |
|---|---|
| Name | polymarket-canary-tape |
| License | [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) |
| Files | 3 (shared SQLite schema) |
| Coverage | 2026-04-30 to 2026-07-05 (with a gap 2026-05-03 to 2026-05-13) |
| Primary file | canary node, 2026-05-13 to 2026-07-05: 271.6M CEX trades, 27.9M PM WS events, 23,750 markets |
| Second vantage | home-lab node, 2026-06-03 to 2026-07-01 (overlaps canary): 33.3M PM WS events, 4.3M CEX trades |
| Early snapshot | 72h, 2026-04-30 to 2026-05-03: 532K PM WS events |
| Hosting | [Hugging Face](https://huggingface.co/datasets/oraclemangle/polymarket-canary-tape) |

The canary/second-vantage overlap window supports cross-vantage latency and
feed-consistency studies (same markets, two independent receive clocks).

## Purpose

Canary-period market tape for offline research: CEX trade flow, Polymarket WS
events, and market universe snapshots aligned to the window above. Captured by
**Scribe** (Bot E / `bot_e_recorder`), the fleet's always-on market recorder.
Intended for replication studies, microstructure work, and strategy post-mortems
that need raw or lightly processed event streams — not for live trading.

## Links

- Hugging Face dataset: https://huggingface.co/datasets/oraclemangle/polymarket-canary-tape

Until those URLs are published, treat this file as the canonical pointer from
the code repo. Do not assume any data files ship inside this Git tree.

## Relationship to the code export

| Artifact | License | Location |
|---|---|---|
| Bot lab code, ADRs, post-mortems | Apache-2.0 | This repository (polymarket-bot-lab) |
| polymarket-canary-tape | CC-BY-4.0 | Companion release (Zenodo / Hugging Face) |

External scored outputs from closed products (including Oraclemangle) are **not**
part of polymarket-canary-tape and are not redistributed here.

## Citation

Cite the software via [CITATION.cff](CITATION.cff). When the dataset DOI is live,
prefer the Zenodo citation for data-only use; cite both when combining code and tape.

## Research only

Dataset contents are observational market data for research. They are not
financial advice and do not guarantee any strategy outcome.
