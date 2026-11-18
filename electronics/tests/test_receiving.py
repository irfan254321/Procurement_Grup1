from contextlib import closing
import json
from pathlib import Path
from random import Random
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from finance import vat


class ReceivingTests(unittest.TestCase):
    def advance_to_receipt(self, world):
        for _ in range(300):
            if world["phase"] == "receive":
                return
            server.step(world, world["mode"])
        self.fail("Simulation did not reach an incoming shipment.")

    def inspection(self, world, state):
        event = world["history"][0]["inspection"]
        self.assertEqual(event["state"], state)
        return event

    def product_for_shipment(self, world):
        return next(product for product in world["products"]
                    if product["name"] == world["case"]["product"])

    def balances(self, world):
        return (world["cash"], world["tax"]["input_vat"],
                world["reserved"], world["fund"])

    def test_damage_excludes_stock_and_holds_payment_until_invoice_is_corrected(self):
        world = server.new_world("damage")
        self.advance_to_receipt(world)
        shipment = world["case"]
        product = self.product_for_shipment(world)
        stock_before, cost_before = product["units"], product["cost"]
        ordered = shipment["restock"]
        accepted = ordered - 2
        corrected_cost = round(shipment["agreed"] * accepted, 2)
        corrected_vat = vat(corrected_cost)
        corrected_invoice = round(corrected_cost + corrected_vat, 4)
        cash, input_vat, original_invoice, fund = self.balances(world)
        self.assertEqual(original_invoice, shipment["invoice"])
        self.assertGreater(original_invoice, corrected_invoice)

        server.step(world, "damage")
        inspected = self.inspection(world, "inspected")
        self.assertEqual((inspected["ordered"], inspected["accepted"], inspected["damaged"]),
                         (ordered, accepted, 2))
        self.assertEqual((inspected["product"], inspected["vendor"]),
                         (product["name"], shipment["vendor"]))
        self.assertEqual(product["units"], stock_before + accepted)
        self.assertEqual(product["cost"], round(
            (stock_before * cost_before + corrected_cost) / product["units"], 2))
        self.assertEqual(self.balances(world), (cash, input_vat, original_invoice, fund))

        # An interrupted simulation retains the inspection and outstanding invoice.
        world = json.loads(json.dumps(world))
        server.step(world, "damage")
        self.inspection(world, "invoice_hold")
        self.assertEqual(self.balances(world), (cash, input_vat, original_invoice, fund))

        server.step(world, "damage")
        self.inspection(world, "invoice_corrected")
        self.assertEqual(self.balances(world), (cash, input_vat, original_invoice, fund))

        server.step(world, "damage")
        self.inspection(world, "paid")
        paid_balances = (round(cash - corrected_invoice, 4), round(input_vat + corrected_vat, 4),
                         0, round(fund + original_invoice - corrected_invoice, 4))
        self.assertEqual(self.balances(world), paid_balances)
        self.assertEqual(self.product_for_shipment(world)["units"], stock_before + accepted)
        purchase = world["last_purchase"]
        self.assertEqual(purchase["quantity"], ordered)
        self.assertEqual(purchase["received_quantity"], accepted)
        self.assertEqual(purchase["damaged_quantity"], 2)
        self.assertEqual(purchase["invoice_original"], original_invoice)
        self.assertEqual(purchase["cost"], corrected_cost)
        self.assertEqual(purchase["vat"], corrected_vat)
        self.assertEqual(purchase["invoice"], corrected_invoice)
        self.assertEqual(purchase["revenue"], round(purchase["retail"] * accepted, 2))

        server.step(world, "damage")
        self.assertEqual(self.balances(world), paid_balances)
        self.advance_to_receipt(world)
        server.step(world, "damage")
        self.assertEqual(self.inspection(world, "inspected")["damaged"], 0)
        server.step(world, "damage")
        self.inspection(world, "paid")

    def test_healthy_shipment_pays_original_invoice_after_inspection(self):
        world = server.new_world("healthy")
        self.advance_to_receipt(world)
        product = self.product_for_shipment(world)
        stock_before = product["units"]
        ordered = world["case"]["restock"]
        cost = world["case"]["total"]
        cash, input_vat, invoice, fund = self.balances(world)

        server.step(world, "healthy")
        inspected = self.inspection(world, "inspected")
        self.assertEqual((inspected["accepted"], inspected["damaged"]), (ordered, 0))
        self.assertEqual(product["units"], stock_before + ordered)
        self.assertEqual(self.balances(world), (cash, input_vat, invoice, fund))

        server.step(world, "healthy")
        self.inspection(world, "paid")
        self.assertEqual(self.balances(world), (round(cash - invoice, 4),
                                               round(input_vat + vat(cost), 4), 0, fund))
        self.assertEqual(product["units"], stock_before + ordered)
        self.assertEqual(world["last_purchase"]["invoice"], invoice)

    def test_automatic_cash_opening_recovers_through_sales_and_restocks(self):
        # A seeded automatic session starts with little cash and other products on the shelf.
        seed = next(seed for seed in range(100) if Random(seed).choice(server.OPENINGS) == "cash")
        world = server.new_world("auto", rng=Random(seed))
        self.assertEqual(world["opening"], "cash")
        transitions = []
        for _ in range(200):
            # A step from an old client cannot override the stored opening.
            server.step(world, "healthy")
            self.assertEqual(world["mode"], "auto")
            event = world["history"][0]
            if event["tick"] != world["tick"]:
                continue
            if event["title"] == "Pembelian ditahan" and "Laptop" in world["restock_holds"]:
                if not transitions:
                    hold = world["restock_holds"]["Laptop"]
                    self.assertGreater(hold["required"], hold["available"])
                    self.assertEqual(world["reserved"], 0)
                    held_fund = world["fund"]
                    world = json.loads(json.dumps(world))
                    transitions.append("held")
            elif event["title"] == "Penjualan berhasil" and transitions == ["held"]:
                self.assertGreater(world["last_sale"]["profit"], 0)
                self.assertGreater(world["reinvested"], 0)
                self.assertGreater(world["fund"], held_fund)
                transitions.append("sold")
            elif event["title"] == "Dana restok tersedia" and world["case"]["product"] == "Laptop":
                self.assertNotIn("Laptop", world["restock_holds"])
                transitions.append("released")
            elif event.get("inspection", {}).get("state") == "paid" and event["inspection"]["product"] == "Laptop":
                self.assertGreater(event["inspection"]["accepted"], 0)
                self.assertGreater(self.product_for_shipment(world)["units"], 0)
                transitions.append("paid")
                break
        self.assertEqual(transitions, ["held", "sold", "released", "paid"])

    def test_automatic_mode_can_start_in_all_openings(self):
        openings = {server.new_world("auto", rng=Random(seed))["opening"] for seed in range(100)}
        self.assertEqual(openings, set(server.OPENINGS))

    def test_stockout_closes_sale_and_delivery_allows_new_purchase(self):
        world = server.new_world("stock")
        laptop = world["products"][0]
        customer = {"id": 1, "product": laptop["name"], "quantity": 3, "buy": True}
        world.update(phase="seller", case=customer.copy(), customer_count=1)
        cash_before = world["cash"]

        server.step(world, "stock")
        self.assertEqual(world["customer_results"][0]["status"], "Stok kosong")
        self.assertEqual(world["cash"], cash_before)
        self.assertEqual(world["sales"], 0)
        self.assertNotIn("waiting", world)
        self.assertFalse(world["queue"])

        self.advance_to_receipt(world)
        self.assertEqual(laptop["units"], 0)
        server.step(world, "stock")
        self.inspection(world, "inspected")
        server.step(world, "stock")
        paid = self.inspection(world, "paid")
        self.assertEqual(laptop["units"], paid["accepted"])
        self.assertFalse(world["queue"])
        self.assertEqual(world["customer_results"][0]["status"], "Stok kosong")

        world["queue"].append({**customer, "id": 2, "quantity": 1})
        server.step(world, "stock")
        server.step(world, "stock")
        self.assertEqual(world["last_sale"]["customer"], 2)
        self.assertEqual(laptop["units"], paid["accepted"] - 1)
        self.assertEqual([result["status"] for result in world["customer_results"]], ["Terlayani", "Stok kosong"])

    def test_insufficient_stock_rejects_full_transaction(self):
        world = server.new_world("stock")
        laptop = world["products"][0]
        laptop["units"] = 2
        world.update(phase="seller", case={"id": 1, "product": laptop["name"], "quantity": 3, "buy": True})

        server.step(world, "stock")
        self.assertEqual(laptop["units"], 2)
        self.assertIsNone(world["last_sale"])
        self.assertEqual(world["customer_results"][0]["status"], "Stok tidak cukup")
        self.assertNotIn("waiting", world)

    def test_saved_backorders_are_closed_without_discarding_normal_queue(self):
        world = server.new_world("stock")
        order = {"product": "Laptop", "quantity": 1, "buy": True}
        world.update(waiting=[{**order, "id": 1}],
                     queue=[{**order, "id": 2, "restocked": True}, {**order, "id": 3}],
                     phase="seller", case={**order, "id": 4, "restocked": True})
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE TABLE world (id INTEGER PRIMARY KEY, state TEXT)")
            db.execute("INSERT INTO world VALUES (1,?)", (json.dumps(world),))
            saved = server.load_world(db)

        self.assertEqual([entry["id"] for entry in saved["queue"]], [3])
        self.assertEqual([result["id"] for result in saved["customer_results"]], [1, 2, 4])
        self.assertTrue(all(result["status"] == "Stok tidak cukup" for result in saved["customer_results"]))
        self.assertNotIn("waiting", saved)
        self.assertEqual(saved["phase"], "buyer")

    def test_automatic_reset_and_step_are_advertised_and_available(self):
        def request(path, method):
            handler = object.__new__(server.Handler)
            handler.path = path
            response = []
            handler.send_data = lambda body, status=200: response.append((status, body))
            getattr(handler, f"do_{method}")()
            status, body = response[0]
            self.assertEqual(status, 200)
            return body

        with TemporaryDirectory() as folder, patch.object(server, "DB", Path(folder) / "world.sqlite3"):
            server.initialize()
            self.assertIn("auto", request("/api/models", "GET")["scenarios"])
            reset = request("/api/reset/auto", "POST")
            self.assertEqual(reset["mode"], "auto")
            world = request("/api/step/auto", "POST")
            self.assertEqual(world["tick"], 1)
            self.assertEqual(world["opening"], reset["opening"])
