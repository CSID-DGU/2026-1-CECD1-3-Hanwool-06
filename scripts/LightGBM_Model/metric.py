"""LightGBM 전용 평가/이상탐지 지표.

이상탐지 흐름(분위수 기반):
  1) score_residuals : 예측 잔차를 고객번호별 robust z-score 로 바꾼다.
  2) quantile_thresholds : 기준 분포(보통 valid)의 |z| 에서 q95/q99 임계값을 구한다.
  3) classify : 그 임계값으로 정상/주의/경고 + 방향(과다/과소)을 매긴다.
  → valid 의 |z| q95/q99 를 test 에도 그대로 적용하면, test 가 실제로 더 이상할 때
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
    """평균절대오차(톤). 극단치에 덜 민감(robust)."""
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    return float(np.mean(np.abs(actual - pred)))


def score_residuals(meta: pd.DataFrame, pred_ton: np.ndarray) -> pd.DataFrame:
    """예측 잔차와 고객번호별 robust z-score 까지만 계산(심각도 분류 전 단계)."""
    df = meta.copy()
    df["pred_ton"] = np.asarray(pred_ton, dtype=float).round(3)
    df["residual"] = (df["일사용량_톤"] - df["pred_ton"]).round(3)
    df["z_score"] = df.groupby("고객번호")["residual"].transform(_robust_zscore).round(3)
    # 명백한 데이터 오류(음수/비현실적 대용량)는 따로 표시 → RMSE 계산에서 분리할 때 사용
    df["data_error_candidate"] = (df["일사용량_톤"] < 0) | (df["일사용량_톤"] > 500)
    return df


def quantile_thresholds(z_score: pd.Series, warn_q: float, alert_q: float) -> tuple[float, float]:
    """|z| 분포에서 주의/경고 임계값을 분위수로 구한다 (예: warn_q=0.95, alert_q=0.99)."""
    abs_z = z_score.abs()
    return float(abs_z.quantile(warn_q)), float(abs_z.quantile(alert_q))


def classify(df: pd.DataFrame, warn_t: float, alert_t: float) -> pd.DataFrame:
    """|z| 가 임계값 이상이면 주의/경고로 분류하고 방향(과다/과소)을 매긴다."""
    out = df.copy()
    abs_z = out["z_score"].abs()
    out["심각도"] = np.where(abs_z >= alert_t, "경고",
                           np.where(abs_z >= warn_t, "주의", "정상"))
    out["방향"] = np.where(out["심각도"] == "정상", "",
                         np.where(out["z_score"] > 0, "과다", "과소"))
    return out


def summarize(anomalies: pd.DataFrame) -> dict:
    """RMSE 변형들과 이상탐지 건수를 요약한다.

    rmse_without_data_errors : 음수/비현실 대용량(데이터 오류)만 뺀 정직한 예측오차(헤드라인 권장).
    rmse_non_alert_diagnostic: 경고로 탐지된 날까지 뺀 값 — 진단용(낙관적, 헤드라인 비권장).
    """
    actual = anomalies["일사용량_톤"].to_numpy(dtype=float)
    pred = anomalies["pred_ton"].to_numpy(dtype=float)
    normal = (anomalies["심각도"] != "경고").to_numpy()
    clean = (~anomalies["data_error_candidate"]).to_numpy()
    normal_clean = normal & clean
    normal_only = (anomalies["심각도"] == "정상").to_numpy()   # 주의·경고 모두 제외

    return {
        "rmse": round(rmse(actual, pred), 4),
        "rmse_without_data_errors": round(rmse(actual[clean], pred[clean]), 4),
        "rmse_non_alert_diagnostic": round(rmse(actual[normal], pred[normal]), 4),
        "rmse_non_alert_clean_diagnostic": round(rmse(actual[normal_clean], pred[normal_clean]), 4),
        "rmse_normal_only": round(rmse(actual[normal_only], pred[normal_only]), 4),  # 정상 범주만
        "mae_normal_only": round(mae(actual[normal_only], pred[normal_only]), 4),
        "mae_all": round(mae(actual, pred), 4),
        "n_samples": int(len(anomalies)),
        "n_normal": int(normal.sum()),
        "n_normal_only": int(normal_only.sum()),
        "n_clean": int(clean.sum()),
        "경고": int((anomalies["심각도"] == "경고").sum()),
        "주의": int((anomalies["심각도"] == "주의").sum()),
        "과다": int((anomalies["방향"] == "과다").sum()),
        "과소": int((anomalies["방향"] == "과소").sum()),
        "data_error_candidate": int(anomalies["data_error_candidate"].sum()),
    }


def _robust_zscore(series: pd.Series) -> pd.Series:
    """(값-중앙값)/(1.4826*MAD). MAD 가 0 이면 표준편차로 대체."""
    median = series.median()
    mad = (series - median).abs().median()
    if mad == 0 or pd.isna(mad):
        std = series.std()
        if std == 0 or pd.isna(std):
            return pd.Series(0.0, index=series.index)
        return (series - median) / std
    return (series - median) / (1.4826 * mad)
