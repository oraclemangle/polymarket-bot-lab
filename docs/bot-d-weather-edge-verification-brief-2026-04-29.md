# Bot D Weather Edge Verification Brief

**Date:** 2026-04-29
**Audience:** Grok / external verifier
**Scope:** Read-only research brief for improving Bot D profitability on Polymarket daily temperature markets.
**Status:** Hypothesis and implementation roadmap, not a live-trading approval.

## 2026-04-29 Implementation Addendum

After external verification, the P0/P1 foundations from this brief were
implemented in Session 47:

- `SettlementSpec` station/source/rounding metadata added.
- NYC now anchors to `KLGA`; Dallas now anchors to `KDAL`.
- Verified airport-station markets no longer receive urban-core UHI uplift.
- Open-Meteo pulls now use settlement-station coordinates where configured.
- AviationWeather METAR/SPECI records feed latest observation and same-day
  max-so-far/min-so-far constraints.
- Raw ensemble member highs/lows are retained.
- Empirical member-count bucket probability is computed beside the existing
  fitted CDF probability.
- CDF-vs-empirical disagreement skips trades when the model shape is not
  supported by raw ensemble members.

This remains paper-safe infrastructure, not a live-trading approval. The
remaining research thread is OQ-058: finish the all-city settlement-source
audit and evaluate NBM percentiles in shadow mode.

## One-Sentence Thesis

Bot D's likely edge is not in copying public weather bots; it is in making the existing Bot D stack settlement-exact: correct airport/station anchors, explicit settlement rounding, empirical ensemble probabilities, same-day max-so-far constraints, and calibrated per-city error tracking.

## Backdrop

This repo runs a fleet of Polymarket bots. Bot D is the weather-temperature bot and is the current leading candidate for eventual live graduation, but it remains gated by paper evidence, monitoring, and explicit operator approval.

The V2/pUSD migration is complete and the trading infrastructure is technically ready, but readiness to place orders is not the same thing as having a profitable signal. The operator asked for a deeper search for what could make Bot D profitable, specifically by examining open-source weather/prediction-market projects and extracting anything that could improve our bot.

The context that matters: Polymarket weather contracts often resolve on narrow temperature buckets. A 1-2 F bucket leaves almost no room for sloppy assumptions. If the model forecasts city center while settlement is an airport station, or if the model treats a rounded settlement bucket as a continuous interval, a good-looking edge can become a structurally losing trade.

## Local Bot D Baseline

Bot D is already more sophisticated than most public bot code reviewed.

Local files reviewed:

- `bots/bot_d_weather/config.py`
- `bots/bot_d_weather/weather_fetcher.py`
- `bots/bot_d_weather/strategy.py`
- `bots/bot_d_weather/discovery.py`
- `bots/bot_d_weather/executor.py`

Current useful features:

- Open-Meteo ensemble forecast path using GFS + ECMWF members.
- NWS gridpoint second-opinion filter for US cities.
- METAR observation adjustment for same-day high markets.
- Seasonal RMSE multiplier.
- Skew-normal / Gaussian bucket probability model.
- Fee-aware net edge.
- One-bet-per-event filter.
- Wave-regime sizing.
- Kelly-style position sizing and fleet exposure caps.
- Edge-collapse exits.

The current likely weak points are not missing execution features. They are weather/settlement modeling details.

## Local Evidence To Challenge

### 1. City Coordinates Are City Center, Not Settlement Station

In `bots/bot_d_weather/config.py`, city configs use city-center coordinates. Examples:

- NYC uses `40.7128, -74.0060`.
- Chicago uses `41.8781, -87.6298`.
- Dallas uses `32.7767, -96.7970`.
- Atlanta uses `33.7490, -84.3880`.
- Miami uses `25.7617, -80.1918`.

These are reasonable city coordinates, but they are not necessarily the station or airport coordinates used for settlement.

### 2. Dallas METAR Station Is Currently DFW

In `bots/bot_d_weather/weather_fetcher.py`, `CITY_ICAO` maps:

- NYC -> `KLGA`
- Chicago -> `KORD`
- Dallas -> `KDFW`
- Atlanta -> `KATL`
- Miami -> `KMIA`

The Dallas mapping is a red flag because one reviewed weather bot claims Dallas Polymarket weather markets resolve on Love Field (`KDAL`), not DFW (`KDFW`). If true, this is a direct edge leak.

### 3. Probability Is Model-Fitted, Not Empirical Member Count

In `bots/bot_d_weather/strategy.py`, Bot D:

1. Chooses mean/std for high or low.
2. Combines ensemble spread with seasonal RMSE.
3. Computes bucket probability via `_range_probability_with_shape(...)`.

This is elegant and smooth, but it compresses the raw ensemble member distribution into mean/std before calculating probability. If the ensemble is skewed or multimodal, a fitted curve can produce a confident probability that the member distribution itself does not support.

### 4. Same-Day METAR Is A Mean Adjustment, Not A Full Settlement Constraint

Bot D only uses fresh METAR to raise same-day high mean when the observed airport temperature exceeds the forecast mean. It does not yet appear to use full intraday `max_so_far` as a hard lower bound on daily high settlement buckets.

For daily high markets, once observed max-so-far crosses a bucket boundary, some buckets become impossible. That should be represented as a probability constraint, not just a mean shift.

## External Repositories Reviewed

### A. alteregoeth-ai/weatherbot

Repository:
https://github.com/alteregoeth-ai/weatherbot

Why it matters:

This is not as sophisticated as Bot D overall, but it makes one crucial claim: Polymarket weather markets resolve on specific airport stations, and most bots lose edge by using city-center coordinates.

Evidence from README:

- It says city-center coordinates are wrong for these markets.
- It says NYC resolves on LaGuardia (`KLGA`).
- It says Dallas resolves on Love Field (`KDAL`), not DFW.
- It claims city-center vs airport differences can be 3-8 F.
- It lists station anchors for NYC, Chicago, Miami, Dallas, Seattle, Atlanta, London, Tokyo, and others.

Useful code idea:

Use a `SettlementSpec` registry that separates display city from settlement station, forecast coordinate, observation station, unit, and rounding method.

Do not copy:

- Its simple bucket probability logic. Bot D's existing probability model is stronger.
- Its execution code.

### B. suislanchez/polymarket-kalshi-weather-bot

Repository:
https://github.com/suislanchez/polymarket-kalshi-weather-bot

Why it matters:

This repo is useful because it preserves raw ensemble member highs/lows and computes probability as the fraction of ensemble members above/below a threshold.

Relevant files:

- `backend/data/weather.py`
- `backend/core/weather_signals.py`
- `VALIDATED_RESEARCH.md`
- `backend/data/kalshi_markets.py`

Useful ideas:

- Keep `member_highs` and `member_lows`, not only mean/std.
- Compute empirical ensemble probability directly.
- Track Brier score after settlement.
- Use Kalshi KXHIGH markets as a read-only comparator where definitions are comparable.

Important caution:

The repo's weather code only handles threshold-style probabilities cleanly. Polymarket range buckets need exact bucket/range parsing and settlement rounding. Bot D already has stronger market discovery/execution than this repo.

### C. yangyuan-zhen/PolyWeather

Repository:
https://github.com/yangyuan-zhen/PolyWeather

Why it matters:

This is the most sophisticated public weather-intelligence stack reviewed. It is not a drop-in bot, but it has production-grade concepts around settlement sources, rounding, max-so-far, peak windows, bucket distributions, and calibration.

Relevant files inspected locally after cloning:

- `src/analysis/settlement_rounding.py`
- `src/analysis/probability_calibration.py`
- `src/analysis/trend_engine.py`
- `src/data_collection/weather_sources.py`
- `src/data_collection/city_registry.py`
- `src/models/lgbm_features.py`
- `src/models/lgbm_daily_high.py`

Useful ideas:

- Dedicated settlement rounding layer.
- Per-city settlement source metadata.
- Intraday max-so-far and peak-window logic.
- Probability bucket distribution constrained by observed max-so-far.
- City station clusters, e.g. NYC around `KLGA/KJFK/KEWR/KTEB/KHPN`, Dallas around `KDAL/KDFW/KADS/KGKY`.
- Shadow evaluation gates for ML models rather than promoting them because they sound advanced.

Do not copy blindly:

- LGBM/EMOS primary path. Their own docs indicate these need validation gates and can degrade bucket performance.
- Dashboard/product code.
- Any hardcoded tokens or operational secrets if present in the public repo.

## External Docs / Data Sources Checked

### Open-Meteo Ensemble API

Docs:
https://open-meteo.com/en/docs/ensemble-api

Relevant facts:

- Supports individual ensemble member forecasts.
- Supports GFS ensemble with 31 members.
- Supports ECMWF IFS ensemble with 51 members.
- Supports daily maximum/minimum temperature variables as well as hourly variables.

Implication:

Bot D should retain raw daily high/low member values and compute empirical probabilities directly. It can still keep the fitted CDF model as a second opinion.

### NOAA National Blend of Models

AWS registry:
https://registry.opendata.aws/noaa-nbm/

Relevant facts:

- NOAA NBM is a calibrated blend of NWS and non-NWS model guidance.
- Data updates hourly.
- Data is available in public S3 buckets without an AWS account.
- GRIB2 bucket: `s3://noaa-nbm-grib2-pds/`.

Implication:

For US city temperature markets, NBM percentiles should be evaluated as a shadow input. It may be a better near-term probabilistic source than using deterministic NWS gridpoint forecasts only as a veto.

### Aviation Weather API

Docs:
https://aviationweather.gov/data/api

Relevant facts:

- Provides METAR terminal observations.
- Provides TAF forecasts.
- Supports JSON/GeoJSON/XML/CSV formats.
- Current METAR cache updates frequently.

Implication:

Bot D can get richer same-day station observations and TAF context, especially for airport-settled markets.

## Ranked Edge Hypotheses

### P0: Settlement Station Audit And Registry

Build a new explicit station registry:

```python
@dataclass(frozen=True)
class SettlementSpec:
    city: str
    settlement_station: str
    forecast_lat: float
    forecast_lon: float
    obs_station: str
    timezone: str
    unit: str
    rounding: Literal["wu_nearest_int", "floor", "exact"]
    aliases: tuple[str, ...]
```

Then audit every active Bot D city against actual Polymarket market rules.

Initial suspect corrections:

- NYC forecast coordinate should likely be near `KLGA`, not Manhattan city center.
- Dallas should likely be `KDAL`, not `KDFW`, if WeatherBot's claim matches actual Polymarket rules.
- International markets should not assume US METAR-style rounding or station sources.

Why this is P0:

A 2 F station error on a 1-2 F bucket is not noise. It turns the model into a confident bettor on the wrong event.

What Grok should verify:

1. For each active Polymarket daily temperature city, what source/station does the market resolution text specify?
2. Does Dallas resolve using `KDAL`, `KDFW`, Wunderground, NWS, or another source?
3. Does NYC resolve on `KLGA`, Central Park, Wunderground city page, or another source?
4. Are temperatures rounded, floored, truncated, or settled exactly?

### P0: Empirical Ensemble Probability Gate

Enhance `ForecastResult` to include:

```python
member_highs_f: tuple[float, ...]
member_lows_f: tuple[float, ...]
```

Then compute:

```python
empirical_prob = count_members_in_bucket(member_values, bucket_low, bucket_high, rounding_mode) / len(member_values)
```

Compare this to the existing fitted CDF probability:

```python
if abs(empirical_prob - cdf_prob) > 0.10:
    skip_or_downsize("ensemble_shape_disagreement")
```

Why this is P0:

The current mean/std approach can overstate confidence around discontinuous settlement buckets. Empirical member counts reveal whether the ensemble itself actually supports the trade.

What Grok should verify:

1. Does Open-Meteo return daily `temperature_2m_max` / `temperature_2m_min` per member for both GFS and ECMWF in the format needed?
2. Is member-count probability materially better calibrated for range buckets than Gaussian/skew-normal CDF?
3. What disagreement threshold should be used: 5pp, 10pp, or horizon-dependent?

### P1: Same-Day Max-So-Far / Dead-Bucket Engine

For same-day high markets, fetch all station observations since local midnight and compute:

```python
max_so_far = max(observed_station_temps)
settled_floor = apply_settlement_rounding(max_so_far)
```

Then constrain bucket probabilities:

- Buckets below the observed settlement floor are zero.
- If after peak window and temperature is falling, further upside probability shrinks.
- If current temp is still within 0.5 F of max-so-far inside peak window, upside remains open.

Why this is P1:

Same-day markets often become mechanically resolvable before market prices fully adjust. This is likely one of the cleanest practical edges if implemented carefully.

What Grok should verify:

1. Which observation API gives the most complete intraday station history for each settlement station?
2. Does AviationWeather METAR history have enough observations for max-so-far?
3. Are there missing special observations (`SPECI`) that matter during fast intraday changes?
4. How should max-so-far be handled for low-temperature markets?

### P1: NBM Percentiles For US Markets

Evaluate NOAA NBM percentiles as a shadow forecast source for US daily high/low markets.

Target fields:

- MaxT percentiles.
- MinT percentiles.
- 10th, 25th, 50th, 75th, 90th percentile values.

Use them to build a distribution:

```python
nbm_prob = interpolate_percentile_distribution(bucket_low, bucket_high)
```

Why this is P1:

NWS gridpoint forecasts are deterministic. NBM percentiles are specifically calibrated probabilistic guidance and update hourly. This could improve short-horizon probability estimates.

Implementation caution:

NBM GRIB2 parsing adds operational complexity. This should run shadow-only until it proves lower Brier / log loss than current Bot D.

What Grok should verify:

1. Best no-key access path for point extracting NBM MaxT/MinT percentiles.
2. Whether COG or GRIB2 is easier for our Python stack.
3. Whether Open-Meteo already exposes enough NBM-like blended probabilistic data to avoid GRIB2.
4. Whether NBM percentiles are station-specific enough for airport-settled markets.

### P1: Settlement Rounding Layer

Create one canonical function:

```python
def apply_settlement_value(city: str, raw_temp: float) -> int | float:
    ...
```

Candidate modes:

- `wu_nearest_int`: positive temps use `floor(x + 0.5)`, negative use `ceil(x - 0.5)`.
- `floor`: useful for specific exact-source markets if rules say so.
- `exact`: no rounding, if market uses exact decimal source.

Then evaluate bucket probabilities over settlement values, not continuous raw forecast values.

Why this is P1:

Rounding can flip boundary buckets. A raw 72.49 F and 72.51 F are different only if the settlement rules say they are.

What Grok should verify:

1. Polymarket daily city temperature rounding rules by source.
2. Whether Wunderground-style nearest integer is actually used for current daily high markets.
3. Whether international city markets use Celsius and different rounding conventions.

### P1: Calibration And Brier Tracking By City / Source / Horizon

Persist every forecast decision:

```text
city
date
temp_type
bucket_low
bucket_high
market_yes_price
cdf_prob
empirical_prob
nbm_prob
nws_value
metar_max_so_far
source_set
horizon_hours
decision
final_settlement_value
resolved_yes
```

Compute:

- Brier score by city.
- Brier score by horizon bucket.
- Error by forecast source.
- Calibration bins: predicted 60-70%, 70-80%, etc.
- Market-vs-model delta after settlement.

Why this is P1:

Bot D cannot know it has edge from a handful of wins. The edge needs to survive ex-outlier and by-bin calibration checks.

What Grok should verify:

1. Minimum sample size before live sizing is justified.
2. Whether Brier or log loss is the better promotion gate.
3. How to account for correlated bucket markets from the same event.

### P2: Kalshi Read-Only Comparator

Use Kalshi KXHIGH markets as a read-only reference for overlapping cities.

Important:

This is not an arbitrage or cross-venue trading proposal. It is a sanity check and feature source.

Potential use:

```python
if polymarket_model_edge > threshold and kalshi_implied_prob agrees:
    confidence += small_boost
elif polymarket_edge is large but kalshi disagrees strongly:
    skip_or_downsize("cross_venue_disagreement")
```

Why this is P2:

Weather markets can be efficient. If another venue disagrees hard with our model, it is a signal to re-check settlement definitions, price mapping, and model assumptions.

What Grok should verify:

1. Which Kalshi contracts match Polymarket markets closely enough.
2. Which ones differ by station/source and should not be compared.
3. Whether Kalshi prices are liquid enough to be meaningful.

### P2: Dynamic Station-Cluster Adjustment

Instead of static urban heat island offsets, fetch nearby station cluster readings.

Example clusters from PolyWeather:

- NYC: `KLGA`, `KJFK`, `KEWR`, `KTEB`, `KHPN`
- Dallas: `KDAL`, `KDFW`, `KADS`, `KGKY`

Use cluster deltas to understand whether the settlement station is running hot/cold relative to nearby stations.

Why this is P2:

This helps same-day markets and airport-specific microclimates. It is more defensible than static UHI offsets.

What Grok should verify:

1. Whether cluster deltas improve settlement-station forecasts or just add noise.
2. How often nearby stations update relative to the primary station.
3. Whether airport geography creates stable bias patterns by wind direction.

### P3: LGBM / EMOS / ML Layer

Do not promote ML as a live signal yet.

Reason:

PolyWeather has LGBM/EMOS infrastructure, but its docs emphasize shadow evaluation and gating. That is the correct posture. Without sufficient resolved truth data, ML can overfit bucket noise and degrade live decisions.

Acceptable near-term use:

- Shadow-only model.
- Compare MAE, Brier, and log loss against current Bot D.
- Promote only if it beats the baseline over enough resolved events and does not rely on leaked settlement information.

What Grok should verify:

1. Minimum data needed for LGBM by city/horizon.
2. Whether cross-city pooling helps or hurts.
3. Whether historical weather truth can be reconstructed without settlement-source mismatch.

## Proposed Bot D Implementation Order

### Phase 1: No New Trading Logic, Fix Truth Layer

1. Add `SettlementSpec`.
2. Move active cities from city-center coordinates to verified settlement station coordinates.
3. Add settlement rounding function.
4. Add tests for NYC, Dallas, Chicago, Miami, Atlanta.
5. Add a script that prints active Polymarket weather markets with parsed city/date/range/source assumptions.

Acceptance criteria:

- Every active city has an explicit station/source/rounding rule.
- Dallas station mismatch is resolved by source evidence.
- Existing Bot D tests pass.

### Phase 2: Shadow Probabilities

1. Store raw ensemble member highs/lows in `ForecastResult`.
2. Compute empirical bucket probability beside current CDF probability.
3. Log both probabilities for every discovered market.
4. Add disagreement gate in paper only.

Acceptance criteria:

- No live behavior change.
- Paper decisions can be compared under old vs new probability logic.
- Reports show where current model and empirical model disagree.

### Phase 3: Same-Day Settlement Engine

1. Fetch station observations since local midnight.
2. Compute `max_so_far` / `min_so_far`.
3. Apply settlement rounding.
4. Zero impossible buckets.
5. Add peak-window status and cooling/rising state.

Acceptance criteria:

- Same-day high buckets below observed max-so-far become impossible.
- Tests cover boundary rounding.
- No paper/live order path can buy an impossible bucket.

### Phase 4: Calibration Store

1. Persist forecast snapshots and resolved outcomes.
2. Compute Brier/log-loss by city/source/horizon.
3. Add ex-outlier EV reports.
4. Gate live graduation on forward sample quality, not anecdotal wins.

Acceptance criteria:

- Bot D can answer: "When we say 70%, how often did it resolve YES?"
- EV remains positive after excluding the largest 1-2 wins.
- Correlated same-event bucket exposure is accounted for.

### Phase 5: NBM And Cross-Venue Comparator

1. Add NBM extraction prototype for US cities.
2. Run NBM shadow probabilities.
3. Add read-only Kalshi comparator only for matched definitions.
4. Promote only if calibration improves.

Acceptance criteria:

- NBM improves Brier/log-loss over existing Open-Meteo + RMSE model.
- Kalshi comparator reduces false positives rather than adding noise.

## Direct Questions For Grok

Please verify or refute these claims with external sources:

1. For Polymarket daily city temperature markets, are settlement stations airport-specific, city-center, Wunderground pages, NWS climate reports, or market-specific?
2. Does Dallas resolve on `KDAL` or `KDFW`?
3. Does NYC resolve on `KLGA`, Central Park, or another source?
4. What are the exact rounding rules for US and international city temperature markets?
5. Is Open-Meteo daily ensemble member max/min reliable enough for empirical bucket probabilities?
6. Is NBM percentile extraction practical enough for a solo-operator bot?
7. Does NBM offer better point/station specificity than Open-Meteo for airport-settled markets?
8. Should same-day max-so-far be based on METAR only, AviationWeather history, NWS observations, Wunderground, or the exact settlement source?
9. What sample size should be required before taking Bot D live?
10. Which of these ideas is likely to add real edge, and which is complexity theater?

## Bottom Line

Bot D should not go live just because V2 is ready. The profitable path is to make the model settlement-exact and calibration-measured.

The priority is:

1. Settlement station and rounding correctness.
2. Empirical ensemble probability as a guard against fitted-distribution overconfidence.
3. Same-day max-so-far / impossible-bucket detection.
4. Brier/log-loss calibration by city and horizon.
5. NBM and Kalshi comparator as shadow sources only.

The public repos are useful as research, but their execution layers are not better than ours. The edge is in the boring details: exact station, exact rounding, exact bucket mapping, and proving that our stated probabilities are calibrated after settlement.
