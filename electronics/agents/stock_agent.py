"""Business phases owned by the stock agent."""

from finance import vat
from supply_chain import active_order, summarize_purchase
from .analytics import forecast_demand, observe_delivery
from .availability import online
from .base import record_receipt


def stock(ctx, w, c, p, q, rng, mode, opening):
    lead = min((s["lead_days"] for name,s in w.get("suppliers", {}).items()
                if s.get("lead_days") and online(w,name)), default=1)
    forecast = forecast_demand(p, w["day"], lead)
    reorder = forecast["dynamic_rop"]
    projected = (q if c.get("stock_shortage") else 0) + sum(
        order["quantity"] for order in w["queue"] if order["product"] == p["name"] and order["buy"])
    needs_order = ctx.record(w, "stock", "Periksa rak dan gudang",
                             f"{p['name']} · sisa {p['units']} unit, permintaan tercatat {projected}, titik pesan {reorder}.",
                             vector=[p["units"], projected, reorder])
    low_stock = p["units"] <= reorder or c.get("stock_shortage") or (projected > 0 and needs_order)
    if p["name"] in w["restock_holds"]:
        w["history"][0]["detail"] += " Permintaan restok aktif. Keuangan menunggu dana tersedia."
        w["phase"] = "buyer"
        return
    if low_stock and w["tick"] < p.get("retry_after", 0):
        w["history"][0]["detail"] += f" Restok ditahan sampai giliran {p['retry_after']} agar penawaran yang sama tidak langsung diulang."
    if low_stock and w["tick"] >= p.get("retry_after", 0):
        request = w["restock_requests"].setdefault(p["name"], {"product": p["name"], "quantity": 0, "buy": False})
        request["demand"] = max(projected, request.get("demand", 0))
    w["phase"] = "buyer"


def receive(ctx, w, c, p, q, rng, mode, opening):
    order = active_order(w)
    if order:
        w["day"] = max(w["day"], order["arrival_day"])
    damaged = 0
    scripted_damage = opening == "damage" and not w.get("damage_simulated")
    if scripted_damage or (mode == "auto" and rng.randrange(12) == 0):
        damaged = min(2, c["restock"])
        w["damage_simulated"] = True
    accepted = c["restock"] - damaged
    accepted_cost = round(round(c["agreed"] * accepted, 2) + c.get("freight", 0), 4) if damaged else c["total"]
    expected_invoice = round(accepted_cost + vat(accepted_cost), 4) if "invoice" in c else accepted_cost
    c.update(received_quantity=accepted, damaged_quantity=damaged,
             accepted_cost=accepted_cost, invoice_quantity=c["restock"],
             invoice_original=c.get("invoice", c["total"]), expected_invoice=expected_invoice)
    if accepted:
        p["cost"] = round((p["units"] * p["cost"] + accepted_cost) / (p["units"] + accepted), 2)
        p["units"] += accepted
    elif c.get("freight"):
        w["cogs"] = round(w["cogs"] + c["freight"], 4)
    purchase = w.get("last_purchase")
    if order:
        order.update(received_quantity=accepted, damaged_quantity=damaged,
                     status="inspected", expected_invoice=expected_invoice, received_day=w["day"])
        observe_delivery(w["suppliers"].get(order["vendor"]),order["quantity"],damaged,w["day"],
                         order.get("promised_day",order["arrival_day"]))
        summarize_purchase(w)
    elif purchase:
        purchase.update(received_quantity=accepted, damaged_quantity=damaged,
                        status="Menunggu pemeriksaan faktur")
        if damaged:
            purchase["invoice_original"] = c["invoice_original"]
    detail = f"{p['name']} dari {c['vendor']} · {c['restock']} unit diperiksa, {accepted} unit masuk stok jual."
    if damaged:
        detail += f" {damaged} unit rusak dipisahkan untuk retur."
    record_receipt(ctx, w, "stock", "Pemeriksaan barang", detail, "inspected")
    w["history"][0]["shipment"] = "delivered"
    w["phase"] = "invoice_check"
