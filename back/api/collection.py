"""Persistent collection queue and one daily KST run, owned by the API process."""
import fcntl
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from . import auth, catalog, config, db

KST = ZoneInfo('Asia/Seoul')
ACTIVE = ('queued', 'running')
logger = logging.getLogger(__name__)


def configured():
    ready = all(config.configured(os.getenv(key) or os.getenv(old, '')) for key, old in
                [('ARISU_USER_ID', 'I121_USER_ID'), ('ARISU_USER_PWD', 'I121_USER_PWD')])
    return {'water': ready, 'bills': True}


def settings(c, current=None):
    current = current or datetime.now(KST)
    row = c.execute("SELECT value FROM settings WHERE key='collection_schedule'").fetchone()
    value = json.loads(row[0]) if row else {'enabled': True, 'hour': 8}
    next_run = current.replace(hour=value['hour'], minute=0, second=0, microsecond=0)
    last = c.execute("SELECT value FROM settings WHERE key='collection_auto_day'").fetchone()
    if next_run <= current and last and last[0] == current.date().isoformat():
        next_run += timedelta(days=1)
    elif next_run < current:
        next_run = current
    return value | {'timezone': 'Asia/Seoul', 'next_run_at': next_run.isoformat()
                    if value['enabled'] and config.COLLECTION_WORKER_ENABLED else None}


def enqueue(c, meter_ids, trigger, actor_id=None):
    """Caller holds BEGIN IMMEDIATE, so a customer cannot be queued twice."""
    if not meter_ids:
        raise HTTPException(422, '수집할 활성 아리수 계량기가 없습니다.')
    placeholders = ','.join('?' for _ in meter_ids)
    busy = c.execute(f"SELECT 1 FROM collection_items WHERE meter_id IN ({placeholders}) AND status IN ('queued','running') LIMIT 1", meter_ids).fetchone()
    if busy:
        raise HTTPException(409, '선택한 계량기는 이미 수집 중이거나 대기 중입니다. 진행 상황을 확인하세요.')
    job_id = c.execute("INSERT INTO collection_jobs(status,trigger,actor_id,created_at) VALUES('queued',?,?,?)",
                       (trigger, actor_id, db.now())).lastrowid
    c.executemany('INSERT INTO collection_items(job_id,meter_id) VALUES(?,?)', [(job_id, m) for m in meter_ids])
    return job_id


def job_view(c, job, allowed):
    if job is None:
        return None
    items = [dict(r) for r in c.execute('SELECT * FROM collection_items WHERE job_id=? ORDER BY meter_id', (job['id'],)) if r['meter_id'] in allowed]
    if not items:
        return None
    for item in items:
        item.update({'connection_verified': bool(item['connection_verified']),
                     'display_name': allowed[item['meter_id']]['display_name'],
                     'customer_number': allowed[item['meter_id']]['customer_number']})
    completed = sum(i['status'] not in ACTIVE for i in items)
    running = next((i for i in items if i['status'] == 'running'), None)
    # Status and counts describe only the viewer's permitted meters.
    status = 'running' if running else 'queued' if completed < len(items) else outcome(items)
    if job['status'] == 'interrupted':
        status = 'interrupted'
    counts = [('성공', ('success',)), ('자료 없음', ('empty',)), ('조회 권한 필요', ('access_required',)), ('일부 실패', ('partial',)),
              ('실패', ('failed', 'configuration_required')), ('제외', ('skipped',)), ('중단', ('interrupted',))]
    summary = ' · '.join(f'{label} {count}개' for label, values in counts
                         if (count := sum(i['status'] in values for i in items)))
    messages = {i['message'] for i in items}
    if status == 'failed' and len(messages) == 1:
        summary += '. ' + next(iter(messages))
    return {k: job[k] for k in ('id', 'trigger', 'created_at', 'started_at', 'finished_at')} | {
        'status': status, 'total': len(items), 'completed': completed, 'items': items,
        'message': running['message'] if running else '수집 대기 중입니다.' if status == 'queued' else summary}


def outcome(items):
    successes = sum(i['status'] in ('success', 'empty') for i in items)
    if successes == len(items):
        return 'success'
    if successes or any(i['status'] == 'partial' for i in items):
        return 'partial'
    return 'failed'


def status(user):
    with db.connect() as c:
        meters = catalog.list_meters(c, auth.office_scope(user))
        allowed = {m['id']: m for m in meters}
        marks = ','.join('?' for _ in allowed)
        jobs = c.execute(f'SELECT * FROM collection_jobs WHERE EXISTS (SELECT 1 FROM collection_items i WHERE i.job_id=collection_jobs.id AND i.meter_id IN ({marks})) ORDER BY id DESC', list(allowed)) if allowed else []
        views = [job_view(c, r, allowed) for index, r in enumerate(jobs) if index < 20 or r['status'] in ACTIVE]
        views = [v for v in views if v]
        active = [v for v in views if v['status'] in ACTIVE]
        running = next((v for v in reversed(active) if v['status'] == 'running'), active[-1] if active else None)
        states = []
        for meter in meters:
            if meter['provider'] != 'arisu':
                continue
            latest = c.execute('SELECT * FROM collection_items WHERE meter_id=? ORDER BY job_id DESC LIMIT 1', (meter['id'],)).fetchone()
            success = c.execute('SELECT finished_at FROM collection_items WHERE meter_id=? AND connection_verified=1 ORDER BY job_id DESC LIMIT 1', (meter['id'],)).fetchone()
            states.append({'meter_id': meter['id'], 'status': latest['status'] if latest else 'unverified',
                'message': latest['message'] if latest else '아리수 연결 확인 전입니다.',
                'last_attempt_at': latest['started_at'] if latest else None,
                'last_success_at': success[0] if success else None,
                'daily_rows': latest['daily_rows'] if latest else 0, 'bill_rows': latest['bill_rows'] if latest else 0,
                'connection_verified': bool(success)})
        return {'settings': settings(c), 'configured': configured(), 'worker_enabled': config.COLLECTION_WORKER_ENABLED,
                'running': running, 'latest': views[0] if views else None, 'history': views[:20], 'meters': states}


def schedule_due(c, current=None):
    current = current or datetime.now(KST)
    schedule = settings(c, current)
    day = current.date().isoformat()
    last = c.execute("SELECT value FROM settings WHERE key='collection_auto_day'").fetchone()
    if not schedule['enabled'] or current.hour < schedule['hour'] or (last and last[0] == day):
        return
    if c.execute("SELECT 1 FROM collection_jobs WHERE status IN ('queued','running')").fetchone():
        return
    ids = [m['id'] for m in catalog.list_meters(c) if m['active'] and m['provider'] == 'arisu']
    if ids:
        enqueue(c, ids, 'automatic')
        c.execute("INSERT INTO settings VALUES('collection_auto_day',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (day,))


def run_job(job_id, stop):
    from back.pipelines.incremental import collect_meter
    from back.scripts.billing_etl.i121_crawler.auth import collection_session
    session = None

    def collect_shared(meter, progress):
        nonlocal session
        if session is None:
            try:
                session = collection_session(config.ROOT / '.env')
            except Exception as exc:
                result = failure_result(exc)
                logger.error('Collection session setup failed for job %s (%s)', job_id, type(exc).__name__)
                return result | {'setup_failed': True}
        return collect_meter(meter, progress=progress, session=session)
    try:
        _run_job(job_id, stop, collect_shared)
    finally:
        if session is not None:
            session.close()


def failure_result(exc):
    from requests.exceptions import ConnectionError, HTTPError, Timeout
    from back.scripts.billing_etl.i121_crawler.auth import ConfigurationError, LoginError
    status = 'failed'
    if isinstance(exc, ConfigurationError):
        status, message = 'configuration_required', '서버에 아리수 아이디와 비밀번호를 설정해야 합니다.'
    elif isinstance(exc, LoginError):
        message = '아리수 로그인에 실패했습니다. 계정과 조회 권한을 확인하세요.'
    elif isinstance(exc, Timeout):
        message = '아리수 서버의 응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요.'
    elif isinstance(exc, HTTPError):
        code = exc.response.status_code if exc.response is not None else None
        if code in (401, 403):
            message = f'아리수 서버가 접근을 거부했습니다(HTTP {code}). 로그인 방식과 조회 권한을 확인해야 합니다.'
        elif code == 404:
            message = '아리수 조회 주소를 찾을 수 없습니다(HTTP 404). 수집 연결 주소를 확인해야 합니다.'
        elif code == 429:
            message = '아리수 요청 한도를 초과했습니다(HTTP 429). 잠시 후 다시 시도하세요.'
        else:
            message = f'아리수 서버가 오류를 반환했습니다{f"(HTTP {code})" if code else ""}. 잠시 후 다시 시도하세요.'
    elif isinstance(exc, ConnectionError):
        message = '아리수 서버에 연결하지 못했습니다. 서버의 네트워크 연결을 확인하세요.'
    else:
        message = '수집 처리에 실패했습니다. 서버 기록을 확인하세요.'
    return {'status': status, 'message': message + ' 기존 자료는 보존됩니다.'}


def _run_job(job_id, stop, collect_meter):
    with db.connect() as c:
        ids = [r[0] for r in c.execute("SELECT meter_id FROM collection_items WHERE job_id=? AND status='queued' ORDER BY meter_id", (job_id,))]
    for meter_id in ids:
        if stop.is_set():
            break
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            pending = c.execute('SELECT status FROM collection_items WHERE job_id=? AND meter_id=?', (job_id, meter_id)).fetchone()
            if not pending or pending['status'] != 'queued':
                continue
            meter = next((m for m in catalog.list_meters(c) if m['id'] == meter_id), None)
            if not meter or not meter['active'] or meter['provider'] != 'arisu':
                c.execute("UPDATE collection_items SET status='skipped',message='삭제 또는 비활성화되어 수집에서 제외했습니다.',finished_at=? WHERE job_id=? AND meter_id=?", (db.now(), job_id, meter_id))
                continue
            c.execute("UPDATE collection_items SET status='running',started_at=?,message='아리수 연결을 확인하고 있습니다.' WHERE job_id=? AND meter_id=?", (db.now(), job_id, meter_id))

        def progress(message):
            with db.connect() as c:
                c.execute('UPDATE collection_items SET message=? WHERE job_id=? AND meter_id=?', (message, job_id, meter_id))
        try:
            result = collect_meter(meter, progress=progress)
        except Exception as exc:
            logger.error('Collection failed for job %s (%s)', job_id, type(exc).__name__)
            result = failure_result(exc)
        if result.get('setup_failed'):
            with db.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                c.execute("UPDATE collection_items SET status='skipped',message='삭제 또는 비활성화되어 수집에서 제외했습니다.',finished_at=? WHERE job_id=? AND status='queued' AND meter_id NOT IN (SELECT id FROM meters WHERE active=1 AND deleted_at IS NULL AND provider='arisu')", (db.now(), job_id))
                c.execute("UPDATE collection_items SET status=?,message=?,started_at=COALESCE(started_at,?),finished_at=? WHERE job_id=? AND status IN ('queued','running')",
                          (result['status'], '공통 연결 단계에서 중단했습니다. ' + result['message'], db.now(), db.now(), job_id))
            break
        with db.connect() as c:
            c.execute('UPDATE collection_items SET status=?,message=?,finished_at=?,daily_rows=?,bill_rows=?,connection_verified=? WHERE job_id=? AND meter_id=?',
                      (result['status'], result['message'], db.now(), result.get('daily_rows', 0), result.get('bill_rows', 0), int(result.get('connection_verified', False)), job_id, meter_id))
    with db.connect() as c:
        items = list(c.execute('SELECT status FROM collection_items WHERE job_id=?', (job_id,)))
        state = 'interrupted' if stop.is_set() else outcome(items)
        if stop.is_set():
            c.execute("UPDATE collection_items SET status='interrupted',message='서버가 중지되었습니다. 정보 업데이트로 다시 시도하세요.',finished_at=? WHERE job_id=? AND status IN ('queued','running')", (db.now(), job_id))
        c.execute('UPDATE collection_jobs SET status=?,finished_at=? WHERE id=?', (state, db.now(), job_id))


def worker(stop):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (config.DATA_DIR / '.collection-worker.lock').open('a') as lock:
        while not stop.is_set():
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                stop.wait(2)  # Take over if the API process owning this queue exits.
        else:
            return
        with db.connect() as c:
            c.execute("UPDATE collection_items SET status='interrupted',message='이전 수집 중 서버가 중지되었습니다. 다시 시도하세요.',finished_at=? WHERE job_id IN (SELECT id FROM collection_jobs WHERE status='running') AND status IN ('queued','running')", (db.now(),))
            c.execute("UPDATE collection_jobs SET status='interrupted',finished_at=? WHERE status='running'", (db.now(),))
        while not stop.is_set():
            try:
                with db.connect() as c:
                    c.execute('BEGIN IMMEDIATE')
                    schedule_due(c)
                    row = c.execute("SELECT id FROM collection_jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
                    if row:
                        c.execute("UPDATE collection_jobs SET status='running',started_at=? WHERE id=?", (db.now(), row[0]))
                if row:
                    run_job(row[0], stop)
                    continue
            except Exception as exc:
                logger.error('Collection worker failed (%s)', type(exc).__name__)
                with db.connect() as c:
                    c.execute("UPDATE collection_items SET status='failed',message='수집 처리 오류입니다. 다시 시도하세요.',finished_at=? WHERE job_id IN (SELECT id FROM collection_jobs WHERE status='running') AND status IN ('queued','running')", (db.now(),))
                    c.execute("UPDATE collection_jobs SET status='failed',finished_at=? WHERE status='running'", (db.now(),))
            stop.wait(2)


def start_worker():
    stop = threading.Event()
    thread = threading.Thread(target=worker, args=(stop,), name='arisu-collection', daemon=True)
    if config.COLLECTION_WORKER_ENABLED:
        thread.start()
    return stop, thread
