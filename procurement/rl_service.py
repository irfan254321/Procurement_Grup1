# PANDUAN MAHASISWA: Jembatan formulir ke model terlatih: validasi input, muat checkpoint, jalankan episode, dan bentuk laporan akhir.
"""Hubungkan input sederhana dengan kebijakan MARL terlatih dan laporan singkat."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

from procurement_marl.agents.iql import IQL
from procurement_marl.agents.ctde_ac import CTDEActorCritic
from procurement_marl.env import ProcurementEnv
from procurement_marl.evaluate import run_episode
from procurement_marl.scenario import Scenario, Vendor, load_scenario
from procurement.baseline_ml import classify_decision


PROJECT = Path(__file__).resolve().parents[1]
CHECKPOINTS = {
    "IQL": PROJECT / "runs" / "iql" / "checkpoint.json",
    "CTDE": PROJECT / "runs" / "ctde" / "checkpoint.pt",
}
MODEL_VERSION = 8

INT_VENDOR_FIELDS = ("list_price", "transport", "risk", "quality", "lead_time", "capacity",
                     "initial_offer", "floor_price", "discount_pct")
FLOAT_VENDOR_FIELDS = ("reputation", "relation")


def default_vendor_rows() -> list[dict]:
    """Data A/B/C BAB 6 dalam bentuk baris yang bisa ditampilkan oleh Streamlit."""
    return [asdict(v) for v in load_scenario().vendors]


def validate_vendor_rows(rows: list[dict]) -> tuple[Vendor, ...]:
    """Validasi editor vendor dan ubah nilainya menjadi objek Vendor yang konsisten."""
    if len(rows) != 3 or [str(row.get("name", "")).strip() for row in rows] != ["A", "B", "C"]:
        raise ValueError("Konfigurasi harus tetap berisi Vendor A, B, dan C dalam urutan tersebut.")
    vendors = []
    for raw in rows:
        name = str(raw["name"]).strip()
        try:
            data = {"name": name}
            data.update({field: int(raw[field]) for field in INT_VENDOR_FIELDS})
            data.update({field: float(raw[field]) for field in FLOAT_VENDOR_FIELDS})
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Vendor {name}: seluruh kolom harus berisi angka yang valid.") from None
        if min(data["list_price"], data["initial_offer"], data["floor_price"]) <= 0:
            raise ValueError(f"Vendor {name}: harga harus lebih besar dari nol.")
        if not data["floor_price"] <= data["initial_offer"] <= data["list_price"]:
            raise ValueError(f"Vendor {name}: harga minimum ≤ penawaran awal ≤ harga daftar.")
        if data["transport"] < 0 or data["risk"] < 0:
            raise ValueError(f"Vendor {name}: transportasi dan risiko tidak boleh negatif.")
        if data["capacity"] <= 0 or data["lead_time"] <= 0:
            raise ValueError(f"Vendor {name}: kapasitas dan lead time harus lebih besar dari nol.")
        if not 0 <= data["quality"] <= 10 or not 0 <= data["reputation"] <= 10:
            raise ValueError(f"Vendor {name}: kualitas dan reputasi harus berada pada rentang 0–10.")
        if not 0 <= data["relation"] <= 1:
            raise ValueError(f"Vendor {name}: relasi harus berada pada rentang 0–1.")
        if not 0 <= data["discount_pct"] <= 100:
            raise ValueError(f"Vendor {name}: diskon harus berada pada rentang 0–100%.")
        vendors.append(Vendor(**data))
    return tuple(vendors)


def scenario_from_request(quantity: int, urgent: int, budget: int, vendor_rows: list[dict] | None = None):
    """Vendor dan asumsi kas datang dari fixture; pengguna mengubah tiga variabel inti."""
    if quantity <= 0 or not 0 <= urgent <= quantity or budget <= 0:
        raise ValueError("Periksa jumlah unit, unit mendesak, dan anggaran")
    vendors = validate_vendor_rows(vendor_rows) if vendor_rows is not None else load_scenario().vendors
    # replace membuat salinan dataclass fixture BAB 6; berkas YAML tidak ditimpa.
    return replace(load_scenario(), quantity=quantity, urgent_quantity=urgent, budget=budget, vendors=vendors)


def scenario_from_snapshot(data: dict) -> Scenario:
    """Pulihkan data vendor asli suatu run walaupun konfigurasi aplikasi kelak berubah."""
    return Scenario(**(data | {
        "vendors": tuple(Vendor(**vendor) for vendor in data["vendors"]),
        "other_needs": tuple(data["other_needs"]),
        "inflows": tuple(data["inflows"]),
    }))


def policy_from_checkpoint(name: str):
    """Tidak ada pengganti heuristik diam-diam bila checkpoint belum tersedia."""
    if name not in CHECKPOINTS:
        raise ValueError("Pilih CTDE atau IQL")
    path = CHECKPOINTS[name]
    if not path.exists():
        raise FileNotFoundError(f"Model {name} belum dilatih: {path}")
    config_path = path.with_name("config.json")
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    if config.get("model_version") != MODEL_VERSION:
        raise RuntimeError(f"Model {name} versi lama; latih ulang untuk alur negosiasi versi {MODEL_VERSION}.")
    # Cabang ini benar-benar memuat parameter hasil train, bukan memilih fungsi aturan.
    return IQL.load(path) if name == "IQL" else CTDEActorCritic.load(path)


def checkpoint_metadata(name: str) -> dict:
    """Catat identitas model agar hasil lama dapat diaudit dan direproduksi."""
    path = CHECKPOINTS[name]
    config_path = path.with_name("config.json")
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "model_version": config.get("model_version", MODEL_VERSION),
        "checkpoint": str(path.relative_to(PROJECT)),
        "checkpoint_sha256": digest,
        "training_episodes": config.get("episodes"),
        "training_seed": config.get("seed"),
    }


def short_report(result: dict, scenario, policy: str, seed: int) -> dict:
    """Status berasal dari pemeriksaan environment, bukan dari besarnya reward."""
    checks = [e for e in result["log"] if e.get("event") in {"cek_batasan", "diagnosis"}]
    final = checks[-1] if checks else {}
    outcome = result["outcome"]
    if outcome == "LAYAK":
        next_action = "Lanjutkan ke persetujuan manusia; simulasi belum mengeksekusi pembelian."
    elif outcome == "TIDAK FEASIBLE":
        next_action = "Ubah pendanaan, anggaran, atau jumlah unit karena dana total tidak cukup bahkan pada biaya minimum."
    else:
        next_action = "Periksa jumlah, pemasok, harga, atau termin lalu jalankan skenario baru."
    report = {
        "status": outcome,
        "policy": policy,
        "seed": seed,
        "model": checkpoint_metadata(policy),
        "quantity": scenario.quantity,
        "urgent_quantity": scenario.urgent_quantity,
        "budget": scenario.budget,
        "total": result["total"],
        "total_kind": "batas_bawah" if final.get("event") == "diagnosis" else "rencana",
        "cash": final.get("cash", []),
        "violations": result["violations"],
        "rounds": result["rounds"],
        "stop_reason": result["stop_reason"],
        "cash_diagnosis": result.get("cash_diagnosis", {}) if outcome == "TIDAK FEASIBLE" else {},
        "next_action": next_action,
    }
    # Baseline hanya mengevaluasi rencana yang sudah dibuat MARL. Ia tidak
    # memilih aksi dan tidak memengaruhi status kelayakan dari environment.
    report["baseline_ml"] = classify_decision(scenario, result)
    return report


def simulate(policy: str, quantity: int, urgent: int, budget: int, seed: int,
             vendor_rows: list[dict] | None = None) -> tuple[dict, dict, dict]:
    """Jalankan episode penuh; setiap langkah agen disimpan oleh lapisan database."""
    scenario = scenario_from_request(quantity, urgent, budget, vendor_rows)
    model = policy_from_checkpoint(policy)
    env = ProcurementEnv(scenario)
    # seed diteruskan ke RNG environment agar negosiasi/termin dapat diulang.
    result = run_episode(env, model, seed=seed,
                         options={"scenario": scenario, "stop_on_repeat": True})
    return asdict(scenario), result, short_report(result, scenario, policy, seed)
