"""Business phases owned by the deal agent."""

from supply_chain import quote_routes
from .base import meeting, rupiah


def counter(ctx, w, c, p, q, rng, mode, opening):
    c["round"] += 1
    c["counter"] = round(min(c["ceiling"],c["ask"]*(.86+.045*c["round"])),2)
    ctx.record(w, "deal", f"Putaran {c['round']} · tawar balik",
           f"PT. Biz Indonesia Market menawarkan {rupiah(c['counter'])} per unit kepada {c['vendor']}.",
           vector=[c["counter"], c["ceiling"], c["floor"]])
    meeting(w, "buyer", "counter", c["counter"])
    w["phase"] = "vendor_reply"


def vendor_result(ctx, w, c, p, q, rng, mode, opening):
    price = c.get("agreed", c["ask"])
    accepted = "agreed" in c and ctx.predict("deal", [price, c["ceiling"], c["floor"]])
    routes = quote_routes(w, c["vendor"], c.get("quote_quantity", c["restock"]), price) if accepted else []
    c["offers"].append({"vendor":c["vendor"], "price":price, "accepted":accepted,
                        "capacity":c["cap"], "routes":routes})
    ctx.record(w, "deal", "Vendor sepakat" if accepted else "Negosiasi vendor berakhir",
           f"{c['vendor']} · {rupiah(price)} per unit. " + ("Masuk daftar penawaran final." if accepted else "Tidak tercapai kesepakatan."),
           vector=[price,c["ceiling"],c["floor"]])
    meeting(w, "buyer", "accept" if accepted else "reject", price)
    c["vendor_index"] += 1
    w["phase"] = "vendor_open" if c["vendor_index"] < len(c["candidates"]) else "compare"
