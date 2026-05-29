#!/usr/bin/env python3
"""i121.seoul.go.kr 청구서 크롤링 + CSV 전처리 통합 파이프라인.

이 파일 하나만 실행하면:
  [1/3] m_key 자동 발견  → Raw_data/i121_mkeys.json
  [2/3] 청구서 HTML 크롤링 + 파싱  → Raw_data/i121_bills/bills_long.csv
  [3/3] 검토 xlsx 와 join → 정형화  → Processed_data/Bill_Data/*.csv

전제:
  - 같은 폴더의 .env.example 을 복사해 .env 를 만들고 I121_USER_ID / I121_USER_PWD 설정
  - Raw_data/@수도요금...xlsx (검토 표) 존재
  - Raw_data/일일데이터/*.csv (일일 사용량) 존재 — meter_match.csv 생성용

사용 예:
  python make_data/청구서크롤링/run.py              # 전체 파이프라인
  python make_data/청구서크롤링/run.py --skip-crawl # 캐시만 사용 (네트워크 불필요)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 같은 폴더 안의 모듈을 절대 import 로 부르기 위해 sys.path 에 자기 폴더 추가.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import crawl  # noqa: E402
import discover  # noqa: E402
import postprocess  # noqa: E402


ROOT = HERE.parents[1]  # Capstone_Design/


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--env-path", type=Path, default=ROOT / ".env",
                   help="I121_USER_ID / I121_USER_PWD 가 있는 .env 경로")
    p.add_argument("--raw-dir", type=Path, default=ROOT / "Raw_data",
                   help="@수도요금...xlsx 가 있는 디렉토리")
    p.add_argument("--cache-dir", type=Path, default=ROOT / "Raw_data" / "i121_cache",
                   help="크롤링 HTML 캐시 디렉토리")
    p.add_argument("--mkeys-path", type=Path, default=ROOT / "Raw_data" / "i121_mkeys.json",
                   help="m_key 리스트 JSON 출력 경로")
    p.add_argument("--bills-dir", type=Path, default=ROOT / "Raw_data" / "i121_bills",
                   help="bills_long.csv 출력 디렉토리")
    p.add_argument("--daily-dir", type=Path, default=ROOT / "Raw_data" / "일일데이터",
                   help="meter_match 매칭에 쓸 일일 CSV 디렉토리")
    p.add_argument("--out-dir", type=Path, default=ROOT / "Processed_data" / "Bill_Data",
                   help="정형화 CSV 최종 출력 디렉토리")
    p.add_argument("--sleep", type=float, default=1.5,
                   help="크롤링 시 live fetch 사이 대기 초")
    p.add_argument("--skip-crawl", action="store_true",
                   help="크롤링 건너뛰고 기존 bills_long.csv 만 후처리")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 70)
    print("[STEP 1/3] m_key 자동 발견")
    print("=" * 70)
    mkeys = discover.run(args.mkeys_path, args.cache_dir, args.env_path)

    print()
    print("=" * 70)
    print("[STEP 2/3] 청구서 HTML 크롤링 + bills_long.csv")
    print("=" * 70)
    bills_csv = args.bills_dir / "bills_long.csv"
    if args.skip_crawl:
        if not bills_csv.exists():
            print(f"ERROR: --skip-crawl 지정됐지만 {bills_csv} 가 없습니다.", file=sys.stderr)
            return 1
        print(f"  --skip-crawl: 기존 {bills_csv.name} 사용")
    else:
        bills_csv, _ = crawl.run(
            mkeys, args.cache_dir, args.bills_dir, args.env_path, sleep=args.sleep,
        )

    print()
    print("=" * 70)
    print("[STEP 3/3] 후처리 → Processed_data/Bill_Data/")
    print("=" * 70)
    postprocess.run(args.raw_dir, bills_csv, args.daily_dir, args.out_dir)

    print()
    print("=" * 70)
    print(f"DONE — 최종 출력: {args.out_dir}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
