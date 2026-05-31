#!/usr/bin/env python3
"""Combine all downloaded Seoul subway ridership CSVs into a single long file.

Inputs:
    Raw_data/seoul_ridership/raw/CARD_SUBWAY_MONTH_*.csv  (mixed encoding)
    Processed_data/Bill_Data/meter_match.csv              (for match validation)

Output:
    Processed_data/Daily_Data/ridership_long.csv         (한글 헤더, normalized)
    Processed_data/Daily_Data/ridership_match_report.json (매칭 진단)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from i121_postprocess_bills import parse_station_meter  # reuse


DEFAULT_RAW_DIR = PROJECT_ROOT / "Raw_data" / "승하차데이터"
DEFAULT_METER_MATCH = PROJECT_ROOT / "Processed_data" / "Bill_Data" / "meter_match.csv"
DEFAULT_OUT_CSV = PROJECT_ROOT / "Processed_data" / "승하차데이터" / "ridership_long.csv"
DEFAULT_REPORT = PROJECT_ROOT / "Processed_data" / "승하차데이터" / "ridership_match_report.json"


def resolve_korean_path(path: Path) -> Path:
    """Match a Korean path against actual filesystem entries (handles NFC vs NFD)."""
    if path.exists():
        return path
    parent = path.parent
    target_nfc = unicodedata.normalize("NFC", path.name)
    if not parent.exists():
        return path
    for n in os.listdir(parent):
        if unicodedata.normalize("NFC", n) == target_nfc:
            return parent / n
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--meter-match-csv", type=Path, default=DEFAULT_METER_MATCH)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--min-year", type=int, default=2015)
    return parser.parse_args()


RIDERSHIP_COLS = ["사용일자", "노선명", "역명", "승차총승객수", "하차총승객수", "등록일자"]


def read_ridership_csv(path: Path) -> pd.DataFrame:
    """Read a single ridership CSV; handle UTF-8-BOM vs EUC-KR + trailing comma.

    The CSVs have a trailing comma on data rows (`"...","20260404",""`) but
    not on the header. We explicitly declare an extra `_trail` column to swallow
    that empty trailing field, otherwise pandas mis-aligns columns and dates
    end up parsed as line names. Yearly files (e.g. 2020) also contain a few
    malformed rows with extra fields; we tolerate them via on_bad_lines='skip'.
    """
    last_error: Exception | None = None
    encodings = ("utf-8-sig", "euc-kr", "cp949")
    # try both with and without trailing column
    name_variants = [RIDERSHIP_COLS + ["_trail"], RIDERSHIP_COLS]
    for enc in encodings:
        for names in name_variants:
            try:
                df = pd.read_csv(
                    path,
                    encoding=enc,
                    names=names,
                    header=0,
                    on_bad_lines="skip",
                )
                if "역명" not in df.columns or "사용일자" not in df.columns:
                    continue
                # validate: 사용일자 should look like YYYYMMDD
                sample = df["사용일자"].dropna().astype(str).head(20)
                if sample.empty:
                    continue
                if not sample.str.match(r"^\d{8}$").all():
                    continue
                return df.drop(columns=["_trail"], errors="ignore")
            except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
                last_error = exc
                continue
    raise RuntimeError(f"failed to parse {path}: {last_error}")


def parse_ridership_line(value) -> int | None:
    if pd.isna(value):
        return None
    s = str(value).strip()
    m = re.match(r"^(\d+)호선$", s)
    return int(m.group(1)) if m else None


def normalize_ridership_station(name) -> str:
    """Ridership 역명에는 '역' 접미사가 없음. 우리 데이터와 매칭을 위해 '역' 추가."""
    if not isinstance(name, str):
        return ""
    base, _, _ = parse_station_meter(name + "역")
    return base


def main() -> int:
    args = parse_args()
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)

    raw_dir = resolve_korean_path(args.raw_dir)
    if not raw_dir.exists():
        raise SystemExit(f"raw dir not found: {args.raw_dir}")
    files = sorted(
        raw_dir / name
        for name in os.listdir(raw_dir)
        if unicodedata.normalize("NFC", name).startswith("CARD_SUBWAY_MONTH_")
        and unicodedata.normalize("NFC", name).endswith(".csv")
    )
    print(f"[1/4] reading {len(files)} ridership CSVs ...", flush=True)
    frames: list[pd.DataFrame] = []
    for f in files:
        df = read_ridership_csv(f)
        if "사용일자" not in df.columns:
            print(f"  SKIP {f.name}: missing 사용일자", flush=True)
            continue
        keep = df[["사용일자", "노선명", "역명", "승차총승객수", "하차총승객수"]].copy()
        frames.append(keep)
    combined = pd.concat(frames, ignore_index=True)
    print(f"  raw rows combined: {len(combined):,}", flush=True)

    print("[2/4] normalize / typing ...", flush=True)
    combined["사용일"] = pd.to_datetime(combined["사용일자"].astype(str), format="%Y%m%d", errors="coerce")
    combined = combined[combined["사용일"].notna()].copy()
    combined = combined[combined["사용일"].dt.year >= args.min_year].copy()
    combined["호선"] = combined["노선명"].map(parse_ridership_line).astype("Int64")
    combined["역명_원본"] = combined["역명"]
    combined["역명"] = combined["역명_원본"].map(normalize_ridership_station)
    combined["승차총승객수"] = pd.to_numeric(combined["승차총승객수"], errors="coerce").fillna(0).astype("Int64")
    combined["하차총승객수"] = pd.to_numeric(combined["하차총승객수"], errors="coerce").fillna(0).astype("Int64")
    combined["총승객수"] = combined["승차총승객수"] + combined["하차총승객수"]

    # Dedupe: same (사용일, 호선, 역명_원본) — first one wins (file later in time)
    before = len(combined)
    combined = (
        combined.sort_values(["사용일", "호선", "역명_원본"])
        .drop_duplicates(subset=["사용일", "호선", "역명_원본"], keep="last")
        .reset_index(drop=True)
    )
    dedupe_dropped = before - len(combined)

    print("[3/4] matching against our 80 meters + filtering ...", flush=True)
    mm = pd.read_csv(args.meter_match_csv, encoding="utf-8-sig", dtype={"고객번호": str})
    # Build a set of (역명_정규화, 호선) for ridership
    ridership_pairs = set(
        zip(
            combined["역명"].astype(str),
            combined["호선"].fillna(-1).astype(int).astype(int),
        )
    )

    def lookup(meter_station: str, meter_line) -> dict:
        line = None
        try:
            line = int(meter_line) if pd.notna(meter_line) else None
        except (ValueError, TypeError):
            line = None
        # Try (station, line); if no line specified, try any line for station
        if line is not None and (meter_station, line) in ridership_pairs:
            return {"matched": True, "match_type": "station_line", "matched_line": line}
        if line is None:
            for rs, rl in ridership_pairs:
                if rs == meter_station:
                    return {"matched": True, "match_type": "station_only", "matched_line": rl if rl != -1 else None}
        return {"matched": False, "match_type": None, "matched_line": None}

    match_rows = []
    keep_station_line: set[tuple[str, int]] = set()
    keep_station_any_line: set[str] = set()
    for _, row in mm.iterrows():
        result = lookup(row["역명"], row["호선"])
        match_rows.append(
            {
                "meter_id": row["고객번호"],
                "csv_name": row["일일CSV파일명"],
                "our_station": row["역명"],
                "our_line": row["호선"] if pd.notna(row["호선"]) else None,
                "usage_type": row["용도"],
                **result,
            }
        )
        if pd.notna(row["호선"]):
            try:
                keep_station_line.add((row["역명"], int(row["호선"])))
            except (ValueError, TypeError):
                keep_station_any_line.add(row["역명"])
        else:
            keep_station_any_line.add(row["역명"])

    match_df = pd.DataFrame(match_rows)
    matched_meters = int(match_df["matched"].sum())
    unmatched_meters = match_df[~match_df["matched"]][["csv_name", "our_station", "our_line"]].to_dict("records")

    print(f"  matched: {matched_meters} / {len(mm)}", flush=True)
    if unmatched_meters:
        print(f"  unmatched first 10:", flush=True)
        for u in unmatched_meters[:10]:
            print(f"    {u}", flush=True)

    line_int = combined["호선"].fillna(-1).astype(int).astype(int)
    filter_mask = combined["역명"].isin(keep_station_any_line) | combined.apply(
        lambda r: (r["역명"], -1 if pd.isna(r["호선"]) else int(r["호선"])) in keep_station_line,
        axis=1,
    )
    before_filter = len(combined)
    combined_filtered = combined[filter_mask].copy()
    after_filter = len(combined_filtered)
    print(f"  filter to our 80 stations: {before_filter:,} → {after_filter:,} rows", flush=True)

    print("[4/4] saving ridership_long.csv ...", flush=True)
    out_cols = ["사용일", "호선", "노선명", "역명", "역명_원본", "승차총승객수", "하차총승객수", "총승객수"]
    final = combined_filtered[out_cols].sort_values(["역명", "호선", "사용일"]).reset_index(drop=True)
    final["사용일"] = final["사용일"].dt.strftime("%Y-%m-%d")
    final.to_csv(args.out_csv, index=False, encoding="utf-8-sig")

    report = {
        "raw_files": len(files),
        "raw_rows_after_combine": int(before),
        "dedupe_dropped": int(dedupe_dropped),
        "rows_before_meter_filter": int(before_filter),
        "rows_after_meter_filter": int(after_filter),
        "final_rows": int(len(final)),
        "date_range": [str(final["사용일"].min()), str(final["사용일"].max())],
        "unique_stations": int(final["역명"].nunique()),
        "unique_lines": sorted([int(x) for x in final["호선"].dropna().unique()]),
        "meter_match": {
            "total_meters": int(len(mm)),
            "matched": matched_meters,
            "unmatched": len(mm) - matched_meters,
            "unmatched_examples": unmatched_meters[:20],
        },
    }
    args.report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"  rows: {len(final):,}  size: {args.out_csv.stat().st_size/1_000_000:.1f} MB")
    print(f"  → {args.out_csv.relative_to(PROJECT_ROOT)}")
    print(f"  → {args.report_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
