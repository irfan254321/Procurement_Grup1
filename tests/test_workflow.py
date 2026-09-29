# PANDUAN MAHASISWA: Tes perpindahan tahapan dan penyimpanan alur lama memakai database sementara.
"""Tes transisi tahap, persistensi SQLite, dan variasi vendor."""
import json
import unittest
from dataclasses import asdict

from procurement.models import Scenario, VENDORS
from procurement.storage import create_run, events, get_report, get_run
from procurement.workflow import advance, finish, market


def memory_db():
    """Skema sama dengan aplikasi, disimpan sementara untuk tes."""
    from procurement.storage import connect
    # SQLite :memory: membuat database sementara tanpa menulis file.
    return connect(":memory:")


class WorkflowTests(unittest.TestCase):
    def test_manual_steps_and_default_report(self):
        db = memory_db()
        run_id = create_run(db, asdict(Scenario()), 42, 0)
        first = advance(db, run_id)
        self.assertEqual(first["agent"], "IRE")
        self.assertEqual(get_run(db, run_id)["step"], 1)
        finish(db, run_id)
        self.assertEqual(len(events(db, run_id)), 8)
        self.assertEqual(get_run(db, run_id)["status"], "selesai")
        initial = json.loads(events(db, run_id)[4]["data_json"])
        staged = json.loads(events(db, run_id)[6]["data_json"])["assessment"]
        decision = json.loads(events(db, run_id)[7]["data_json"])
        self.assertEqual(initial["total_cost"], 99_710_000)
        self.assertEqual(initial["cash_month_1"], -19_710_000)
        self.assertEqual(staged["total_cost"], 100_397_000)
        self.assertEqual(staged["cash_month_2"], -20_397_000)
        self.assertFalse(decision["approved"])
        report = get_report(db, run_id)
        self.assertEqual(report["status"], "PERLU REVISI")
        self.assertEqual(report["staged_cost"], 100_397_000)
        self.assertEqual(report["staged_cash_month_2"], -20_397_000)

    def test_vendor_changes_are_reproducible(self):
        first = market(VENDORS, 17, 0.2, 1)
        self.assertEqual(first, market(VENDORS, 17, 0.2, 1))
        self.assertNotEqual(first, market(VENDORS, 17, 0.2, 2))
        self.assertNotEqual(first, VENDORS)



if __name__ == "__main__":
    unittest.main()
