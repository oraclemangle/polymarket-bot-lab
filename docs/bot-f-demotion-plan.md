# Bot F Demotion Plan — Executor Dropped, Sensor Survives

**Date:** 2026-04-17 (Session 17g execution).
**Owner:** Claude proposes; operator approves deploy changes on LXC.
**Objective:** drop Bot F as a trading bot. Keep it alive as read-only intelligence infrastructure that feeds Bot A / Bot B as down-weighters.

---

## Why

Local `data/bot_f.db` evidence: 200 mirror signals, **zero** with `would_have_traded = 1`. Every signal rejected with `age > 90s`. Production has 2117 signals / 404 would-trade / 45 wallets — but production's "would have traded" is synthetic (the executor never ran live). The 90s latency cutoff is binding on every local signal; from an UK homelab routed through Stockholm the VPN provider, the latency race against on-chain Polygon block indexers is structurally lost.

Meanwhile the crowded-competitor problem (Codex peer review flagged 2/5 confidence, named PolyProbs, WhaleTrail, PolyCopyTrade as live competitors) means even if we could fill faster, the alpha is being actively competed away.

But the **observation infrastructure** has value independent of execution:
- 45-wallet ranked dataset.
- WSS subscription infrastructure.
- Mirror-signal event stream.

Repurpose these to feed Bot A / Bot B candidate filters as **down-weighters**: "don't buy into markets where 6+ known copy-bots just entered."

---

## Deletions

### From `bots/bot_f/`
- `executor.py` — delete entirely (the "trigger" path).
- `README.md` — rewrite to reflect sensor role.

### From `bots/bot_f/__main__.py`
- Remove the `Trigger` loop and its `ClobWrapper` wiring.
- Remove any `POLYMARKET_ENV=live` handling.
- Keep the `Hunter` (daily ranker) and `Mirror` (WSS observer) loops.
- Delete `would_have_traded` path from `Mirror` — replace with pure signal-emission.

### From `bots/bot_f/config.py`
- Delete `FBankrollConfig`, per-trade size, order caps — any executor-side config.
- Keep ranking thresholds, WSS reconnect params.

### From the bot LXC container
- Stop and disable `polymarket-bot-f.service`.
- Replace with `polymarket-bot-f-sensor.service` (new; reads-only) once F-2 lands.

---

## Additions (for F-2; can follow in a later session)

### New table: `crowd_signals`

```sql
CREATE TABLE crowd_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at DATETIME NOT NULL,
    condition_id TEXT NOT NULL,
    category TEXT,
    wallet_inflow_count_6h INTEGER NOT NULL,
    bot_pattern_wallet_count_6h INTEGER NOT NULL,
    category_inflow_24h_usd NUMERIC(18, 2),
    score REAL NOT NULL  -- 0.0 to 1.0; how 'crowded' this market looks right now
);
CREATE INDEX ix_crowd_cid_ts ON crowd_signals(condition_id, computed_at);
CREATE INDEX ix_crowd_category_ts ON crowd_signals(category, computed_at);
```

### New module: `bots/bot_f/sensor.py`

Daily cron job. Reads `mirror_signals` + `hunter_rankings` + on-chain Polygon data. Writes `crowd_signals`. No orders. No Polymarket CLOB access needed.

### Consumption

`bots/bot_a/candidates.py` and `bots/bot_b/candidates.py` each gain a **down-weighter** hook:

```python
from bots.bot_f.crowd import is_crowd_contested

def filter_candidates(cands):
    return [c for c in cands if not is_crowd_contested(c.condition_id, threshold=6)]
```

`is_crowd_contested(cid, threshold)` returns True if `crowd_signals.bot_pattern_wallet_count_6h >= threshold`. Default threshold 6 = very conservative; can be tuned when data accumulates.

**Opt-in only.** Bot A and Bot B's behavior without the hook is unchanged. The hook is off by default; operator enables via env once the signal is validated.

---

## What we preserve

- The 45-wallet hunter rankings dataset.
- The WSS mirror infrastructure (free intelligence flow).
- The ability to flip Bot F back to executor mode in a future session IF the second-order anti-bot thesis finds real edge (unlikely but not forbidden).

## What we lose

- The notion that copy-trading whales is a viable direct strategy for this operator.
- Executor code paths that never landed a real trade anyway.

---

## Migration sequence

1. **Session 17g (this session):** draft this plan. No code deletion yet — deletion needs a fresh session with Bot F scope.
2. **Next session:** delete `executor.py`; strip `__main__.py`; update LXC systemd unit; run `.venv/bin/pytest`; commit.
3. **Session +2:** F-2 `crowd_signals` table + sensor module + (optional) Bot A/B integration hook. Opt-in; default disabled.

---

## Dashboard implications

Bot F row on the dashboard becomes an **intelligence panel**, not a P&L row:
- Top 5 wallets by recent activity.
- Crowd-contested market count today.
- Category inflow rankings.
- No "Live / Paper / 7d P&L" columns for Bot F.

The S-1 dashboard scorecard covers Bots A/B/C/D/E only.

---

## Privacy / security

- `hunter_rankings` contains pseudo-public wallet addresses. Not PII in the HIGH sense, but do not upload to cloud LLMs.
- The sensor reads on-chain Polygon data via Alchemy/Infura free tier. Stay in free tier; rate-limit defensively.
- No Polymarket CLOB calls from the sensor (no auth required).

---

## Kill criteria

Sensor-role Bot F has no kill date — low cost, persistent intelligence value. However:
- If `crowd_signals` emits < 10 distinct crowd-contested markets/week for 4 consecutive weeks, the sensor isn't seeing any competitor crowding and can be idled.
- If Bot A / Bot B enable the hook and observe > 20% candidate-set shrinkage with no improvement in realised edge after 60 days, the down-weighter is wrong and gets disabled.
