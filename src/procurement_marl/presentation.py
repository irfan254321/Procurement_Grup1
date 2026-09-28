"""Shared Indonesian log labels for the dashboard, CSV and report CLI."""

from .env import IRE_LABELS

VIOLATION = {"kas_negatif": "kas negatif", "anggaran": "anggaran terlampaui",
             "unit_mendesak": "unit mendesak terlambat", "kas_minimum": "kas di bawah minimum",
             "kapasitas": "kapasitas vendor kurang",
             "tanpa_pemasok_layak": "tidak ada pemasok yang memenuhi syarat",
             "dana_tidak_cukup": "dana total tidak cukup", "revisi_diminta": "revisi skenario diminta"}
REASON = {"kapasitas": "kapasitas kurang", "skor": "gugur skor komposit",
          "lead_time": "lead time melewati tenggat", "dikecualikan": "dikecualikan"}
STOP_REASON = {
    "consensus": "Rencana memenuhi batasan simulasi; belum mengeksekusi pembayaran ERP.",
    "report_revision_required": "Usulan perlu revisi sebelum disetujui. IRE meninjau kebutuhan, "
                                "VMI alternatif vendor, DA harga/termin, dan SLM dampak kas (Bab 6.5).",
    "no_progress": "Kebijakan tetap mengulang rencana dan keadaan yang sama tanpa kemajuan.",
    "cycle_limit": "Batas siklus simulasi tercapai; solusi belum ditemukan.",
    "step_limit": "Batas langkah pengaman simulasi tercapai.",
    "single_round_limit": "Evaluasi rencana satu putaran selesai; usulan masih melanggar batasan.",
    "infeasible_proven": "Batas bawah biaya melampaui dana yang tersedia; perubahan termin saja tidak cukup.",
    "revision_requested": "SLM meminta perubahan pendanaan, jumlah, harga, atau asumsi skenario.",
}


def rp(x: int) -> str:
    return ("-" if x < 0 else "") + "Rp" + f"{abs(x):,}".replace(",", ".")


def describe(e: dict) -> tuple[str, str]:
    event, a = e.get("event"), e["agent"]
    if event == "episode_stopped":
        return "SIMULASI DIHENTIKAN", STOP_REASON[e["stop_reason"]]
    if event == "term_request":
        return "usulkan revisi termin ke DA", f"batch {e['batch'] + 1}, {e['vendor']}; menunggu kesepakatan vendor."
    if event == "term_response":
        outcome = "diterima" if e["accepted"] else "ditolak; gunakan jatuh tempo"
        return "negosiasi ulang termin", f"batch {e['batch'] + 1}, {e['vendor']}: {outcome}. Hasil diteruskan ke SLM."
    if event == "revision_request":
        proof = "terbukti tidak feasible" if e["proven_infeasible"] else "perlu pemeriksaan ulang"
        return "minta revisi skenario", (f"Dana tersedia {rp(e['available'])}; batas bawah biaya "
                                          f"{rp(e['lower_bound'])}; {proof}.")
    if event == "diagnosis":
        return "TIDAK FEASIBLE" if e["stop_reason"] == "infeasible_proven" else "PERLU REVISI", STOP_REASON[e["stop_reason"]]
    if event == "vendor_check_start":
        return f"periksa Vendor {e['vendor']}", f"batch {e['batch'] + 1}; status sedang diperiksa."
    if event == "vendor_screening":
        if e["passed"]:
            result = "lolos penyaringan"
        else:
            labels = {"score": "skor", "capacity": "kapasitas", "deadline": "tenggat",
                      "not_excluded": "sudah dikeluarkan"}
            result = "gagal: " + ", ".join(labels.get(x, x) for x in e.get("failed_checks", []))
        checks = e["checks"]
        detail = (f"batch {e['batch'] + 1}; skor {e['score']:.2f}; "
                  f"skor={'lolos' if checks['score'] else 'gagal'}, "
                  f"kapasitas={'lolos' if checks['capacity'] else 'gagal'}, "
                  f"tenggat={'lolos' if checks['deadline'] else 'gagal'}.")
        return result, detail
    if a == "IRE":
        return IRE_LABELS[e["action"]], "; ".join(f"{b['qty']} unit bulan {b['month']}" for b in e["batches"])
    if a == "VMI":
        masked = ", ".join(f"{v}: {REASON[r]}" for v, r in e["masked"].items()) or "tidak ada yang di-mask"
        notes = ""
        if e.get("score_fallback"):
            notes += " Semua vendor di bawah ambang skor; vendor terbaik dipertahankan sesuai asumsi simulator."
        if e.get("no_vendor_fits"):
            notes += f" Tidak ada vendor layak; pilihan {e['vendor']} akan ditandai sebagai pelanggaran."
        return f"pilih {e['vendor']}", f"batch {e['batch'] + 1}. Di-mask: {masked}. Estimasi {rp(e['estimate'])}.{notes}"
    if a == "DA":
        note = ""
        if e.get("accepted") is not None:
            note = " (diterima)" if e["accepted"] else " (ditolak)"
        if e.get("withdrew"):
            note += ", vendor mundur"
        price = f"harga {rp(e['price'])}/unit" if e["price"] else "kembali ke VMI"
        return e["action"] + note, f"batch {e['batch'] + 1}, {e['vendor']}, {price}"
    if a == "SLM":
        note = ""
        if e["term_accepted"] is not None:
            note = " (termin diterima)" if e["term_accepted"] else " (termin ditolak, jatuh tempo)"
        return "rekomendasi " + e["action"] + note, (
            f"batch {e['batch'] + 1}: barang {rp(e['goods_value'])}, diskon {rp(e['discount'])}, "
            f"transport+risiko {rp(e['logistics'])}, total {rp(e['total'])}. Jadwal: "
            + "; ".join(f"bulan {m}: {rp(amount)}" for m, amount in e["schedule"].items()))
    names = ", ".join(VIOLATION[v] for v in e["violations"])
    decision = "KONSENSUS RENCANA" if e["consensus"] else "konflik"
    if e.get("stop_reason") == "report_revision_required":
        decision = "USULAN PERLU REVISI"
    detail = f"total {rp(e['total'])}, sisa anggaran {rp(e['budget_left'])}. "
    if names:
        detail += f"Pelanggaran: {names}. "
    if e.get("warnings"):
        detail += "Peringatan: kas di bawah minimum (belum menjadi syarat wajib). "
    if e.get("stop_reason"):
        detail += STOP_REASON[e["stop_reason"]]
    return decision, detail


def log_rows(log: list[dict]) -> list[dict]:
    rows = []
    for i, e in enumerate(log, 1):
        decision, detail = describe(e)
        row = {"Langkah": i}
        if "coordination_step" in e:
            row.update({"Tahap koordinasi": e["coordination_step"], "Uraian tahap": e["coordination_label"]})
        else:
            row["Siklus simulasi"] = e["round"]
        row.update({"Agen": e.get("reviewer", e["agent"]), "Keputusan": decision, "Rincian": detail})
        rows.append(row)
    return rows


def round_payments(log: list[dict], step: int) -> dict[int, int]:
    """Proposed payments only; requests and DA responses must not be counted twice."""
    rnd, payments = log[step - 1]["round"], {}
    for e in log[:step]:
        if e["round"] == rnd and e.get("event") == "payment_plan":
            for m, amount in e["schedule"].items():
                payments[m] = payments.get(m, 0) + amount
    return payments
