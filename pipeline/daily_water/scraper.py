"""
아리수 일별 사용량 스크래퍼

기본 동작: 어제 날짜(today - 1일) 데이터를 수집해 data/daily/YYYY-MM-DD.csv 로 저장.
직접 실행 시 날짜를 인자로 줄 수 있음:
    python scraper.py              # 어제 데이터
    python scraper.py 2026-05-26   # 특정 날짜
"""

import os
import re
import csv
import time
import argparse
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 프로젝트 루트 기준으로 .env 로드
ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

USER_ID  = os.getenv("ARISU_USER_ID")
USER_PWD = os.getenv("ARISU_USER_PWD")

DAILY_DIR = ROOT / "data" / "daily" / "water"
DAILY_DIR.mkdir(parents=True, exist_ok=True)

CUSTOMER_MAP = {
    "강동역":                   "024666597",
    "강일역":                   "041559288",
    "건대입구역7":               "006743375",
    "경복궁역":                  "000017682",
    "경찰병원역":                "036081434",
    "고속터미널역3":              "024691164",
    "군자역5":                   "001159721",
    "굽은다리역":                "024167685",
    "길동역":                   "030632270",
    "길음역":                   "001703793",
    "까치산역5":                 "027579083",
    "녹사평역":                  "032082173",
    "답십리역":                  "004769658",
    "대청역":                   "022652784",
    "대치역":                   "024655212",
    "돌곶이역":                  "031928061",
    "동대문역1":                 "000013307",
    "동대문역사문화공원역2":       "006240178",
    "동대문역사문화공원역4":       "006240196",
    "동대문역사문화공원역5":       "006205316",
    "동대입구역":                "000266613",
    "동묘앞역1":                 "035270286",
    "마포역":                   "026547747",
    "먹골역":                   "006735213",
    "명동역":                   "000399808",
    "문정역":                   "030154123",
    "미아역":                   "002956726",
    "방이역":                   "023654087",
    "방화역":                   "021091226",
    "버티고개역":                "032121991",
    "보문역":                   "032086710",
    "복정역":                   "030179738",
    "사가정역":                  "006499412",
    "삼각지역6":                 "032072396",
    "삼성역":                   "022277395",
    "상계역":                   "002296399",
    "상봉역":                   "000828353",
    "서울대입구역":              "035438586",
    "석계역":                   "031914399",
    "석촌역":                   "023726393",
    "성신여대입구역":             "001506473",
    "시청역1":                  "000252579",
    "시청역2":                  "000390183",
    "신당역2":                  "000262188",
    "신도림역":                  "023011906",
    "신용산역":                  "021205524",
    "신정네거리역":              "020681438",
    "신풍역":                   "031834359",
    "쌍문역":                   "001895650",
    "아차산역":                  "000978203",
    "안국역":                   "000214696",
    "암사역":                   "031750442",
    "암사역사공원역":             "042547672",
    "약수역3":                  "000362246",
    "약수역6":                  "032144824",
    "양평역":                   "029874620",
    "어린이대공원역":             "006742276",
    "영등포구청역5":              "029689088",
    "온수역":                   "031829466",
    "왕십리역2":                 "035833138",
    "왕십리역5":                 "000451150",
    "월드컵경기장역":             "032864224",
    "을지로3가역2":              "000315938",
    "을지로3가역3":              "000316239",
    "을지로4가역5":              "000342971",
    "응암역":                   "031921584",
    "이대역":                   "024635854",
    "이태원역":                  "032125776",
    "잠실새내역":                "024583082",
    "장한평역":                  "004779648",
    "종로3가역3":                "000137601",
    "증산역":                   "032013846",
    "창신역":                   "032026818",
    "총신대입구(이수)역4":        "024630785",
    "학여울역":                  "022357530",
    "행당역":                   "006390427",
    "혜화역":                   "000248906",
}


def login() -> requests.Session:
    if not USER_ID or not USER_PWD:
        raise ValueError(".env 파일에 ARISU_USER_ID / ARISU_USER_PWD 가 설정되지 않았습니다.")

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        )
    })
    session.post(
        "https://i121.seoul.go.kr/cs/cyber/front/login/AR_loginAction.do",
        data={"userId": USER_ID, "userPwd": USER_PWD},
        allow_redirects=True,
    )
    return session


def fetch_station(session: requests.Session, name: str, mkey: str,
                  target_date: date) -> list[list]:
    """
    특정 역의 target_date 가 포함된 납기 데이터를 가져온다.
    아리수 사이트는 월 단위로 조회되므로 해당 월을 요청한다.
    """
    ym = target_date.strftime("%Y-%m")
    resp = session.get(
        "https://i121.seoul.go.kr/cs/cyber/front/mypage/NR_myArisu.do",
        params={
            "searchMkey":    mkey,
            "searchStartYm": ym,
            "searchEndYm":   ym,
            "isSearch":      "Y",
            "searchGumChim": "Y",
            "_m":            "m6_1",
        },
    )

    soup = BeautifulSoup(resp.text, "html.parser")
    target_str = target_date.strftime("%Y-%m-%d")
    seen, rows = set(), []

    for td in soup.find_all("td", class_=re.compile(r'^\d{8}View$')):
        tr = td.find_parent("tr")
        if tr is None or id(tr) in seen:
            continue
        seen.add(id(tr))

        napgi_cls = next((c for c in td.get("class", []) if re.match(r'^\d{8}View$', c)), "")
        napgi = napgi_cls.replace("View", "")
        napgi_fmt = f"{napgi[:4]}-{napgi[4:6]}-{napgi[6:]}"

        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        row = [name, napgi_fmt] + cells

        # 사용일(cells[0])이 target_date 인 행만 필터
        if len(cells) >= 1 and cells[0] == target_str:
            rows.append(row)

    return rows


def scrape(target_date: date | None = None) -> Path:
    """
    target_date 의 전체 역 사용량을 수집해 CSV로 저장하고 경로를 반환.
    target_date 기본값: 어제
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    out_path = DAILY_DIR / f"{target_date}.csv"
    if out_path.exists():
        print(f"이미 수집된 파일: {out_path}")
        return out_path

    print(f"수집 대상 날짜: {target_date}")
    session = login()
    skipped = []

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["역명", "납기", "사용일", "검침일자", "지침값",
                         "일사용량(톤)", "납기별누적사용량(톤)"])

        for name, mkey in CUSTOMER_MAP.items():
            rows = fetch_station(session, name, mkey, target_date)
            if rows:
                writer.writerows(rows)
                print(f"  ✅ {name} ({len(rows)}행)")
            else:
                skipped.append(name)
                print(f"  ⚠️  {name} — {target_date} 데이터 없음 (아직 미업로드이거나 해당없음)")
            time.sleep(0.4)

    print(f"\n저장 완료: {out_path}")
    if skipped:
        print(f"데이터 없음 ({len(skipped)}개): {', '.join(skipped)}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="아리수 일별 사용량 수집")
    parser.add_argument("date", nargs="?", help="수집 날짜 YYYY-MM-DD (기본: 어제)")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else None
    scrape(target)
