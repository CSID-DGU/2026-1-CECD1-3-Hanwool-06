"""GPT 에이전트.

  · daily_summary  : 당일 이상징후를 보고 '오늘의 업무'로 요약(팝업용)
  · analyze_cause  : 특정 역/날짜 이상의 원인 분석
                     - 주말/공휴일은 달력 데이터로 즉시 판정
                     - 평일인데 튀면 web_search 툴로 역 주변 행사/이슈 검색

모델명은 .env 의 OPENAI_MODEL(기본 gpt-5.5) 로 교체 가능.
"""
import json

from openai import OpenAI

from . import config, data_access


def _client() -> OpenAI:
    if not config.openai_ready():
        raise RuntimeError("OPENAI_API_KEY 가 설정되지 않았습니다. .env 를 확인하세요.")
    return OpenAI(api_key=config.OPENAI_API_KEY)


def _extract_text(resp) -> str:
    """Responses API 응답에서 텍스트만 추출(SDK 버전 차이에 견고하게)."""
    text = getattr(resp, "output_text", None)
    if text:
        return text
    parts = []
    for item in getattr(resp, "output", []) or []:
        for c in getattr(item, "content", []) or []:
            t = getattr(c, "text", None)
            if t:
                parts.append(t)
    return "\n".join(parts)


def _parse_json(text: str) -> dict:
    """모델이 코드펜스/잡설을 붙여도 첫 JSON 오브젝트를 회수."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        return json.loads(text)
    except Exception:
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except Exception:
                pass
    return {"_raw": text}


def _respond(instructions: str, prompt: str, tools=None) -> str:
    client = _client()
    kwargs = dict(model=config.OPENAI_MODEL, instructions=instructions, input=prompt)
    if tools:
        kwargs["tools"] = tools
    try:
        resp = client.responses.create(**kwargs)
    except Exception:
        # web_search 툴 타입을 못 쓰는 환경이면 툴 없이 재시도
        if tools:
            resp = client.responses.create(
                model=config.OPENAI_MODEL, instructions=instructions, input=prompt
            )
        else:
            raise
    return _extract_text(resp)


# ── 당일 업무 요약(팝업) ───────────────────────────────────────────
def daily_summary(date: str | None = None) -> dict:
    date = date or data_access.reference_date()
    items = data_access.anomalies_on(date)
    cal = data_access.calendar_info(date)

    n_alert = sum(1 for x in items if x["심각도"] == "경고")
    n_warn = sum(1 for x in items if x["심각도"] == "주의")

    # OpenAI 키가 없으면 규칙 기반으로라도 요약(팝업이 깨지지 않게).
    if items and not config.openai_ready():
        return {
            "기준일": date,
            "headline": f"{date} 기준 경고 {n_alert}건 · 주의 {n_warn}건이 감지됐습니다.",
            "counts": {"경고": n_alert, "주의": n_warn, "총": len(items)},
            "items": [
                {
                    "역명": x["역명"],
                    "심각도": x["심각도"],
                    "pct": x["pct"],
                    "dir": x["방향"],
                    "err_ton": x["error_ton"],
                    "action": "현장/계량 확인 필요"
                    + (" · 데이터오류 의심" if x["likely_data_error"] else ""),
                }
                for x in items
            ],
            "actions": [
                f"경고 {n_alert}건 우선 점검",
                "이탈 폭이 큰 역부터 원인 분석",
            ],
            "calendar": cal,
            "generated_by": "rule (OPENAI_API_KEY 미설정)",
        }

    if not items:
        return {
            "기준일": date,
            "headline": f"{date} 기준 새로운 이상징후가 없습니다.",
            "counts": {"경고": 0, "주의": 0, "총": 0},
            "items": [],
            "actions": ["특이사항 없음 · 정기 점검만 진행하세요."],
            "calendar": cal,
            "generated_by": "rule",
        }

    compact = [
        {
            "역명": x["역명"],
            "영업사업소": x["영업사업소"],
            "심각도": x["심각도"],
            "방향": x["방향"],
            "예측대비%": x["pct"],
            "예측오차톤": x["error_ton"],
            "deviation": x["deviation_score"],
            "데이터오류의심": x["likely_data_error"],
        }
        for x in items
    ]

    instructions = (
        "너는 '물샘이', 서울교통공사 상수도 관제 담당자를 돕는 분석 에이전트다. "
        "주어진 당일 이상징후 목록을 보고 담당자가 바로 처리할 '오늘의 업무'로 요약한다. "
        "과장 없이 사실 기반으로, 한국어로 간결하게. "
        "반드시 아래 JSON 스키마로만 답한다(설명 문장 금지).\n"
        "{\n"
        '  "headline": "한 줄 총평(가장 시급한 것 중심)",\n'
        '  "items": [{"역명": "...", "심각도": "경고|주의", "one_line": "무엇이 어떻게 이상한지 한 줄", "action": "권장 조치 한 줄"}],\n'
        '  "actions": ["담당자가 오늘 해야 할 일 2~4개"]\n'
        "}"
    )
    prompt = (
        f"기준일: {date} (요일: {cal.get('요일')}, 주말: {cal.get('weekend')}, "
        f"공휴일: {cal.get('holiday')} {cal.get('holiday_name')})\n"
        f"경고 {n_alert}건, 주의 {n_warn}건.\n"
        f"이상징후 목록(JSON):\n{json.dumps(compact, ensure_ascii=False)}\n\n"
        "심각도 '경고' 와 deviation 절대값이 큰 항목을 우선하라. "
        "'데이터오류의심'=true 인 항목은 계량/전송 오류 가능성을 함께 언급하라."
    )

    text = _respond(instructions, prompt)
    parsed = _parse_json(text)
    parsed.setdefault("headline", f"{date} 기준 경고 {n_alert}건 · 주의 {n_warn}건")
    parsed.setdefault("actions", [])
    # 수치는 실데이터로 고정하고, 역별 권장조치(action)만 모델 출력에서 가져온다.
    ai_action = {
        it.get("역명"): it.get("action")
        for it in parsed.get("items", [])
        if isinstance(it, dict)
    }
    return {
        "기준일": date,
        "headline": parsed["headline"],
        "counts": {"경고": n_alert, "주의": n_warn, "총": len(items)},
        "items": [
            {
                "역명": x["역명"],
                "심각도": x["심각도"],
                "pct": x["pct"],
                "dir": x["방향"],
                "err_ton": x["error_ton"],
                "action": ai_action.get(x["역명"]) or "현장/계량 확인 필요",
            }
            for x in items
        ],
        "actions": parsed["actions"],
        "calendar": cal,
        "generated_by": config.OPENAI_MODEL,
    }


# ── 이상 원인 분석 ─────────────────────────────────────────────────
def analyze_cause(역명: str, date: str | None = None) -> dict:
    item = data_access.find_one(역명, date)
    if not item:
        return {"error": f"'{역명}' 의 이상 기록을 찾지 못했습니다."}
    date = item["날짜"]
    cal = data_access.calendar_info(date)
    history = data_access.station_history(역명, days=7)

    instructions = (
        "너는 '물샘이', 서울교통공사 상수도 이상징후의 '원인'을 추정하는 분석 에이전트다.\n"
        "분석 절차:\n"
        "1) 먼저 달력 정보로 그날이 주말/공휴일/연휴인지 확인한다. 맞다면 사용량 변동의 1차 원인으로 제시한다.\n"
        "2) 평일인데 사용량이 크게 튀었다면, web_search 로 해당 역 주변에서 그 날짜 전후에 "
        "행사·집회·축제·공사·단수·동파 등 물 사용에 영향 줄 사건이 있었는지 찾는다.\n"
        "3) 데이터오류의심=true 이면 계량기/전송 오류 가능성도 후보로 둔다.\n"
        "근거 없이 단정하지 말고 확신도를 솔직히 표기한다. 한국어. 출처 URL 은 가능하면 포함.\n"
        "반드시 아래 JSON 으로만 답한다.\n"
        "{\n"
        '  "primary_cause": "가장 유력한 원인 한 줄",\n'
        '  "reasons": ["근거가 된 사실 1~4개(달력/행사/데이터 등)"],\n'
        '  "events": [{"title": "찾은 사건/행사", "date": "YYYY-MM-DD 또는 기간", "source": "URL 또는 출처"}],\n'
        '  "is_calendar_effect": true,\n'
        '  "confidence": "높음|보통|낮음",\n'
        '  "recommendation": "담당자 권장 조치 한 줄"\n'
        "}"
    )
    prompt = (
        f"역명: {역명}\n날짜: {date} (요일: {cal.get('요일')}, "
        f"주말: {cal.get('weekend')}, 공휴일: {cal.get('holiday')} {cal.get('holiday_name')})\n"
        f"심각도: {item['심각도']} / 방향: {item['방향']}\n"
        f"예측 {item['predicted_ton']}톤 vs 실제 {item['actual_ton']}톤 "
        f"(오차 {item['error_ton']}톤, 예측대비 {item['pct']}%, deviation {item['deviation_score']})\n"
        f"데이터오류의심: {item['likely_data_error']}\n"
        f"최근 이상 이력: {json.dumps([{'날짜': h['날짜'], '심각도': h['심각도'], 'pct': h['pct']} for h in history], ensure_ascii=False)}\n"
    )

    if not config.openai_ready():
        return {
            "역명": 역명,
            "날짜": date,
            "anomaly": item,
            "calendar": cal,
            "analysis": {"error": "OPENAI_API_KEY 미설정 — .env 에 키를 넣으면 원인 분석이 동작합니다."},
            "generated_by": "none",
        }

    tools = [{"type": "web_search"}]
    text = _respond(instructions, prompt, tools=tools)
    parsed = _parse_json(text)
    return {
        "역명": 역명,
        "날짜": date,
        "anomaly": item,
        "calendar": cal,
        "analysis": parsed,
        "generated_by": config.OPENAI_MODEL,
    }
