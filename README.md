# 서울교통공사 상수도 관리

역 수도 사용량과 승하차 자료를 모아 이상 사용을 찾아내는 웹 서비스입니다. React/Vite 화면, FastAPI API, SQLite DB, LightGBM 모델로 이루어져 있습니다.

## 폴더

| 경로 | 내용 |
|---|---|
| `front/` | 웹 화면 |
| `back/api/` | API, 계정·계량기 관리, 자동 수집 예약 |
| `back/pipelines/` | 아리수 사용량·청구서 수집, 승하차 수집, 모델 갱신(`refresh`) |
| `back/ml/lightgbm/` | 예측·이상탐지 모델 |
| `data/app_seed/`, `data/processed/`, `data/billing/` | 초기 자료, 정제 자료, 계량기 매핑 |
| `data/runtime/` | 운영 DB, 수집 결과, 모델 결과, 스냅샷 (비공개, git 제외) |
| `archive/` | 지금은 쓰지 않는 과거 코드·자료 |

## 설치와 실행

Python 3.11 이상, Node.js 20.19 이상. 저장소 루트에서 실행합니다.

```sh
conda env create -f environment.yml && conda activate hanul   # 또는 python -m venv .venv 후 pip install -r requirements-dev.txt
npm install
cp .env.example .env   # 처음 한 번. ADMIN_EMAIL, ADMIN_PASSWORD(12~128자)를 채우면 첫 실행 때 총괄 관리자가 만들어집니다
```

```sh
npm run dev:api   # 터미널 1: API 127.0.0.1:8000
npm run dev       # 터미널 2: 화면 127.0.0.1:5173 (/api 는 8000번으로 전달)
```

운영처럼 한 프로세스로 띄우려면 `npm run build && npm run start`(8000번에서 화면과 API를 함께 서비스)입니다. 두 명령 모두 활성화된 환경의 `python`을 씁니다. 공개 회원가입은 없고 담당자 계정은 관리자가 관리 화면에서 만듭니다. macOS에서 LightGBM이 `libomp.dylib`을 못 찾으면 `brew install libomp`를 실행합니다.

운영 배포에서는 `APP_ENV=production`, `APP_COOKIE_SECURE=true`, `APP_ORIGINS`, `APP_ALLOWED_HOSTS`, `APP_DATA_DIR`를 실제 값으로 두고 HTTPS 프록시 뒤에서 8000번은 로컬에만 엽니다. DB는 SQLite 전용이라 RDS(PostgreSQL)로 바로 옮길 수 없습니다.

## 자료 갱신

- **사용량·청구서(아리수)**: `.env`에 `ARISU_USER_ID`, `ARISU_USER_PWD`를 넣으면 화면의 **정보 업데이트**로 수집하고, 매일 08:00(한국시간)에 자동 수집합니다(서버가 켜져 있어야 함). 음수·빈 검침은 그날만 제외하고 0으로 바꾸지 않습니다.
- **승하차**: 일별 API(`SEOUL_PSGR_KEY`, 최근 1주일치만 제공)와 서울 열린데이터광장 월별 파일(OA-12914, 키 불필요, 그 달이 지난 뒤 게시)로 채웁니다.
- **모델**: 자동 수집은 모델을 다시 돌리지 않습니다. 수집 뒤 아래 명령을 실행하면 수집된 마지막 날까지 위험도가 갱신됩니다.

```sh
python -m back.pipelines.refresh --start 2026-09-20 --end 2026-09-22 --water --ridership   # CLI 수집
python -m back.pipelines.daily_ridership.monthly 2026-05 2026-08                           # 승하차 월별 파일 보충
python -m back.pipelines.refresh --model                                                   # 저장된 자료로 모델 다시 실행
python -m back.pipelines.refresh --model --train-end 2026-01-28 --valid-end 2026-05-13     # 분할 경계를 새로 정할 때
```

결과와 오류는 `data/runtime/refresh_report.json`에 남습니다.

## 모델

LightGBM이 계량기별 일 사용량을 예측하고, 오차를 그 계량기의 최근 28일 사용량과 평소 변동 폭에 견줘 정상·주의·경고로 나눕니다(검증 구간 상위 5%·1%).

- 학습·검증·평가는 시간 순서로 나눕니다. 경계를 생략하면 직전 실행의 경계를 그대로 써서 같은 모델로 최신 날짜까지 판정합니다. 현재 경계는 학습 ~2026-01-28, 검증 ~2026-05-13입니다.
- 예측 목표는 최근 7일 사용량 대비 비율이고, 같은 날 다른 역들이 함께 벗어난 만큼 예측을 보정합니다(자기 검침값 제외, 그날 다른 역 6곳 이상 필요).
- 당일·전날 승하차가 아직 없는 날은 승하차 없이 학습한 보조 모델로 판정합니다.
- 학습 90일·검증 14일에 못 미치는 계량기는 자료 부족으로 두고 임의로 판정하지 않습니다.
- 결과는 `data/runtime/model/`에 저장됩니다(`metrics.json`, `test_anomalies.csv`, `model.txt`, `model_without_ridership.txt`).

## 테스트

```sh
python -m unittest discover -s tests
npm test
npm run build
```

## 확인 상태 (2026-10-06)

- 실제 아리수 계정으로 수집을 확인했습니다. 천왕역7·보문역6·서울역4·역삼역2는 계정에 일일 조회가 등록돼 있지 않아 청구서만 들어옵니다. 미아역4 2026-04-24(음수), 동대문역사문화공원역4 2024-05-22(빈 값)는 원자료 오류라 그날만 제외합니다.
- 모델은 평가 구간(2026-05-14 ~ 08-31, 7,607행)에서 기준 모델 대비 MAE 3.73 → 3.30, RMSE 6.40 → 6.00, 주의·경고 비율 13.7% → 7.3%입니다. 기준 모델 결과와 이전 스냅샷은 `data/runtime/backups/`에 있습니다.
- 아직 확인하지 않은 것: OpenAI 원인 추정과 SMTP 발송의 실제 연결, 아리수 원본 고지서 PDF(현재 PDF는 저장된 자료로 만든 조회내역), PostgreSQL 배포, 2026-09 승하차 월별 파일.

## 백업·계정

```sh
python -m back.api.manage backup /private/backup/water.sqlite3    # 실행 중에도 안전한 SQLite 백업
python -m back.api.manage reset-password admin@example.com        # 비밀번호 재설정(터미널에서 입력, 다음 로그인 때 변경 요구)
```

`data/runtime/`에는 계정·세션·수집 자료가 있으니 외부에 노출하지 않습니다.
