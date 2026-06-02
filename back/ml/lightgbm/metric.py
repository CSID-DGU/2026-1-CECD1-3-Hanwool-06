"""평가 지표 + 이상탐지.

이상탐지 흐름:
  1) score_predictions : 예측오차(error_ton)를 역별 'deviation_score' 로 바꾼다.
       deviation_score = (오차 − 오차중앙값) / (1.4826 × 중앙값절대편차)
       → 평균/표준편차 대신 '중앙값' 기준이라 극단치 몇 개에 흔들리지 않는다.
  2) score_quantiles : 기준 분포(보통 valid)의 |deviation_score| 에서 q95/q99 임계값을 구한다.
  3) classify : 그 임계값으로 정상/주의/경고 + 방향(과다/과소)을 매긴다.
  → valid 의 q95/q99 를 test 에도 그대로 적용하면, test 가 실제로 더 이상할 때
    경고가 1% 보다 많이 잡혀 '이상 정도'를 반영한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rmse(actual: np.ndarray, pred: np.ndarray) -> float:
    """평균제곱근오차(톤). 큰 오차에 더 민감 → 극단치 1건에도 크게 튄다."""
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    return float(np.sqrt(np.mean((actual - pred) ** 2)))


def mae(actual: np.ndarray, pred: np.ndarray) -> float:
    """평균절대오차(톤). 극단치에 덜 민감."""
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    return float(np.mean(np.abs(actual - pred)))


def score_predictions(meta: pd.DataFrame, predicted_ton: np.ndarray) -> pd.DataFrame:
    """예측오차와 역별 deviation_score 까지만 계산(심각도 분류 전 단계)."""
    df = meta.copy()
    df["predicted_ton"] = np.asarray(predicted_ton, dtype=float).round(3)
    df["error_ton"] = (df["일사용량_톤"] - df["predicted_ton"]).round(3)   # 실제 − 예측
    df["deviation_score"] = df.groupby("고객번호")["error_ton"].transform(_deviation_score).round(3)
    # 명백한 데이터 오류(음수/비현실적 대용량)는 따로 표시 → RMSE 계산에서 분리할 때 사용
    df["likely_data_error"] = (df["일사용량_톤"] < 0) | (df["일사용량_톤"] > 500)
    return df


def score_quantiles(deviation_score: pd.Series, warn_q: float, alert_q: float) -> tuple[float, float]:
    """|deviation_score| 분포에서 주의/경고 임계값을 분위수로 구한다 (예: warn_q=0.95, alert_q=0.99)."""
    abs_score = deviation_score.abs()
    return float(abs_score.quantile(warn_q)), float(abs_score.quantile(alert_q))


def classify(df: pd.DataFrame, warn_threshold: float, alert_threshold: float) -> pd.DataFrame:
    """|deviation_score| 가 임계값 이상이면 주의/경고로 분류하고 방향(과다/과소)을 매긴다."""
    out = df.copy()
    abs_score = out["deviation_score"].abs()
    out["심각도"] = np.where(abs_score >= alert_threshold, "경고",
                           np.where(abs_score >= warn_threshold, "주의", "정상"))
    out["방향"] = np.where(out["심각도"] == "정상", "",
                         np.where(out["deviation_score"] > 0, "과다", "과소"))
    return out


def summarize(anomalies: pd.DataFrame) -> dict:
    """RMSE 변형들과 이상탐지 건수를 요약한다.

    rmse_without_data_errors : 음수/비현실 대용량(데이터 오류)만 뺀 정직한 예측오차(헤드라인 권장).
    rmse_excluding_alerts    : 경고로 탐지된 날까지 뺀 값 — 참고용(낙관적).
    rmse_normal_only         : 주의·경고 모두 뺀 '정상'만 — 정상 패턴 적합도.
    """
    actual = anomalies["일사용량_톤"].to_numpy(dtype=float)
    pred = anomalies["predicted_ton"].to_numpy(dtype=float)
    not_alert = (anomalies["심각도"] != "경고").to_numpy()
    no_error = (~anomalies["likely_data_error"]).to_numpy()
    normal_only = (anomalies["심각도"] == "정상").to_numpy()   # 주의·경고 모두 제외

    return {
        "rmse": round(rmse(actual, pred), 4),
        "rmse_without_data_errors": round(rmse(actual[no_error], pred[no_error]), 4),
        "rmse_excluding_alerts": round(rmse(actual[not_alert], pred[not_alert]), 4),
        "rmse_normal_only": round(rmse(actual[normal_only], pred[normal_only]), 4),
        "mae": round(mae(actual, pred), 4),
        "mae_normal_only": round(mae(actual[normal_only], pred[normal_only]), 4),
        "n_samples": int(len(anomalies)),
        "n_not_alert": int(not_alert.sum()),
        "n_normal_only": int(normal_only.sum()),
        "n_without_errors": int(no_error.sum()),
        "경고": int((anomalies["심각도"] == "경고").sum()),
        "주의": int((anomalies["심각도"] == "주의").sum()),
        "과다": int((anomalies["방향"] == "과다").sum()),
        "과소": int((anomalies["방향"] == "과소").sum()),
        "n_likely_data_error": int(anomalies["likely_data_error"].sum()),
    }


def _deviation_score(series: pd.Series) -> pd.Series:
    """(값 − 중앙값) / (1.4826 × 중앙값절대편차). 편차가 0 이면 표준편차로 대체.

    평균/표준편차 대신 중앙값 기준이라 극단치에 강건하다(이상치가 기준을 흔들지 않음).
    """
    median = series.median()
    median_abs_dev = (series - median).abs().median()
    if median_abs_dev == 0 or pd.isna(median_abs_dev):
        std = series.std()
        if std == 0 or pd.isna(std):
            return pd.Series(0.0, index=series.index)
        return (series - median) / std
    return (series - median) / (1.4826 * median_abs_dev)
