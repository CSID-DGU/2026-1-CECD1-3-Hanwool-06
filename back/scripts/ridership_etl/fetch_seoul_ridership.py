#!/usr/bin/env python3
"""Download Seoul Open Data subway ridership monthly CSV files.

Source: data.seoul.go.kr OA-12914 (서울시 지하철호선별 역별 승하차 인원 정보)
- 2015 ~ 2022 annual files
- 2023-01 onward monthly files
- Direct CSV download via POST (no API key required)

Outputs:
    data/raw/ridership/seoul_api/raw/CARD_SUBWAY_MONTH_*.csv  (cached, resume-capable)
    data/raw/ridership/seoul_api/file_index.csv               (seqNo ↔ filename map)
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATASET_ID = "OA-12914"
INF_SEQ = "3"
LIST_PAGE_URL = f"https://data.seoul.go.kr/dataList/{DATASET_ID}/F/1/datasetView.do"
DOWNLOAD_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?useCache=false"

DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "raw" / "ridership" / "seoul_api" / "raw"
DEFAULT_INDEX_PATH = PROJECT_ROOT / "data" / "raw" / "ridership" / "seoul_api" / "file_index.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

DOWNLOAD_HEADERS = {
    **HEADERS,
    "Referer": LIST_PAGE_URL,
    "Origin": "https://data.seoul.go.kr",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--min-year", type=int, default=2022,
                        help="skip files older than this year (default 2022 = our daily start)")
    parser.add_argument("--max-files", type=int, default=0,
                        help="if >0, limit number of downloads (debug)")
    parser.add_argument("--sleep", type=float, default=1.5,
                        help="seconds to sleep between live downloads")
    parser.add_argument("--force", action="store_true",
                        help="re-download even if cached")
    return parser.parse_args()


def fetch_file_index(session: requests.Session) -> list[dict]:
    """Scrape the dataset page and return list of {seq_no, filename, year_month}."""
    response = session.get(LIST_PAGE_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    pattern = re.compile(r"downloadFile\('(\d+)'\)[^>]*>(CARD_SUBWAY_MONTH_(\d+)\.csv)")
    found: dict[str, dict] = {}
    for seq_no, filename, suffix in pattern.findall(response.text):
        if seq_no in found:
            continue
        if len(suffix) == 4:
            year = int(suffix)
            month = None
            key_date = f"{year:04d}-00"
        elif len(suffix) == 6:
            year = int(suffix[:4])
            month = int(suffix[4:6])
            key_date = f"{year:04d}-{month:02d}"
        else:
            continue
        found[seq_no] = {
            "seq_no": seq_no,
            "filename": filename,
            "year": year,
            "month": month,
            "key_date": key_date,
        }
    return sorted(found.values(), key=lambda x: (x["year"], x["month"] or 0))


def download_one(
    session: requests.Session,
    seq_no: str,
    filename: str,
    out_dir: Path,
    *,
    force: bool,
    timeout: float = 60.0,
) -> tuple[Path, bool]:
    """Download a single CSV. Returns (path, was_cached)."""
    out_path = out_dir / filename
    if out_path.exists() and not force:
        return out_path, True
    response = session.post(
        DOWNLOAD_URL,
        headers=DOWNLOAD_HEADERS,
        data={
            "infId": DATASET_ID,
            "infSeq": INF_SEQ,
            "seqNo": seq_no,
            "seq": seq_no,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = response.content
    if content[:6] == b"<html>" or b"<script" in content[:200]:
        raise RuntimeError(f"download blocked for seq={seq_no}; response was HTML")
    out_path.write_bytes(content)
    return out_path, False


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.index_path.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    print(f"[1/3] scraping file index from {LIST_PAGE_URL} ...", flush=True)
    index = fetch_file_index(session)
    print(f"  found {len(index)} files (range "
          f"{index[0]['key_date']} ~ {index[-1]['key_date']})", flush=True)

    eligible = [item for item in index if item["year"] >= args.min_year]
    if args.max_files > 0:
        eligible = eligible[: args.max_files]
    print(f"[2/3] downloading {len(eligible)} files (year >= {args.min_year}) ...", flush=True)

    rows_for_index: list[dict] = []
    live = 0
    cached = 0
    for idx, item in enumerate(eligible, 1):
        try:
            out_path, was_cached = download_one(
                session, item["seq_no"], item["filename"], args.out_dir,
                force=args.force,
            )
        except Exception as exc:
            print(f"  [{idx}/{len(eligible)}] FAIL {item['filename']}: {type(exc).__name__}: {exc}",
                  flush=True)
            continue
        size_kb = out_path.stat().st_size / 1024 if out_path.exists() else 0
        tag = "CACHE" if was_cached else "LIVE "
        print(f"  [{idx}/{len(eligible)}] {tag} {item['filename']} "
              f"({size_kb:,.0f} KB)", flush=True)
        if was_cached:
            cached += 1
        else:
            live += 1
            time.sleep(args.sleep)
        rows_for_index.append(
            {
                "seq_no": item["seq_no"],
                "filename": item["filename"],
                "year": item["year"],
                "month": item["month"] or "",
                "key_date": item["key_date"],
                "size_bytes": out_path.stat().st_size if out_path.exists() else 0,
            }
        )

    import csv
    with args.index_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["seq_no", "filename", "year", "month", "key_date", "size_bytes"])
        writer.writeheader()
        writer.writerows(rows_for_index)

    print(f"[3/3] done. live={live} cached={cached}", flush=True)
    print(f"  index → {args.index_path.relative_to(PROJECT_ROOT)}")
    print(f"  raw dir → {args.out_dir.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
