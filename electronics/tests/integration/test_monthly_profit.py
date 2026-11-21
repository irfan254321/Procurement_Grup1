import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import agent
from database import storage
from finance import SCALE

FINANCE = "/api/companies/biz/finance"


class MonthlyProfitTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.object(agent, "DB", Path(folder) / "district.sqlite3"))
        agent.initialize()

    def request(self, path, payload=None, *, token=None, method=None):
        handler = object.__new__(agent.Handler)
        handler.path = path
        results = []
        handler.send_data = lambda body, mime="application/json", status=200: results.append((status, body))
        content = json.dumps(payload).encode()
        handler.headers = {"Content-Length": str(len(content)), "Content-Type": "application/json"}
        if token:
            handler.headers["Authorization"] = "Bearer " + token
        handler.rfile = io.BytesIO(content)
        method = method or ("POST" if payload is not None or "/reset/" in path or "/step/" in path else "GET")
        getattr(handler, "do_" + method)()
        return results[0]

    def login(self, slug="biz", setup=True):
        status, access = self.request("/api/companies/" + slug + "/access",
                                      {"password": "finance-test-only", "setup": setup})
        self.assertEqual(status, 200)
        return access["token"]

    def test_expenses_reduce_cash_and_tax_is_recognized_only_once(self):
        self.request("/api/reset/healthy")
        token = self.login()
        _, opening = self.request(FINANCE, token=token)
        _, posted = self.request(FINANCE, {"action": "expense", "kind": "payroll", "amount": 200_000}, token=token)
        cost = 200_000 / SCALE
        self.assertAlmostEqual(posted["cash"], opening["cash"] - cost)
        self.assertAlmostEqual(posted["payroll"], opening["payroll"] - cost)
        self.assertEqual(posted["profit_report"]["periods"][0]["operating_profit"], -cost)
        denied, _ = self.request(FINANCE, {"action": "expense", "kind": "rent", "amount": 1_000_000_000_000}, token=token)
        self.assertEqual(denied, 400)
        self.assertEqual(self.request(FINANCE, token=token)[1]["cash"], posted["cash"])

        _, assessed = self.request(FINANCE, {"action": "assessment", "kind": "pph_badan", "amount": 50_000}, token=token)
        _, paid = self.request(FINANCE, {"action": "pay", "kind": "pph_badan"}, token=token)
        tax = 50_000 / SCALE
        self.assertEqual(assessed["cash"], posted["cash"])
        self.assertAlmostEqual(paid["cash"], posted["cash"] - tax)
        period = paid["profit_report"]["periods"][0]
        self.assertEqual(period["income_tax"], tax)
        self.assertEqual(period["net_profit"], -cost - tax)
        self.assertEqual(period["expenses"], [{"day": 0, "kind": "payroll", "amount": cost}])
        self.assertEqual(self.request(FINANCE, token=token)[1]["profit_report"], paid["profit_report"])
        cash_flow = paid["cash_flow"]["periods"][0]
        self.assertEqual(cash_flow["operating_payments"], cost)
        self.assertEqual(cash_flow["tax_payments"], tax)
        self.assertAlmostEqual(cash_flow["closing_cash"], cash_flow["opening_cash"] - cost - tax)
        balance = paid["balance_sheet"]
        self.assertAlmostEqual(balance["total_assets"], balance["total_liabilities"] + balance["equity"])
        self.assertEqual(assessed["balance_sheet"]["assessed_tax_due"], tax)
        self.assertEqual(balance["assessed_tax_due"], 0)

    def test_legacy_totals_excluded_and_sales_recorded_after_month_rollover(self):
        world = agent.new_world("healthy")
        del world["profit_report"]
        del world["cash_flow"]
        world.update(tick=99, day=29, sales=900, cogs=500)
        with agent.connect() as db, db:
            storage.save_world(db, world)

        token = self.login()
        _, first_month = self.request(FINANCE, {"action": "expense", "kind": "rent", "amount": 10_000}, token=token)
        self.assertEqual(first_month["profit_report"]["start_tick"], 99)
        self.assertEqual(first_month["profit_report"]["periods"][0]["sales"], 0)
        with patch.object(agent, "predict", return_value=True):
            _, next_month = self.request("/api/step/healthy")
            self.assertEqual(next_month["day"], 30)
            self.request("/api/step/healthy")
            self.request("/api/step/healthy")
        _, sold = self.request(FINANCE, token=token)

        first, second = sold["profit_report"]["periods"]
        self.assertEqual(first["month"], 1)
        self.assertEqual(first["operating_expenses"], 1)
        self.assertEqual(second["month"], 2)
        self.assertEqual(second["sales"], sold["last_sale"]["revenue"])
        self.assertEqual(second["cogs"], sold["last_sale"]["cost"])
        self.assertEqual(second["operating_expenses"], 0)
        self.assertEqual(sold["cash_flow"]["periods"][1]["customer_receipts"], sold["last_sale"]["total"])
        self.request("/api/reset/healthy")
        self.assertEqual(self.request(FINANCE, token=token)[0], 401)
        _, reset = self.request(FINANCE, token=self.login(setup=False))
        self.assertEqual(reset["profit_report"]["start_tick"], 0)
        self.assertEqual(len(reset["profit_report"]["periods"]), 1)
        self.assertEqual(reset["profit_report"]["periods"][0]["expenses"], [])

    def test_reports_and_writes_require_biz_session(self):
        vendor = self.login("techmart")
        self.assertEqual(self.request(FINANCE)[0], 401)
        self.assertEqual(self.request(FINANCE, token=vendor)[0], 401)
        payload = {"action": "expense", "kind": "payroll", "amount": 100_000}
        self.assertEqual(self.request(FINANCE, payload, token=vendor)[0], 401)
        self.assertEqual(self.request("/api/finance/expense", payload)[0], 404)
        self.assertEqual(self.request("/api/tax/pay", payload)[0], 404)
        for public in (self.request("/api/world")[1], self.request("/api/step/healthy")[1]):
            self.assertTrue({"profit_report", "cash", "finance_series", "cash_flow", "last_sale"}.isdisjoint(public))
            self.assertEqual(set(public["tax"]), {"rate"})
        token = self.login()
        self.assertEqual(self.request("/api/companies/biz/negotiations", token=token)[0], 200)
        self.assertEqual(self.request(FINANCE, token=token)[0], 200)
        self.request("/api/companies/biz/logout", {}, token=token)
        self.assertEqual(self.request(FINANCE, token=token)[0], 401)
