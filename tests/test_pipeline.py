"""Offline collector regressions. No credentials, network requests, or production writes."""
import csv
import json
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from back.pipelines.common import merge_csv
from back.pipelines.daily_water import scraper as water
from back.pipelines.daily_ridership import scraper as riders
from back.scripts.billing_etl import crawl_bills as bills
from back.scripts.billing_etl.i121_crawler import auth
from back.ml.lightgbm import metric, dataset
from back.pipelines.refresh import build_dataset, publish_snapshot
from back.pipelines import refresh

METERS = [{"id": str(n), "customer_number": str(n).zfill(9), "provider": "arisu",
           "station_name": {1: "강동역", 2: "길동역"}[n], "line": n, "active": True, "daily_enabled": True}
          for n in [1, 2]]


def reading_payload(value=12):
    return {"result": True, "searchMkey": "000000001", "groups": [
        {"mkey": "000000001", "napgi": "20260930", "thsmmUseqty": "100", "details": [
            {"measDt": "2026-06-01 00:00:00", "realGcDay": "2026060200",
             "thsmmPointer": "1,000", "dayUseQty": value, "thsmmUseqty": "0", "status": "정상"}]}]}


def reading_response(payload=None):
    payload = reading_payload() if payload is None else payload
    return Mock(text=json.dumps(payload), url='https://i121.seoul.go.kr/cyber/front/mypage/JR_remoteMeterHistory.do',
                status_code=200, json=Mock(return_value=payload))


def bill_html():
    return '<table><caption>부과내역이며</caption><tbody>' + ''.join(
        f'<tr><td>{i}</td><td>000000001</td><td>{kind}</td><td>2026-06-30</td><td>수납 완료</td><td>100</td><td>역1</td><td>20</td><td><a onclick="jungInfoDetail(\'20260630\')"></a></td></tr>'
        for i, kind in enumerate(['정기분', '수시분'], 1)) + '</tbody></table>'


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self, path):
        with path.open(encoding='utf-8-sig', newline='') as fp:
            return list(csv.DictReader(fp))

    def test_water_month_reuse_upsert_partial_and_login_error(self):
        session = Mock()
        response = reading_response()
        session.get.return_value = response
        reports = water.scrape_range(date(2026, 6, 1), date(2026, 6, 2), meters=METERS[:1],
                                     session=session, out_dir=self.path, sleep=0)
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(reports[1]['status'], 'pending')
        self.assertFalse((self.path / '2026-06-02.csv').exists())
        water.scrape_range(date(2026, 6, 1), date(2026, 6, 1), meters=METERS[:1],
                          session=session, out_dir=self.path, sleep=0)
        path = self.path / '2026-06-01.csv'
        self.assertEqual(len(self.rows(path)), 1)
        before = path.read_bytes()
        response.text = '<input name="userId"><input name="userPwd">'
        reports = water.scrape_range(date(2026, 6, 1), date(2026, 6, 1), meters=METERS,
                                     session=session, out_dir=self.path, sleep=0)
        self.assertEqual(reports[0]['status'], 'failed')
        self.assertEqual(path.read_bytes(), before)

    def test_water_json_identity_empty_error_and_numeric_validation(self):
        session = Mock()
        for identity in ('top', 'group'):
            payload = reading_payload()
            if identity == 'top':
                payload['searchMkey'] = '000000002'
            else:
                payload['groups'][0]['mkey'] = '000000002'
            session.get.return_value = reading_response(payload)
            with self.assertRaises(ValueError):
                water.fetch_month(session, METERS[0], '2026-06')
        for value in ('', None, 'NaN', '-1', 'Infinity'):
            session.get.return_value = reading_response(reading_payload(value))
            with self.subTest(value=value), self.assertRaises(ValueError):
                water.fetch_month(session, METERS[0], '2026-06')
        session.get.return_value = reading_response(reading_payload(0))
        row = water.fetch_month(session, METERS[0], '2026-06')[0]
        self.assertEqual((row['일사용량(톤)'], row['납기별누적사용량(톤)']), ('0', '0'))
        self.assertEqual((row['사용일'], row['검침일자'], row['지침값']), ('2026-06-01', '2026-06-02', '1000'))
        self.assertEqual(session.get.call_args.kwargs['params']['searchEndYm'], '2026-09')
        for payload, error in [({'result': False, 'message': '로그인 시간이 만료되었습니다.'}, auth.LoginError),
                               ({'result': False, 'message': '조회 가능한 고객번호가 아닙니다.'}, auth.CustomerAccessError),
                               ({'result': False, 'message': '조회 오류'}, ValueError),
                               ({'result': True, 'searchMkey': '000000001'}, ValueError)]:
            session.get.return_value = reading_response(payload)
            with self.assertRaises(error):
                water.fetch_month(session, METERS[0], '2026-06')
        session.get.return_value = reading_response({'result': True, 'searchMkey': '000000001', 'groups': []})
        self.assertEqual(water.fetch_month(session, METERS[0], '2026-06'), [])

    def test_water_json_skips_incomplete_or_abnormal_observations(self):
        session = Mock()
        payload = reading_payload()
        detail = payload['groups'][0]['details'][0]
        for change in ({'status': '수집중'}, {'measDt': '2026-06-02 00:00:00', 'realGcDay': '2026060300'},
                       {'realGcDay': '2026060300'}):
            payload['groups'][0]['details'] = [detail | change]
            session.get.return_value = reading_response(payload)
            with patch.object(water, 'today', return_value=date(2026, 6, 2)):
                self.assertEqual(water.fetch_month(session, METERS[0], '2026-06'), [])
        payload['groups'][0]['details'] = [detail | {'measDt': '2026-06-31 00:00:00'}]
        session.get.return_value = reading_response(payload)
        with self.assertRaises(ValueError):
            water.fetch_month(session, METERS[0], '2026-06')

    def test_invalid_reading_is_reported_by_day_without_losing_good_days(self):
        payload = reading_payload()
        detail = payload['groups'][0]['details'][0]
        payload['groups'][0]['details'].extend([
            detail | {'measDt': '2026-06-02', 'realGcDay': '2026060300', 'dayUseQty': '-6'},
            detail | {'measDt': '2026-06-03', 'realGcDay': '2026060400', 'dayUseQty': ''},
            detail | {'measDt': '2026-06-04', 'realGcDay': '2026060500', 'dayUseQty': '3186'}])
        session = Mock()
        session.get.return_value = reading_response(payload)
        with self.assertRaises(ValueError):
            water.fetch_month(session, METERS[0], '2026-06')
        issues = []
        rows = water.fetch_month(session, METERS[0], '2026-06', issues=issues)
        self.assertEqual(issues, ['2026-06-02', '2026-06-03'])
        self.assertEqual([r['사용일'] for r in rows], ['2026-06-01', '2026-06-04'])
        self.assertEqual(rows[-1]['일사용량(톤)'], '3186')
        reports = water.scrape_range(date(2026, 6, 1), date(2026, 6, 4), meters=METERS[:1],
                                     session=session, out_dir=self.path, sleep=0)
        self.assertEqual([r['status'] for r in reports], ['complete', 'failed', 'failed', 'complete'])
        self.assertEqual([r['errors'][0]['date'] for r in reports if r['errors']], issues)
        self.assertTrue((self.path / '2026-06-01.csv').exists())
        self.assertTrue((self.path / '2026-06-04.csv').exists())

    def test_latest_normal_reading_clears_duplicate_source_issue(self):
        history = reading_payload('')
        history['groups'][0]['details'] *= 2
        session = Mock()
        session.get.side_effect = [reading_response(history), reading_response(reading_payload(0))]
        issues = []
        with patch.object(water, 'today', return_value=date(2026, 6, 23)):
            rows = water.fetch_month(session, METERS[0], '2026-06', issues=issues)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['일사용량(톤)'], '0')
        self.assertEqual(issues, [])

    def test_matching_daily_reading_in_two_due_periods_is_only_counted_once(self):
        payload = reading_payload()
        original = payload['groups'][0]
        detail = original['details'][0]
        duplicate = original | {'napgi': '20261031', 'details': [detail | {
            'thsmmPointer': '1000.0', 'dayUseQty': '12.0', 'thsmmUseqty': '999'}]}
        payload['groups'].append(duplicate)
        session = Mock()
        session.get.return_value = reading_response(payload)
        rows = water.fetch_month(session, METERS[0], '2026-06')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['일사용량(톤)'], '12')
        self.assertEqual(rows[0]['납기별누적사용량(톤)'], '0')
        for change in ({'realGcDay': '2026060300'}, {'thsmmPointer': '1001'}, {'dayUseQty': '13'}):
            duplicate['details'] = [detail | change]
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'Conflicting'):
                water.fetch_month(session, METERS[0], '2026-06')

    def test_latest_daily_readings_fill_unbilled_days_and_reuse_one_query(self):
        def payload(days):
            result = reading_payload()
            detail = result['groups'][0]['details'][0]
            result['groups'][0]['details'] = [detail | {'measDt': day, 'realGcDay': measured}
                for day, measured in days]
            return result
        history = payload([('2026-08-22', '2026082300')])
        latest = payload([('2026-08-22', '2026082300'), ('2026-08-23', '2026082400'),
                          ('2026-09-22', '2026092300'), ('2026-09-23', '2026092400')])
        session = Mock()
        session.get.side_effect = lambda url, **_: reading_response(latest if 'DayList' in url else history)
        with patch.object(water, 'today', return_value=date(2026, 9, 23)):
            august = water.fetch_month(session, METERS[0], '2026-08')
            september = water.fetch_month(session, METERS[0], '2026-09')
        self.assertEqual([r['사용일'] for r in august], ['2026-08-22', '2026-08-23'])
        self.assertEqual([r['사용일'] for r in september], ['2026-09-22'])
        urls = [call.args[0] for call in session.get.call_args_list]
        self.assertEqual(sum('DayList' in url for url in urls), 1)
        self.assertEqual(len(urls), 3)
        with patch.object(water, 'today', return_value=date(2026, 9, 24)):
            next_day = water.fetch_month(session, METERS[0], '2026-09')
        self.assertEqual([r['사용일'] for r in next_day], ['2026-09-22', '2026-09-23'])
        self.assertEqual(sum('DayList' in call.args[0] for call in session.get.call_args_list), 2)

    def test_latest_daily_response_also_rejects_another_customer(self):
        history = {'result': True, 'searchMkey': '000000001', 'groups': []}
        latest = {'result': True, 'searchMkey': '000000002', 'groups': []}
        session = Mock()
        session.get.side_effect = [reading_response(history), reading_response(latest)]
        with patch.object(water, 'today', return_value=date(2026, 9, 23)), self.assertRaises(ValueError):
            water.fetch_month(session, METERS[0], '2026-09')
        self.assertEqual(session._arisu_day_readings, {})

    def test_ridership_partial_retains_previous_and_pending_never_zeros(self):
        path = self.path / '2026-06-01.csv'
        fields = ['고객번호', '역명', '날짜', '총승객수']
        merge_csv(path, [{'고객번호': '000000002', '역명': '역2', '날짜': '2026-06-01', '총승객수': 40}], fields, ['고객번호', '날짜'])
        riders.scrape(date(2026, 6, 1), meters=METERS, out_dir=self.path,
                      fetcher=lambda *_: ({('강동', 1): 30}, {'강동': 30}))
        self.assertEqual(len(self.rows(path)), 2)
        previous = path.read_bytes()
        self.assertIsNone(riders.scrape(date(2026, 6, 1), meters=METERS, out_dir=self.path,
                                       fetcher=lambda *_: ({}, {})))
        self.assertEqual(path.read_bytes(), previous)

    def test_bills_preserve_partial_success_and_supplementary_rows(self):
        def fetch(_session, customer, *_args, **_kwargs):
            if customer.endswith('2'):
                raise TimeoutError()
            return bill_html(), True
        with patch.object(bills, 'fetch_bill_window', side_effect=fetch):
            for _ in range(2):
                report = bills.collect_bills(start_ym='2026-06', end_ym='2026-06', mkeys=['1', '2'],
                    session=Mock(), cache_dir=self.path / 'cache', out_dir=self.path, sleep=0)
        self.assertEqual(report['status'], 'failed')
        rows = self.rows(self.path / 'bills_long.csv')
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['gubun'] for r in rows}, {'정기분', '수시분'})

    def test_supplementary_notice_numbers_survive_csv_refresh(self):
        html = '<form action="/cyber/front/mypage/NR_levySearch.do"><input type="hidden" name="searchMkey" value="000000001"></form>'
        html += bill_html().replace('<td>000000001</td><td>수시분</td>', '<td>900000001</td><td>수시분</td>')
        second = '<tr><td>3</td><td>900000002</td><td>수시분</td><td>2026-06-30</td><td>수납 완료</td><td>0</td><td>역1</td><td>0</td><td></td></tr>'
        html = html.replace('</tbody>', second + '</tbody>')
        with patch.object(bills, 'fetch_bill_window', return_value=(html, True)):
            for _ in range(2):
                report = bills.collect_bills(start_ym='2026-06', end_ym='2026-06', mkeys=['1'],
                    session=Mock(), cache_dir=self.path / 'cache', out_dir=self.path, sleep=0)
                self.assertEqual(report['errors'], [])
        rows = self.rows(self.path / 'bills_long.csv')
        self.assertEqual(len(rows), 3)
        self.assertEqual({r['mkey'] for r in rows}, {'000000001'})
        self.assertEqual({r['notice_number'] for r in rows}, {'', '900000001', '900000002'})

    def test_env_credentials_prefer_arisu_and_login_is_verified(self):
        with patch.dict('os.environ', {'ARISU_USER_ID': 'new', 'ARISU_USER_PWD': 'pwd',
                                      'I121_USER_ID': 'old', 'I121_USER_PWD': 'oldpwd'}, clear=True):
            with patch.object(auth, 'login', return_value='session') as login:
                self.assertEqual(auth.session_from_env(self.path / 'missing.env'), 'session')
                login.assert_called_once_with('new', 'pwd')
        session = Mock()
        session.get.return_value = Mock(text='<input name="userId">', url='https://x/NR_loginForm.do')
        with patch.object(auth, '_new_session', return_value=session):
            with self.assertRaises(auth.LoginError):
                auth.login('user', 'password')

    def test_validation_calibration_is_unchanged_by_future_outlier(self):
        valid = pd.DataFrame({'고객번호': ['1'] * 3, '일사용량_톤': [9., 10., 11.]})
        calibration = metric.fit_calibration(valid, np.array([10., 10., 10.]))
        earlier = valid.iloc[:1].copy()
        score = metric.score_predictions(earlier, np.array([10.]), calibration)['deviation_score'].iloc[0]
        later = pd.concat([earlier, pd.DataFrame({'고객번호': ['1'], '일사용량_톤': [999.]})], ignore_index=True)
        scored = metric.score_predictions(later, np.array([10., 10.]), calibration)
        self.assertEqual(score, scored['deviation_score'].iloc[0])
        unknown = pd.DataFrame({'고객번호': ['new'], '일사용량_톤': [10.]})
        self.assertEqual(metric.classify(metric.score_predictions(unknown, np.array([10.]), calibration), 2, 3)['심각도'].iloc[0], '자료부족')

    def test_bill_baseline_never_reads_future_bills(self):
        path = self.path / 'bills.csv'
        pd.DataFrame([{'고객번호': '000000001', '포함월수': 2, '격월사용량_톤': 608,
                       '시작연월': '2024-01', '종료연월': '2024-02'}]).to_csv(path, index=False)
        frame = pd.DataFrame({'고객번호': ['000000001'] * 2, '날짜': pd.to_datetime(['2024-02-01', '2025-02-01'])})
        result = dataset._merge_bill_baseline(frame, {'data': {'bills': str(path)}})
        self.assertTrue(pd.isna(result['bill_daily_avg'].iloc[0]))
        self.assertAlmostEqual(result['bill_daily_avg'].iloc[1], 10.)

    def test_perfect_validation_does_not_mark_zero_error_as_alert(self):
        frame = pd.DataFrame({'고객번호': ['1'] * 3, '일사용량_톤': [10.] * 3})
        scored = metric.score_predictions(frame, np.array([10.] * 3))
        thresholds = metric.score_quantiles(scored['deviation_score'], .95, .99)
        result = metric.classify(scored, *thresholds)
        self.assertEqual(set(result['심각도']), {'정상'})

    def test_snapshot_pointer_only_changes_after_both_files_validate(self):
        master = pd.DataFrame({'고객번호': ['000000001'], '날짜': ['2026-06-01'], '일사용량_톤': [12.]})
        ride = pd.DataFrame({'고객번호': ['000000001'], '날짜': ['2026-06-01'], '총승객수': [30.]})
        manifest = publish_snapshot(master, ride, output_dir=self.path)
        before = (self.path / 'manifest.json').read_bytes()
        self.assertTrue((self.path / manifest['directory'] / 'daily.json').exists())
        with self.assertRaises(ValueError):
            publish_snapshot(master, ride, output_dir=self.path, previous_risk={'bad': [float('nan')]})
        self.assertEqual((self.path / 'manifest.json').read_bytes(), before)

    def test_first_observation_only_refresh_preserves_initial_risk(self):
        master = pd.DataFrame({'고객번호': ['000000001'], '날짜': ['2026-06-01'], '일사용량_톤': [12.]})
        riders = pd.DataFrame({'고객번호': ['000000001'], '날짜': ['2026-06-01'], '총승객수': [30.]})
        risk = {'000000001': [{'date': '2026-05-31', 'severity': '주의'}]}
        args = Namespace(runtime_dir=self.path, start=date(2026, 6, 1), end=date(2026, 6, 1),
                         water=True, ridership=False, bills=False, model=False, train_end=None, valid_end=None, jobs=1)
        with patch('back.api.catalog.collector_meters', return_value=METERS), \
             patch('back.api.catalog.data_sources', return_value=({}, risk)), \
             patch.object(water, 'scrape_range', return_value=[]), \
             patch.object(refresh, 'build_dataset', return_value=(master, riders, [], set())), \
             patch.object(refresh, 'build_calendar'):
            self.assertEqual(refresh.run(args), 0)
        manifest = json.loads((self.path / 'snapshot/manifest.json').read_text())
        self.assertEqual(manifest['risk_as_of'], '2026-05-31')
        self.assertEqual(json.loads((self.path / 'snapshot' / manifest['directory'] / 'risk.json').read_text()), risk)

    def test_dataset_joins_customer_numbers_and_withholds_new_contract(self):
        processed = self.path / 'processed'
        processed.mkdir()
        (self.path / 'billing').mkdir()
        dates = pd.date_range('2025-01-01', periods=110).strftime('%Y-%m-%d')
        water = [{'고객번호': '1', '검침일': day, '일사용량_톤': 10} for day in dates]
        water[-1]['일사용량_톤'] = 3186
        water.append({'고객번호': '2', '검침일': dates[-1], '일사용량_톤': 20})
        pd.DataFrame(water).to_csv(processed / 'daily_water_usage.csv', index=False)
        pd.DataFrame([{'고객번호': '1', '사용일': dates[-1], '승차총승객수': 30, '하차총승객수': 40}]).to_csv(processed / 'ridership.csv', index=False)
        pd.DataFrame([{'고객번호': '1', '일일CSV파일명': '옛이름'}]).to_csv(self.path / 'billing/meter_match.csv', index=False)
        master, _, withheld, eligible = build_dataset(self.path / 'output', meters=METERS,
            data_root=self.path, daily_root=self.path / 'daily', train_end=dates[89], valid_end=dates[103])
        self.assertEqual(eligible, {'000000001'})
        self.assertEqual(master[master['고객번호'] == '000000001'].iloc[-1]['일사용량_톤'], 3186)
        self.assertEqual(withheld[0]['customer_number'], '000000002')
        new = master[master['고객번호'] == '000000002'].iloc[0]
        self.assertEqual(new['역명'], '길동역')
        self.assertTrue(pd.isna(new['총승객수']))


if __name__ == '__main__':
    unittest.main()
