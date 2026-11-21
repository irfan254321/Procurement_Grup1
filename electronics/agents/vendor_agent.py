"""Business phases owned by the vendor agent."""

from supply_chain import active_order, summarize_purchase
from .base import NEGOTIATION_ROUNDS, OFFER_FLOOR_MULTIPLIER, OFFER_OPENING_MULTIPLIER, meeting, record_receipt, rupiah, shipment_snapshot


def vendor_open(ctx, w, c, p, q, rng, mode, opening):
    v = c["candidates"][c["vendor_index"]]
    if v["capacity"] <= 0:
        c["offers"].append({"vendor":v["name"],"price":v["price"],"capacity":0,"accepted":False,"routes":[]})
        ctx.record(w,"vendor","Kapasitas vendor habis",f"{v['name']} belum memiliki stok/kapasitas untuk {p['name']}.")
        w["history"][0]["vendor"] = v["name"]
        c["vendor_index"] += 1
        w["phase"] = "vendor_open" if c["vendor_index"] < len(c["candidates"]) else "compare"
        return
    c.update(vendor=v["name"], ask=round(v["price"] * OFFER_OPENING_MULTIPLIER, 2),
             floor=round(v["price"] * OFFER_FLOOR_MULTIPLIER, 2), cap=v["capacity"], round=0,
             quote_quantity=min(c["restock"], v["capacity"]))
    c.pop("agreed", None)
    ctx.record(w, "vendor", "Harga pembuka",
           f"{c['vendor']} menawarkan {rupiah(c['ask'])} per unit; tersedia hingga {c['quote_quantity']} unit dari kebutuhan {c['restock']}.",
           vector=[c["ask"], c["floor"], c["quote_quantity"], c["cap"]])
    meeting(w, "vendor", "opening", c["ask"])
    w["phase"] = "counter"


def vendor_reply(ctx, w, c, p, q, rng, mode, opening):
    price = c["counter"]
    accept = ctx.record(w, "vendor", f"Putaran {c['round']} · jawaban vendor",
                    f"{c['vendor']} meninjau {rupiah(price)} per unit.",
                    vector=[price, c["floor"], c.get("quote_quantity", c["restock"]), c["cap"]])
    if price >= c["floor"] and c.get("quote_quantity", c["restock"]) <= c["cap"] and accept:
        c["agreed"] = price
        w["history"][0]["detail"] += " Vendor menerima tawaran."
        meeting(w, "vendor", "accept", price)
        w["phase"] = "vendor_result"
    else:
        c["ask"] = round(max(c["floor"], (c["ask"]+max(price,c["floor"]))/2),2)
        w["history"][0]["detail"] += f" Vendor menawarkan balik {rupiah(c['ask'])}."
        meeting(w, "vendor", "counter", c["ask"])
        w["phase"] = "counter" if c["round"] < NEGOTIATION_ROUNDS else "vendor_result"


def packing(ctx, w, c, p, q, rng, mode, opening):
    for order in c.get("orders", []):
        order["status"] = "packing"
    ctx.record(w, "vendor", "Pesanan disiapkan", f"Pemasok mengemas {c.get('planned_quantity',c['restock'])} × {p['name']} dalam {len(c.get('orders',[])) or 1} kiriman.")
    w["history"][0].update(shipment="packing", vendor=c["vendor"], shipments=shipment_snapshot(c))
    w["phase"] = "shipping"


def shipping(ctx, w, c, p, q, rng, mode, opening):
    for order in c.get("orders", []):
        order["status"] = "shipping"
    ctx.record(w,"vendor","Barang dalam perjalanan",f"{len(c.get('orders',[])) or 1} kiriman pemasok menuju Gudang BIZ; diterima menurut urutan ETA simulasi.")
    w["history"][0].update(shipment="shipping", vendor=c["vendor"], shipments=shipment_snapshot(c))
    w["phase"] = "receive"


def invoice_correction(ctx, w, c, p, q, rng, mode, opening):
    accepted = c["received_quantity"]
    cost = c["accepted_cost"]
    c.update(invoice_quantity=accepted, invoice=c["expected_invoice"])
    purchase = w.get("last_purchase")
    order = active_order(w)
    if order:
        order.update(cost=cost, goods_cost=round(c["agreed"] * accepted, 2),
                     vat=round(c["invoice"] - cost, 4), invoice=c["invoice"], status="corrected")
        summarize_purchase(w)
    elif purchase:
        revenue = round(p["retail"] * accepted, 2)
        purchase.update(cost=cost, vat=round(c["invoice"] - cost, 4), invoice=c["invoice"], revenue=revenue,
                        profit=round(revenue - cost, 2), status="Faktur dikoreksi · menunggu pembayaran")
    record_receipt(ctx, w, "vendor", "Faktur dikoreksi",
                   f"{c['vendor']} menerbitkan faktur pengganti senilai {rupiah(c['invoice'])} "
                   f"untuk {accepted} unit yang lolos pemeriksaan.", "invoice_corrected")
    w["phase"] = "invoice_check"
