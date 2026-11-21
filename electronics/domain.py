import json
from collections import defaultdict
from statistics import median

from finance import vat
from datasets.purchases import RETIRED_SUPPLIER, read_purchases
from paths import DATA, ROOT

MIN_MARKUP = 1.15
MODEL_VERSION = 2
AGENTS = {
    "stock": ("Stock", "Mendeteksi kebutuhan restok", "Restok perlu", "Stok cukup"),
    "finance": ("Keuangan", "Menilai kas dan margin restok", "Layak", "Tahan"),
    "seller": ("Penjual", "Memeriksa apakah pesanan bisa dilayani", "Layani", "Tunda"),
    "buyer": ("Pembeli", "Menilai minat pelanggan terhadap harga toko", "Beli", "Lewat"),
    "procurement": ("Pengadaan", "Memilih vendor untuk permintaan restok", "Prioritas", "Bandingkan"),
    "vendor": ("Vendor", "Menilai harga dan kapasitas pemasok", "Terima", "Tawar balik"),
    "deal": ("Negosiasi", "Menilai kecocokan tawaran dengan batas pembeli", "Sepakat", "Lanjut tawar"),
}
FEATURES = {
    "stock": ("stok", "permintaan", "titik pesan"),
    "finance": ("harga pengadaan", "dana tersedia", "potensi penjualan"),
    "seller": ("stok", "permintaan", "harga jual"),
    "buyer": ("harga jual", "kesediaan bayar", "jumlah"),
    "procurement": ("penawaran", "harga acuan", "kapasitas", "kebutuhan"),
    "vendor": ("tawaran pembeli", "harga minimum", "jumlah", "kapasitas"),
    "deal": ("tawaran penjual", "batas pembeli", "harga minimum"),
}


def load_models(directory=DATA):
    import joblib

    try:
        report = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        if report.get("model_version") != MODEL_VERSION:
            return None
        artifact = joblib.load(directory / "models.joblib")
    except (OSError, ValueError, EOFError):
        return None
    if artifact.get("model_version") != MODEL_VERSION:
        return None
    models = artifact["agents"]
    if any(report["agents"][role]["main"] not in models.get(role, {}) for role in AGENTS):
        return None
    return report, models


def make_catalog(rows):
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["Category"] == "Electronics" and row["Supplier"] != RETIRED_SUPPLIER:
            groups[row["ItemName"]][row["Supplier"]].append(float(row["UnitPrice"]))
    return [
        {"name": name, "reference": round(median(p for prices in vendors.values() for p in prices), 2),
         "vendors": [{"name": vendor, "price": round(median(prices), 2)}
                     for vendor, prices in sorted(vendors.items())]}
        for name, vendors in sorted(groups.items())
    ]


def targets(agent, x):
    a, b, c, *rest = x
    if agent == "stock":
        return a - b <= c
    if agent == "finance":
        return round(a + vat(a), 4) <= b and c >= round(a * MIN_MARKUP, 2)
    if agent == "seller":
        return a >= b
    if agent == "buyer":
        return a <= b
    if agent == "procurement":
        return a <= b * 1.08 and c >= rest[0]
    if agent == "vendor":
        return a >= b and c <= rest[0]
    return c <= a <= b
