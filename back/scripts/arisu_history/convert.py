"""
아리수 역사별 엑셀 → CSV 변환기

crawl.py 로 수집한 XLS 파일을 역별 CSV로 변환.
  - 역별 분리: data/arisu_station_history/{역명}.csv

실행: python back/scripts/arisu_history/convert.py
"""

import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT    = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "arisu_station_history" / "raw"
OUT_DIR = ROOT / "data" / "arisu_station_history"

# 파일명 끝의 날짜 범위 패턴 (예: _2024-05~2025-05)
_DATE_SUFFIX = re.compile(r"_\d{4}-\d{2}~\d{4}-\d{2}$")

# 크롤링 시 사용한 이름 → 확정 역명 매핑
NAME_MAP: dict[str, str] = {
    "1호선동대문역":              "동대문역1",
    "지하철역장":                  "종로3가역3",
    "안국지하철역":                "안국역",
    "시청1역":                    "시청역1",
    "신당지하철역(2호선)":         "신당역2",
    "지하철동대입구":              "동대입구역",
    "을지로3가2역":               "을지로3가역2",
    "을지3가3호선":               "을지로3가역3",
    "5호선 을지로4가역":           "을지로4가역5",
    "지하철공사약수역(3호선)":      "약수역3",
    "시청2역":                    "시청역2",
    "명동역장":                   "명동역",
    "왕십리역":                   "왕십리역5",
    "군자역(5)":                  "군자역5",
    "성신여대역":                  "성신여대입구역",
    "상계역장":                   "상계역",
    "5호선 동대문역사문화공원역":   "동대문역사문화공원역5",
    "동대문역사문화공원2역":        "동대문역사문화공원역2",
    "동대문역사문화공원(4역)":      "동대문역사문화공원역4",
    "건대입구역":                  "건대입구역7",
    "신정네거리역 역무실":          "신정네거리역",
    "삼성지하철":                  "삼성역",
    "총신대입구역":                "총신대입구(이수)역4",
    "이대역사":                   "이대역",
    "고속터미널역":                "고속터미널역3",
    "까치산역":                   "까치산역5",
    "영등포구청역":                "영등포구청역5",
    "서울교통공사(석관동)":        "돌곶이역",
    "삼각지역":                   "삼각지역6",
    "약수역":                     "약수역6",
    "월드컵경기장(성산)역":        "월드컵경기장역",
    "서울교통공사(보문동)":        "보문역-직원용",
    "동묘역(1호선)":              "동묘앞역1",
    "지하철2호 왕십리역":          "왕십리역2",
}


def station_from(fpath: Path) -> str:
    """파일명에서 역명 추출 후 확정 역명으로 변환."""
    raw = _DATE_SUFFIX.sub("", fpath.stem)
    return NAME_MAP.get(raw, raw)


def load_xls(fpath: Path, station: str) -> pd.DataFrame | None:
    try:
        df = pd.read_html(fpath, encoding="utf-8")[1]
        df.insert(0, "역명", station)
        return df
    except Exception as e:
        print(f"  ❌ {fpath.name} 실패: {e}")
        return None


def merge_by_station(files: list[Path]) -> None:
    station_files: dict[str, list[Path]] = defaultdict(list)
    for fpath in files:
        station_files[station_from(fpath)].append(fpath)

    for station, fpaths in station_files.items():
        dfs = [df for fpath in sorted(fpaths) if (df := load_xls(fpath, station)) is not None]
        if not dfs:
            continue

        result = pd.concat(dfs, ignore_index=True)
        result = result.drop_duplicates()
        result = result.sort_values("검침일자").reset_index(drop=True)

        out = OUT_DIR / f"{station}.csv"
        result.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"  ☑️ {station}.csv ({len(result):,}행)")


if __name__ == "__main__":
    xls_files = sorted(RAW_DIR.glob("*.xls"))
    if not xls_files:
        print(f"XLS 파일이 없습니다: {RAW_DIR}")
        raise SystemExit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUT_DIR.glob("*.csv"):
        f.unlink()
    print(f"출력 디렉토리 초기화 완료 ({OUT_DIR})\n")

    merge_by_station(xls_files)
    print(f"\n☑️ 역별 저장 완료: {OUT_DIR.relative_to(ROOT)}/")
