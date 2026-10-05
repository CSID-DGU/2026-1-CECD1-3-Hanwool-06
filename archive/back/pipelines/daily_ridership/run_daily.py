"""
승하차 수집 파이프라인 수동 진입점. 정기 실행은 back.pipelines.refresh를 사용한다.

직접 실행:
  python back/pipelines/daily_ridership/run_daily.py                        # 어제
  python back/pipelines/daily_ridership/run_daily.py 2026-05-29             # 특정 날짜
  python back/pipelines/daily_ridership/run_daily.py 2026-05-24 2026-05-30  # 범위(백필)

승하차는 적재 지연이 있어 어제치가 아직 안 떴을 수 있다. 미적재 날짜는 건너뛰며(에러 아님),
Actions 는 최근 며칠치를 덮어쓰며 돌려 빠진 날을 자동으로 메꾼다.

네트워크·인증·데이터 오류는 실패로 반환하며 기존 관측값을 보존한다.
"""
import argparse
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scraper import scrape
from back.pipelines.common import RUNTIME, collection_lock, today


def run(start: date | None = None, end: date | None = None) -> bool:
    if start is None:
        start = today() - timedelta(days=1)
    if end is None:
        end = start
    if start > end:
        raise ValueError("start must be on or before end")

    print("=" * 50)
    print(f"[승하차 파이프라인 시작] 대상: {start} ~ {end}")
    print("=" * 50)

    ok = True
    day = start
    while day <= end:
        try:
            path = scrape(day)
            print(f"  {day} → {path}" if path else f"  {day}: API 미적재 → 건너뜀")
        except (URLError, TimeoutError, OSError) as e:
            print(f"  {day}: collection failed ({type(e).__name__}); prior data preserved")
            ok = False
        except Exception as e:
            print(f"  ❌ {day} 수집 실패: {e}")
            traceback.print_exc()
            ok = False
        day += timedelta(days=1)

    print("=" * 50)
    print("[파이프라인 완료]")
    print("=" * 50)
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="일별 승하차 인원 수집")
    parser.add_argument("start", nargs="?", help="시작일 YYYY-MM-DD (기본: 어제)")
    parser.add_argument("end", nargs="?", help="종료일 YYYY-MM-DD (기본: start)")
    args = parser.parse_args()
    s = date.fromisoformat(args.start) if args.start else None
    e = date.fromisoformat(args.end) if args.end else None
    with collection_lock(RUNTIME):
        sys.exit(0 if run(s, e) else 1)
