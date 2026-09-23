# 백엔드

전체 설치·실행·권한·백업 절차는 루트 `README.md`를 참고하세요.

- `api/`: FastAPI, SQLite 등록부·계정·세션, 보호된 자료 조회, PDF/Excel, 분석·메일.
- `pipelines/`: 아리수·승하차 수집과 모델 실행. `python -m back.pipelines.refresh --help`.
- `scripts/`: 현재 청구서 수집·연결 진단 도구와 운영 파이프라인에서 공유하는 ETL 함수.
- `ml/lightgbm/`: 현재 사용하는 CPU 학습·검증·이상 탐지 코드.

운영 API와 수집기는 같은 비공개 `APP_DATA_DIR`와 SQLite DB를 사용합니다.
수집 원본·완성 스냅샷은 웹 정적 폴더나 데이터 Git 브랜치에 게시하지 않습니다.

이전 분석·크롤러·ETL 및 저장된 실험 결과는 [`archive/`](../archive/README.md)에 있습니다.
현재 `ml/lightgbm/` 모델 코드와 `scripts/dataset_etl/build_clean_dataset.py`의 청구 집계 함수는 계속 사용합니다.
