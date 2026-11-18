"""Load source-trained supplier forecasts, with explicit simulation transfer.

The historical suppliers sold health commodities, not electronics. Local order
quantities are mapped relative to a 12-unit simulation reference order; currency
and vendor identities are never presented as real electronics observations.
"""
from functools import lru_cache
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parent
SUPPLIER_DATA = ROOT / "data" / "supplier"
SOURCE = SUPPLIER_DATA / "SCMS_Delivery_History_Dataset.csv"
MODEL_VERSION = 2
FEATURES = (
    "vendor", "country", "shipment_mode", "fulfill_via", "incoterm",
    "product_group", "sub_classification", "log_quantity", "log_pack_price",
    "scheduled_days", "order_month", "order_year",
)
CATEGORICAL = tuple(range(7))
DATASET_URL = "https://www.kaggle.com/datasets/divyeshardeshana/supply-chain-shipment-pricing-data"


@lru_cache(maxsize=1)
def load_supplier_models():
    """Return the versioned bundle, or None until supplier_training --ensure."""
    import joblib

    try:
        report = json.loads((SUPPLIER_DATA / "metrics.json").read_text(encoding="utf-8"))
        profiles = json.loads((SUPPLIER_DATA / "profiles.json").read_text(encoding="utf-8"))
        artifact = joblib.load(SUPPLIER_DATA / "models.joblib")
    except (OSError, ValueError, EOFError, KeyError):
        return None
    if report.get("model_version") != MODEL_VERSION or artifact.get("model_version") != MODEL_VERSION:
        return None
    if artifact.get("features") != list(FEATURES) or not profiles:
        return None
    return {"report": report, "artifact": artifact, "profiles": profiles}


def get_supplier_profiles():
    bundle = load_supplier_models()
    if bundle is None:
        raise RuntimeError("Model pemasok belum tersedia. Jalankan supplier_training.py --ensure.")
    return [dict(profile) for profile in bundle["profiles"]]


def predict_supply(profile, quantity, mode="Truck", scheduled_days=None):
    """Predict historical-domain days/risk for a simulation supplier profile.

    quantity is local electronics units. Scaling to the profile's historical
    median avoids treating 12 laptops as 12 medical packs. Mode names follow
    the historical dataset (Air, Truck, Ocean, Air Charter).
    """
    bundle = load_supplier_models()
    if bundle is None:
        raise RuntimeError("Model pemasok belum tersedia. Jalankan supplier_training.py --ensure.")
    if not isinstance(profile, dict) or not profile.get("source_vendor"):
        raise ValueError("Profil pemasok historis tidak valid.")
    if not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity <= 0:
        raise ValueError("Jumlah pesanan harus positif.")
    if mode not in {"Air", "Truck", "Ocean", "Air Charter"}:
        raise ValueError("Moda pengiriman tidak dikenal.")
    scheduled = float(profile["scheduled_days"] if scheduled_days is None else scheduled_days)
    if not math.isfinite(scheduled) or scheduled <= 0:
        raise ValueError("Jadwal pengiriman harus positif.")
    mapped_quantity = max(1.0, float(profile["reference_quantity"]) * quantity / 12.0)
    vector = [
        profile["source_vendor"], profile["country"], mode, profile["fulfill_via"],
        profile["incoterm"], profile["product_group"], profile["sub_classification"],
        math.log1p(mapped_quantity), math.log1p(float(profile["typical_unit_price"])),
        scheduled, int(profile["order_month"]), int(profile["order_year"]),
    ]
    artifact = bundle["artifact"]
    probability = float(artifact["late"].predict_proba([vector])[0][1])
    use_regression = bundle["report"]["lead"]["selected_model"] == "CatBoostResidual"
    deviation = float(artifact["lead"].predict([vector])[0]) if use_regression else 0.0
    days = max(0.0, min(730.0, scheduled + deviation))
    return {
        "late_probability": round(probability, 6),
        "late_risk_score": round(probability, 6),
        "probability_calibrated": False,
        "predicted_days": round(days, 2),
        "lead_ratio": round(days / scheduled, 4),
        "scheduled_days": scheduled,
        "source_vendor": profile["source_vendor"],
        "source_country": profile["country"],
        "source_quantity": round(mapped_quantity, 2),
        "mode": mode,
        "domain_transfer": True,
        "high_risk": probability >= bundle["report"]["late"]["threshold"],
        "model": "CatBoost",
        "eta_model": bundle["report"]["lead"]["selected_model"],
    }
