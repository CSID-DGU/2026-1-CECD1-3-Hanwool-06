"""
매일 1회 실행되는 파이프라인 진입점 (GitHub Actions daily.yml 에서 호출).

직접 실행:
  python back/pipelines/daily_water/run_daily.py              # 어제 날짜
  python back/pipelines/daily_water/run_daily.py 2026-05-05   # 특정 날짜
"""

import argparse
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper import scrape


def run(target_date: date | None = None) -> bool:
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    print(f"{'='*50}")
    print(f"[파이프라인 시작] 대상 날짜: {target_date}")
    print(f"{'='*50}")

    try:
        csv_path = scrape(target_date)
        print(f"  → {csv_path}")
    except Exception as e:
        print(f"  ❌ 수집 실패: {e}")
        traceback.print_exc()
        return False

    print(f"\n{'='*50}")
    print("[파이프라인 완료]")
    print(f"{'='*50}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="일별 수도 사용량 파이프라인")
    parser.add_argument("date", nargs="?", help="실행 날짜 YYYY-MM-DD (기본: 어제)")
    args = parser.parse_args()
    target = date.fromisoformat(args.date) if args.date else None
    success = run(target)
    sys.exit(0 if success else 1)
