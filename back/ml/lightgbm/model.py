"""LightGBM 회귀 모델 래퍼."""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from tqdm.auto import tqdm


def _tqdm_callback(total: int, desc: str):
    """부스팅 라운드 진행률 + 매 라운드 loss(평가지표)를 tqdm 막대에 보여주는 콜백."""
    bar = tqdm(total=total, desc=desc, leave=False)

    def _callback(env: "lgb.callback.CallbackEnv") -> None:
        """매 부스팅 라운드마다 LightGBM 이 호출 → 막대 1칸 전진 + loss 갱신."""
        bar.update(1)
        # eval_set 이 있으면 (데이터명, 지표명, 값, ...) 리스트가 채워진다 → 막대 오른쪽에 표시
        if env.evaluation_result_list:
            loss = ", ".join(
                f"{eval_name}={value:.4f}"
                for _, eval_name, value, *_ in env.evaluation_result_list
            )
            bar.set_postfix_str(loss)
        if env.iteration + 1 >= env.end_iteration:   # 조기종료 포함 마지막 라운드면 닫기
            bar.close()

    return _callback


class LightGBMForecaster:
    """LightGBM 회귀기를 감싼 예측기 (config 의 model 파라미터로 생성)."""

    name = "LightGBM"

    def __init__(self, params: dict):
        """config 의 model 섹션(dict)을 받아 LGBMRegressor 를 만든다."""
        self.params = dict(params)
        self.model = lgb.LGBMRegressor(**self.params)

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        categorical_cols: list[str],
        eval_set: tuple[pd.DataFrame, pd.Series] | None = None,
        early_stopping_rounds: int | None = None,
        progress_desc: str = "LightGBM 학습",
    ) -> "LightGBMForecaster":
        """모델을 학습한다.

        categorical_cols      : 범주형으로 처리할 컬럼(고객번호 등) — LightGBM 이 native 처리
        eval_set              : 평가셋. 주면 매 라운드 loss 가 tqdm 에 표시되고 조기종료 기준이 됨
        early_stopping_rounds : 이 라운드만큼 개선 없으면 조기 종료(None 이면 끝까지)
        """
        # 부스팅 라운드 수만큼 진행률 막대 표시 (device=cuda 이면 GPU 에서 학습됨)
        callbacks = [_tqdm_callback(int(self.params.get("n_estimators", 100)), progress_desc)]
        fit_kwargs = {"categorical_feature": categorical_cols}
        if eval_set is not None:
            fit_kwargs["eval_set"] = [eval_set]
            fit_kwargs["eval_metric"] = "rmse"
        if early_stopping_rounds:
            callbacks.append(lgb.early_stopping(early_stopping_rounds, verbose=False))
        fit_kwargs["callbacks"] = callbacks
        self.model.fit(X, y, **fit_kwargs)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """예측값(톤)을 반환. 음수 사용량은 불가능하므로 0 이상으로 자른다(clip)."""
        pred = np.asarray(self.model.predict(X), dtype=float)
        return np.clip(pred, 0.0, None)

    def feature_importance(self, feature_names: list[str]) -> pd.DataFrame:
        """피처별 중요도를 내림차순 표로 반환한다(어떤 피처가 예측에 많이 쓰였는지)."""
        return (
            pd.DataFrame({
                "feature": feature_names,
                "importance": self.model.feature_importances_,
            })
            .sort_values("importance", ascending=False)
            .reset_index(drop=True)
        )
