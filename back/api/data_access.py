"""Use the same private snapshot and registry as the dashboard, scoped before analysis."""
from datetime import date as Date
from . import catalog, config, db

SEV_RANK = {'정상': 0, '주의': 1, '경고': 2}


def reference_date(office_ids=None):
    if config.TODAY_OVERRIDE:
        return config.TODAY_OVERRIDE
    daily, risk = catalog.data_sources()
    with db.connect() as c:
        ids = {m['customer_number'] for m in catalog.list_meters(c, office_ids)
               if m['active'] and catalog.meter_data_mode(m, daily) == 'daily'}
    dates = [r['date'] for cid in ids for r in risk.get(cid, [])]
    if not dates:
        dates = [r['date'] for cid in ids for r in daily.get(cid, {}).get('usage', [])]
    return max(dates, default=Date.today().isoformat())


def calendar_info(date):
    day = Date.fromisoformat(date)
    result = {'weekend': day.weekday() >= 5, 'holiday': None, 'holiday_name': '', '요일': '월화수목금토일'[day.weekday()]}
    for row in catalog.read_csv(config.DATE_INDEX):
        if row.get('날짜') == date:
            result.update(holiday=str(row.get('공휴일')) in ('1', '1.0', 'True'), holiday_name=row.get('공휴일명') or '')
            break
    return result


def item_from_row(meter, row):
    pred, actual = catalog.number(row.get('pred')), catalog.number(row.get('actual'))
    error, z = catalog.number(row.get('residual')), catalog.number(row.get('z'))
    data_error = row.get('err') in (True, 'true', 'True', 1)
    return {'meter_id': meter['id'], '고객번호': meter['customer_number'], '역명': meter['display_name'],
            '날짜': row['date'], '심각도': '자료 확인' if data_error else row.get('severity') or '미분석', '방향': row.get('dir') or '',
            'predicted_ton': pred, 'actual_ton': actual, 'error_ton': error, 'deviation_score': z,
            'pct': round(error / pred * 100) if pred and error is not None else None,
            'likely_data_error': data_error,
            '영업사업소': meter['office_name'], '용도': meter['purpose']}


def anomalies_on(date=None, include_normal=False, office_ids=None):
    date = date or reference_date(office_ids)
    with db.connect() as c:
        meters = catalog.list_meters(c, office_ids)
    daily, risk = catalog.data_sources()
    items = [item_from_row(m, r) for m in meters if m['active'] and catalog.meter_data_mode(m, daily) == 'daily'
             for r in risk.get(m['customer_number'], []) if r['date'] == date]
    items = [item for item in items if include_normal or item['심각도'] in ('주의', '경고', '자료 확인')]
    return sorted(items, key=lambda x: (x['likely_data_error'], -SEV_RANK.get(x['심각도'], 0), -abs(x['deviation_score'] or 0)))


def find_one(meter_id, date=None, office_ids=None):
    return next((i for i in anomalies_on(date, True, office_ids) if i['meter_id'] == meter_id), None)


def station_history(meter_id, date, office_ids=None, days=7):
    with db.connect() as c:
        meter = next((m for m in catalog.list_meters(c, office_ids) if m['id'] == meter_id), None)
    if not meter or not meter['active']:
        return []
    daily, risk = catalog.data_sources()
    if catalog.meter_data_mode(meter, daily) != 'daily':
        return []
    rows = sorted((r for r in risk.get(meter['customer_number'], []) if r['date'] <= date), key=lambda r: r['date'])[-days:]
    return [item_from_row(meter, row) for row in rows]
