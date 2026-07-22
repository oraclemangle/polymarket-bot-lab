# Polymarket ToS Eligibility Research — UK / CLOB-API Bot

**Author:** research agent
**Date:** 2026-04-14
**Scope:** Whether a UK-resident operator of an automated trading bot against `clob.polymarket.com` is eligible under Polymarket's current Terms of Service, and under what conditions.
**Non-goal:** This is *not* legal advice. No conclusion is offered on whether any particular conduct is "safe" or "legal". Clauses are reported as written; ambiguities are flagged for a solicitor to resolve.

---

## 0. Executive summary (flagged findings)

1. **UK is explicitly named as a fully-blocked jurisdiction.** The Polymarket Help Center's "Geographic Restrictions" article (last updated **2026-02-23**) lists "GB | United Kingdom" in the blocked countries table, alongside the US, Germany, France, Singapore, Australia, and OFAC-sanctioned states. The docs site's geoblocking page says: *"Orders submitted from blocked regions will be rejected."*
2. **The canonical ToS at `https://polymarket.com/tos` does not render a ToS body.** As of the fetch on 2026-04-14, the page returns a Next.js shell with page chrome (nav, footer, category links) and **no ToS clauses**. The previously-rendered text appears to have been removed from the public SPA build sometime after 2025-03-28 (the last Wayback capture with a material payload). **A lawyer should obtain the current operative text directly from Polymarket / QSS Inc.** before relying on it. See §1 and §6.
3. **There is no separate, publicly-linked API / Developer Terms document.** The `docs.polymarket.com` site, the CLOB introduction, and the authentication page contain **no eligibility, KYC, or jurisdiction language**. The ToS at `polymarket.com/tos` is the only legal instrument referenced, and the geoblock applies to "orders" universally — not differentiated between web UI and API. See §4.
4. **The front-end click-through wording is the clearest extant primary source.** The public site footer and order-entry attestation require users to confirm they are *"not a U.S. person, are not located in the U.S. and are not the resident of or located in a restricted jurisdiction."* This is the only verbatim eligibility language currently reachable without authentication. See §2.
5. **Corporate structure matters.** The international platform is operated by **Adventure One QSS Inc.** (footer: "© 2026"). The US platform is a separate entity (QCX LLC d/b/a Polymarket US, CFTC-regulated DCM). UK users are, per the published country list, blocked from *both* front-ends; Polymarket US is currently waitlist-only (`polymarket.us` returns an early-access landing page, no ToS).
6. **Ambiguity a lawyer must resolve:** (a) the operative ToS text itself is not publicly rendered, so "clauses as written" cannot be fully quoted from the primary source; (b) whether direct, non-browser CLOB API use (which bypasses the front-end click-through and the browser geoblock) constitutes acceptance of the ToS is **not addressed in any public document located** — it is a material open question for UK bot operators.

---

## 1. URL + date of last ToS update

| Document | URL | Status as of 2026-04-14 | Last-updated date |
|---|---|---|---|
| Terms of Use (international) | `https://polymarket.com/tos` | Page loads; **body is empty** (SPA renders only chrome) | Not displayed on page |
| Privacy Policy | `https://polymarket.com/privacy` | Page loads; body empty in SSR/client fetch | Not displayed |
| Risk Disclosure | `https://polymarket.com/risk` / `/risks` | 404 | — |
| Market Integrity | `https://polymarket.com/market-integrity` | Loads; body empty in SSR | Not displayed |
| Help Center — Geographic Restrictions | `https://help.polymarket.com/en/articles/13364163-geographic-restrictions` | Loads with full text | **Updated 2026-02-23** ("over 2 months ago" as of 2026-04-14) |
| Docs — Geographic Restrictions (FAQ) | `https://docs.polymarket.com/polymarket-learn/FAQ/geoblocking` | Loads with full text | Not dated on page |
| Polymarket US ToS | `https://polymarket.us/terms-of-service` | Returns the waitlist landing page; no ToS published yet | N/A |

**Flag:** The absence of the rendered ToS text on the canonical URL is itself a material finding. Two possibilities a lawyer should run down: (a) the text is behind a client-side fetch gated by geo/authentication that the research tooling here cannot trigger; (b) the ToS page is genuinely empty pending a rewrite in light of the December-2025 US re-opening and the April-2026 FCA cryptoasset-regime finalisation. Neither was confirmable from the public web.

---

## 2. Eligibility / geographic restrictions — verbatim extracts

### 2.1 Front-end attestation (verbatim, from rendered site chrome)

From the Polymarket site footer / pre-order modal (captured via `r.jina.ai` reader, 2026-04-14):

> "…users must attest they are **not a U.S. person, are not located in the U.S. and are not the resident of or located in a restricted jurisdiction**."

> "Polymarket operates globally through separate legal entities. Polymarket US is operated by QCX LLC d/b/a Polymarket US, a CFTC-regulated Designated Contract Market. **This international platform is not regulated by the CFTC and operates independently.** Trading involves substantial risk of loss."

### 2.2 Help Center — Geographic Restrictions (verbatim excerpt of list, fair-use short-extract)

Article: *"Geographic Restrictions | Polymarket Help Center"*, last updated 2026-02-23.

Rationale stated: *"International sanctions and embargoes, local financial regulations, gambling and prediction market laws, AML requirements, and KYC regulations."*

Full blocked list (33 countries + sub-national regions), reproduced because it operates as the de-facto "Prohibited Jurisdictions" definition pending recovery of the formal ToS text:

> Australia · Belgium · Belarus · Burundi · Central African Republic · Congo (Kinshasa) · Cuba · Germany · Ethiopia · France · **United Kingdom** · Iran · Iraq · Italy · North Korea · Lebanon · Libya · Myanmar · Nicaragua · Poland · Russia · Singapore · Somalia · South Sudan · Sudan · Syria · Thailand · Taiwan · United States Minor Outlying Islands · United States · Venezuela · Yemen · Zimbabwe.
>
> Sub-national: **Ontario (Canada); Crimea, Donetsk, Luhansk (Ukraine).**
>
> The docs FAQ variant additionally lists **Netherlands** as Blocked, and puts **Poland, Singapore, Thailand, Taiwan** in a "Close-Only" bucket (can exit existing positions, cannot open new ones).

### 2.3 Docs FAQ — order-level enforcement (verbatim, fair-use)

From `docs.polymarket.com/polymarket-learn/FAQ/geoblocking`:

> *"Orders submitted from blocked regions will be rejected."*

No carve-out is stated for the method of submission (web UI vs API).

### 2.4 "Restricted Persons" / "Prohibited Jurisdictions" — formal definitions

**Not recoverable from the public-rendered ToS** (see §1 flag). Secondary sources (third-party legal explainers, news articles) reference a **Section 2.1.4** of Polymarket's ToS that prohibits circumventing geographic restrictions (VPN ban). The research here could not independently verify that section numbering against the primary source; cited only as lead for a lawyer to pull the authoritative text.

---

## 3. UK-specific language

- **Explicit naming:** Yes. The Help Center's country list (2026-02-23 update) contains `GB | United Kingdom` in the "Blocked" column.
- **By reference (FCA / UKGC):** The Help Center cites *"local financial regulations, gambling and prediction market laws"* as generic bases; it does **not** name the FCA or UK Gambling Commission. The UKGC is the operative UK regulator most commentators cite (prediction-market contracts arguably constitute unlicensed betting under the Gambling Act 2005); the FCA's 2019 binary-options retail ban is the other commonly-cited theory. Neither is named in Polymarket's own published materials located here.
- **Sanctions lists:** The UK is **not** on any OFAC/EU/UK sanctions list; the UK block is a voluntary business-level restriction, not a sanctions-compliance one. The rationale is therefore "local financial regulations / gambling laws" — consistent with the UKGC licence gap.
- **Silence elsewhere:** The Privacy Policy does not render enough text to confirm UK-GDPR handling. `polymarket.us/tos` is not yet published. No separate UK-facing terms exist.

---

## 4. API / automated-trading clauses

### 4.1 Is there a separate API / Developer Terms document?

**No, not publicly located.** The following were checked:

- `https://docs.polymarket.com` — no Legal/Terms section in the index or `llms.txt`.
- `https://docs.polymarket.com/api-reference/introduction` — no eligibility language.
- `https://docs.polymarket.com/developers/CLOB/introduction` — technical only; no terms, KYC, or jurisdiction clauses.
- `https://docs.polymarket.com/developers/CLOB/authentication` — technical only.
- Probed `/legal/terms`, `/legal/tos`, `/user-agreement` on `polymarket.com` — all 404.

The GitHub SDKs (`py-clob-client`, `rs-clob-client`) ship under permissive software licences but carry no end-user terms.

### 4.2 Does the ToS distinguish web UI vs API (`clob.polymarket.com`)?

**Silent.** Nothing located in any public document carves out a different rule for direct API use. The Help Center and docs FAQ describe the restriction at the *order* level: orders from blocked regions are rejected. Enforcement mechanisms mentioned are IP-based (front-end and order-submission endpoints).

### 4.3 Are bots / algorithmic trading explicitly permitted, prohibited, or silent?

- **Explicit permission:** Not found. No clause says "bots are permitted."
- **Explicit prohibition:** Not found in the materials accessible. (The VPN/circumvention clause — reported by third parties as ToS §2.1.4 — prohibits bypassing *geographic* restrictions, not automation per se.)
- **Implicit signal:** Polymarket publishes official CLOB client SDKs (TypeScript, Python, Rust), documents batch order submission up to 15 orders/call, Ed25519 authentication, and WebSocket streaming. The product surface is clearly designed for programmatic use. The Builder Program and public Rewards programme presuppose automated market-making.
- **Flag:** The combination "API is clearly designed for bots + UK is explicitly blocked + no API-specific terms" means a UK operator must rely on inferences from a general ToS whose text is not publicly rendered. **A lawyer needs the authoritative ToS text to confirm (a) whether mere API call-and-response constitutes acceptance of the ToS, (b) whether the geographic restriction applies at account level, IP level, or residency level, and (c) whether "location" is read against the calling server's IP or the operator's residency.**

---

## 5. KYC triggers

Polymarket's public documents located here do **not** enumerate a deposit or withdrawal dollar threshold triggering KYC on the international platform. Observable facts:

- The Help Center article cites *"AML requirements, and KYC regulations"* as one of the general rationales for geoblocking — implying KYC is a jurisdictional compliance layer, not a per-transaction threshold.
- The international platform (Adventure One QSS Inc.) has historically operated without broad KYC on deposits/withdrawals (funds move via on-chain USDC on Polygon and a fun.xyz Bridge API); front-end account creation asks only for a wallet connection and the geographic attestation quoted in §2.1.
- **Polymarket US (QCX LLC)** as a CFTC-regulated DCM will require full KYC at onboarding, but that platform is US-only and currently waitlist-only; not relevant to a UK operator.
- **API-specific KYC:** Nothing located. L1 (EIP-712 signature) and L2 (HMAC API credentials) authentication are purely cryptographic; no identity check is part of credential issuance per the docs.

**Flag for counsel:** The absence of explicit KYC thresholds on the international platform does **not** mean none exist — the current ToS text (not publicly rendered) may impose identity-verification powers at Polymarket's discretion, particularly if an account is flagged for high-volume or suspected-restricted-jurisdiction activity. This needs to be read from the authoritative ToS.

---

## 6. Archive.org diff

**Direct retrieval of archive snapshots was blocked by the research tooling** (WebFetch cannot reach `web.archive.org`; Bash `curl` of Wayback HTML succeeded but the snapshots themselves are Next.js SPA shells that do not contain the ToS body in the captured HTML — the text was client-rendered and never serialised into the snapshot).

Available snapshot metadata (from the Wayback CDX index):

| Period | Snapshots captured (200-status) | Rendered-body size | Notes |
|---|---|---|---|
| 2023-02 → 2025-03 | Dozens of captures, ~8–13 KB each | All SPA shells; no ToS text serialised | Cannot diff clause-level |
| 2025-04 → 2026-04 | **None captured with status 200 by Wayback** | N/A | The page stopped being meaningfully archived ~end of March 2025 |

**Material change flag:** The gap in the archive record from April 2025 onward coincides with (a) the Polymarket build-ID change visible in the HTML (`dpl_EeuimUHWnCqdUa4Sj1rbfj4Z1tNV`) and (b) the CFTC approval of Polymarket US in December 2025. It is plausible the ToS was substantively rewritten at least once in that window. **A 12-month and 6-month diff cannot be produced from the public archive** because the text is not in the snapshots. A lawyer should request prior versions directly from Polymarket, or obtain them via discovery if a dispute arises.

---

## 7. Separate API ToS — summary

**None located.** `clob.polymarket.com` does not publish its own terms. `docs.polymarket.com` contains no legal section. The ToS that governs API use (to the extent any does) is — by default and by silence — the same `polymarket.com/tos` document that governs web users.

Open question for counsel: *whether* that document's acceptance mechanism (click-through on the web front-end) reaches a user who never touches the web front-end and submits orders only via signed API calls. That is a formation-of-contract question, not a jurisdiction question, and it is not answered by anything Polymarket publishes.

---

## 8. Consolidated source list

**Primary (Polymarket-owned):**
- `https://polymarket.com/tos` — canonical ToS URL; **body empty on render** as of 2026-04-14.
- `https://polymarket.com/privacy` — canonical Privacy URL; body empty on render.
- `https://polymarket.com/market-integrity` — body empty on render.
- `https://help.polymarket.com/en/articles/13364163-geographic-restrictions` — geographic restrictions article, updated 2026-02-23.
- `https://docs.polymarket.com/polymarket-learn/FAQ/geoblocking` — docs geoblocking FAQ.
- `https://docs.polymarket.com/api-reference/introduction` — CLOB API intro (no legal content).
- `https://docs.polymarket.com/developers/CLOB/authentication` — auth docs (no legal content).
- `https://polymarket.us/terms-of-service` — waitlist page; no ToS published.

**Secondary / contextual (third-party summaries; reference only, not primary-source-verified):**
- Datawallet — *"Polymarket Supported and Restricted Countries (2026)."*
- Trade the Outcome — *"How to use Polymarket in UK? [2026 Updated]."*
- HolyPoly — *"Is Polymarket Legal? Where Is Polymarket Available in 2026?"*
- Homes Found / PredictBlog — *"The UK Paradox: Navigating Polymarket in a Regulated Landscape (2026 Guide)."*
- Cryptonews — *"Is Polymarket Legal in the U.S. and Europe? April 2026 Guide."*
- CoinDesk (2024-11-14) — *"Polymarket's Probe Highlights Challenges of Blocking U.S. Users (and Their VPNs)."*
- Wikipedia — *"Polymarket"* (2022 CFTC settlement, US block 2022→Dec 2025, July 2025 end of federal investigations).

**Archive:**
- `https://web.archive.org/web/*/polymarket.com/tos` — CDX index shows 200-status captures 2023-02 through 2025-03-28; no captures with rendered ToS body; no captures since March 2025.

---

## 9. What a solicitor still needs to obtain

1. **The authoritative current ToS text.** Request from Polymarket legal (Adventure One QSS Inc.) or inspect the client-rendered DOM on a browser session from a permitted jurisdiction. The SPA-only rendering blocks ordinary desk research.
2. **The operative definition of "Restricted Persons" / "Prohibited Jurisdictions"** as written, with section numbering. Third-party references to "§2.1.4" circumvention are unverified against primary source here.
3. **Prior versions** of the ToS from the past 12 months — not reconstructable from Wayback because of the SPA shell problem.
4. **Whether API-only use constitutes ToS acceptance** — confirm the contract-formation mechanism for direct CLOB users who never load the web front-end.
5. **Any separate API / Developer Agreement** — confirm directly with Polymarket that none exists (current public evidence suggests none, but absence of publication is not absence of existence).
6. **KYC discretionary powers** — the clause(s) permitting Polymarket to request identity verification on international-platform accounts, and any published dollar thresholds.
7. **UK-specific basis** — whether the UK block is premised on UKGC (gambling) or FCA (binary options / cryptoasset regime) reasoning, as this affects which UK regulator a UK-based operator would be exposed to.

---

*End of report.*
