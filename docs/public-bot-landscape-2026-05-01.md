# Public Bot Landscape First Pass

**Date:** 2026-05-01
**Status:** First pass; not yet wallet-complete.
**Purpose:** Replace vague "contrarian" claims with observed public bot
archetypes and a concrete data request for named wallet classification.

## Current Finding

The public Polymarket automation landscape is crowded enough that direct
copy-trading, generic market-making, and short-horizon crypto automation
should be treated as contested surfaces. This does not prove the fleet has a
contrarian edge. It proves the next step: measure named wallets and strategy
archetypes before using "opposite of other bots" as a thesis.

## Public Archetypes

| Archetype | Public evidence checked 2026-05-01 | Strategic implication |
|---|---|---|
| Copy-trading bots | QuickNode has a 2026 guide for building a Polymarket copy-trading bot that tracks a wallet, logs trades in real time, and adds position tracking/risk caps. Polybuild and multiple Reddit/side-project posts advertise wallet-copying tools. | Direct mirror trading is crowded. Bot F should measure post-copy-cascade drift before expanding allowlists. |
| Telegram execution/copy tools | QuickNode marketplace lists PolyCop as a Telegram execution layer for Polymarket with copy trading/sniping positioning. Search results also show Shadower and PolyApex-style tools. | Latency-adjusted copying is a commercial product category, not a hidden edge. |
| Market makers | Official Polymarket market-maker docs and liquidity rewards docs describe resting limit orders, two-sided depth, spread scoring, and daily maker rewards. | Maker economics can matter, but adverse selection and reward reconciliation must be modeled. |
| Liquidity reward farmers | Polymarket rewards formula pays daily to maker addresses, has a $1 minimum payout, and scores order size/tightness across samples. | A break-even maker strategy plus rewards is plausible enough to analyze, not enough to assume. |
| Short-horizon crypto automation | Local repo history, public bot posts, and Polymarket developer guides show crypto bots are common. | Bot E/G must avoid taker-heavy churn and prove maker fill quality. |
| Whale/large-trader analytics | Academic and public commentary around 2024 election markets focuses on whale traders and transaction-level flow. | Wallet flow can be a signal, but naive following risks crowding and manipulation. |

## Named Wallets/Actors From Existing Local Research

These names appear in local project docs and should be revalidated before
being treated as current competitors:

| Name | Source context | Use |
|---|---|---|
| `swisstony` | `docs/bot-f-ideas.md`, sports structural-arb example. | Candidate archetype: sports cross-market / structural trader. |
| `gatorr` | `docs/bot-f-ideas.md`, sports state-change repricing example. | Candidate archetype: sports repricing. |
| `tradecraft` | `docs/bot-f-ideas.md`, tennis directional hedge example. | Candidate archetype: skewed hedged directional. |
| `kch123` | `docs/bot-f-ideas.md`, NBA/NHL probability model example. | Candidate archetype: sports model + hedge. |

These are not yet classified as active 2026 bot wallets. They are seeds for
the named-wallet pass.

## Data Work Required

To satisfy Opus's critique, the next report must classify at least 10 named
wallets or tools:

1. Pull top recent wallets by volume/P&L where public APIs allow it.
2. Classify each wallet by category mix, hold time, repeat cadence, order
   size, and signal-lag profile.
3. Estimate capital footprint and whether the behavior looks like:
   market-making, copy-trading, sports model, crypto scalper, whale, or
   unknown.
4. Compare our candidate trades against these archetypes:
   - are we following,
   - fading,
   - avoiding,
   - or trading an unrelated surface?

## Sources Checked

- QuickNode trading guide index, "Building a Polymarket Copy Trading Bot",
  created 2026-02-20:
  <https://www.quicknode.com/guides/tags/trading>
- QuickNode marketplace listing for PolyCop:
  <https://www.quicknode.com/builders-guide/tools/polycop-by-polycop?category=trading-tools>
- Polymarket market-maker docs:
  <https://docs.polymarket.com/market-makers/overview>
- Polymarket liquidity rewards:
  <https://docs.polymarket.com/market-makers/liquidity-rewards>
- Polybuild copy-trading post:
  <https://www.polybuild.app/blog/polymarket-copy-trading-bot>
- Search-visible Reddit/side-project posts from February-March 2026 advertising
  copy-trading and AI Polymarket bots. These are treated as weak evidence of
  crowdedness, not performance proof.

