"""Business phases owned by the procurement agent."""

from domain import MIN_MARKUP
from supply_chain import allocate_orders, carrier_quote_options
from .availability import online
from .base import hold_restock, restock_funds, rupiah


def procurement(ctx, w, c, p, q, rng, mode, opening):
    c.setdefault("rfq_id", f"RFQ-{w['tick']:06d}")
    c.setdefault("planning_day", w["day"])
    demand = c.get("demand", 0)
    c.setdefault("restock", min(40 if opening == "supply" else 14,
                                max(6,12-p["units"],demand-p["units"])))
    c.setdefault("deadline_days", 12)
    candidates = [{**v, "capacity": min(w["suppliers"][v["name"]]["capacity_remaining"],
                                        w["suppliers"][v["name"]]["stock"][p["name"]], c["restock"])}
                  for v in p["vendors"] if v["name"] in w["suppliers"] and online(w,v["name"])]
    def key(v):
        priority = ctx.predict("procurement", [v["price"], p["reference"], v["capacity"], min(c["restock"], v["capacity"])])
        return (not priority, v["price"], v["name"])
    c.update(candidates=sorted(candidates, key=key), vendor_index=0, offers=[],
             ceiling=round(min(p["reference"]*1.08, p["retail"]/MIN_MARKUP), 2),
             planned_quantity=c["restock"])
    if not candidates:
        ctx.record(w, "procurement", "Pemasok sedang tutup", f"{p['name']} menunggu pemasok kembali online.")
        p["retry_after"] = w["tick"] + 8
        w["phase"] = "buyer"
        return
    v = c["candidates"][0]
    ctx.record(w, "procurement", "Permintaan penawaran",
           f"{c['restock']} × {p['name']} · {len(candidates)} vendor diundang.",
           vector=[v["price"], p["reference"], v["capacity"], min(c["restock"], v["capacity"])])
    w["phase"] = "vendor_open"


def compare(ctx, w, c, p, q, rng, mode, opening):
    c.setdefault("deadline_days", 12)
    quantity = c.get("planned_quantity", c["restock"])
    available = restock_funds(w)
    cost_limit = round(p["retail"] * quantity, 2) / MIN_MARKUP
    plan = allocate_orders(c["offers"], quantity, available, c["deadline_days"],
                           cost_limit=cost_limit)
    if plan:
        c.update(orders=plan, vendor=plan[0]["vendor"],
                 agreed=round(sum(order["goods_cost"] for order in plan)/quantity, 4))
        c["planned_money"] = {key: round(sum(order[key] for order in plan),4)
                              for key in ("goods_cost","freight","vat","invoice")}
        def route_label(order):
            route = order["route"]
            return " ".join(part for part in (route.get("carrier"), route["name"]) if part)

        ctx.record(w, "procurement", "Vendor terpilih",
               " · ".join(f"{order['vendor']}: {order['quantity']} unit via {route_label(order)} ({order['lead_days']} hari simulasi)" for order in plan)
               + f". Alokasi memenuhi {quantity} unit dengan biaya termasuk ongkir/PPN dan prior risiko; tenggat {c['deadline_days']} hari.")
        w["history"][0].update(vendor=plan[0]["vendor"], allocations=plan)
        w["phase"] = "carrier_quote"
    else:
        cheapest = allocate_orders(c["offers"], quantity, float("inf"), c["deadline_days"],
                                   risk_weight=0, cost_limit=cost_limit)
        if cheapest:
            required = round(sum(order["invoice"] for order in cheapest), 4)
            hold_restock(w, p["name"], quantity, required, c["deadline_days"])
            ctx.record(w, "finance", "Pembelian ditahan",
                   f"{p['name']} · {quantity} unit. Rencana termurah memerlukan {rupiah(required)} termasuk ongkir dan PPN. Dana tersedia {rupiah(available)}.")
        else:
            ctx.record(w, "procurement", "Tidak tercapai kesepakatan",
                   f"Tidak ada kombinasi lengkap {quantity} unit yang memenuhi kapasitas, tenggat, dan target laba. Restok ditunda 18 giliran.")
            p["retry_after"] = w["tick"]+18
        w["phase"] = "buyer"


def carrier_quote(ctx, w, c, p, q, rng, mode, opening):
    lots = carrier_quote_options(c["orders"], c["offers"], c["deadline_days"])
    detail = " · ".join(f"{lot['vendor']}: {lot['selected_carrier']} {lot['selected_service']}" for lot in lots)
    ctx.record(w, "procurement", "Bandingkan penawaran logistik",
           f"{detail}. Jarak, ongkir, kapasitas, tenggat, dan risiko menentukan rute sebelum diajukan ke Keuangan.")
    w["history"][0].update(
        vendor=lots[0]["vendor"], carrier=lots[0]["selected_carrier"],
        carrier_quote={"product": p["name"], "quantity": c["planned_quantity"],
                       "deadline_days": c["deadline_days"], "orders": lots},
    )
    w["phase"] = "finance"
