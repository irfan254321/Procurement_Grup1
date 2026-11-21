from math import ceil, sqrt

from finance import VAT_RATE
from .availability import held_partner


def observe_demand(product, day, units):
    if units <= 0:
        return
    days = product.setdefault("demand_observations", {})
    key = str(day)
    days[key] = days.get(key, 0) + units
    for key in list(days):
        if int(key) < day - 29:
            del days[key]


def forecast_demand(product, day, lead_days=1):
    rows = product.get("demand_observations", {})
    day = max(day, max(map(int, rows), default=day))
    average = variance = 0.0
    if rows:
        first = max(min(map(int, rows)), day - 29)
        average = rows.get(str(first), 0)
        for observed_day in range(first+1, day+1):
            delta = rows.get(str(observed_day), 0) - average
            average += .3 * delta
            variance = .7 * (variance + .3 * delta**2)
    lead_days = max(1, min(12, lead_days))
    safety = ceil(1.65 * sqrt(variance * lead_days))
    return {"product": product["name"], "daily_ewma": round(average, 3), "forecast_3_days": round(average*3, 3),
            "safety_stock": safety, "dynamic_rop": max(3, ceil(average*lead_days)+safety),
            "lead_days": lead_days, "observation_days": len(rows)}


def observe_delivery(supplier, ordered, damaged, actual_day, eta):
    if supplier is None or ordered <= 0:
        return
    data = supplier.setdefault("scorecard", {"shipments": 0, "on_time": 0, "units": 0, "defects": 0})
    data["shipments"] += 1
    data["on_time"] += int(actual_day <= eta)
    data["units"] += ordered
    data["defects"] += damaged


def vendor_scorecard(supplier, prior=.1, strength=10):
    data = supplier.get("scorecard", {})
    shipments = data.get("shipments", 0)
    on_time = data.get("on_time", 0)
    units = data.get("units", 0)
    defects = data.get("defects", 0)
    posterior = (prior*strength + shipments-on_time)/(strength+shipments)
    rate = defects/units if units else 0
    grade = "A" if posterior < .15 and rate <= .025 else "B" if posterior < .30 and rate <= .10 else "C"
    return {"shipments": shipments, "on_time": on_time, "otd": round(on_time/shipments, 4) if shipments else None,
            "units": units, "defects": defects, "defect_rate": round(rate, 4) if units else None,
            "posterior_risk": round(posterior, 6), "grade": grade if shipments else None}


def procurement_outputs(world, case, history):
    orders = case.get("orders", [])
    quantity = case.get("planned_quantity", case.get("restock", 0))
    day = case.get("planning_day", world["day"])
    deadline = day + case.get("deadline_days", 12)
    blocked = held_partner(world,world["phase"],case)
    lots = []
    for index, order in enumerate(orders, 1):
        route = order.get("route", {})
        dispatch = order.get("dispatch_day", day)
        eta = order.get("arrival_day", dispatch + order.get("lead_days", 1))
        status = order.get("status", "planned")
        carrier = route.get("carrier")
        lots.append({"order_key": order.get("id", f"lot-{index}"), "vendor": order["vendor"],
                     "carrier": carrier, "service": route.get("name"), "units": order["quantity"],
                     "dispatch_day": dispatch, "eta_day": eta, "deadline_day": order.get("deadline_day", deadline),
                     "distance": route.get("distance"), "delivery_route": [name for name in
                         (carrier, order["vendor"], "Gudang BIZ") if name],
                     "gps_iot_status": f"Menunggu {blocked} online" if blocked and status in {"reserved","packing"} else
                         "Dalam perjalanan" if status=="shipping" else
                         "Tiba di Gudang BIZ" if status in {"inspected","invoice_hold","corrected","paid"} else "Menunggu armada",
                     "invoice_status": status})
    total = lambda key: round(sum(order.get(key, 0) for order in orders), 4)
    cost = case.get("planned_money") or {key: total(key) for key in ("goods_cost","freight","vat","invoice")}
    eta = max((lot["eta_day"] for lot in lots), default=None)
    allocated = sum(order["quantity"] for order in orders)
    accepted = sum(order.get("received_quantity", 0) for order in orders)
    damaged = sum(order.get("damaged_quantity", 0) for order in orders)
    paid = sum(order.get("status") == "paid" for order in orders)
    return {
        "purchase_plan": {"product": case.get("product"), "requested_units": quantity, "allocated_units": allocated,
                          **cost, "vat_rate": VAT_RATE, "currency": "IDR", "rupiah_multiplier": 10000,
                          "formula": "C = Σ(q × harga satuan); faktur PO = C + ongkir + PPN"},
        "supplier_allocation": {"source_system": "Oracle SCM · Vendor (simulasi)",
                                "split": len(orders)>1, "lots": [
                                    {"vendor": o["vendor"], "units": o["quantity"], "carrier": o.get("route",{}).get("carrier")}
                                    for o in orders]},
        "negotiation_history": {"rounds": [r for r in history if r["kind"]=="negotiation"],
                                "carrier_quotes": [r for r in history if r["kind"]=="carrier_quote"]},
        "delivery_schedule": {"tracking_source": "GPS/IoT Fleet (simulasi)", "lots": lots},
        "projected_completion": {"completion_day": eta, "margin_days": deadline-eta if eta is not None else None,
                                 "fulfillment_percent": round(100*allocated/quantity, 2) if quantity else 0,
                                 "accepted_units": accepted, "damaged_units": damaged,
                                 "realized_percent": round(100*accepted/quantity, 2) if quantity else 0,
                                 "paid_invoices": paid, "total_invoices": len(orders),
                                 "invoice_status": "paid" if orders and paid==len(orders) else
                                     "invoice_hold" if any(o.get("status")=="invoice_hold" for o in orders) else "pending"},
    }
