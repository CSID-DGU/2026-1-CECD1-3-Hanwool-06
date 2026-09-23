LightGBM 기반 사용량 예측 및 이상탐지 모델 코드입니다.

운영 자료로 재학습하고 API 스냅샷까지 갱신하려면 저장소 루트에서 `python -m back.pipelines.refresh --model`을 실행합니다. 결과는 `APP_DATA_DIR/model/`에 저장되며 기본 경로는 `data/runtime/model/`입니다.

모델만 직접 시험하려면 `python -m back.ml.lightgbm.main`을 사용합니다. 기본 설정은 `data/ml_dataset/`과 `data/processed/`를 읽고 `data/runtime/model/`에 결과를 저장합니다. `--config`와 `--out-dir`로 별도 입력 설정과 출력 경로를 지정할 수 있습니다.

이전 `results/`는 [`archive/back/ml/lightgbm/results/`](../../../archive/back/ml/lightgbm/results/)에 보관했습니다. 초기 앱의 위험도 자료는 `data/app_seed/risk/test_anomalies.csv`에 별도로 유지합니다.
