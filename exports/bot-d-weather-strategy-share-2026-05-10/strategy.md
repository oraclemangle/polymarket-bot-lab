# Strategy

## Core Thesis

Daily weather markets often price off generic city forecasts, but settlement
usually depends on a specific airport or official station. The edge is not
"predict weather better than meteorologists"; it is:

1. use the correct settlement station;
2. compare multiple forecast sources;
3. avoid trades when official sources disagree too much;
4. size up only when the live evidence says a slice is working.

The bot focuses on daily high/low temperature markets with fixed bucket or
threshold outcomes.

## Market Selection

Candidate markets must have:

- known city and date;
- known temperature type: high or low;
- known bucket/threshold;
- verified settlement station;
- known market end date;
- sufficient market volume;
- no stale or single-source forecast path for live entries.

Markets without verified settlement mapping are skipped. This matters because
"New York City" may resolve at an airport station rather than a city-centre
weather station.

## Forecast Inputs

The strategy compares a market-implied probability with a weather-derived
probability. Live entries are allowed only when the forecast source is useful
enough for that market. The current source hierarchy is:

1. multi-model forecast source when available;
2. NOAA NBM forecast;
3. GribStream NBM as a paid/source-confidence supplement;
4. NWS-only fallback for diagnostics, not live entries.

If the system falls back to a single NWS point forecast, live entries are
blocked because the model and veto would be the same source.

## Probability And Edge

The bot estimates the probability that the market resolves YES from the
forecast mean and uncertainty. It then compares that to the market price.

```text
model_probability = probability(bucket resolves YES)
market_probability = current YES price
net_edge = model_probability - market_probability
```

If `net_edge` is positive, the candidate is a possible YES buy. If negative,
the candidate is a possible NO buy. Tiny edges are ignored.

## Second Opinion Gates

The strategy avoids trades where the model signal is likely to be false
precision:

- NWS second-opinion veto: skip if NWS disagrees too much with the model.
- Empirical ensemble-shape veto: skip when model CDF and ensemble member
  distribution disagree materially.
- Expensive-NO guard: for high-priced NO entries, require enough distance from
  the bucket and enough independent source agreement.
- Source freshness checks: avoid stale forecasts.
- Fallback block: live entries never use NWS-only fallback.

## Trade Lifecycle

1. Scan temperature markets.
2. Parse city, date, high/low, bucket bounds, and settlement station.
3. Pull or reuse weather forecasts.
4. Estimate model probability and edge.
5. Apply vetoes and quality labels.
6. Size the order.
7. Place a live limit order only if all caps and guards pass.
8. Reconcile live fills.
9. Auto-sell near-certain winners around 99c when market depth allows.
10. Redeem resolved winners through the normal settlement path.

