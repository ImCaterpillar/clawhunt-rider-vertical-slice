# -*- coding: utf-8 -*-
import unittest
from dashboard import pii_fuzz_scan, seed_events, sql_metrics, verify_dashboard

class DashboardTests(unittest.TestCase):
    def test_seed_is_deterministic(self):
        self.assertEqual(seed_events(50,9),seed_events(50,9))
        self.assertNotEqual(seed_events(50,9),seed_events(50,10))

    def test_independent_sql_matches_python_on_12000_events(self):
        result=verify_dashboard()
        self.assertEqual(result['events'],12000)
        self.assertTrue(result['metrics_equal'],result['mismatches'])
        self.assertTrue(result['pii_scan']['passed'])

    def test_pii_dimensions_and_filters_rejected(self):
        import sqlite3
        from dashboard import build_metric_views
        db=sqlite3.connect(':memory:');build_metric_views(db,seed_events(2))
        for key in ('phone','name','email'):
            with self.assertRaisesRegex(ValueError,'FILTER_NOT_ALLOWED'):sql_metrics(db,{key:'x'})

    def test_empty_dataset_metrics_are_zero(self):
        self.assertEqual(verify_dashboard(n=0)['sql'],{'total':0,'complete':0,'booked':0,'completion_rate':0.0})

if __name__=='__main__':unittest.main(verbosity=2)
