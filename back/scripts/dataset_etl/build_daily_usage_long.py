#!/usr/bin/env python3
"""Combine 80 per-meter daily CSVs into one long-format file with Korean headers.

Inputs:
    data/raw/daily_water_usage/*.csv  80 per-meter daily readings (raw)
    data/billing/meter_match.csv      mkey ↔ daily CSV 1-to-1 map (Korean cols)

Output:
    data/processed/daily_usage_long.csv  all meters concatenated, Korean cols,
                                         identifier columns joined in
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DAILY = ROOT / "data" / "raw" / "daily_water_usage"
DEFAULT_MATCH = ROOT / "data" / "billing" / "meter_match.csv"
DEFAULT_OUT = ROOT / "data" / "processed" / "daily_usage_long.csv"


COLUMN_RENAME: dict[str, str] = {
    "납기": "납기일",
    "사용일": "사용기간",
    "검침일자": "검침일",
    "지침값": "지침값",
    "일사용량(톤)": "일사용량_톤",
    "납기별 누적사용량(톤)": "납기별_누적사용량_톤",
}

FINAL_COLS: list[str] = [
    "일일CSV파일명", "고객번호", "역명", "호선", "용도",
    "검침일", "검침일_연도", "검침일_월",
    "일사용량_톤", "납기별_누적사용량_톤", "지침값",
    "납기일", "사용기간",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-dir", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--match-csv", type=Path, default=DEFAULT_MATCH)
    parser.add_argument("--out-path", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("=== 1) load meter_match.csv ===", flush=True)
    match = pd.read_csv(
        args.match_csv,
        encoding="utf-8-sig",
        dtype={"고객번호": str},
    )
    match["호선"] = pd.to_numeric(match["호선"], errors="coerce").astype("Int64")
    print(f"  rows: {len(match)}")
    lookup = match.set_index("일일CSV파일명")[["고객번호", "역명", "호선", "용도"]]

    print("\n=== 2) read and concat daily csvs ===", flush=True)
    files = sorted(args.daily_dir.glob("*.csv"))
    print(f"  found {len(files)} files")
    parts: list[pd.DataFrame] = []
    unmatched: list[str] = []
    for f in files:
        df = pd.read_csv(f, encoding="utf-8-sig")
        df = df.rename(columns=COLUMN_RENAME)
        stem = f.stem
        df.insert(0, "일일CSV파일명", stem)
        if stem in lookup.index:
            ident = lookup.loc[stem]
            df["고객번호"] = ident["고객번호"]
            df["역명"] = ident["역명"]
            df["호선"] = ident["호선"]
            df["용도"] = ident["용도"]
        else:
            unmatched.append(stem)
            df["고객번호"] = pd.NA
            df["역명"] = pd.NA
            df["호선"] = pd.NA
            df["용도"] = pd.NA
        parts.append(df)
    if unmatched:
        print(f"  WARNING: {len(unmatched)} csvs not in meter_match → {unmatched[:5]}")
    daily = pd.concat(parts, ignore_index=True)
    print(f"  combined rows: {len(daily):,}")

    print("\n=== 3) derive 검침일_연도 / 검침일_월 ===", flush=True)
    parsed = pd.to_datetime(daily["검침일"], errors="coerce")
    n_bad = int(parsed.isna().sum())
    if n_bad:
        print(f"  WARNING: {n_bad} rows have unparseable 검침일")
    daily["검침일_연도"] = parsed.dt.year.astype("Int64")
    daily["검침일_월"] = parsed.dt.month.astype("Int64")
    daily["검침일"] = parsed.dt.strftime("%Y-%m-%d")
    daily["호선"] = daily["호선"].astype("Int64")

    print("\n=== 4) reorder, sort, save ===", flush=True)
    daily = daily[[c for c in FINAL_COLS if c in daily.columns]]
    daily = daily.sort_values(
        ["역명", "호선", "용도", "검침일"], na_position="last"
    ).reset_index(drop=True)
    daily.to_csv(args.out_path, index=False, encoding="utf-8-sig")
    print(f"  rows: {len(daily):,}")
    print(f"  unique 일일CSV파일명: {daily['일일CSV파일명'].nunique()}")
    print(f"  unique 역명: {daily['역명'].nunique()}")
    print(f"  date range: {daily['검침일'].min()} ~ {daily['검침일'].max()}")
    print(f"  → {args.out_path.relative_to(ROOT)} "
          f"({args.out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
