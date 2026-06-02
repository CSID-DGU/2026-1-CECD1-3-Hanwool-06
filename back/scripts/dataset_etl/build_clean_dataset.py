#!/usr/bin/env python3
"""정리: 모델 학습에 진짜 필요한 3개 깨끗한 CSV만 만든다.

출력 (모두 data/processed/ 루트, UTF-8-BOM + 한글 헤더):
  1) daily_water_usage.csv : 미터 × 날짜 → 일사용량
  2) water_bills.csv       : 미터 × 월 → 월사용량 (격월 청구는 2달로 분할해서 월별 통일)
  3) ridership.csv         : (역, 호선) × 날짜 → 승하차

읽는 컬럼만 잘라서 보관. 분석/이해를 위한 사람이 보는 데이터 형태.
"""

from __future__ import annotations

import argparse
import os
import unicodedata
from pathlib import Path

import pandas as pd


def resolve_korean_path(path: Path) -> Path:
    """Resolve a path whose Korean component may be in NFC or NFD form."""
    if path.exists():
        return path
    if not path.parent.exists():
        return path
    target_nfc = unicodedata.normalize("NFC", path.name)
    for n in os.listdir(path.parent):
        if unicodedata.normalize("NFC", n) == target_nfc:
            return path.parent / n
    return path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROCESSED = PROJECT_ROOT / "data" / "processed"

DEFAULT_DAILY_IN = PROCESSED / "daily_usage_long.csv"
DEFAULT_BILLS_IN = PROJECT_ROOT / "data" / "billing" / "bills_clean.csv"
DEFAULT_RIDERS_IN = PROCESSED / "ridership_long.csv"

OUT_DAILY = PROCESSED / "daily_water_usage.csv"
OUT_BILLS = PROCESSED / "water_bills.csv"
OUT_RIDERS = PROCESSED / "ridership.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-in", type=Path, default=DEFAULT_DAILY_IN)
    parser.add_argument("--bills-in", type=Path, default=DEFAULT_BILLS_IN)
    parser.add_argument("--riders-in", type=Path, default=DEFAULT_RIDERS_IN)
    return parser.parse_args()


def _load_meter_to_station() -> pd.DataFrame:
    """미터별 표시용 역명 만들기.

    Excel 3차검토의 '고지서_성명' 을 역명 자리에 사용 (미터별로 unique 한 라벨).
    예: 강동역(미사용지하수), 길동역(본선), 명일역장 등 시설/용도까지 구분됨.

    단, 고지서_성명이 중복인 케이스 (예: 두 미터 모두 '서울교통공사') 는
    자동으로 (정규역명, 용도) 부기를 붙여 disambiguate.
    """
    m = pd.read_csv(
        PROJECT_ROOT / "data" / "billing" / "mkey_station_map.csv",
        encoding="utf-8-sig",
        dtype={"고객번호": str},
    )[["고객번호", "역명", "고지서_성명", "용도"]].copy()
    counts = m["고지서_성명"].value_counts()

    def make_label(row: pd.Series) -> str:
        name = str(row["고지서_성명"])
        if counts.get(name, 0) > 1:
            suffix = str(row["역명"])
            if row["용도"] == "직원용":
                suffix = f"{suffix} 직원용"
            return f"{name}({suffix})"
        return name

    m["역명"] = m.apply(make_label, axis=1)
    return m[["고객번호", "역명"]]


def build_daily(daily_path: Path) -> pd.DataFrame:
    df = pd.read_csv(daily_path, encoding="utf-8-sig", dtype={"고객번호": str})
    df["검침일"] = pd.to_datetime(df["검침일"], errors="coerce")
    df = df.dropna(subset=["검침일"]).copy()
    df = df[df["일사용량_톤"].notna()].copy()
    # 음수 사용량 제외 (계량기 reset / 측정 오류)
    df = df[df["일사용량_톤"] >= 0].copy()
    # 비정상적 상한 outlier 제외 (>= 1000톤/일, 정상 max ~655톤. 3186톤=계량기 reset 추정)
    df = df[df["일사용량_톤"] < 1000].copy()
    out = df[["고객번호", "검침일", "일사용량_톤"]].copy()
    out = out.drop_duplicates(subset=["고객번호", "검침일"], keep="first")
    # 역명 join (사람이 보기 쉽게)
    out = out.merge(_load_meter_to_station(), on="고객번호", how="left")
    out = out[["고객번호", "역명", "검침일", "일사용량_톤"]]
    out = out.sort_values(["역명", "고객번호", "검침일"]).reset_index(drop=True)
    out["검침일"] = out["검침일"].dt.strftime("%Y-%m-%d")
    return out


def build_bills_bimonthly(bills_path: Path) -> pd.DataFrame:
    """모든 청구를 **2개월 단위**로 통일.

    - 원래 격월(2개월) 청구: 그대로 유지. period = (납기월-1, 납기월)
    - 원래 월별(1개월) 청구: 인접한 2개의 월별 청구를 합쳐 1개 격월 행으로 집계
                            (홀수월 청구는 다음달과, 짝수월 청구는 이전달과 짝지음)
    """
    b = pd.read_csv(bills_path, encoding="utf-8-sig", dtype={"고객번호": str})
    b["납기일"] = pd.to_datetime(b["납기일"], errors="coerce")
    b = b.dropna(subset=["납기일"]).sort_values(["고객번호", "납기일"]).reset_index(drop=True)
    b["총사용량_톤"] = pd.to_numeric(b["총사용량_톤"], errors="coerce").fillna(0.0)
    b["부과금액_원"] = pd.to_numeric(b["부과금액_원"], errors="coerce").fillna(0.0)

    # 역명을 다른 CSV들과 통일된 정규화 형태로 교체
    meter_norm = pd.read_csv(
        PROCESSED / "Bill_Data" / "meter_match.csv",
        encoding="utf-8-sig",
        dtype={"고객번호": str},
    )[["고객번호", "역명"]].rename(columns={"역명": "역명_정규화"})
    b = b.merge(meter_norm, on="고객번호", how="left")
    b["역명"] = b["역명_정규화"].fillna(b["역명"])
    b = b.drop(columns=["역명_정규화"])

    median_gaps = b.groupby("고객번호")["납기일"].apply(lambda s: s.diff().dt.days.median())
    mkey_cycle: dict[str, int] = {
        mkey: (1 if (gap is not None and not pd.isna(gap) and gap < 40) else 2)
        for mkey, gap in median_gaps.items()
    }

    def assign_bucket(napgi: pd.Timestamp, cycle: int) -> tuple[str, str]:
        if cycle == 2:
            start = napgi - pd.DateOffset(months=1)
            end = napgi
        else:
            if napgi.month % 2 == 0:
                start = napgi - pd.DateOffset(months=1)
                end = napgi
            else:
                start = napgi
                end = napgi + pd.DateOffset(months=1)
        return start.strftime("%Y-%m"), end.strftime("%Y-%m")

    bucket_rows: list[dict] = []
    for r in b.itertuples(index=False):
        cycle = mkey_cycle.get(r.고객번호, 2)
        start_ym, end_ym = assign_bucket(r.납기일, cycle)
        bucket_rows.append(
            {
                "고객번호": r.고객번호,
                "역명": r.역명,
                "영업사업소": r.영업사업소,
                "용도": r.용도,
                "시작연월": start_ym,
                "종료연월": end_ym,
                "원본_청구주기_개월": cycle,
                "사용량_톤": float(r.총사용량_톤),
                "부과금액_원": float(r.부과금액_원),
            }
        )
    df = pd.DataFrame(bucket_rows)

    agg = (
        df.groupby(
            ["고객번호", "역명", "영업사업소", "용도",
             "시작연월", "종료연월", "원본_청구주기_개월"],
            as_index=False,
            dropna=False,
        )
        .agg(
            청구건수=("사용량_톤", "count"),
            격월사용량_톤=("사용량_톤", "sum"),
            격월부과금액_원=("부과금액_원", "sum"),
        )
    )
    agg["포함월수"] = agg.apply(
        lambda r: 2 if (r["원본_청구주기_개월"] == 2 or r["청구건수"] == 2) else 1,
        axis=1,
    ).astype(int)

    # 역명 join (사람이 보기 쉽게)
    agg = agg.merge(_load_meter_to_station(), on="고객번호", how="left", suffixes=("", "_정답"))
    if "역명_정답" in agg.columns:
        agg["역명"] = agg["역명_정답"]
        agg = agg.drop(columns=["역명_정답"])
    out = agg[
        [
            "고객번호",
            "역명",
            "시작연월",
            "종료연월",
            "포함월수",
            "격월사용량_톤",
            "격월부과금액_원",
        ]
    ].sort_values(["역명", "고객번호", "시작연월"]).reset_index(drop=True)
    return out


def build_riders(riders_path: Path) -> pd.DataFrame:
    """승하차를 각 고객번호(미터)별로 expand. 같은 (역, 호선)의 여러 미터는 동일 승하차 공유."""
    r = pd.read_csv(riders_path, encoding="utf-8-sig")
    r["사용일"] = pd.to_datetime(r["사용일"], errors="coerce")
    r = r.dropna(subset=["사용일"]).copy()
    r["호선"] = pd.to_numeric(r["호선"], errors="coerce").astype("Int64")

    mm = pd.read_csv(
        PROCESSED / "Bill_Data" / "meter_match.csv",
        encoding="utf-8-sig",
        dtype={"고객번호": str},
    )
    mm["호선"] = pd.to_numeric(mm["호선"], errors="coerce").astype("Int64")

    pieces: list[pd.DataFrame] = []
    for _, m in mm.iterrows():
        station = m["역명"]
        line = m["호선"]
        if pd.notna(line):
            sub = r[(r["역명"] == station) & (r["호선"] == line)]
        else:
            # line=NaN 미터: 같은 역의 모든 호선 데이터를 (사용일) 기준으로 합산
            # (LLM 피드백: 운영 관점에서 sum 집계가 표준)
            sub = r[r["역명"] == station]
        if sub.empty:
            continue
        agg = (
            sub.groupby("사용일", as_index=False)[
                ["승차총승객수", "하차총승객수"]
            ].sum()
        )
        piece = pd.DataFrame(
            {
                "고객번호": m["고객번호"],
                "사용일": pd.to_datetime(agg["사용일"]),
                "승차총승객수": agg["승차총승객수"].to_numpy(),
                "하차총승객수": agg["하차총승객수"].to_numpy(),
            }
        )
        pieces.append(piece)

    out = pd.concat(pieces, ignore_index=True)
    # 안전망: 만약 같은 (고객번호, 사용일) 중복이 남아있으면 합산
    out = (
        out.groupby(["고객번호", "사용일"], as_index=False)[
            ["승차총승객수", "하차총승객수"]
        ].sum()
    )
    # 역명 join (사람이 보기 쉽게)
    out = out.merge(_load_meter_to_station(), on="고객번호", how="left")
    out = out[["고객번호", "역명", "사용일", "승차총승객수", "하차총승객수"]]
    out = out.sort_values(["역명", "고객번호", "사용일"]).reset_index(drop=True)
    out["사용일"] = out["사용일"].dt.strftime("%Y-%m-%d")
    return out


def main() -> int:
    args = parse_args()

    print("[1/3] daily_water_usage.csv ...", flush=True)
    daily = build_daily(args.daily_in)
    daily.to_csv(OUT_DAILY, index=False, encoding="utf-8-sig")
    print(f"  rows: {len(daily):,}  → {OUT_DAILY.relative_to(PROJECT_ROOT)}")

    print("[2/3] water_bills.csv (2개월 단위 통일) ...", flush=True)
    bills = build_bills_bimonthly(args.bills_in)
    bills.to_csv(OUT_BILLS, index=False, encoding="utf-8-sig")
    coverage_counts = bills["포함월수"].value_counts().sort_index().to_dict()
    print(f"  rows: {len(bills):,}  → {OUT_BILLS.relative_to(PROJECT_ROOT)}")
    print(f"  포함월수 분포: {coverage_counts}")

    print("[3/3] ridership.csv ...", flush=True)
    riders_parent = resolve_korean_path(args.riders_in.parent)
    riders_in = riders_parent / args.riders_in.name
    riders = build_riders(riders_in)
    riders.to_csv(OUT_RIDERS, index=False, encoding="utf-8-sig")
    print(f"  rows: {len(riders):,}  → {OUT_RIDERS.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
