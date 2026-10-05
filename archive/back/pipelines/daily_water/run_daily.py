"""Collect one day or an inclusive date range, using the shared registered contracts."""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from back.pipelines.common import RUNTIME, collection_lock, today
from back.pipelines.daily_water.scraper import scrape_range


def run(start=None, end=None):
    start = start or today() - timedelta(days=1)
    reports = scrape_range(start, end or start)
    for report in reports:
        print(report)
    return not any(r["errors"] for r in reports)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start", nargs="?", type=date.fromisoformat)
    parser.add_argument("end", nargs="?", type=date.fromisoformat)
    args = parser.parse_args()
    with collection_lock(RUNTIME):
        raise SystemExit(0 if run(args.start, args.end) else 1)
