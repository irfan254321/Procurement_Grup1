"""Business phases owned by the buyer agent."""

from finance import vat
from .base import restock_funds, rupiah


def arrive(ctx, w, rng, mode):
    products = w["products"]
    first = next((p for p in products if not p["units"]), products[0])
    queue = w["queue"]
    for index in range(rng.randint(2,4)):
        p = first if index == 0 and mode in ("stock","cash") else rng.choice(products)
        q = rng.randint(1,4)
        premium = 1.35 if mode in ("stock","cash") else rng.uniform(.94,1.32)
        budget = round(p["retail"]*premium,2)
        price_to_customer = p["retail"] + vat(p["retail"])
        prediction = ctx.predict("buyer", [price_to_customer,budget,q])
        w["customer_count"] += 1
        queue.append({"id":w["customer_count"],"product":p["name"],"quantity":q,"mode":mode,
                      "budget":budget,"prediction":prediction,"buy":budget>=price_to_customer and prediction})
    ctx.record(w,"buyer",f"{len(queue)} pelanggan datang",
           " · ".join(f"Pelanggan {c['id']} mencari {c['quantity']} × {c['product']}" for c in queue))
    w["history"][0]["customers"] = [dict(customer) for customer in queue]


def buyer(ctx, w, c, p, q, rng, mode, opening):
    if w["queue"]:
        w["case"] = w["queue"].pop(0)
        w["phase"] = "seller"
        return
    available = restock_funds(w)
    for product, hold in w["restock_holds"].items():
        if available >= hold["required"]:
            w["case"] = {"product": product, "quantity": 0, "restock": hold["quantity"], "buy": False,
                         "deadline_days": hold.get("deadline_days", 12)}
            del w["restock_holds"][product]
            ctx.record(w, "finance", "Dana restok tersedia",
                   f"{product} · Dana tersedia {rupiah(available)}. Pengadaan {hold['quantity']} unit dilanjutkan.")
            w["phase"] = "procurement"
            return
    if w["restock_requests"]:
        product = next(iter(w["restock_requests"]))
        w["case"] = w["restock_requests"].pop(product)
        w["phase"] = "procurement"
    else:
        w["day"] += 1
        arrive(ctx, w,rng,opening)
    return
