"""상수도 이상징후 관제 — 에이전트 API 서버 (FastAPI).

실행 (반드시 레포 루트에서 — 상대 import 때문에 cd back/api 로는 안 됨):
  uvicorn back.api.main:app --reload --port 8000

엔드포인트:
  GET  /api/health
  GET  /api/anomalies?date=YYYY-MM-DD        이상 목록(실데이터)
  GET  /api/summary?date=&refresh=true        당일 업무 요약(에이전트, 팝업용)
  POST /api/analyze  {역명, 날짜?}             이상 원인 분석(에이전트 · web_search)
  POST /api/alert    {역명, 날짜?, to?, analyze?}  이상 알림 메일 발송
"""
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import agent, config, data_access, mailer


def _sync_agent_data() -> None:
    """daily-snapshot 의 최신 test_anomalies.csv 를 가져온다 (에이전트 일별 자동 반영). 실패해도 무시."""
    rel = str(config.ANOMALIES_FLAGGED.relative_to(config.ROOT))
    try:
        subprocess.run(["git", "fetch", "origin", "daily-snapshot", "-q"],
                       cwd=config.ROOT, check=True, timeout=30)
        out = subprocess.run(["git", "show", f"origin/daily-snapshot:{rel}"],
                             cwd=config.ROOT, check=True, capture_output=True, timeout=30)
        config.ANOMALIES_FLAGGED.write_bytes(out.stdout)
        data_access._flagged.cache_clear()  # 캐시 비워 새 CSV 를 읽게
        print(f"[sync] {rel} ← daily-snapshot")
    except Exception as e:
        print(f"[sync] 에이전트 데이터 동기화 건너뜀 ({e}) — 기존 CSV 사용")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _sync_agent_data()
    yield


app = FastAPI(title="상수도 이상징후 관제 API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONT_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

_summary_cache: dict[str, dict] = {}  # date -> summary


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "reference_date": data_access.reference_date(),
        "openai": config.openai_ready(),
        "smtp": config.smtp_ready(),
        "model": config.OPENAI_MODEL,
    }


@app.get("/api/anomalies")
def anomalies(date: str | None = None, include_normal: bool = False):
    date = date or data_access.reference_date()
    return {
        "기준일": date,
        "calendar": data_access.calendar_info(date),
        "items": data_access.anomalies_on(date, include_normal=include_normal),
    }


@app.get("/api/summary")
def summary(date: str | None = None, refresh: bool = False):
    if refresh:
        _sync_agent_data()  # 최신 CSV 다시 받아오고 캐시 비움 → 기준일도 갱신
    date = date or data_access.reference_date()
    if refresh or date not in _summary_cache:
        _summary_cache[date] = agent.daily_summary(date)
    return _summary_cache[date]


class AnalyzeReq(BaseModel):
    역명: str
    날짜: str | None = None


@app.post("/api/analyze")
def analyze(req: AnalyzeReq):
    return agent.analyze_cause(req.역명, req.날짜)


class AlertReq(BaseModel):
    역명: str
    날짜: str | None = None
    to: str | None = None
    analyze: bool = True  # 메일에 원인분석 포함 여부


@app.post("/api/alert")
def alert(req: AlertReq):
    item = data_access.find_one(req.역명, req.날짜)
    if not item:
        return {"sent": False, "reason": f"'{req.역명}' 이상 기록 없음"}
    analysis = agent.analyze_cause(req.역명, item["날짜"]) if req.analyze else None
    html = mailer.build_alert_html(item, analysis)
    subject = f"[{item['심각도']}] {item['역명']} 상수도 이상징후 ({item['날짜']})"
    result = mailer.send_mail(subject, html, to=req.to)
    return {**result, "item": item, "analysis": analysis}
