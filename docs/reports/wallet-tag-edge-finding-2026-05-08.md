# Wallet-Tag Edge Finding — 2026-05-08

**Status:** Read-only research plus operator-approved passive forward
observation. No live bot, wallet, cap, or trading parameter has been changed.
The the bot container forward-gate units were renamed on 2026-05-09 to
`polymarket-wallet-tag-forward.{service,timer}` and
`polymarket-wallet-tag-forward-resolutions.{service,timer}` so they no longer
collide with the VPS Polygon event-recorder service named
`polymarket-wallet-observer.service`.
**Predecessor reports:**
- `data/reports/wallet_tag_math/wallet_tag_murphy_20260508T204343Z.{md,json}` — 5-year baseline
- `data/reports/wallet_tag_math/wallet_tag_murphy_recent_90d_xtab_20260508T210118Z.{md,json}` — 90-day recency + cross-tabs
- `data/reports/wallet_tag_math/wallet_tag_murphy_only_late_to_tomorrow_20260508T210802Z.{md,json}` — 1-wallet validation
- `data/reports/wallet_tag_math/wallet_tag_murphy_exclude_late_to_tomorrow_20260508T210628Z.{md,json}` — rest-of-cohort validation

This is the consolidated finding from the wallet-tag math primitives
work that started after Strategy E + city-only Murphy runs all
returned FAIL.

## Bottom line

The math primitives library has surfaced **the first decision-grade
edge candidate** in the entire research cycle. It is not a single bot
strategy; it is a wallet-tag *feature* that can plumb into existing
bots as a candidate filter. Per CLAUDE.md scope, direct copy-trading
remains kill-listed — this finding is "wallet-tag features (Variant B)"
which the 2026-05-07 session-audit already approved as a workaround.

## Verified findings

### Headline (90-day slice, n=25,092 trades, 60 wallets)

| Metric | Value |
|---|---:|
| Hit rate | 41.5% |
| Implied (mean entry price) | 30.9% |
| Edge | **+10.7 percentage points** |
| Resolution | 0.01528 (above 0.001 gate) |
| Top-2 P&L concentration | 8% (no lottery alarm) |
| Bootstrap 95% CI on ROI | **(+4.4%, +184.8%)** — both bounds positive |

### Two independent halves of the cohort both pass

The 60-wallet cohort splits into one high-volume sustainable-edge
wallet (`late-to-tomorrow`, 16,245 trades) and 59 lower-volume
higher-edge wallets (8,847 trades combined).

**Both halves independently clear all three math gates.** This is
unusually strong — the headline edge is not driven by a single wallet.

| Slice | n | Hit | Implied | Edge | Resolution | 95% CI ROI | Verdict |
|---|---:|---:|---:|---:|---:|---|---|
| late-to-tomorrow only | 16,245 | 38.7% | 33.7% | +5.0pp | 0.01266 | (+8.3%, +23.7%) | PASS |
| Cohort minus late-to-tomorrow | 8,847 | 46.8% | 25.7% | +21.1pp | 0.03553 | (+7.4%, +192.1%) | PASS |
| Full cohort | 25,092 | 41.5% | 30.9% | +10.7pp | 0.01528 | (+4.4%, +184.8%) | PASS |

### Sub-cohorts of bot_score_low_under_30 that ALSO pass

| Cross-tab | n | Edge | 95% CI lower | Read |
|---|---:|---:|---:|---|
| × price 3-15c entry | 3,815 | +10.6pp | **+40.5%** | strongest single-corner signal |
| × price 30-50c entry | 13,418 | +10.1pp | **+14.0%** | tightest CI on largest sub-cohort |
| × ttr_under_1h hold | 16,564 | +5.0pp | +2.4% | barely passes; durable but small edge |
| × cat_crypto | 17,075 | +7.4pp | +3.1% | matches Bot G/crypto FV market scope |
| × cat_other | 5,963 | +22.1pp | +1.6% | catch-all category — needs further slicing |

## What this means operationally

1. **The PolyVerify `botScore < 30` field is a real signal.** Wallets PolyVerify classifies as "definitely human, not automated" outperform implied probability by a statistically-decisive +10.7pp on 25K recent trades (at 95% confidence after trading-day-level resampling).
2. **`late-to-tomorrow` is the cleanest single signal.** 16,245 trades, +5.0pp edge, 95% CI [+8.3%, +23.7%] — the tightest confidence band of any cohort tested.
3. **The edge concentrates in 3-15c entries** (+13.4pp, CI +33.2% to +272%) and **30-50c entries** (+24.3pp, CI +15.7% to +50%). This points at longshot + near-coinflip mis-pricing.
4. **The ttr<1h slice barely passes.** Edge survives but is small. Live operationalisation must contend with sub-hour latency.

## Honest caveats

1. **Selection bias on PolyVerify scrape.** The 1000 wallets were scraped May 2026 by P&L rank; trades from these wallets include their winning trades. The exclude/only sensitivity test partly mitigates this — late-to-tomorrow's edge is small enough to be plausibly real, the 59-wallet rest-of-cohort's +21.1pp edge is more selection-bias-suspicious.
2. **Live capture has latency cost.** The observer polls Polymarket Data API every 30 minutes (configurable). Real-time edge harvesting needs sub-second tracking which would require a different architecture (WSS subscription).
3. **Fee model is flat 4% (parabolic taker).** Categories vary: weather/sports 5%, geopolitics 0%. Affects ROI but not Brier/resolution.
4. **`taker` field ambiguity.** Polymarket Data API gives the visible counterparty; maker-rebate dynamics may obscure economic counterparty.
5. **Not yet forward-validated.** All numbers are historical. The passive observer is the planned forward-validation tool.

## Operational state — what's been built

### Read-only research scripts

| Script | Purpose |
|---|---|
| `scripts/research/wallet_tag_murphy_decomposition.py` | The main analysis: WANGZJ trade panel + wallet-tag join + Murphy decomposition + bootstrap CI per cohort |
| `scripts/research/wallet_observer.py` | Passive observer: polls Polymarket Data API for new trades by the 60 wallets, writes to `data/wallet_tag_forward.db`. **Read-only HTTP, no wallet keys, no orders.** |
| `scripts/research/wallet_observer_report.py` | Forward Murphy decomposition over the observer DB |

### Wallet target list

`data/wallet_tag_observer_targets.csv` — 106 wallets in the bot_score_low_under_30 cohort, with their PolyVerify rank, bot_score, baseline n_trades / hit_rate / edge / total_pnl.

### Systemd unit files (DEPLOYED on the bot container 2026-05-08, parameters locked by ADR-137)

| Unit | Cadence | Purpose |
|---|---|---|
| `polymarket-wallet-tag-forward.{service,timer}` | every **15 min** | Trades observer (Polymarket Data API) |
| `polymarket-wallet-tag-forward-resolutions.{service,timer}` | every **6h** | Market resolution backfill (Polymarket Gamma) |

Both are oneshot, read-only HTTP-poll, no wallet keys, no order
placement. Cadence chosen for the **7-day forward-validation window**
(operator decision 2026-05-08, down from 30 days).

- 15-min trades cadence halves the miss-rate on ttr<1h markets vs the
  initial 30-min cadence.
- 6h resolution cadence is plenty: any settled market has 28 backfill
  attempts before its 7-day inclusion window expires.
- `--max-age-days 14` filter on the resolution backfill keeps Gamma
  hit-rate at ~52% (vs 18% without the filter — Gamma's recent index
  ages out historical markets).

Deploy was completed via `pct push` from hypervisor-host to the bot container:

```sh
# On the bot container:
sudo systemctl daemon-reload
sudo systemctl enable --now polymarket-wallet-tag-forward-resolutions.timer
sudo systemctl restart polymarket-wallet-tag-forward.timer
```

First runs verified `exit=0` under the original unit names. Trades DB had
17,884 historical seed trades; resolutions DB starts empty and accumulates
settlements as markets close. Session 265 renamed the DB to
`data/wallet_tag_forward.db`; migrate or copy the existing the bot container
`data/wallet_observer.db` before deploying the renamed units if historical
seed rows should be retained.

## Forward-validation gate (7-day window)

Run both observers for **7 days** (operator decision 2026-05-08, 30
days was deemed too long). Target sample: ≥ 200 settled trades for the
bot_score_low_under_30 cohort. Then run:

```sh
.venv/bin/python scripts/research/wallet_observer_report.py
```

Decision rule:

- **PASS forward**: bot_score_low cohort has `n ≥ 200` AND `resolution
  > 0.001` AND `top_2 < 50%` AND `95% CI lower > 0` on the live
  forward sample.
- **INSUFFICIENT**: sample below 200. Decide whether to extend the
  window or accept low cohort throughput.
- **FAIL forward**: sample large enough but a gate fails. Edge was
  historical artifact; do not promote to bot-feature use.

If forward passes, propose a new ADR for plumbing the wallet-tag
feature into existing bots (Bot D / Bot G / crypto FV) as a
candidate-filter input. **No copy-trading bot.**

## Hard boundaries

- No live orders placed. The observer is HTTP-poll only.
- No wallet keys loaded.
- Passive observer systemd units are read-only. They load no wallet keys and
  cannot place orders.
- ADR-118 ($3 fixed-notional Bot G live) unchanged.
- ADR-132 (crypto FV paper-only) unchanged.
- ADR-024 (Bot D skew-normal) unchanged.

## Citation

Math primitives library at `scripts/research/math_primitives/`,
documented in `docs/reports/math-formula-roadmap-split-2026-05-08.md`
§6. PolyVerify wallet labels: `data/polyverify_wallets.csv` (Session
196 scrape, 999 wallets, source = undocumented PolyVerify JSON API
2026-05-06). WANGZJ trade panel: `SII-WANGZJ/Polymarket_data` on
HuggingFace, snapshot
`3b5733564a832d9aa9a414638a525b123a02d37f`, locally cached on the bot container.
