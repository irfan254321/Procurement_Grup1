import json
from datetime import datetime, timedelta, timezone

from agents.analytics import forecast_demand, procurement_outputs, vendor_scorecard
from agents.availability import online
from agents.base import NEGOTIATION_ROUNDS

BIZ = "PT. Biz Indonesia Market"
CAPACITY_BASELINES = {"CloudSoft Corp.":7,"FurniWorks Ltd.":10,"QuickDeliver Ltd.":9,"TechMart Inc.":12}
JAKARTA = timezone(timedelta(hours=7))


def logs(db, company, cycle=None, limit=100):
    clause, values = (" AND cycle=?", (company,cycle,limit)) if cycle else ("",(company,limit))
    rows = db.execute("SELECT tick,cycle,kind,payload FROM negotiation_logs WHERE company=?"+clause+
                      " ORDER BY tick DESC LIMIT ?",values)
    return [dict(tick=tick,cycle=batch,kind=kind,**json.loads(payload)) for tick,batch,kind,payload in rows]


def schedules(db, company):
    return [dict(cycle=cycle,**json.loads(payload)) for cycle,payload in db.execute(
        "SELECT cycle,payload FROM delivery_schedules WHERE company=? ORDER BY cycle DESC,order_key LIMIT 100", (company,))]


def negotiation_schedule(db, company):
    return [dict(cycle=cycle,partner=partner,**json.loads(payload)) for cycle,partner,payload in db.execute(
        """SELECT cycle,partner,payload FROM negotiation_schedules WHERE company=?
           ORDER BY cycle DESC,partner LIMIT 100""",(company,))]


def schedule_partner(db, cycle, partner, **fields):
    for company in {BIZ,partner}:
        saved = db.execute("SELECT payload FROM negotiation_schedules WHERE company=? AND cycle=? AND partner=?",
                           (company,cycle,partner)).fetchone()
        entry = json.loads(saved[0]) if saved else {}
        entry.update(fields)
        db.execute("INSERT OR REPLACE INTO negotiation_schedules VALUES (?,?,?,?)",
                   (company,cycle,partner,json.dumps(entry)))


def add_log(db, company, tick, cycle, kind, payload):
    db.execute("INSERT OR REPLACE INTO negotiation_logs VALUES (?,?,?,?,?)",
               (company,tick,cycle,kind,json.dumps(payload)))


def alert(db, tick, code, subject, score, reason):
    score = round(max(0,min(1,score)),3)
    severity = "tinggi" if score>=.65 else "sedang" if score>=.35 else "rendah"
    db.execute("INSERT OR REPLACE INTO anomaly_alerts VALUES (?,?,?,?,?,?)",
               (tick,code,subject,score,severity,json.dumps({"reason":reason})))


def capacity_alerts(db, world):
    for name,supplier in world["suppliers"].items():
        nominal = CAPACITY_BASELINES.get(name,supplier["capacity"])
        if supplier["capacity"] < nominal and not db.execute(
                "SELECT 1 FROM anomaly_alerts WHERE code='capacity_drop' AND subject=?", (name,)).fetchone():
            alert(db,world["tick"],"capacity_drop",name,1-supplier["capacity"]/nominal,
                  f"Kapasitas turun dari {nominal} menjadi {supplier['capacity']} unit.")


def epcis(db, world, order, step, disposition, source, *, action="OBSERVE", measures=None):
    if not order or not order.get("id"):
        return
    tick, day = world["tick"], world["day"]
    epc = f"urn:bizdistrict:lot:{order['id']}"
    stamp = datetime(2026,1,1,tzinfo=JAKARTA)+timedelta(days=day,minutes=tick%1440)
    data = {"type":"ObjectEvent","eventTime":stamp.isoformat(),"eventTimeZoneOffset":"+07:00",
            "epcList":[epc],"action":action,"bizStep":f"https://ref.gs1.org/cbv/BizStep-{step}",
            "disposition":f"https://ref.gs1.org/cbv/Disp-{disposition}",
            "source_system":source,"order_id":order["id"],"day":day,"measures":measures or {}}
    db.execute("INSERT OR REPLACE INTO epcis_events VALUES (?,?,?,?,?)",
               (epc,tick,step,disposition,json.dumps(data)))


def capture_turn(db, world):
    capacity_alerts(db,world)
    tick = world["tick"]
    event = world["history"][0] if world["history"] and world["history"][0]["tick"]==tick else {}
    case = world.get("case") or {}
    cycle = case.get("rfq_id") or case.get("batch_id")
    if not cycle:
        return
    if event.get("title")=="Permintaan penawaran":
        db.execute("DELETE FROM negotiation_schedules WHERE cycle=? AND json_extract(payload,'$.state')='Dijadwalkan'",(cycle,))
        for offset,candidate in enumerate(case["candidates"]):
            schedule_partner(db,cycle,candidate["name"],stage="Negosiasi harga",
                             scheduled_tick=tick+1+offset*(2*NEGOTIATION_ROUNDS+2),
                             day=world["day"],state="Dijadwalkan",actual_tick=None)
    if event.get("allocations"):
        names = {route["carrier"] for offer in case["offers"] for route in offer["routes"]}
        for carrier in names:
            active = online(world,carrier)
            schedule_partner(db,cycle,carrier,stage="Penawaran ekspedisi",scheduled_tick=tick+1 if active else None,
                             day=world["day"],state="Dijadwalkan" if active else "Offline",actual_tick=None)
    meeting = event.get("meeting")
    if meeting:
        vendor = meeting["vendor"]
        payload = {"day":world["day"],"vendor":vendor,"round":meeting["round"], **meeting["event"]}
        finalized = event.get("role")=="deal" and payload["action"] in {"accept","reject"}
        state = ("Sepakat" if payload["action"]=="accept" else "Gagal sepakat") if finalized else "Berlangsung"
        schedule_partner(db,cycle,vendor,stage="Negosiasi harga",state=state,actual_tick=tick,day=world["day"])
        for company in {BIZ,vendor}:
            add_log(db,company,tick,cycle,"negotiation",payload)
        reference = next((p["reference"] for p in world["products"] if p["name"]==case.get("product")),0)
        if reference > 0 and payload["amount"] > reference*1.15:
            alert(db,tick,"price_spike",vendor,(payload["amount"]/reference-1)*2,
                  "Tawaran melampaui harga acuan katalog lebih dari 15%.")
    quotation = event.get("carrier_quote")
    if quotation:
        add_log(db,BIZ,tick,cycle,"carrier_quote",quotation)
        per_carrier = {}
        for lot in quotation["orders"]:
            add_log(db,lot["vendor"],tick,cycle,"carrier_quote",{**quotation,"orders":[lot]})
            for choice in lot["options"]:
                per_carrier.setdefault(choice["carrier"],[]).append({"vendor":lot["vendor"],"quantity":lot["quantity"],**choice})
                if choice["selected"] and choice.get("late_probability",0)>=.35:
                    alert(db,tick,"delay_risk",lot["vendor"],choice["late_probability"],
                          "Risiko terlambat pada layanan terpilih mencapai batas peringatan.")
        for carrier, choices in per_carrier.items():
            schedule_partner(db,cycle,carrier,stage="Penawaran ekspedisi",actual_tick=tick if online(world,carrier) else None,
                             state="Dibandingkan" if online(world,carrier) else "Offline",day=world["day"])
            add_log(db,carrier,tick,cycle,"carrier_quote",
                    {"product":quotation["product"],"deadline_days":quotation["deadline_days"],"options":choices})

    orders = case.get("orders", [])
    shipment = event.get("shipment")
    if event.get("title") == "Pembelian disetujui":
        for order in orders:
            epcis(db,world,order,"commissioning","active","SAP ERP · BIZ",action="ADD")
    if shipment in {"packing","shipping"}:
        for order in orders:
            epcis(db,world,order,shipment,"in_transit" if shipment=="shipping" else "in_progress",
                  "GPS/IoT Fleet" if shipment=="shipping" else "Oracle SCM · Vendor")
    inspection = event.get("inspection")
    if inspection:
        order = next((o for o in orders if o.get("id")==inspection["order_id"]),None)
        state = inspection["state"]
        rejected, accepted = inspection["damaged"], inspection["accepted"]
        if state == "inspected":
            epcis(db,world,order,"receiving","in_progress","PostgreSQL WMS · Gudang BIZ")
            epcis(db,world,order,"inspecting","damaged" if rejected else "available","PostgreSQL WMS · Gudang BIZ",
                  measures={"accepted_units":accepted,"damaged_units":rejected})
            if rejected:
                alert(db,tick,"damage",inspection["vendor"],rejected/max(1,inspection["ordered"]),
                      f"{rejected} unit dikarantina setelah inspeksi.")
        elif state == "invoice_hold":
            alert(db,tick,"invoice_mismatch",inspection["vendor"],.85,"Pembayaran ditahan sampai faktur dikoreksi.")
            epcis(db,world,order,"holding","non_sellable_other","SAP ERP · BIZ")
        elif state == "paid":
            epcis(db,world,order,"accepting","available","SAP ERP · BIZ",measures={"paid_units":accepted})
    report = procurement_outputs(world,case,list(reversed(logs(db,BIZ,cycle,400))))
    db.execute("INSERT OR REPLACE INTO procurement_cycles VALUES (?,?,?)",(cycle,tick,json.dumps(report)))
    db.execute("DELETE FROM delivery_schedules WHERE cycle=?", (cycle,))
    for lot in report["delivery_schedule"]["lots"]:
        for company in {BIZ,lot["vendor"],lot.get("carrier")} - {None,"Pemasok arsip"}:
            db.execute("INSERT OR REPLACE INTO delivery_schedules VALUES (?,?,?,?)",
                       (company,cycle,lot["order_key"],json.dumps(lot)))


def control_tower(db, world):
    cycles = []
    for cycle,tick,payload in db.execute("SELECT cycle,tick,payload FROM procurement_cycles ORDER BY tick DESC LIMIT 20"):
        outputs = json.loads(payload)
        history = outputs["negotiation_history"]
        outputs["negotiation_history"] = {"rounds_count":len(history["rounds"]),
                                          "carrier_quote_count":len(history["carrier_quotes"]),"locked":True}
        cycles.append(dict(cycle=cycle,tick=tick,**outputs))
    lead = min((s["lead_days"] for s in world["suppliers"].values() if s.get("lead_days")),default=1)
    return {"cycles":cycles, "forecast":[forecast_demand(p,world["day"],lead) for p in world["products"]],
            "scorecards":[dict(vendor=name,**vendor_scorecard(s)) for name,s in world["suppliers"].items()],
            "epcis_events":[dict(epc_id=epc,tick=tick,biz_step=step,disposition_code=disp,**json.loads(data))
                            for epc,tick,step,disp,data in db.execute(
                                "SELECT * FROM epcis_events ORDER BY tick DESC LIMIT 50")],
            "anomaly_alerts":[dict(tick=tick,code=code,subject=subject,score=score,severity=severity,**json.loads(data))
                              for tick,code,subject,score,severity,data in db.execute(
                                  "SELECT * FROM anomaly_alerts ORDER BY tick DESC LIMIT 50")]}
