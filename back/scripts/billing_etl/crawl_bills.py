#!/usr/bin/env python3
"""Crawl all bills for every mkey using backward 1-year windows.

For each mkey:
  - Start from end_ym = today (YYYY-MM) and step backwards by 12-month windows.
  - Stop when a window returns no bills (empty 부과내역 table).
  - Raw HTML is cached so re-runs skip already-fetched windows.

Outputs:
  data/raw/billing_i121/i121_bills/bills_long.csv   one row per bill, sorted by (mkey, napgi)
  data/raw/billing_i121/i121_bills/crawl_summary.json  per-mkey stats
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw" / "billing_i121"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from i121_crawler.auth import session_from_env  # noqa: E402
from i121_crawler.fetch import fetch_bill_window, shift_month  # noqa: E402
from i121_crawler.parser import parse_bill_list  # noqa: E402


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mkeys-path", type=Path, default=RAW_DIR / "i121_mkeys.json")
    parser.add_argument("--cache-dir", type=Path, default=RAW_DIR / "i121_cache")
    parser.add_argument("--out-dir", type=Path, default=RAW_DIR / "i121_bills")
    parser.add_argument("--env-path", type=Path, default=ROOT / ".env")
    parser.add_argument("--sleep", type=float, default=1.5, help="seconds to sleep between live fetches")
    parser.add_argument("--floor-year", type=int, default=2008, help="stop iterating below this year")
    parser.add_argument("--max-windows-per-mkey", type=int, default=30, help="safety cap on windows per mkey")
    parser.add_argument("--max-mkeys", type=int, default=None, help="limit to first N mkeys (debug)")
    parser.add_argument("--end-ym", type=str, default=None, help="latest YYYY-MM to start from (default: today)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    mkeys: list[str] = json.loads(args.mkeys_path.read_text(encoding="utf-8"))
    if args.max_mkeys:
        mkeys = mkeys[: args.max_mkeys]

    if args.env_path.exists():
        session = session_from_env(env_path=args.env_path)
    else:
        session = session_from_env()
    print(f"login ok — crawling {len(mkeys)} mkeys", flush=True)

    today = datetime.now()
    start_end_ym = args.end_ym or f"{today.year:04d}-{today.month:02d}"

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
        end_ym = start_end_ym

        for _ in range(args.max_windows_per_mkey):
            start_ym = shift_month(end_ym, -11)
            if int(start_ym.split("-")[0]) < args.floor_year:
                break

            try:
                html, was_cached = fetch_bill_window(
                    session, mkey, start_ym, end_ym, args.cache_dir
                )
            except Exception as exc:
                print(
                    f"  [{index}/{len(mkeys)}] mkey={mkey} window={start_ym}~{end_ym} "
                    f"FAILED: {type(exc).__name__}: {exc}",
                    flush=True,
                )
                break

            per_windows += 1
            if was_cached:
                fetches_cached += 1
            else:
                fetches_live += 1
                time.sleep(args.sleep)

            bills = parse_bill_list(html)
            if not bills:
                break

            for bill in bills:
                key = (bill["mkey"], bill.get("napgi_compact") or bill.get("napgi") or "")
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

            end_ym = shift_month(start_ym, -1)

        summary[mkey] = {
            "bills": per_count,
            "windows": per_windows,
            "oldest_napgi": oldest,
            "latest_napgi": latest,
        }
        print(
            f"  [{index:2d}/{len(mkeys)}] mkey={mkey} "
            f"bills={per_count:3d} windows={per_windows:2d} range={oldest}~{latest}",
            flush=True,
        )

    csv_path = args.out_dir / "bills_long.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDNAMES)
        writer.writeheader()
        for bill in sorted(all_bills, key=lambda b: (b["mkey"], b.get("napgi_compact") or "")):
            writer.writerow({k: bill.get(k) for k in FIELDNAMES})

    summary_path = args.out_dir / "crawl_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"saved {len(all_bills)} bills → {csv_path.relative_to(ROOT)}")
    print(f"saved summary → {summary_path.relative_to(ROOT)}")
    print(f"fetches: live={fetches_live} cached={fetches_cached}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
