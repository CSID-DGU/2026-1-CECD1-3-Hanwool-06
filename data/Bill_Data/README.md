# Bill_Data/

청구서(i121 크롤링) + 정답 매핑(Excel 3차검토)을 정제·결합한 결과 파일들. 모두 UTF-8-BOM + 한글 헤더.

생성 스크립트: `scripts/i121_postprocess_bills.py`

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
- 일일CSV파일명 : `Raw_data/일일데이터/{이 이름}.csv` (예 `강동역`, `보문역-직원용`)
- 역명 : 정규화된 base 역명 (예 `강동역`)
- 호선 : 정수 (단일 호선 역은 빈값)
- 용도 : `시민용` / `직원용`
- 역명_원본 : Excel의 원본 표기 (정규화 전)
- 매칭근거 : `exact` (역+호선+용도 일치) / `line` (역+호선) / `usage` (역+용도) / `station_only` (역명만)

---

## station_month_baseline.csv : 역 × 12개월 시즌 통계 (948행)

- 역명 : 역 이름
- 월 : 1~12
- 관측수 : 해당 (역, 월) 버킷에 들어간 청구서 수
- 중간값_톤 : median 월평균 사용량
- 평균_톤 : mean
- 25분위_톤 / 75분위_톤 : 분위수
- 표준편차_톤 : std
- IQR_톤 : 75분위 - 25분위

> 단위는 **월별** 톤. 일일과 비교하려면 ÷30.

---

## mkey_month_baseline.csv : 미터 × 12개월 시즌 통계 (960행)

- 고객번호 : mkey
- 역명 : 정답 역명
- 월 : 1~12
- 관측수 / 중간값_톤 / 평균_톤 / 25분위_톤 / 75분위_톤 / 표준편차_톤 / IQR_톤 : `station_month_baseline.csv`와 동일 의미, 미터 단위

---

## daily_csv_baseline.csv : 일일CSV별로 join 가능한 baseline (960행)

- 일일CSV파일명 : 매핑 키
- 고객번호 : 해당 미터의 mkey
- 역명 : 정규화 역명
- 호선 : 정수 또는 빈값
- 용도 : `시민용` / `직원용`
- 월 : 1~12
- 관측수 / 중간값_톤 / 평균_톤 / 25분위_톤 / 75분위_톤 / 표준편차_톤 / IQR_톤 : `mkey_month_baseline.csv`와 동일 값을 일일CSV파일명 키로 redistribute

---

## postprocess_report.json : 청구서 정제 진단

- review_xlsx : 사용된 Excel 파일명
- crawled_mkeys : 크롤링된 mkey 수
- mkey_station_mapped : 정답 매핑 성공 수 (80/80)
- bills_initial / bills_after_gubun_filter / bills_clean_final : 필터링 단계별 행 수
- station_month_baseline_rows / mkey_month_baseline_rows : 생성 baseline 행 수
- meter_match_pairs / meter_match_reasons : 매칭 결과 분포
