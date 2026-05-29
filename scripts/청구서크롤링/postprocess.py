"""크롤링된 청구서 + Excel 검토표 → Processed_data/Bill_Data/ 정형화 (3단계)."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd


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


STATION_ALIASES: dict[str, str] = {
    "이수역": "총신대입구역",
}


def write_csv_kr(df: pd.DataFrame, path: Path) -> None:
    """UTF-8-BOM CSV, 한글 컬럼명."""
    df.rename(columns=COLUMN_RENAME_KR).to_csv(path, index=False, encoding="utf-8-sig")


def find_review_xlsx(raw_dir: Path) -> Path:
    """가장 최근 '검토' xlsx 찾기 (NFD 파일명 처리 포함)."""
    candidates: list[tuple[str, Path]] = []
    for name in os.listdir(raw_dir):
        nfc = unicodedata.normalize("NFC", name)
        if "검토" in nfc and name.endswith(".xlsx"):
            candidates.append((nfc, raw_dir / name))
    if not candidates:
        raise FileNotFoundError(f"{raw_dir} 에 '검토' xlsx 가 없습니다")
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


def _paren_handler(match: re.Match) -> str:
    inside = match.group(1).strip()
    return inside if inside == "역" else ""


def parse_station_meter(name) -> tuple[str, int | None, str | None]:
    """역명 라벨 → (역명_base, 호선, 용도) 분해."""
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
    """청구서 미터 ↔ 일일 CSV 1:1 매칭 (4단계 progressive fallback)."""
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


def _agg_stats(group: pd.Series) -> pd.Series:
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


def run(raw_dir: Path, bills_csv: Path, daily_dir: Path, out_dir: Path) -> Path:
    """크롤링 결과 + 검토 xlsx → Processed_data/Bill_Data/ 출력."""
    out_dir.mkdir(parents=True, exist_ok=True)

    print("  [post 1/8] 검토 xlsx 로드", flush=True)
    review_path = find_review_xlsx(raw_dir)
    review = load_review(review_path)
    print(f"    file: {review_path.name}  rows: {len(review)}  unique mkeys: {review['mkey'].nunique()}")

    print("  [post 2/8] 크롤링된 청구서 로드", flush=True)
    bills_raw = pd.read_csv(bills_csv, encoding="utf-8-sig", dtype={"mkey": str})
    crawled_mkeys = sorted(bills_raw["mkey"].unique())
    print(f"    bills_long rows: {len(bills_raw)}  unique mkeys: {len(crawled_mkeys)}")

    print("  [post 3/8] mkey_station_map.csv 생성", flush=True)
    map_full = review[
        [
            "mkey", "station", "office", "water_office", "bill_name",
            "usage_type", "review_dongguk", "review_planning",
        ]
    ].drop_duplicates(subset=["mkey"], keep="first")
    mkey_map = map_full[map_full["mkey"].isin(crawled_mkeys)].copy()
    unmapped = sorted(set(crawled_mkeys) - set(mkey_map["mkey"]))
    map_path = out_dir / "mkey_station_map.csv"
    write_csv_kr(mkey_map.sort_values(["station", "mkey"]), map_path)
    print(f"    mapped: {len(mkey_map)}/{len(crawled_mkeys)} → {map_path}")

    print("  [post 4/8] bills_clean.csv", flush=True)
    bills = bills_raw.merge(
        mkey_map[["mkey", "station", "office", "usage_type", "bill_name"]],
        on="mkey", how="left",
    )
    n_initial = len(bills)
    bills = bills[bills["gubun"] == "정기분"].copy()
    n_after_gubun = len(bills)
    bills = bills[bills["napgi"].notna() & bills["total_usage_ton"].notna()].copy()
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
        bills[slim_cols].sort_values(["station", "mkey", "napgi"]).reset_index(drop=True)
    )
    bills_clean_path = out_dir / "bills_clean.csv"
    write_csv_kr(bills_clean, bills_clean_path)
    print(f"    initial={n_initial} → 정기분={n_after_gubun} → notnull={n_after_null} → final={len(bills_clean)}")

    print("  [post 5/8] 2개월 청구서 → 캘린더 월 attribution", flush=True)
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
    print(f"    attribution rows: {len(attrib)}")

    print("  [post 6/8] station/mkey 월별 baseline", flush=True)
    station_bl = (
        attrib.dropna(subset=["station"])
        .groupby(["station", "calendar_month"])["monthly_avg_ton"]
        .apply(_agg_stats).unstack().reset_index()
        .sort_values(["station", "calendar_month"])
    )
    station_bl["iqr_ton"] = station_bl["p75_ton"] - station_bl["p25_ton"]
    write_csv_kr(station_bl, out_dir / "station_month_baseline.csv")

    mkey_bl = (
        attrib.groupby(["mkey", "station", "calendar_month"])["monthly_avg_ton"]
        .apply(_agg_stats).unstack().reset_index()
        .sort_values(["mkey", "calendar_month"])
    )
    mkey_bl["iqr_ton"] = mkey_bl["p75_ton"] - mkey_bl["p25_ton"]
    write_csv_kr(mkey_bl, out_dir / "mkey_month_baseline.csv")
    print(f"    station_bl={len(station_bl)} mkey_bl={len(mkey_bl)}")

    print("  [post 7/8] 미터 1:1 매칭 (청구서 ↔ 일일 CSV)", flush=True)
    daily_files = sorted(daily_dir.glob("*.csv"))
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
    write_csv_kr(meter_match, out_dir / "meter_match.csv")
    unmatched_bills = [bill_recs[i]["mkey"] for i in range(len(bill_recs)) if i not in matched_bi]
    unmatched_daily = [daily_recs[i]["csv_stem"] for i in range(len(daily_recs)) if i not in matched_di]
    print(f"    pairs: {len(meter_match)}  reasons: {dict(meter_match['match_reason'].value_counts())}")
    print(f"    unmatched bills: {len(unmatched_bills)}  unmatched daily: {len(unmatched_daily)}")

    print("  [post 8/8] daily CSV별 월별 baseline + report.json", flush=True)
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
    write_csv_kr(baseline_for_daily, out_dir / "daily_csv_baseline.csv")
    n_csvs_with_baseline = baseline_for_daily["daily_csv_stem"].nunique()

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
    report_path = out_dir / "postprocess_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"    → {report_path}")
    return report_path
