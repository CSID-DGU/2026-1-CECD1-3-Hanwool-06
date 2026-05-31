"""
이상치 탐지기

과거 데이터(data/Processed_data/일일사용량.csv) + 수집된 daily CSV를 합쳐
역별로 STL 잔차 + Isolation Forest 로 이상치를 탐지하고 결과 DataFrame 을 반환합니다.

사용:
    python detector.py                   # 어제 날짜 탐지
    python detector.py 2026-05-05        # 특정 날짜 탐지
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.seasonal import STL

ROOT      = Path(__file__).resolve().parent.parent
HIST_PATH = ROOT / "data" / "processed_data" / "일일사용량.csv"
CAL_PATH  = ROOT / "data" / "processed_data" / "날짜인덱스.csv"
DAILY_DIR = ROOT / "data" / "daily"

MZ_WARN   = 2.5    # 주의 기준 (Modified Z-score)
MZ_ALERT  = 3.5    # 경고 기준
IF_THRESH = -0.05  # Isolation Forest 이상 판정 경계


def load_history() -> pd.DataFrame:
    hist = pd.read_csv(HIST_PATH, encoding="utf-8-sig", parse_dates=["검침일"])
    cal  = pd.read_csv(CAL_PATH,  encoding="utf-8-sig", parse_dates=["날짜"])
    hist = hist.merge(cal, left_on="검침일", right_on="날짜", how="left")
    return hist


def load_daily(target: date) -> pd.DataFrame:
    path = DAILY_DIR / f"{target}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} 없음. 먼저 scraper.py {target} 실행하세요."
        )
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df.rename(columns={"일사용량(톤)": "일사용량_톤"})
    df["검침일"] = pd.to_datetime(df["사용일"])
    return df[["역명", "검침일", "일사용량_톤"]]


def stl_residual(series: pd.Series) -> pd.Series:
    """일별 시계열에서 STL 잔차를 반환. 결측은 선형보간."""
    filled = series.interpolate(method="linear", limit_direction="both")
    res = STL(filled, period=7, robust=True).fit()
    return pd.Series(res.resid, index=series.index)


def modified_zscore(residuals: pd.Series) -> pd.Series:
    median = residuals.median()
    mad = (residuals - median).abs().median()
    if mad == 0:
        return pd.Series(np.zeros(len(residuals)), index=residuals.index)
    return 0.6745 * (residuals - median) / mad


def build_features(s: pd.DataFrame) -> pd.DataFrame:
    """
    Isolation Forest 에 넣을 특성 벡터.
    절대량 대신 '정규화된 상대량'을 씀 → 역별 스케일 차이 무시.
    """
    df = s.copy().sort_values("검침일")

    # 7일/30일 이동평균 대비 비율
    roll7  = df["일사용량_톤"].rolling(7,  min_periods=3).mean()
    roll30 = df["일사용량_톤"].rolling(30, min_periods=10).mean()
    df["ratio_7d"]  = df["일사용량_톤"] / roll7.replace(0, np.nan)
    df["ratio_30d"] = df["일사용량_톤"] / roll30.replace(0, np.nan)

    # 같은 요일 전주 대비 비율
    df["prev_week"] = df["일사용량_톤"].shift(7)
    df["ratio_wow"] = df["일사용량_톤"] / df["prev_week"].replace(0, np.nan)

    # 달력 특성
    df["month"]      = df["검침일"].dt.month
    df["dayofweek"]  = df["검침일"].dt.dayofweek
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
    df["is_holiday"] = df.get("공휴일", pd.Series(0, index=df.index)).fillna(0).astype(int)

    return df


def detect_station(history: pd.DataFrame, station: str,
                   target_date: date) -> dict | None:
    """
    단일 역의 target_date 에 대한 이상치 탐지 결과를 반환.
    데이터 부족 시 None.
    """
    s = (history[history["역명"] == station]
         .sort_values("검침일")
         .drop_duplicates("검침일")
         .set_index("검침일")
         .asfreq("D"))

    if s["일사용량_톤"].notna().sum() < 90:
        return None

    # 오늘 값 확인
    target_ts = pd.Timestamp(target_date)
    if target_ts not in s.index or pd.isna(s.loc[target_ts, "일사용량_톤"]):
        return None

    actual = float(s.loc[target_ts, "일사용량_톤"])

    # ── STL 잔차 기반 MZ score ──
    residuals = stl_residual(s["일사용량_톤"])
    mz_all    = modified_zscore(residuals)
    mz_today  = float(mz_all.get(target_ts, np.nan))

    # STL 기반 기댓값 범위 (잔차의 IQR → 역방향으로 정상 범위 추정)
    stl_res  = STL(s["일사용량_톤"].interpolate(method="linear", limit_direction="both"),
                   period=7, robust=True).fit()
    expected = float(stl_res.trend[target_ts] + stl_res.seasonal[target_ts])
    q1, q3   = residuals.quantile(0.25), residuals.quantile(0.75)
    iqr      = q3 - q1
    normal_lo = expected + (q1 - 1.5 * iqr)
    normal_hi = expected + (q3 + 1.5 * iqr)

    # ── Isolation Forest ──
    feat_df = build_features(s.reset_index())
    feat_cols = ["ratio_7d", "ratio_30d", "ratio_wow", "month", "dayofweek",
                 "is_weekend", "is_holiday"]
    feat_clean = feat_df[feat_cols].dropna()

    if len(feat_clean) < 30:
        if_score = np.nan
        if_flag  = False
    else:
        clf = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
        clf.fit(feat_clean)
        today_feat = feat_df.loc[feat_df["검침일"] == target_ts, feat_cols]
        if today_feat.dropna().empty:
            if_score, if_flag = np.nan, False
        else:
            if_score = float(clf.score_samples(today_feat.dropna())[0])
            if_flag  = if_score < IF_THRESH

    # ── 심각도 결정 ──
    stl_flag_warn  = abs(mz_today) >= MZ_WARN  if not np.isnan(mz_today) else False
    stl_flag_alert = abs(mz_today) >= MZ_ALERT if not np.isnan(mz_today) else False

    if stl_flag_alert and if_flag:
        severity = "경고"
    elif stl_flag_warn and if_flag:
        severity = "주의"
    elif stl_flag_alert or (stl_flag_warn and abs(mz_today) >= 3.0):
        severity = "주의"
    else:
        severity = "정상"

    direction = ""
    if severity != "정상":
        direction = "과다" if actual > expected else "과소"

    return {
        "역명":       station,
        "날짜":       str(target_date),
        "실제값(톤)":  round(actual, 1),
        "기댓값(톤)":  round(expected, 1),
        "정상범위":    [round(normal_lo, 1), round(normal_hi, 1)],
        "mz_score":   round(mz_today, 3) if not np.isnan(mz_today) else None,
        "if_score":   round(if_score,  4) if not np.isnan(if_score)  else None,
        "방향":        direction,
        "심각도":      severity,
    }


def detect(target_date: date | None = None) -> pd.DataFrame:
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    print(f"탐지 대상 날짜: {target_date}")

    history = load_history()
    daily   = load_daily(target_date)

    history = pd.concat(
        [history, daily[["역명", "검침일", "일사용량_톤"]]],
        ignore_index=True
    ).drop_duplicates(subset=["역명", "검침일"], keep="last")

    results = []
    for station in history["역명"].unique():
        res = detect_station(history, station, target_date)
        if res is None:
            continue
        results.append(res)
        if res["심각도"] != "정상":
            icon = "🔴" if res["심각도"] == "경고" else "🟡"
            print(f"  {icon} [{res['심각도']}] {station} "
                  f"실제 {res['실제값(톤)']}톤 / 기댓값 {res['기댓값(톤)']}톤 "
                  f"({res['방향']}, MZ={res['mz_score']})")

    result_df = pd.DataFrame(results)

    alerts = result_df[result_df["심각도"] != "정상"]
    print(f"\n경고 {(result_df['심각도']=='경고').sum()}건 / "
          f"주의 {(result_df['심각도']=='주의').sum()}건 / "
          f"정상 {(result_df['심각도']=='정상').sum()}건")
    return result_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="수도 사용량 이상치 탐지")
    parser.add_argument("date", nargs="?", help="탐지 날짜 YYYY-MM-DD (기본: 어제)")
    args = parser.parse_args()
    target = date.fromisoformat(args.date) if args.date else None
    detect(target)
