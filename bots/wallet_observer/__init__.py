"""Wallet observer — passive Polygon CTF Exchange event subscription.

Records every fill where the maker or taker matches a curated whitelist
of 245 retail-tier wallets (Tier A + Tier B from the WANGZJ mining at
`data/retail_wallets_xref_2026-05-07.csv`).

Read-only relative to Polymarket: NEVER places trades, NEVER signs
transactions, NEVER touches operator wallets. Pure observation pipeline.

Authority: ADR-126 (paper-only forward observation; no copy-trading
authorization).
"""
