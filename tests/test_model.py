"""Model inputs retain unknown values and do not hide genuine usage spikes."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from back.ml.lightgbm import metric
from back.scripts.dataset_etl.build_clean_dataset import build_bills_bimonthly


class ModelDataTest(unittest.TestCase):
    def test_large_valid_reading_remains_an_alert_not_a_data_error(self):
        valid = pd.DataFrame({'고객번호': ['1'] * 3, '일사용량_톤': [9., 10., 11.]})
        calibration = metric.fit_calibration(valid, np.array([10.] * 3))
        observations = pd.DataFrame({'고객번호': ['1'] * 4, '일사용량_톤': [3186., -1., np.nan, np.inf]})
        result = metric.classify(metric.score_predictions(observations, np.array([10.] * 4), calibration), 2, 3)
        self.assertEqual(result['likely_data_error'].tolist(), [False, True, True, True])
        self.assertEqual(result.iloc[0]['심각도'], '경고')

    def test_bill_baseline_preserves_missing_usage_and_counts_distinct_months(self):
        labels = pd.DataFrame([{'고객번호': '000000001', '역명': '가역'}])
        common = {'고객번호': '000000001', '역명': '가역', '영업사업소': '동부', '용도': '직원', '부과금액_원': 100}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bills.csv'
            rows = [common | {'납기일': '2026-01-15', '총사용량_톤': 10},
                    common | {'납기일': '2026-01-31', '총사용량_톤': None}]
            pd.DataFrame(rows).to_csv(path, index=False)
            result = build_bills_bimonthly(path, labels)
            self.assertEqual(result.iloc[0]['포함월수'], 1)
            self.assertTrue(pd.isna(result.iloc[0]['격월사용량_톤']))
            self.assertEqual(result.iloc[0]['격월부과금액_원'], 200)
            rows.append(common | {'납기일': '2026-02-28', '총사용량_톤': 0})
            pd.DataFrame(rows).to_csv(path, index=False)
            result = build_bills_bimonthly(path, labels)
            self.assertEqual(result.iloc[0]['포함월수'], 2)
            self.assertTrue(pd.isna(result.iloc[0]['격월사용량_톤']))
            pd.DataFrame(rows).iloc[:0].to_csv(path, index=False)
            self.assertTrue(build_bills_bimonthly(path, labels).empty)


if __name__ == '__main__':
    unittest.main()
