#!/usr/bin/env python3
"""Download a filtered slice of the SII-WANGZJ/Polymarket_data dataset.

Source: https://huggingface.co/datasets/SII-WANGZJ/Polymarket_data
Full size: 107 GB across 5 parquet files. We pull a filtered slice containing
only markets in our target categories {geopolitics, politics, finance,
economics}, plus the corresponding trades / users / quant rows. Expected
slice size: 3–8 GB depending on category breadth in the full data.

Storage
-------
Writes to `data/wangzj_slice/` on whichever host runs this script. On the bot host
this requires `data/` to live on a disk with ≥10 GB free; the Session 17g
late-PM plan calls for a +24 GB LXC rootfs resize (8 GB → 32 GB) before
running.

Strategy
--------
1. Download `markets.parquet` (68 MB, cheap).
2. Read + filter to target categories.
3. Emit `data/wangzj_slice/markets.parquet` (filtered).
4. Collect market_ids into an allow-set.
5. Stream-download `trades.parquet` / `users.parquet` / `quant.parquet` in
   row-groups, filter each row-group against the allow-set, write filtered
   output. Row-group streaming keeps peak memory low.
6. Emit a `meta.json` with slice stats (row counts, categories, source
   commit SHA).

Dependencies
------------
  pyarrow        — parquet I/O
  huggingface_hub — HuggingFace Datasets auth (optional; public dataset
                   doesn't strictly require it but auth raises rate limits)

Install:
    .venv/bin/pip install pyarrow huggingface_hub

Usage
-----
    # Dry-run: download markets.parquet and print filter stats only:
    python scripts/download_wangzj_slice.py

    # Full slice download:
    python scripts/download_wangzj_slice.py --execute
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


HF_REPO_ID = "SII-WANGZJ/Polymarket_data"
HF_REPO_TYPE = "dataset"
FILES = ("markets.parquet", "trades.parquet", "users.parquet", "quant.parquet")
DEFAULT_CATEGORIES = ("geopolitics", "politics", "finance", "economics")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "wangzj_slice"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download filtered wangzj dataset slice.")
    p.add_argument("--execute", action="store_true",
                   help="Perform the full slice download. Default: fetch "
                        "markets.parquet only and print filter stats.")
    p.add_argument(
        "--categories",
        default=",".join(DEFAULT_CATEGORIES),
        help=f"Comma-separated category list. Default: {','.join(DEFAULT_CATEGORIES)}.",
    )
    p.add_argument("--output-dir", default=str(OUTPUT_DIR),
                   help=f"Where to write the slice. Default: {OUTPUT_DIR}.")
    p.add_argument("--cache-dir", default=None,
                   help="HuggingFace cache dir. Default: HF default (~/.cache/huggingface).")
    p.add_argument("--skip-files", default="",
                   help="Comma-separated file list to skip (useful to resume).")
    return p.parse_args(argv)


def _require_deps() -> None:
    missing = []
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        missing.append("pyarrow")
    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        missing.append("huggingface_hub")
    if missing:
        raise RuntimeError(
            f"missing dependencies: {', '.join(missing)}. "
            f"Install: .venv/bin/pip install {' '.join(missing)}"
        )


def download_file_from_hf(filename: str, cache_dir: str | None) -> Path:
    """Download one file from the HF dataset repo. Returns local path."""
    from huggingface_hub import hf_hub_download
    log.info("downloading %s from %s", filename, HF_REPO_ID)
    local = hf_hub_download(
        repo_id=HF_REPO_ID,
        repo_type=HF_REPO_TYPE,
        filename=filename,
        cache_dir=cache_dir,
    )
    return Path(local)


def discover_category_column(parquet_path: Path) -> str:
    """Inspect markets.parquet schema and pick the most likely category column."""
    import pyarrow.parquet as pq
    schema = pq.read_schema(parquet_path)
    candidates = ("category", "tags", "market_type", "event_category", "event_slug")
    names_lower = {n.lower(): n for n in schema.names}
    for c in candidates:
        if c in names_lower:
            return names_lower[c]
    # Fall back to the first string-typed column that contains the word "category".
    for name in schema.names:
        if "category" in name.lower():
            return name
    raise RuntimeError(
        f"could not find a category column in {parquet_path}. "
        f"Schema: {schema.names}"
    )


def discover_market_id_column(parquet_path: Path) -> str:
    """Inspect schema and pick the most likely market_id column."""
    import pyarrow.parquet as pq
    schema = pq.read_schema(parquet_path)
    candidates = ("market_id", "condition_id", "market", "marketId", "conditionId")
    for c in candidates:
        if c in schema.names:
            return c
    for name in schema.names:
        if "market" in name.lower() and "id" in name.lower():
            return name
    raise RuntimeError(
        f"could not find a market_id column in {parquet_path}. Schema: {schema.names}"
    )


def filter_markets(markets_path: Path, categories: list[str]) -> tuple[Path, set[str]]:
    """Filter markets.parquet to target categories. Returns (output_path, market_id_set)."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    cat_col = discover_category_column(markets_path)
    mid_col = discover_market_id_column(markets_path)
    log.info("using category column: %s", cat_col)
    log.info("using market_id column: %s", mid_col)

    tbl = pq.read_table(markets_path, columns=None)
    cat_values = tbl.column(cat_col)
    # Lower-case compare to handle "Geopolitics" vs "geopolitics".
    lower = pc.utf8_lower(pc.cast(cat_values, pa.string()))
    target_lower = [c.lower() for c in categories]
    mask = pc.is_in(lower, value_set=pa.array(target_lower))
    filtered = tbl.filter(mask)
    log.info(
        "markets: %d total → %d matched categories %s",
        tbl.num_rows, filtered.num_rows, categories,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "markets.parquet"
    pq.write_table(filtered, out_path)
    mids = set(filtered.column(mid_col).to_pylist())
    # Normalize: cast all market_ids to string.
    mids = {str(m) for m in mids if m is not None}
    log.info("wrote %s (%d rows, %d unique market_ids)", out_path, filtered.num_rows, len(mids))
    return out_path, mids


def filter_secondary_file(
    input_path: Path, output_path: Path, mids: set[str], mid_col_candidates: tuple[str, ...]
) -> int:
    """Stream-filter a parquet by market_id membership, row-group by row-group."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    reader = pq.ParquetFile(input_path)
    schema = reader.schema_arrow
    mid_col = None
    names_lower = {n.lower(): n for n in schema.names}
    for cand in mid_col_candidates:
        if cand.lower() in names_lower:
            mid_col = names_lower[cand.lower()]
            break
    if mid_col is None:
        raise RuntimeError(
            f"could not find market_id column in {input_path}. "
            f"Looked for {mid_col_candidates}, schema has {schema.names}"
        )
    log.info("filtering %s on column %s (%d target market_ids)",
             input_path.name, mid_col, len(mids))

    mids_arr = pa.array(sorted(mids), type=pa.string())
    output_path.parent.mkdir(parents=True, exist_ok=True)

    writer = None
    rows_in = 0
    rows_out = 0
    try:
        for rg_idx in range(reader.num_row_groups):
            rg_tbl = reader.read_row_group(rg_idx)
            rows_in += rg_tbl.num_rows
            col = rg_tbl.column(mid_col)
            col_str = pc.cast(col, pa.string())
            mask = pc.is_in(col_str, value_set=mids_arr)
            filtered = rg_tbl.filter(mask)
            if filtered.num_rows == 0:
                continue
            if writer is None:
                writer = pq.ParquetWriter(output_path, filtered.schema)
            writer.write_table(filtered)
            rows_out += filtered.num_rows
            if rg_idx % 10 == 0:
                log.info("  row_group %d/%d  in=%d  out=%d",
                         rg_idx + 1, reader.num_row_groups, rows_in, rows_out)
    finally:
        if writer is not None:
            writer.close()

    log.info("wrote %s (%d/%d rows)", output_path, rows_out, rows_in)
    return rows_out


def write_meta(meta: dict, output_dir: Path) -> None:
    path = output_dir / "meta.json"
    with open(path, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    log.info("wrote %s", path)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = parse_args(argv)
    try:
        _require_deps()
    except RuntimeError as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 2

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    output_dir = Path(args.output_dir)
    skip = {s.strip() for s in args.skip_files.split(",") if s.strip()}

    print(f"\n=== SII-WANGZJ slice download ===")
    print(f"categories: {categories}")
    print(f"output_dir: {output_dir}")
    print(f"mode: {'EXECUTE' if args.execute else 'DRY-RUN (markets.parquet only)'}")
    print()

    # Step 1+2: always fetch + filter markets.parquet.
    markets_local = download_file_from_hf("markets.parquet", args.cache_dir)
    markets_out, mids = filter_markets(markets_local, categories)

    if not args.execute:
        print(f"\n=== DRY RUN complete. markets.parquet slice: {markets_out} "
              f"({len(mids)} market_ids). Re-run with --execute to pull "
              f"trades/users/quant rows. ===")
        return 0

    # Step 5: stream-filter the secondary files.
    secondary_mid_candidates = (
        "market_id", "conditionId", "condition_id", "market",
        "marketId", "id", "token_market_id",
    )
    meta_files: list[dict] = [
        {"name": "markets.parquet", "rows": len(mids), "path": str(markets_out)}
    ]
    for fname in FILES[1:]:
        if fname in skip:
            log.info("skipping %s (--skip-files)", fname)
            continue
        try:
            local = download_file_from_hf(fname, args.cache_dir)
        except Exception as e:
            log.exception("download failed for %s: %s", fname, e)
            continue
        out = output_dir / fname
        try:
            rows = filter_secondary_file(
                local, out, mids, mid_col_candidates=secondary_mid_candidates
            )
            meta_files.append({"name": fname, "rows": rows, "path": str(out)})
        except Exception as e:
            log.exception("filter failed for %s: %s", fname, e)

    meta = {
        "dataset": HF_REPO_ID,
        "categories": categories,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "files": meta_files,
        "unique_market_ids": len(mids),
    }
    write_meta(meta, output_dir)

    print(f"\n=== Slice complete. Total market_ids: {len(mids)} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
