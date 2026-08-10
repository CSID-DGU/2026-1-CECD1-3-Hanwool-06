"""서울교통공사 역별승하차 API → 일별 역 총승객수(모델 입력 형식) 수집.

소스 : 공공데이터포털 B553766  getStnPsgr
키   : .env 의 SEOUL_PSGR_KEY (포털 Encoding 키 — URL 에 그대로 붙임, 재인코딩 금지)
출력 : data/daily/ridership/<YYYY-MM-DD>.csv  (고객번호, 역명, 날짜, 총승객수)

집계: 응답은 일자×시간×권종×사용자구분별 승차(rideNope)/하차(gffNope) → 역·호선별 전부 합산.
매칭: API stnNm 은 부역명 '(...)' 을 달고 '역' 이 없으므로 정규화해 meter_match 와 맞춘다.
      환승역은 호선별(모델 역명이 base+호선숫자). 호선 공란 미터는 단일호선이라 역 총합=그 호선.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENDPOINT = "https://apis.data.go.kr/B553766/psgr/getStnPsgr"
METER_MATCH = PROJECT_ROOT / "data" / "billing" / "meter_match.csv"
OUT_DIR = PROJECT_ROOT / "data" / "daily" / "ridership"
NUM_OF_ROWS = 1000   # 하루 ≈ 66k행 → ~66콜/일 (일일한도 10,000)


def _load_key() -> str:
    for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("SEOUL_PSGR_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("SEOUL_PSGR_KEY 가 .env 에 없음")


def _normalize_station(name: str) -> str:
    """API/우리 역명을 공통 키로: 부역명 '(...)' · 끝 숫자 · 끝 '역' 제거."""
    s = re.sub(r"\(.*?\)", "", str(name).strip())
    s = re.sub(r"\d+$", "", s)
    return re.sub(r"역$", "", s)


def _parse_line(line_name: str) -> int | None:
    m = re.match(r"(\d+)호선", str(line_name))
    return int(m.group(1)) if m else None


def _load_meters() -> list[dict]:
    """meter_match → [{고객번호(int), 역명(모델형식), key역(정규화), 호선(int|None)}]."""
    meters = []
    with open(METER_MATCH, encoding="utf-8-sig") as fp:
        for row in csv.DictReader(fp):
            base = row["역명"].strip()
            ln = row["호선"].strip()
            line = int(float(ln)) if ln else None
            model_name = f"{base}{line}" if line else base   # ml_dataset 형식
            meters.append({
                "고객번호": int(str(row["고객번호"]).strip()),
                "역명": model_name,
                "key역": _normalize_station(base),
                "호선": line,
            })
    return meters


def _fetch_day(key: str, ymd: str) -> tuple[dict, dict]:
    """하루치를 받아 (역·호선)별·(역)별 총승객수를 만든다. 미적재면 ({}, {})."""
    def call(page: int, retries: int = 3) -> dict:
        url = (f"{ENDPOINT}?serviceKey={key}&pageNo={page}"
               f"&numOfRows={NUM_OF_ROWS}&dataType=JSON&pasngYmd={ymd}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        for attempt in range(1, retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError):
                if attempt == retries:
                    raise
                time.sleep(3)  # 일시적 SSL/네트워크 오류 재시도 (67콜 중 1건 타임아웃에 하루 전체가 죽는 것 방지)

    body = call(1)["response"]["body"]
    total = int(body["totalCount"])
    if total == 0 or body["items"] in ("", None):
        return {}, {}
    items = body["items"]["item"]
    if isinstance(items, dict):
        items = [items]
    pages = -(-total // len(items))

    byline: dict = defaultdict(int)
    bystn: dict = defaultdict(int)
    for page in range(1, pages + 1):
        rows = items if page == 1 else call(page)["response"]["body"]["items"]["item"]
        if isinstance(rows, dict):
            rows = [rows]
        for it in rows:
            n = _normalize_station(it["stnNm"])
            v = int(it["rideNope"]) + int(it["gffNope"])
            byline[(n, _parse_line(it["lineNm"]))] += v
            bystn[n] += v
    return byline, bystn


def scrape(target_date: date) -> Path | None:
    """하루치 수집 → data/daily/ridership/<date>.csv 저장 후 경로 반환. 미적재면 None."""
    key = _load_key()
    meters = _load_meters()
    byline, bystn = _fetch_day(key, target_date.strftime("%Y%m%d"))
    if not bystn:
        return None   # 아직 미적재(범위 밖/미게시)

    iso = target_date.strftime("%Y-%m-%d")
    rows = []
    for m in meters:
        total = byline.get((m["key역"], m["호선"])) if m["호선"] is not None else bystn.get(m["key역"])
        if total is None:
            print(f"  ⚠ {m['역명']}(고객 {m['고객번호']}) API 매칭 실패")
            continue
        rows.append({"고객번호": m["고객번호"], "역명": m["역명"], "날짜": iso, "총승객수": int(total)})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{iso}.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["고객번호", "역명", "날짜", "총승객수"])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["고객번호"]))
    return path
