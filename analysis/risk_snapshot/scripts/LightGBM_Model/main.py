"""LightGBM 전용 학습/평가 진입점 (오케스트레이션만 담당).

실행:
  conda run -n hanul python AI_Sunghyun/LightGBM/main.py

흐름:
  [1/2] 검증모델  train -> valid : 조기종료로 라운드 결정 + valid 잔차로 이상탐지 임계값(q95/q99) 확정
  [2/2] 최종모델  train+valid -> test : 재학습 후 후처리 → 이상탐지 → 결과/그림 저장

실제 로직은 dataset.py(피처) · model.py(모델) · metric.py(지표) · utils.py(설정/후처리/그림)에 있다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import dataset  # noqa: E402
import metric  # noqa: E402
import utils  # noqa: E402
from model import LightGBMForecaster  # noqa: E402


def run(config_path: Path | None = None) -> dict:
    """전체 파이프라인 실행: 검증모델→임계값 확정, 최종모델→test 예측·이상탐지·결과저장. 지표 dict 반환."""
    cfg = utils.load_config(config_path or HERE / "config.yaml")
    utils.set_seed(int(cfg["seed"]))
    results_dir = utils.ensure_dir(HERE / "results")
    warn_q = float(cfg["anomaly"]["warn_quantile"])    # 주의 분위수 (상위 5%)
    alert_q = float(cfg["anomaly"]["alert_quantile"])  # 경고 분위수 (상위 1%)

    # [1/2] 검증모델: train 으로 학습, valid 로 조기종료 + 임계값 산출
    print("[1/2] validation model: train -> valid")
    valid_data = dataset.prepare_data(cfg, fit_splits=("train",))
    train_mask = dataset.training_mask(valid_data.frame, ("train",), cfg)
    X_train, y_train = dataset.split_xy(valid_data, train_mask)
    X_valid = dataset.split_features(valid_data, "valid")
    y_valid = valid_data.frame.loc[valid_data.frame["split"] == "valid", dataset.TARGET].reset_index(drop=True)

    valid_model = LightGBMForecaster(cfg["model"])
    valid_model.fit(X_train, y_train, valid_data.categorical_cols,
                    eval_set=(X_valid, y_valid),
                    early_stopping_rounds=int(cfg["modeling"]["early_stopping_rounds"]))

    valid_meta = dataset.split_meta(valid_data, "valid")
    valid_pred = valid_model.predict(X_valid)
    # valid 잔차 |z| 분포의 q95/q99 를 임계값으로 확정 → test 에도 동일 적용
    valid_scored = metric.score_residuals(valid_meta, valid_pred)
    warn_t, alert_t = metric.quantile_thresholds(valid_scored["z_score"], warn_q, alert_q)
    valid_summary = metric.summarize(metric.classify(valid_scored, warn_t, alert_t))
    valid_bias = utils.build_valid_bias(valid_meta, valid_pred)
    print(f"  임계값(|z|): 주의>={warn_t:.3f} (q{warn_q:g}), 경고>={alert_t:.3f} (q{alert_q:g})")
    print(f"  valid {utils.format_summary(valid_summary)}")

    # [2/2] 최종모델: train+valid 로 재학습, test 예측 → 후처리 → 이상탐지
    print("[2/2] final model: train+valid -> test")
    final_data = dataset.prepare_data(cfg, fit_splits=("train", "valid"))
    final_mask = dataset.training_mask(final_data.frame, ("train", "valid"), cfg)
    X_final, y_final = dataset.split_xy(final_data, final_mask)
    X_test = dataset.split_features(final_data, "test")

    final_model = LightGBMForecaster(cfg["model"])
    # 조기종료는 없지만 tqdm 에 train loss 가 보이도록 학습셋을 eval 로 넣는다
    final_model.fit(X_final, y_final, final_data.categorical_cols, eval_set=(X_final, y_final))

    test_meta = dataset.split_meta(final_data, "test")
    test_pred_raw = final_model.predict(X_test)
    test_pred = utils.postprocess_predictions(test_meta, test_pred_raw, valid_bias, cfg)
    test_anomalies = metric.classify(metric.score_residuals(test_meta, test_pred), warn_t, alert_t)
    test_anomalies.insert(5, "raw_pred_ton", np.asarray(test_pred_raw, dtype=float).round(3))
    test_summary = metric.summarize(test_anomalies)
    print(f"  test {utils.format_summary(test_summary)}")

    # 결과 저장
    metrics = {
        "model": "LightGBM",
        "mode": "validation=train->valid, final=train+valid->test",
        "postprocess": cfg.get("postprocess", {}),
        "feature_count": len(final_data.feature_cols),
        "train_rows_for_valid_model": int(train_mask.sum()),
        "train_rows_for_final_model": int(final_mask.sum()),
        "valid": valid_summary,
        "test": test_summary,
    }
    utils.save_json(metrics, results_dir / "metrics.json")
    utils.save_csv(test_anomalies, results_dir / "test_anomalies.csv")
    utils.save_csv(test_anomalies[test_anomalies["심각도"] != "정상"].sort_values("z_score"),
                   results_dir / "test_anomalies_flagged.csv")
    utils.save_csv(final_model.feature_importance(final_data.feature_cols),
                   results_dir / "feature_importance.csv")
    utils.save_scatter_plot(test_anomalies, warn_q, alert_q, results_dir / "test_pred_vs_actual.png")
    print(f"  saved: {results_dir}")
    return metrics


if __name__ == "__main__":
    run()
