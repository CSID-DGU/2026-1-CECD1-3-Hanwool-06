현재 앱과 모델이 재사용하는 과거 정제 CSV입니다. 일일 상수도 관측, 청구서 집계, 날짜 인덱스, 승하차 자료를 유지합니다.

운영 갱신은 이 자료와 새 관측을 합쳐 `APP_DATA_DIR/processed/` 및 `APP_DATA_DIR/dataset/`에 결과를 저장합니다. 기본 운영 경로는 `data/runtime/`입니다. 이전 일회성 생성 도구는 [`archive/`](../../archive/README.md)에 있으며, 현재 갱신 명령은 `python -m back.pipelines.refresh`입니다.
