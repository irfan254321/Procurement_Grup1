"""Run a single business phase under the orchestrator's turn context."""

from random import Random

from finance import initialize_finance, record_cash_flow, record_trade_result
from supply_chain import refresh_supply
from . import buyer_agent, seller_agent, stock_agent, procurement_agent, vendor_agent, deal_agent, finance_agent
from .base import DecisionContext, customer_state
from .availability import held_partner


PHASES = {
    "buyer": ("buyer", buyer_agent.buyer),
    "seller": ("seller", seller_agent.seller),
    "stock": ("stock", stock_agent.stock),
    "receive": ("stock", stock_agent.receive),
    "procurement": ("procurement", procurement_agent.procurement),
    "compare": ("procurement", procurement_agent.compare),
    "carrier_quote": ("procurement", procurement_agent.carrier_quote),
    "vendor_open": ("vendor", vendor_agent.vendor_open),
    "vendor_reply": ("vendor", vendor_agent.vendor_reply),
    "packing": ("vendor", vendor_agent.packing),
    "shipping": ("vendor", vendor_agent.shipping),
    "invoice_correction": ("vendor", vendor_agent.invoice_correction),
    "counter": ("deal", deal_agent.counter),
    "vendor_result": ("deal", deal_agent.vendor_result),
    "finance": ("finance", finance_agent.finance),
    "invoice_check": ("finance", finance_agent.invoice_check),
}


def run_turn(w, mode, *, predict, model_name, migrate, memory=None):
    initialize_finance(w)
    previous_sales, previous_cogs, previous_cash = w["sales"], w["cogs"], w["cash"]
    customer_state(w)
    migrate(w)
    case, purchase = w.get("case") or {}, w.get("last_purchase") or {}
    if case.get("batch_id") and case["batch_id"] == purchase.get("batch_id"):
        case["orders"] = purchase["orders"]
    w["tick"] += 1
    refresh_supply(w)
    rng = Random(9821 + w["tick"])
    mode = w.get("mode", mode)
    opening = w.get("opening", mode)
    phase = w["phase"]
    case = w["case"]
    if phase=="deal" or phase in ("vendor_open", "counter", "vendor_reply", "vendor_result", "compare") and not (case or {}).get("planned_quantity"):
        phase = "procurement"
    role, execute = PHASES[phase]
    product = next((p for p in w["products"] if p["name"] == (case or {}).get("product")), None)
    quantity = (case or {}).get("quantity", 0)
    roles = [role, "orchestrator"]
    recalled = {}
    if memory:
        for owner in roles:
            previous = memory.recall(owner, limit=1)
            if previous:
                recalled[owner] = previous[0]
    context = DecisionContext(predict, model_name, recalled)
    partner = held_partner(w, phase, case)
    if partner:
        context.record(w, role, "Menunggu perusahaan online", f"{partner} sedang tutup. PO tetap dicadangkan.")
        w["history"][0]["offline_hold"] = partner
        w["day"] += 1
        if phase in {"packing","shipping"}:
            for order in case.get("orders", []):
                if "arrival_day" in order:
                    order.setdefault("promised_day",order["arrival_day"])
                    order["arrival_day"] += 1
                    order["dispatch_day"] = w["day"]
    else:
        execute(context, w, case, product, quantity, rng, mode, opening)
    record_trade_result(w, previous_sales, previous_cogs)
    cash_movement = "customer_receipts" if w["cash"] > previous_cash else "supplier_payments" if w["cash"] < previous_cash else None
    record_cash_flow(w, previous_cash, cash_movement)
    if memory:
        event = w["history"][0] if w["history"] and w["history"][0]["tick"] == w["tick"] else {}
        reason = ("Tawaran dinilai dari aturan harga dan kapasitas; rincian ada di portal perusahaan." if event.get("meeting") else
                  "Opsi dibandingkan pada ongkir, kapasitas, ETA, dan tenggat." if event.get("carrier_quote") else
                  event.get("detail") or f"Transisi {phase} → {w['phase']} dari state terverifikasi.")
        for owner in roles:
            facts = {"day": w["day"], "stock_units": product["units"] if product else None,
                     "requested_units": quantity, "queue_size": len(w["queue"]),
                     "online_suppliers": sum(w.get("company_availability",{}).get(v,True) for v in w["suppliers"]),
                     "next_phase": w["phase"]}
            if owner=="finance":
                facts.update(cash=w["cash"],restock_fund=w["fund"],reserved=w["reserved"])
            previous = recalled.get(owner)
            if previous:
                facts["prior_tick"] = previous["tick"]
                if product and previous["subject"] == product["name"]:
                    old_stock = previous["facts"].get("stock_units")
                    if old_stock is not None:
                        facts["stock_delta"] = product["units"] - old_stock
            memory.remember(owner,w["tick"],w["day"],product["name"] if product else "Distrik",facts,
                            event.get("title",w["phase"]),reason)
