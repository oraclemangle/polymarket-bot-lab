# Data Sources

## Market Data

The strategy uses prediction-market order books and market metadata:

- active temperature markets;
- YES/NO token ids;
- market prices;
- order book depth;
- market close/end dates;
- resolution outcome after settlement.

Raw credentials, wallet identity, and production endpoints are not included in
this share pack.

## Weather Data

The strategy uses station-level weather forecasts rather than generic city
headlines.

| Source | Role |
|---|---|
| Multi-model forecast source | Primary when available; useful for model agreement |
| NOAA NBM | Strong live performer so far; important fallback/primary source |
| GribStream NBM | Paid/source-confidence supplement; useful comparison input |
| NWS forecast | Second opinion and diagnostic source |
| METAR / station observations | Current observed high/low and late-day reality check |

## Station Mapping

The strategy maps markets to settlement stations. Example station-style
mapping:

| Market city | Settlement style |
|---|---|
| New York City | Airport station rather than city-centre forecast |
| Chicago | Airport station |
| Dallas | Airport station |
| Miami | Airport station |
| Seattle | Airport station |
| Atlanta | Airport station |

The important principle is not the exact list above. The important principle
is to use the market's settlement station, not the generic city forecast.

## Source Freshness

Forecasts are only useful if they are fresh enough. The strategy records
forecast source, forecast timestamp, source snapshots, and model agreement so
later reviews can separate:

- good trades made with fresh multi-source evidence;
- weak trades made during fallback or disagreement conditions;
- stale forecast risk;
- source-specific P&L.

