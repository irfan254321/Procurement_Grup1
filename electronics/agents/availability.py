def online(world, name):
    return world.get("company_availability", {}).get(name, True)


def change_availability(world, name, enabled):
    if online(world,name) == enabled:
        return
    world.setdefault("company_availability", {})[name] = enabled
    case = world.get("case") or {}
    phase = world["phase"]
    if not enabled and phase in {"procurement","vendor_open","counter","vendor_reply","vendor_result",
                                 "compare","carrier_quote","finance"}:
        # Restart only an uncommitted RFQ. An approved PO keeps its reservation.
        retained = ("product","quantity","buy","restock","demand","deadline_days","rfq_id","planning_day")
        world["case"] = {key: case[key] for key in retained if key in case}
        world["phase"] = "procurement"
    if enabled:
        for product in world["products"]:
            product.pop("retry_after", None)


def held_partner(world, phase, case):
    if phase == "invoice_correction":
        vendor = (case or {}).get("vendor")
        return vendor if not online(world, vendor) else None
    if phase not in {"packing","shipping"}:
        return None
    for order in (case or {}).get("orders", []):
        for name in (order["vendor"], order.get("route", {}).get("carrier")):
            if not online(world, name):
                return name
    return None
