"""Canonical bot registry.

Single source of truth for every bot's metadata. Replaces the scattered
`known_bots` tuple, `BOT_ARCHETYPE` dict, dashboard service list, and
readiness-script service list that Codex fleet review Section C and GLM-5.1
review A7 flagged as drift-prone.

Every bot entry includes:
  - bot_id: key used in Portfolio / Position / HaltFlag rows
  - archetype: coarse risk-factor bucket (short_surprise, momentum,
    momentum_obi, copy, longshot, ...)
  - systemd_unit: full systemd service name (None if not deployed)
  - status: "archived" | "paper" | "paper_tuning" | "live" | "paused" | "shadow"
  - bankroll_env: env var name holding bankroll (None if not applicable)
  - include_in_cap: whether `core/fleet.check_fleet_exposure` should
    include this bot's exposure in aggregate cap
  - description: one-line operator-facing description
  - display_name: current operator-facing label
  - dashboard_visible: whether the bot appears in the active dashboard fleet
  - dashboard_services: service names that represent this dashboard row

Add a bot by adding one entry here. All downstream consumers
(`fleet.known_bots`, `BOT_ARCHETYPE`, dashboard inventory, watchdog cancel
wrappers, readiness scripts) should derive their lists from this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BotStatus = Literal["archived", "paper", "paper_tuning", "live", "paused", "shadow", "sensor"]


@dataclass(frozen=True)
class BotMeta:
    bot_id: str
    archetype: str
    systemd_unit: str | None
    status: BotStatus
    bankroll_env: str | None
    include_in_cap: bool
    description: str
    display_name: str = ""
    dashboard_visible: bool = False
    dashboard_services: tuple[str, ...] = ()


REGISTRY: tuple[BotMeta, ...] = (
    BotMeta(
        bot_id="bot_a",
        archetype="short_surprise",
        systemd_unit="polymarket-bot-a.service",
        status="archived",
        bankroll_env="BOT_A_BANKROLL_USD",
        include_in_cap=False,  # archived — no new positions
        description="Longshot-fade on political/geopolitical tails. Archived ADR-033 2026-04-18.",
        display_name="Longshot (Tail Fade)",
    ),
    BotMeta(
        bot_id="bot_a_shadow",
        archetype="short_surprise",
        systemd_unit=None,  # shadow is in-process under main bot
        status="archived",
        bankroll_env=None,
        include_in_cap=False,
        description="Bot A paper shadow for retrospective analysis.",
        display_name="Longshot Shadow",
    ),
    BotMeta(
        bot_id="bot_b",
        archetype="short_surprise",
        systemd_unit="polymarket-bot-b.service",
        status="paper",
        bankroll_env="BOT_B_BANKROLL_GBP",
        include_in_cap=True,
        description="LLM directional (external scorer; code excluded from public export). Parked.",
        display_name="Oracle (LLM Directional)",
    ),
    BotMeta(
        bot_id="bot_b_shadow",
        archetype="short_surprise",
        systemd_unit="polymarket-bot-b-shadow.service",
        status="shadow",
        bankroll_env=None,
        include_in_cap=False,
        description="Bot B paper shadow. Parked from active dashboard pending spin-off plan.",
        display_name="Oracle Shadow",
    ),
    BotMeta(
        bot_id="bot_c",
        archetype="momentum",
        systemd_unit="polymarket-bot-c.service",
        status="archived",
        bankroll_env="BOT_C_BANKROLL_USD",
        include_in_cap=False,
        description="Pyth Directional trading archived by ADR-093; Pyth/Hermes data and probability-model pieces retained for research reuse.",
        display_name="Pythia (Pyth Directional)",
    ),
    BotMeta(
        bot_id="bot_d",
        archetype="short_surprise",
        systemd_unit="polymarket-bot-d.service",
        status="paper",
        bankroll_env="BOT_D_BANKROLL_USD",
        include_in_cap=True,
        description="Weather Fade. Paper; station-exact daily proof before live wallet proposal.",
        display_name="Nimbus (Weather Fade)",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-d",),
    ),
    BotMeta(
        bot_id="bot_d_live_probe",
        archetype="short_surprise",
        systemd_unit="polymarket-bot-d-live.service",
        status="paused",
        bankroll_env="BOT_D_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Weather Fade live probe. Operator-halted with all live services "
            "on 2026-05-19; retained in cap/accounting surfaces for residual exposure."
        ),
        display_name="Nimbus Live Probe",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-d-live",),
    ),
    BotMeta(
        bot_id="bot_d_maker_live_probe",
        archetype="short_surprise_maker",
        systemd_unit="polymarket-bot-d-maker-live.service",
        status="paused",
        bankroll_env="BOT_D_MAKER_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Weather Fade maker live probe. Operator-halted with all live services "
            "on 2026-05-19; retained in cap/accounting surfaces for residual exposure."
        ),
        display_name="Nimbus Maker Live Probe",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-d-maker-live",),
    ),
    BotMeta(
        bot_id="bot_d_source_shadow",
        archetype="short_surprise",
        systemd_unit="polymarket-bot-d-source-shadow.service",
        status="paper_tuning",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Bot D source-sliced paper shadow: live-shaped Weather Fade "
            "settings under a separate bot_id for source/tier/city proof. "
            "No wallet keys, no live orders."
        ),
        display_name="Nimbus Source Shadow (paper)",
        dashboard_services=("polymarket-bot-d-source-shadow",),
    ),
    BotMeta(
        bot_id="bot_d_ensemble_ladder",
        archetype="weather_ladder",
        systemd_unit="polymarket-bot-d-ensemble-ladder.service",
        status="paper_tuning",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Bot D Ensemble Ladder paper lane: station-exact ICON/GFS/ECMWF "
            "consensus baskets across adjacent cheap YES temperature buckets. "
            "Event rows only; no CLOB client, orders, fills, or positions."
        ),
        display_name="Nimbus Ensemble Ladder Paper",
        dashboard_services=("polymarket-bot-d-ensemble-ladder",),
    ),
    BotMeta(
        bot_id="bot_d_spike",
        archetype="weather_longshot",
        systemd_unit="polymarket-bot-d-spike.service",
        status="live",
        bankroll_env="BOT_D_SPIKE_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Bot D-Spike Strategy E tiny live probe: 6-12h cheap-YES weather "
            "buckets in positive-EV cities, max $2 order / $10 daily gross / "
            "$20 open exposure."
        ),
        display_name="Nimbus Spike Live Probe",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-d-spike",),
    ),
    BotMeta(
        bot_id="bot_d_spike_short",
        archetype="weather_longshot",
        systemd_unit="polymarket-bot-d-spike-short-vps.service",
        status="archived",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Bot D-Spike-Short Strategy E2 paper lane. Archived by ADR-187 "
            "after the 2026-05-26 shutdown packet; negative paper evidence "
            "and no live-transfer case."
        ),
        display_name="Nimbus Spike Short Paper",
        dashboard_services=("polymarket-bot-d-spike-short-vps",),
    ),
    BotMeta(
        bot_id="bot_d_station_lock",
        archetype="weather_longshot",
        systemd_unit="polymarket-bot-d-station-lock-live-probe.service",
        status="paused",
        bankroll_env="BOT_D_STATION_LOCK_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Bot D Station Lock tiny live probe. Operator-halted with all live "
            "services on 2026-05-19; retained in cap/accounting surfaces."
        ),
        display_name="Nimbus Station Lock Live Probe",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-d-station-lock-live-probe",),
    ),
    BotMeta(
        bot_id="bot_e",
        archetype="momentum_obi",
        systemd_unit="polymarket-bot-e-recorder.service",
        status="sensor",
        bankroll_env="BOT_E_BANKROLL_USD",
        include_in_cap=False,
        description="Maker Flow trading retired by ADR-092; recorder/replay retained as shared data infrastructure.",
        display_name="Scribe (Market Recorder)",
    ),
    BotMeta(
        bot_id="bot_f",
        archetype="copy",
        systemd_unit="polymarket-bot-f-mirror.service",
        status="archived",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Whale-sensor identity. No active service. Crowd/cascade data "
            "rows preserved as historical evidence. Superseded by "
            "wallet_observer (ADR-126/137) and bot_h_maker_v2 (ADR-134) "
            "for active wallet-flow research. Archive-confirmed in the "
            "2026-05-09 final evaluation pass."
        ),
        display_name="Sonar (Cascade Detector)",
    ),
    BotMeta(
        bot_id="bot_f_mirror",
        archetype="copy",
        systemd_unit="polymarket-bot-f-paper-mirror.service",
        status="archived",
        bankroll_env=None,  # fixed $5/trade
        include_in_cap=False,
        description="Legacy Bot F paper executor. Archived from active surfaces by ADR-071.",
        display_name="Sonar Mirror (legacy)",
    ),
    BotMeta(
        bot_id="bot_f_momentum_paper",
        archetype="crowd_momentum",
        systemd_unit="polymarket-bot-f-momentum-paper.service",
        status="archived",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Archived Bot F same-side momentum paper ledger. ADR-187 stopped "
            "the timer after the 2026-05-26 audit confirmed 0 entries after "
            "a large run sample."
        ),
        display_name="Sonar Momentum Paper",
        dashboard_services=("polymarket-bot-f-momentum-paper",),
    ),
    BotMeta(
        bot_id="bot_g",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-longshot.service",
        status="archived",
        bankroll_env="BOT_G_BANKROLL_USD",
        include_in_cap=False,
        description="Original raw longshot-fade cohort. Archived 2026-04-30 after 100 closed / -51% ROI.",
        display_name="Dash (Longshot Raw, archived)",
    ),
    BotMeta(
        bot_id="bot_g_jackpot",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-jackpot.service",
        status="archived",
        bankroll_env="BOT_G_BANKROLL_USD",
        include_in_cap=False,
        description="Bot G raw jackpot cohort. Archived 2026-04-30 after 80 closed / 0 wins.",
        display_name="Dash Jackpot (archived)",
    ),
    BotMeta(
        bot_id="bot_g_scalp",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-scalp.service",
        status="archived",
        bankroll_env="BOT_G_BANKROLL_USD",
        include_in_cap=False,
        description="Bot G raw scalp cohort. Archived 2026-04-30; retained as evidence for Prime.",
        display_name="Dash Scalp (archived)",
    ),
    BotMeta(
        bot_id="bot_g_prime",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime.service",
        status="paper",
        bankroll_env="BOT_G_BANKROLL_USD",
        include_in_cap=True,
        description="Bot G Prime: 4-8c late crypto tails with CEX confirmation. Paper-only.",
        display_name="Dash Prime",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-g-prime",),
    ),
    BotMeta(
        bot_id="bot_g_prime_live",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-live.service",
        status="paused",
        bankroll_env="BOT_G_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Bot G Prime live $1 high-tail data-gathering micro-probe. "
            "Operator-halted with all live services on 2026-05-19."
        ),
        display_name="Dash Prime Live",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-g-prime-live",),
    ),
    BotMeta(
        bot_id="bot_g_prime_live_maker",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-live-maker-paper.service",
        status="archived",
        bankroll_env="BOT_G_LIVE_WALLET_USD",
        include_in_cap=False,
        description=(
            "Archived maker paper-shadow of Bot G Prime Live. ADR-187 stopped "
            "the lane after negative maker-shadow evidence; no live wallet path."
        ),
        display_name="Dash Prime Live Maker Shadow (paper)",
        dashboard_services=("polymarket-bot-g-prime-live-maker-paper",),
    ),
    BotMeta(
        bot_id="bot_g_prime_maker",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-maker-paper.service",
        status="shadow",
        bankroll_env="BOT_G_BANKROLL_USD",
        include_in_cap=False,
        description=(
            "Maker paper-shadow of Bot G Prime paper: 4-8c late crypto "
            "tails, resting at bid with taker baseline retained."
        ),
        display_name="Dash Prime Maker Shadow (paper)",
        dashboard_services=("polymarket-bot-g-prime-maker-paper",),
    ),
    BotMeta(
        bot_id="bot_g_prime_shadow_maker",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-shadow-maker-paper.service",
        status="archived",
        bankroll_env="BOT_G_LIVE_WALLET_USD",
        include_in_cap=False,
        description=(
            "Archived maker paper-shadow of Bot G live-mirror paper lane. "
            "ADR-187 stopped the lane after negative maker-shadow evidence."
        ),
        display_name="Dash Prime Live-Mirror Maker Shadow (paper)",
        dashboard_services=("polymarket-bot-g-prime-shadow-maker-paper",),
    ),
    BotMeta(
        bot_id="bot_g_prime_shadow",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-shadow.service",
        status="archived",
        bankroll_env="BOT_G_LIVE_WALLET_USD",
        include_in_cap=False,
        description=(
            "Archived Bot G paper-only live mirror. ADR-187 stopped the "
            "3.5-5.5c live-shaped cohort after negative transfer evidence."
        ),
        display_name="Dash Prime Live Mirror (paper)",
        dashboard_services=("polymarket-bot-g-prime-shadow",),
    ),
    BotMeta(
        bot_id="bot_g_prime_high_tail",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-high-tail.service",
        status="archived",
        bankroll_env="BOT_G_BANKROLL_USD",
        include_in_cap=False,
        description=(
            "Archived Bot G paper-only high-tail probe. ADR-187 stopped the "
            "6.5-8c lane after the 2026-05-26 audit found no live candidate."
        ),
        display_name="Dash Prime High Tail (paper)",
        dashboard_services=("polymarket-bot-g-prime-high-tail",),
    ),
    BotMeta(
        bot_id="bot_g_prime_high_tail_maker",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-high-tail-maker-paper.service",
        status="archived",
        bankroll_env="BOT_G_BANKROLL_USD",
        include_in_cap=False,
        description=(
            "Archived maker paper-shadow of Bot G high-tail paper lane. "
            "ADR-187 stopped the lane after negative maker-shadow evidence."
        ),
        display_name="Dash Prime High-Tail Maker Shadow (paper)",
        dashboard_services=("polymarket-bot-g-prime-high-tail-maker-paper",),
    ),
    BotMeta(
        bot_id="bot_g_prime_late_cheap",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-late-cheap.service",
        status="archived",
        bankroll_env="BOT_G_BANKROLL_USD",
        include_in_cap=False,
        description=(
            "Bot G paper late-cheap probe (1-3c, 30s, BTC/ETH/SOL). "
            "Archived 2026-05-09 by ADR-140 after 152 closed / 1 win / "
            "-86.4% ROI; ADR-128 -100% rolling-ROI floor violated; "
            "thesis falsified."
        ),
        display_name="Dash Prime Late Cheap (paper, archived)",
        dashboard_services=("polymarket-bot-g-prime-late-cheap",),
    ),
    BotMeta(
        bot_id="bot_g_prime_take_profit",
        archetype="longshot",
        systemd_unit="polymarket-bot-g-prime-take-profit.service",
        status="archived",
        bankroll_env="BOT_G_LIVE_WALLET_USD",
        include_in_cap=False,
        description=(
            "Bot G paper take-profit probe (live-mirror entries with "
            "synthetic 50c exits inside the final 25s-8s window). "
            "Archived 2026-05-09 by ADR-140 after 65 closed / 1 win / "
            "-67.5% ROI; replay shows 0/26 positions ever hit the 50c "
            "threshold; thesis decisively falsified."
        ),
        display_name="Dash Prime Take Profit (paper, archived)",
        dashboard_services=("polymarket-bot-g-prime-take-profit",),
    ),
    BotMeta(
        bot_id="crypto_probability_gap_paper",
        archetype="crypto_fair_value",
        systemd_unit="polymarket-crypto-prob-gap-paper.service",
        status="archived",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Crypto fair-value probability-gap paper lane. Archived by "
            "ADR-139 after forward paper failed OQ-078 robustness gates; "
            "shared crypto recorder feed retained."
        ),
        display_name="Meridian Probability Gap Paper",
        dashboard_services=("polymarket-crypto-prob-gap-paper",),
    ),
    BotMeta(
        bot_id="crypto_probability_gap_paper_maker",
        archetype="crypto_fair_value",
        systemd_unit="polymarket-crypto-prob-gap-maker-paper.service",
        status="shadow",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Maker paper-shadow for the archived crypto FV probability-gap "
            "lane. Kept report-only for maker-vs-taker evidence; taker "
            "baseline and ADR-139 archive status remain unchanged."
        ),
        display_name="Meridian Probability Gap Maker Shadow",
        dashboard_services=("polymarket-crypto-prob-gap-maker-paper",),
    ),
    BotMeta(
        bot_id="crypto_probability_gap_live_maker",
        archetype="crypto_fair_value",
        systemd_unit="polymarket-crypto-prob-gap-live-maker.service",
        status="paused",
        bankroll_env="CRYPTO_PROB_GAP_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Paused crypto FV probability-gap live-maker probe. Realised live "
            "P&L remains dashboard-visible for postmortem, but ADR-181 blocks "
            "restart until wallet-level accounting is repaired."
        ),
        display_name="Meridian Probability Gap Live Maker",
        dashboard_visible=True,
        dashboard_services=("polymarket-crypto-prob-gap-live-maker",),
    ),
    BotMeta(
        bot_id="crypto_brownian_fv_paper",
        archetype="crypto_fair_value",
        systemd_unit="polymarket-crypto-brownian-fv-paper.service",
        status="archived",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Crypto Brownian fair-value paper lane. Archived by ADR-139 "
            "after forward paper failed OQ-078 robustness gates; shared "
            "crypto recorder feed retained."
        ),
        display_name="Meridian Brownian Paper",
        dashboard_services=("polymarket-crypto-brownian-fv-paper",),
    ),
    BotMeta(
        bot_id="crypto_brownian_fv_paper_maker",
        archetype="crypto_fair_value",
        systemd_unit="polymarket-crypto-brownian-fv-maker-paper.service",
        status="shadow",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Maker paper-shadow for the archived crypto Brownian FV lane. "
            "Kept report-only for maker-vs-taker evidence; taker baseline "
            "and ADR-139 archive status remain unchanged."
        ),
        display_name="Meridian Brownian Maker Shadow",
        dashboard_services=("polymarket-crypto-brownian-fv-maker-paper",),
    ),
    BotMeta(
        bot_id="crypto_brownian_fv_live_maker",
        archetype="crypto_fair_value",
        systemd_unit="polymarket-crypto-brownian-fv-live-maker.service",
        status="paused",
        bankroll_env="CRYPTO_BROWNIAN_FV_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Paused crypto Brownian FV live-maker probe. Realised live P&L "
            "remains dashboard-visible for postmortem, but ADR-181 blocks "
            "restart until wallet-level accounting is repaired."
        ),
        display_name="Meridian Brownian Live Maker",
        dashboard_visible=True,
        dashboard_services=("polymarket-crypto-brownian-fv-live-maker",),
    ),
    BotMeta(
        bot_id="bot_h_maker_v2",
        archetype="maker_recorder",
        systemd_unit="polymarket-bot-h-maker-v2-recorder.service",
        status="sensor",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Bot H Maker V2 Phase 1: paper-only WSS recorder over the wide "
            "politics+sports+awards+crypto cell scope per ADR-134. Phase 2 "
            "quote engine (politics 0-10c, sports 10-20c) ships only after "
            "operator review of recorder data."
        ),
        display_name="Quill (Maker Flow Recorder)",
        dashboard_services=("polymarket-bot-h-maker-v2-recorder",),
    ),
    BotMeta(
        bot_id="bot_h_maker_v2_quote_paper",
        archetype="maker_flow",
        systemd_unit="polymarket-bot-h-maker-v2-quote-paper.service",
        status="paper_tuning",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Bot H Maker V2 quote-paper simulator: paper SELL-YES quote/fill "
            "ledger on the ADR-134 target cells. Uses maker_recorder.db only; "
            "no wallet keys and no live CLOB orders."
        ),
        display_name="Quill Quote Paper",
        dashboard_services=("polymarket-bot-h-maker-v2-quote-paper",),
    ),
    BotMeta(
        bot_id="wallet_observer",
        archetype="wallet_sensor",
        systemd_unit="polymarket-wallet-observer.service",
        status="sensor",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Wallet observer: passive Polygon CTF Exchange recorder for the "
            "245 retail-tier wallets (Tier A + Tier B). No trading. ADR-137 "
            "forward-validation feed for the wallet-tag cohort."
        ),
        display_name="Wallet Observer",
        dashboard_services=("polymarket-wallet-observer",),
    ),
    BotMeta(
        bot_id="wallet_tag_feature_shadow",
        archetype="wallet_feature",
        systemd_unit="polymarket-wallet-tag-feature-shadow.service",
        status="paper_tuning",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Wallet-tag feature shadow: paper ledger for low-bot-score wallet "
            "BUY rows from wallet_tag_forward.db. Feature evidence only; no "
            "copy-trading and no order placement."
        ),
        display_name="Wallet-Tag Feature Shadow",
        dashboard_services=("polymarket-wallet-tag-feature-shadow",),
    ),
    BotMeta(
        bot_id="wallet_tag_elite_cap_paper",
        archetype="wallet_feature",
        systemd_unit="polymarket-wallet-tag-elite-cap-paper.service",
        status="paper_tuning",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Wallet-tag elite cap paper: capped $1/signal paper lane over the "
            "four 2026-05-26 profitable wallet suffixes. One entry per "
            "wallet/market, $15 open-exposure cap, no copy-trading and no "
            "order placement."
        ),
        display_name="Wallet-Tag Elite Cap Paper",
        dashboard_visible=True,
        dashboard_services=("polymarket-wallet-tag-elite-cap-paper",),
    ),
    BotMeta(
        bot_id="wc_negrisk_basket_paper",
        archetype="negrisk_basket",
        systemd_unit="polymarket-wc-negrisk-basket-paper.service",
        status="archived",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Archived WC / negRisk basket paper monitor. ADR-187 stopped the "
            "timer after the 2026-05-26 audit found the lane fee-gated or "
            "illiquid at solo-operator scale."
        ),
        display_name="WC negRisk Basket Paper",
        dashboard_services=("polymarket-wc-negrisk-basket-paper",),
    ),
    BotMeta(
        bot_id="bot_i_persistence",
        archetype="late_window_persistence",
        systemd_unit="polymarket-persistence-paper.service",
        # ADR-128 specifies paper replay-on-recorder behaviour: it does
        # not place CLOB orders, it accumulates synthetic entries in a
        # local SQLite for the n=50/cell forward gate. Dashboard grouping
        # follows the promotion decision in ADR-142: active paper bot,
        # not recorder infrastructure.
        status="paper_tuning",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Bot I Persistence: paper replay-on-recorder for two-cell strategy "
            "from V2 calibration sweep (ADR-128). Cell A = 5m+15m BTC/ETH/SOL "
            "up/down at mid 0.50-0.55 in last 60s; Cell B = 15m at mid "
            "0.85-0.95. Daily timer at 06:30 UTC. Halt switch on cumulative "
            "post-fee ROI < -5% on n>=100. the bot container-local."
        ),
        display_name="Persistence Paper (I)",
        dashboard_services=("polymarket-persistence-paper",),
    ),
    BotMeta(
        bot_id="bot_i_persistence_maker",
        archetype="late_window_persistence",
        systemd_unit="polymarket-bot-i-persistence-maker-paper.service",
        status="shadow",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Maker paper-shadow of Bot I Persistence replay: same cells and "
            "daily recorder scan, but accounts entries at bid with zero maker "
            "fee. Separate DB/report keeps the taker baseline intact."
        ),
        display_name="Persistence Maker Shadow (I paper)",
        dashboard_services=("polymarket-bot-i-persistence-maker-paper",),
    ),
    BotMeta(
        bot_id="bot_i_persistence_live",
        archetype="late_window_persistence",
        systemd_unit="polymarket-bot-i-persistence-live.service",
        status="paused",
        bankroll_env="BOT_I_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Paused Bot I Persistence live tiny probe. It used a separate "
            "persistence_live.db ledger; ADR-181 blocks restart until Bot I "
            "winner accounting and wallet-level ownership reconciliation are fixed."
        ),
        display_name="Persistence Live (I)",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-i-persistence-live",),
    ),
    BotMeta(
        bot_id="bot_i_persistence_live_maker",
        archetype="late_window_persistence",
        systemd_unit="polymarket-bot-i-persistence-live-maker-paper.service",
        status="shadow",
        bankroll_env="BOT_I_LIVE_WALLET_USD",
        include_in_cap=False,
        description=(
            "Maker paper-shadow of Bot I Persistence Live under the same "
            "$5/$100 operator envelope. Report-only until S6 evidence clears."
        ),
        display_name="Persistence Live Maker Shadow (I paper)",
        dashboard_services=("polymarket-bot-i-persistence-live-maker-paper",),
    ),
    BotMeta(
        bot_id="bot_i_cell_c_maker",
        archetype="late_window_persistence",
        systemd_unit="polymarket-bot-i-cell-c-maker-paper.service",
        status="shadow",
        bankroll_env="BOT_I_LIVE_WALLET_USD",
        include_in_cap=False,
        description=(
            "Cell C maker paper-shadow for the maker-conversion S7 gate: "
            "BTC/ETH/SOL 5m+15m up/down at mid_high 0.95-0.99, accounted at "
            "bid with zero maker fee. Separate DB/report; no live orders."
        ),
        display_name="Cell C Maker Shadow (I paper)",
        dashboard_services=("polymarket-bot-i-cell-c-maker-paper",),
    ),
    BotMeta(
        bot_id="bot_j_nr_wallet",
        archetype="wallet_filter",
        systemd_unit="polymarket-bot-j-nr-wallet-paper.service",
        status="paused",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Paused Bot J Near-Resolution Wallet paper lane. ADR-187 stopped "
            "runtime collection until OQ-113 has decision-grade closed evidence."
        ),
        display_name="Relay (NR Wallet Paper)",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-j-nr-wallet-paper",),
    ),
    BotMeta(
        bot_id="bot_k_sports_taker",
        archetype="market_open_taker",
        systemd_unit="polymarket-bot-k-sports-taker-paper.service",
        status="paused",
        bankroll_env=None,
        include_in_cap=False,
        description=(
            "Paused Bot K Sports Taker paper lane. ADR-187 stopped runtime "
            "collection until OQ-114 has decision-grade forward resolved evidence."
        ),
        display_name="Playbook (Sports Taker Paper)",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-k-sports-taker-paper",),
    ),
    BotMeta(
        bot_id="bot_l_complete_set",
        archetype="complete_set_convergence",
        systemd_unit="polymarket-bot-l-complete-set-live-probe-vps.service",
        status="paused",
        bankroll_env="BOT_L_COMPLETE_SET_LIVE_WALLET_USD",
        include_in_cap=True,
        description=(
            "Bot L BTC 5-minute complete-set BUY/MERGE tiny live probe. "
            "Operator-halted with all live services on 2026-05-19; paper timer stays separate."
        ),
        display_name="Compass (BTC Complete-Set Live Probe)",
        dashboard_visible=True,
        dashboard_services=("polymarket-bot-l-complete-set-live-probe-vps.timer",),
    ),
)


def by_id() -> dict[str, BotMeta]:
    """Return {bot_id: BotMeta} for O(1) lookup."""
    return {b.bot_id: b for b in REGISTRY}


def all_bot_ids() -> tuple[str, ...]:
    """All known bot_ids, in registration order."""
    return tuple(b.bot_id for b in REGISTRY)


def active_bot_ids() -> tuple[str, ...]:
    """bot_ids that are NOT archived (includes paper, live, shadow, sensor)."""
    return tuple(b.bot_id for b in REGISTRY if b.status != "archived")


def dashboard_bot_ids() -> tuple[str, ...]:
    """bot_ids that should appear in the active operator dashboard."""
    return tuple(b.bot_id for b in REGISTRY if b.dashboard_visible)


def archived_dashboard_bot_ids() -> tuple[str, ...]:
    """bot_ids hidden from aggregate dashboard/report surfaces by default."""
    hidden = {b.bot_id for b in REGISTRY if not b.dashboard_visible}
    # Historical event/order rows used this variant-like id even though it is
    # not a registry bot_id.
    hidden.add("bot_f_paper_mirror")
    return tuple(sorted(hidden))


def cap_member_bot_ids() -> tuple[str, ...]:
    """bot_ids that contribute to the aggregate fleet exposure cap."""
    return tuple(b.bot_id for b in REGISTRY if b.include_in_cap)


def archetype_map() -> dict[str, str]:
    """{bot_id: archetype} — replaces the legacy BOT_ARCHETYPE dict in
    core/fleet.py. Includes every bot, so archetype_exposure_breakdown
    no longer returns "unknown" for bot_f_mirror / bot_g etc."""
    return {b.bot_id: b.archetype for b in REGISTRY}


def systemd_units() -> tuple[str, ...]:
    """All systemd units in the fleet, excluding shadows that run
    in-process. Used by watchdog + readiness scripts + dashboard."""
    return tuple(b.systemd_unit for b in REGISTRY if b.systemd_unit)


def active_systemd_units() -> tuple[str, ...]:
    """Long-running systemd units for the current active operating model."""
    extra = {
        "polymarket-bot-g-prime-maker-paper.service",
        "polymarket-maker-conversion-gate-watch.timer",
        "polymarket-bot-g-lead-bucket-roi-report.timer",
        "polymarket-bot-d-source-shadow.service",
        "polymarket-bot-d-spike.service",
        "polymarket-bot-h-maker-v2-recorder.service",
        "polymarket-bot-h-maker-v2-quote-paper.service",
        "polymarket-bot-h-maker-v2-quote-paper.timer",
        "polymarket-bot-h-maker-v2-resolution-backfill.timer",
        "polymarket-bot-h-maker-v2-daily-replay.timer",
        "polymarket-bot-l-complete-set-paper-vps.service",
        "polymarket-bot-l-complete-set-paper-vps.timer",
        "polymarket-wallet-observer.service",
        "polymarket-wallet-observer-daily-report.timer",
        "polymarket-wallet-tag-feature-shadow.service",
        "polymarket-wallet-tag-feature-shadow.timer",
        "polymarket-wallet-tag-elite-cap-paper.timer",
        "polymarket-bot-e-recorder.service",
        "polymarket-persistence-paper.service",
        "polymarket-persistence-paper.timer",
        "polymarket-bot-i-persistence-maker-paper.service",
        "polymarket-bot-i-persistence-maker-paper.timer",
        "polymarket-bot-i-persistence-live-maker-paper.service",
        "polymarket-bot-i-persistence-live-maker-paper.timer",
        "polymarket-bot-d-wallet-reconcile.service",
        "polymarket-bot-d-wallet-reconcile.timer",
        "polymarket-dashboard.service",
        "polymarket-notify.service",
        "polymarket-watchdog.service",
    }
    units = {
        b.systemd_unit
        for b in REGISTRY
        if b.dashboard_visible and b.systemd_unit and b.status != "paused"
    }
    units |= extra
    return tuple(sorted(units))


def meta(bot_id: str) -> BotMeta | None:
    """Lookup by bot_id; None if not found (caller decides how to handle)."""
    return by_id().get(bot_id)
