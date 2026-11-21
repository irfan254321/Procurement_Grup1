from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.analytics import forecast_demand, observe_delivery, observe_demand, vendor_scorecard


class AnalyticsTests(unittest.TestCase):
    def test_ewma_dynamic_reorder_uses_daily_observations(self):
        product = {"name":"Laptop"}
        self.assertEqual(forecast_demand(product,1)["dynamic_rop"],3)
        observe_demand(product,1,2)
        observe_demand(product,2,8)
        observe_demand(product,2,2)
        forecast = forecast_demand(product,2,2)
        self.assertEqual(forecast["daily_ewma"],4.4)
        self.assertEqual(forecast["forecast_3_days"],13.2)
        self.assertGreater(forecast["safety_stock"],0)
        self.assertGreater(forecast["dynamic_rop"],3)
        self.assertLess(forecast_demand(product,10)["daily_ewma"],4.4)

    def test_bayesian_scorecard_and_grade_use_actual_outcomes(self):
        supplier = {}
        self.assertIsNone(vendor_scorecard(supplier)["otd"])
        observe_delivery(supplier,10,0,2,2)
        self.assertLess(vendor_scorecard(supplier)["posterior_risk"],.1)
        observe_delivery(supplier,10,3,6,5)
        score = vendor_scorecard(supplier)
        self.assertEqual(score["otd"],.5)
        self.assertEqual(score["defect_rate"],.15)
        self.assertEqual(score["grade"],"C")
        self.assertAlmostEqual(score["posterior_risk"],2/12,places=6)
