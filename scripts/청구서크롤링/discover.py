"""m_key 자동 발견 (1단계)."""

from __future__ import annotations

import json
from pathlib import Path

from auth import MYARISU_URL, session_from_env
from bill_parser import discover_mkeys


def run(out_path: Path, cache_dir: Path, env_path: Path) -> list[str]:
    """로그인 → 메인 페이지 → m_key 리스트 추출 → JSON 저장.

    이미 out_path 가 있으면 재발견 생략 (네트워크 절약).
    """
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"  [discover] 캐시 사용: {out_path.name} ({len(existing)} 개)")
        return existing

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = session_from_env(env_path=env_path if env_path.exists() else None)
    print("  [discover] 로그인 성공")

    response = session.get(MYARISU_URL, params={"_m": "m6"}, timeout=30)
    response.raise_for_status()
    html_path = cache_dir / "myarisu_initial.html"
    html_path.write_text(response.text, encoding="utf-8")

    mkeys = discover_mkeys(response.text)
    if not mkeys:
        raise RuntimeError(
            "m_key 발견 실패. 로그인 응답을 확인하세요: "
            f"{html_path}"
        )

    out_path.write_text(
        json.dumps(mkeys, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [discover] {len(mkeys)} 개 m_key → {out_path}")
    return mkeys
