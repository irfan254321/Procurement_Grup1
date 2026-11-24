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
    """Persist the current turn in the caller's transaction."""
    capacity_alerts(db, world)
    tick = world["tick"]
    history = world["history"]
    event = history[0] if history and history[0]["tick"] == tick else {}
    case = world.get("case") or {}
    cycle = case.get("rfq_id") or case.get("batch_id")
    if not cycle:
        return

    _schedule_negotiations(db, world, cycle, case, event)
    if meeting := event.get("meeting"):
        _record_vendor_negotiation(db, world, cycle, case.get("product"), meeting, event.get("role"))
    if quotation := event.get("carrier_quote"):
        _record_carrier_quotation(db, world, cycle, quotation)
    _record_order_events(db, world, case.get("orders", []), event)
    _refresh_cycle_outputs(db, world, cycle, case)


def _schedule_negotiations(db, world, cycle, case, event):
    tick, day = world["tick"], world["day"]
    if event.get("title") == "Permintaan penawaran":
        db.execute("DELETE FROM negotiation_schedules "
                   "WHERE cycle=? AND json_extract(payload,'$.state')='Dijadwalkan'", (cycle,))
        for offset, candidate in enumerate(case["candidates"]):
            schedule_partner(db, cycle, candidate["name"], stage="Negosiasi harga",
                             scheduled_tick=tick + 1 + offset * (2 * NEGOTIATION_ROUNDS + 2),
                             day=day, state="Dijadwalkan", actual_tick=None)
    if event.get("allocations"):
        carriers = {route["carrier"] for offer in case["offers"] for route in offer["routes"]}
        for carrier in carriers:
            active = online(world, carrier)
            schedule_partner(db, cycle, carrier, stage="Penawaran ekspedisi",
                             scheduled_tick=tick + 1 if active else None, day=day,
                             state="Dijadwalkan" if active else "Offline", actual_tick=None)


def _record_vendor_negotiation(db, world, cycle, product_name, meeting, role):
    tick, day = world["tick"], world["day"]
    vendor = meeting["vendor"]
    payload = {"day": day, "vendor": vendor, "round": meeting["round"], **meeting["event"]}
    state = "Berlangsung"
    if role == "deal":
        state = {"accept": "Sepakat", "reject": "Gagal sepakat"}.get(payload["action"], state)
    schedule_partner(db, cycle, vendor, stage="Negosiasi harga", state=state, actual_tick=tick, day=day)
    for company in {BIZ, vendor}:
        add_log(db, company, tick, cycle, "negotiation", payload)

    reference = next((product["reference"] for product in world["products"]
                      if product["name"] == product_name), 0)
    if reference > 0 and payload["amount"] > reference * 1.15:
        alert(db, tick, "price_spike", vendor, (payload["amount"] / reference - 1) * 2,
              "Tawaran melampaui harga acuan katalog lebih dari 15%.")


def _record_carrier_quotation(db, world, cycle, quotation):
    tick, day = world["tick"], world["day"]
    add_log(db, BIZ, tick, cycle, "carrier_quote", quotation)
    options_by_carrier = {}
    for lot in quotation["orders"]:
        vendor = lot["vendor"]
        add_log(db, vendor, tick, cycle, "carrier_quote", {**quotation, "orders": [lot]})
        for option in lot["options"]:
            options_by_carrier.setdefault(option["carrier"], []).append(
                {"vendor": vendor, "quantity": lot["quantity"], **option})
            late_probability = option.get("late_probability", 0)
            if option["selected"] and late_probability >= .35:
                alert(db, tick, "delay_risk", vendor, late_probability,
                      "Risiko terlambat pada layanan terpilih mencapai batas peringatan.")

    for carrier, options in options_by_carrier.items():
        active = online(world, carrier)
        schedule_partner(db, cycle, carrier, stage="Penawaran ekspedisi", actual_tick=tick if active else None,
                         state="Dibandingkan" if active else "Offline", day=day)
        add_log(db, carrier, tick, cycle, "carrier_quote", {
            "product": quotation["product"], "deadline_days": quotation["deadline_days"], "options": options,
        })


def _record_order_events(db, world, orders, event):
    if event.get("title") == "Pembelian disetujui":
        for order in orders:
            epcis(db, world, order, "commissioning", "active", "SAP ERP · BIZ", action="ADD")

    shipment = event.get("shipment")
    if shipment in {"packing", "shipping"}:
        disposition, source = (("in_transit", "GPS/IoT Fleet") if shipment == "shipping"
                               else ("in_progress", "Oracle SCM · Vendor"))
        for order in orders:
            epcis(db, world, order, shipment, disposition, source)

    if inspection := event.get("inspection"):
        order = next((order for order in orders if order.get("id") == inspection["order_id"]), None)
        _record_inspection(db, world, order, inspection)


def _record_inspection(db, world, order, inspection):
    tick = world["tick"]
    state = inspection["state"]
    rejected, accepted = inspection["damaged"], inspection["accepted"]
    if state == "inspected":
        source = "PostgreSQL WMS · Gudang BIZ"
        epcis(db, world, order, "receiving", "in_progress", source)
        epcis(db, world, order, "inspecting", "damaged" if rejected else "available", source,
              measures={"accepted_units": accepted, "damaged_units": rejected})
        if rejected:
            alert(db, tick, "damage", inspection["vendor"], rejected / max(1, inspection["ordered"]),
                  f"{rejected} unit dikarantina setelah inspeksi.")
    elif state == "invoice_hold":
        alert(db, tick, "invoice_mismatch", inspection["vendor"], .85,
              "Pembayaran ditahan sampai faktur dikoreksi.")
        epcis(db, world, order, "holding", "non_sellable_other", "SAP ERP · BIZ")
    elif state == "paid":
        epcis(db, world, order, "accepting", "available", "SAP ERP · BIZ", measures={"paid_units": accepted})


def _refresh_cycle_outputs(db, world, cycle, case):
    history = list(reversed(logs(db, BIZ, cycle, 400)))
    report = procurement_outputs(world, case, history)
    db.execute("INSERT OR REPLACE INTO procurement_cycles VALUES (?,?,?)",
               (cycle, world["tick"], json.dumps(report)))
    db.execute("DELETE FROM delivery_schedules WHERE cycle=?", (cycle,))
    for lot in report["delivery_schedule"]["lots"]:
        payload = json.dumps(lot)
        for company in {BIZ, lot["vendor"], lot.get("carrier")} - {None, "Pemasok arsip"}:
            db.execute("INSERT OR REPLACE INTO delivery_schedules VALUES (?,?,?,?)",
                       (company, cycle, lot["order_key"], payload))


def _public_procurement_cycles(db):
    cycles = []
    for cycle, tick, payload in db.execute(
            "SELECT cycle,tick,payload FROM procurement_cycles ORDER BY tick DESC LIMIT 20"):
        outputs = json.loads(payload)
        history = outputs["negotiation_history"]
        outputs["negotiation_history"] = {
            "rounds_count": len(history["rounds"]),
            "carrier_quote_count": len(history["carrier_quotes"]),
            "locked": True,
        }
        cycles.append(dict(cycle=cycle, tick=tick, **outputs))
    return cycles


def control_tower(db, world):
    cycles = _public_procurement_cycles(db)
    suppliers = world["suppliers"]
    lead = min((supplier["lead_days"] for supplier in suppliers.values() if supplier.get("lead_days")), default=1)
    return {
        "cycles": cycles,
        "forecast": [forecast_demand(product, world["day"], lead) for product in world["products"]],
        "scorecards": [dict(vendor=name, **vendor_scorecard(supplier)) for name, supplier in suppliers.items()],
        "epcis_events": [
            dict(epc_id=epc, tick=tick, biz_step=step, disposition_code=disposition, **json.loads(payload))
            for epc, tick, step, disposition, payload in db.execute(
                "SELECT epc_id,tick,biz_step,disposition,payload FROM epcis_events ORDER BY tick DESC LIMIT 50")
        ],
        "anomaly_alerts": [
            dict(tick=tick, code=code, subject=subject, score=score, severity=severity, **json.loads(payload))
            for tick, code, subject, score, severity, payload in db.execute(
                "SELECT tick,code,subject,score,severity,payload FROM anomaly_alerts ORDER BY tick DESC LIMIT 50")
        ],
    }
