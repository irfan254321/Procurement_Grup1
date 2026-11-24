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
    "company-negotiations.js", "company-status.js", "room-3d.mjs", "room-stage.mjs", "district-3d.mjs",
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


OFFLINE_COPY = {
    "cloudsoft": (
        "CS", "Layanan pasokan sedang ditutup.",
        "Akses katalog dan penawaran CloudSoft ditangguhkan selama perusahaan berstatus offline.",
        "Pemasok perangkat elektronik",
    ),
    "furniworks": (
        "FW", "Layanan kami tutup sementara.",
        "FurniWorks sedang offline. Katalog dan permintaan pasokan tersedia kembali setelah perusahaan dibuka.",
        "Pengadaan untuk ruang kerja",
    ),
    "quickdeliver": (
        "QD", "Pemenuhan pesanan sedang dijeda.",
        "QuickDeliver sedang offline. Permintaan penawaran dan persiapan pesanan baru ditangguhkan.",
        "Pusat pemenuhan elektronik",
    ),
    "techmart": (
        "TM", "Portal pemasok belum tersedia.",
        "TechMart sedang offline. Akses katalog, harga, dan penawaran dibuka kembali setelah perusahaan aktif.",
        "Distribusi perangkat elektronik",
    ),
    "jne": (
        "JNE", "Layanan pengiriman sedang ditutup.",
        "JNE sedang offline di BIZ District. Penawaran pengiriman dan permintaan penjemputan baru ditangguhkan.",
        "Informasi layanan pengiriman",
    ),
    "jt-cargo": (
        "J&T", "Terminal belum menerima permintaan.",
        "J&T Cargo sedang offline di BIZ District. Penawaran kargo dan permintaan penjemputan baru ditangguhkan.",
        "Informasi layanan kargo",
    ),
    "pos-logistik": (
        "POS", "Layanan logistik ditutup sementara.",
        "Pos Logistik Indonesia sedang offline di BIZ District. Portal operasional dan penawaran baru dibuka kembali setelah perusahaan aktif.",
        "Informasi layanan logistik",
    ),
}


def _offline_content(slug):
    mark, title, description, label = OFFLINE_COPY[slug]
    services = ("Katalog produk", "Permintaan penawaran", "Portal operasional")
    if slug in CARRIER_PROFILES:
        services = ("Penawaran pengiriman", "Permintaan penjemputan", "Portal operasional")
    rows = "".join(
        f'<li><span>{escape(service)}</span><span class="offline-service-state">'
        '<i aria-hidden="true"></i>Ditangguhkan</span></li>'
        for service in services
    )
    return f"""
<section class="company-offline-layout profile-shell" aria-labelledby="offline-title">
  <div class="offline-section-label">
    <span>Pusat layanan</span><span aria-hidden="true">/</span><span>Ketersediaan perusahaan</span>
  </div>
  <div class="offline-main">
    <div class="offline-copy">
      <p class="offline-badge"><span aria-hidden="true"></span>Perusahaan offline</p>
      <h1 id="offline-title">{escape(title)}</h1>
      <p class="offline-description">{escape(description)}</p>
      <div class="offline-actions">
        <button class="profile-button offline-check" id="company-status-check" type="button">Periksa status<span aria-hidden="true">↻</span></button>
        <a class="offline-back" href="/">Kembali ke distrik<span aria-hidden="true">↗</span></a>
      </div>
      <p class="offline-live" id="company-status-message" role="status" aria-live="polite">Status diperiksa otomatis. Halaman akan terbuka kembali saat perusahaan aktif.</p>
      <div class="offline-cover" aria-hidden="true"></div>
    </div>
    <aside class="offline-service-card" aria-label="Status layanan {escape(COMPANY_NAMES[slug])}">
      <div class="offline-card-brand">
        <span class="offline-monogram" aria-hidden="true">{escape(mark)}</span>
        <div><strong>{escape(COMPANY_NAMES[slug])}</strong><span>{escape(label)}</span></div>
      </div>
      <div class="offline-card-heading"><h2>Status layanan</h2><span class="offline-paused">Ditutup</span></div>
      <ul class="offline-services">{rows}</ul>
      <dl class="offline-reopening">
        <div><dt>Pembukaan kembali</dt><dd>Belum ditetapkan</dd></div>
        <div><dt>Pembaruan status</dt><dd>Otomatis</dd></div>
      </dl>
      <p class="offline-verified" id="company-status-time">Menunggu konfirmasi status terkini</p>
    </aside>
  </div>
  <div class="offline-notice">
    <span class="offline-notice-icon" aria-hidden="true">i</span>
    <div><h2>Ingin melanjutkan pengadaan?</h2>
      <p>Aktifkan kembali perusahaan melalui panel perusahaan di BIZ District. Status website akan diperbarui secara otomatis.</p></div>
    <a href="/">Buka distrik<span aria-hidden="true">→</span></a>
  </div>
</section>"""


def company_profile(slug, *, online=True):
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
    if font_query and online:
        font_link = f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{escape(font_query)}">'
    template = (WEB / "company-profile.html").read_text(encoding="utf-8")
    if not online:
        template = template.replace('<link rel="preconnect" href="https://fonts.googleapis.com">', "")
        template = template.replace('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>', "")
    navigation = """<nav class="profile-nav" aria-label="Halaman perusahaan">
        <a href="#profil" data-company-view aria-current="page">Profil</a>
        <a href="#aturan" data-company-view>Aturan</a>
        <a href="#biaya-logistik" data-company-view>Biaya logistik</a>
        <a href="#negosiasi" data-company-view>Jadwal &amp; negosiasi</a>
      </nav>"""
    scripts = """<script defer src="/format.js"></script>
  <script defer src="/company-dashboard.js"></script>
  <script defer src="/company-negotiations.js"></script>
  <script defer src="/company-profile.js"></script>"""
    return Template(template).substitute(
        slug=slug,
        page_title=name + (" | BIZ District" if online else " | Offline"),
        offline="false" if online else "true",
        navigation=navigation if online else "",
        scripts=scripts if online else "",
        footer_link='<a href="#ringkasan">Ringkasan operasional</a>' if online else '<a href="/">Kembali ke BIZ District</a>',
        name=name,
        description=escape(profile["description"]),
        font_link=font_link,
        stylesheet=f"/{group}-profiles.css",
        content=profile["body"] if online else _offline_content(slug),
        operations=operations if online else "",
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
