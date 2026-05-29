"""i121 청구서 페이지 HTTP fetch (캐시 포함)."""

from __future__ import annotations

from pathlib import Path

import requests

from auth import BASE, MYARISU_URL


def shift_month(ym: str, delta: int) -> str:
    """YYYY-MM 문자열을 delta 개월만큼 이동."""
    y, m = map(int, ym.split("-"))
    idx = y * 12 + (m - 1) + delta
    return f"{idx // 12:04d}-{(idx % 12) + 1:02d}"


def fetch_bill_window(
    session: requests.Session,
    mkey: str,
    start_ym: str,
    end_ym: str,
    cache_dir: Path,
    *,
    timeout: float = 30.0,
    force: bool = False,
) -> tuple[str, bool]:
    """(mkey, start_ym~end_ym) 윈도우 HTML 가져오기 → (html, was_cached)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{mkey}_{start_ym}_{end_ym}.html"
    if cache_path.exists() and not force:
        return cache_path.read_text(encoding="utf-8"), True

    params = {
        "searchMkey": mkey,
        "searchCsNm": "",
        "searchStartYm": start_ym,
        "searchEndYm": end_ym,
        "isSearch": "Y",
        "searchNapgi": "",
        "searchGumChim": "N",
        "searchCstmidno": "",
        "_m": "m6",
    }
    headers = {
        "Referer": f"{BASE}/cs/cyber/front/main/NR_index.do",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = session.get(MYARISU_URL, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    cache_path.write_text(response.text, encoding="utf-8")
    return response.text, False
