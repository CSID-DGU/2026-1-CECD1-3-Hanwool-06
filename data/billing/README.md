# data/billing/

과거 청구서(i121 크롤링)와 검토 매핑(Excel 3차검토)을 정제·결합한 자료입니다. 현재 앱·모델이 재사용하는 아래 세 파일을 유지합니다. 모두 UTF-8-BOM + 한글 헤더입니다.

과거 생성 스크립트는 [`archive/back/scripts/billing_etl/postprocess_bills.py`](../../archive/back/scripts/billing_etl/postprocess_bills.py)에 보관했습니다. 새 수집 결과는 운영 DB와 `APP_DATA_DIR` 아래에 저장합니다.

---

## bills_clean.csv : 청구서 원본을 정기분만 필터링하고 식별자를 붙인 통합 파일 (10,260행)

- 고객번호 : mkey (9자리 zero-padded)
- 역명 : Excel 검토표 기준 정답 역명 (예 `건대입구역(7호선)`)
- 영업사업소 : 서울교통공사 영업사업소
- 용도 : `시민용` / `직원용`
- 고지서_성명 : 청구서에 찍히는 이름 (예 `강동역(미사용지하수)`)
- 납기일 : YYYY-MM-DD
- 납기_연도 : 정수 연도
- 납기_월 : 정수 월 (1~12)
- 납기_연월 : `YYYY-MM`
- 구분 : `정기분`만 남김
- 수납상태 : 예 `수납 완료`
- 총사용량_톤 : 청구 주기 총 사용량 (격월=2개월 분)
- 월평균사용량_톤 : 총사용량 ÷ 2
- 부과금액_원 : 청구 금액

---

## mkey_station_map.csv : 우리 80개 mkey의 정답 매핑 (80행)

- 고객번호 : mkey
- 역명 : 정답 역명 (Excel 검토표 기준)
- 영업사업소 : 서울교통공사 영업사업소
- 수도사업소 : 관할 수도사업소
- 고지서_성명 : 청구서상 성명
- 용도 : `시민용` / `직원용`
- 1차검토_동국대 : `O`/`X`/`불일치`/`추가`
- 2차검토_영업계획처 : 2차 검토 결과

---

## meter_match.csv : mkey ↔ 일일CSV 1-to-1 매핑 (80행, 마스터 키)

- 고객번호 : mkey
- 일일CSV파일명 : `data/raw/daily_water_usage/{이 이름}.csv` (예 `강동역`, `보문역-직원용`)
- 역명 : 정규화된 base 역명 (예 `강동역`)
- 호선 : 정수 (단일 호선 역은 빈값)
- 용도 : `시민용` / `직원용`
- 역명_원본 : Excel의 원본 표기 (정규화 전)
- 매칭근거 : `exact` (역+호선+용도 일치) / `line` (역+호선) / `usage` (역+용도) / `station_only` (역명만)

---

## 보관한 이전 결과

다음 파일은 [`archive/data/billing/`](../../archive/data/billing/)에 있습니다. 현재 운영 파이프라인은 이 통계 파일을 읽지 않습니다.

- `station_month_baseline.csv`: 역별 월 사용량의 과거 시즌 통계.
- `mkey_month_baseline.csv`: 계량기별 월 사용량의 과거 시즌 통계.
- `daily_csv_baseline.csv`: 위 통계를 일일 CSV 별칭으로 연결한 결과.
- `postprocess_report.json`: 당시 매핑·정제 건수와 사용한 원자료를 기록한 보고서.

현재 모델용 청구 집계는 `back.pipelines.refresh`가 공유 함수 `build_bills_bimonthly`를 호출해 생성합니다.
