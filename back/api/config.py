"""환경설정 로딩. 모든 시크릿/경로는 여기 한 곳에서만 읽는다."""
import os
from pathlib import Path

from dotenv import load_dotenv

# back/api/config.py -> 프로젝트 루트는 2단계 위
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# ── OpenAI (에이전트) ──────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")  # .env 로 교체 가능

# ── 메일 발송 (Gmail SMTP) ─────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")  # Gmail 앱 비밀번호
ALERT_FROM = os.getenv("ALERT_FROM", "") or SMTP_USER
ALERT_TO = os.getenv("ALERT_TO", "")  # 기본 수신처(콤마로 다중 가능)

# ── 데모 기준일 ────────────────────────────────────────────────────
# 비우면 이상탐지 CSV 의 가장 최근 날짜를 '오늘'로 사용한다.
TODAY_OVERRIDE = os.getenv("TODAY_OVERRIDE", "").strip()

# ── 데이터 경로 ────────────────────────────────────────────────────
RESULTS = ROOT / "back" / "ml" / "lightgbm" / "results"
ANOMALIES_FLAGGED = RESULTS / "test_anomalies_flagged.csv"
ANOMALIES_ALL = RESULTS / "test_anomalies.csv"
DATE_INDEX = ROOT / "data" / "processed" / "date_index.csv"
BILLS_CLEAN = ROOT / "data" / "billing" / "bills_clean.csv"

# 프론트(개발 서버) 출처 — CORS 허용용
FRONT_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


def openai_ready() -> bool:
    return bool(OPENAI_API_KEY)


def smtp_ready() -> bool:
    return bool(SMTP_USER and SMTP_PASS)
