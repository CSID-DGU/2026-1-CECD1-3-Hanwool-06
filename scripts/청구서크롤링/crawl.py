"""모든 m_key 청구서 HTML 크롤링 (2단계)."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path

from auth import session_from_env
from bill_parser import parse_bill_list
from fetch import fetch_bill_window, shift_month


FIELDNAMES = [
    "mkey",
    "sunbeon",
    "gubun",
    "napgi",
    "napgi_compact",
    "sunap_status",
    "bugwa_amount_won",
    "total_usage_ton",
    "station_from_address",
    "address",
]


def run(
    mkeys: list[str],
    cache_dir: Path,
    out_dir: Path,
    env_path: Path,
    *,
    sleep: float = 1.5,
    floor_year: int = 2008,
    max_windows_per_mkey: int = 30,
    end_ym: str | None = None,
) -> tuple[Path, Path]:
    """미터별 12개월 윈도우 역방향 크롤링 → bills_long.csv 저장."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = session_from_env(env_path=env_path if env_path.exists() else None)
    print(f"  [crawl] 로그인 성공 — {len(mkeys)} 개 m_key 크롤링 시작")

    today = datetime.now()
    start_end_ym = end_ym or f"{today.year:04d}-{today.month:02d}"

    seen: set[tuple[str, str]] = set()
    all_bills: list[dict] = []
    summary: dict[str, dict] = {}
    fetches_live = 0
    fetches_cached = 0

    for index, mkey in enumerate(mkeys, 1):
        per_count = 0
        per_windows = 0
        oldest: str | None = None
        latest: str | None = None
        cur_end = start_end_ym

        for _ in range(max_windows_per_mkey):
            start_ym = shift_month(cur_end, -11)
            if int(start_ym.split("-")[0]) < floor_year:
                break

            try:
                html, was_cached = fetch_bill_window(
                    session, mkey, start_ym, cur_end, cache_dir
                )
            except Exception as exc:
                print(
                    f"    [{index}/{len(mkeys)}] mkey={mkey} {start_ym}~{cur_end} "
                    f"FAIL: {type(exc).__name__}: {exc}",
                    flush=True,
                )
                break

            per_windows += 1
            if was_cached:
                fetches_cached += 1
            else:
                fetches_live += 1
                time.sleep(sleep)

            bills = parse_bill_list(html)
            if not bills:
                break

            for bill in bills:
                key = (
                    bill["mkey"],
                    bill.get("napgi_compact") or bill.get("napgi") or "",
                )
                if key in seen:
                    continue
                seen.add(key)
                all_bills.append(bill)
                per_count += 1
                napgi = bill.get("napgi")
                if napgi:
                    if oldest is None or napgi < oldest:
                        oldest = napgi
                    if latest is None or napgi > latest:
                        latest = napgi

            cur_end = shift_month(start_ym, -1)

        summary[mkey] = {
            "bills": per_count,
            "windows": per_windows,
            "oldest_napgi": oldest,
            "latest_napgi": latest,
        }
        print(
            f"    [{index:2d}/{len(mkeys)}] mkey={mkey} "
            f"bills={per_count:3d} windows={per_windows:2d} range={oldest}~{latest}",
            flush=True,
        )

    csv_path = out_dir / "bills_long.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDNAMES)
        writer.writeheader()
        for bill in sorted(
            all_bills, key=lambda b: (b["mkey"], b.get("napgi_compact") or "")
        ):
            writer.writerow({k: bill.get(k) for k in FIELDNAMES})

    summary_path = out_dir / "crawl_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [crawl] {len(all_bills):,} 건 저장 → {csv_path}")
    print(f"  [crawl] fetches: live={fetches_live} cached={fetches_cached}")
    return csv_path, summary_path
