import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import agent
from database import operations


class ControlTowerTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        override = patch.object(agent,"DB",Path(folder.name)/"district.sqlite3")
        override.start()
        self.addCleanup(override.stop)
        agent.initialize()

    def request(self,path,payload=None,token=None,method=None):
        handler = object.__new__(agent.Handler)
        handler.path = path
        handler.headers = {"Authorization":"Bearer "+token} if token else {}
        if payload is not None:
            content = json.dumps(payload).encode()
            handler.headers.update({"Content-Type":"application/json","Content-Length":str(len(content))})
            handler.rfile = io.BytesIO(content)
        results = []
        handler.send_data = lambda body,mime="application/json",status=200: results.append((status,body))
        getattr(handler,"do_"+(method or ("POST" if payload is not None else "GET")))()
        return results[0]

    def advance(self, scenario, criterion, limit=150):
        for _ in range(limit):
            status,world = self.request("/api/step/"+scenario,method="POST")
            self.assertEqual(status,200)
            if criterion(world):
                return world
        self.fail("Target simulator state not reached")

    def test_split_quote_memory_and_company_auth(self):
        self.request("/api/reset/supply",method="POST")
        self.assertEqual(self.request("/api/companies/biz/availability",{"online":False})[0],404)
        self.assertEqual(self.request("/api/companies/cloudsoft/availability",{"online":False})[0],200)
        self.assertEqual(self.request("/api/companies/jne/availability",{"online":False})[0],200)
        quote_world = self.advance("supply",lambda w:w["history"] and w["history"][0].get("carrier_quote"))
        quote = quote_world["history"][0]["carrier_quote"]
        self.assertEqual(quote["quantity"],30)
        for order in quote["orders"]:
            self.assertNotEqual(order["vendor"],"CloudSoft Corp.")
            self.assertNotEqual(order["selected_carrier"],"JNE")
            self.assertEqual({x["carrier"] for x in order["options"]},{"JNE","J&T Cargo","Pos Logistik Indonesia"})
            self.assertTrue(all(not option["eligible"] for option in order["options"] if option["carrier"]=="JNE"))
        tower = self.request("/api/control-tower")[1]
        self.assertEqual({a["code"] for a in tower["anomaly_alerts"] if a["code"]=="capacity_drop"},{"capacity_drop"})
        cycle = tower["cycles"][0]
        self.assertTrue({"purchase_plan","supplier_allocation","negotiation_history","delivery_schedule","projected_completion"}<=cycle.keys())
        self.assertTrue(cycle["supplier_allocation"]["split"])
        plan=cycle["purchase_plan"]
        self.assertAlmostEqual(plan["invoice"],plan["goods_cost"]+plan["freight"]+plan["vat"],places=4)
        self.assertEqual(plan["vat_rate"],.11)
        self.assertTrue(cycle["negotiation_history"]["locked"])
        self.assertNotIn("rounds",cycle["negotiation_history"])
        for role in ("procurement","vendor","deal","orchestrator"):
            rows=self.request("/api/memory/"+role)[1]["memory"]
            self.assertTrue(rows)
            self.assertEqual(rows[0]["role"],role)
            self.assertIn("stock_units",rows[0]["facts"])
        self.assertEqual(self.request("/api/memory/unknown")[0],404)
        private="/api/companies/jne/negotiations"
        self.assertEqual(self.request(private)[0],401)
        status,access=self.request("/api/companies/jne/access",{"password":"test-pass-123","setup":True})
        self.assertEqual(status,200)
        token=access["token"]
        self.assertEqual(self.request("/api/companies/jt-cargo/negotiations",token=token)[0],401)
        private_data=self.request(private,token=token)[1]
        logs=private_data["negotiation_history"]
        self.assertEqual({option["carrier"] for log in logs for option in log["options"]},{"JNE"})
        self.assertEqual(private_data["negotiation_schedule"][0]["state"],"Offline")
        self.request("/api/reset/normal",method="POST")
        self.assertEqual(self.request(private,token=token)[0],401)
        self.assertEqual(self.request("/api/memory")[1]["memory"],[])
        self.assertTrue(self.request("/api/companies/jne/access")[1]["configured"])
        with agent.connect() as db:
            for table in ("agent_memory","epcis_events","anomaly_alerts","negotiation_logs","delivery_schedules",
                          "negotiation_schedules","procurement_cycles"):
                self.assertEqual(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0],0)

    def test_inspection_invoice_hold_epcis_and_scorecard(self):
        self.request("/api/reset/damage",method="POST")
        self.advance("damage",lambda world:world["phase"]=="invoice_correction")
        tower=self.request("/api/control-tower")[1]
        self.assertTrue({"damage","invoice_mismatch"}<={row["code"] for row in tower["anomaly_alerts"]})
        self.assertTrue({"SAP ERP · BIZ","Oracle SCM · Vendor","GPS/IoT Fleet","PostgreSQL WMS · Gudang BIZ"}<=
                        {row["source_system"] for row in tower["epcis_events"]})
        self.assertEqual(tower["cycles"][0]["projected_completion"]["invoice_status"],"invoice_hold")
        self.advance("damage",lambda world:world["history"][0].get("inspection",{}).get("state")=="paid")
        tower=self.request("/api/control-tower")[1]
        self.assertTrue(any(row["defects"]>0 for row in tower["scorecards"]))
        self.assertTrue(any(row["epc_id"].startswith("urn:bizdistrict:lot:") and row["biz_step"]=="holding"
                            for row in tower["epcis_events"]))
        with agent.connect() as db, db:
            world=agent.load_world(db)
            product=world["products"][0]
            world["tick"]+=1
            world["case"]={"rfq_id":"TEST","product":product["name"]}
            world["history"].insert(0,{
                "tick":world["tick"],"meeting":{"round":1,"vendor":"TechMart Inc.",
                    "event":{"amount":product["reference"]*1.4,"speaker":"vendor","action":"opening","reason":"Uji"}},
                "carrier_quote":{"orders":[{"vendor":"TechMart Inc.","quantity":1,"options":[
                    {"carrier":"JNE","late_probability":.7,"selected":True}]}],
                    "product":product["name"],"deadline_days":6},
            })
            operations.capture_turn(db,world)
        alerts=self.request("/api/control-tower")[1]["anomaly_alerts"]
        self.assertTrue({"price_spike","delay_risk"}<={row["code"] for row in alerts})

    def test_retired_supplier_is_purged_from_current_version_negotiation(self):
        world=agent.new_world("supply")
        world.update(phase="counter",case={"product":world["products"][0]["name"],"quantity":0,
            "vendor":agent.RETIRED_SUPPLIER,"candidates":[{"name":agent.RETIRED_SUPPLIER}],"offers":[],"orders":[]})
        with agent.connect() as db, db:
            agent.storage.save_world(db,world)
            loaded=agent.load_world(db)
        self.assertEqual(loaded["phase"],"procurement")
        self.assertNotIn(agent.RETIRED_SUPPLIER,json.dumps(loaded))

    def test_exclusive_server_rejects_a_second_listener(self):
        with agent.ExclusiveHTTPServer(("127.0.0.1",0),agent.Handler) as server:
            with self.assertRaises(OSError):
                agent.ExclusiveHTTPServer(server.server_address,agent.Handler)

    def test_offline_committed_carrier_delays_without_cancelling_invoice(self):
        self.request("/api/reset/supply",method="POST")
        before=self.advance("supply",lambda w:w["phase"]=="packing")
        with agent.connect() as db:
            reserved=agent.load_world(db)["reserved"]
        shipment=before["case"]["orders"][0]
        carrier=shipment["route"]["carrier"]
        slug=next(slug for slug,name in agent.COMPANY_NAMES.items() if name==carrier)
        path=f"/api/companies/{slug}/availability"
        self.request(path,{"online":False})
        held=self.advance("supply",lambda w:w["history"][0].get("offline_hold"))
        self.assertEqual(held["phase"],"packing")
        with agent.connect() as db:
            self.assertEqual(agent.load_world(db)["reserved"],reserved)
        self.assertEqual(held["case"]["orders"][0]["arrival_day"],shipment["arrival_day"]+1)
        self.request(path,{"online":True})
        self.advance("supply",lambda w:w["history"][0].get("shipment")=="shipping")
