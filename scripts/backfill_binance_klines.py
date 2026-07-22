#!/usr/bin/env python3
"""Download Binance public monthly kline ZIPs and write local Parquet.

This is a read-only external-data backfill for research reports. It writes
only under the configured output directory and does not touch bot databases,
wallets, or services.
"""
from __future__ import annotations

import argparse
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

DEFAULT_OUT_DIR = Path(
    "data/external/cex/binance/klines"
)
UTC = timezone.utc  # noqa: UP017 - Becker's uv env runs Python 3.9.
BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
COLUMNS = [
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time_ms",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    p.add_argument("--interval", default="1m")
    p.add_argument("--start-month", required=True, help="YYYY-MM")
    p.add_argument("--end-month", required=True, help="YYYY-MM, inclusive")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def month_range(start: str, end: str) -> list[str]:
    start_dt = datetime.strptime(start, "%Y-%m")
    end_dt = datetime.strptime(end, "%Y-%m")
    months = []
    year, month = start_dt.year, start_dt.month
    while (year, month) <= (end_dt.year, end_dt.month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def download_zip(symbol: str, interval: str, month: str) -> bytes:
    url = f"{BASE_URL}/{symbol}/{interval}/{symbol}-{interval}-{month}.zip"
    with urlopen(url, timeout=60) as response:
        return response.read()


def zip_to_dataframe(raw: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = [name for name in zf.namelist() if name.endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected one CSV in ZIP, found {names}")
        with zf.open(names[0]) as fh:
            df = pd.read_csv(fh, header=None, names=COLUMNS)
    df = df.drop(columns=["ignore"])
    numeric_cols = [c for c in df.columns if c not in {"open_time_ms", "close_time_ms", "trade_count"}]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("open_time_ms", "close_time_ms", "trade_count"):
        df[col] = pd.to_numeric(df[col], errors="raise").astype("int64")
    # Recent Binance Vision files use microsecond timestamps while older docs
    # and filenames still describe millisecond kline fields.
    for col in ("open_time_ms", "close_time_ms"):
        if int(df[col].max()) > 10_000_000_000_000:
            df[col] = (df[col] // 1000).astype("int64")
    df["open_time"] = pd.to_datetime(df["open_time_ms"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time_ms"], unit="ms", utc=True)
    return df


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_dir).resolve()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    months = month_range(args.start_month, args.end_month)
    manifest = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "base_url": BASE_URL,
        "interval": args.interval,
        "symbols": symbols,
        "months": months,
        "files": [],
    }
    for symbol in symbols:
        symbol_dir = out_root / args.interval / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        for month in months:
            out_path = symbol_dir / f"{symbol}-{args.interval}-{month}.parquet"
            if out_path.exists() and not args.force:
                print(f"skip existing {out_path}")
            else:
                print(f"download {symbol} {args.interval} {month}")
                raw = download_zip(symbol, args.interval, month)
                df = zip_to_dataframe(raw)
                df.to_parquet(out_path, index=False)
            manifest["files"].append(str(out_path))
    manifest_path = out_root / args.interval / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()
