"""라이브 daily(water+ridership)를 ai_dataset 포맷 행으로 만들어 test.csv 뒤에 붙인다.

- 팀원 모델 코드/데이터는 안 건드림: 원본 test.csv 그대로 두고 my_test.csv 를 새로 씀.
- water 는 역명키 → ai_dataset 의 역명↔고객번호로 고객번호 부여.
- 승차/하차 분리값은 라이브에 없어 공란(NaN) → LightGBM 이 결측 처리.
"""
import glob
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
AI = HERE / "data" / "ai_dataset"
# 일별 수집(daily-collect 브랜치)이 쌓는 표준 위치 — build_daily_json 과 동일
WATER = sorted(glob.glob(str(ROOT / "data" / "daily" / "water" / "*.csv")))
RIDE = sorted(glob.glob(str(ROOT / "data" / "daily" / "ridership" / "*.csv")))
COLS = ["고객번호", "사업소명", "고지서_성명", "역명", "날짜",
        "승차총승객수", "하차총승객수", "총승객수", "일사용량_톤", "일유형", "요일"]
KDOW = ["월", "화", "수", "목", "금", "토", "일"]

test = pd.read_csv(AI / "test.csv", encoding="utf-8-sig")
meta = test.drop_duplicates("고객번호", keep="last").set_index("고객번호")[["사업소명", "고지서_성명", "역명"]]
name2cust = test.drop_duplicates("역명", keep="last").set_index("역명")["고객번호"]

# ── water: 역명 → 고객번호, 사용일 = 날짜, 일사용량 ──
wf = []
for p in WATER:
    df = pd.read_csv(p)
    df = df.rename(columns={"일사용량(톤)": "일사용량_톤", "사용일": "날짜"})
    wf.append(df[["역명", "날짜", "일사용량_톤"]])
water = pd.concat(wf, ignore_index=True)
unmapped = sorted(set(water["역명"]) - set(name2cust.index))
if unmapped:
    print("⚠️ 매핑 실패 water 역명:", unmapped)
water["고객번호"] = water["역명"].map(name2cust)
water = water.dropna(subset=["고객번호"])
water["고객번호"] = water["고객번호"].astype(int)
water = water[["고객번호", "날짜", "일사용량_톤"]]

# ── ridership: 고객번호 → 총승객수 ──
rf = []
for p in RIDE:
    df = pd.read_csv(p)
    rf.append(df[["고객번호", "날짜", "총승객수"]])
ride = pd.concat(rf, ignore_index=True)

# ── usage 기준 left join (사용량 있는 역만 위험도 대상) ──
live = water.merge(ride, on=["고객번호", "날짜"], how="left")
live = live.join(meta, on="고객번호")
live["승차총승객수"] = pd.NA
live["하차총승객수"] = pd.NA
dt = pd.to_datetime(live["날짜"])
live["요일"] = dt.dt.weekday.map(lambda i: KDOW[i])
live["일유형"] = pd.NA
live = live[COLS]

# 라이브가 test 범위와 겹치지 않게(과거 test 우선 아님 — 라이브가 최신이라 keep last)
out = pd.concat([test[COLS], live], ignore_index=True)
out = out.drop_duplicates(subset=["고객번호", "역명", "날짜"], keep="last").sort_values(["고객번호", "날짜"])
out.to_csv(HERE / "my_test.csv", index=False, encoding="utf-8-sig")

print(f"원본 test {len(test):,}행 + 라이브 {len(live):,}행 → my_test.csv {len(out):,}행")
print(f"라이브 날짜: {live['날짜'].min()} ~ {live['날짜'].max()} · 역 {live['고객번호'].nunique()}개")
print(f"라이브 승객결측: {live['총승객수'].isna().sum()}행 / 사용량결측: {live['일사용량_톤'].isna().sum()}행")
