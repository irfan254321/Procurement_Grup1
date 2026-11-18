"""Persistent simulated supply, route choices, and exact small-order allocation.

Kaggle shipment models provide historical priors, not electronics ground truth.
Inventory, the road graph, freight tariffs and day conversion are explicit scenario
assumptions. No capacity or damaged-goods labels are invented from shipment data.
"""
from functools import lru_cache
from heapq import heappop, heappush
from math import ceil

from finance import vat

SUPPLY_VERSION = 1
HISTORICAL_DAYS_PER_SIM_DAY = 30


@lru_cache(maxsize=1)
def supplier_profiles():
    from supplier_data import get_supplier_profiles
    return get_supplier_profiles()


def init_supply(world, catalog):
    world.setdefault("day", 0)
    world.setdefault("purchase_count", 0)
    if world.get("supply_version") == SUPPLY_VERSION:
        return
    profiles = supplier_profiles()
    names = sorted({vendor["name"] for product in catalog for vendor in product["vendors"]})
    suppliers = {}
    for index, name in enumerate(names):
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
    world.update(suppliers=suppliers, supply_version=SUPPLY_VERSION,
                 supply_replenished_tick=world["tick"], purchase_orders=[])


def refresh_supply(world):
    # Replenishment is a stated simulator rule, not a trained inventory forecast.
    if world["tick"] - world.get("supply_replenished_tick", 0) < 24:
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


def quote_routes(world, vendor, quantity, unit_price):
    from supplier_data import predict_supply
    supplier = world["suppliers"][vendor]
    index = supplier["index"]
    graph = {
        vendor: [("Hub Utara", 5 + index * 2), ("Hub Selatan", 9 + index)],
        "Hub Utara": [("Simpang BIZ", 7)],
        "Hub Selatan": [("Simpang BIZ", 5)],
        "Simpang BIZ": [("Gudang BIZ", 3)],
    }
    regular = shortest_path(graph, vendor, "Gudang BIZ")
    # The express service uses a dedicated southern corridor and slower
    # handling is compressed by its service profile, independently of length.
    express_graph = {**graph, vendor: [graph[vendor][1]]}
    express = shortest_path(express_graph, vendor, "Gudang BIZ")
    routes = []
    for name, mode, speed, multiplier, (path, distance) in [
        ("Reguler", "Truck", 1, 1, regular),
        ("Ekspres", "Air", .75, 1.7, express),
    ]:
        prediction = predict_supply(supplier["profile"], quantity, mode=mode)
        source_days = float(prediction["predicted_days"])
        lead_days = max(1, min(12, ceil(source_days / HISTORICAL_DAYS_PER_SIM_DAY * speed)))
        risk = max(0, min(1, float(prediction["late_probability"])))
        routes.append({
            "name": name, "mode": "Darat", "source_mode": mode, "path": path, "distance": distance,
            "lead_days": lead_days, "late_probability": risk,
            "source_prediction_days": round(source_days, 2),
            "fixed_freight": round(unit_price * .012 * distance / 10 * multiplier, 4),
            "unit_freight": round(unit_price * .004 * multiplier, 4),
            "domain_transfer": True,
        })
    supplier.update(lead_days=routes[0]["lead_days"], late_probability=routes[0]["late_probability"])
    return routes


def allocate_orders(offers, quantity, budget, deadline_days, risk_weight=.15, cost_limit=float("inf")):
    """Exact integer allocation for <= 40 units and a handful of vendor options.

    Pareto frontiers retain both invoice cost and risk-adjusted objective, so a
    cheaper feasible combination isn't lost merely because a risky one scores
    differently. At most one route is activated per supplier; freight is charged
    once per activated shipment. No partial/infeasible plan is called complete.
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
            if route["lead_days"] > deadline_days:
                continue
            for previous_quantity, previous in frontiers.items():
                for count in range(1, min(capacity, quantity - previous_quantity) + 1):
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
