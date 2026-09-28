"""Server-only settings; environment variables take precedence over .env."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
os.umask(0o077)  # Runtime database, collected observations and snapshots are private.
if os.getenv('APP_ENV') != 'production':
    load_dotenv(ROOT / '.env')
DATA_DIR = Path(os.getenv('APP_DATA_DIR') or ROOT / 'data/runtime').resolve()
APP_DB_PATH = Path(os.getenv('APP_DB_PATH') or DATA_DIR / 'app.sqlite3').resolve()
SEED_DIR = ROOT / 'data/app_seed'
APP_ENV = os.getenv('APP_ENV', 'development')
COOKIE_SECURE = os.getenv('APP_COOKIE_SECURE', str(APP_ENV == 'production')).lower() == 'true'
SESSION_HOURS = int(os.getenv('SESSION_HOURS', '8'))
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '').strip().lower()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
ADMIN_NAME = os.getenv('ADMIN_NAME', '총괄 관리자').strip()
FRONT_ORIGINS = [v.strip() for v in os.getenv('APP_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000').split(',') if v.strip()]
ALLOWED_HOSTS = [v.strip() for v in os.getenv('APP_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(',') if v.strip()]
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.5')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
ALERT_FROM = os.getenv('ALERT_FROM', '') or SMTP_USER
TODAY_OVERRIDE = os.getenv('TODAY_OVERRIDE', '').strip()
COLLECTION_WORKER_ENABLED = os.getenv('COLLECTION_WORKER_ENABLED', 'true').lower() == 'true'
DATE_INDEX = ROOT / 'data/processed/date_index.csv'
BILLS_CLEAN = ROOT / 'data/billing/bills_clean.csv'

def configured(value):
    return bool(value and not value.lower().startswith(('your_', 'sk-...')))

def openai_ready():
    return configured(OPENAI_API_KEY)

def smtp_ready():
    return configured(SMTP_USER) and configured(SMTP_PASS)


def validate_deployment():
    if APP_ENV not in ('development', 'production'):
        raise RuntimeError('APP_ENV는 development 또는 production이어야 합니다.')
    if not 1 <= SESSION_HOURS <= 24:
        raise RuntimeError('SESSION_HOURS는 1~24 사이여야 합니다.')
    if APP_ENV != 'production':
        return
    if not COOKIE_SECURE:
        raise RuntimeError('운영 환경에서는 APP_COOKIE_SECURE=true가 필요합니다.')
    if TODAY_OVERRIDE:
        raise RuntimeError('운영 환경에서는 TODAY_OVERRIDE를 비워야 합니다.')
    if not FRONT_ORIGINS:
        raise RuntimeError('운영 APP_ORIGINS에는 공개 HTTPS 출처만 지정하세요.')
    for origin in FRONT_ORIGINS:
        url = urlsplit(origin)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.path or url.query or url.fragment):
            raise RuntimeError('운영 APP_ORIGINS에는 공개 HTTPS 출처만 지정하세요.')
    if not ALLOWED_HOSTS or any('*' in host or host == 'testserver' for host in ALLOWED_HOSTS):
        raise RuntimeError('운영 APP_ALLOWED_HOSTS에는 실제 호스트를 명시하세요.')
    if DATA_DIR.is_relative_to(ROOT) or APP_DB_PATH.is_relative_to(ROOT):
        raise RuntimeError('운영 데이터와 DB는 저장소 밖의 비공개 경로에 두세요.')
