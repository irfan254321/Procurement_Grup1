import json
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from random import SystemRandom
from urllib.parse import urlsplit

from agents.base import (NEGOTIATION_ROUNDS, OFFER_FLOOR_MULTIPLIER, OFFER_OPENING_MULTIPLIER,
                         RESTOCK_THRESHOLD, customer_state, refresh_restock_holds, rupiah)
from agents.orchestrator import run_turn
from agents.availability import change_availability
from database import company_access, operations, storage
from database.agent_memory import AgentMemory
from finance import (VAT_RATE, apply_tax_action, company_finance, initialize_finance,
                     record_operating_expense, track_finance)
from domain import AGENTS, MIN_MARKUP, RETIRED_SUPPLIER, load_models, make_catalog, read_purchases
from paths import WEB, WORLD_DATABASE
from supplier_data import load_supplier_models
from supply_chain import (SUPPLY_VERSION, SUPPLIER_REPLENISH_TICKS, active_order, init_supply,
                          carrier_catalog, supplier_freight_catalog)
from web_views import ASSETS, COMPANY_NAMES, COMPANY_PAGES, company_profile, public_memory, public_world

ARCHIVED_SUPPLIER = "Pemasok arsip"
CATALOG = make_catalog(read_purchases())
trained = load_models()
if trained is None:
    raise SystemExit("Model perlu disiapkan ulang. Jalankan installer BIZ District.")
REPORT, MODELS = trained
supplier_bundle = load_supplier_models()
if supplier_bundle is None:
    raise SystemExit("Model pemasok belum tersedia. Jalankan installer BIZ District.")
SUPPLIER_REPORT = supplier_bundle["report"]
DB = WORLD_DATABASE
OPENINGS = ("healthy", "normal", "stock", "cash", "damage", "supply")
SCENARIOS = ("auto", *OPENINGS)
SCENARIO_ENDPOINTS = {
    "/api/reset": ("reset", "auto"),
    **{f"/api/{action}/{scenario}": (action, scenario)
       for action in ("step", "reset") for scenario in SCENARIOS},
}
MAX_JSON_BODY_BYTES = 4096
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


def connect():
    return storage.connect(DB)


def initialize():
    with connect() as db, db:
        db.execute("BEGIN IMMEDIATE")
        storage.create_schema(db)
        saved = db.execute("SELECT state FROM world WHERE id=1").fetchone()
        if saved is None:
            storage.save_world(db, new_world())
        else:
            world = json.loads(saved[0])
            if migrate_supplier_catalog(world):
                storage.save_world(db, world)


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
            "customer_results": [], "company_availability": {}}
    init_supply(world, CATALOG)
    if opening == "supply":
        world["restock_requests"][CATALOG[0]["name"]] = {
            "product": CATALOG[0]["name"], "quantity": 0, "buy": False,
            "demand": 30, "deadline_days": 4,
        }
    initialize_finance(world)
    return world


def load_world(db):
    world = storage.read_world(db)
    customer_state(world)
    initialize_finance(world)
    migrate_supplier_catalog(world)
    world.setdefault("company_availability", {})
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


def migrate_supplier_catalog(world):
    case = world.get("case") or {}
    candidates = case.get("candidates", [])
    offers = case.get("offers", [])
    orders = case.get("orders", [])
    removed_vendor = case.get("vendor") == RETIRED_SUPPLIER
    removed_candidate = any(item.get("name") == RETIRED_SUPPLIER for item in candidates)
    removed_offer = any(item.get("vendor") == RETIRED_SUPPLIER for item in offers)
    removed_order = any(item.get("vendor") == RETIRED_SUPPLIER for item in orders)
    retired_in_catalog = any(v.get("name")==RETIRED_SUPPLIER for p in world["products"] for v in p["vendors"])
    retired_in_history = any(RETIRED_SUPPLIER in str(world.get(key)) for key in ("history","purchase_orders","last_purchase"))
    if world.get("supply_version") == SUPPLY_VERSION and not (
            removed_vendor or removed_candidate or removed_offer or removed_order or retired_in_catalog or retired_in_history
            or RETIRED_SUPPLIER in world.get("suppliers",{})):
        return False

    catalog = {product["name"]: product for product in CATALOG}
    for product in world["products"]:
        current = catalog.get(product["name"])
        if current:
            product.update(reference=current["reference"], vendors=current["vendors"])
        else:
            product["vendors"] = [item for item in product["vendors"] if item["name"] != RETIRED_SUPPLIER]

    # Keep reservations and invoice history. Only uncommitted plans can be requoted.
    phase = world["phase"]
    negotiating = phase in ("vendor_open", "counter", "vendor_reply", "vendor_result", "compare", "deal")
    if (negotiating and (removed_candidate or removed_offer or removed_vendor) or
            phase in ("carrier_quote", "finance") and (removed_vendor or removed_order)):
        world["case"] = {key: case[key] for key in
                         ("product", "quantity", "buy", "restock", "demand", "deadline_days") if key in case}
        world["phase"] = "procurement"
    elif case:
        if "candidates" in case:
            case["candidates"] = [item for item in case["candidates"] if item["name"] != RETIRED_SUPPLIER]
        if "offers" in case:
            case["offers"] = [item for item in case["offers"] if item["vendor"] != RETIRED_SUPPLIER]

    init_supply(world, CATALOG)
    world["suppliers"].pop(RETIRED_SUPPLIER,None)
    world.get("company_availability",{}).pop(RETIRED_SUPPLIER,None)
    archive_supplier_labels(world)
    return True


def archive_supplier_labels(value):
    if isinstance(value, str):
        return value.replace(RETIRED_SUPPLIER, ARCHIVED_SUPPLIER)
    if isinstance(value, dict):
        for key, item in value.items():
            value[key] = archive_supplier_labels(item)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = archive_supplier_labels(item)
    return value


def predict(role, vector):
    main = REPORT["agents"][role]["main"]
    return bool(MODELS[role][main].predict([vector])[0])


def step(w, mode, *, memory=None):
    run_turn(w, mode, predict=predict, model_name=lambda role: REPORT["agents"][role]["main"],
             migrate=migrate_supplier_catalog, memory=memory)


def _save_simulation(db, world):
    refresh_restock_holds(world)
    track_finance(world)
    storage.save_world(db, world)


def _company_endpoint(segments):
    if len(segments) == 4 and segments[:2] == ["api", "companies"] and segments[2] in COMPANY_NAMES:
        return segments[2], segments[3]
    return None


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
        path = urlsplit(self.path).path
        segments = path.strip("/").split("/")
        slug, *page = segments
        if slug in COMPANY_NAMES and (page in ([], ["dashboard"]) or (slug == "biz" and page == ["profil"])):
            self.send_data(company_profile(slug).encode("utf-8"), "text/html")
        elif path in ASSETS:
            name, mime = ASSETS[path]
            self.send_data((WEB / name).read_bytes(), mime)
        elif path == "/api/models":
            self.send_data({"roles": AGENTS, "benchmark": REPORT, "scenarios": SCENARIOS,
                            "supplier_model": SUPPLIER_REPORT, "company_policy": COMPANY_POLICY})
        elif path == "/api/world":
            with connect() as db:
                self.send_data(public_world(load_world(db)))
        elif path == "/api/memory" or path.startswith("/api/memory/"):
            role = path.removeprefix("/api/memory/") if path != "/api/memory" else None
            self.send_memory(role)
        elif path == "/api/control-tower":
            with connect() as db:
                self.send_data(operations.control_tower(db,load_world(db)))
        elif company := _company_endpoint(segments):
            self.send_company_data(*company)
        else:
            self.send_data({"error":"Halaman tidak tersedia."},status=404)

    def send_memory(self, role):
        if role is not None and role != "orchestrator" and role not in AGENTS:
            self.send_data({"error": "Agen tidak ditemukan."}, status=404)
            return
        with connect() as db:
            self.send_data({"memory": public_memory(AgentMemory(db).recall(role))})

    def send_company_data(self, slug, command):
        if command not in {"access", "negotiations"} and (slug, command) != ("biz", "finance"):
            self.send_data({"error": "Halaman tidak tersedia."}, status=404)
            return
        with connect() as db:
            if command == "access":
                self.send_data({"configured": company_access.configured(db, slug)})
            elif not company_access.authorized(db, slug, self.headers.get("Authorization", "")):
                self.send_data({"error": "Masuk dengan kata sandi perusahaan."}, status=401)
            elif command == "finance":
                self.send_data(company_finance(load_world(db)))
            else:
                name = COMPANY_NAMES[slug]
                self.send_data({
                    "negotiation_history": operations.logs(db, name),
                    "negotiation_schedule": operations.negotiation_schedule(db, name),
                    "delivery_schedule": operations.schedules(db, name),
                })

    def do_POST(self):
        segments = urlsplit(self.path).path.strip("/").split("/")
        if company := _company_endpoint(segments):
            self.company_action(*company)
            return
        if self.path not in SCENARIO_ENDPOINTS:
            self.send_data({"error": "Aksi tidak tersedia."}, status=404)
            return
        action, mode = SCENARIO_ENDPOINTS[self.path]
        with connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            world = load_world(db)
            if action == "reset":
                world = new_world(mode)
                storage.clear_scenario(db)
                operations.capacity_alerts(db, world)
            else:
                step(world, mode, memory=AgentMemory(db))
                operations.capture_turn(db, world)
            _save_simulation(db, world)
        self.send_data(public_world(world))

    def read_json_body(self, invalid_length):
        length = int(self.headers.get("Content-Length", 0))
        if not 0 < length <= MAX_JSON_BODY_BYTES:
            raise ValueError(invalid_length)
        return json.loads(self.rfile.read(length))

    def company_action(self, slug, command):
        if slug == "biz" and command == "finance":
            self.finance_action()
            return
        if command not in {"access","logout","availability"} or command=="availability" and slug=="biz":
            self.send_data({"error":"Aksi tidak tersedia."},status=404)
            return
        invalid_request = "Data permintaan tidak valid."
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError(invalid_request)
            data = self.read_json_body(invalid_request)
            if not isinstance(data, dict):
                raise ValueError(invalid_request)
        except ValueError:
            self.send_data({"error": invalid_request}, status=400)
            return
        with connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            if command == "access":
                status, body = company_access.exchange_password(db,slug,data.get("password"),setup=data.get("setup") is True)
            elif command == "logout":
                company_access.revoke(db,slug,self.headers.get("Authorization",""))
                status, body = 200, {"locked":True}
            elif type(data.get("online")) is bool:
                world = load_world(db)
                change_availability(world,COMPANY_NAMES[slug],data["online"])
                storage.save_world(db,world)
                status, body = 200, public_world(world)
            else:
                status, body = 400, {"error":"Status perusahaan harus online atau offline."}
        self.send_data(body,status=status)

    def finance_action(self):
        with connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not company_access.authorized(db, "biz", self.headers.get("Authorization", "")):
                self.send_data({"error": "Masuk dengan kata sandi perusahaan BIZ."}, status=401)
                return
            world = load_world(db)
            try:
                payload = self.read_json_body("Data keuangan tidak valid.")
                action = payload.get("action") if isinstance(payload, dict) else None
                if action == "expense":
                    record_operating_expense(world, payload)
                elif action in ("assessment", "pay"):
                    apply_tax_action(world, action, payload)
                else:
                    raise ValueError("Aksi keuangan tidak tersedia.")
            except ValueError as error:
                self.send_data({"error": str(error)}, status=400)
                return
            _save_simulation(db, world)
        self.send_data(company_finance(world))


class ExclusiveHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        if hasattr(socket,"SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

if __name__ == "__main__":
    try:
        with ExclusiveHTTPServer(("127.0.0.1",8081),Handler) as server:
            initialize()
            print("BIZ District tersedia di http://127.0.0.1:8081",flush=True)
            server.serve_forever()
    except OSError as error:
        if getattr(error,"winerror",None) in (10013,10048) or error.errno in (13,48,98):
            raise SystemExit("Server tidak bisa memakai port 8081. Hentikan server BIZ District lama.") from error
        raise
