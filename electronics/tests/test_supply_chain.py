"""Capacity, route, allocation, and split-invoice business invariants."""
import json
from contextlib import closing
from math import isinf
from pathlib import Path
import sqlite3
import sys
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finance import vat
import supply_chain


def route(name="Reguler", *, days=2, risk=0, fixed=0, unit=0):
    return {"name": name, "path": ["Vendor", "Hub", "Gudang BIZ"],
            "distance": 10, "mode": "Truck", "lead_days": days,
            "late_probability": risk, "fixed_freight": fixed,
            "unit_freight": unit}


def offer(name, price, capacity, routes=None, *, accepted=True):
    return {"vendor": name, "price": price, "capacity": capacity,
            "routes": routes or [route()], "accepted": accepted}


class AllocationTests(unittest.TestCase):
    def assert_quantity(self, plan, requested):
        self.assertIsNotNone(plan)
        self.assertEqual(sum(line["quantity"] for line in plan), requested)
        for line in plan:
            self.assertGreater(line["quantity"], 0)
            self.assertAlmostEqual(line["cost"], line["goods_cost"] + line["freight"], places=4)
            self.assertAlmostEqual(line["invoice"], line["cost"] + vat(line["cost"]), places=4)

    def test_split_fills_exact_demand_without_exceeding_supplier_capacity(self):
        plan = supply_chain.allocate_orders(
            [offer("A", 10, 3), offer("B", 12, 4)], 6, 100, 3)
        self.assert_quantity(plan, 6)
        quantities = {line["vendor"]: line["quantity"] for line in plan}
        self.assertEqual(quantities, {"A": 3, "B": 3})
        self.assertAlmostEqual(sum(line["invoice"] for line in plan), 73.26, places=4)

    def test_insufficient_capacity_is_not_reported_as_completed_plan(self):
        self.assertIsNone(supply_chain.allocate_orders(
            [offer("A", 10, 2), offer("B", 11, 2)], 5, 100, 3))

    def test_alternate_routes_cannot_double_the_same_supplier_capacity(self):
        routes = [route("Reguler"), route("Ekspres", days=1, fixed=2)]
        self.assertIsNone(supply_chain.allocate_orders(
            [offer("A", 10, 2, routes)], 3, 100, 3))

    def test_optimizer_uses_carrier_capacity_deadline_and_freight(self):
        routes = [
            dict(route(days=2, fixed=1), carrier="Pos Logistik Indonesia", capacity=8),
            dict(route(days=1, fixed=4), carrier="J&T Cargo", capacity=12),
            dict(route(days=1, fixed=2), carrier="JNE", capacity=4),
        ]
        offers = [offer("A", 10, 12, routes)]
        for quantity, deadline, carrier in (
            (4, 2, "Pos Logistik Indonesia"),
            (4, 1, "JNE"),
            (10, 2, "J&T Cargo"),
        ):
            with self.subTest(quantity=quantity, deadline=deadline):
                plan = supply_chain.allocate_orders(offers, quantity, 200, deadline)
                self.assert_quantity(plan, quantity)
                self.assertEqual(plan[0]["route"]["carrier"], carrier)

    def test_deadline_excludes_cheaper_slow_shipments(self):
        plan = supply_chain.allocate_orders(
            [offer("A", 5, 4, [route(days=7)]), offer("B", 10, 4)],
            4, 100, 3)
        self.assert_quantity(plan, 4)
        self.assertEqual([line["vendor"] for line in plan], ["B"])
        self.assertIsNone(supply_chain.allocate_orders(
            [offer("A", 5, 4, [route(days=7)])], 4, 100, 3))

    def test_optimizer_accounts_for_fixed_freight_not_only_unit_price(self):
        plan = supply_chain.allocate_orders(
            [offer("A", 10, 3, [route(fixed=10)]), offer("B", 11, 5)],
            4, 100, 3)
        self.assert_quantity(plan, 4)
        self.assertEqual([line["vendor"] for line in plan], ["B"])
        self.assertAlmostEqual(plan[0]["invoice"], 48.84, places=4)

    def test_budget_includes_freight_and_vat_with_exact_boundary(self):
        offers = [offer("A", 10, 3, [route(fixed=2, unit=1)])]
        # 3 x 10 + 2 fixed + 3 x 1 freight = 35; VAT = 3.85.
        self.assertIsNone(supply_chain.allocate_orders(offers, 3, 38.84, 3))
        plan = supply_chain.allocate_orders(offers, 3, 38.85, 3)
        self.assert_quantity(plan, 3)
        self.assertAlmostEqual(plan[0]["freight"], 5, places=4)
        self.assertAlmostEqual(plan[0]["invoice"], 38.85, places=4)

    def test_risk_adjusted_objective_can_choose_slightly_higher_price(self):
        offers = [offer("Risky", 10, 3, [route(risk=.9)]),
                  offer("Reliable", 10.1, 3, [route(risk=.01)])]
        plan = supply_chain.allocate_orders(offers, 3, 100, 3)
        self.assertEqual([line["vendor"] for line in plan], ["Reliable"])
        cheapest = supply_chain.allocate_orders(offers, 3, 100, 3, risk_weight=0)
        self.assertEqual([line["vendor"] for line in cheapest], ["Risky"])

    def test_unaccepted_offer_is_never_allocated(self):
        plan = supply_chain.allocate_orders(
            [offer("Rejected", 1, 4, accepted=False), offer("Accepted", 10, 4)],
            4, 100, 3)
        self.assertEqual([line["vendor"] for line in plan], ["Accepted"])


class InventoryAndRoutingTests(unittest.TestCase):
    def catalog(self):
        return [{"name": "Laptop", "vendors": [{"name": "A"}, {"name": "B"}]}]

    def initialized_world(self):
        world = {"tick": 0, "opening": "supply"}
        with patch.object(supply_chain, "supplier_profiles", return_value=[{"source_vendor": "Historical vendor"}]):
            supply_chain.init_supply(world, self.catalog())
        return world

    def test_saved_inventory_is_not_reinitialized_and_replenishment_is_bounded(self):
        world = self.initialized_world()
        supplier = world["suppliers"]["A"]
        supplier["stock"]["Laptop"] = 1
        supplier["capacity_remaining"] = 0
        supply_chain.init_supply(world, self.catalog())
        self.assertEqual(supplier["stock"]["Laptop"], 1)
        world["tick"] = 23
        supply_chain.refresh_supply(world)
        self.assertEqual(supplier["capacity_remaining"], 0)
        world["tick"] = 24
        supply_chain.refresh_supply(world)
        self.assertEqual(supplier["capacity_remaining"], supplier["capacity"])
        self.assertEqual(supplier["stock"]["Laptop"], 1 + supplier["capacity"])
        supplier["stock"]["Laptop"] = supplier["capacity"] * 4
        world["tick"] = 48
        supply_chain.refresh_supply(world)
        self.assertEqual(supplier["stock"]["Laptop"], supplier["capacity"] * 4)

    def test_shortest_path_checks_intermediate_edges_and_unreachable_destination(self):
        graph = {"A": [("B", 9), ("C", 2)], "C": [("B", 2), ("D", 20)], "B": [("D", 3)]}
        self.assertEqual(supply_chain.shortest_path(graph, "A", "D"), (["A", "C", "B", "D"], 7))
        path, distance = supply_chain.shortest_path(graph, "D", "A")
        self.assertEqual(path, [])
        self.assertTrue(isinf(distance))

    def test_model_days_conversion_is_explicit_and_preserves_historical_prediction(self):
        world = self.initialized_world()
        model = types.SimpleNamespace(predict_supply=Mock(return_value={
            "predicted_days": 110, "late_probability": .25}))
        with patch.dict(sys.modules, {"supplier_data": model}):
            routes = supply_chain.quote_routes(world, "A", 8, 100)
        self.assertEqual({call.kwargs["mode"] for call in model.predict_supply.call_args_list}, {"Truck", "Air"})
        self.assertEqual(model.predict_supply.call_count, 2)
        self.assertEqual([r["lead_days"] for r in routes], [3, 3, 4, 3, 4, 3])
        self.assertTrue(all(r["source_prediction_days"] == 110 for r in routes))
        self.assertTrue(all(r["domain_transfer"] for r in routes))
        self.assertEqual(world["suppliers"]["A"]["late_probability"], .25)

    def test_tariff_catalog_and_route_quote_agree_for_each_carrier(self):
        world = self.initialized_world()
        model = types.SimpleNamespace(predict_supply=Mock(return_value={
            "predicted_days": 110, "late_probability": .25}))
        services = supply_chain.supplier_freight_catalog(self.catalog())["A"]["services"]
        with patch.dict(sys.modules, {"supplier_data": model}):
            routes = supply_chain.quote_routes(world, "A", 5, 123.45)
        self.assertEqual({route["carrier"] for route in routes}, set(supply_chain.CARRIERS))
        for service, route in zip(services, routes, strict=True):
            self.assertEqual(route["path"], service["path"])
            self.assertEqual(route["path"][-2], route["carrier"])
            self.assertEqual(route["capacity"], supply_chain.CARRIERS[route["carrier"]]["capacity"])
            self.assertEqual(route["fixed_freight"], round(123.45 * service["fixed_rate"], 4))
            self.assertEqual(route["unit_freight"], round(123.45 * service["unit_rate"], 4))


class SplitPurchaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import agent
        cls.server = agent

    def persisted(self, world):
        """Use the production loader, so case/order aliases must survive JSON."""
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE TABLE world (id INTEGER PRIMARY KEY, state TEXT)")
            db.execute("INSERT INTO world VALUES (1,?)", (json.dumps(world),))
            return self.server.load_world(db)

    def test_thirty_unit_supply_shock_resumes_and_pays_each_invoice_once(self):
        server = self.server
        with patch.object(server, "predict", return_value=True):
            world = server.new_world("supply")
            quote = None
            reservation = None
            paid_ids = set()
            for _ in range(500):
                world = self.persisted(world)
                cash_before, fund_before = world["cash"], world["fund"]
                reserved_before = world["reserved"]
                vat_before = world["tax"]["input_vat"]
                server.step(world, world["mode"])
                event = world["history"][0] if world["history"] else {}
                self.assertGreaterEqual(world["reserved"], -.00005)
                for supplier in world["suppliers"].values():
                    self.assertGreaterEqual(supplier["capacity_remaining"], 0)
                    self.assertTrue(all(stock >= 0 for stock in supplier["stock"].values()))
                if event.get("tick") != world["tick"]:
                    continue
                if event.get("carrier_quote") and quote is None:
                    quote = event["carrier_quote"]
                    self.assertIsNone(reservation)
                    self.assertEqual(world["phase"], "finance")
                    self.assertEqual(quote["quantity"], 30)
                    self.assertEqual((world["cash"], world["fund"], world["reserved"]),
                                     (cash_before, fund_before, reserved_before))
                    planned = {order["vendor"]: order for order in world["case"]["orders"]}
                    for lot in quote["orders"]:
                        self.assertEqual(len(lot["options"]), 6)
                        self.assertEqual({route["carrier"] for route in lot["options"]}, set(supply_chain.CARRIERS))
                        self.assertEqual(lot["quantity"], planned[lot["vendor"]]["quantity"])
                        winner, = [route for route in lot["options"] if route["selected"]]
                        self.assertTrue(winner["eligible"])
                        self.assertEqual(winner["carrier"], planned[lot["vendor"]]["route"]["carrier"])
                        self.assertEqual(winner["invoice"], planned[lot["vendor"]]["invoice"])
                if event["title"] == "Pembelian disetujui" and reservation is None:
                    self.assertIsNotNone(quote, "Carrier quotes must be recorded before approval.")
                    orders = world["last_purchase"]["orders"]
                    self.assertGreaterEqual(len(orders), 3)
                    self.assertEqual(sum(order["quantity"] for order in orders), 30)
                    self.assertEqual(len({order["id"] for order in orders}), len(orders))
                    total = sum(order["invoice"] for order in orders)
                    self.assertAlmostEqual(world["reserved"], total, places=4)
                    self.assertAlmostEqual(world["fund"], fund_before - total, places=4)
                    self.assertAlmostEqual(world["cash"], cash_before, places=4)
                    reservation = (cash_before, fund_before)
                if event.get("inspection", {}).get("state") == "paid":
                    orders = world["last_purchase"]["orders"]
                    newly_paid = [order for order in orders
                                  if order["status"] == "paid" and order["id"] not in paid_ids]
                    self.assertEqual(len(newly_paid), 1)
                    order = newly_paid[0]
                    self.assertEqual(event["inspection"]["carrier"], order["route"]["carrier"])
                    self.assertIn(order["route"]["carrier"], supply_chain.CARRIERS)
                    self.assertLessEqual(order["quantity"], order["route"]["capacity"])
                    self.assertLessEqual(order["arrival_day"], order["deadline_day"])
                    paid_ids.add(order["id"])
                    original = order.get("invoice_original", order["invoice"])
                    self.assertAlmostEqual(cash_before - world["cash"], order["invoice"], places=4)
                    self.assertAlmostEqual(reserved_before - world["reserved"], original, places=4)
                    self.assertAlmostEqual(world["fund"] - fund_before, original - order["invoice"], places=4)
                    self.assertAlmostEqual(world["tax"]["input_vat"] - vat_before, order["vat"], places=4)
                    if len(paid_ids) == len(orders):
                        break
            self.assertIsNotNone(reservation, "Supply shock never reserved its split purchase.")
            purchase = world["last_purchase"]
            orders = purchase["orders"]
            self.assertEqual(len(paid_ids), len(orders), "Split purchase did not settle every invoice.")
            self.assertAlmostEqual(world["reserved"], 0, places=4)
            self.assertAlmostEqual(world["cash"], reservation[0] - sum(o["invoice"] for o in orders), places=4)
            self.assertAlmostEqual(world["fund"], reservation[1] - sum(o["invoice"] for o in orders), places=4)
            self.assertEqual(sum(o["received_quantity"] + o["damaged_quantity"] for o in orders), 30)
            for field in ("quantity", "received_quantity", "damaged_quantity", "cost", "freight", "vat", "invoice"):
                self.assertAlmostEqual(purchase[field], sum(o[field] for o in orders), places=4)
            balances = (world["cash"], world["fund"], world["reserved"], world["tax"]["input_vat"])
            world = self.persisted(world)
            server.step(world, world["mode"])
            self.assertEqual((world["cash"], world["fund"], world["reserved"], world["tax"]["input_vat"]), balances)

    def test_positive_finance_prediction_cannot_spend_insufficient_budget(self):
        server = self.server
        with patch.object(server, "predict", return_value=True):
            world = server.new_world("healthy")
            world.update(phase="procurement", case={"product": "Laptop", "quantity": 0,
                                                    "restock": 10, "buy": False})
            for _ in range(150):
                if world["phase"] == "finance":
                    break
                server.step(world, world["mode"])
            self.assertEqual(world["phase"], "finance")
            world["fund"] = 0
            cash = world["cash"]
            server.step(world, world["mode"])
            self.assertEqual(world["history"][0]["title"], "Pembelian ditahan")
            self.assertEqual(world["cash"], cash)
            self.assertEqual(world["fund"], 0)
            self.assertEqual(world["reserved"], 0)


if __name__ == "__main__":
    unittest.main()
