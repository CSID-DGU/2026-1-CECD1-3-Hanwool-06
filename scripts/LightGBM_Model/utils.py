"""LightGBM 전용 유틸리티."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from tqdm.auto import tqdm

# 예측 타겟 컬럼명 (후처리에서 실측값 참조용)
TARGET = "일사용량_톤"


def load_config(path: str | Path) -> dict:
    """config.yaml 을 읽어 dict 로 반환한다."""
    with open(path, "r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def set_seed(seed: int) -> None:
    """재현성을 위해 파이썬/넘파이 난수 시드를 고정한다."""
    random.seed(seed)
    np.random.seed(seed)


def ensure_dir(path: str | Path) -> Path:
    """폴더가 없으면 만들고 Path 로 반환한다."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(obj: dict, path: str | Path) -> None:
    """dict 를 보기 좋은 JSON(한글 그대로)으로 저장한다."""
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=2)


def save_csv(df: pd.DataFrame, path: str | Path) -> None:
    """DataFrame 을 UTF-8-BOM CSV(엑셀 호환)로 저장한다."""
    df.to_csv(path, index=False, encoding="utf-8-sig")


def format_summary(summary: dict) -> str:
    """metric.summarize 결과를 한 줄 로그 문자열로 만든다."""
    return (
        f"rmse={summary['rmse']:.4f} "
        f"rmse_without_data_errors={summary['rmse_without_data_errors']:.4f} "
        f"rmse_normal_only={summary['rmse_normal_only']:.4f} "
        f"non_alert_diagnostic={summary['rmse_non_alert_diagnostic']:.4f} "
        f"경고={summary['경고']} 주의={summary['주의']}"
    )


# ── 예측 후처리 (bias 보정) ─────────────────────────────────────────
# 모두 valid(과거) 잔차만 쓰므로 누수 없음. config 의 postprocess 섹션으로 켜고 끈다.

def build_valid_bias(valid_meta: pd.DataFrame, valid_pred: np.ndarray) -> dict:
    """valid 잔차(실측-예측)의 전역/역별/역×요일 중앙값을 구한다 (test 보정 기준)."""
    frame = valid_meta.copy()
    frame["_residual"] = frame[TARGET].to_numpy(dtype=float) - np.asarray(valid_pred, dtype=float)
    frame["_dow"] = pd.to_datetime(frame["날짜"]).dt.dayofweek
    return {
        "global": float(frame["_residual"].median()),
        "station": frame.groupby("고객번호")["_residual"].median(),
        "station_dow": frame.groupby(["고객번호", "_dow"])["_residual"].median(),
    }


def postprocess_predictions(meta: pd.DataFrame, pred: np.ndarray, valid_bias: dict, cfg: dict) -> np.ndarray:
    """config postprocess 설정대로 (역×요일 bias + 온라인 잔차) 보정을 순서대로 적용한다."""
    pp = cfg.get("postprocess", {})
    out = _apply_valid_station_dow_bias(meta, pred, valid_bias, float(pp.get("valid_station_dow_bias_weight", 0.0)))
    out = _apply_online_residual_correction(meta, out, float(pp.get("online_residual_alpha", 0.0)),
                                            float(pp.get("online_residual_clip", 0.0)))
    return out


def _apply_valid_station_dow_bias(meta, pred, valid_bias, weight: float) -> np.ndarray:
    """valid 의 역×요일 잔차 중앙값을 weight 만큼 예측에 더해 계통오차를 보정한다."""
    pred = np.asarray(pred, dtype=float)
    if weight <= 0:
        return pred.copy()
    dow = pd.to_datetime(meta["날짜"]).dt.dayofweek
    station_bias, station_dow_bias, global_bias = valid_bias["station"], valid_bias["station_dow"], valid_bias["global"]
    adjustment = np.array(
        [station_dow_bias.get((cid, d), station_bias.get(cid, global_bias)) for cid, d in zip(meta["고객번호"], dow)],
        dtype=float,
    )
    return np.clip(pred + weight * adjustment, 0.0, None)


def _apply_online_residual_correction(meta, pred, alpha: float, clip_value: float) -> np.ndarray:
    """역별로 날짜순 진행하며 과거 잔차의 지수이동평균(EWMA)을 다음 예측에 더한다 (인과적 온라인 보정)."""
    pred = np.asarray(pred, dtype=float)
    if alpha <= 0 or clip_value <= 0:
        return pred.copy()
    corrected = np.zeros_like(pred, dtype=float)
    state: dict[int, float] = {}
    work = meta[["고객번호", "날짜", TARGET]].copy()
    work["_pred"] = pred
    work["_row"] = np.arange(len(work))
    ordered = work.sort_values(["고객번호", "날짜"])
    for cid, _, actual, base_pred, row_idx in tqdm(
        ordered.itertuples(index=False, name=None), total=len(ordered), desc="온라인 잔차보정", leave=False,
    ):
        correction = state.get(cid, 0.0)
        corrected[row_idx] = max(float(base_pred) + correction, 0.0)
        if 0 <= actual <= 500:   # 데이터오류는 보정 학습에서 제외
            residual = float(np.clip(actual - base_pred, -clip_value, clip_value))
            state[cid] = (1.0 - alpha) * correction + alpha * residual
    return corrected


def save_scatter_plot(anomalies: pd.DataFrame, warn_q: float, alert_q: float, path: str | Path) -> None:
    """예측(x) vs 실측(y) 산점도를 저장한다.

    - y=x 완벽예측선: 검은 실선
    - 잔차 |actual-pred| 의 q95/q99 밴드: 빨간 점선 (y=x ± 해당 잔차)
    - 점 색: 심각도(정상/주의/경고). 축 가독성을 위해 데이터오류(음수/대용량)는 제외.
    (한글 폰트 깨짐 방지로 라벨은 영문)
    """
    import matplotlib
    matplotlib.use("Agg")   # 화면 없이 파일로만 저장
    import matplotlib.pyplot as plt

    df = anomalies[~anomalies["data_error_candidate"]]
    actual = df["일사용량_톤"].to_numpy(dtype=float)
    pred = df["pred_ton"].to_numpy(dtype=float)
    abs_resid = np.abs(actual - pred)
    d_warn = float(np.quantile(abs_resid, warn_q))    # 잔차 q95
    d_alert = float(np.quantile(abs_resid, alert_q))  # 잔차 q99
    hi = float(max(actual.max(), pred.max())) * 1.02
    lim = (0.0, hi)

    fig, ax = plt.subplots(figsize=(7, 7))
    palette = [("정상", "Normal", "#7f9bb3"),
               ("주의", "Warning", "#f5a142"),
               ("경고", "Alert", "#d62728")]
    for sev_kr, sev_en, color in palette:
        m = (df["심각도"] == sev_kr).to_numpy()
        ax.scatter(pred[m], actual[m], s=12, alpha=0.85, c=color,
                   edgecolors="none", label=f"{sev_en} ({int(m.sum())})")

    line = np.array(lim)
    ax.plot(line, line, color="black", lw=1.8, label="y = x (perfect)")
    for d in (d_warn, d_alert):   # 양방향(과다/과소) 밴드
        ax.plot(line, line + d, "r--", lw=1.1, alpha=0.85)
        ax.plot(line, line - d, "r--", lw=1.1, alpha=0.85)
    ax.plot([], [], "r--", lw=1.1, label=f"residual q{warn_q:g}=±{d_warn:.1f}, q{alert_q:g}=±{d_alert:.1f}")

    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal")
    ax.set_xlabel("Prediction (ton)")
    ax.set_ylabel("Actual (ton)")
    ax.set_title("LightGBM — Prediction vs Actual (test)")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.grid(True, ls=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
