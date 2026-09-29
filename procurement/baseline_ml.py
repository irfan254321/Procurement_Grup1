# PANDUAN MAHASISWA: Mengubah rencana akhir menjadi fitur tabular lalu menjalankan pembanding LR, SVM, Random Forest, dan XGBoost; tidak memilih aksi MARL.
"""Baseline supervised learning untuk menilai keputusan procurement.

Baseline ini terpisah dari IQL/CTDE. Model membaca fitur skenario dan rencana
yang sudah dihasilkan, lalu mengklasifikasikannya sebagai optimal atau tidak.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from procurement_marl.scenario import Scenario, composite_scores


PROJECT = Path(__file__).resolve().parents[1]
BASELINE_DIR = PROJECT / "runs" / "baseline"
MODEL_PATH = BASELINE_DIR / "models.joblib"
METRICS_PATH = BASELINE_DIR / "metrics.json"

# Urutan fitur harus tetap sama saat latihan dan inferensi.
FEATURE_COLUMNS = [
    "quantity", "urgent_share", "budget_per_unit", "deadline_days",
    "available_cash_per_unit", "min_cash_per_unit", "vendor_price_mean",
    "vendor_capacity_max_ratio", "plan_total_per_unit", "budget_ratio",
    "cash_after_per_unit", "cash_min_per_unit", "batch_count",
    "selected_vendor_count", "fast_payment_share", "due_payment_share",
    "term_payment_share", "selected_price_per_unit", "selected_quality",
    "selected_reputation", "selected_lead_ratio", "selected_capacity_ratio",
    "selected_score", "urgent_late_share",
]


def _safe_div(value: float, denominator: float) -> float:
    return float(value) / max(float(denominator), 1.0)


def decision_features(scenario: Scenario, result: dict) -> dict[str, float] | None:
    """Ubah satu rencana procurement menjadi satu baris data terstruktur.

    Hanya event ``payment_plan`` pada siklus akhir yang dipakai. Jika agen
    menghentikan skenario sebelum membuat rencana, baseline tidak mengarang
    prediksi karena belum ada keputusan vendor/pembayaran yang bisa dinilai.
    """
    log = result.get("log", [])
    # List comprehension mengambil hanya keputusan pembayaran; run yang
    # berhenti sebelum ada rencana tidak layak diberi label prediksi.
    payments = [event for event in log if event.get("event") == "payment_plan"]
    if not payments:
        return None
    final_round = max(event.get("round", 1) for event in payments)
    payments = [event for event in payments if event.get("round", 1) == final_round]
    if not payments:
        return None

    quantity = scenario.quantity
    scores = composite_scores(scenario)
    total = float(result.get("total") or sum(event.get("total", 0) for event in payments))
    final_check = next((event for event in reversed(log)
                        if event.get("event") == "cek_batasan" and event.get("round") == final_round), {})
    cash = final_check.get("cash") or payments[-1].get("cash") or []
    selected_qty = []
    selected_vendors = []
    for event in payments:
        vendor = scenario.vendor(event["vendor"])
        # goods_value / price mengembalikan jumlah unit batch tanpa menambah
        # field tersembunyi baru ke log simulator.
        price = max(float(event.get("price", 0)), 1.0)
        qty = round(float(event.get("goods_value", 0)) / price)
        selected_qty.append(max(qty, 0))
        selected_vendors.append(vendor)
    qty_sum = max(sum(selected_qty), 1)

    def weighted(attribute: str) -> float:
        return sum(qty * float(getattr(vendor, attribute))
                   for qty, vendor in zip(selected_qty, selected_vendors)) / qty_sum

    mode_shares = {
        mode: sum(qty for qty, event in zip(selected_qty, payments) if event.get("mode") == mode) / qty_sum
        for mode in ("bayar_cepat", "bayar_jatuh_tempo", "revisi_termin")
    }
    urgent_late = sum(
        qty for qty, vendor, event in zip(selected_qty, selected_vendors, payments)
        if event.get("batch", 0) == 0 and scenario.urgent_quantity > 0
        and vendor.lead_time > scenario.deadline_days
    )
    selected_price = sum(qty * float(event.get("price", 0))
                         for qty, event in zip(selected_qty, payments)) / qty_sum
    available_cash = scenario.initial_cash + sum(scenario.inflows) - sum(scenario.other_needs)
    return {
        "quantity": float(quantity),
        "urgent_share": _safe_div(scenario.urgent_quantity, quantity),
        "budget_per_unit": _safe_div(scenario.budget, quantity),
        "deadline_days": float(scenario.deadline_days),
        "available_cash_per_unit": _safe_div(available_cash, quantity),
        "min_cash_per_unit": _safe_div(scenario.min_cash, quantity),
        "vendor_price_mean": float(np.mean([v.list_price for v in scenario.vendors])),
        "vendor_capacity_max_ratio": _safe_div(max(v.capacity for v in scenario.vendors), quantity),
        "plan_total_per_unit": _safe_div(total, quantity),
        "budget_ratio": _safe_div(total, scenario.budget),
        "cash_after_per_unit": _safe_div(cash[-1] if cash else available_cash - total, quantity),
        "cash_min_per_unit": _safe_div(min(cash) if cash else available_cash - total, quantity),
        "batch_count": float(len(payments)),
        "selected_vendor_count": float(len({v.name for v in selected_vendors})),
        "fast_payment_share": mode_shares["bayar_cepat"],
        "due_payment_share": mode_shares["bayar_jatuh_tempo"],
        "term_payment_share": mode_shares["revisi_termin"],
        "selected_price_per_unit": selected_price,
        "selected_quality": weighted("quality"),
        "selected_reputation": weighted("reputation"),
        "selected_lead_ratio": _safe_div(weighted("lead_time"), scenario.deadline_days),
        "selected_capacity_ratio": _safe_div(weighted("capacity"), quantity),
        "selected_score": sum(qty * scores[vendor.name]
                              for qty, vendor in zip(selected_qty, selected_vendors)) / qty_sum,
        "urgent_late_share": _safe_div(urgent_late, max(scenario.urgent_quantity, 1)),
    }


def feature_vector(features: dict[str, float]) -> pd.DataFrame:
    """Susun fitur sesuai urutan yang direkam pada artefak pelatihan."""
    return pd.DataFrame([[features[name] for name in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS,
                        dtype=np.float64)


@lru_cache(maxsize=1)
def load_bundle(path: str | Path = MODEL_PATH) -> dict:
    """Muat model satu kali agar pergantian langkah Streamlit tetap cepat."""
    # Decorator cache menghindari baca joblib berulang pada setiap rerun UI.
    return joblib.load(Path(path))


def baseline_metadata() -> dict:
    """Identitas artefak untuk audit dan reproduksi laporan."""
    if not MODEL_PATH.exists() or not METRICS_PATH.exists():
        return {}
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return {
        "artifact": str(MODEL_PATH.relative_to(PROJECT)),
        "artifact_sha256": hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
        "dataset_source": metrics["dataset"]["source"],
        "train_rows": metrics["dataset"]["train_rows"],
        "test_rows": metrics["dataset"]["test_rows"],
        "split": metrics["dataset"]["split"],
        "label_rule": metrics["dataset"]["label_rule"],
        "comparator": metrics["comparator"],
    }


def classify_decision(scenario: Scenario, result: dict) -> dict:
    """Nilai keputusan MARL memakai semua baseline terlatih.

    XGBoost dipakai sebagai pembanding utama sesuai rancangan laporan. Hasil
    empat model tetap dikembalikan supaya perbandingan tidak disembunyikan.
    """
    features = decision_features(scenario, result)
    if features is None:
        return {
            "applicable": False,
            "label": "BELUM DAPAT DINILAI",
            "reason": "Agen menghentikan skenario sebelum rencana vendor dan pembayaran lengkap terbentuk.",
            "metadata": baseline_metadata(),
        }
    if not MODEL_PATH.exists():
        return {
            "applicable": False,
            "label": "MODEL BELUM DILATIH",
            "reason": "Jalankan scripts/train_baseline.py untuk membuat artefak baseline ML.",
            "metadata": {},
        }
    bundle = load_bundle()
    x = feature_vector(features)
    predictions = {}
    for name, model in bundle["models"].items():
        predicted = int(model.predict(x)[0])
        probability = float(model.predict_proba(x)[0, 1])
        predictions[name] = {"optimal": bool(predicted), "probability_optimal": probability}
    comparator = bundle.get("comparator", "XGBoost")
    chosen = predictions[comparator]
    return {
        "applicable": True,
        "label": "OPTIMAL" if chosen["optimal"] else "TIDAK OPTIMAL",
        "probability_optimal": chosen["probability_optimal"],
        "comparator": comparator,
        "predictions": predictions,
        "features": features,
        "metadata": baseline_metadata(),
    }


def metrics_report() -> dict:
    """Baca metrik test set yang tidak pernah dipakai untuk melatih model."""
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
