"""master(과거) + 라이브(water·ridership) → front/public/daily.json.

- 고객번호 키 9자리 0패딩.
- usage: master 일사용량_톤(~2026-04-30) + 라이브 water(05-31~). water는 역명키 → master로 고객번호 부여.
- ridership: master 총승객수 + 라이브 ridership(고객번호키).
- 전구간을 다 담는다(프론트는 선택일 기준 7일 윈도우로 표시).
"""
import glob
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MASTER = ROOT / "data" / "ml_dataset" / "master.csv"
# 일별 수집(GitHub Actions)이 daily-collect 브랜치에 쌓는 표준 위치
WATER = sorted(glob.glob(str(ROOT / "data" / "daily" / "water" / "*.csv")))
RIDE = sorted(glob.glob(str(ROOT / "data" / "daily" / "ridership" / "*.csv")))
DST = ROOT / "front" / "public" / "daily.json"

m = pd.read_csv(MASTER, encoding="utf-8-sig")
name2cust = m.drop_duplicates("역명", keep="last").set_index("역명")["고객번호"]

# ── usage = master + 라이브 water ──
usage = m[["고객번호", "날짜", "일사용량_톤"]].rename(columns={"일사용량_톤": "value"})
wf = []
for p in WATER:
    df = pd.read_csv(p, encoding="utf-8-sig").rename(columns={"일사용량(톤)": "value", "사용일": "날짜"})
    df["고객번호"] = df["역명"].map(name2cust)
    wf.append(df.dropna(subset=["고객번호"])[["고객번호", "날짜", "value"]])
usage = pd.concat([usage] + wf, ignore_index=True)
usage["고객번호"] = usage["고객번호"].astype(int)

# ── ridership = master + 라이브 ridership ──
ride = m[["고객번호", "날짜", "총승객수"]].rename(columns={"총승객수": "value"})
rf = [pd.read_csv(p, encoding="utf-8-sig")[["고객번호", "날짜", "총승객수"]].rename(columns={"총승객수": "value"}) for p in RIDE]
ride = pd.concat([ride] + rf, ignore_index=True)


def series(df, intify):
    df = df.drop_duplicates(["고객번호", "날짜"], keep="last").sort_values(["고객번호", "날짜"])
    out = {}
    for cust, g in df.groupby("고객번호"):
        key = str(int(cust)).zfill(9)
        out[key] = [{"date": d, "value": (int(round(v)) if intify else round(float(v), 1))}
                    for d, v in zip(g["날짜"], g["value"])]
    return out


usage_s, ride_s = series(usage, False), series(ride, True)
out = {}
for key in set(usage_s) | set(ride_s):
    out[key] = {"usage": usage_s.get(key, []), "ridership": ride_s.get(key, [])}

DST.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
nu = sum(len(v["usage"]) for v in out.values())
nr = sum(len(v["ridership"]) for v in out.values())
print(f"{DST}: 고객번호 {len(out)}개 · usage {nu}점 · ridership {nr}점 · {DST.stat().st_size/1024/1024:.2f}MB")
