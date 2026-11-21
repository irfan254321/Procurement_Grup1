"""Business phases owned by the seller agent."""

from finance import vat
from .analytics import observe_demand
from .base import refresh_restock_holds, rupiah


def seller(ctx, w, c, p, q, rng, mode, opening):
    features = [p["units"],q,p["retail"]]
    can_sell = ctx.predict("seller",features)
    total_to_customer = round(q*p["retail"], 2)
    total_to_customer += vat(total_to_customer)
    wants_to_buy = c["buy"] and round(c.get("budget", total_to_customer) * q, 4) >= round(total_to_customer, 4)
    sold = q if wants_to_buy and p["units"] >= q and can_sell else 0
    stock_shortage = wants_to_buy and p["units"] < q
    if sold or stock_shortage:
        observe_demand(p, w["day"], q)
    customer = "Pelanggan "+str(c["id"]) if "id" in c else "Pelanggan"
    if sold:
        title, status = "Penjualan berhasil", "Terlayani"
    elif stock_shortage:
        title, status = ("STOK KOSONG", "Stok kosong") if not p["units"] else ("Stok tidak cukup", "Stok tidak cukup")
        c["stock_shortage"] = True
    elif not wants_to_buy:
        title, status = "Pelanggan batal", "Tidak jadi beli"
    else:
        title, status = "Penjual menunda pesanan", "Tidak dilayani"
    if "id" in c:
        previous_results = [result for result in w["customer_results"] if result["id"] != c["id"]]
        w["customer_results"] = [{"id":c["id"],"product":p["name"],"status":status},
                                 *previous_results[:19]]
    ctx.record(w,"seller",title,
           f"{customer} · {p['name']} · pesan {q} · tersedia {p['units']} · {status}.",
           vector=features)
    if stock_shortage:
        w["history"][0]["detail"] += " Transaksi ditutup."
    if "id" in c:
        w["history"][0]["customer"] = dict(c)
    if sold:
        revenue = round(sold*p["retail"], 2)
        cost = round(sold*p["cost"], 2)
        sale = {"customer":c.get("id"), "product":p["name"], "quantity":sold, "retail":p["retail"], "unit_cost":p["cost"],
                "revenue":revenue, "cost":cost, "profit":round(revenue-cost,2)}
        sale["vat"] = vat(revenue)
        sale["total"] = round(revenue + sale["vat"], 4)
        sale["reinvested"] = round(max(0, sale["profit"]) * .5, 4)
        working_capital = min(revenue, cost)
        w["fund"] = round(w["fund"] + working_capital + sale["reinvested"], 4)
        w["reinvested"] = round(w["reinvested"] + sale["reinvested"], 4)
        w["tax"]["output_vat"] = round(w["tax"]["output_vat"] + sale["vat"], 4)
        w["last_sale"] = sale
        w["history"][0]["detail"] += (
            f" Total pelanggan {rupiah(sale['total'])} termasuk PPN {rupiah(sale['vat'])} · Omzet {rupiah(revenue)} · HPP {rupiah(cost)} · laba kotor {rupiah(sale['profit'])}."
            f" Modal {rupiah(working_capital)} dan laba {rupiah(sale['reinvested'])} dialokasikan ke dana restok."
        )
        p["units"] -= sold
        w["cash"] = round(w["cash"]+sale["total"],4)
        w["sales"] = round(w["sales"]+sold*p["retail"],2)
        w["cogs"] = round(w["cogs"]+sold*p["cost"],2)
        refresh_restock_holds(w)
        c["quantity"] = 0
    w["phase"] = "stock"
