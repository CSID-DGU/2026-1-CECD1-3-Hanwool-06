"""서울 열린데이터광장 월별 승하차 파일(OA-12914)로 지난 날짜의 승하차를 채운다.

일별 API(scraper.py)는 최근 1주일치만 주므로, 그보다 오래된 날짜는 이 월별 파일이 유일한 원천이다.
인증키는 필요 없다. 출력은 scraper.py 와 같다: APP_DATA_DIR/daily/ridership/<YYYY-MM-DD>.csv

    python -m back.pipelines.daily_ridership.monthly 2026-05 2026-08

집계 기준은 같은 원천으로 만든 data/processed/ridership.csv 와 같다. 검토 매핑(meter_match.csv)에
호선이 비어 있는 계량기는 같은 이름의 역 전체 합계를, 호선이 있는 계량기와 새 계량기는 그 호선만 쓴다.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import requests

from back.pipelines.common import ROOT, RUNTIME, atomic_bytes, collection_lock, collector_meters, customer_number
from back.pipelines.daily_ridership.scraper import _normalize_station, _parse_line, scrape
from back.scripts.billing_etl.i121_crawler.fetch import shift_month

LIST_URL = "https://data.seoul.go.kr/dataList/OA-12914/F/1/datasetView.do"
DOWNLOAD_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?useCache=false"
RAW_DIR = RUNTIME / "raw" / "ridership_monthly"
MATCH = ROOT / "data" / "billing" / "meter_match.csv"


def published_months(session) -> dict[str, str]:
    """{'2026-05': 내려받기 번호}. 아직 올라오지 않은 달은 들어 있지 않다."""
    page = session.get(LIST_URL, timeout=60)
    page.raise_for_status()
    found = re.findall(r"downloadFile\('(\d+)'\)[^>]*>CARD_SUBWAY_MONTH_(\d{4})(\d{2})\.csv", page.text)
    return {f"{year}-{month}": seq for seq, year, month in found}


def download_month(month: str, seq: str, session, raw_dir=None) -> Path:
    """한 달 파일을 받아 둔다. 이미 받은 달은 다시 받지 않는다."""
    path = Path(raw_dir or RAW_DIR) / f"CARD_SUBWAY_MONTH_{month.replace('-', '')}.csv"
    if path.exists():
        return path
    response = session.post(DOWNLOAD_URL, timeout=120, headers={"Referer": LIST_URL, "Origin": "https://data.seoul.go.kr"},
                            data={"infId": "OA-12914", "infSeq": "3", "seqNo": seq, "seq": seq})
    response.raise_for_status()
    if response.content.lstrip()[:1] == b"<":
        raise ValueError("Monthly ridership download returned a page instead of a CSV file")
    atomic_bytes(path, response.content)
    return path


def read_month(path) -> dict:
    """{YYYYMMDD: ((역, 호선)별 합계, 역별 합계)}. 승차와 하차를 더한다."""
    content = Path(path).read_bytes()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp949")  # 2022년 이전 파일
    days = defaultdict(lambda: (defaultdict(int), defaultdict(int)))
    for row in csv.DictReader(text.splitlines()):
        if not re.fullmatch(r"\d{8}", row["사용일자"]):
            raise ValueError("Unexpected date in monthly ridership file")
        ride, alight = int(row["승차총승객수"]), int(row["하차총승객수"])
        if ride < 0 or alight < 0:
            raise ValueError("Negative ridership count")
        station = _normalize_station(row["역명"])
        byline, bystn = days[row["사용일자"]]
        byline[(station, _parse_line(row["노선명"]))] += ride + alight
        bystn[station] += ride + alight
    return days


def monthly_meters(registered=None) -> list[dict]:
    """등록 계량기에 기존 정제 자료와 같은 집계 기준을 입힌다(호선을 지우면 역 전체 합계를 쓴다)."""
    with MATCH.open(encoding="utf-8-sig", newline="") as fp:
        whole_station = {customer_number(row["고객번호"]) for row in csv.DictReader(fp) if not row["호선"]}
    return [meter | {"line": None} if customer_number(meter["customer_number"]) in whole_station else meter
            for meter in collector_meters(registered)]


def import_month(path, *, meters=None, out_dir=None) -> list[str]:
    """한 달 파일을 날짜별 파일로 풀어 쓴다. 같은 고객·날짜의 기존 행은 새 값으로 바뀐다."""
    meters = monthly_meters(meters)
    written = []
    for ymd, totals in sorted(read_month(path).items()):
        day = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
        if scrape(day, meters=meters, out_dir=out_dir, fetcher=lambda _key, _ymd, totals=totals: totals):
            written.append(str(day))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("start", help="첫 달 YYYY-MM")
    parser.add_argument("end", nargs="?", help="마지막 달 YYYY-MM (생략하면 첫 달만)")
    args = parser.parse_args()
    end = args.end or args.start
    for month in (args.start, end):
        date.fromisoformat(month + "-01")
    if args.start > end:
        parser.error("첫 달이 마지막 달보다 늦습니다.")
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    published = published_months(session)
    missing = False
    month = args.start
    with collection_lock(RUNTIME):
        while month <= end:
            if month in published:
                days = import_month(download_month(month, published[month], session))
                print(f"{month}: {len(days)}일치 저장 ({days[0]} ~ {days[-1]})" if days else f"{month}: 저장한 날짜 없음")
            else:
                print(f"{month}: 아직 올라오지 않은 달입니다.")
                missing = True
            month = shift_month(month, 1)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
