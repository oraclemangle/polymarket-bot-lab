# Evidence Summary

**Snapshot date:** 2026-05-10
**Sample:** small live probe sample, not a final proof of scalability.

## Closed Live Weather Lots

| Slice | Closed | Wins | Win rate | P&L | Cost | ROI |
|---|---:|---:|---:|---:|---:|---:|
| All closed | 35 | 25 | 71.4% | +$13.31 | $109.52 | +12.15% |
| `>=50c` | 28 | 23 | 82.1% | +$10.48 | $102.44 | +10.23% |
| `20-50c` | 3 | 1 | 33.3% | -$1.02 | $5.98 | -17.08% |
| `<10c` | 4 | 1 | 25.0% | +$3.85 | $1.10 | +349.00% |

There were no closed `10-20c` lots in this snapshot.

## Forecast Source

| Source | Closed | Wins | Win rate | P&L | ROI |
|---|---:|---:|---:|---:|---:|
| NOAA NBM | 14 | 10 | 71.4% | +$8.05 | +19.72% |
| Multi-model | 16 | 11 | 68.8% | +$5.84 | +12.12% |
| GribStream NBM | 4 | 3 | 75.0% | -$1.72 | -10.32% |

## Setup Tier

| Tier | Closed | Wins | Win rate | P&L | ROI |
|---|---:|---:|---:|---:|---:|
| A | 8 | 6 | 75.0% | +$0.16 | +0.54% |
| B | 23 | 18 | 78.3% | +$17.02 | +23.75% |
| C | 3 | 0 | 0.0% | -$5.00 | -100.00% |

This is why the ladder uses Tier B rather than assuming Tier A is best.

## City

| City | Closed | Wins | Win rate | P&L | ROI |
|---|---:|---:|---:|---:|---:|
| NYC | 11 | 9 | 81.8% | +$14.14 | +47.21% |
| Chicago | 4 | 4 | 100.0% | +$4.65 | +30.52% |
| Atlanta | 5 | 4 | 80.0% | +$1.60 | +8.75% |
| Seattle | 7 | 3 | 42.9% | -$6.40 | -30.01% |
| Denver | 2 | 1 | 50.0% | -$2.28 | -31.49% |

The sample is too small for a final city ranking, but large enough to avoid
scaling the weakest city slices immediately.

## Replayed Sizing

| Schedule | Closed P&L | Closed cost | ROI |
|---|---:|---:|---:|
| Fixed 5 shares | +$13.31 | $109.52 | +12.15% |
| Evidence-gated ladder | +$50.08 | $180.56 | +27.73% |

The replay assumes the same fills and prices. It does not prove future fills
will behave identically. It only shows that the old flat sizing underweighted
the realised winning slices.

