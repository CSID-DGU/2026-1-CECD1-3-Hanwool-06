"""test_anomalies.csv → front/public/risk.json (위험도 패널용).

- 고객번호 키 9자리 0패딩(bills/stations 와 통일).
- 라이브 구간(2026-05-31~)만 담는다: 최신=기준일, 최근 N일=이력.
- 프론트가 pct(=residual/pred) 등은 직접 계산.
"""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SRC = HERE / "scripts" / "LightGBM_Model" / "results" / "test_anomalies.csv"
DST = HERE.parent.parent / "front" / "public" / "risk.json"
LIVE_FROM = "2026-05-31"

df = pd.read_csv(SRC, encoding="utf-8-sig")
df = df[df["날짜"] >= LIVE_FROM].sort_values(["고객번호", "날짜"])

out = {}
for cust, g in df.groupby("고객번호"):
    key = str(int(cust)).zfill(9)
    out[key] = [
        {
            "date": r.날짜,
            "actual": round(float(r.일사용량_톤), 1),
            "pred": round(float(r.pred_ton), 1),
            "residual": round(float(r.residual), 1),
            "z": round(float(r.z_score), 2),
            "severity": r.심각도,
            "dir": r.방향 if isinstance(r.방향, str) else "",
            "err": bool(r.data_error_candidate),
        }
        for r in g.itertuples(index=False)
    ]

DST.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
n = sum(len(v) for v in out.values())
print(f"{DST}: 고객번호 {len(out)}개 · {n}행 · {DST.stat().st_size/1024:.0f}KB")
