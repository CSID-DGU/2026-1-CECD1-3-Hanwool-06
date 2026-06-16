"""ML 실산출 CSV · 달력(주말/공휴일) · 청구서(영업사업소) 를 읽어
에이전트와 API 가 쓰기 좋은 형태로 가공한다. 파일은 1회 로드 후 캐시.
"""
from functools import lru_cache

import pandas as pd

from . import config

SEV_RANK = {"정상": 0, "주의": 1, "경고": 2}


def _norm_id(series: pd.Series) -> pd.Series:
    """고객번호를 정수 문자열로 정규화(zero-pad 차이 흡수)."""
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("0")
        .replace("", "0")
    )


@lru_cache(maxsize=1)
def _flagged() -> pd.DataFrame:
    df = pd.read_csv(config.ANOMALIES_FLAGGED, encoding="utf-8-sig")
    # 라이브 소스(risk.json 과 동일) 컬럼명을 기존 스키마로 매핑.
    df = df.rename(
        columns={
            "pred_ton": "predicted_ton",
            "residual": "error_ton",
            "z_score": "deviation_score",
            "data_error_candidate": "likely_data_error",
        }
    )
    df["날짜"] = df["날짜"].astype(str)
    df["cid"] = _norm_id(df["고객번호"])
    return df


@lru_cache(maxsize=1)
def _calendar() -> pd.DataFrame:
    df = pd.read_csv(config.DATE_INDEX, encoding="utf-8-sig")
    df["날짜"] = df["날짜"].astype(str)
    return df.set_index("날짜")


@lru_cache(maxsize=1)
def _office_map() -> dict:
    """고객번호(int문자열) -> {영업사업소, 용도, 고지서_성명}."""
    try:
        df = pd.read_csv(
            config.BILLS_CLEAN,
            encoding="utf-8-sig",
            usecols=["고객번호", "영업사업소", "용도", "고지서_성명"],
            dtype=str,
        )
    except Exception:
        return {}
    df = df.fillna("")  # 결측(용도 등)은 NaN→"" (NaN 은 JSON 직렬화 불가)
    df["cid"] = _norm_id(df["고객번호"])
    df = df.drop_duplicates("cid", keep="last")
    return {
        r["cid"]: {
            "영업사업소": r.get("영업사업소") or "",
            "용도": r.get("용도") or "",
            "고지서_성명": r.get("고지서_성명") or "",
        }
        for _, r in df.iterrows()
    }


def reference_date() -> str:
    """데모 기준일. TODAY_OVERRIDE 우선, 없으면 이상탐지 CSV 의 최신 날짜."""
    if config.TODAY_OVERRIDE:
        return config.TODAY_OVERRIDE
    return _flagged()["날짜"].max()


def calendar_info(date: str) -> dict:
    cal = _calendar()
    if date not in cal.index:
        return {"weekend": None, "holiday": None, "holiday_name": ""}
    row = cal.loc[date]
    hname = row.get("공휴일명", "")
    hname = "" if pd.isna(hname) else str(hname).strip()
    return {
        "weekend": bool(int(row.get("주말", 0))),
        "holiday": bool(int(row.get("공휴일", 0))),
        "holiday_name": hname,
        "요일": str(row.get("요일", "") or ""),
    }


def _row_to_item(r: pd.Series) -> dict:
    cid = r["cid"]
    meta = _office_map().get(cid, {})
    predicted = float(r["predicted_ton"])
    actual = float(r["일사용량_톤"])
    error = float(r["error_ton"])
    pct = round((error / predicted) * 100) if predicted else 0
    return {
        "고객번호": cid,
        "역명": str(r["역명"]),
        "날짜": str(r["날짜"]),
        "심각도": str(r["심각도"]),
        "방향": str(r.get("방향") or ""),
        "predicted_ton": round(predicted, 2),
        "actual_ton": round(actual, 2),
        "error_ton": round(error, 2),
        "deviation_score": round(float(r["deviation_score"]), 2),
        "pct": pct,
        "likely_data_error": bool(r.get("likely_data_error")),
        "영업사업소": meta.get("영업사업소", ""),
        "용도": meta.get("용도", ""),
    }


def anomalies_on(date: str | None = None, include_normal: bool = False) -> list[dict]:
    """기준일의 이상 항목 목록(심각도 높은 순). 데이터 오류로 의심되는 행은 뒤로."""
    date = date or reference_date()
    df = _flagged()
    day = df[df["날짜"] == date]
    if not include_normal:
        day = day[day["심각도"].isin(["주의", "경고"])]
    items = [_row_to_item(r) for _, r in day.iterrows()]
    items.sort(
        key=lambda x: (
            x["likely_data_error"],          # 데이터오류 의심은 뒤로
            -SEV_RANK.get(x["심각도"], 0),     # 경고 > 주의
            -abs(x["deviation_score"]),
        )
    )
    return items


def find_one(역명: str, date: str | None = None) -> dict | None:
    date = date or reference_date()
    df = _flagged()
    hit = df[(df["역명"] == 역명) & (df["날짜"] == date)]
    if hit.empty:
        # 날짜 무관하게 역명만으로 최근 1건
        hit = df[df["역명"] == 역명].sort_values("날짜")
        if hit.empty:
            return None
        hit = hit.tail(1)
    return _row_to_item(hit.iloc[0])


def station_history(역명: str, days: int = 7) -> list[dict]:
    """해당 역의 최근 이상 이력(있는 날짜만)."""
    df = _flagged()
    hit = df[df["역명"] == 역명].sort_values("날짜").tail(days)
    return [_row_to_item(r) for _, r in hit.iterrows()]
