"""Private water-monitoring API and production SPA entry point."""
import json
import re
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import date as Date, datetime, timezone
from urllib.parse import quote

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import agent, auth, catalog, collection, config, data_access, db, documents, mailer


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        catalog.bootstrap(c)
    auth.bootstrap_admin()
    stop, thread = collection.start_worker()
    try:
        yield
    finally:
        stop.set()
        if thread.is_alive():
            thread.join(timeout=2)


app = FastAPI(title='서울교통공사 상수도 관리', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=config.FRONT_ORIGINS, allow_credentials=True,
                   allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Content-Type', 'X-CSRF-Token'])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)


@app.middleware('http')
async def private_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    if config.COOKIE_SECURE:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response


@app.get('/api/health')
def health():
    with db.connect() as c:
        setup_required = not bool(c.execute('SELECT 1 FROM users LIMIT 1').fetchone())
    return {'ok': True, 'setup_required': setup_required}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(StrictModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


DUMMY_HASH = auth.hash_password(secrets.token_urlsafe(32))


@app.post('/api/auth/login')
def login(body: Login, request: Request, response: Response):
    auth.check_origin(request)
    email = body.email.strip().lower()
    host = request.client.host if request.client else 'unknown'
    identity = auth.token_hash(email + ':' + host)
    ip_identity = auth.token_hash(host)
    now = time.time()
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM login_attempts WHERE attempted_at<?', (now-900,))
        counts = {r['identity']: r['n'] for r in c.execute('SELECT identity,count(*) AS n FROM login_attempts WHERE identity IN (?,?) GROUP BY identity', (identity, ip_identity))}
        if counts.get(identity, 0) >= 5 or counts.get(ip_identity, 0) >= 30:
            raise HTTPException(429, '로그인 시도가 너무 많습니다. 15분 후 다시 시도하세요.')
        row = c.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        valid = auth.verify_password(body.password, row['password_hash'] if row else DUMMY_HASH)
        if not valid or not row or not row['active']:
            c.executemany('INSERT INTO login_attempts(attempted_at,identity) VALUES(?,?)', [(now, identity), (now, ip_identity)])
            user = None
        else:
            c.execute('DELETE FROM login_attempts WHERE identity=?', (identity,))
            c.execute('DELETE FROM sessions WHERE expires_at<?', (now,))
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            c.execute('INSERT INTO sessions VALUES(?,?,?,?)', (auth.token_hash(token), row['id'], csrf, now + config.SESSION_HOURS*3600))
            user = auth.public_user(c, row)
            db.audit(c, user['id'], 'login')
    if user is None:
        raise HTTPException(401, '이메일 또는 비밀번호를 확인하세요.')
    response.set_cookie(auth.COOKIE, token, max_age=config.SESSION_HOURS*3600, httponly=True, secure=config.COOKIE_SECURE, samesite='lax', path='/')
    return {'user': user, 'csrf_token': csrf}


@app.get('/api/auth/me')
def me(user=Depends(auth.current_user)):
    return {'user': {k: v for k, v in user.items() if k != 'csrf_token'}, 'csrf_token': user['csrf_token']}


@app.post('/api/auth/logout')
def logout(request: Request, response: Response, user=Depends(auth.current_user)):
    with db.connect() as c:
        c.execute('DELETE FROM sessions WHERE token_hash=?', (auth.token_hash(request.cookies.get(auth.COOKIE, '')),))
    response.delete_cookie(auth.COOKIE, path='/', secure=config.COOKIE_SECURE, httponly=True, samesite='lax')
    return {'ok': True}


class Password(StrictModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


@app.post('/api/auth/password')
def password(body: Password, request: Request, user=Depends(auth.current_user)):
    with db.connect() as c:
        row = c.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()
        if not auth.verify_password(body.current_password, row['password_hash']):
            raise HTTPException(400, '현재 비밀번호를 확인하세요.')
        if body.current_password == body.new_password:
            raise HTTPException(400, '기존 비밀번호와 다른 값을 입력하세요.')
        c.execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?', (auth.hash_password(body.new_password), user['id']))
        c.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?', (user['id'], auth.token_hash(request.cookies.get(auth.COOKIE, ''))))
        db.audit(c, user['id'], 'password_change', user['id'])
    return {'ok': True}


@app.get('/api/data')
def data(user=Depends(auth.current_user)):
    return catalog.payload(auth.office_scope(user))


@app.get('/api/offices')
def offices(user=Depends(auth.current_user)):
    with db.connect() as c:
        return [dict(r) for r in c.execute('SELECT * FROM offices ORDER BY name') if user['role'] == 'superadmin' or r['id'] in user['office_ids']]


@app.get('/api/meters')
def meters(include_deleted: bool = False, user=Depends(auth.current_user)):
    with db.connect() as c:
        return catalog.list_meters(c, auth.office_scope(user), include_deleted=include_deleted)


def get_meter(c, meter_id, user, include_deleted=False):
    meter = next((m for m in catalog.list_meters(c, auth.office_scope(user), include_deleted=include_deleted) if m['id'] == meter_id), None)
    if meter is None:
        raise HTTPException(404, '계량기를 찾을 수 없습니다.')
    return meter


METER_FIELDS = {'provider', 'customer_number', 'station_id', 'station_name', 'office_id', 'line', 'display_name', 'purpose', 'tariff', 'address', 'active', 'daily_enabled', 'metadata', 'map_x', 'map_y'}


def meter_values(c, body, user, existing=None):
    if set(body) - METER_FIELDS:
        raise HTTPException(422, '허용되지 않은 계량기 필드입니다.')
    value = (existing or {}) | body
    for key in ('provider', 'customer_number', 'station_id', 'station_name', 'office_id', 'line', 'display_name', 'purpose', 'tariff', 'address'):
        raw = value.get(key) or ''
        if not isinstance(raw, (str, int)) or len(str(raw)) > (500 if key == 'address' else 100) or any(ord(ch) < 32 for ch in str(raw)):
            raise HTTPException(422, f'{key} 값이 올바르지 않습니다.')
        value[key] = str(raw).strip()
    value['provider'] = value['provider'] or 'arisu'
    if value['provider'] not in ('arisu', 'other'):
        raise HTTPException(422, 'provider는 arisu 또는 other여야 합니다.')
    cid = value['customer_number']
    if not cid or (value['provider'] == 'arisu' and not re.fullmatch(r'\d{9}', cid)):
        raise HTTPException(422, '아리수 고객번호는 앞자리 0을 포함한 9자리입니다.')
    if existing and (cid != existing['customer_number'] or value['provider'] != existing['provider']):
        raise HTTPException(422, '고객번호·공급기관 변경은 새 계량기로 등록하세요. 기존 이력은 보존됩니다.')
    if not value['display_name']:
        raise HTTPException(422, '계량기 표시명을 입력하세요.')
    if value['line'] and not re.fullmatch(r'[1-9]', value['line']):
        raise HTTPException(422, '호선은 1~9 중 선택하세요.')
    for key in ('active', 'daily_enabled'):
        raw = value.get(key, key == 'active')
        if raw not in (True, False, 0, 1):
            raise HTTPException(422, f'{key}는 참/거짓이어야 합니다.')
        value[key] = int(raw)
    if value['provider'] != 'arisu' and value['daily_enabled']:
        raise HTTPException(422, '아리수 고객번호만 일일 자동 수집을 활성화할 수 있습니다.')
    auth.require_office(user, value['office_id'])
    if not c.execute('SELECT 1 FROM offices WHERE id=?', (value['office_id'],)).fetchone():
        raise HTTPException(422, '등록된 사업소를 선택하세요.')
    station_id = value['station_id']
    if station_id and not c.execute('SELECT 1 FROM stations WHERE id=?', (station_id,)).fetchone():
        raise HTTPException(422, '등록된 역을 선택하거나 새 역명을 입력하세요.')
    if not station_id:
        station_id = value['station_name']
        if not station_id:
            raise HTTPException(422, '역명을 입력하세요.')
        c.execute('INSERT OR IGNORE INTO stations(id,name) VALUES(?,?)', (station_id, station_id))
    value['station_id'] = station_id
    # Coordinates describe the physical station shared by several meters.
    if 'map_x' in body or 'map_y' in body:
        if user['role'] != 'superadmin':
            raise HTTPException(403, '공용 노선도 위치는 총괄 관리자만 변경할 수 있습니다.')
        x, y = value.get('map_x'), value.get('map_y')
        if not all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in (x, y)):
            raise HTTPException(422, '지도 위치는 0~100 사이의 x,y 값을 함께 입력하세요.')
        c.execute('UPDATE stations SET map_x=?,map_y=? WHERE id=?', (x, y, station_id))
    metadata = value.get('metadata') or {}
    if not isinstance(metadata, dict):
        raise HTTPException(422, '계량기 메타데이터가 올바르지 않습니다.')
    if 'metadata' in body:
        if not isinstance(body['metadata'], dict):
            raise HTTPException(422, '계량기 메타데이터가 올바르지 않습니다.')
        if set(body['metadata']) - {'계량기번호', 'arisu_customer_name'} or any(not isinstance(v, str) or len(v) > 100 or any(ord(ch) < 32 for ch in v) for v in body['metadata'].values()):
            raise HTTPException(422, '계량기번호와 고지서상 성명은 100자 이하로 입력하세요.')
        metadata = (existing or {}).get('metadata', {}) | body['metadata']
    name = metadata.get('arisu_customer_name', '').strip()
    if '*' in name or '＊' in name:
        raise HTTPException(422, '별표로 가린 성명 대신 아리수에 등록된 고지서상 성명 전체를 입력하세요.')
    if 'arisu_customer_name' in metadata:
        metadata['arisu_customer_name'] = name
    value['metadata'] = json.dumps(metadata, ensure_ascii=False)
    return value


def save_meter(body, user, meter_id=None):
    try:
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            existing = get_meter(c, meter_id, user) if meter_id else None
            if existing and c.execute("SELECT 1 FROM collection_items WHERE meter_id=? AND status='running'", (meter_id,)).fetchone():
                raise HTTPException(409, '현재 수집 중인 계량기입니다. 수집 완료 후 수정하세요.')
            v = meter_values(c, body, user, existing)
            columns = ('provider', 'customer_number', 'station_id', 'office_id', 'line', 'display_name', 'purpose', 'tariff', 'address', 'active', 'daily_enabled', 'metadata')
            if existing:
                c.execute('UPDATE meters SET ' + ','.join(f'{k}=?' for k in columns) + ',updated_at=? WHERE id=?', [v[k] for k in columns] + [db.now(), meter_id])
            else:
                meter_id = v['customer_number'] if v['provider'] == 'arisu' else 'other-' + secrets.token_hex(8)
                c.execute('INSERT INTO meters(id,' + ','.join(columns) + ',created_at,updated_at) VALUES(' + ','.join('?' for _ in range(len(columns)+3)) + ')', [meter_id] + [v[k] for k in columns] + [db.now(), db.now()])
                if v['provider'] == 'arisu' and v['active']:
                    collection.enqueue(c, [meter_id], 'registration', user['id'])
            db.audit(c, user['id'], 'meter_update' if existing else 'meter_create', meter_id, {k: body[k] for k in body if k != 'metadata'})
            return get_meter(c, meter_id, user)
    except sqlite3.IntegrityError:
        raise HTTPException(409, '이미 등록된 공급기관·고객번호입니다. 기존 계량기의 정보 업데이트를 실행하거나 삭제 목록에서 복원하세요.') from None


@app.post('/api/meters', status_code=201)
def create_meter(body: dict = Body(...), user=Depends(auth.current_user)):
    return save_meter(body, user)


@app.patch('/api/meters/{meter_id}')
def patch_meter(meter_id: str, body: dict = Body(...), user=Depends(auth.current_user)):
    return save_meter(body, user, meter_id)


@app.delete('/api/meters/{meter_id}')
def delete_meter(meter_id: str, user=Depends(auth.current_user)):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        get_meter(c, meter_id, user)
        if c.execute("SELECT 1 FROM collection_items WHERE meter_id=? AND status='running'", (meter_id,)).fetchone():
            raise HTTPException(409, '수집 중인 계량기는 수집 완료 후 삭제할 수 있습니다.')
        c.execute('UPDATE meters SET deleted_at=?,active=0,updated_at=? WHERE id=?', (db.now(), db.now(), meter_id))
        c.execute("UPDATE collection_items SET status='skipped',message='삭제되어 수집에서 제외했습니다.',finished_at=? WHERE meter_id=? AND status='queued'", (db.now(), meter_id))
        db.audit(c, user['id'], 'meter_delete', meter_id)
    return {'ok': True}


@app.post('/api/meters/{meter_id}/restore')
def restore_meter(meter_id: str, user=Depends(auth.current_user)):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        meter = get_meter(c, meter_id, user, include_deleted=True)
        if not meter['deleted_at']:
            raise HTTPException(409, '삭제되지 않은 계량기입니다.')
        c.execute('UPDATE meters SET deleted_at=NULL,active=1,updated_at=? WHERE id=?', (db.now(), meter_id))
        if meter['provider'] == 'arisu':
            collection.enqueue(c, [meter_id], 'restoration', user['id'])
        db.audit(c, user['id'], 'meter_restore', meter_id)
        return get_meter(c, meter_id, user)


@app.get('/api/collection')
def collection_status(user=Depends(auth.current_user)):
    return collection.status(user)


class CollectionRequest(StrictModel):
    meter_id: str | None = Field(default=None, min_length=1, max_length=100)


@app.post('/api/collection', status_code=202)
def collect(body: CollectionRequest, user=Depends(auth.current_user)):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        selected = [get_meter(c, body.meter_id, user)] if body.meter_id else catalog.list_meters(c, auth.office_scope(user))
        selected = [m for m in selected if m['active'] and m['provider'] == 'arisu']
        job_id = collection.enqueue(c, [m['id'] for m in selected], 'manual', user['id'])
        db.audit(c, user['id'], 'collection_start', job_id, {'meter_count': len(selected)})
        return collection.job_view(c, c.execute('SELECT * FROM collection_jobs WHERE id=?', (job_id,)).fetchone(), {m['id']: m for m in selected})


class CollectionSettings(StrictModel):
    enabled: bool = Field(strict=True)
    hour: int = Field(ge=0, le=23, strict=True)


@app.patch('/api/collection/settings')
def collection_settings(body: CollectionSettings, user=Depends(auth.superadmin)):
    with db.connect() as c:
        c.execute("INSERT INTO settings VALUES('collection_schedule',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(body.model_dump()),))
        db.audit(c, user['id'], 'collection_schedule', details=body.model_dump())
        return collection.settings(c)


@app.get('/api/users')
def users(user=Depends(auth.superadmin)):
    with db.connect() as c:
        return [auth.public_user(c, row) for row in c.execute('SELECT * FROM users ORDER BY name,id')]


def save_user(body, actor, user_id=None):
    if set(body) - {'email', 'name', 'password', 'role', 'office_ids', 'active'}:
        raise HTTPException(422, '허용되지 않은 사용자 필드입니다.')
    try:
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone() if user_id else None
            if user_id and row is None:
                raise HTTPException(404, '사용자를 찾을 수 없습니다.')
            old = auth.public_user(c, row) if row else {}
            v = old | body
            email, name = v.get('email', ''), v.get('name', '')
            if not isinstance(email, str) or len(email) > 254 or not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', email):
                raise HTTPException(422, '유효한 업무 이메일을 입력하세요.')
            email = email.strip().lower()
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
                raise HTTPException(422, '담당자 이름을 입력하세요.')
            if v.get('role') not in ('superadmin', 'office_admin') or v.get('active', True) not in (True, False, 0, 1):
                raise HTTPException(422, '역할과 활성 상태를 확인하세요.')
            active, role = bool(v.get('active', True)), v['role']
            offices = v.get('office_ids', [])
            if not isinstance(offices, list) or any(not isinstance(o, str) for o in offices):
                raise HTTPException(422, '담당 사업소 목록이 올바르지 않습니다.')
            offices = sorted(set(offices)) if role == 'office_admin' else []
            if role == 'office_admin' and active and not offices:
                raise HTTPException(422, '사업소 담당자는 담당 사업소를 지정해야 합니다.')
            for office in offices:
                if not c.execute('SELECT 1 FROM offices WHERE id=?', (office,)).fetchone():
                    raise HTTPException(422, '등록된 사업소를 선택하세요.')
                count = c.execute('SELECT count(*) FROM office_members m JOIN users u ON u.id=m.user_id WHERE m.office_id=? AND u.active=1 AND u.id<>?', (office, user_id or -1)).fetchone()[0]
                if active and count >= 2:
                    raise HTTPException(409, '사업소 담당자는 최대 2명까지 지정할 수 있습니다.')
            if row and row['role'] == 'superadmin' and row['active'] and (role != 'superadmin' or not active):
                if not c.execute("SELECT 1 FROM users WHERE role='superadmin' AND active=1 AND id<>?", (user_id,)).fetchone():
                    raise HTTPException(409, '활성 총괄 관리자를 최소 1명 유지해야 합니다.')
            password_hash = row['password_hash'] if row else None
            if body.get('password'):
                try:
                    password_hash = auth.hash_password(body['password'])
                except ValueError as error:
                    raise HTTPException(422, str(error)) from None
            if password_hash is None:
                raise HTTPException(422, '최초 비밀번호를 입력하세요.')
            if row:
                c.execute('UPDATE users SET email=?,name=?,role=?,active=?,password_hash=?,must_change_password=? WHERE id=?',
                          (email, name.strip(), role, int(active), password_hash, int(bool(body.get('password')) or row['must_change_password']), user_id))
                c.execute('DELETE FROM office_members WHERE user_id=?', (user_id,))
                c.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
            else:
                cursor = c.execute('INSERT INTO users(email,name,role,active,password_hash,must_change_password,created_at) VALUES(?,?,?,?,?,1,?)', (email, name.strip(), role, int(active), password_hash, db.now()))
                user_id = cursor.lastrowid
            c.executemany('INSERT INTO office_members(user_id,office_id) VALUES(?,?)', [(user_id, office) for office in offices])
            db.audit(c, actor['id'], 'user_update' if row else 'user_create', user_id, {k: body[k] for k in body if k != 'password'})
            return auth.public_user(c, c.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone())
    except sqlite3.IntegrityError:
        raise HTTPException(409, '이미 등록된 이메일입니다.') from None


@app.post('/api/users', status_code=201)
def create_user(body: dict = Body(...), user=Depends(auth.superadmin)):
    return save_user(body, user)


@app.patch('/api/users/{user_id}')
def patch_user(user_id: int, body: dict = Body(...), user=Depends(auth.superadmin)):
    return save_user(body, user, user_id)


def checked_date(value):
    try:
        return Date.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        raise HTTPException(422, '날짜는 YYYY-MM-DD 형식이어야 합니다.') from None


@app.get('/api/anomalies')
def anomalies(date: str | None = None, include_normal: bool = False, user=Depends(auth.current_user)):
    scope = auth.office_scope(user)
    date = checked_date(date or data_access.reference_date(scope))
    return {'기준일': date, 'calendar': data_access.calendar_info(date), 'items': data_access.anomalies_on(date, include_normal, scope)}


@app.get('/api/summary')
def summary(date: str | None = None, refresh: bool = False, user=Depends(auth.current_user)):
    scope = auth.office_scope(user)
    return agent.daily_summary(checked_date(date or data_access.reference_date(scope)), scope)


class Analyze(StrictModel):
    meter_id: str = Field(min_length=1, max_length=100)
    date: str | None = None


def analysis_input(body, user):
    with db.connect() as c:
        meter = get_meter(c, body.meter_id, user)
    date = checked_date(body.date or data_access.reference_date(auth.office_scope(user)))
    item = data_access.find_one(body.meter_id, date, auth.office_scope(user))
    if not item:
        raise HTTPException(404, '해당 계량기와 날짜의 분석 데이터가 없습니다.')
    if item['likely_data_error']:
        raise HTTPException(422, '자료 확인이 필요한 관측값입니다. 원자료를 확인한 뒤 원인 분석과 이상 알림을 요청하세요.')
    return meter, date, item


@app.post('/api/analyze')
def analyze(body: Analyze, user=Depends(auth.current_user)):
    _, date, _ = analysis_input(body, user)
    return agent.analyze_cause(body.meter_id, date, auth.office_scope(user))


@app.post('/api/alert')
def alert(body: Analyze, user=Depends(auth.current_user)):
    meter, _, item = analysis_input(body, user)
    if item['심각도'] not in ('주의', '경고'):
        raise HTTPException(422, '주의·경고 항목에만 이상 알림을 발송할 수 있습니다.')
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        recipients = [r[0] for r in c.execute('SELECT u.email FROM users u JOIN office_members m ON m.user_id=u.id WHERE u.active=1 AND m.office_id=?', (meter['office_id'],))]
        recent = c.execute("SELECT created_at FROM audit_log WHERE action IN ('alert_attempt','alert_sent') AND target=? ORDER BY id DESC LIMIT 1", (body.meter_id + ':' + item['날짜'],)).fetchone()
        if recent and recent[0] > datetime.fromtimestamp(time.time()-60, timezone.utc).isoformat(timespec='seconds'):
            raise HTTPException(429, '같은 항목은 1분 후 다시 발송할 수 있습니다.')
        db.audit(c, user['id'], 'alert_attempt', body.meter_id + ':' + item['날짜'])
    result = mailer.send_mail(f"[{item['심각도']}] {item['역명']} 수도 사용량 확인 ({item['날짜']})", mailer.build_alert_html(item), ','.join(recipients))
    with db.connect() as c:
        db.audit(c, user['id'], 'alert_sent' if result['sent'] else 'alert_failed', body.meter_id + ':' + item['날짜'])
    return {**result, 'item': item}


@app.get('/api/bills/{bill_id}/pdf')
def bill_pdf(bill_id: str, download: bool = False, user=Depends(auth.current_user)):
    with db.connect() as c:
        bill = c.execute('SELECT * FROM bills WHERE id=?', (bill_id,)).fetchone()
        if bill is None:
            raise HTTPException(404, '청구내역을 찾을 수 없습니다.')
        meter = get_meter(c, bill['meter_id'], user)
    payload = json.loads(bill['payload']) | {'id': bill['id'], 'source': bill['source'], 'gubun': bill['gubun'], 'notice_number': bill['notice_number']}
    suffix = '_' + bill['notice_number'] if bill['notice_number'] else ''
    name = f"{meter['display_name']}_{bill['period']}_{bill['gubun']}{suffix}.pdf"
    return Response(documents.bill_pdf(meter, payload), media_type='application/pdf',
                    headers={'Content-Disposition': f"{'attachment' if download else 'inline'}; filename=water-bill.pdf; filename*=UTF-8''{quote(name, safe='')}"})


def export_rows(user, kind, start=None, end=None, office_id=None, line=None, meter_id=None):
    if kind not in ('usage', 'bills'):
        raise HTTPException(422, 'kind는 usage 또는 bills여야 합니다.')
    start, end = checked_date(start or '2000-01-01'), checked_date(end or Date.today().isoformat())
    if start > end:
        raise HTTPException(422, '시작일은 종료일보다 늦을 수 없습니다.')
    if office_id:
        auth.require_office(user, office_id)
    with db.connect() as c:
        available = catalog.list_meters(c, auth.office_scope(user))
        if meter_id:
            get_meter(c, meter_id, user)
        selected = [m for m in available if (not office_id or m['office_id'] == office_id) and (not line or m['line'] == line) and (not meter_id or m['id'] == meter_id)]
        daily, _ = catalog.data_sources() if kind == 'usage' else ({}, {})
        rows = []
        for m in selected:
            meta = {'계량기ID': m['id'], '고객번호': m['customer_number'], '역명': m['display_name'], '사업소ID': m['office_id'], '영업사업소': m['office_name'], '호선': m['line'], '사용목적': m['purpose']}
            if kind == 'usage':
                if m['provider'] != 'arisu' or not m['daily_enabled']:
                    continue
                for r in daily.get(m['customer_number'], {}).get('usage', []):
                    if start <= r['date'] <= end:
                        rows.append(meta | {'날짜': r['date'], '사용량_톤': r['value']})
            else:
                for b in c.execute('SELECT * FROM bills WHERE meter_id=? AND period>=? AND period<=? ORDER BY period,gubun', (m['id'], start[:7], end[:7])):
                    payload = json.loads(b['payload']) | {'source': b['source']}
                    rows.append(meta | {'청구월': b['period'], '청구구분': b['gubun'], '고지번호': b['notice_number'], **{k: payload.get(k) for k in ('사용량', '지하수사용량', '총사용량', '납부금액', '부과금액', '총사용금액', '차감금액', '상수도_기본료', '상수도_사용료', '하수도_사용료', '물이용부담금', '계량기대금', '설치비', '연체금', '수납상태', '납부방법', '납기일', 'periodStart', 'periodEnd', 'summary_only', 'detail_available')}, '집계사용량_톤': catalog.bill_usage(payload), '출처': b['source']})
    return rows


@app.get('/api/export.xlsx')
def export(kind: str = 'usage', start: str | None = None, end: str | None = None, office_id: str | None = None, line: str | None = None, meter_id: str | None = None, user=Depends(auth.current_user)):
    rows = export_rows(user, kind, start, end, office_id, line, meter_id)
    return Response(documents.export_xlsx(rows), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment; filename=water-{kind}.xlsx'})


@app.get('/api/stats')
def statistics(start: str | None = None, end: str | None = None, office_id: str | None = None, line: str | None = None, meter_id: str | None = None, user=Depends(auth.current_user)):
    groups = {}
    for kind in ('usage', 'bills'):
        for row in export_rows(user, kind, start, end, office_id, line, meter_id):
            month = row.get('날짜', row.get('청구월'))[:7]
            key = (month, row['사업소ID'], row['호선'])
            group = groups.setdefault(key, {'month': month, 'office_id': row['사업소ID'], 'office_name': row['영업사업소'], 'line': row['호선'], 'usage_ton': None, 'billed_usage_ton': None, 'billed_won': None, 'observation_count': 0, 'bill_count': 0, 'summary_bill_count': 0})
            if kind == 'bills':
                if row.get('납부금액') is None:
                    row['납부금액'] = row.get('부과금액')
                    group['summary_bill_count'] += 1
            fields = [('usage_ton', '사용량_톤')] if kind == 'usage' else [('billed_usage_ton', '집계사용량_톤'), ('billed_won', '납부금액')]
            for target, source in fields:
                number = catalog.number(row.get(source))
                if number is not None:
                    group[target] = round((group[target] or 0) + number, 3)
            group['observation_count' if kind == 'usage' else 'bill_count'] += 1
    return {'rows': [groups[key] for key in sorted(groups)], 'note': '일 사용량은 관측일, 요금은 청구월 기준입니다. 요금은 납부금액을 우선 합산하며 상세 미확인 건은 부과금액으로 집계합니다. 상세 미확인 요금은 수납상태를 별도로 확인하세요. 결측은 합산하지 않습니다.'}


# Only explicitly built frontend assets are public; raw data directories are never mounted.
DIST = config.ROOT / 'front/dist'
if (DIST / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')


@app.get('/{path:path}')
def spa(path: str):
    if path.startswith('api/') or path.endswith('.json'):
        raise HTTPException(404, '경로를 찾을 수 없습니다.')
    resolved = (DIST / path).resolve()
    if path and resolved.is_relative_to(DIST.resolve()) and resolved.is_file() and resolved.suffix in ('.png', '.svg', '.ico', '.woff2'):
        return FileResponse(resolved)
    if (DIST / 'index.html').is_file():
        return FileResponse(DIST / 'index.html', headers={'Cache-Control': 'no-cache'})
    raise HTTPException(404, '프론트엔드를 빌드하거나 개발 서버(5173)를 실행하세요.')
