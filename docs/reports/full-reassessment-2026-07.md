# Full Reassessment 2026-07 — Where Is the Edge?

**Date:** 2026-07-20  
**Session:** 468  
**Status:** Final verdict (analysis complete; this file is the write-up only)  
**Author:** Grok report writer/executor (director goal loop)  
**Mode:** Docs only. No code, `.env`, keystore, systemd, bot runtime, SSH, or live paths touched.  
**Capital framing:** $2k total research/ops budget; current funding note `$137` (live only with explicit the operator approval).  
**Evidence pack (canonical):**  
`/private/tmp/claude-501/-Users-operator-Code-longshot-research--claude-worktrees-elated-meninsky-482395/0f5cdd1a-0c3a-46c3-a66e-01f240a7196f/scratchpad/evidence-pack.md`  
**Companion inputs (scratchpad):**  
Original files `candidates.md`, `grok_adversarial.md`, `codex_ranking.md`, `grok_x_insight.md` were lost to tmp cleanup during Session 468 turn 1. Kill-criteria, Codex fee correction, and X-insight content were **restored verbatim** from the director's session transcript into `scratchpad/kill_criteria_restored.md` (2026-07-11 Grok 4.5 high adversarial pass + Codex gpt-5.5 additions + 2026-07-08 X survey one-liner). Only the **raw full transcripts** remain unavailable. Evidence numbers remain from `evidence-pack.md` and accepted repo reports/ADRs.

**Cross-refs:** ADR-033, ADR-139, ADR-176, ADR-181, ADR-183, ADR-185, ADR-187, ADR-191..194 (this session), OQ-123, OQ-124, OQ-127..133, `docs/reports/strategy-ranking-and-data-roadmap-2026-05-09.md`, `docs/reports/creative-edge-mining-2026-06-09.md`, `docs/active-operating-model-2026-05-02.md`.

---

## 1. Mission recap

Answer, with numbers and kill gates: **where is the remaining edge** after the 2026-04 through 2026-06 fleet of paper and live probes?

Constraints of this reassessment:

- All analysis already done (Phase 1–3). This session **writes only**.
- the bot container offline (do not SSH).
- Old the VPS provider VPS decommissioned (Session 466).
- Polymarket domains geo-blocked from reachable UK machines.
- Gemini CLI broken (`IneligibleTierError` — Antigravity migration needed).
- Live trading remains **halted** under ADR-183; any future live step needs **explicit the operator approval**, a new ADR, and accounting gates (OQ-123/124).

Operator question this report answers: given a record of 25+ dead or archived lanes and a $2k research budget, what is the single primary research path, the runner-up, and what is permanently presumed dead until stronger evidence?

---

## 2. Method

1. **Director evidence pack** compiled 2026-07-20 from prior empirical work (canary DB, local `backtest.db` re-verification, maker fill stats, sports mid-band re-check, live Bot D P&L, fee dispute notes).
2. **Multi-model consensus** (internal evidence + Grok adversarial + Codex ranking) reported as **unanimous** in the pack on C1 primary / C2 runner-up. Kill-criteria / Codex / X-insight content restored from transcript via `kill_criteria_restored.md`; raw full transcripts remain unavailable.
3. **No re-analysis** of DBs, hosts, or APIs in this write session. Numbers are copied from the pack; no invented figures.
4. **Historical ranking base** remains `docs/reports/strategy-ranking-and-data-roadmap-2026-05-09.md` plus ADRs that archived lanes (especially ADR-033, ADR-139, ADR-181, ADR-183, ADR-185, ADR-187).
5. **Fee stress (Codex correction):** docs show sports `feeRate` **0.05 → max $1.25/100sh** (not $0.75); crypto **0.07 → $1.75**. Re-run every ROI claim with per-market fee metadata, not a hardcoded table. Pending VPN primary-source verification (OQ-130). Formula: `fee = C * feeRate * p * (1-p)`; makers 0 fee + 20–25% rebate share.
6. **X-insight (Grok survey, 2026-07-08):** Publicly hyped lanes (crypto 5m/15m taker, YES+NO arb, copy-trading, buying cheap longshots, UMA plays) are dead or HFT-only for a $2k account; surviving lanes are maker-side execution discipline, behavioral tail-fade, thin niche modeling, and rare slow combinatorial inconsistencies — realistic ceiling at $2k is a few hundred dollars/year.

---

## 3. Strategy-record summary

Pattern (evidence pack + ranking report): **every death = buying overpriced tail as taker, or tail-blind gates**.

| Lane / edge | Best cited P&L or result | Sample | Verdict | Pin |
|---|---|---:|---|---|
| Bot A Longshot Fade | Walk-forward `-$13,613.58`, 93.7% hit | 12,521 trades | Dead / archived | ADR-033 |
| Bot G Prime live | `-$82.84`, `-80.6%` ROI | 51 closed | No scale | ranking 2026-05-09; ADR-183/185 |
| Bot G live mirror / late-cheap / take-profit / raw variants | deeply negative (e.g. late-cheap `-$560.71` / `-86.4%`) | dozens–152 | Dead / archived | ADR-140, ADR-185, ADR-187 |
| Crypto FV Probability Gap | `-$104.00`, `-14.4%` | 144 closed | Dead | ADR-139 |
| Crypto FV Brownian | `-$100.80`, `-10.3%` | 196 closed | Dead | ADR-139 |
| Maker live probes (aggregate this reassessment) | `-$63.25`, `-$104.05` | live probes | Reject reopen until fill-conditioned replay | pack C5; ADR-176/193 |
| Strategy E / E2 weather cheap-YES | Murphy fail / forward 0 wins early | WANGZJ + tiny forward | Dead / archived paper | ADR-185/187; strategy-e2 reports |
| Crowd Momentum F | 0 entries after 1,519 runs | — | Archived | ADR-185/187 |
| WC / negRisk basket | 0 real arbs after gates / fee-gated | monitor | No bot | ADR-119, ADR-185 |
| Wallet-Tag Elite Cap paper | Forward ROI `-16.55%` at $1 | paper | Archive default | overhaul plan; ADR-186/187 |
| Persistence Cell C maker | blocked / live blocked | n=69 borderline | Blocked | ADR-176 |
| Bot I live | paused during loss reassessment | — | Paused | ADR-181, ADR-183 |
| Bot C Pyth | `-$1,149.41` | 233 trades | Dead | ADR-093 |
| Bot B Oraclemangle | parked spin-off | tiny | Hidden | operating model |
| **Bot D live range-fade (survivor)** | **`+$31.06` / `+11.07%` ROI** | **95 closed groups** | Only positive live P&L ever; restart gated on OQ-123/124 | pack C2; ADR-185 |

Full historical ranking table: `docs/reports/strategy-ranking-and-data-roadmap-2026-05-09.md`.  
Fleet pause/archive: ADR-183, ADR-185, ADR-187.

---

## 4. Six candidates (C1–C6)

### C1 — Sports mid-band NO-fade (PRIMARY)

**Thesis:** Buy NO when sports YES is priced **55–75c**, entry **6–78h** pre-close. Expresses favorite-longshot overpricing in the mid band, not the 0–5c tail that killed Bot A/G.

**Evidence for (verbatim pack / linked reports):**

- Independent re-verification on local `backtest.db` (April tape): **n=573** regex-matched sports in 55–75c band; hit **57.4%** vs **63.5c** implied; NO-fade ROI **+5.32%** post-fee (orig creative-edge report **+9.22%**); trade-bootstrap 95% CI **[-4.73%, +15.64%]** — **crosses zero**.
- Favorite-longshot overpricing statistically real **only** in 55–75c YES (implied above Wilson CI upper bound in **60–65c** and **65–70c**), **not** proven at 30–40c.
- Earlier creative-edge mining (2026-06-09): sports n=557, hit 58.5% vs 63.6c implied; post-fee **+9.22%**, ex-top-2 **+8.50%**, day bootstrap **[-5.78%, +23.27%]** — one-week tape risk (OQ-127).
- Wallet-tag historical corroboration (30–50c human BUYs): **+10.1pp**, CI lower **+14.0%**, **n=13,418** (cited in OQ-127 / creative-edge report).
- Landscape: sports **56.5%** of venue volume (secondary, June 2026); venue ~**$5.9B/mo**.

**Evidence against:**

- Bootstrap CI still crosses zero on local tape → **not** paper-ready until WANGZJ multi-month replay with locked sports taxonomy and fee-exact P&L.
- Fee rate **disputed** (see §9); all sports ROI stress must use **$1.25/100sh** conservative max until OQ-130.
- Geo-block blocks primary docs/API from UK machines without VPN/VPS.

**Verdict:** **PRIMARY research path.** Research-first only. No paper lane until OQ-127-style gates clear on multi-month tape. ADR-191.

---

### C2 — Weather range-fade NO restart (Bot D) (RUNNER-UP)

**Thesis:** Restart the only live-positive weather range-fade expression after accounting truth is restored.

**Evidence for:**

- Bot D live probe: **only positive live P&L ever** — **+$31.06 / +11.07% ROI / 95 closed groups** (pack; ADR-185).
- Consistent with mid-band/favorite-longshot pattern (fade overpriced side), not cheap-YES tail buying.

**Evidence against:**

- Paper Bot D is outlier-dominated (historical ex-largest / ex-top-two negatives in bot-d-full-review-audit — see ranking report).
- **OQ-123 / OQ-124** wallet-accounting and residual-exposure gates still open.
- Live fleet remains halted (ADR-183). Current funding note **$137** for any future tiny live packet.
- the bot container offline this session → cannot refresh live ledger truth here.

**Verdict:** **RUNNER-UP.** Live-probe paper-parity restart only after OQ-123/124 close; any live step = explicit the operator approval + ADR. ADR-191.

---

### C3 — Crypto last-minutes leader-follow (STALE-QUOTE MIRAGE presumption)

**Thesis (challenged):** Near close, when CEX is beyond strike, PM mid underreacts and can be faded/followed.

**Fresh calibration (pack):**

- Canary DB (**58G**, 2026-05-13→07-05, the local workstation `(local archive, not exported)`): **271,566,165** `cex_trades`; **27,919,423** `pm_events`; **23,750** markets. Event mix: price_change **25.1M**, best_bid_ask **1.50M**, book **817k**, last_trade_price **384k**.
- Latency (n=282 CEX moves ≥5bps/2s over 300 subs): median PM quote reaction **520ms** (p25 **340ms**, p90 **9.4s**); reacted ≥1c within 2s: **62.4%**; BTC within 5s only **35.7%**; post-move abs mid shift median **2c**, ≥1c in **64.5%**.
- Last-minutes calibration: **357** windows processed of **1271**; **509** skipped dead books (**selection-bias caveat**). Biggest gaps at T-1min distance **10–20bps (+23.7pp, n=26)** and **≥20bps (+20.6pp, n=15)**. Pack also states T-1min, CEX ≥10bps beyond strike: PM **0.76–0.79** vs realized **1.00**, **+17–24pp**, n=**26+15**.

**Evidence against / presumption:**

- Presumed **stale-quote mirage** until a **fill-conditioned** replay on the existing **58GB** tape proves executability.
- Does **not** reopen the near-resolution kill-list line.
- Research autopsy only; **pre-registered permanent kill** if fill-conditioned ROI **≤0** on **n≥200** executable windows.

**Verdict:** Autopsy-only. ADR-192. Ownership for autopsy: OQ-131.

---

### C4 — Elite cheap-tail co-sign (filter only)

**Thesis:** Use PolyVerify low-bot-score wallets' cheap-YES co-sign as a **filter**, never a standalone bot.

**Evidence for:**

- Historical 3–15c CI-lower **+40.5%** (**n=3,815**) stands.
- Local forward **+63%** (**n=74** pack; creative-edge had **+63.1% n=78** on 0–10c) — pack notes single-market artifact risk.

**Evidence against:**

- Local forward **+63% (n=74)** is a **single-market artifact** (one Iran market = whole tail; **ex- that market +22.6% n=51**).
- Failed elite-cap paper (`-16.55%`) mirrored all cohort trades — wrong expression.
- Needs prod settlement join (OQ-128) before any composition with C1.

**Verdict:** Filter only; A/B on top of C1 once prod settlement join exists (60–90d roadmap). Never standalone.

---

### C5 — Maker lanes (REJECTED for now)

**Thesis:** Maker quotes capture spread / rebates where paper showed +10–15%.

**Evidence for:**

- Paper historically **+10–15%** (pack).
- Makers: **0 fee** + **20–25%** rebate share (pack fee note).

**Evidence against:**

- Live probes negative **twice**: **-$63.25**, **-$104.05** despite paper optimism.
- Canary fill reality (**202k+** prints): at-touch **61–83%** by asset (**BTC 83.2%**); trade-through only **1.2–4.0%** → **adverse-selection fills** explain live losses (pack: 83% at-touch, only 3–4% trade-through).
- Prior blocks: ADR-176 (Cell C $1 maker live), ADR-139 (crypto FV archive), ADR-185/187 (lane shutdowns).

**Verdict:** **Rejected for now.** Reopen **only** via fill-conditioned replay that reproduces the live losses (gate, not promotion). ADR-193.

---

### C6 — Small the VPS provider VPS (infra, not an edge)

**Thesis:** Sample factory + honest re-test bench after Session 466 decommission of `the-vps`.

**Decision:** **APPROVE** new small the VPS provider VPS **~EUR 5–8/mo**, low CPU fine, as:

1. Recorder host  
2. Daily calibration-tape harvester (feeds C1; honest re-test for C3/C4)

Not an edge itself. Aligns with OQ-129 harvest intent and post-466 infra gap. ADR-194.

---

## 5. Consensus ranking

| Rank | ID | Role | Action now |
|---:|---|---|---|
| 1 | **C1** | PRIMARY | WANGZJ multi-month sports mid-band NO-fade replay; lock taxonomy + fee-exact P&L; **no paper yet** |
| 2 | **C2** | RUNNER-UP | Close OQ-123/124; then paper-parity restart path only |
| 3 | C4 | Filter | Hold until settlement join; never standalone |
| 4 | C3 | Autopsy | Fill-conditioned canary replay; permanent kill if ROI ≤0 on n≥200 |
| 5 | C6 | Infra | Provision ~EUR 5–8/mo VPS (recorder + harvester) |
| 6 | C5 | Rejected | Blocked behind fill-conditioned replay gate |

**Unanimous internal + Grok + Codex** per pack. Raw full companion transcripts remain unavailable (tmp cleanup); restored kill/Codex/X content applied in §7 and §2.

---

## 6. 30 / 60 / 90-day roadmap (sized to $2k)

Budget assumption: research + infra only under $2k; trading capital remains the separate **$137** funding note until the operator revises caps.

### Days 0–30 (research + infra only)

| Item | Owner | Cap / note |
|---|---|---|
| Provision C6 VPS (~EUR 5–8/mo) | the operator ops | Infra ADR-194 |
| Deploy recorder + daily sports calibration harvester | Claude/Codex | OQ-129 path |
| Lock sports taxonomy + fee function (conservative $1.25/100sh) | Research | OQ-130 fee verify via VPN |
| Run WANGZJ multi-month replay for C1 | Research | OQ-127 |
| Close OQ-123/124 accounting for C2 | Claude + the operator | Blocks any C2 restart claim |
| **No paper. No live.** | All | ADR-183 remains |

### Days 30–60

| Gate | Action if PASS | Action if FAIL |
|---|---|---|
| C1: fee-exact ROI **≥ +3%** after 1-tick adverse fill; block-bootstrap CI lower **> 0**; sign stable **ex-top-2** weeks/leagues | Start **C1 paper** lane (new ADR + the operator approval still required for any later live) | Archive C1 idea (OQ-127 FAIL) |
| OQ-123/124 clean | Restart **C2** live-probe **paper-parity** only | Keep C2 research/shadow only |
| C3 fill-conditioned autopsy on canary tape (the local workstation; no new infra) | If ROI ≤0 on n≥200 executable windows → **permanent kill** (ADR-192) | If executable edge survives → new research ADR only (still not kill-list reopen) |

### Days 60–90

| Item | Gate |
|---|---|
| C1 paper | n≥**500** closed groups; fee-adj ROI **≥ +3%**; ex-top-2 positive; **≥2** sports categories same sign |
| C4 co-sign A/B | On top of C1 once prod settlement join exists (OQ-128) |
| Any live step | **Explicit the operator approval** + ADR + **$137** current funding note |

**Explicit rule:** **No live trading without the operator approval.**

---

## 7. Per-lane kill-criteria tables

> Source: `kill_criteria_restored.md` — verbatim from the 2026-07-11 Grok 4.5 high adversarial pass, plus independent Codex gpt-5.5 additions. Original companion files lost to tmp cleanup; this section is the restored content integrated into the report.

### C1 sports mid-band NO-fade

**Evidence demanded before any paper bot:**

1. WANGZJ (or multi-month) walk-forward, fixed sports taxonomy locked **BEFORE** measuring ROI. No post-hoc regex.
2. Fee-exact PnL using live sports fee schedule on entry price; report net ROI, not hit rate.
3. Block-bootstrap by event-day with lower CI **> 0**, or pre-registered kill if CI still includes 0 after **n ≥ 2,000** independent event-days.
4. Ex-outlier / ex-top-league / ex-top-2-weeks all same sign.
5. Fill model: mid vs ask walk; edge must survive **+1c** adverse entry and **50%** depth haircut.
6. Maker-vs-taker split on the same signals — if only mid marks work and real asks fail, paper stays blocked.
7. Daily calibration harvester running **≥ 14 days** before the paper loop, so paper is out-of-sample relative to discovery tape.

| Gate | Rule |
|---|---|
| Paper gate (not live) | n ≥ **500** closed paper groups; fee-adjusted ROI **≥ +3%**; trimmed (ex-top-2) positive; same-sign in **≥ 2** sports categories |
| Kill (adversarial) | fee-exact walk-forward ROI **≤ 0**, or block-bootstrap CI includes 0 at n ≥ 2,000 event-days; sign flips after regex freeze or ex-top-2 weeks / ex-largest league; ask-walk entry destroys **≥ 100%** of edge; after 500 paper closes: fee-adj ROI **< +3%**, or ex-top-2 **≤ 0**, or one slate/day **> 50%** of PnL |
| Kill (Codex) | full replay net ROI **< +3%** after current fees and one-tick penalty; 55–75c bucket loses sign after correct sports classification; first 500 paper closes fail to beat break-even by **≥ 2pp** net of fees |
| Live (later, explicit the operator only) | 100 closed ROI **< 0**, or max DD **> 15%** of allocated bot bankroll |

### C2 weather range-fade NO

**Evidence demanded before paper re-deploy:**

1. Wallet-accounting OQs closed with three-way reconcile: CLOB fills ↔ on-chain/CTF ↔ internal ledger (OQ-123/124).
2. Ex-top-2 still positive on the **95** live groups + city-level stability table.
3. Source freshness gate instrumented: max forecast age, exact station ID match, fail-closed on fallback.
4. Depth-walk at intended size (**$5–$20**): edge after walking the NO ladder, not top-of-book.
5. Capacity honesty: if median daily deployable notional **< $50** after depth, keep as research/canary only.

| Gate | Rule |
|---|---|
| Paper gate | accounting clean + **50** new closed groups with fee-adj ROI **≥ +5%** and no single city **> 40%** of PnL |
| Kill (adversarial) | ledger vs venue still disagrees after one full resolve cycle; 50 paper closed fee-adj ROI **< +5%** or single city **> 40%** PnL; median deployable depth at target size **< $5** (demote to research permanently); any repeat of unreconciled PnL, or 50 closed live ROI **< 0** after fees |
| Kill (Codex) | accounting review turns historical ROI negative; **150** new closed groups flat/negative after fees; edge concentrates in one city/range-template |

### C3 last-minutes leader-follow (mirage test — ALL required before paper)

1. Fill-conditioned replay: at signal time walk the actual ask ladder for fixed notional (**$5/$20/$50**); entry = depth-weighted price, not mid.
2. Only count windows with live top-of-book age **< X ms** and size **≥ Y shares**; report ROI on restricted **and** full set.
3. Through-touch/cancel analysis: fill probability at ≤ signal mid+1c within **500ms/2s/5s**; if **< 20%**, dead at retail.
4. Latency budget from the real path (the VPN provider + Mac/VPS → CLOB): p50/p95 signal→ack; if p95 **>** book reaction median, we are the adverse flow.
5. Fee-exact net EV at true entry price; EV **> 0** after 1c extra slippage stress.
6. Competition test: exclude top-of-book updates **< 200ms** after CEX move; edge must survive on the remainder.
7. **Pre-registered kill:** fill-conditioned ROI **≤ 0** on **n ≥ 200** executable windows → close C3 permanently (no third revival). ADR-192.

**Layer classification:** CEX→PM information lag **REAL**; mid miscalibration **REAL** as measurement; executable edge for a $2k solo stack **NOT ESTABLISHED** — default = mirage.

| Gate | Rule |
|---|---|
| Permanent kill (adversarial) | fill-conditioned ROI ≤ 0 on n ≥ 200 executable windows |
| Kill (Codex) | fill-conditioned EV not positive after crypto fees + one-tick latency penalty; opportunity count **< 100/month** at minimum size; T-1 edge disappears when requiring executable top-of-book depth for **3** consecutive snapshots |
| Near-resolution kill-list | **Does not reopen** regardless of mid-gap size |
| Selection bias | 357/1271 windows processed; 509 skipped dead books — must be modelled; ignore mid-only gaps |

### C4 elite cheap-tail co-sign — before any use

1. Prod settlement join complete (wallet tags ↔ resolved markets, no backfill bias) — OQ-128.
2. Co-sign only: never a standalone entry signal; stack on C1 or C2.
3. Ex-top-market, ex-category, time-split all same sign for the filter **LIFT**.
4. Forward sample **n ≥ 200** co-signed trades with lift **≥ +3pp** vs base strategy alone.

| Gate | Rule |
|---|---|
| Kill (adversarial + Codex) | as filter, if it cuts sample count **> 50%** without improving net ROI **≥ +3pp** out-of-sample |
| Artifact guard | Iran-style single market drives whole tail (pack: local +63% n=74 collapses to +22.6% n=51 ex-Iran) |

### C5 maker conversion — before paper AGAIN (high bar; paper already lied)

1. Fill-conditioned replay gate mandatory: only credit fills the tape shows would occur under a queue model (at-touch fraction, cancel rate, markout 1s/5s/30s).
2. Markout **≤ 0** at 5s and 30s on would-be fills, or EV after markout still **>** rebate.
3. Live-shadow quotes (post-only, cancel, no intent to trade) measuring real queue position for **2 weeks**.
4. Same sign on maker PnL after an adverse-selection tax equal to the observed live probe loss rate.
5. No paper credit for unfilled resting orders marked to mid.

| Gate | Rule |
|---|---|
| Default | **Blocked** (ADR-193) |
| Kill / stay killed | stays killed unless fill-conditioned replay shows **positive EV AND** reproduces the two negative live probes (**-$63.25**, **-$104.05**) without handwaving |
| Live promotion | Still requires separate the operator ADR; not in this verdict |

### C6 VPS / harvester

| Gate | Rule |
|---|---|
| Kill | only if disk/ops cost exceeds research throughput for **30 days** with **zero** usable calibration rows |
| Role creep | Used for live order placement without new ADR (forbidden by this verdict / ADR-194) |
| Storage | Harvester retention must align with OQ-053 / OQ-133 |

---

## 8. Infra decision

**Approve** a **small the VPS provider VPS at ~EUR 5–8/mo** (low CPU acceptable) for:

1. Continuous / daily **recorder** replacement after Session 466 decommission.  
2. **Daily calibration-tape harvester** (sample factory for C1; re-test bench for C3/C4).

Rationale: geo-blocked UK endpoints, the bot container offline, canary tape is a finite 58G historical asset on the local workstation, and C1 cannot clear multi-month gates without a harvest flywheel (OQ-129).  

Not approved: live trading host, wallet automation, or bypass of ADR-183.

Logged as **ADR-194**.

---

## 9. Explicit live-trading ban (until the operator)

- **No live trading without the operator approval.**  
- ADR-183 live halt remains in force.  
- OQ-123/124 block trusted P&L and residual-exposure closeout.  
- Funding note for any future tiny probe: **$137** until the operator revises.  
- Report writer/executor has no authority to enable services, place orders, or touch keystore/`.env`.

---

## 10. Limitations

| Limitation | Impact |
|---|---|
| **Geo-blocked Polymarket APIs/docs** from reachable machines (UK) | Cannot verify fee primary source or refresh market APIs without VPN/VPS (OQ-130) |
| **Disputed fee rate (Codex correction applied)** | Codex: docs show sports `feeRate` **0.05 → max $1.25/100sh** (not $0.75); crypto **0.07 → $1.75**. Re-run every ROI claim with per-market fee metadata. Geo-blocked from re-verifying primary page (OQ-130). All sports ROI stress uses **$1.25** |
| **the bot container offline** | No host dry-run, no WANGZJ SSH this session; C1 multi-month replay and OQ-123 host steps deferred |
| **Canary calibration selection bias** | 357/1271 windows processed; **509 skipped dead books** — mid-gap stats are conditional on live books |
| **Companion files lost to tmp cleanup** | Original `candidates.md`, `grok_adversarial.md`, `codex_ranking.md`, `grok_x_insight.md` were lost. Kill-criteria, Codex fee correction, and X-insight one-liner were **restored verbatim** from the director's session transcript into `kill_criteria_restored.md` and integrated here. **Only the raw full transcripts remain unavailable.** |
| **ADR number pack note** | Director said "next ADR 188"; file already has ADR-188..190 → this session uses **ADR-191..194** |
| **Gemini CLI broken** | Antigravity migration required (OQ-132); consensus incomplete for that model |
| **Canary.db ~57–58G on the local workstation** | No retention/rollover policy yet (OQ-133; ties OQ-053) |
| **One-week sports tape risk** | Local +5.32% / +9.22% class results can be calendar artifacts until WANGZJ multi-month clears |
| **X-insight ceiling** | At $2k, realistic public-edge ceiling is a few hundred dollars/year; hyped HFT/arb/copy lanes are dead for this stack |

---

## 11. ADRs and OQs emitted this session

| ID | Title |
|---|---|
| ADR-191 | Full reassessment 2026-07 verdict: C1 primary, C2 runner-up |
| ADR-192 | C3 stale-quote-mirage presumption + pre-registered permanent kill |
| ADR-193 | C5 maker reopen blocked behind fill-conditioned replay gate |
| ADR-194 | Approve small the VPS provider VPS (~EUR 5–8/mo) for recorder + harvester |
| OQ-130 | Fee-rate primary-source verification via VPN |
| OQ-131 | C3 fill-conditioned autopsy ownership |
| OQ-132 | Gemini CLI broken (Antigravity migration) |
| OQ-133 | canary.db ~57–58G retention policy on the local workstation |

---

## 12. Source inventory

| Source | Status |
|---|---|
| `scratchpad/evidence-pack.md` | Read; canonical numbers |
| `scratchpad/kill_criteria_restored.md` | Restored adversarial kill criteria + Codex additions + X-insight one-liner (verbatim from director transcript) |
| `scratchpad/candidates.md` | Lost to tmp cleanup; raw transcript unavailable |
| `scratchpad/grok_adversarial.md` | Lost to tmp cleanup; kill content restored via `kill_criteria_restored.md` |
| `scratchpad/codex_ranking.md` | Lost to tmp cleanup; fee correction + kill additions restored |
| `scratchpad/grok_x_insight.md` | Lost to tmp cleanup; one-liner restored |
| `docs/reports/strategy-ranking-and-data-roadmap-2026-05-09.md` | Used for historical ranking / dead-lane summary |
| `docs/reports/creative-edge-mining-2026-06-09.md` | Used for C1/C4 prior numbers |
| ADR-033 / 139 / 176 / 181 / 183 / 185 / 187 / 191..194 | Cited |

---

**End of report.** Session 468 write-up only. No live trading.

