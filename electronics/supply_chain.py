"""Persistent simulated supply, route choices, and exact small-order allocation.

Kaggle shipment models provide historical priors, not electronics ground truth.
Inventory, the road graph, freight tariffs and day conversion are explicit scenario
assumptions. No capacity or damaged-goods labels are invented from shipment data.
"""
from functools import lru_cache
from heapq import heappop, heappush
from math import ceil

from finance import vat

SUPPLY_VERSION = 2
HISTORICAL_DAYS_PER_SIM_DAY = 30
SUPPLIER_REPLENISH_TICKS = 24
ROUTE_PUBLIC_FIELDS = ("name", "mode", "path", "distance", "carrier", "capacity")
# Keep the established distance, stock limit, and historical profile slots stable.
SUPPLIER_SLOTS = {
    "CloudSoft Corp.": 0,
    "FurniWorks Ltd.": 1,
    "QuickDeliver Ltd.": 3,
    "TechMart Inc.": 4,
}
# Route lengths, capacities, costs, and time factors belong to the district
# simulator. The linked company sources describe only their actual businesses.
CARRIERS = {
    "JNE": {
        "description": "JNE menyediakan layanan JTR untuk kiriman besar melalui jalur darat dan laut.",
        "source_url": "https://www.jne.co.id/jtr-id", "capacity": 8,
        "hub_legs": {"Hub Utara": 4, "Hub Selatan": 7}, "warehouse_leg": 4,
        "fixed_tariff_factor": 1.24, "unit_tariff_factor": 1.24, "transit_factor": .76,
    },
    "J&T Cargo": {
        "description": "J&T Cargo melayani pengiriman kargo dan menawarkan layanan antarkota melalui darat.",
        "source_url": "https://www.jtcargo.id/serviceProducts", "capacity": 12,
        "hub_legs": {"Hub Utara": 7, "Hub Selatan": 4}, "warehouse_leg": 4,
        "fixed_tariff_factor": 1.02, "unit_tariff_factor": 1.06, "transit_factor": .94,
    },
    "Pos Logistik Indonesia": {
        "description": "Anak usaha Pos Indonesia yang bergerak di bidang transportasi, pergudangan, dan pengiriman kargo.",
        "source_url": "https://admin-piol.posindonesia.co.id/media/AR%20POS%202024%20HiRes.pdf", "capacity": 16,
        "hub_legs": {"Hub Utara": 6, "Hub Selatan": 5}, "warehouse_leg": 5,
        "fixed_tariff_factor": 1.24, "unit_tariff_factor": .86, "transit_factor": 1.06,
    },
}


@lru_cache(maxsize=1)
def supplier_profiles():
    from supplier_data import get_supplier_profiles
    return get_supplier_profiles()


def supplier_names(catalog):
    return sorted({vendor["name"] for product in catalog for vendor in product["vendors"]})


def init_supply(world, catalog):
    world.setdefault("day", 0)
    world.setdefault("purchase_count", 0)
    if world.get("supply_version") == SUPPLY_VERSION:
        return
    profiles = supplier_profiles()
    previous = world.get("suppliers", {})
    suppliers = {}
    for position, name in enumerate(supplier_names(catalog)):
        index = SUPPLIER_SLOTS.get(name, position)
        if name in previous:
            suppliers[name] = previous[name]
            continue
        profile = profiles[index % len(profiles)]
        capacity = [7, 10, 14, 9, 12][index % 5]
        if world.get("opening") == "supply" and index == 0:
            capacity = 4
        suppliers[name] = {
            "name": name, "profile": profile,
            "source_vendor": profile.get("source_vendor", profile.get("vendor", "")),
            "capacity": capacity, "capacity_remaining": capacity,
            "stock": {product["name"]: capacity * 3 for product in catalog},
            "lead_days": None, "late_probability": None,
            "domain_transfer": True, "index": index,
        }
    world.update(suppliers=suppliers, supply_version=SUPPLY_VERSION)
    world.setdefault("supply_replenished_tick", world["tick"])
    world.setdefault("purchase_orders", [])


def refresh_supply(world):
    # Replenishment is a stated simulator rule, not a trained inventory forecast.
    if world["tick"] - world.get("supply_replenished_tick", 0) < SUPPLIER_REPLENISH_TICKS:
        return
    for supplier in world["suppliers"].values():
        supplier["capacity_remaining"] = supplier["capacity"]
        for product, stock in supplier["stock"].items():
            supplier["stock"][product] = min(supplier["capacity"] * 4,
                                             stock + supplier["capacity"])
    world["supply_replenished_tick"] = world["tick"]


def shortest_path(graph, start, finish):
    """Dijkstra on the scenario's nonnegative distance graph."""
    queue = [(0, start, [start])]
    best = {}
    while queue:
        distance, node, path = heappop(queue)
        if distance > best.get(node, float("inf")):
            continue
        if node == finish:
            return path, distance
        for neighbor, weight in graph.get(node, []):
            total = distance + weight
            if total < best.get(neighbor, float("inf")):
                best[neighbor] = total
                heappush(queue, (total, neighbor, path + [neighbor]))
    return [], float("inf")


def freight_services(vendor, index):
    """Return each simulator route and tariff as rates against unit price."""
    supplier_legs = [("Hub Utara", 5 + index * 2), ("Hub Selatan", 9 + index)]
    routes = []
    for carrier, settings in CARRIERS.items():
        graph = {hub: [(carrier, distance)] for hub, distance in settings["hub_legs"].items()}
        graph[carrier] = [("Gudang BIZ", settings["warehouse_leg"])]
        for name, source_mode, speed, multiplier, allowed_legs in (
            ("Reguler", "Truck", 1, 1, supplier_legs),
            ("Ekspres", "Air", .75, 1.7, supplier_legs[1:]),
        ):
            graph[vendor] = allowed_legs
            path, distance = shortest_path(graph, vendor, "Gudang BIZ")
            routes.append({
                "name": name, "mode": "Darat", "path": path, "distance": distance,
                "carrier": carrier, "capacity": settings["capacity"],
                "fixed_rate": .012 * distance / 10 * multiplier * settings["fixed_tariff_factor"],
                "unit_rate": .004 * multiplier * settings["unit_tariff_factor"],
                "source_mode": source_mode, "speed": speed * settings["transit_factor"],
            })
    return routes


def carrier_catalog():
    return {carrier: {
        "description": settings["description"], "source_url": settings["source_url"],
        "capacity": settings["capacity"], "terminal": carrier,
        "capacity_unit": "unit per kiriman",
    } for carrier, settings in CARRIERS.items()}


def supplier_freight_catalog(catalog):
    fields = (*ROUTE_PUBLIC_FIELDS, "fixed_rate", "unit_rate")
    return {vendor: {"services": [
        {field: service[field] for field in fields}
        for service in freight_services(vendor, SUPPLIER_SLOTS.get(vendor, index))
    ]} for index, vendor in enumerate(supplier_names(catalog))}


def quote_routes(world, vendor, quantity, unit_price):
    from supplier_data import predict_supply
    supplier = world["suppliers"][vendor]
    routes = []
    predictions = {}
    for service in freight_services(vendor, supplier["index"]):
        source_mode = service["source_mode"]
        if source_mode not in predictions:
            predictions[source_mode] = predict_supply(supplier["profile"], quantity, mode=source_mode)
        prediction = predictions[source_mode]
        source_days = float(prediction["predicted_days"])
        lead_days = max(1, min(12, ceil(source_days / HISTORICAL_DAYS_PER_SIM_DAY * service["speed"])))
        risk = max(0, min(1, float(prediction["late_probability"])))
        from agents.analytics import vendor_scorecard
        risk = vendor_scorecard(supplier, prior=risk, strength=6)["posterior_risk"]
        routes.append({
            **{field: service[field] for field in ROUTE_PUBLIC_FIELDS},
            "source_mode": source_mode,
            "lead_days": lead_days, "late_probability": risk,
            "source_prediction_days": round(source_days, 2),
            "fixed_freight": round(unit_price * service["fixed_rate"], 4),
            "unit_freight": round(unit_price * service["unit_rate"], 4),
            "domain_transfer": True,
            "online": world.get("company_availability", {}).get(service["carrier"], True),
        })
    # Summarize the fastest quoted route with enough space for the request.
    available = [route for route in routes if route["online"]]
    eligible = [route for route in available if route["capacity"] >= quantity]
    fastest = min(eligible or available or routes, key=lambda route: (
        route["lead_days"], route["fixed_freight"] + route["unit_freight"] * quantity))
    supplier.update(lead_days=fastest["lead_days"], late_probability=fastest["late_probability"])
    return routes


def carrier_quote_options(orders, offers, deadline_days):
    """Compare carrier routes for planned lots at their negotiated quantities."""
    routes_by_vendor = {offer["vendor"]: offer["routes"] for offer in offers if offer["accepted"]}
    lots = []
    for order in orders:
        quantity = order["quantity"]
        selected_route = order["route"]
        options = []
        for route in routes_by_vendor[order["vendor"]]:
            freight = round(route["fixed_freight"] + route["unit_freight"] * quantity, 4)
            cost = round(order["goods_cost"] + freight, 4)
            selected = (route["carrier"], route["name"]) == (selected_route["carrier"], selected_route["name"])
            options.append({**route, "freight": freight, "invoice": round(cost + vat(cost), 4),
                            "eligible": route.get("online", True) and quantity <= route["capacity"] and route["lead_days"] <= deadline_days,
                            "selected": selected})
        lots.append({"vendor": order["vendor"], "quantity": quantity,
                     "selected_carrier": selected_route["carrier"], "selected_service": selected_route["name"],
                     "options": options})
    return lots


def allocate_orders(offers, quantity, budget, deadline_days, risk_weight=.15, cost_limit=float("inf")):
    """Exact integer allocation for <= 40 units and a handful of vendor options.

    Pareto frontiers retain both invoice cost and risk-adjusted objective, so a
    cheaper feasible combination isn't lost merely because a risky one scores
    differently. At most one route is activated per supplier; freight is charged
    once per activated shipment. Carrier limits apply per shipment. No
    partial/infeasible plan is called complete.
    """
    if quantity <= 0 or quantity > 40 or budget < 0:
        return None
    # Entries: (invoiced total, landed cost, objective, order list).
    frontiers = {0: [(0., 0., 0., [])]}
    for offer in offers:
        if not offer.get("accepted", True):
            continue
        updated = {units: list(values) for units, values in frontiers.items()}
        capacity = max(0, int(offer["capacity"]))
        for route in offer["routes"]:
            if not route.get("online", True) or route["lead_days"] > deadline_days:
                continue
            shipment_capacity = min(capacity, route.get("capacity", capacity))
            for previous_quantity, previous in frontiers.items():
                for count in range(1, min(shipment_capacity, quantity - previous_quantity) + 1):
                    goods = round(offer["price"] * count, 2)
                    freight = round(route["fixed_freight"] + route["unit_freight"] * count, 4)
                    cost = round(goods + freight, 4)
                    tax = vat(cost)
                    invoice = round(cost + tax, 4)
                    risk_cost = goods * route["late_probability"] * risk_weight
                    for old_total, old_cost, old_objective, plan in previous:
                        total = round(old_total + invoice, 4)
                        landed_cost = round(old_cost + cost, 4)
                        if total > budget + .00005 or landed_cost > cost_limit:
                            continue
                        order = {"vendor": offer["vendor"], "quantity": count,
                                 "unit_cost": offer["price"], "goods_cost": goods,
                                 "freight": freight, "cost": cost, "vat": tax,
                                 "invoice": invoice, "route": dict(route),
                                 "lead_days": route["lead_days"],
                                 "late_probability": route["late_probability"],
                                 "source_prediction_days": route.get("source_prediction_days", 0)}
                        updated.setdefault(previous_quantity + count, []).append(
                            (total, landed_cost, old_objective + invoice + risk_cost, plan + [order]))
        # Remove dominated states with identical filled quantity.
        for filled, values in updated.items():
            kept = []
            for value in sorted(values, key=lambda value: value[:3]):
                _, cost, objective, _ = value
                if not any(previous[1] <= cost and previous[2] <= objective for previous in kept):
                    kept.append(value)
            updated[filled] = kept
        frontiers = updated
    candidates = frontiers.get(quantity, [])
    if not candidates:
        return None
    return min(candidates, key=lambda value: (value[2], value[0]))[3]


def summarize_purchase(world):
    purchase = world.get("last_purchase")
    if not purchase or not purchase.get("orders"):
        return
    orders = purchase["orders"]
    for field in ("quantity", "received_quantity", "damaged_quantity", "cost", "freight", "vat", "invoice"):
        purchase[field] = round(sum(order.get(field, 0) for order in orders), 4)
    purchase["invoice_original"] = round(sum(order.get("invoice_original", order["invoice"]) for order in orders), 4)
    expected_units = sum(order.get("received_quantity", order["quantity"]) for order in orders)
    purchase["unit_cost"] = round(sum(order.get("goods_cost", 0) for order in orders) / expected_units, 4) if expected_units else 0
    purchase["vendor"] = ", ".join(order["vendor"] for order in orders)
    purchase["revenue"] = round(purchase["retail"] * expected_units, 2)
    purchase["profit"] = round(purchase["revenue"] - purchase["cost"], 2)
    purchase["profit_per_unit"] = round(purchase["profit"] / expected_units, 4) if expected_units else 0
    paid = sum(order.get("status") == "paid" for order in orders)
    purchase["status"] = "Seluruh faktur dibayar" if paid == len(orders) else f"{paid}/{len(orders)} faktur dibayar"


def activate_order(case, order):
    case.update(vendor=order["vendor"], restock=order["quantity"], agreed=order["unit_cost"],
                total=order["cost"], freight=order["freight"], invoice=order["invoice"],
                active_order_id=order["id"])
    for key in ("received_quantity", "damaged_quantity", "accepted_cost", "invoice_quantity", "invoice_original", "expected_invoice"):
        case.pop(key, None)


def active_order(world):
    case = world["case"]
    return next((order for order in case.get("orders", []) if order["id"] == case.get("active_order_id")), None)
