#!/usr/bin/env python3
"""Log into i121.seoul.go.kr and extract the full mkey dropdown.

Outputs:
    Raw_data/i121_mkeys.json       — list of mkey strings
    Raw_data/i121_cache/myarisu_initial.html  — raw landing HTML (debug)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from i121_crawler.auth import MYARISU_URL, session_from_env  # noqa: E402
from i121_crawler.parser import discover_mkeys  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-path",
        type=Path,
        default=ROOT / "Raw_data" / "i121_mkeys.json",
        help="where to save the extracted mkey list",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "Raw_data" / "i121_cache",
        help="where to save the raw landing HTML for debugging",
    )
    parser.add_argument(
        "--env-path",
        type=Path,
        default=ROOT / ".env",
        help="path to .env containing I121_USER_ID / I121_USER_PWD",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.env_path.exists():
        session = session_from_env(env_path=args.env_path)
    else:
        session = session_from_env()
    print("login ok", flush=True)

    response = session.get(MYARISU_URL, params={"_m": "m6"}, timeout=30)
    response.raise_for_status()
    html_path = args.cache_dir / "myarisu_initial.html"
    html_path.write_text(response.text, encoding="utf-8")
    print(f"saved landing html → {html_path.relative_to(ROOT)}", flush=True)

    mkeys = discover_mkeys(response.text)
    if not mkeys:
        print(
            "ERROR: no mkeys found in the dropdown. "
            "Inspect the saved HTML to see what the page actually returned.",
            file=sys.stderr,
        )
        return 1

    args.out_path.write_text(
        json.dumps(mkeys, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"discovered {len(mkeys)} mkeys → {args.out_path.relative_to(ROOT)}")
    for k in mkeys[:5]:
        print(f"  {k}")
    if len(mkeys) > 5:
        print(f"  ...({len(mkeys) - 5} more)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
