"""Checks for causal source partitioning and safe cross-domain inference."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from supplier_data import FEATURES, get_supplier_profiles, load_supplier_models, predict_supply
from supplier_training import chronological_parts, read_examples


class SupplierDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples, cls.cleaning = read_examples()
        cls.parts, cls.split = chronological_parts(cls.examples)

    def test_purchase_orders_and_future_outcomes_do_not_cross_split(self):
        groups = [{row["group"] for row in part} for part in self.parts]
        self.assertFalse(groups[0] & groups[1])
        self.assertFalse(groups[0] & groups[2])
        self.assertFalse(groups[1] & groups[2])
        for left, right in zip(self.parts, self.parts[1:]):
            self.assertLess(max(row["delivered"] for row in left), min(row["ordered"] for row in right))

    def test_features_do_not_include_outcomes_or_tracking_identifiers(self):
        forbidden = {"actual_days", "delivered", "late", "delivery_recorded_date", "id", "purchase_order", "freight_cost"}
        self.assertFalse(set(FEATURES) & forbidden)
        self.assertEqual(self.cleaning["source_rows"], 10324)
        self.assertEqual(sum(self.cleaning["excluded"].values()) + len(self.examples), 10324)
        self.assertTrue(all(len(row["x"]) == len(FEATURES) for row in self.examples))

    def test_source_models_and_metrics_are_present(self):
        bundle = load_supplier_models()
        self.assertIsNotNone(bundle)
        self.assertEqual(len(get_supplier_profiles()), 5)
        self.assertEqual(bundle["report"]["features"], list(FEATURES))
        self.assertIn(bundle["report"]["lead"]["selected_model"], {"ScheduledBaseline", "CatBoostResidual"})

    def test_prediction_preserves_source_context_and_scales_quantity(self):
        profile = get_supplier_profiles()[0]
        first = predict_supply(profile, 12)
        doubled = predict_supply(profile, 24)
        self.assertEqual(first["source_vendor"], profile["source_vendor"])
        self.assertEqual(first["source_quantity"], profile["reference_quantity"])
        self.assertEqual(doubled["source_quantity"], first["source_quantity"] * 2)
        self.assertTrue(first["domain_transfer"])
        self.assertFalse(first["probability_calibrated"])
        self.assertTrue(0 <= first["late_risk_score"] <= 1)
        self.assertTrue(math.isfinite(first["predicted_days"]))

    def test_eta_uses_validation_selected_schedule_baseline(self):
        profile = get_supplier_profiles()[0]
        prediction = predict_supply(profile, 12)
        if prediction["eta_model"] == "ScheduledBaseline":
            self.assertEqual(prediction["predicted_days"], profile["scheduled_days"])
        report = load_supplier_models()["report"]
        self.assertLessEqual(report["lead"]["validation"]["mae_days"], report["lead"]["validation"]["baseline_scheduled_mae_days"] + 1e-5)

    def test_invalid_quantity_and_modes_are_rejected(self):
        profile = get_supplier_profiles()[0]
        for quantity in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                predict_supply(profile, quantity)
        with self.assertRaises(ValueError):
            predict_supply(profile, 12, mode="untracked rocket")


if __name__ == "__main__":
    unittest.main()
