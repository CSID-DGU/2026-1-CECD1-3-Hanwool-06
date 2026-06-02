#!/usr/bin/env python3
"""Postprocess i121 crawled bills + review xlsx into training-ready data.

Inputs:
    data/raw/billing_i121/i121_bills/bills_long.csv        crawled bills (10K+ rows)
    data/raw/billing_i121/review/*.xlsx                    authoritative mkey↔역명 map
    data/raw/daily_water_usage/*.csv                       per-meter daily readings

Outputs (under data/billing/):
    mkey_station_map.csv          one row per crawled mkey
    bills_clean.csv               filtered, joined, slim bills
    station_month_baseline.csv    seasonal baseline at station level
    mkey_month_baseline.csv       seasonal baseline at meter level
    station_daily_match.csv       station ↔ daily-csv mapping
    postprocess_report.json       counts + diagnostics
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
RAW_ROOT = ROOT / "data" / "raw" / "billing_i121"
DEFAULT_RAW = RAW_ROOT / "review"
DEFAULT_BILLS = RAW_ROOT / "i121_bills" / "bills_long.csv"
DEFAULT_DAILY = ROOT / "data" / "raw" / "daily_water_usage"
DEFAULT_OUT = ROOT / "data" / "billing"


COLUMN_RENAME_KR: dict[str, str] = {
    "mkey": "고객번호",
    "station": "역명",
    "station_base": "역명",
    "bill_station_full": "역명_원본",
    "office": "영업사업소",
    "water_office": "수도사업소",
    "bill_name": "고지서_성명",
    "usage_type": "용도",
    "review_dongguk": "1차검토_동국대",
    "review_planning": "2차검토_영업계획처",
    "daily_csv_stem": "일일CSV파일명",
    "line": "호선",
    "match_reason": "매칭근거",
    "napgi": "납기일",
    "napgi_year": "납기_연도",
    "napgi_month": "납기_월",
    "napgi_year_month": "납기_연월",
    "gubun": "구분",
    "sunap_status": "수납상태",
    "total_usage_ton": "총사용량_톤",
    "monthly_avg_ton": "월평균사용량_톤",
    "bugwa_amount_won": "부과금액_원",
    "calendar_month": "월",
    "n_obs": "관측수",
    "median_ton": "중간값_톤",
    "mean_ton": "평균_톤",
    "p25_ton": "25분위_톤",
    "p75_ton": "75분위_톤",
    "std_ton": "표준편차_톤",
    "iqr_ton": "IQR_톤",
}


def write_csv_kr(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame as UTF-8-BOM CSV with columns renamed to Korean."""
    df.rename(columns=COLUMN_RENAME_KR).to_csv(
        path, index=False, encoding="utf-8-sig"
    )


def find_review_xlsx(raw_dir: Path) -> Path:
    """Locate the most recent 검토 xlsx (NFD filenames OK)."""
    candidates: list[tuple[str, Path]] = []
    for name in os.listdir(raw_dir):
        nfc = unicodedata.normalize("NFC", name)
        if "검토" in nfc and name.endswith(".xlsx"):
            candidates.append((nfc, raw_dir / name))
    if not candidates:
        raise FileNotFoundError(f"no 검토 xlsx found in {raw_dir}")
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def load_review(xlsx_path: Path) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, sheet_name="수도요금 고지서 정보", header=3)
    df = df.dropna(how="all")
    df = df.rename(
        columns={
            "사업소명": "office",
            "역명": "station",
            "고객 번호": "mkey_raw",
            "수도 사업소 명": "water_office",
            "고지서상 성명": "bill_name",
            "1차 검토(동국대)": "review_dongguk",
            "2차 검토(영업계획처)": "review_planning",
            "용도 표기": "usage_type",
        }
    )

    def to_mkey(v) -> str | None:
        try:
            n = int(v)
        except (TypeError, ValueError):
            return None
        return f"{n:09d}"

    df["mkey"] = df["mkey_raw"].map(to_mkey)
    df = df[df["mkey"].notna()].copy()
    return df


STATION_ALIASES: dict[str, str] = {
    "이수역": "총신대입구역",
}


def _paren_handler(match: re.Match) -> str:
    """Keep parens content only when it IS the '역' marker itself.

    '(역)' → keep '역' (e.g. '동묘앞(역)' → '동묘앞역')
    '(무역센터)' / '(능동)' / '(강동구민회관앞)' → drop entirely
    """
    inside = match.group(1).strip()
    return inside if inside == "역" else ""


def parse_station_meter(name) -> tuple[str, int | None, str | None]:
    """Parse a station label into (station_base, line_no, usage_type).

    Only treats a digit as a line number when it sits next to the trailing '역'
    or at the very end of the name. Middle digits (e.g. '을지로3가') are kept as
    part of the station base.

      '동대문역사문화공원역(2호선)' -> ('동대문역사문화공원역', 2, None)
      '동대문역사문화공원역2'      -> ('동대문역사문화공원역', 2, None)
      '시청1역' / '시청역1'         -> ('시청역', 1, None)
      '을지로3가역(2호선)'          -> ('을지로3가역', 2, None)
      '을지로3가역2'                -> ('을지로3가역', 2, None)
      '보문역-직원용'               -> ('보문역', None, '직원용')
      '이수(총신대입구)역(4호선)'   -> ('총신대입구역', 4, None)   # alias
      '굽은다리(강동구민회관앞)역'   -> ('굽은다리역', None, None)
      '동묘앞(역)'                  -> ('동묘앞역', None, None)
    """
    if not isinstance(name, str):
        return ("", None, None)
    name = name.strip()
    usage: str | None = None
    m = re.search(r"-([가-힣]+용)$", name)
    if m:
        usage = m.group(1)
        name = name[: m.start()]
    line: int | None = None
    m = re.search(r"\((\d+)호선\)", name)
    if m:
        line = int(m.group(1))
        name = name[: m.start()] + name[m.end():]
    name = re.sub(r"\(([^)]*)\)", _paren_handler, name)
    if line is None:
        m = re.search(r"(\d+)역$", name)
        if m:
            line = int(m.group(1))
            name = name[: m.start()] + "역"
    if line is None:
        m = re.search(r"(\d+)$", name)
        if m:
            line = int(m.group(1))
            name = name[: m.start()]
    name = re.sub(r"\s+", "", name)
    if name and not name.endswith("역"):
        name = name + "역"
    name = STATION_ALIASES.get(name, name)
    return (name, line, usage)


def match_meter_level(
    bill_recs: list[dict], daily_recs: list[dict]
) -> list[tuple[int, int, str]]:
    """1-to-1 match by (station_base, line, usage_type) with progressive fallback.

    Pass order:
      1) exact (station + line + usage)
      2) (station + line)
      3) (station + usage)
      4) station alone, only when exactly 1 candidate remains on each side
    """
    from collections import defaultdict

    matches: list[tuple[int, int, str]] = []
    used_daily: set[int] = set()
    matched_bill: set[int] = set()

    def try_pass(predicate, reason: str) -> None:
        for bi, b in enumerate(bill_recs):
            if bi in matched_bill:
                continue
            for di, d in enumerate(daily_recs):
                if di in used_daily:
                    continue
                if b["station_base"] != d["station_base"]:
                    continue
                if predicate(b, d):
                    matches.append((bi, di, reason))
                    matched_bill.add(bi)
                    used_daily.add(di)
                    break

    try_pass(
        lambda b, d: b["line"] == d["line"] and b["usage_type"] == d["usage_type"],
        "exact",
    )
    try_pass(
        lambda b, d: b["line"] is not None and b["line"] == d["line"],
        "line",
    )
    try_pass(
        lambda b, d: b["usage_type"] is not None and b["usage_type"] == d["usage_type"],
        "usage",
    )

    bill_rem: dict[str, list[int]] = defaultdict(list)
    daily_rem: dict[str, list[int]] = defaultdict(list)
    for bi, b in enumerate(bill_recs):
        if bi not in matched_bill:
            bill_rem[b["station_base"]].append(bi)
    for di, d in enumerate(daily_recs):
        if di not in used_daily:
            daily_rem[d["station_base"]].append(di)
    for station in list(bill_rem):
        if len(bill_rem[station]) == 1 and len(daily_rem.get(station, [])) == 1:
            bi = bill_rem[station][0]
            di = daily_rem[station][0]
            matches.append((bi, di, "station_only"))
            matched_bill.add(bi)
            used_daily.add(di)
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--bills-csv", type=Path, default=DEFAULT_BILLS)
    parser.add_argument("--daily-dir", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=== 1) load review xlsx ===", flush=True)
    review_path = find_review_xlsx(args.raw_dir)
    review = load_review(review_path)
    print(f"  review file:   {review_path.name}")
    print(f"  review rows:   {len(review)}  unique mkeys: {review['mkey'].nunique()}")

    print("\n=== 2) load crawled bills ===", flush=True)
    bills_raw = pd.read_csv(args.bills_csv, encoding="utf-8-sig", dtype={"mkey": str})
    crawled_mkeys = sorted(bills_raw["mkey"].unique())
    print(f"  bills_long rows: {len(bills_raw)}  unique mkeys: {len(crawled_mkeys)}")

    print("\n=== 3) build mkey_station_map.csv ===", flush=True)
    map_full = review[
        ["mkey", "station", "office", "water_office", "bill_name",
         "usage_type", "review_dongguk", "review_planning"]
    ].drop_duplicates(subset=["mkey"], keep="first")
    mkey_map = map_full[map_full["mkey"].isin(crawled_mkeys)].copy()
    unmapped = sorted(set(crawled_mkeys) - set(mkey_map["mkey"]))
    print(f"  mapped:   {len(mkey_map)} / {len(crawled_mkeys)}")
    print(f"  unmapped: {len(unmapped)} {unmapped[:5]}")
    map_path = args.out_dir / "mkey_station_map.csv"
    write_csv_kr(mkey_map.sort_values(["station", "mkey"]), map_path)
    print(f"  → {map_path.relative_to(ROOT)}")

    print("\n=== 4) clean bills_long → bills_clean ===", flush=True)
    bills = bills_raw.merge(
        mkey_map[["mkey", "station", "office", "usage_type", "bill_name"]],
        on="mkey",
        how="left",
    )
    n_initial = len(bills)
    bills = bills[bills["gubun"] == "정기분"].copy()
    n_after_gubun = len(bills)
    bills = bills[bills["napgi"].notna()].copy()
    bills = bills[bills["total_usage_ton"].notna()].copy()
    n_after_null = len(bills)
    bills["napgi_date"] = pd.to_datetime(bills["napgi"], errors="coerce")
    bills = bills[bills["napgi_date"].notna()].copy()
    bills["napgi_year"] = bills["napgi_date"].dt.year.astype(int)
    bills["napgi_month"] = bills["napgi_date"].dt.month.astype(int)
    bills["napgi_year_month"] = bills["napgi_date"].dt.strftime("%Y-%m")
    bills["total_usage_ton"] = bills["total_usage_ton"].astype(float)
    bills["bugwa_amount_won"] = bills["bugwa_amount_won"].astype(float)
    bills["monthly_avg_ton"] = bills["total_usage_ton"] / 2.0
    slim_cols = [
        "mkey", "station", "office", "usage_type", "bill_name",
        "napgi", "napgi_year", "napgi_month", "napgi_year_month",
        "gubun", "sunap_status",
        "total_usage_ton", "monthly_avg_ton", "bugwa_amount_won",
    ]
    bills_clean = (
        bills[slim_cols]
        .sort_values(["station", "mkey", "napgi"])
        .reset_index(drop=True)
    )
    bills_clean_path = args.out_dir / "bills_clean.csv"
    write_csv_kr(bills_clean, bills_clean_path)
    print(f"  rows: initial={n_initial}  after gubun=='정기분'={n_after_gubun}  "
          f"after non-null filter={n_after_null}  final={len(bills_clean)}")
    print(f"  → {bills_clean_path.relative_to(ROOT)}")

    print("\n=== 5) attribute bi-monthly bills to calendar months ===", flush=True)
    attrib_records: list[dict] = []
    for row in bills_clean.itertuples():
        if pd.isna(row.total_usage_ton) or row.total_usage_ton <= 0:
            continue
        m1 = int(row.napgi_month)
        m0 = m1 - 1 if m1 > 1 else 12
        per_month = row.monthly_avg_ton
        for m in (m0, m1):
            attrib_records.append(
                {
                    "mkey": row.mkey,
                    "station": row.station,
                    "calendar_month": m,
                    "monthly_avg_ton": per_month,
                }
            )
    attrib = pd.DataFrame(attrib_records)
    print(f"  attribution rows: {len(attrib)}  "
          f"(non-positive bills skipped: "
          f"{len(bills_clean) - (len(attrib) // 2)})")

    print("\n=== 6) build station_month_baseline + mkey_month_baseline ===", flush=True)
    def agg_stats(group: pd.Series) -> pd.Series:
        s = group.dropna()
        return pd.Series(
            {
                "n_obs": int(s.count()),
                "median_ton": float(s.median()) if len(s) else float("nan"),
                "mean_ton": float(s.mean()) if len(s) else float("nan"),
                "p25_ton": float(s.quantile(0.25)) if len(s) else float("nan"),
                "p75_ton": float(s.quantile(0.75)) if len(s) else float("nan"),
                "std_ton": float(s.std()) if len(s) > 1 else 0.0,
            }
        )

    station_bl = (
        attrib.dropna(subset=["station"])
        .groupby(["station", "calendar_month"])["monthly_avg_ton"]
        .apply(agg_stats)
        .unstack()
        .reset_index()
        .sort_values(["station", "calendar_month"])
    )
    station_bl["iqr_ton"] = station_bl["p75_ton"] - station_bl["p25_ton"]
    station_bl_path = args.out_dir / "station_month_baseline.csv"
    write_csv_kr(station_bl, station_bl_path)
    print(f"  station_month_baseline rows: {len(station_bl)}")
    print(f"  → {station_bl_path.relative_to(ROOT)}")

    mkey_bl = (
        attrib.groupby(["mkey", "station", "calendar_month"])["monthly_avg_ton"]
        .apply(agg_stats)
        .unstack()
        .reset_index()
        .sort_values(["mkey", "calendar_month"])
    )
    mkey_bl["iqr_ton"] = mkey_bl["p75_ton"] - mkey_bl["p25_ton"]
    mkey_bl_path = args.out_dir / "mkey_month_baseline.csv"
    write_csv_kr(mkey_bl, mkey_bl_path)
    print(f"  mkey_month_baseline rows: {len(mkey_bl)}")
    print(f"  → {mkey_bl_path.relative_to(ROOT)}")

    print("\n=== 7) meter-level match: bill mkey ↔ daily csv (1-to-1) ===", flush=True)
    daily_files = sorted(args.daily_dir.glob("*.csv"))

    bill_recs: list[dict] = []
    for row in mkey_map.itertuples():
        station_base, line, usage_from_name = parse_station_meter(row.station)
        usage_type = row.usage_type if pd.notna(row.usage_type) else usage_from_name
        bill_recs.append(
            {
                "mkey": row.mkey,
                "station_full": row.station,
                "station_base": station_base,
                "line": line,
                "usage_type": usage_type,
            }
        )

    daily_recs: list[dict] = []
    for f in daily_files:
        station_base, line, usage = parse_station_meter(f.stem)
        daily_recs.append(
            {
                "csv_stem": f.stem,
                "station_base": station_base,
                "line": line,
                "usage_type": usage,
            }
        )

    pairs = match_meter_level(bill_recs, daily_recs)
    matched_bi: set[int] = {bi for bi, _, _ in pairs}
    matched_di: set[int] = {di for _, di, _ in pairs}

    meter_rows: list[dict] = []
    for bi, di, reason in pairs:
        b = bill_recs[bi]
        d = daily_recs[di]
        meter_rows.append(
            {
                "mkey": b["mkey"],
                "daily_csv_stem": d["csv_stem"],
                "station_base": b["station_base"],
                "line": b["line"] if b["line"] is not None else d["line"],
                "usage_type": b["usage_type"] or d["usage_type"],
                "bill_station_full": b["station_full"],
                "match_reason": reason,
            }
        )
    meter_match = pd.DataFrame(meter_rows).sort_values(
        ["station_base", "line", "usage_type"], na_position="last"
    )
    meter_match_path = args.out_dir / "meter_match.csv"
    write_csv_kr(meter_match, meter_match_path)

    unmatched_bills = [
        bill_recs[i]["mkey"] for i in range(len(bill_recs)) if i not in matched_bi
    ]
    unmatched_daily = [
        daily_recs[i]["csv_stem"]
        for i in range(len(daily_recs))
        if i not in matched_di
    ]
    print(f"  bill mkeys: {len(bill_recs)}  daily csvs: {len(daily_recs)}")
    print(f"  matched (1-to-1): {len(meter_match)}")
    print(f"  match reasons: {dict(meter_match['match_reason'].value_counts())}")
    print(f"  unmatched bill mkeys: {len(unmatched_bills)} → {unmatched_bills[:5]}")
    print(f"  unmatched daily csvs: {len(unmatched_daily)} → {unmatched_daily[:5]}")
    print(f"  → {meter_match_path.relative_to(ROOT)}")

    print("\n=== 7.5) per-daily-csv monthly baseline ===", flush=True)
    baseline_for_daily = meter_match[
        ["daily_csv_stem", "mkey", "station_base", "line", "usage_type"]
    ].merge(mkey_bl, on="mkey", how="left")
    baseline_cols = [
        "daily_csv_stem", "mkey", "station_base", "line", "usage_type",
        "calendar_month", "n_obs",
        "median_ton", "mean_ton", "p25_ton", "p75_ton", "std_ton", "iqr_ton",
    ]
    baseline_for_daily = baseline_for_daily[baseline_cols].sort_values(
        ["daily_csv_stem", "calendar_month"]
    )
    baseline_for_daily_path = args.out_dir / "daily_csv_baseline.csv"
    write_csv_kr(baseline_for_daily, baseline_for_daily_path)
    n_csvs_with_baseline = baseline_for_daily["daily_csv_stem"].nunique()
    print(
        f"  rows: {len(baseline_for_daily)} "
        f"({n_csvs_with_baseline} daily csvs × 12 months)"
    )
    print(f"  → {baseline_for_daily_path.relative_to(ROOT)}")

    print("\n=== 8) write report ===", flush=True)
    report = {
        "review_xlsx": unicodedata.normalize("NFC", review_path.name),
        "review_total_rows_with_mkey": int(len(review)),
        "review_unique_mkeys": int(review["mkey"].nunique()),
        "crawled_mkeys": int(len(crawled_mkeys)),
        "mkey_station_mapped": int(len(mkey_map)),
        "mkey_unmapped_examples": unmapped[:10],
        "bills_initial": int(n_initial),
        "bills_after_gubun_filter": int(n_after_gubun),
        "bills_after_null_filter": int(n_after_null),
        "bills_clean_final": int(len(bills_clean)),
        "bills_clean_stations": int(bills_clean["station"].nunique()),
        "station_month_baseline_rows": int(len(station_bl)),
        "mkey_month_baseline_rows": int(len(mkey_bl)),
        "daily_csvs": int(len(daily_files)),
        "meter_match_pairs": int(len(meter_match)),
        "meter_match_reasons": {
            k: int(v) for k, v in meter_match["match_reason"].value_counts().items()
        },
        "unmatched_bill_mkeys": unmatched_bills,
        "unmatched_daily_csvs": unmatched_daily,
        "daily_csv_baseline_rows": int(len(baseline_for_daily)),
        "daily_csvs_with_baseline": int(n_csvs_with_baseline),
    }
    report_path = args.out_dir / "postprocess_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  → {report_path.relative_to(ROOT)}")
    print("\n=== DONE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
