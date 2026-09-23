"""
아리수 역사별 수도 사용 내역 크롤러

서울시 아리수 홈페이지에서 지하철 역사별 고지서 상세 내역을 엑셀로 다운로드.
연도 단위로 최신→과거 방향으로 순회하며 데이터가 없을 때 종료.

출력: data/arisu_station_history/raw/{역명}_{시작월}~{종료월}.xls
실행: python back/scripts/arisu_history/crawl.py
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dateutil.relativedelta import relativedelta

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from back.pipelines.common import RUNTIME, atomic_bytes, collector_meters, today
from back.scripts.billing_etl.i121_crawler.auth import session_from_env, _looks_like_login_page, LoginError

RAW_DIR = RUNTIME / "raw" / "arisu_station_history"


CHECK_URL = "https://i121.seoul.go.kr/cs/cyber/front/mypage/PR_jsGumchimDetail.do"
EXCEL_URL = "https://i121.seoul.go.kr/cs/cyber/report/NR_gumchimDetailExcelDown.do"


def make_session() -> requests.Session:
    return session_from_env(ROOT / ".env")


def get_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response:
    # The authenticated session's HTTPAdapter handles transient retries.
    response = session.get(url, timeout=30, **kwargs)
    response.raise_for_status()
    if _looks_like_login_page(response.text):
        raise LoginError("Arisu session expired")
    return response


def crawl(session: requests.Session, name: str, mkey: str) -> None:
    print(f"\n▶ {name}")
    end_ym = datetime.combine(today().replace(day=1), datetime.min.time())

    while True:
        start_ym = end_ym - relativedelta(years=1)
        start_str = start_ym.strftime("%Y-%m")
        end_str   = end_ym.strftime("%Y-%m")

        check = get_with_retry(session, CHECK_URL, params={
            "searchStartYm": start_str,
            "searchEndYm":   end_str,
            "searchMkey":    mkey,
            "searchFlag":    "Y",
        })

        if "조회된 결과가 없습니다" in check.text:
            print(f"  ⛔ {start_str}~{end_str} 데이터 없음, 종료")
            break
        if "일별 자료 보기" not in check.text:
            raise ValueError("Unexpected Arisu history response")

        xls = get_with_retry(session, EXCEL_URL, params={
            "searchStartYm": start_str,
            "searchEndYm":   end_str,
            "searchMkey":    mkey,
            "searchFlag":    "",
        })

        fname = RAW_DIR / f"{name}_{start_str}~{end_str}.xls"
        if not xls.content:
            raise ValueError("Empty Arisu history download")
        atomic_bytes(fname, xls.content)
        print(f"  ☑️ {start_str}~{end_str} 저장 ({len(xls.content):,} bytes)")

        end_ym = start_ym
        time.sleep(1)


if __name__ == "__main__":
    session = make_session()
    for meter in collector_meters():
        crawl(session, meter["customer_number"], meter["customer_number"])
