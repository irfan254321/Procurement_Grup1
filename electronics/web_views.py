"""Company pages, static assets and public views of the simulation."""

from html import escape
from string import Template

from carrier_profiles import CARRIER_PROFILES
from paths import WEB
from supplier_profiles import SUPPLIER_PROFILES


COMPANY_NAMES = {
    "biz": "PT. Biz Indonesia Market",
    "cloudsoft": "CloudSoft Corp.",
    "furniworks": "FurniWorks Ltd.",
    "quickdeliver": "QuickDeliver Ltd.",
    "techmart": "TechMart Inc.",
    "jne": "JNE",
    "jt-cargo": "J&T Cargo",
    "pos-logistik": "Pos Logistik Indonesia",
}
COMPANY_PAGES = {f"/{slug}/": name for slug, name in COMPANY_NAMES.items()}
COMPANY_PROFILES = {**SUPPLIER_PROFILES, **CARRIER_PROFILES}

SCRIPTS = (
    "app.js", "format.js", "finance.js", "scenes.js", "interiors.js", "room-jobs.js",
    "company-dashboard.js", "biz-profile.js", "company-profile.js", "control-tower.js",
    "company-negotiations.js", "room-3d.mjs", "room-stage.mjs", "district-3d.mjs",
    "district-scenery.mjs", "studio.mjs", "poly-assets.mjs", "character-3d.mjs",
    "character-studio.mjs", "three/OrbitControls.js", "three/three.module.min.js",
    "three/three.core.min.js", "three/GLTFLoader.js", "three/BufferGeometryUtils.js",
    "three/SkeletonUtils.js",
)
STYLES = (
    "character-studio.css", "biz-profile.css", "biz-finance.css", "company-profile.css",
    "company-operations.css", "supplier-profiles.css", "carrier-profiles.css", "style.css",
    "scenes.css",
)
PROFILE_IMAGES = (
    "biz-warehouse", "profile-furniworks", "profile-techmart",
    "profile-jne", "profile-jt-cargo", "profile-pos-logistik",
)
MODEL_ASSETS = ("laptop", "monitor", "printer", "office", "sofa", "truck")
ASSETS = {
    "/": ("index.html", "text/html"),
    "/character-studio": ("character-studio.html", "text/html"),
    "/character-studio/": ("character-studio.html", "text/html"),
    **{f"/{name}": (name, "text/css") for name in STYLES},
    **{f"/{name}": (name, "text/javascript") for name in SCRIPTS},
    **{f"/assets/{name}.webp": (f"assets/{name}.webp", "image/webp") for name in PROFILE_IMAGES},
    **{f"/assets/{name}.glb": (f"assets/{name}.glb", "model/gltf-binary") for name in MODEL_ASSETS},
}

PRIVATE_WORLD_FIELDS = {
    "cash", "payroll", "operations", "reserve", "fund", "reserved", "sales", "cogs",
    "reinvested", "last_sale", "profit_report", "finance_series", "cash_flow", "tax",
}
PRIVATE_PURCHASE_FIELDS = {"free_cash", "available", "fund", "profit", "profit_per_unit", "revenue"}
CASE_FIELDS = ("product", "quantity", "offers", "orders", "restock", "planned_quantity", "deadline_days")
SELLER_CASE_FIELDS = ("id", "buy", "budget", "restocked")
FINANCE_DETAIL = "Rincian keuangan tersedia di portal BIZ."
NEGOTIATION_DETAIL = "Rincian tersimpan di riwayat negosiasi pada portal perusahaan."


def company_profile(slug):
    name = escape(COMPANY_NAMES[slug])
    operations = Template((WEB / "company-operations.html").read_text(encoding="utf-8")).substitute(name=name)
    if slug == "biz":
        finance = (WEB / "biz-finance.html").read_text(encoding="utf-8")
        operations = operations.replace("<!-- biz-finance -->", finance)
        profile = (WEB / "biz-profile.html").read_text(encoding="utf-8")
        return profile.replace("<!-- company-operations -->", operations)

    operations = operations.replace("<!-- biz-finance -->", "")
    profile = COMPANY_PROFILES[slug]
    group = "supplier" if slug in SUPPLIER_PROFILES else "carrier"
    font_query = profile.get("font_query")
    font_link = ""
    if font_query:
        font_link = f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{escape(font_query)}">'
    return Template((WEB / "company-profile.html").read_text(encoding="utf-8")).substitute(
        slug=slug,
        name=name,
        description=escape(profile["description"]),
        font_link=font_link,
        stylesheet=f"/{group}-profiles.css",
        content=profile["body"],
        operations=operations,
    )


def _has_finance_detail(role, detail):
    return role in {"finance", "seller"} or "Dana tersedia Rp" in detail


def _public_purchase(purchase):
    return {key: value for key, value in purchase.items() if key not in PRIVATE_PURCHASE_FIELDS}


def _public_event(event, *, live):
    if _has_finance_detail(event.get("role"), event.get("detail", "")):
        event = {key: value for key, value in event.items() if key not in {"detail", "features"}}
        event["detail"] = FINANCE_DETAIL
    if live or not (event.get("meeting") or event.get("carrier_quote")):
        return event

    visible = {key: value for key, value in event.items()
               if key not in {"features", "carrier_quote", "detail", "prediction"}}
    if meeting := event.get("meeting"):
        decision = {key: value for key, value in meeting["event"].items() if key in {"speaker", "action"}}
        visible["meeting"] = {**meeting, "event": decision}
    visible["detail"] = NEGOTIATION_DETAIL
    return visible


def _public_case(case, phase):
    fields = CASE_FIELDS + SELLER_CASE_FIELDS if phase == "seller" else CASE_FIELDS
    visible = {key: case[key] for key in fields if key in case}
    if "offers" in visible:
        visible["offers"] = [{"vendor": offer["vendor"], "accepted": offer["accepted"]}
                             for offer in case["offers"]]
    return visible


def public_world(world):
    """Expose live activity while keeping financial and archived negotiation details private."""
    result = {key: value for key, value in world.items() if key not in PRIVATE_WORLD_FIELDS}
    result["tax"] = {"rate": world["tax"]["rate"]}
    result["products"] = [{key: value for key, value in product.items() if key != "cost"}
                          for product in world["products"]]
    result["restock_holds"] = {name: {"quantity": hold["quantity"]}
                               for name, hold in world.get("restock_holds", {}).items()}
    if purchase := world.get("last_purchase"):
        result["last_purchase"] = _public_purchase(purchase)
    result["purchase_orders"] = [_public_purchase(purchase) for purchase in world.get("purchase_orders", [])]
    result["history"] = [_public_event(event, live=index == 0) for index, event in enumerate(world["history"])]
    if case := world.get("case"):
        result["case"] = _public_case(case, world["phase"])
    return result


def public_memory(rows):
    visible = []
    for row in rows:
        role = row["role"]
        entry = dict(row)
        if role == "finance":
            entry["facts"] = {key: value for key, value in row["facts"].items()
                              if key not in {"cash", "restock_fund", "reserved"}}
        if _has_finance_detail(role, row["reason"]):
            entry["reason"] = FINANCE_DETAIL
        visible.append(entry)
    return visible
