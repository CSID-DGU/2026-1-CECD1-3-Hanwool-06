#!/usr/bin/env python3
"""학습에 쓸 날짜 인덱스 (요일·주말·공휴일 + 한국 공휴일명) 생성.

3개 main CSV (daily_water_usage/water_bills/ridership)가 모두 겹치는 기간 (2022-01-02 ~ 2026-04-30)
1,580일에 대해 한 행씩 만든다.

Output: data/processed/date_index.csv  (UTF-8-BOM + 한글 헤더)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import holidays
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROCESSED = PROJECT_ROOT / "data" / "processed"
DEFAULT_OUT = PROCESSED / "date_index.csv"

DEFAULT_START = "2022-01-02"
DEFAULT_END = "2026-04-30"

DOW_KR = ["월", "화", "수", "목", "금", "토", "일"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=str, default=DEFAULT_START, help="YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=DEFAULT_END, help="YYYY-MM-DD")
    parser.add_argument("--out-path", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)
    years = list(range(start.year, end.year + 1))
    ko = holidays.KR(years=years, language="ko")

    rng = pd.date_range(start, end, freq="D")
    rows: list[dict] = []
    for d in rng:
        py_date = d.date()
        is_pub_holiday = py_date in ko
        name = str(ko.get(py_date)) if is_pub_holiday else ""
        dow = d.weekday()  # 0=월, 6=일
        is_weekend = 1 if dow >= 5 else 0
        rows.append(
            {
                "날짜": d.strftime("%Y-%m-%d"),
                "연도": d.year,
                "월": d.month,
                "일": d.day,
                "요일": DOW_KR[dow],
                "요일_숫자": dow,
                "주말": is_weekend,
                "공휴일": 1 if is_pub_holiday else 0,
                "공휴일명": name,
                "휴무일": 1 if (is_weekend or is_pub_holiday) else 0,
            }
        )

    df = pd.DataFrame(rows)

    # 징검다리: 평일이지만 그 전날 또는 다음날 모두 휴무일인 경우 (= 휴무일 사이에 낀 평일)
    prev_off = df["휴무일"].shift(1).fillna(0).astype(int)
    next_off = df["휴무일"].shift(-1).fillna(0).astype(int)
    is_bridge = (df["휴무일"] == 0) & (prev_off == 1) & (next_off == 1)
    df["징검다리"] = is_bridge.astype(int)

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_path, index=False, encoding="utf-8-sig")

    print(f"saved → {args.out_path.relative_to(PROJECT_ROOT)} ({len(df):,}일)")
    print(f"  기간: {df['날짜'].iloc[0]} ~ {df['날짜'].iloc[-1]}")
    print(f"  공휴일: {df['공휴일'].sum()}일")
    print(f"  주말: {df['주말'].sum()}일")
    print(f"  휴무일 (주말+공휴일): {df['휴무일'].sum()}일")
    print(f"  평일: {(df['휴무일']==0).sum()}일")
    print(f"  징검다리: {df['징검다리'].sum()}일")
    print()
    print("=== 공휴일 목록 (첫 10건) ===")
    print(df[df["공휴일"] == 1][["날짜", "요일", "공휴일명"]].head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
