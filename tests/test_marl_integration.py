# PANDUAN MAHASISWA: Tes lintas modul memastikan environment, checkpoint, laporan, dan tabel putaran bekerja bersama.
"""Pastikan kedua pilihan benar-benar memiliki pembaruan parameter belajar."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from procurement.rl_service import (default_vendor_rows, scenario_from_request, scenario_from_snapshot,
                                    short_report, simulate, validate_vendor_rows)
from procurement.rl_storage import (connect, load_events, load_run, load_vendor_settings,
                                    reset_vendor_settings, save_run, save_vendor_settings)
from procurement_marl.agents.ctde_ac import CTDEActorCritic
from procurement_marl.agents.iql import IQL
from procurement_marl.env import ProcurementEnv
from procurement_marl.scenario import cash_diagnosis
from procurement_marl.evaluate import run_episode
from procurement.baseline_ml import decision_features
from procurement.rl_presentation import audit_rows, competition_round_rows
from procurement_marl.vendor_agents import VendorNegotiator


class MarlIntegrationTests(unittest.TestCase):
    def test_competition_round_table_serializes_to_arrow(self):
        """Label Awal dan nomor ronde tidak boleh mencampur str/int di Streamlit."""
        import pandas as pd
        import pyarrow as pa

        scenario = scenario_from_request(700, 700, 100_000_000)
        env = ProcurementEnv(scenario)
        env.reset(seed=0)
        env.step(0)
        for step in range(1, len(env.log) + 1):
            rows = competition_round_rows(env.log, step, cycle=1, batch=0)
            if rows:
                self.assertTrue(all(isinstance(row["Putaran"], str) for row in rows))
                pa.Table.from_pandas(pd.DataFrame(rows), preserve_index=False)

    def test_minimum_cash_is_warning_when_balance_stays_positive(self):
        """Target Rp60 juta memberi peringatan, bukan menolak rencana yang likuid."""
        from procurement_marl.oracle import PlanPolicy

        scenario = scenario_from_request(300, 300, 100_000_000)
        diagnosis = cash_diagnosis(scenario)
        self.assertFalse(scenario.enforce_min_cash)
        self.assertEqual(diagnosis["available"], 80_000_000)
        self.assertFalse(diagnosis["infeasible"])
        result = run_episode(ProcurementEnv(scenario), PlanPolicy((0, ((0, 0, 1),))),
                             seed=0, options={"scenario": scenario})
        final = next(event for event in reversed(result["log"]) if event.get("event") == "cek_batasan")
        self.assertTrue(result["consensus"])
        self.assertLess(min(final["cash"]), scenario.min_cash)
        self.assertIn("kas_di_bawah_minimum", final["warnings"])

    def test_audit_export_keeps_all_four_cash_months(self):
        """Pembayaran termin bulan 3/4 harus dapat diaudit dari CSV."""
        rows = audit_rows(
            [{"round": 1, "agent": "ENV", "event": "cek_batasan", "cash": [80, 70, 60, 50],
              "total": 100, "budget_left": 0, "violations": [], "consensus": True}],
            {"policy": "IQL", "seed": 0, "model": {"model_version": 6}}, 0)
        self.assertEqual([rows[0][f"kas_bulan_{month}"] for month in range(1, 5)], [80, 70, 60, 50])

    def test_competing_vendors_quote_before_vmi_selects(self):
        """Vendor layak harus menawar lebih dulu, sehingga VMI melihat harga aktual."""
        from procurement_marl.env import ProcurementEnv
        from procurement_marl.scenario import load_scenario

        env = ProcurementEnv(load_scenario())
        env.reset(seed=0)
        env.step(1)  # IRE membagi 700 unit mendesak dan 300 unit berikutnya.
        chosen = env.batch
        self.assertEqual(env.agent_selection, "VMI")
        quoted = set(chosen["quotes"])
        self.assertGreaterEqual(len(quoted), 2)
        vmi_position = next((i for i, e in enumerate(env.log)
                             if e.get("agent") == "VMI" and e.get("action")), len(env.log))
        for vendor in quoted:
            self.assertTrue(any(e.get("event") == "vendor_counter_offer"
                                and e.get("vendor") == vendor
                                for e in env.log[:vmi_position]))
        for vendor in env.scenario.vendors:
            if vendor.name in quoted:
                expected = chosen["qty"] * (chosen["quotes"][vendor.name]["price"]
                                            + vendor.transport + vendor.risk)
                self.assertEqual(env._estimates(chosen["qty"])[vendor.name], expected)

    def test_three_inputs_preserve_vendor_fixture(self):
        sc = scenario_from_request(600, 420, 100_000_000)
        self.assertEqual((sc.quantity, sc.urgent_quantity, sc.budget), (600, 420, 100_000_000))
        self.assertEqual([(v.name, v.list_price) for v in sc.vendors],
                         [("A", 100_000), ("B", 90_000), ("C", 110_000)])
        with self.assertRaises(ValueError):
            scenario_from_request(600, 700, 100_000_000)

    def test_vendor_editor_validates_and_changes_only_new_scenario(self):
        rows = default_vendor_rows()
        rows[0]["list_price"] = 98_000
        rows[0]["initial_offer"] = 94_000
        rows[0]["floor_price"] = 92_000
        vendors = validate_vendor_rows(rows)
        custom = scenario_from_request(700, 700, 100_000_000, rows)
        default = scenario_from_request(700, 700, 100_000_000)
        self.assertEqual(vendors[0].floor_price, 92_000)
        self.assertEqual(custom.vendors[0].list_price, 98_000)
        self.assertEqual(default.vendors[0].list_price, 100_000)
        bad = default_vendor_rows()
        bad[0]["floor_price"] = 110_000
        with self.assertRaises(ValueError):
            validate_vendor_rows(bad)

    def test_vendor_settings_round_trip(self):
        db = connect(":memory:")
        rows = default_vendor_rows()
        rows[1]["capacity"] = 1_500
        save_vendor_settings(db, rows)
        self.assertEqual(load_vendor_settings(db)[1]["capacity"], 1_500)
        reset_vendor_settings(db)
        self.assertIsNone(load_vendor_settings(db))
        db.close()

    def test_vmi_screening_is_logged_vendor_by_vendor(self):
        env = ProcurementEnv(scenario_from_request(700, 700, 100_000_000))
        env.reset(seed=1)
        env.step(0)
        checks = [e for e in env.log if e.get("event") in {"vendor_check_start", "vendor_screening"}]
        self.assertEqual([(e["vendor"], e["event"]) for e in checks],
                         [(v, event) for v in ("A", "B", "C")
                          for event in ("vendor_check_start", "vendor_screening")])
        c_result = checks[-1]
        self.assertFalse(c_result["passed"])
        self.assertEqual(set(c_result["failed_checks"]), {"score", "capacity"})

    def test_vendor_negotiates_in_rounds_without_crossing_floor(self):
        scenario = scenario_from_request(600, 420, 100_000_000)
        vendor = scenario.vendor("B")
        price, accepted, transcript = VendorNegotiator(scenario).negotiate_price(
            vendor, 600, relation=0.6, competitors=2, urgent_share=0.7)
        self.assertGreaterEqual(len(transcript), 2)
        self.assertTrue(accepted)
        self.assertGreaterEqual(price, vendor.floor_price)
        self.assertLess(price, vendor.initial_offer)
        self.assertEqual([row["negotiation_round"] for row in transcript], [1, 2])
        fixed = scenario.vendor("A")
        fixed_price, fixed_accepted, _ = VendorNegotiator(scenario).negotiate_price(
            replace(fixed, floor_price=fixed.initial_offer), 300, 0.6, 1, 0.5)
        self.assertTrue(fixed_accepted)
        self.assertEqual(fixed_price, fixed.initial_offer)

    def test_snapshot_and_trained_policies_keep_report_infeasible(self):
        for policy in ("IQL", "CTDE"):
            snapshot, result, report = simulate(policy, 1000, 700, 100_000_000, seed=0)
            restored = scenario_from_snapshot(snapshot)
            self.assertEqual(restored.vendors[1].list_price, 90_000)
            self.assertFalse(result["consensus"])
            self.assertEqual(report["status"], "TIDAK FEASIBLE")
            self.assertEqual(report["seed"], 0)
            self.assertTrue(report["model"]["checkpoint_sha256"])

    def test_slm_can_request_revision_and_env_proves_cash_shortfall(self):
        env = ProcurementEnv(scenario_from_request(1000, 700, 100_000_000))
        env.reset(seed=0)
        env.step(0)  # IRE membuat satu batch.
        env.step(1)  # VMI memilih vendor B.
        env.step(1)  # DA menawar balik.
        env.step(3)  # SLM meminta perubahan skenario.
        self.assertEqual(env.stop_reason, "infeasible_proven")
        self.assertTrue(all(env.terminations.values()))
        self.assertEqual(env.log[-1]["event"], "diagnosis")
        self.assertGreater(env.log[-1]["shortfall"], 0)

    def test_identical_material_plan_stops_as_no_progress(self):
        class FixedPlan:
            def act(self, env, agent):
                # Pilih aksi valid pertama, kecuali VMI memilih B bila tersedia.
                mask = env.observe(agent)["action_mask"]
                if agent == "VMI" and mask[1]:
                    return 1
                return int(next(i for i, allowed in enumerate(mask) if allowed))

        base = scenario_from_request(1000, 700, 90_000_000)
        scenario = replace(base, initial_cash=300_000_000, other_needs=(0, 0, 0, 0))
        result = run_episode(ProcurementEnv(scenario), FixedPlan(), seed=0)
        self.assertEqual(result["stop_reason"], "no_progress")
        self.assertEqual(result["rounds"], 2)
        self.assertEqual(result["outcome"], "PERLU REVISI")

    def test_iql_updates_a_q_table(self):
        agent = IQL(epsilon=1.0, seed=5)
        agent.train_episode(ProcurementEnv(scenario_from_request(1000, 700, 100_000_000)), seed=5)
        self.assertTrue(any(abs(value).sum() > 0 for table in agent.q.values() for value in table.values()))

    def test_ctde_uses_shared_replay_and_gradient(self):
        agent = CTDEActorCritic(seed=7, greedy=False, critic_batch=16)
        env = ProcurementEnv(scenario_from_request(1000, 700, 100_000_000))
        episode, _ = agent.collect_episode(env, seed=7)
        before = next(agent.actors.parameters()).detach().clone()
        info = agent.update([episode])
        self.assertGreater(info["replay_size"], 0)
        self.assertFalse((before == next(agent.actors.parameters()).detach()).all())

    def test_report_and_log_saved_atomically(self):
        db = connect(":memory:")
        sc = scenario_from_request(1000, 700, 100_000_000)
        diagnosis = cash_diagnosis(sc)
        self.assertTrue(diagnosis["infeasible"])
        result = {"consensus": False, "total": 99_710_000, "rounds": 1,
                  "violations": ["kas_negatif"], "stop_reason": "cycle_limit",
                  "outcome": "PERLU REVISI",
                  "log": [{"round": 1, "agent": "ENV", "event": "cek_batasan",
                           "cash": [-19_710_000], "total": 99_710_000}]}
        report = short_report(result, sc, "IQL", seed=0)
        run_id = save_run(db, "IQL", 0, {"quantity": 1000, "urgent": 700,
                                          "budget": 100_000_000}, result, report)
        self.assertEqual(load_run(db, run_id)["status"], "PERLU REVISI")
        self.assertEqual(load_events(db, run_id)[0]["agent"], "ENV")
        db.close()

    def test_baseline_features_are_separate_from_marl_action(self):
        # Jumlah kecil menyisakan cadangan kas wajib sehingga model membuat
        # rencana lengkap yang dapat dinilai baseline supervised learning.
        snapshot, result, report = simulate("IQL", 150, 150, 100_000_000, seed=1)
        scenario = scenario_from_snapshot(snapshot)
        features = decision_features(scenario, result)
        self.assertIsNotNone(features)
        self.assertEqual(set(features), set(__import__("procurement.baseline_ml", fromlist=["FEATURE_COLUMNS"]).FEATURE_COLUMNS))
        self.assertGreater(features["plan_total_per_unit"], 0)
        self.assertIn("baseline_ml", report)


if __name__ == "__main__":
    unittest.main()
