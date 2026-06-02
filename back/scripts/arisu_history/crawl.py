"""
아리수 역사별 수도 사용 내역 크롤러

서울시 아리수 홈페이지에서 지하철 역사별 고지서 상세 내역을 엑셀로 다운로드.
연도 단위로 최신→과거 방향으로 순회하며 데이터가 없을 때 종료.

출력: data/arisu_station_history/raw/{역명}_{시작월}~{종료월}.xls
실행: python back/scripts/arisu_history/crawl.py
"""

import os
import time
from datetime import datetime
from pathlib import Path

import requests
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

USER_ID  = os.getenv("ARISU_USER_ID")
USER_PWD = os.getenv("ARISU_USER_PWD")

RAW_DIR = ROOT / "data" / "arisu_station_history" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

CUSTOMER_MAP = {
    "1호선동대문역":              "000013307",
    "경복궁역":                   "000017682",
    "지하철역장":                  "000137601",
    "안국지하철역":                "000214696",
    "혜화역":                     "000248906",
    "시청1역":                    "000252579",
    "신당지하철역(2호선)":         "000262188",
    "지하철동대입구":              "000266613",
    "을지로3가2역":               "000315938",
    "을지3가3호선":               "000316239",
    "5호선 을지로4가역":           "000342971",
    "지하철공사약수역(3호선)":      "000362246",
    "시청2역":                    "000390183",
    "명동역장":                   "000399808",
    "왕십리역":                   "000451150",
    "상봉역":                     "000828353",
    "아차산역":                   "000978203",
    "군자역(5)":                  "001159721",
    "성신여대역":                  "001506473",
    "길음역":                     "001703793",
    "쌍문역":                     "001895650",
    "상계역장":                   "002296399",
    "미아역":                     "002956726",
    "답십리역":                   "004769658",
    "장한평역":                   "004779648",
    "5호선 동대문역사문화공원역":   "006205316",
    "동대문역사문화공원2역":        "006240178",
    "동대문역사문화공원(4역)":      "006240196",
    "행당역":                     "006390427",
    "사가정역":                   "006499412",
    "먹골역":                     "006735213",
    "어린이대공원역":              "006742276",
    "건대입구역":                  "006743375",
    "신정네거리역 역무실":          "020681438",
    "방화역":                     "021091226",
    "신용산역":                   "021205524",
    "삼성지하철":                  "022277395",
    "학여울역":                   "022357530",
    "대청역":                     "022652784",
    "신도림역":                   "023011906",
    "방이역":                     "023654087",
    "석촌역":                     "023726393",
    "굽은다리역":                  "024167685",
    "잠실새내역":                  "024583082",
    "총신대입구역":                "024630785",
    "이대역사":                   "024635854",
    "대치역":                     "024655212",
    "강동역":                     "024666597",
    "고속터미널역":                "024691164",
    "마포역":                     "026547747",
    "까치산역":                   "027579083",
    "영등포구청역":                "029689088",
    "양평역":                     "029874620",
    "문정역":                     "030154123",
    "복정역":                     "030179738",
    "길동역":                     "030632270",
    "암사역":                     "031750442",
    "온수역":                     "031829466",
    "신풍역":                     "031834359",
    "천왕역":                     "031842931",
    "석계역":                     "031914399",
    "응암역":                     "031921584",
    "서울교통공사(석관동)":        "031928061",
    "증산역":                     "032013846",
    "창신역":                     "032026818",
    "삼각지역":                   "032072396",
    "녹사평역":                   "032082173",
    "보문역":                     "032086710",
    "버티고개역":                  "032121991",
    "이태원역":                   "032125776",
    "약수역":                     "032144824",
    "월드컵경기장(성산)역":        "032864224",
    "서울교통공사(보문동)":        "032909986",
    "동묘역(1호선)":              "035270286",
    "서울대입구역":                "035438586",
    "역삼역":                     "035487398",
    "지하철2호 왕십리역":          "035833138",
    "경찰병원역":                  "036081434",
    "강일역":                     "041559288",
    "암사역사공원역":              "042547672",
}

LOGIN_URL = "https://i121.seoul.go.kr/cs/cyber/front/login/AR_loginAction.do"
CHECK_URL = "https://i121.seoul.go.kr/cs/cyber/front/mypage/PR_jsGumchimDetail.do"
EXCEL_URL = "https://i121.seoul.go.kr/cs/cyber/report/NR_gumchimDetailExcelDown.do"


RETRY_DELAYS = [5, 15, 30]  # 재시도 대기 시간(초)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    s.post(LOGIN_URL, data={"userId": USER_ID, "userPwd": USER_PWD})
    return s


def get_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response:
    for attempt, delay in enumerate(RETRY_DELAYS, 1):
        try:
            return session.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  요청 실패 ({attempt}/{len(RETRY_DELAYS)}): {e!r} — {delay}초 후 재시도")
            time.sleep(delay)
            session = make_session()  # 세션 재로그인
    return session.get(url, **kwargs)  # 마지막 시도, 실패 시 예외 전파


def crawl(session: requests.Session, name: str, mkey: str) -> None:
    print(f"\n▶ {name}")
    end_ym = datetime.today().replace(day=1)

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

        if "조회된 결과가 없습니다" in check.text or "일별 자료 보기" not in check.text:
            print(f"  ⛔ {start_str}~{end_str} 데이터 없음, 종료")
            break

        xls = get_with_retry(session, EXCEL_URL, params={
            "searchStartYm": start_str,
            "searchEndYm":   end_str,
            "searchMkey":    mkey,
            "searchFlag":    "",
        })

        fname = RAW_DIR / f"{name}_{start_str}~{end_str}.xls"
        fname.write_bytes(xls.content)
        print(f"  ☑️ {start_str}~{end_str} 저장 ({len(xls.content):,} bytes)")

        end_ym = start_ym
        time.sleep(1)


if __name__ == "__main__":
    for f in RAW_DIR.glob("*.xls"):
        f.unlink()
    print(f"raw/ 초기화 완료 ({RAW_DIR})\n")

    session = make_session()
    for name, mkey in CUSTOMER_MAP.items():
        crawl(session, name, mkey)
