"""Shared decision context and verified simulation facts."""

from domain import AGENTS, FEATURES
from finance import free_cash
from supply_chain import active_order

RESTOCK_THRESHOLD = 3
NEGOTIATION_ROUNDS = 3
OFFER_OPENING_MULTIPLIER = 1.10
OFFER_FLOOR_MULTIPLIER = .90


def rupiah(value):
    return "Rp" + f"{value * 10_000:,.0f}".replace(",", ".")


class DecisionContext:
    def __init__(self, predict, model_name, recalled):
        self.predict = predict
        self.model_name = model_name
        self.recalled = recalled

    def record(self, world, role, title, detail, *, vector=None):
        event = {"tick": world["tick"], "role": role, "title": title, "detail": detail}
        if role in self.recalled:
            event["prior_memory_tick"] = self.recalled[role]["tick"]
        if vector is not None:
            vote = self.predict(role, vector)
            event.update(model=self.model_name(role), prediction=AGENTS[role][2 if vote else 3],
                         features=dict(zip(FEATURES[role], vector)))
        world["scene"] = role
        world["history"] = [event, *world["history"][:79]]
        return event.get("prediction") == AGENTS[role][2]


def meeting(w, speaker, action, amount):
    c = w["case"]
    event = w["history"][0]
    event["meeting"] = {
        "vendor": c["vendor"], "round": c["round"],
        "vendorPosition": c["vendor_index"]+1, "vendorTotal": len(c["candidates"]),
        "event": {"speaker": speaker, "action": action, "amount": amount, "reason": event["detail"]},
    }


def record_receipt(ctx, w, role, title, detail, state):
    case = w["case"]
    order = active_order(w)
    carrier = (order or {}).get("route", {}).get("carrier")
    ctx.record(w, role, title, detail)
    w["history"][0].update(vendor=case["vendor"], inspection={
        "state": state, "product": case["product"], "vendor": case["vendor"],
        "ordered": case["restock"], "accepted": case["received_quantity"],
        "damaged": case["damaged_quantity"],
        "order_id": case.get("active_order_id"), "carrier": carrier,
    })


def shipment_snapshot(case):
    return [{key: order[key] for key in ("id", "vendor", "quantity", "route", "arrival_day", "status")}
            for order in case.get("orders", [])]


def customer_state(w):
    for key, default in (("queue", []), ("restock_requests", {}),
                         ("restock_holds", {}), ("reinvested", 0), ("customer_count", 0),
                         ("customer_results", [])):
        w.setdefault(key, default)
    # Existing saves may still have customers from the previous backorder flow.
    cancelled = w.pop("waiting", [])
    if any(order.get("restocked") for order in w["queue"]):
        cancelled.extend(order for order in w["queue"] if order.get("restocked"))
        w["queue"] = [order for order in w["queue"] if not order.get("restocked")]
    if w["phase"] == "seller" and (w.get("case") or {}).get("restocked"):
        cancelled.append(w["case"])
        w.update(phase="buyer", case=None)
    if cancelled:
        products = {order["id"]: order["product"] for order in cancelled if "id" in order}
        results = [{"id": order_id, "product": name, "status": "Stok tidak cukup"}
                   for order_id, name in products.items()]
        results.extend(result for result in w["customer_results"] if result["id"] not in products)
        w["customer_results"] = results[:20]


def restock_funds(w):
    return max(0, min(free_cash(w) - w["reserved"], w["fund"]))


def hold_restock(w, product, quantity, required, deadline_days=12):
    available = restock_funds(w)
    w["restock_holds"][product] = {"quantity": quantity, "required": required, "available": available,
                                  "deadline_days": deadline_days,
                                  "shortfall": round(max(0, required - available), 4)}


def refresh_restock_holds(w):
    if w["restock_holds"]:
        available = restock_funds(w)
        for hold in w["restock_holds"].values():
            hold.update(available=available, shortfall=round(max(0, hold["required"] - available), 4))

