"""Business phases owned by the finance agent."""

from domain import MIN_MARKUP
from finance import vat, free_cash
from supply_chain import active_order, activate_order, summarize_purchase
from .base import hold_restock, record_receipt, restock_funds, rupiah


def finance(ctx, w, c, p, q, rng, mode, opening):
    if not c.get("orders"):
        # A saved pre-upgrade quote can still complete without inventing freight.
        goods = round(c["agreed"] * c["restock"], 2)
        c["orders"] = [{"vendor": c["vendor"], "quantity": c["restock"],
                         "unit_cost": c["agreed"], "goods_cost": goods,
                         "freight": 0, "cost": goods, "vat": vat(goods),
                         "invoice": round(goods + vat(goods), 4), "lead_days": 1,
                         "route": {"name":"Penawaran tersimpan", "path":[c["vendor"],"Gudang BIZ"]}}]
    quantity = c.get("planned_quantity", c["restock"])
    cost = c["total"] = round(sum(order["cost"] for order in c["orders"]), 4)
    cash_free = free_cash(w)
    invoice = round(sum(order["invoice"] for order in c["orders"]), 4)
    available = restock_funds(w)
    revenue = round(p["retail"]*quantity,2)
    features = [cost,available,revenue]
    profit = round(revenue-cost,2)
    enough_cash = invoice <= cash_free - w["reserved"]
    enough_fund = invoice <= w["fund"]
    enough_profit = revenue >= round(cost*MIN_MARKUP,2)
    approved = enough_cash and enough_fund and enough_profit
    reasons = []
    if not enough_cash:
        reasons.append(f"Kas kurang {rupiah(invoice-cash_free+w['reserved'])} setelah kewajiban.")
    if not enough_fund:
        reasons.append(f"Anggaran kurang {rupiah(invoice-w['fund'])}.")
    if not enough_profit:
        reasons.append("Proyeksi laba kotor di bawah target 15% dari biaya beli.")
    model_agrees = ctx.predict("finance", features) == approved
    if not model_agrees:
        reasons.append("Prediksi model berbeda. Keputusan memakai perhitungan kas, anggaran, dan margin.")
    w["last_purchase"] = {"product":p["name"],"vendor":c["vendor"],"quantity":quantity,
                          "unit_cost":c["agreed"],"retail":p["retail"],"cost":cost,
                          "revenue":revenue,"profit":profit,"available":available,"vat":vat(cost),"invoice":invoice,
                          "free_cash":cash_free,"fund":w["fund"],
                          "profit_per_unit":round(p["retail"]-c["agreed"],2),
                          "status":"Dana dicadangkan" if approved else "Ditahan"}
    detail = (f"{len(c['orders'])} pesanan pemasok · {quantity} unit · biaya barang dan ongkir {rupiah(cost)}. "
              f"Harga jual {rupiah(p['retail'])}/unit · omzet jika semua laku {rupiah(revenue)} · laba kotor proyeksi {rupiah(profit)}. ")
    ctx.record(w,"finance","Pembelian disetujui" if approved else "Pembelian ditahan",
           detail + " ".join(reasons),vector=features)
    if approved:
        w["purchase_count"] += 1
        batch_id = f"PO-{w['purchase_count']:05d}"
        c.update(batch_id=batch_id, planned_quantity=quantity)
        for index, order in enumerate(c["orders"]):
            order.update(id=f"{batch_id}-{index+1}", product=p["name"],
                         invoice_original=order["invoice"], dispatch_day=w["day"],
                         arrival_day=w["day"] + order["lead_days"],
                         deadline_day=w["day"] + c.get("deadline_days", 12), status="reserved")
            supplier = w["suppliers"][order["vendor"]]
            supplier["stock"][p["name"]] -= order["quantity"]
            supplier["capacity_remaining"] -= order["quantity"]
        c["orders"].sort(key=lambda order: (order["arrival_day"], order["id"]))
        w["last_purchase"].update(batch_id=batch_id, orders=c["orders"])
        w["reserved"] = round(w["reserved"] + invoice, 4)
        w["fund"] = round(w["fund"]-invoice,4)
        activate_order(c, c["orders"][0])
        summarize_purchase(w)
    elif not enough_cash or not enough_fund:
        hold_restock(w, p["name"], quantity, invoice, c.get("deadline_days", 12))
    else:
        p["retry_after"] = w["tick"]+18
    w["phase"] = "packing" if approved else "buyer"


def invoice_check(ctx, w, c, p, q, rng, mode, opening):
    accepted = c["received_quantity"]
    invoice = c.get("invoice", c["invoice_original"])
    if c["invoice_quantity"] != accepted or invoice != c["expected_invoice"]:
        order = active_order(w)
        if order:
            order["status"] = "invoice_hold"
            summarize_purchase(w)
        elif w.get("last_purchase"):
            w["last_purchase"].update(status="Pembayaran ditahan · menunggu koreksi faktur",
                                      invoice_original=c["invoice_original"])
        record_receipt(ctx, w, "finance", "Faktur ditahan",
                       f"Tagihan {c['invoice_quantity']} unit senilai {rupiah(invoice)}. Hasil pemeriksaan "
                       f"gudang dan harga pesanan hanya mendukung {accepted} unit senilai "
                       f"{rupiah(c['expected_invoice'])}. Keuangan meminta faktur pengganti.", "invoice_hold")
        w["phase"] = "invoice_correction"
        return
    w["fund"] = round(w["fund"] + c["invoice_original"] - invoice, 4)
    cost = c["accepted_cost"]
    w["tax"]["input_vat"] = round(w["tax"]["input_vat"] + invoice - cost, 4)
    w["cash"] = round(w["cash"] - invoice, 4)
    w["reserved"] = round(w["reserved"] - c["invoice_original"], 4)
    order = active_order(w)
    if order:
        order.update(status="paid", paid_invoice=invoice, paid_day=w["day"])
        summarize_purchase(w)
    elif w.get("last_purchase"):
        w["last_purchase"]["status"] = "Faktur dibayar · stok diterima"
    record_receipt(ctx, w, "finance", "Faktur dibayar",
                   f"Pesanan, hasil pemeriksaan gudang, dan faktur cocok untuk {accepted} unit yang dapat "
                   f"ditagihkan. Keuangan membayar {rupiah(invoice)} kepada {c['vendor']}.", "paid")
    pending = [candidate for candidate in c.get("orders", []) if candidate["status"] != "paid"]
    if pending:
        activate_order(c, pending[0])
        w["phase"] = "receive"
    else:
        if c.get("orders"):
            w["purchase_orders"] = [*w.get("purchase_orders", [])[-49:], w["last_purchase"]]
        w["phase"] = "buyer"
