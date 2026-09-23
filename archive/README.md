# 이전 코드와 자료 보관

현재 실행 경로에서 사용하지 않는 분석 실험, 크롤러·ETL, 과거 원자료와 결과를 보관합니다. 파일은 `archive/` 아래에 **기존 저장소 경로를 그대로 유지**했습니다. 예를 들어 이전 `analysis/`는 `archive/analysis/`에 있습니다. 사용 중인 프론트 파일에서 제거한 일부 함수·스타일은 출처 주석과 함께 별도 파일에 보존했습니다.

## 보관 목록

| 보관 위치 (`archive/` 기준) | 내용 |
|---|---|
| `analysis/` | 이전 분석·모델 실험과 당시 산출물 |
| `back/ml/lightgbm/requirements.txt` | 과거 분석 의존성 목록; 현행에서 미사용 seaborn·statsmodels 제외 |
| `back/ml/lightgbm/results/` | 이전 LightGBM 실행 결과 |
| `back/scripts/arisu_history/` | 이전 아리수 이력 수집·변환 도구와 설명 |
| `back/pipelines/daily_water/detector.py` | 사용을 마친 STL·IsolationForest 분석기 |
| `back/scripts/dataset_etl/build_daily_usage_long.py` | 과거 역별 이력 CSV 병합 도구 |
| `back/scripts/dataset_etl/build_clean_dataset.py` | 이전 일괄 변환 CLI 전체; 운영에는 청구 집계 함수만 유지 |
| `back/scripts/dataset_etl/build_date_index.py` | 과거 고정 기간의 달력 생성 도구 |
| `back/scripts/ridership_etl/` | 과거 월별 승하차 CSV 다운로드·정제 도구와 설명 |
| `back/scripts/billing_etl/postprocess_bills.py` | 검토표와 과거 청구서를 결합하던 일회성 후처리 도구 |
| `data/raw/water_bills/` | 과거 사업소별 청구 원자료 |
| `data/raw/ridership/ridership.csv` | 과거 승하차 원본 CSV |
| `data/billing/station_month_baseline.csv` | 역별 월 사용량의 과거 시즌 통계 |
| `data/billing/mkey_month_baseline.csv` | 계량기별 월 사용량의 과거 시즌 통계 |
| `data/billing/daily_csv_baseline.csv` | 일일 CSV 별칭으로 연결한 과거 시즌 통계 |
| `data/billing/postprocess_report.json` | 당시 청구 자료 정제·매핑 보고서 |
| `data/arisu_station_history/` | 과거 아리수 계량기별 이력 원본 |
| `front/unused-styles.css` | 현재 화면에서 사용하지 않는 과거 스타일과 원본 위치 |
| `front/unused-functions.jsx` | 사용하지 않는 함수·컴포넌트와 원본 위치 |
| `front/src/pages/Detail/sm-logo.svg` | 사용하지 않는 상세 화면 로고 |

추가로 이전 커밋(HEAD)의 `.github/workflows/daily_ridership.yml`, `daily_snapshot.yml`, `front/package-lock.json`, `front/scripts/build-html.mjs`, `sync-data.mjs`, `front/vite.singlefile.config.js`를 같은 경로 아래 보관했습니다. 이 workflow는 보관용이며 실행되지 않습니다. 삭제한 `front/public/bills.json`과 `stations.json`은 현재 `data/app_seed/` 파일과 내용이 동일하므로 중복 복사하지 않았습니다.

## 현재 운영 경로

현재 앱과 수집 작업은 이 보관 폴더를 입력으로 사용하지 않습니다. 운영 코드는 `back/api/`, `back/pipelines/`, `back/scripts/billing_etl/`, `back/ml/lightgbm/`에 있습니다. `back/scripts/dataset_etl/build_clean_dataset.py`의 청구 집계 함수도 현재 모델 갱신에서 사용하므로 원래 위치에 유지했습니다.

`data/app_seed/`, `data/processed/`, `data/ml_dataset/`와 현재 쓰는 `data/billing/` 매핑·정제 자료를 유지합니다. 초기 위험도 자료 11,285행은 `data/app_seed/risk/test_anomalies.csv`에 따로 보존했습니다. 새 수집·학습 결과는 `APP_DATA_DIR` 아래에 저장하며 기본 경로는 `data/runtime/`입니다.

`.env`, 계정·세션 DB, 운영 수집 캐시 등 비공개 실행 자료는 이 폴더에 옮기지 않았습니다. 보관 자료에도 기존 원자료가 포함되어 있으므로 웹 정적 자산이나 공개 다운로드 경로로 제공하지 않습니다.

## 과거 작업을 재현할 때

각 하위 폴더의 기존 문서·스크립트 설명은 당시 상태로 보존했습니다. 따라서 그 안의 명령과 경로는 이동 전 위치를 가리킵니다. 보관된 스크립트는 상대 경로·형제 모듈에 의존하므로 **필요한 코드와 입력 파일을 별도 작업 복사본의 원래 위치로 복원한 뒤** 실행해야 합니다. 특히 승하차 ETL과 `postprocess_bills.py`는 함께 참조하는 경로를 복원해야 합니다.

과거 환경과 데이터 기준도 확인해야 하며, 폐기된 아리수 `/cs/` 주소를 쓰는 수집기는 위치 복원만으로 현재 사이트에서 작동하지 않습니다. 현재 자료를 갱신할 때는 [루트 README](../README.md)와 [운영 파이프라인 문서](../back/pipelines/README.md)의 명령을 사용하세요.
