"""Shared crypto recorder — data-only capture for Bot G and replay research.

This module began as Bot E0 under ADR-022. It now captures Polymarket CLOB WSS
events, Binance CEX trade ticks, and periodic Gamma market-metadata snapshots
for crypto Up/Down markets so Bot G can compare live entries against a broader
paper/replay tape.

**Zero order placement. No live trading.**

Package layout:
- `config.py` — capture parameters (target markets, DB path, scan interval)
- `schema.py` — SQLite schema for replay-ready events
- `market_discovery.py` — find currently-live crypto markets via Gamma
- `capture.py` — main async capture loop; wires WSS clients to the DB writer
- `audit.py` — post-capture data-quality audit (gaps, stale feeds, throughput)
- `__main__.py` — CLI entry point

Read [`docs/decisions-log.md`](../../docs/decisions-log.md) ADR-022 and the
latest crypto-recorder ADR before touching anything here.
"""
