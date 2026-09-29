# PANDUAN MAHASISWA: Tes hasil dan batasan simulator aturan lama untuk menjaga contoh laporan.
"""Jalankan dengan python -m unittest discover -s tests -v."""
import unittest
from procurement.models import Scenario
from procurement.simulator import run


class ReportCaseTests(unittest.TestCase):
    def test_default_case_preserves_report_and_marks_infeasible(self):
        result = run(Scenario())
        self.assertEqual(result.initial.total_cost, 99_710_000)
        self.assertEqual(result.initial.cash_month_1, -19_710_000)
        self.assertFalse(result.initial.feasible)
        self.assertEqual(result.staged.cost_month_1, 69_797_000)
        self.assertEqual(result.staged.cost_month_2, 30_600_000)
        self.assertEqual(result.staged.total_cost, 100_397_000)
        self.assertEqual(result.staged.cash_month_1, 10_203_000)
        self.assertEqual(result.staged.cash_month_2, -20_397_000)
        self.assertFalse(result.staged.feasible)
        self.assertEqual(len(result.log), 6)

    def test_minimum_cash_and_capacity(self):
        result = run(Scenario(minimum_cash=60_000_000, quantity=1300))
        self.assertTrue(any("Kapasitas" in x for x in result.initial.violations))
        self.assertTrue(any("Kas bulan pertama" in x for x in result.staged.violations))


if __name__ == "__main__":
    unittest.main()
