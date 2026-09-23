"""One-contract refresh checks using temporary storage and mocked remote responses."""
import json
import os
import sqlite3
import tempfile
import time
import unittest
import csv
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from back.api import catalog, config, db
from back.pipelines import incremental as inc
from back.pipelines.daily_water import scraper as water
from back.pipelines.refresh import publish_data
from back.pipelines import refresh
from back.scripts.billing_etl.i121_crawler.auth import ConfigurationError, LoginError


class IncrementalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = patch.multiple(config, ROOT=self.root, DATA_DIR=self.root / 'runtime',
                                     APP_DB_PATH=self.root / 'app.sqlite3')
        self.config.start()
        self.clock = patch.object(inc, 'today', return_value=date(2026, 6, 3))
        self.clock.start()
        db.init_db()
        with db.connect() as conn:
            conn.execute("INSERT INTO offices(id,name) VALUES('office','사업소')")
            conn.execute("INSERT INTO stations(id,name) VALUES('station','가역')")
            conn.execute("""INSERT INTO meters(id,provider,customer_number,station_id,office_id,display_name,created_at,updated_at)
                            VALUES('meter','arisu','000000001','station','office','가역','now','now')""")
            conn.execute('UPDATE meters SET daily_enabled=1')
            self.meter = catalog.list_meters(conn)[0]
        self.session = patch.object(inc, 'collection_session', return_value=Mock())
        self.session.start()

    def tearDown(self):
        self.session.stop()
        self.clock.stop()
        self.config.stop()
        self.tmp.cleanup()

    def row(self, day='2026-06-01', value=10):
        return {'고객번호': '000000001', '역명': '가역', '사용일': day, '일사용량(톤)': value}

    def bill(self):
        return {'mkey': '000000001', 'napgi': '2026-06-30', 'napgi_compact': '20260630',
                'gubun': '정기분', 'total_usage_ton': 12, 'bugwa_amount_won': 500, 'address': '서울 가역'}

    def test_new_daily_enabled_meter_is_probed_published_and_repeated_safely(self):
        messages = []
        with patch.object(inc, 'fetch_month', side_effect=lambda _s, _m, month, **_: [self.row()] if month == '2026-06' else []) as fetch:
            with patch.object(inc, 'collect_bills', return_value={'rows': [self.bill()], 'errors': []}):
                first = inc.collect_meter(self.meter, progress=messages.append)
                self.assertEqual(fetch.call_count, 12)
                second = inc.collect_meter(self.meter)
        self.assertEqual(first['status'], 'success')
        self.assertTrue(first['connection_verified'])
        self.assertTrue(second['daily_available'])
        self.assertTrue(messages)
        daily, _ = catalog.data_sources()
        self.assertEqual(daily['000000001']['usage'], [{'date': '2026-06-01', 'value': 10.0}])
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM bills').fetchone()[0], 1)
            row = conn.execute('SELECT daily_enabled,address FROM meters').fetchone()
            self.assertEqual(tuple(row), (1, '서울 가역'))

    def test_empty_refresh_preserves_existing_data_and_does_not_claim_invalid_customer(self):
        with patch.object(inc, 'fetch_month', return_value=[self.row()]), patch.object(inc, 'collect_bills', return_value={'rows': [self.bill()], 'errors': []}):
            inc.collect_meter(self.meter)
        manifest = config.DATA_DIR / 'snapshot/manifest.json'
        before = manifest.read_bytes()
        with patch.object(inc, 'fetch_month', return_value=[]), patch.object(inc, 'collect_bills', return_value={'rows': [], 'errors': []}):
            result = inc.collect_meter(self.meter)
        self.assertEqual(result['status'], 'empty')
        self.assertFalse(result['connection_verified'])
        self.assertTrue(result['daily_available'])
        self.assertIn('단정할 수 없습니다', result['message'])
        self.assertEqual(manifest.read_bytes(), before)
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM bills').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT daily_enabled FROM meters').fetchone()[0], 1)

    def test_partial_success_survives_other_month_and_bill_failure(self):
        def fetch(_session, _meter, month, **kwargs):
            if month == '2026-06':
                raise TimeoutError()
            return [self.row('2026-05-31')] if month == '2026-05' else []
        with patch.object(inc, 'fetch_month', side_effect=fetch), patch.object(inc, 'collect_bills', side_effect=TimeoutError()):
            result = inc.collect_meter(self.meter)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['daily_rows'], 1)
        self.assertTrue(result['connection_verified'])
        self.assertEqual(catalog.data_sources()[0]['000000001']['usage'][0]['date'], '2026-05-31')

    def test_configuration_and_login_failures_are_distinct(self):
        for error, status, message in [(ConfigurationError(), 'configuration_required', '설정'),
                                       (LoginError(), 'failed', '로그인')]:
            with patch.object(inc, 'collection_session', side_effect=error):
                result = inc.collect_meter(self.meter)
            self.assertEqual(result['status'], status)
            self.assertIn(message, result['message'])
            self.assertFalse(result['connection_verified'])

    def test_failed_bill_window_is_retried_even_when_existing_months_are_present(self):
        with patch.object(inc, 'fetch_month', return_value=[]), patch.object(inc, 'collect_bills',
                return_value={'rows': [self.bill()], 'errors': [{'start': '2025-07', 'error': 'ValueError'}]}):
            result = inc.collect_meter(self.meter)
        self.assertEqual(result['status'], 'partial')
        with patch.object(inc, 'fetch_month', return_value=[]), patch.object(inc, 'collect_bills',
                return_value={'rows': [self.bill()], 'errors': []}) as collect:
            inc.collect_meter(self.meter)
        self.assertEqual(collect.call_args.kwargs['start_ym'], '2025-07')
        state = json.loads((config.DATA_DIR / 'collection/000000001.json').read_text())
        self.assertIsNone(state['bill_retry_from'])

    def test_batch_session_is_reused_and_owned_by_caller(self):
        session = Mock()
        with patch.object(inc, 'collection_session', side_effect=AssertionError('must reuse session')):
            with patch.object(inc, 'fetch_month', return_value=[]), patch.object(inc, 'collect_bills', return_value={'rows': [], 'errors': []}):
                result = inc.collect_meter(self.meter, session=session)
        self.assertEqual(result['status'], 'empty')
        session.close.assert_not_called()

    def test_unregistered_billing_only_customer_skips_daily_and_collects_bills(self):
        session = Mock(arisu_customer_numbers=frozenset({'000000002'}))
        meter = self.meter | {'daily_enabled': False, 'metadata': {'arisu_customer_name': '가역'}}
        with patch.object(inc, 'fetch_month') as water, patch.object(inc, 'collect_bills', return_value={'rows': [self.bill()], 'errors': []}) as bills:
            result = inc.collect_meter(meter, session=session)
        self.assertEqual(result['status'], 'success')
        self.assertIn('청구 전용', result['message'])
        self.assertTrue(result['connection_verified'])
        water.assert_not_called()
        self.assertEqual(bills.call_args.kwargs['customer_names'], {'000000001': '가역'})
        self.assertFalse((config.DATA_DIR / 'snapshot/manifest.json').exists())

    def test_unregistered_daily_customer_still_saves_public_bills(self):
        session = Mock(arisu_customer_numbers=frozenset({'000000002'}))
        with patch.object(inc, 'fetch_month') as water, patch.object(inc, 'collect_bills', return_value={'rows': [self.bill()], 'errors': []}):
            result = inc.collect_meter(self.meter, session=session)
        self.assertEqual(result['status'], 'partial')
        self.assertIn('일일 사용량', result['message'])
        self.assertEqual(result['bill_rows'], 1)
        water.assert_not_called()
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM bills').fetchone()[0], 1)

    def test_billing_gap_windows_do_not_recrawl_fifteen_stored_years(self):
        with db.connect() as conn:
            for ym in ['2010-11', '2012-01', *[f'{year}-{month:02d}' for year in range(2012, 2027) for month in range(1, 13) if f'{year}-{month:02d}' <= '2026-05']]:
                conn.execute("INSERT OR IGNORE INTO bills(id,meter_id,period,gubun,payload,source) VALUES(?, 'meter', ?, '정기분', '{}', 'test')", (ym, ym))
        self.assertEqual(inc._bill_windows('meter', '2026-09'), [('2026-06', '2026-09'), ('2010-12', '2011-12')])

    def test_monthly_bill_gap_is_found_even_with_supplementary_notice(self):
        with db.connect() as conn:
            for ym in ['2025-01', '2025-02', '2025-04', '2025-05', '2025-06']:
                conn.execute("INSERT INTO bills(id,meter_id,period,gubun,payload,source) VALUES(?, 'meter', ?, '정기분', '{}', 'test')", (ym, ym))
            conn.execute("INSERT INTO bills(id,meter_id,period,gubun,payload,source) VALUES('extra', 'meter', '2025-03', '수시분', '{}', 'test')")
        self.assertIn(('2025-03', '2025-03'), inc._bill_windows('meter', '2026-09'))
        with db.connect() as conn:
            conn.execute("DELETE FROM bills WHERE period IN ('2025-02', '2025-04', '2025-06')")
            conn.execute("INSERT INTO bills(id,meter_id,period,gubun,payload,source) VALUES('regular', 'meter', '2025-03', '정기분', '{}', 'test')")
        windows = inc._bill_windows('meter', '2026-09')
        self.assertFalse(any(start <= '2025-02' <= end or start <= '2025-04' <= end for start, end in windows))

    def test_refresh_cli_preserves_blank_and_zero_prefixed_notice_ids(self):
        path = config.DATA_DIR / 'raw/billing_i121/i121_bills/bills_long.csv'
        path.parent.mkdir(parents=True)
        rows = [self.bill() | {'notice_number': ''},
                self.bill() | {'gubun': '수시분', 'notice_number': '090000001'}]
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        # The collector's raw CSV is the boundary under test; no request or model work.
        import pandas as pd
        old = pd.DataFrame(columns=['고객번호', '납기일', '역명', '영업사업소', '용도'])
        with patch('back.scripts.billing_etl.crawl_bills.collect_bills', return_value={'errors': []}), \
             patch.object(refresh, '_read_csv', return_value=old), \
             patch('back.scripts.dataset_etl.build_clean_dataset.build_bills_bimonthly', return_value=pd.DataFrame()):
            for _ in range(2):
                refresh.refresh_bills(date(2026, 6, 1), date(2026, 6, 30), [self.meter], config.DATA_DIR)
        with db.connect() as conn:
            stored = [tuple(row) for row in conn.execute('SELECT gubun,notice_number FROM bills ORDER BY gubun')]
        self.assertEqual(stored, [('수시분', '090000001'), ('정기분', '')])

    def test_database_failure_retains_successfully_fetched_bill_window_for_retry(self):
        with patch.object(inc, 'fetch_month', return_value=[]), patch.object(inc, 'collect_bills', return_value={'rows': [self.bill()], 'errors': []}), patch.object(inc, 'upsert_bill_summaries', side_effect=sqlite3.OperationalError('locked')):
            result = inc.collect_meter(self.meter)
        self.assertEqual(result['status'], 'partial')
        state = json.loads((config.DATA_DIR / 'collection/000000001.json').read_text())
        self.assertEqual(state['bill_retry_windows'], [['2025-07', '2026-06']])

    def test_history_gaps_retry_weekly_and_recent_dates_always_retry(self):
        months = inc.water_months(['2026-01-01', '2026-06-01'], date(2026, 6, 2),
                                  {'2026-01': '2026-06-01', '2026-02': '2026-05-01'})
        self.assertNotIn('2026-01', months)
        self.assertIn('2026-02', months)
        self.assertIn('2026-06', months)
        months = inc.water_months(['2026-08-01'], date(2026, 9, 22), {'2026-08': '2026-09-22'})
        self.assertIn('2026-08', months)

    def test_nan_observation_never_publishes_or_verifies_connection(self):
        with patch.object(inc, 'fetch_month', return_value=[self.row(value=float('nan'))]), patch.object(inc, 'collect_bills', return_value={'rows': [], 'errors': []}):
            result = inc.collect_meter(self.meter)
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['connection_verified'])
        self.assertFalse((config.DATA_DIR / 'snapshot/manifest.json').exists())

    def test_invalid_source_day_does_not_discard_valid_large_reading(self):
        def fetch(_session, _meter, month, *, issues, **kwargs):
            if month != '2026-06':
                return []
            issues.append('2026-06-02')
            return [self.row(value=3186)]
        with patch.object(inc, 'fetch_month', side_effect=fetch), patch.object(inc, 'collect_bills', return_value={'rows': [], 'errors': []}):
            result = inc.collect_meter(self.meter)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['daily_rows'], 1)
        self.assertIn('2026-06-02 아리수 검침값 누락', result['message'])
        self.assertEqual(catalog.data_sources()[0]['000000001']['usage'], [{'date': '2026-06-01', 'value': 3186.0}])

    def test_remote_default_customer_is_not_accepted_for_another_customer(self):
        session = Mock()
        payload = {"result": True, "searchMkey": "000000002", "groups": []}
        session.get.return_value = Mock(url='https://i121.seoul.go.kr/cyber/front/mypage/JR_remoteMeterHistory.do',
                                       status_code=200, text=json.dumps(payload), json=Mock(return_value=payload))
        with self.assertRaises(ValueError):
            water.fetch_month(session, self.meter, '2026-06', verify_customer=True)

    def test_readding_same_customer_cannot_create_second_contract(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with db.connect() as conn:
                conn.execute("""INSERT INTO meters(id,provider,customer_number,station_id,office_id,display_name,created_at,updated_at)
                            VALUES('another','arisu','000000001','station','office','가역','now','now')""")
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM meters').fetchone()[0], 1)

    def test_snapshot_retention_keeps_recent_versions_and_unmanaged_files(self):
        root = config.DATA_DIR / 'snapshot'
        for index in range(6):
            directory = root / 'versions' / f'{index:032x}'
            directory.mkdir(parents=True)
            (directory / 'daily.json').write_text('{}')
            timestamp = time.time() - (90000 - index)
            os.utime(directory, (timestamp, timestamp))
        recent = root / 'versions' / ('f' * 32)
        recent.mkdir()
        unmanaged = root / 'versions/operator-backup'
        unmanaged.mkdir()
        manifest = publish_data({}, {}, output_dir=root)
        self.assertTrue((root / manifest['directory']).is_dir())
        self.assertTrue(recent.is_dir())
        self.assertTrue(unmanaged.is_dir())
        self.assertFalse((root / 'versions' / ('0' * 32)).exists())
        self.assertEqual(len(list((root / 'versions').iterdir())), 4)

    def test_unexpected_failure_logs_type_without_sensitive_exception_text(self):
        with patch.object(catalog, 'data_sources', side_effect=ValueError('do-not-log-secret')):
            with self.assertLogs(inc.logger, level='ERROR') as captured:
                result = inc.collect_meter(self.meter)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('ValueError', captured.output[0])
        self.assertNotIn('do-not-log-secret', captured.output[0])


if __name__ == '__main__':
    unittest.main()
