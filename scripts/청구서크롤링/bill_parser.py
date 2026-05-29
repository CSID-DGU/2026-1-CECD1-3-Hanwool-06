"""i121 청구서 HTML 파싱 (m_key 추출 / 부과내역 / 납부내역)."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag


_MKEY_RE = re.compile(r"^\d{6,12}$")
_STATION_RE = re.compile(r"([가-힣A-Za-z0-9]+역)")


def discover_mkeys(html: str) -> list[str]:
    """<select name="mkey"> dropdown 에서 고객번호 추출."""
    soup = BeautifulSoup(html, "lxml")
    select = soup.find("select", {"name": "mkey"}) or soup.find("select", {"id": "mkey"})
    mkeys: list[str] = []
    if isinstance(select, Tag):
        for opt in select.find_all("option"):
            value = (opt.get("value") or "").strip()
            if _MKEY_RE.match(value):
                mkeys.append(value)
    seen: set[str] = set()
    out: list[str] = []
    for v in mkeys:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def parse_bill_list(html: str) -> list[dict[str, Any]]:
    """NR_myArisu.do 응답의 부과내역 테이블 파싱."""
    soup = BeautifulSoup(html, "lxml")
    table = _find_table_by_caption(soup, "부과내역이며")
    if table is None:
        return []
    tbody = table.find("tbody")
    if not isinstance(tbody, Tag):
        return []

    rows: list[dict[str, Any]] = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 8:
            continue
        sunbeon = _clean(cells[0].get_text())
        if not sunbeon.isdigit():
            continue

        mkey = _clean(cells[1].get_text())
        gubun = _clean(cells[2].get_text())
        napgi = _clean(cells[3].get_text())
        sunap_status = _clean(cells[4].get_text())
        bugwa_amount = _to_int(cells[5].get_text())
        address = _clean(cells[6].get_text())
        total_usage = _to_int(cells[7].get_text())
        napgi_compact = _extract_napgi_param(cells[-1])

        rows.append(
            {
                "sunbeon": int(sunbeon),
                "mkey": mkey,
                "gubun": gubun,
                "napgi": napgi,
                "napgi_compact": napgi_compact,
                "sunap_status": sunap_status,
                "bugwa_amount_won": bugwa_amount,
                "address": address,
                "station_from_address": _extract_station(address),
                "total_usage_ton": total_usage,
            }
        )
    return rows


def parse_payment_list(html: str) -> list[dict[str, Any]]:
    """납부내역 테이블 파싱."""
    soup = BeautifulSoup(html, "lxml")
    table = _find_table_by_caption(soup, "납부내역이며")
    if table is None:
        return []
    tbody = table.find("tbody")
    if not isinstance(tbody, Tag):
        return []
    rows: list[dict[str, Any]] = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue
        mkey = _clean(cells[0].get_text())
        if not _MKEY_RE.match(mkey):
            continue
        rows.append(
            {
                "mkey": mkey,
                "paid_amount_won": _to_int(cells[1].get_text()),
                "payment_method": _clean(cells[2].get_text()),
                "paid_date": _clean(cells[3].get_text()),
                "address": _clean(cells[4].get_text()),
            }
        )
    return rows


def _find_table_by_caption(soup: BeautifulSoup, caption_substring: str) -> Tag | None:
    for cap in soup.find_all("caption"):
        if caption_substring in cap.get_text():
            parent = cap.find_parent("table")
            if isinstance(parent, Tag):
                return parent
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _to_int(text: str) -> int | None:
    s = _clean(text).replace(",", "")
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _extract_station(address: str) -> str | None:
    if not address:
        return None
    matches = _STATION_RE.findall(address)
    if not matches:
        return None
    return matches[-1]


def _extract_napgi_param(cell: Tag) -> str | None:
    anchor = cell.find("a")
    if not isinstance(anchor, Tag):
        return None
    onclick = anchor.get("onclick") or ""
    m = re.search(r"jungInfoDetail\('(\d{8})'\)", onclick)
    return m.group(1) if m else None
