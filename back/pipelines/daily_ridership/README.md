서울교통공사 일별 승하차 인원 수집 파이프라인입니다.

등록부의 일일 수집 대상 역사에 대한 API 자료를 `APP_DATA_DIR/daily/ridership/<date>.csv`와 날짜별 상태 파일에 저장합니다. 기본 경로는 `data/runtime/daily/ridership/`입니다.

`SEOUL_PSGR_KEY`를 설정하고 `python -m back.pipelines.refresh --ridership`으로 갱신합니다. 날짜 범위와 모델 갱신은 [상위 문서](../README.md)를 참고하세요. 과거 월별 CSV 다운로드 도구는 [`archive/back/scripts/ridership_etl/`](../../../archive/back/scripts/ridership_etl/)에 보관했습니다.
