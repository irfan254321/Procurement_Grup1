import json
import re
import sqlite3
from contextlib import closing
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from random import Random, SystemRandom
from urllib.parse import urlsplit

from finance import VAT_RATE, apply_tax_action, free_cash, initialize_finance, track_finance, vat
from domain import AGENTS, DATA, FEATURES, MIN_MARKUP, ROOT, load_models, make_catalog, read_purchases
from supplier_data import load_supplier_models
from supply_chain import (SUPPLIER_REPLENISH_TICKS, init_supply, refresh_supply, quote_routes,
                          allocate_orders, activate_order, active_order, summarize_purchase,
                          carrier_catalog, supplier_freight_catalog)

CATALOG = make_catalog(read_purchases())
trained = load_models()
if trained is None:
    raise SystemExit("Model perlu disiapkan ulang. Jalankan installer BIZ District.")
REPORT, MODELS = trained
supplier_bundle = load_supplier_models()
if supplier_bundle is None:
    raise SystemExit("Model pemasok belum tersedia. Jalankan installer BIZ District.")
SUPPLIER_REPORT = supplier_bundle["report"]
DB = DATA / "electronics.sqlite3"
OPENINGS = ("healthy", "normal", "stock", "cash", "damage", "supply")
SCENARIOS = ("auto", *OPENINGS)
RESTOCK_THRESHOLD = 3
NEGOTIATION_ROUNDS = 3
OFFER_OPENING_MULTIPLIER = 1.10
OFFER_FLOOR_MULTIPLIER = .90
COMPANY_NAMES = {
    "biz": "PT. Biz Indonesia Market",
    "cloudsoft": "CloudSoft Corp.",
    "furniworks": "FurniWorks Ltd.",
    "officesupplies": "OfficeSupplies Co.",
    "quickdeliver": "QuickDeliver Ltd.",
    "techmart": "TechMart Inc.",
    "jne": "JNE",
    "jt-cargo": "J&T Cargo",
    "pos-logistik": "Pos Logistik Indonesia",
}
COMPANY_PAGES = {f"/{slug}/": name for slug, name in COMPANY_NAMES.items()}
COMPANY_POLICY = {
    "restock_threshold": RESTOCK_THRESHOLD,
    "supplier_replenish_ticks": SUPPLIER_REPLENISH_TICKS,
    "negotiation_rounds": NEGOTIATION_ROUNDS,
    "offer_opening_multiplier": OFFER_OPENING_MULTIPLIER,
    "offer_floor_multiplier": OFFER_FLOOR_MULTIPLIER,
    "min_markup": round(MIN_MARKUP - 1, 4),
    "vat_rate": VAT_RATE,
    "freight_tax_note": "Ongkir sebelum PPN. Faktur mengenakan PPN simulasi pada biaya barang dan ongkir.",
    "carrier_simulation_note": "Tarif, kapasitas dan waktu tempuh berasal dari skenario simulasi. Kapasitas berlaku per kiriman.",
    "carriers": carrier_catalog(),
    "suppliers": supplier_freight_catalog(CATALOG),
    "pages": {name: path for path, name in COMPANY_PAGES.items()},
}


def rupiah(value):
    return "Rp" + f"{value * 10_000:,.0f}".replace(",", ".")



def connect():
    return closing(sqlite3.connect(DB, timeout=10))


def initialize():
    with connect() as db, db:
        db.execute("DROP TABLE IF EXISTS purchases")
        db.execute("CREATE TABLE IF NOT EXISTS world (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT)")
        db.execute("INSERT OR IGNORE INTO world VALUES (1,?)", (json.dumps(new_world()),))


def new_world(mode="auto", *, rng=None):
    opening = (rng or SystemRandom()).choice(OPENINGS) if mode == "auto" else mode
    healthy = opening == "healthy"
    cash_multiplier = {"healthy": 250, "supply": 250, "cash": 16}.get(opening, 50)
    cash = round(sum(item["reference"] for item in CATALOG) * cash_multiplier, 2)
    world = {"tick": 0, "cash": cash, "payroll": round(cash*.20,2), "operations": round(cash*.10,2),
            "reserve": round(cash*.10,2), "fund": round(cash*.45,2), "sales": 0, "reinvested": 0,
            "cogs": 0, "reserved": 0, "mode": mode, "opening": opening, "last_sale": None, "last_purchase": None,
            "products": [{**item, "units": [19,24,30][i] if healthy else [0,8,6][i], "cost": item["reference"],
                                        "retail": round(item["reference"]*1.55,2)}
                                       for i,item in enumerate(CATALOG)],
            "scene": "stock", "phase": "buyer", "case": None, "history": [],
            "queue": [], "restock_requests": {}, "restock_holds": {}, "customer_count": 0,
            "customer_results": []}
    init_supply(world, CATALOG)
    if opening == "supply":
        world["restock_requests"][CATALOG[0]["name"]] = {
            "product": CATALOG[0]["name"], "quantity": 0, "buy": False,
            "demand": 30, "deadline_days": 4,
        }
    return world


def load_world(db):
    world = json.loads(db.execute("SELECT state FROM world WHERE id=1").fetchone()[0])
    customer_state(world)
    initialize_finance(world)
    init_supply(world, CATALOG)
    # JSON stores equal objects independently. Reconnect the active batch by ID.
    case, purchase = world.get("case") or {}, world.get("last_purchase") or {}
    if case.get("batch_id") and case["batch_id"] == purchase.get("batch_id"):
        case["orders"] = purchase["orders"]
    for event in world["history"] if "supplier_history_format" not in world else []:
        for target, key in [(event, "detail"), (event.get("meeting", {}).get("event", {}), "reason")]:
            if key in target:
                message = target[key].replace("Â·", "·").replace("Ã—", "×").replace("â†’", "→")
                target[key] = re.sub(
                    r"(?<![\w.,])(-?\d+\.\d{2})(?![\d,])",
                    lambda match: rupiah(float(match[1])), message
                )
    world["supplier_history_format"] = 1
    return world



def predict(role, vector):
    main = REPORT["agents"][role]["main"]
    return bool(MODELS[role][main].predict([vector])[0])


def record(w, role, title, detail, *, vector=None):
    event = {"tick": w["tick"], "role": role, "title": title, "detail": detail}
    if vector is not None:
        main = REPORT["agents"][role]["main"]
        vote = predict(role, vector)
        event.update(model=main, prediction=AGENTS[role][2 if vote else 3],
                     features=dict(zip(FEATURES[role], vector)))
    w["scene"] = role
    w["history"] = [event, *w["history"][:79]]
    return event.get("prediction") == AGENTS[role][2]


def meeting(w, speaker, action, amount):
    c = w["case"]
    event = w["history"][0]
    event["meeting"] = {
        "vendor": c["vendor"], "round": c["round"],
        "vendorPosition": c["vendor_index"]+1, "vendorTotal": len(c["candidates"]),
        "event": {"speaker": speaker, "action": action, "amount": amount, "reason": event["detail"]},
    }


def record_receipt(w, role, title, detail, state):
    case = w["case"]
    order = active_order(w)
    carrier = (order or {}).get("route", {}).get("carrier")
    record(w, role, title, detail)
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


def arrive(w, rng, mode):
    products = w["products"]
    first = next((p for p in products if not p["units"]), products[0])
    queue = w["queue"]
    for index in range(rng.randint(2,4)):
        p = first if index == 0 and mode in ("stock","cash") else rng.choice(products)
        q = rng.randint(1,4)
        premium = 1.35 if mode in ("stock","cash") else rng.uniform(.94,1.32)
        budget = round(p["retail"]*premium,2)
        price_to_customer = p["retail"] + vat(p["retail"])
        prediction = predict("buyer", [price_to_customer,budget,q])
        w["customer_count"] += 1
        queue.append({"id":w["customer_count"],"product":p["name"],"quantity":q,"mode":mode,
                      "budget":budget,"prediction":prediction,"buy":budget>=price_to_customer and prediction})
    record(w,"buyer",f"{len(queue)} pelanggan datang",
           " · ".join(f"Pelanggan {c['id']} mencari {c['quantity']} × {c['product']}" for c in queue))
    w["history"][0]["customers"] = [dict(customer) for customer in queue]


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


def step(w, mode):
    initialize_finance(w)
    customer_state(w)
    init_supply(w, CATALOG)
    case, purchase = w.get("case") or {}, w.get("last_purchase") or {}
    if case.get("batch_id") and case["batch_id"] == purchase.get("batch_id"):
        purchase["orders"] = case["orders"]
    w["tick"] += 1
    refresh_supply(w)
    rng = Random(9821 + w["tick"])
    mode = w.get("mode", mode)
    opening = w.get("opening", mode)
    phase = w["phase"]
    c = w["case"]
    if phase in ("vendor_open", "counter", "vendor_reply", "vendor_result", "compare", "deal") and not (c or {}).get("planned_quantity"):
        # Requote pre-upgrade negotiations. Already committed orders keep their invoice.
        phase = "procurement"
    if phase == "buyer":
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
                record(w, "finance", "Dana restok tersedia",
                       f"{product} · Dana tersedia {rupiah(available)}. Pengadaan {hold['quantity']} unit dilanjutkan.")
                w["phase"] = "procurement"
                return
        if w["restock_requests"]:
            product = next(iter(w["restock_requests"]))
            w["case"] = w["restock_requests"].pop(product)
            w["phase"] = "procurement"
        else:
            w["day"] += 1
            arrive(w,rng,opening)
        return

    p = next(product for product in w["products"] if product["name"] == c["product"])
    q = c["quantity"]
    if phase == "seller":
        features = [p["units"],q,p["retail"]]
        can_sell = predict("seller",features)
        total_to_customer = round(q*p["retail"], 2)
        total_to_customer += vat(total_to_customer)
        wants_to_buy = c["buy"] and round(c.get("budget", total_to_customer) * q, 4) >= round(total_to_customer, 4)
        sold = q if wants_to_buy and p["units"] >= q and can_sell else 0
        stock_shortage = wants_to_buy and p["units"] < q
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
        record(w,"seller",title,
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
    elif phase == "stock":
        projected = (q if c.get("stock_shortage") else 0) + sum(
            order["quantity"] for order in w["queue"] if order["product"] == p["name"] and order["buy"])
        needs_order = record(w, "stock", "Periksa rak dan gudang",
                             f"{p['name']} · sisa {p['units']} unit, permintaan tercatat {projected}, titik pesan {RESTOCK_THRESHOLD}.",
                             vector=[p["units"], projected, RESTOCK_THRESHOLD])
        low_stock = p["units"] <= RESTOCK_THRESHOLD or c.get("stock_shortage") or (projected > 0 and needs_order)
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
    elif phase == "procurement":
        demand = c.get("demand", 0)
        c.setdefault("restock", min(40 if opening == "supply" else 14,
                                    max(6,12-p["units"],demand-p["units"])))
        c.setdefault("deadline_days", 12)
        candidates = [{**v, "capacity": min(w["suppliers"][v["name"]]["capacity_remaining"],
                                            w["suppliers"][v["name"]]["stock"][p["name"]], c["restock"])}
                      for v in p["vendors"]]
        def key(v):
            priority = predict("procurement", [v["price"], p["reference"], v["capacity"], min(c["restock"], v["capacity"])])
            return (not priority, v["price"], v["name"])
        c.update(candidates=sorted(candidates, key=key), vendor_index=0, offers=[],
                 ceiling=round(min(p["reference"]*1.08, p["retail"]/MIN_MARKUP), 2),
                 planned_quantity=c["restock"])
        v = c["candidates"][0]
        record(w, "procurement", "Permintaan penawaran",
               f"{c['restock']} × {p['name']} · {len(candidates)} vendor diundang.",
               vector=[v["price"], p["reference"], v["capacity"], min(c["restock"], v["capacity"])])
        w["phase"] = "vendor_open"
    elif phase == "vendor_open":
        v = c["candidates"][c["vendor_index"]]
        if v["capacity"] <= 0:
            c["offers"].append({"vendor":v["name"],"price":v["price"],"capacity":0,"accepted":False,"routes":[]})
            record(w,"vendor","Kapasitas vendor habis",f"{v['name']} belum memiliki stok/kapasitas untuk {p['name']}.")
            w["history"][0]["vendor"] = v["name"]
            c["vendor_index"] += 1
            w["phase"] = "vendor_open" if c["vendor_index"] < len(c["candidates"]) else "compare"
            return
        c.update(vendor=v["name"], ask=round(v["price"] * OFFER_OPENING_MULTIPLIER, 2),
                 floor=round(v["price"] * OFFER_FLOOR_MULTIPLIER, 2), cap=v["capacity"], round=0,
                 quote_quantity=min(c["restock"], v["capacity"]))
        c.pop("agreed", None)
        record(w, "vendor", "Harga pembuka",
               f"{c['vendor']} menawarkan {rupiah(c['ask'])} per unit; tersedia hingga {c['quote_quantity']} unit dari kebutuhan {c['restock']}.",
               vector=[c["ask"], c["floor"], c["quote_quantity"], c["cap"]])
        meeting(w, "vendor", "opening", c["ask"])
        w["phase"] = "counter"
    elif phase == "counter":
        c["round"] += 1
        c["counter"] = round(min(c["ceiling"],c["ask"]*(.86+.045*c["round"])),2)
        record(w, "deal", f"Putaran {c['round']} · tawar balik",
               f"PT. Biz Indonesia Market menawarkan {rupiah(c['counter'])} per unit kepada {c['vendor']}.",
               vector=[c["counter"], c["ceiling"], c["floor"]])
        meeting(w, "buyer", "counter", c["counter"])
        w["phase"] = "vendor_reply"
    elif phase == "vendor_reply":
        price = c["counter"]
        accept = record(w, "vendor", f"Putaran {c['round']} · jawaban vendor",
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
    elif phase == "vendor_result":
        price = c.get("agreed", c["ask"])
        accepted = "agreed" in c and predict("deal", [price, c["ceiling"], c["floor"]])
        routes = quote_routes(w, c["vendor"], c.get("quote_quantity", c["restock"]), price) if accepted else []
        c["offers"].append({"vendor":c["vendor"], "price":price, "accepted":accepted,
                            "capacity":c["cap"], "routes":routes})
        record(w, "deal", "Vendor sepakat" if accepted else "Negosiasi vendor berakhir",
               f"{c['vendor']} · {rupiah(price)} per unit. " + ("Masuk daftar penawaran final." if accepted else "Tidak tercapai kesepakatan."),
               vector=[price,c["ceiling"],c["floor"]])
        meeting(w, "buyer", "accept" if accepted else "reject", price)
        c["vendor_index"] += 1
        w["phase"] = "vendor_open" if c["vendor_index"] < len(c["candidates"]) else "compare"
    elif phase == "compare":
        c.setdefault("deadline_days", 12)
        quantity = c.get("planned_quantity", c["restock"])
        available = restock_funds(w)
        cost_limit = round(p["retail"] * quantity, 2) / MIN_MARKUP
        plan = allocate_orders(c["offers"], quantity, available, c["deadline_days"],
                               cost_limit=cost_limit)
        if plan:
            c.update(orders=plan, vendor=plan[0]["vendor"],
                     agreed=round(sum(order["goods_cost"] for order in plan)/quantity, 4))
            def route_label(order):
                route = order["route"]
                return " ".join(part for part in (route.get("carrier"), route["name"]) if part)

            record(w, "procurement", "Vendor terpilih",
                   " · ".join(f"{order['vendor']}: {order['quantity']} unit via {route_label(order)} ({order['lead_days']} hari simulasi)" for order in plan)
                   + f". Alokasi memenuhi {quantity} unit dengan biaya termasuk ongkir/PPN dan prior risiko; tenggat {c['deadline_days']} hari.")
            w["history"][0].update(vendor=plan[0]["vendor"], allocations=plan)
            w["phase"] = "finance"
        else:
            cheapest = allocate_orders(c["offers"], quantity, float("inf"), c["deadline_days"],
                                       risk_weight=0, cost_limit=cost_limit)
            if cheapest:
                required = round(sum(order["invoice"] for order in cheapest), 4)
                hold_restock(w, p["name"], quantity, required, c["deadline_days"])
                record(w, "finance", "Pembelian ditahan",
                       f"{p['name']} · {quantity} unit. Rencana termurah memerlukan {rupiah(required)} termasuk ongkir dan PPN. Dana tersedia {rupiah(available)}.")
            else:
                record(w, "procurement", "Tidak tercapai kesepakatan",
                       f"Tidak ada kombinasi lengkap {quantity} unit yang memenuhi kapasitas, tenggat, dan target laba. Restok ditunda 18 giliran.")
                p["retry_after"] = w["tick"]+18
            w["phase"] = "buyer"
    elif phase == "finance":
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
        model_agrees = predict("finance", features) == approved
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
        record(w,"finance","Pembelian disetujui" if approved else "Pembelian ditahan",
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
    elif phase == "packing":
        for order in c.get("orders", []):
            order["status"] = "packing"
        record(w, "vendor", "Pesanan disiapkan", f"Pemasok mengemas {c.get('planned_quantity',c['restock'])} × {p['name']} dalam {len(c.get('orders',[])) or 1} kiriman.")
        w["history"][0].update(shipment="packing", vendor=c["vendor"], shipments=shipment_snapshot(c))
        w["phase"] = "shipping"
    elif phase == "shipping":
        for order in c.get("orders", []):
            order["status"] = "shipping"
        record(w,"vendor","Barang dalam perjalanan",f"{len(c.get('orders',[])) or 1} kiriman pemasok menuju Gudang BIZ; diterima menurut urutan ETA simulasi.")
        w["history"][0].update(shipment="shipping", vendor=c["vendor"], shipments=shipment_snapshot(c))
        w["phase"] = "receive"
    elif phase == "receive":
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
                         status="inspected", expected_invoice=expected_invoice)
            summarize_purchase(w)
        elif purchase:
            purchase.update(received_quantity=accepted, damaged_quantity=damaged,
                            status="Menunggu pemeriksaan faktur")
            if damaged:
                purchase["invoice_original"] = c["invoice_original"]
        detail = f"{p['name']} dari {c['vendor']} · {c['restock']} unit diperiksa, {accepted} unit masuk stok jual."
        if damaged:
            detail += f" {damaged} unit rusak dipisahkan untuk retur."
        record_receipt(w, "stock", "Pemeriksaan barang", detail, "inspected")
        w["history"][0]["shipment"] = "delivered"
        w["phase"] = "invoice_check"
    elif phase == "invoice_correction":
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
        record_receipt(w, "vendor", "Faktur dikoreksi",
                       f"{c['vendor']} menerbitkan faktur pengganti senilai {rupiah(c['invoice'])} "
                       f"untuk {accepted} unit yang lolos pemeriksaan.", "invoice_corrected")
        w["phase"] = "invoice_check"
    elif phase == "invoice_check":
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
            record_receipt(w, "finance", "Faktur ditahan",
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
        record_receipt(w, "finance", "Faktur dibayar",
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


class Handler(BaseHTTPRequestHandler):
    def send_data(self, body, mime="application/json", status=200):
        if mime == "application/json":
            body = json.dumps(body,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",mime+"; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        scripts = (
            "app.js", "format.js", "company-page.js", "finance.js", "scenes.js", "interiors.js",
            "room-jobs.js", "company-dashboard.js",
            "room-3d.mjs", "room-stage.mjs", "district-3d.mjs", "studio.mjs", "poly-assets.mjs",
            "three/three.module.min.js", "three/three.core.min.js", "three/GLTFLoader.js",
            "three/BufferGeometryUtils.js", "three/SkeletonUtils.js",
        )
        assets = {
            "/": ("index.html", "text/html"),
            "/style.css": ("style.css", "text/css"),
            "/scenes.css": ("scenes.css", "text/css"),
            **{"/" + name: (name, "text/javascript") for name in scripts},
            **{f"/assets/{name}.glb": (f"assets/{name}.glb", "model/gltf-binary")
               for name in ("laptop", "monitor", "printer", "office", "sofa", "truck")},
        }
        path = urlsplit(self.path).path
        company = COMPANY_PAGES.get(path.rstrip("/") + "/")
        if company is not None:
            markup = (ROOT / "web" / "company.html").read_text(encoding="utf-8")
            self.send_data(markup.replace("__COMPANY_NAME__", escape(company)).encode("utf-8"), "text/html")
        elif path in assets:
            name, mime = assets[path]
            content = (ROOT/"web"/name).read_bytes()
            self.send_data(content,mime)
        elif path == "/api/models":
            self.send_data({"roles": AGENTS, "benchmark": REPORT, "scenarios": SCENARIOS,
                            "supplier_model": SUPPLIER_REPORT, "company_policy": COMPANY_POLICY})
        elif path == "/api/world":
            with connect() as db:
                self.send_data(load_world(db))
        else:
            self.send_data({"error":"Halaman tidak tersedia."},status=404)

    def do_POST(self):
        modes = {f"/api/{verb}/{scenario}": scenario
                 for verb in ("step", "reset") for scenario in SCENARIOS}
        mode = modes.get(self.path) if self.path != "/api/reset" else "auto"
        action = {"/api/tax/assessment":"assessment", "/api/tax/pay":"pay"}.get(self.path)
        if mode is None and action is None:
            self.send_data({"error":"Aksi tidak tersedia."},status=404)
            return
        with connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            world = load_world(db)
            if action:
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if not 0 < length <= 4096:
                        raise ValueError("Data pajak tidak valid.")
                    apply_tax_action(world, action, json.loads(self.rfile.read(length)))
                except (ValueError, UnicodeError) as error:
                    self.send_data({"error":str(error)},status=400)
                    return
            elif self.path.startswith("/api/reset"):
                world = new_world(mode)
                initialize_finance(world)
            else:
                step(world,mode)
            refresh_restock_holds(world)
            track_finance(world)
            db.execute("UPDATE world SET state=? WHERE id=1",(json.dumps(world),))
        self.send_data(world)


if __name__ == "__main__":
    initialize()
    print("BIZ District tersedia di http://127.0.0.1:8081",flush=True)
    ThreadingHTTPServer(("127.0.0.1",8081),Handler).serve_forever()
