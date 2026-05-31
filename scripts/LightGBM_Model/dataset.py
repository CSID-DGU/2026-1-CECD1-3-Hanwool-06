"""LightGBM 전용 데이터셋/피처 파이프라인.

이 모듈은 상위 공용 코드를 쓰지 않고 LightGBM 폴더 안에서 독립적으로 동작한다.
시간 순서가 있는 일별 수도 사용량 예측 문제이므로, 피처는 모두 해당 날짜 이전에
알 수 있는 값만 사용한다. 최종 test 모델은 train+valid를 과거 학습 구간으로 사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


TARGET = "일사용량_톤"   # 예측 타겟 컬럼명


@dataclass
class PreparedData:
    """피처 생성이 끝난 데이터를 담는 묶음.

    frame            : 전체 행(train/valid/test) + 모든 피처가 들어있는 DataFrame
    feature_cols     : 모델 입력으로 쓸 피처 컬럼 이름들
    categorical_cols : 그중 범주형으로 다룰 컬럼들 (LightGBM 이 직접 처리)
    """
    frame: pd.DataFrame
    feature_cols: list[str]
    categorical_cols: list[str]


def prepare_data(cfg: dict, fit_splits: tuple[str, ...]) -> PreparedData:
    """CSV 로딩부터 피처 생성까지 수행한다.

    fit_splits는 학습에 허용된 과거 split이다. train 평가용 valid 모델은 ("train",),
    최종 test 모델은 ("train", "valid")를 사용한다.
    """
    df = _load_ai_splits(cfg)
    df = _merge_calendar(df, cfg)
    df = _merge_bill_baseline(df, cfg)
    df = _add_time_features(df)
    df = _add_lag_rolling_features(df, cfg)
    df = _add_fit_period_statistics(df, fit_splits)
    df = _finalize_missing_values(df)

    categorical_cols = ["고객번호", "사업소명", "역명", "고지서_성명"]
    for col in categorical_cols:
        df[col] = df[col].astype("category")

    exclude = {"split", "날짜", TARGET}
    feature_cols = [c for c in df.columns if c not in exclude]
    for col in feature_cols:
        if col not in categorical_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)

    return PreparedData(df.copy(), feature_cols, categorical_cols)


def training_mask(df: pd.DataFrame, splits: tuple[str, ...], cfg: dict) -> pd.Series:
    """학습에 사용할 row mask. 과거 split 중 명백한 오류/극단값은 제외한다."""
    mask = df["split"].isin(splits)
    keep = pd.Series(False, index=df.index)
    k = float(cfg["features"]["outlier_iqr_k"])
    drop_negative = bool(cfg["features"]["drop_negative"])
    for _, idx in df[mask].groupby("고객번호").groups.items():
        values = df.loc[idx, TARGET]
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - k * iqr, q3 + k * iqr
        ok = (values >= lo) & (values <= hi)
        if drop_negative:
            ok = ok & (values >= 0)
        keep.loc[idx] = ok
    return keep


def split_xy(prepared: PreparedData, mask: pd.Series):
    """mask 가 True 인 행만 골라 학습용 (X 피처, y 타겟) 으로 나눈다."""
    df = prepared.frame.loc[mask]
    X = df[prepared.feature_cols]
    y = df[TARGET].astype(float)
    return X, y


def split_meta(prepared: PreparedData, split: str) -> pd.DataFrame:
    """특정 split(valid/test)의 식별·실측 정보(고객번호·역명·날짜·실제사용량)만 뽑는다."""
    cols = ["고객번호", "역명", "날짜", TARGET]
    return prepared.frame.loc[prepared.frame["split"] == split, cols].reset_index(drop=True)


def split_features(prepared: PreparedData, split: str) -> pd.DataFrame:
    """특정 split(valid/test)의 피처 행렬 X 만 뽑는다 (예측 입력용)."""
    return prepared.frame.loc[prepared.frame["split"] == split, prepared.feature_cols].reset_index(drop=True)


def _load_ai_splits(cfg: dict) -> pd.DataFrame:
    """train/valid/test CSV 를 split 태그와 함께 하나로 합친다 (중복 제거 + 역·날짜순 정렬).

    lag/이동통계가 분할 경계를 넘어 직전 값을 참조할 수 있도록 따로 계산하지 않고 합친다.
    """
    frames = []
    for split in ("train", "valid", "test"):
        path = Path(cfg["data"][split])
        df = pd.read_csv(path, encoding="utf-8-sig", parse_dates=["날짜"])
        df["split"] = split
        frames.append(df)
    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=["고객번호", "역명", "날짜"], keep="last")
        .sort_values(["고객번호", "날짜"])
        .reset_index(drop=True)
    )


def _merge_calendar(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """날짜인덱스.csv 를 붙여 달력 피처(월/요일/주말/공휴일/휴무일/징검다리)를 추가한다."""
    cal = pd.read_csv(cfg["data"]["calendar"], encoding="utf-8-sig", parse_dates=["날짜"])
    cal = cal[["날짜", "월", "요일_숫자", "주말", "공휴일", "휴무일", "징검다리"]]
    out = df.merge(cal, on="날짜", how="left")
    for col in ["주말", "공휴일", "휴무일", "징검다리"]:
        out[col] = out[col].fillna(0).astype(int)
    return out


def _merge_bill_baseline(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """격월 청구서를 고객번호-월 단위 일평균 baseline으로 변환해 붙인다."""
    bills = pd.read_csv(cfg["data"]["bills"], encoding="utf-8-sig")
    bills = bills[
        bills["포함월수"].notna()
        & (bills["포함월수"] > 0)
        & bills["격월사용량_톤"].notna()
    ].copy()
    bills["monthly_ton"] = bills["격월사용량_톤"] / bills["포함월수"]
    bills["start_m"] = pd.to_datetime(
        bills["시작연월"].astype(str), format="%Y-%m", errors="coerce"
    ).dt.month
    bills["end_m"] = pd.to_datetime(
        bills["종료연월"].astype(str), format="%Y-%m", errors="coerce"
    ).dt.month

    records: list[tuple[int, int, float]] = []
    for row in bills.itertuples(index=False):
        for month in {row.start_m, row.end_m}:
            if pd.notna(month):
                records.append((row.고객번호, int(month), float(row.monthly_ton) / 30.4))
    baseline = pd.DataFrame(records, columns=["고객번호", "월", "bill_daily"])
    baseline = baseline.groupby(["고객번호", "월"], as_index=False)["bill_daily"].median()
    return df.merge(baseline, on=["고객번호", "월"], how="left")


def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """월/요일/일/연중일을 sin·cos 로 인코딩한다(주기성: 12월↔1월, 일↔월요일을 가깝게 연결)."""
    out = df.copy()
    out["day"] = out["날짜"].dt.day
    out["dayofyear"] = out["날짜"].dt.dayofyear
    periodic = [("월", 12), ("요일_숫자", 7), ("day", 31), ("dayofyear", 366)]
    for col, period in periodic:
        out[f"{col}_sin"] = np.sin(2 * np.pi * out[col] / period)
        out[f"{col}_cos"] = np.cos(2 * np.pi * out[col] / period)
    return out


def _add_lag_rolling_features(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """역별 과거 사용량·승객수의 lag / 이동통계 / 비율·차이 피처를 만든다.

    모두 shift(과거로 밀기) 후 계산하므로 '해당 날짜 이전' 정보만 쓴다(누수 없음).
    config 의 usage_lags / passenger_lags / rolling_windows 가 어떤 피처를 만들지 결정.
    """
    out = df.copy()
    group = out.groupby("고객번호", sort=False)
    usage = group[TARGET]
    passenger = group["총승객수"]

    features: dict[str, pd.Series] = {}
    for lag in cfg["features"]["usage_lags"]:
        lag = int(lag)
        features[f"u_lag_{lag}"] = usage.shift(lag)
    for lag in cfg["features"]["passenger_lags"]:
        lag = int(lag)
        features[f"p_lag_{lag}"] = passenger.shift(lag)

    shifted_usage = usage.shift(1)
    shifted_passenger = passenger.shift(1)
    for window in cfg["features"]["rolling_windows"]:
        window = int(window)
        roll_u = shifted_usage.groupby(out["고객번호"]).rolling(window, min_periods=1)
        features[f"u_mean_{window}"] = roll_u.mean().reset_index(level=0, drop=True)
        features[f"u_median_{window}"] = roll_u.median().reset_index(level=0, drop=True)
        features[f"u_std_{window}"] = roll_u.std().reset_index(level=0, drop=True)
        features[f"u_min_{window}"] = roll_u.min().reset_index(level=0, drop=True)
        features[f"u_max_{window}"] = roll_u.max().reset_index(level=0, drop=True)

        roll_p = shifted_passenger.groupby(out["고객번호"]).rolling(window, min_periods=1)
        features[f"p_mean_{window}"] = roll_p.mean().reset_index(level=0, drop=True)
        features[f"p_std_{window}"] = roll_p.std().reset_index(level=0, drop=True)

    out = pd.concat([out, pd.DataFrame(features, index=out.index)], axis=1)
    out["days_since_prev"] = group["날짜"].diff().dt.days.fillna(30).clip(1, 30)
    out["p_ratio_lag7"] = out["총승객수"] / out["p_lag_7"].replace(0, np.nan)
    out["u_ratio_lag7"] = out["u_lag_1"] / out["u_lag_7"].replace(0, np.nan)
    out["u_delta_lag1_lag7"] = out["u_lag_1"] - out["u_lag_7"]
    out["p_delta_today_lag7"] = out["총승객수"] - out["p_lag_7"]
    return out


def _add_fit_period_statistics(df: pd.DataFrame, fit_splits: tuple[str, ...]) -> pd.DataFrame:
    """학습 구간(fit_splits)의 역×월·역×요일 중앙값 baseline 을 만들어 전 행에 붙인다.

    극단치를 뺀(clean) 값으로 계산하며, 역별 값이 없을 때 쓸 전역(월/요일) 중앙값도 함께 둔다.
    학습 구간 통계만 쓰므로 test 에 미래정보가 새지 않는다.
    """
    fit = df[df["split"].isin(fit_splits)].copy()
    keep = _iqr_keep_for_stats(fit)
    clean = fit[keep]

    month_med = (
        clean.groupby(["고객번호", "월"])[TARGET]
        .median()
        .rename("fit_month_median")
        .reset_index()
    )
    dow_med = (
        clean.groupby(["고객번호", "요일_숫자"])[TARGET]
        .median()
        .rename("fit_dow_median")
        .reset_index()
    )
    global_month = (
        clean.groupby("월")[TARGET]
        .median()
        .rename("global_month_median")
        .reset_index()
    )
    global_dow = (
        clean.groupby("요일_숫자")[TARGET]
        .median()
        .rename("global_dow_median")
        .reset_index()
    )

    out = df.merge(month_med, on=["고객번호", "월"], how="left")
    out = out.merge(dow_med, on=["고객번호", "요일_숫자"], how="left")
    out = out.merge(global_month, on="월", how="left")
    out = out.merge(global_dow, on="요일_숫자", how="left")
    return out


def _iqr_keep_for_stats(df: pd.DataFrame) -> pd.Series:
    """baseline 통계 계산에 쓸 정상 행 mask(역별 IQR×3 안 + 음수 제외) — 극단치가 중앙값을 흔들지 않게."""
    keep = pd.Series(True, index=df.index)
    for _, idx in df.groupby("고객번호").groups.items():
        values = df.loc[idx, TARGET]
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        iqr = q3 - q1
        keep.loc[idx] = (values >= q1 - 3.0 * iqr) & (values <= q3 + 3.0 * iqr) & (values >= 0)
    return keep


def _finalize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """결측 피처를 단계적으로 메운다: bill_daily 는 역월→전역월→train중앙값, 핵심 lag 는 bill_daily 로."""
    out = df.copy()
    out["bill_daily"] = (
        out["bill_daily"]
        .fillna(out["fit_month_median"])
        .fillna(out["global_month_median"])
        .fillna(out[TARGET].where(out["split"] == "train").median())
    )
    for col in ["u_lag_1", "u_lag_2", "u_lag_3", "u_lag_7", "u_mean_7", "u_median_7"]:
        if col in out:
            out[col] = out[col].fillna(out["bill_daily"])
    return out
