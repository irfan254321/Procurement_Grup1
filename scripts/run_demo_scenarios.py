# PANDUAN MAHASISWA: Menjalankan 20 contoh sebagai 10 pasangan IQL/CTDE, lalu menulis JSON tanpa mengubah database pengguna.
"""Jalankan 20 contoh pembelajaran tanpa menambah riwayat SQLite pengguna.

Setiap input dipasangkan antara IQL dan CTDE agar perbedaan metode terlihat.
Hasil ditulis sebagai JSON; penjelasan tujuan tiap pasangan ada di
``docs/20_skenario_uji.md``. Profil vendor memakai nilai BAB 6, kecuali
pasangan terakhir yang hanya mengubah ongkos transport Vendor B.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from procurement.rl_service import default_vendor_rows, simulate


# Setiap baris: jumlah, mendesak, anggaran, seed, konfigurasi vendor, tujuan uji.
PAIRS = [
    (1000, 700, 100_000_000, 0, "BAB 6", "Acuan laporan; cek kekurangan dana total"),
    (700, 700, 100_000_000, 0, "BAB 6", "Semua unit mendesak; cek satu batch"),
    (700, 300, 100_000_000, 0, "BAB 6", "Kurangi urgensi tanpa mengubah jumlah"),
    (600, 100, 100_000_000, 0, "BAB 6", "Kurangi jumlah dan urgensi; cari rencana layak"),
    (800, 700, 100_000_000, 0, "BAB 6", "Dekati batas kas dan kapasitas A"),
    (900, 700, 100_000_000, 0, "BAB 6", "Naikkan kebutuhan melewati kapasitas A"),
    (600, 100, 55_000_000, 0, "BAB 6", "Perketat anggaran saja"),
    (600, 100, 100_000_000, 1, "BAB 6", "Ganti seed saja; uji respons termin"),
    (600, 100, 100_000_000, 7, "BAB 6", "Ganti seed lagi; uji kestabilan kebijakan"),
    (600, 100, 100_000_000, 0, "B transport Rp1.000", "Ubah ongkos transport B saja"),
]


def run_all() -> list[dict]:
    rows = []
    for pair_number, (quantity, urgent, budget, seed, vendor_case, purpose) in enumerate(PAIRS, 1):
        for method in ("IQL", "CTDE"):
            vendor_rows = deepcopy(default_vendor_rows())
            if vendor_case != "BAB 6":
                next(row for row in vendor_rows if row["name"] == "B")["transport"] = 1_000
            _, result, report = simulate(method, quantity, urgent, budget, seed, vendor_rows)
            final_round = result["rounds"]
            payments = [event for event in result["log"]
                        if event.get("event") == "payment_plan" and event["round"] == final_round]
            allocations = [
                {"vendor": event["vendor"],
                 "units": round(event["goods_value"] / event["price"]),
                 "payment": event["mode"]}
                for event in payments
            ]
            final_check = next((event for event in reversed(result["log"])
                                if event.get("event") in {"cek_batasan", "diagnosis"}), {})
            baseline = report.get("baseline_ml", {})
            rows.append({
                "number": 2 * pair_number - (method == "IQL"),
                "pair": pair_number,
                "method": method,
                "quantity": quantity,
                "urgent": urgent,
                "budget": budget,
                "seed": seed,
                "vendor_case": vendor_case,
                "purpose": purpose,
                "status": report["status"],
                "total_kind": report["total_kind"],
                "total": report["total"],
                "allocations": allocations,
                "cash": report["cash"],
                "warnings": final_check.get("warnings", []),
                "stop_reason": report["stop_reason"],
                "baseline_label": baseline.get("label") if baseline.get("applicable") else None,
                "baseline_probability": baseline.get("probability_optimal") if baseline.get("applicable") else None,
            })
    return rows


if __name__ == "__main__":
    output = ROOT / "runs" / "demo_scenarios_v7.json"
    output.write_text(json.dumps(run_all(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"20 skenario selesai: {output}")
