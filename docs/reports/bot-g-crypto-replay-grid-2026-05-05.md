# Bot G Crypto Recorder Replay Grid

Generated: `2026-05-05T09:45:05.824915+00:00`
Window start: `2026-05-02T09:45:05.780431+00:00`

## Interpretation

This is read-only analysis. Actual Bot G rows come from orders/trades; recorder rows show observed market availability, not guaranteed fills.

Theory lanes under review:

- `45s-60s`: test whether wider `5c-8c` entries behave better.
- `30s-45s`: test whether `3c-5c` is the stronger late-middle lane.
- `<30s`: test whether `1c-3c` is only sensible very close to close.

## Overall By Bot

| bot | placed | filled | closed | wins | no-fill | open | P&L | ROI | ex-win ROI | ex-two ROI | fill rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bot_g_prime_live | 36 | 31 | 31 | 0 | 5 | 0 | $-71.33 | -100.0% | -100.0% | -100.0% | 86.1% |
| bot_g_prime | 53 | 53 | 53 | 4 | 0 | 0 | $+131.52 | 71.7% | 6.5% | -48.1% | 100.0% |

## bot_g_prime_live Lead x Price Grid

| lead | theory lane | price | placed | filled | closed | wins | P&L | ROI | ex-two ROI | fill rate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 30s-45s | 3c-5c theory lane | 3.5c-5.5c | 6 | 6 | 6 | 0 | $-19.96 | -100.0% | -100.0% | 100.0% |
| 45s-60s | 5c-8c theory lane | 3.5c-5.5c | 10 | 9 | 9 | 0 | $-28.16 | -100.0% | -100.0% | 90.0% |
| <30s | 1c-3c theory lane | 3.5c-5.5c | 11 | 9 | 9 | 0 | $-18.27 | -100.0% | -100.0% | 81.8% |
| after_close | outside theory lanes | 3.5c-5.5c | 9 | 7 | 7 | 0 | $-4.94 | -100.0% | -100.0% | 77.8% |

## bot_g_prime Lead x Price Grid

| lead | theory lane | price | placed | filled | closed | wins | P&L | ROI | ex-two ROI | fill rate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 30s-45s | 3c-5c theory lane | 3.5c-5.5c | 8 | 8 | 8 | 0 | $-21.35 | -100.0% | -100.0% | 100.0% |
| 30s-45s | 3c-5c theory lane | 5.5c-8c | 8 | 8 | 8 | 2 | $+60.92 | 209.4% | -100.0% | 100.0% |
| <30s | 1c-3c theory lane | 3.5c-5.5c | 9 | 9 | 9 | 0 | $-31.89 | -100.0% | -100.0% | 100.0% |
| <30s | 1c-3c theory lane | 5.5c-8c | 6 | 6 | 6 | 0 | $-21.30 | -100.0% | -100.0% | 100.0% |
| after_close | outside theory lanes | 3.5c-5.5c | 17 | 17 | 17 | 2 | $+164.06 | 269.2% | -100.0% | 100.0% |
| after_close | outside theory lanes | 5.5c-8c | 5 | 5 | 5 | 0 | $-18.92 | -100.0% | -100.0% | 100.0% |

## Actual Entry Grid With Symbol And Window

| bot | lead | price | symbol | window | placed | filled | closed | wins | P&L | ROI | ex-two ROI |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bot_g_prime | 30s-45s | 3.5c-5.5c | BTC | unknown | 4 | 4 | 4 | 0 | $-14.40 | -100.0% | -100.0% |
| bot_g_prime | 30s-45s | 3.5c-5.5c | DOGE | 15 | 1 | 1 | 1 | 0 | $-1.56 | -100.0% | -100.0% |
| bot_g_prime | 30s-45s | 3.5c-5.5c | XRP | unknown | 3 | 3 | 3 | 0 | $-5.39 | -100.0% | -100.0% |
| bot_g_prime | 30s-45s | 5.5c-8c | BTC | unknown | 4 | 4 | 4 | 1 | $+45.10 | 259.2% | -100.0% |
| bot_g_prime | 30s-45s | 5.5c-8c | DOGE | unknown | 1 | 1 | 1 | 0 | $-1.40 | -100.0% | -100.0% |
| bot_g_prime | 30s-45s | 5.5c-8c | ETH | unknown | 1 | 1 | 1 | 0 | $-5.00 | -100.0% | -100.0% |
| bot_g_prime | 30s-45s | 5.5c-8c | XRP | unknown | 2 | 2 | 2 | 1 | $+22.22 | 420.1% | -100.0% |
| bot_g_prime | <30s | 3.5c-5.5c | BTC | unknown | 6 | 6 | 6 | 0 | $-27.00 | -100.0% | -100.0% |
| bot_g_prime | <30s | 3.5c-5.5c | DOGE | unknown | 1 | 1 | 1 | 0 | $-1.52 | -100.0% | -100.0% |
| bot_g_prime | <30s | 3.5c-5.5c | ETH | unknown | 1 | 1 | 1 | 0 | $-1.69 | -100.0% | -100.0% |
| bot_g_prime | <30s | 3.5c-5.5c | SOL | unknown | 1 | 1 | 1 | 0 | $-1.68 | -100.0% | -100.0% |
| bot_g_prime | <30s | 5.5c-8c | BTC | unknown | 2 | 2 | 2 | 0 | $-10.00 | -100.0% | -100.0% |
| bot_g_prime | <30s | 5.5c-8c | ETH | unknown | 1 | 1 | 1 | 0 | $-5.00 | -100.0% | -100.0% |
| bot_g_prime | <30s | 5.5c-8c | SOL | unknown | 1 | 1 | 1 | 0 | $-1.98 | -100.0% | -100.0% |
| bot_g_prime | <30s | 5.5c-8c | XRP | unknown | 2 | 2 | 2 | 0 | $-4.32 | -100.0% | -100.0% |
| bot_g_prime | after_close | 3.5c-5.5c | BTC | unknown | 9 | 9 | 9 | 1 | $+90.08 | 258.0% | -100.0% |
| bot_g_prime | after_close | 3.5c-5.5c | ETH | unknown | 5 | 5 | 5 | 1 | $+79.05 | 377.2% | -100.0% |
| bot_g_prime | after_close | 3.5c-5.5c | SOL | unknown | 3 | 3 | 3 | 0 | $-5.06 | -100.0% | -100.0% |
| bot_g_prime | after_close | 5.5c-8c | BTC | unknown | 3 | 3 | 3 | 0 | $-11.27 | -100.0% | -100.0% |
| bot_g_prime | after_close | 5.5c-8c | ETH | unknown | 2 | 2 | 2 | 0 | $-7.64 | -100.0% | -100.0% |
| bot_g_prime_live | 30s-45s | 3.5c-5.5c | BTC | unknown | 4 | 4 | 4 | 0 | $-14.23 | -100.0% | -100.0% |
| bot_g_prime_live | 30s-45s | 3.5c-5.5c | ETH | unknown | 2 | 2 | 2 | 0 | $-5.73 | -100.0% | -100.0% |
| bot_g_prime_live | 45s-60s | 3.5c-5.5c | BTC | unknown | 5 | 4 | 4 | 0 | $-14.27 | -100.0% | -100.0% |
| bot_g_prime_live | 45s-60s | 3.5c-5.5c | ETH | unknown | 1 | 1 | 1 | 0 | $-4.00 | -100.0% | -100.0% |
| bot_g_prime_live | 45s-60s | 3.5c-5.5c | SOL | unknown | 4 | 4 | 4 | 0 | $-9.89 | -100.0% | -100.0% |
| bot_g_prime_live | <30s | 3.5c-5.5c | BTC | unknown | 8 | 6 | 6 | 0 | $-12.15 | -100.0% | -100.0% |
| bot_g_prime_live | <30s | 3.5c-5.5c | ETH | unknown | 2 | 2 | 2 | 0 | $-3.85 | -100.0% | -100.0% |
| bot_g_prime_live | <30s | 3.5c-5.5c | SOL | unknown | 1 | 1 | 1 | 0 | $-2.28 | -100.0% | -100.0% |
| bot_g_prime_live | after_close | 3.5c-5.5c | BTC | unknown | 7 | 6 | 6 | 0 | $-4.69 | -100.0% | -100.0% |
| bot_g_prime_live | after_close | 3.5c-5.5c | ETH | unknown | 2 | 1 | 1 | 0 | $-0.25 | -100.0% | -100.0% |

## Recorder Availability Grid

Recorder availability counts cheap-side market snapshots near close. These are opportunities to investigate, not proof that Bot G would fill.

| lead | theory lane | cheap price | symbol | window | snapshots | markets | avg 24h vol |
|---|---|---|---|---:|---:|---:|---:|
| 30s-45s | 3c-5c theory lane | 1c-3c | BTC | unknown | 3 | 3 | $11993 |
| 30s-45s | 3c-5c theory lane | 1c-3c | DOGE | unknown | 3 | 3 | $142 |
| 30s-45s | 3c-5c theory lane | 1c-3c | ETH | unknown | 2 | 2 | $9692 |
| 30s-45s | 3c-5c theory lane | 1c-3c | XRP | unknown | 2 | 2 | $936 |
| 30s-45s | 3c-5c theory lane | 3.5c-5.5c | BTC | unknown | 2 | 2 | $11490 |
| 30s-45s | 3c-5c theory lane | 3.5c-5.5c | ETH | unknown | 1 | 1 | $9119 |
| 30s-45s | 3c-5c theory lane | 3.5c-5.5c | SOL | unknown | 1 | 1 | $909 |
| 30s-45s | 3c-5c theory lane | 3c-3.5c | SOL | unknown | 1 | 1 | $946 |
| 30s-45s | 3c-5c theory lane | 5.5c-8c | BTC | unknown | 1 | 1 | $22969 |
| 30s-45s | 3c-5c theory lane | 5.5c-8c | SOL | unknown | 2 | 2 | $849 |
| 30s-45s | 3c-5c theory lane | 5.5c-8c | XRP | unknown | 2 | 2 | $1572 |
| 30s-45s | 3c-5c theory lane | <1c | BTC | unknown | 1 | 1 | $94086 |
| 30s-45s | 3c-5c theory lane | <1c | DOGE | unknown | 1 | 1 | $1352 |
| 30s-45s | 3c-5c theory lane | <1c | ETH | unknown | 3 | 3 | $3268 |
| 30s-45s | 3c-5c theory lane | <1c | SOL | unknown | 3 | 3 | $4780 |
| 30s-45s | 3c-5c theory lane | <1c | XRP | unknown | 1 | 1 | $1702 |
| 30s-45s | 3c-5c theory lane | >8c | BTC | 5 | 1 | 1 | $5546 |
| 30s-45s | 3c-5c theory lane | >8c | BTC | unknown | 16 | 16 | $4669 |
| 30s-45s | 3c-5c theory lane | >8c | DOGE | unknown | 8 | 8 | $106 |
| 30s-45s | 3c-5c theory lane | >8c | ETH | unknown | 11 | 11 | $1210 |
| 30s-45s | 3c-5c theory lane | >8c | SOL | unknown | 12 | 12 | $581 |
| 30s-45s | 3c-5c theory lane | >8c | XRP | 15 | 1 | 1 | $519 |
| 30s-45s | 3c-5c theory lane | >8c | XRP | unknown | 12 | 12 | $609 |
| 45s-60s | 5c-8c theory lane | 1c-3c | BTC | unknown | 2 | 2 | $18216 |
| 45s-60s | 5c-8c theory lane | 1c-3c | DOGE | unknown | 1 | 1 | $96 |
| 45s-60s | 5c-8c theory lane | 1c-3c | ETH | unknown | 2 | 2 | $4487 |
| 45s-60s | 5c-8c theory lane | 1c-3c | SOL | unknown | 2 | 2 | $723 |
| 45s-60s | 5c-8c theory lane | 1c-3c | XRP | unknown | 2 | 2 | $1166 |
| 45s-60s | 5c-8c theory lane | 3.5c-5.5c | SOL | unknown | 1 | 1 | $3383 |
| 45s-60s | 5c-8c theory lane | 3c-3.5c | BTC | unknown | 1 | 1 | $95 |
| 45s-60s | 5c-8c theory lane | 3c-3.5c | ETH | unknown | 1 | 1 | $89 |
| 45s-60s | 5c-8c theory lane | 5.5c-8c | DOGE | unknown | 1 | 1 | $94 |
| 45s-60s | 5c-8c theory lane | 5.5c-8c | SOL | unknown | 2 | 2 | $872 |
| 45s-60s | 5c-8c theory lane | 5.5c-8c | XRP | unknown | 1 | 1 | $1205 |
| 45s-60s | 5c-8c theory lane | <1c | BTC | unknown | 4 | 4 | $42834 |
| 45s-60s | 5c-8c theory lane | <1c | DOGE | unknown | 1 | 1 | $1748 |
| 45s-60s | 5c-8c theory lane | <1c | ETH | unknown | 12 | 12 | $40406 |
| 45s-60s | 5c-8c theory lane | <1c | SOL | unknown | 2 | 2 | n/a |
| 45s-60s | 5c-8c theory lane | <1c | XRP | unknown | 2 | 2 | $1103 |
| 45s-60s | 5c-8c theory lane | >8c | BTC | unknown | 23 | 23 | $3105 |
| 45s-60s | 5c-8c theory lane | >8c | DOGE | unknown | 5 | 5 | $91 |
| 45s-60s | 5c-8c theory lane | >8c | ETH | unknown | 17 | 17 | $1243 |
| 45s-60s | 5c-8c theory lane | >8c | SOL | unknown | 14 | 14 | $644 |
| 45s-60s | 5c-8c theory lane | >8c | XRP | unknown | 6 | 6 | $454 |
| 60s-90s | outside theory lanes | 1c-3c | BTC | unknown | 5 | 5 | $7708 |
| 60s-90s | outside theory lanes | 1c-3c | DOGE | unknown | 2 | 2 | $518 |
| 60s-90s | outside theory lanes | 1c-3c | ETH | unknown | 6 | 6 | $2522 |
| 60s-90s | outside theory lanes | 1c-3c | XRP | unknown | 1 | 1 | $974 |
| 60s-90s | outside theory lanes | 3.5c-5.5c | BTC | unknown | 2 | 2 | $11076 |
| 60s-90s | outside theory lanes | 3.5c-5.5c | DOGE | unknown | 2 | 2 | $92 |
| 60s-90s | outside theory lanes | 3.5c-5.5c | SOL | unknown | 2 | 2 | $1024 |
| 60s-90s | outside theory lanes | 3.5c-5.5c | XRP | unknown | 2 | 2 | $1710 |
| 60s-90s | outside theory lanes | 3c-3.5c | DOGE | unknown | 1 | 1 | $99 |
| 60s-90s | outside theory lanes | 3c-3.5c | XRP | unknown | 1 | 1 | $3350 |
| 60s-90s | outside theory lanes | 5.5c-8c | BTC | unknown | 5 | 5 | $14281 |
| 60s-90s | outside theory lanes | 5.5c-8c | DOGE | unknown | 2 | 2 | $94 |
| 60s-90s | outside theory lanes | 5.5c-8c | ETH | unknown | 1 | 1 | $5550 |
| 60s-90s | outside theory lanes | 5.5c-8c | SOL | unknown | 1 | 1 | $562 |
| 60s-90s | outside theory lanes | 5.5c-8c | XRP | unknown | 4 | 4 | $1188 |
| 60s-90s | outside theory lanes | <1c | BTC | unknown | 5 | 5 | $18474 |
| 60s-90s | outside theory lanes | <1c | ETH | unknown | 8 | 8 | $4974 |
| 60s-90s | outside theory lanes | <1c | XRP | unknown | 1 | 1 | $2239 |
| 60s-90s | outside theory lanes | >8c | BTC | unknown | 47 | 47 | $4759 |
| 60s-90s | outside theory lanes | >8c | DOGE | unknown | 14 | 14 | $90 |
| 60s-90s | outside theory lanes | >8c | ETH | unknown | 37 | 37 | $1258 |
| 60s-90s | outside theory lanes | >8c | SOL | unknown | 28 | 28 | $708 |
| 60s-90s | outside theory lanes | >8c | XRP | unknown | 19 | 19 | $757 |
| <30s | 1c-3c theory lane | 1c-3c | BTC | unknown | 7 | 7 | $5420 |
| <30s | 1c-3c theory lane | 1c-3c | DOGE | unknown | 2 | 2 | $176 |
| <30s | 1c-3c theory lane | 1c-3c | ETH | unknown | 7 | 7 | $2069 |
| <30s | 1c-3c theory lane | 1c-3c | SOL | unknown | 1 | 1 | $3828 |
| <30s | 1c-3c theory lane | 1c-3c | XRP | unknown | 6 | 6 | $1546 |
| <30s | 1c-3c theory lane | 3.5c-5.5c | BTC | unknown | 4 | 4 | $15768 |
| <30s | 1c-3c theory lane | 3.5c-5.5c | ETH | unknown | 1 | 1 | $83 |
| <30s | 1c-3c theory lane | 3.5c-5.5c | SOL | unknown | 2 | 2 | $1024 |
| <30s | 1c-3c theory lane | 3.5c-5.5c | XRP | unknown | 2 | 2 | $1745 |
| <30s | 1c-3c theory lane | 3c-3.5c | DOGE | unknown | 1 | 1 | $99 |
| <30s | 1c-3c theory lane | 3c-3.5c | ETH | unknown | 1 | 1 | $9180 |
| <30s | 1c-3c theory lane | 5.5c-8c | BTC | unknown | 3 | 3 | $15732 |
| <30s | 1c-3c theory lane | 5.5c-8c | DOGE | unknown | 1 | 1 | $89 |
| <30s | 1c-3c theory lane | 5.5c-8c | ETH | unknown | 1 | 1 | $5550 |
| <30s | 1c-3c theory lane | 5.5c-8c | SOL | unknown | 3 | 3 | $662 |
| <30s | 1c-3c theory lane | 5.5c-8c | XRP | unknown | 2 | 2 | $1210 |
| <30s | 1c-3c theory lane | <1c | BTC | unknown | 5 | 5 | $18474 |
| <30s | 1c-3c theory lane | <1c | ETH | unknown | 10 | 10 | $5843 |
| <30s | 1c-3c theory lane | <1c | SOL | unknown | 1 | 1 | $4767 |
| <30s | 1c-3c theory lane | <1c | XRP | unknown | 1 | 1 | $2239 |
| <30s | 1c-3c theory lane | >8c | BTC | unknown | 46 | 46 | $5217 |
| <30s | 1c-3c theory lane | >8c | DOGE | unknown | 14 | 14 | $89 |
| <30s | 1c-3c theory lane | >8c | ETH | unknown | 43 | 43 | $1650 |
| <30s | 1c-3c theory lane | >8c | SOL | unknown | 26 | 26 | $937 |
| <30s | 1c-3c theory lane | >8c | XRP | unknown | 24 | 24 | $441 |
| >=90s | outside theory lanes | 1c-3c | BTC | unknown | 7 | 7 | $9445 |
| >=90s | outside theory lanes | 1c-3c | DOGE | unknown | 4 | 4 | $130 |
| >=90s | outside theory lanes | 1c-3c | ETH | unknown | 4 | 4 | $7090 |
| >=90s | outside theory lanes | 1c-3c | SOL | unknown | 1 | 1 | $506 |
| >=90s | outside theory lanes | 1c-3c | XRP | unknown | 4 | 4 | $1066 |
| >=90s | outside theory lanes | 3.5c-5.5c | BTC | unknown | 2 | 2 | $11490 |
| >=90s | outside theory lanes | 3.5c-5.5c | ETH | unknown | 2 | 2 | $4601 |
| >=90s | outside theory lanes | 3.5c-5.5c | SOL | unknown | 2 | 2 | $2146 |
| >=90s | outside theory lanes | 3c-3.5c | ETH | unknown | 2 | 2 | $4649 |
| >=90s | outside theory lanes | 3c-3.5c | SOL | unknown | 1 | 1 | $946 |
| >=90s | outside theory lanes | 5.5c-8c | BTC | unknown | 1 | 1 | $22969 |
| >=90s | outside theory lanes | 5.5c-8c | DOGE | unknown | 1 | 1 | $94 |
| >=90s | outside theory lanes | 5.5c-8c | SOL | unknown | 1 | 1 | $786 |
| >=90s | outside theory lanes | 5.5c-8c | XRP | unknown | 1 | 1 | $719 |
| >=90s | outside theory lanes | <1c | BTC | unknown | 4 | 4 | $61909 |
| >=90s | outside theory lanes | <1c | DOGE | unknown | 2 | 2 | $1550 |
| >=90s | outside theory lanes | <1c | ETH | unknown | 11 | 11 | $41729 |
| >=90s | outside theory lanes | <1c | SOL | unknown | 5 | 5 | $4112 |
| >=90s | outside theory lanes | <1c | XRP | unknown | 1 | 1 | n/a |
| >=90s | outside theory lanes | >8c | BTC | 5 | 1 | 1 | $5546 |
| >=90s | outside theory lanes | >8c | BTC | unknown | 39 | 39 | $3547 |
| >=90s | outside theory lanes | >8c | DOGE | unknown | 12 | 12 | $119 |
| >=90s | outside theory lanes | >8c | ETH | unknown | 22 | 22 | $1853 |
| >=90s | outside theory lanes | >8c | SOL | unknown | 22 | 22 | $673 |
| >=90s | outside theory lanes | >8c | XRP | 15 | 1 | 1 | $519 |
| >=90s | outside theory lanes | >8c | XRP | unknown | 14 | 14 | $560 |

## Recent Entries

| bot | placed | symbol | window | lead | price | outcome | status | P&L |
|---|---|---|---:|---:|---|---|---|---:|
| bot_g_prime | 2026-05-04 21:14:29.923057 | BTC | unknown | 30s-45s | 5.5c-8c | filled | FILLED | $-2.40 |
| bot_g_prime_live | 2026-05-04 21:14:42.578319 | BTC | unknown | <30s | 3.5c-5.5c | filled | matched | $-2.25 |
| bot_g_prime_live | 2026-05-04 21:39:54.747877 | BTC | unknown | <30s | 3.5c-5.5c | filled | matched | $-3.00 |
| bot_g_prime_live | 2026-05-04 22:24:41.466466 | BTC | unknown | <30s | 3.5c-5.5c | no_fill | EXCHANGE_CLOSED | $+0.00 |
| bot_g_prime | 2026-05-04 22:34:41.813919 | BTC | unknown | <30s | 3.5c-5.5c | filled | FILLED | $-5.00 |
| bot_g_prime_live | 2026-05-04 22:34:43.116863 | BTC | unknown | <30s | 3.5c-5.5c | filled | matched | $-1.00 |
| bot_g_prime_live | 2026-05-04 22:39:16.057849 | SOL | unknown | 45s-60s | 3.5c-5.5c | filled | matched | $-3.30 |
| bot_g_prime_live | 2026-05-04 22:54:20.830151 | BTC | unknown | 30s-45s | 3.5c-5.5c | filled | matched | $-4.54 |
| bot_g_prime | 2026-05-04 22:54:23.162655 | BTC | unknown | 30s-45s | 3.5c-5.5c | filled | FILLED | $-5.00 |
| bot_g_prime_live | 2026-05-04 23:24:17.101668 | BTC | unknown | 30s-45s | 3.5c-5.5c | filled | matched | $-1.50 |
| bot_g_prime | 2026-05-04 23:24:23.926674 | BTC | unknown | 30s-45s | 5.5c-8c | filled | FILLED | $-5.00 |
| bot_g_prime | 2026-05-04 23:54:24.396265 | XRP | unknown | 30s-45s | 5.5c-8c | filled | FILLED | $-3.09 |
| bot_g_prime_live | 2026-05-05 00:29:53.649235 | BTC | unknown | <30s | 3.5c-5.5c | filled | matched | $-0.84 |
| bot_g_prime_live | 2026-05-05 01:39:40.836991 | BTC | unknown | <30s | 3.5c-5.5c | no_fill | EXCHANGE_CLOSED | $+0.00 |
| bot_g_prime | 2026-05-05 01:39:48.689417 | BTC | unknown | <30s | 5.5c-8c | filled | FILLED | $-5.00 |
| bot_g_prime | 2026-05-05 02:29:30.614619 | SOL | unknown | <30s | 5.5c-8c | filled | FILLED | $-1.98 |
| bot_g_prime | 2026-05-05 02:54:21.567090 | ETH | unknown | 30s-45s | 5.5c-8c | filled | FILLED | $-5.00 |
| bot_g_prime_live | 2026-05-05 03:19:19.254987 | ETH | unknown | 30s-45s | 3.5c-5.5c | filled | FILLED | $-2.25 |
| bot_g_prime_live | 2026-05-05 04:04:53.114652 | ETH | unknown | <30s | 3.5c-5.5c | filled | EXCHANGE_CLOSED | $-0.95 |
| bot_g_prime | 2026-05-05 04:04:54.353482 | ETH | unknown | <30s | 3.5c-5.5c | filled | FILLED | $-1.69 |
| bot_g_prime_live | 2026-05-05 04:39:12.292443 | BTC | unknown | 45s-60s | 3.5c-5.5c | filled | EXCHANGE_CLOSED | $-4.54 |
| bot_g_prime | 2026-05-05 04:39:27.783179 | BTC | unknown | 30s-45s | 5.5c-8c | filled | FILLED | $-5.00 |
| bot_g_prime_live | 2026-05-05 07:09:23.307218 | BTC | unknown | 30s-45s | 3.5c-5.5c | filled | EXCHANGE_CLOSED | $-4.54 |
| bot_g_prime | 2026-05-05 07:09:23.910740 | BTC | unknown | 30s-45s | 3.5c-5.5c | filled | FILLED | $-5.00 |
| bot_g_prime | 2026-05-05 09:14:18.933108 | DOGE | 15 | 30s-45s | 3.5c-5.5c | filled | FILLED | $-1.56 |
