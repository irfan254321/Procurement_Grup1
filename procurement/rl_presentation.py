# PANDUAN MAHASISWA: Mengubah event MARL menjadi tabel audit dan kalimat UI; irisan log sampai langkah aktif mencegah bocornya hasil masa depan.
"""Kalimat singkat untuk keputusan agen; log lengkap tetap tersedia di pelaporan."""
from procurement_marl.presentation import REASON, VIOLATION, log_rows, rp


def audit_rows(log: list[dict], report: dict, fallback_seed: int) -> list[dict]:
    """Rakit CSV audit; setiap bulan kas punya kolom tetap untuk semua run."""
    model = report.get("model", {})
    rows = []
    for row, raw in zip(log_rows(log), log):
        cash_values = raw.get("cash") or []
        rows.append({
            **row,
            "metode": report["policy"],
            "seed_simulasi": report.get("seed", fallback_seed),
            "versi_model": model.get("model_version", "model lama"),
            "hash_checkpoint": model.get("checkpoint_sha256", "tidak tersedia"),
            **{f"kas_bulan_{month}": cash_values[month - 1]
               if len(cash_values) >= month else None for month in range(1, 5)},
        })
    return rows


def competition_round_rows(log: list[dict], step: int, cycle: int, batch: int) -> list[dict]:
    """Tampilkan tawaran A/B/C sampai langkah terpilih dengan kolom Arrow yang seragam."""
    rows: dict[int, dict] = {}
    for event in log[:step]:
        if event["round"] != cycle or event.get("batch") != batch:
            continue
        vendor = event.get("vendor")
        if vendor not in {"A", "B", "C"}:
            continue
        if event.get("event") == "vendor_opening_offer":
            rows.setdefault(0, {"Putaran": "Awal", "A": "—", "B": "—", "C": "—"})[vendor] = rp(event["offer"])
        elif event.get("event") == "vendor_counter_offer":
            number = event["negotiation_round"]
            # Pandas/Arrow memerlukan tipe konsisten pada satu kolom.
            rows.setdefault(number, {"Putaran": str(number), "A": "—", "B": "—", "C": "—"})[vendor] = (
                f"Kita {rp(event['buyer_offer'])} → vendor {rp(event['vendor_offer'])} · "
                f"{'sepakat' if event['accepted'] else 'lanjut'}")
    return [rows[key] for key in sorted(rows)]


def brief_event(event: dict) -> str:
    agent = event["agent"]
    if event.get("event") == "vendor_opening_offer":
        return (f"Vendor {event['vendor']} membuka penawaran {rp(event['offer'])} per unit "
                f"dari harga daftar {rp(event['list_price'])}; batas bawahnya {rp(event['floor_price'])}.")
    if event.get("event") == "vendor_counter_offer":
        decision = "menyetujui harga" if event["accepted"] else "mengajukan counter offer"
        return (f"Vendor {event['vendor']} {decision} {rp(event['vendor_offer'])} pada ronde negosiasi "
                f"{event['negotiation_round']}; tawaran pembeli {rp(event['buyer_offer'])}.")
    if event.get("event") == "vendor_quote_ready":
        return (f"DA mencatat penawaran akhir Vendor {event['vendor']} sebesar "
                f"{rp(event['price'])} per unit, biaya termasuk transport dan risiko "
                f"{rp(event['landed_cost'])}. VMI membandingkan semua penawaran setelah ini.")
    if event.get("event") == "term_response":
        outcome = "menerima" if event["accepted"] else "menolak"
        draw = (f", angka seed {event['random_value']:.3f}" if event.get("random_value") is not None else "")
        return (f"Vendor {event['vendor']} {outcome} revisi termin; peluang menerima "
                f"{event.get('probability', 0):.1%}{draw}.")
    if event.get("event") == "vendor_check_start":
        return f"VMI sedang memeriksa Vendor {event['vendor']} untuk batch ini."
    if event.get("event") == "vendor_screening":
        if event["passed"]:
            return (f"Vendor {event['vendor']} lolos: skor, kapasitas, tenggat, dan status kandidat "
                    "memenuhi aturan batch.")
        labels = {"score": "skor", "capacity": "kapasitas", "deadline": "tenggat",
                  "not_excluded": "sudah dikeluarkan"}
        failures = ", ".join(labels.get(x, x) for x in event.get("failed_checks", []))
        return f"Vendor {event['vendor']} gagal pemeriksaan: {failures}."
    if event.get("event") == "revision_request":
        return (f"SLM meminta revisi: dana tersedia {rp(event['available'])}, sedangkan batas bawah biaya "
                f"{rp(event['lower_bound'])}. Kekurangan minimal {rp(event['shortfall'])}.")
    if event.get("event") == "diagnosis":
        return (f"Evaluator membuktikan dana kurang minimal {rp(event['shortfall'])}; "
                "mengubah termin saja tidak menyelesaikan masalah.")
    if agent == "IRE":
        parts = [f"{batch['qty']} unit bulan {batch['month']}" for batch in event["batches"]]
        return "IRE menyusun " + " dan ".join(parts) + "."
    if agent == "VMI":
        rejected = ", ".join(f"{vendor} ({REASON.get(reason, reason)})"
                             for vendor, reason in event.get("masked", {}).items())
        note = f" Kandidat tersaring: {rejected}." if rejected else " Semua kandidat memenuhi penyaringan awal."
        return f"VMI memilih vendor {event['vendor']} untuk batch ini." + note
    if agent == "DA":
        if event.get("price") is None:
            return f"DA meminta VMI mencari alternatif untuk vendor {event['vendor']}."
        response = " diterima" if event.get("accepted") is True else " ditolak" if event.get("accepted") is False else ""
        return f"DA memilih {event['action']}{response}; harga {rp(event['price'])} per unit."
    if agent == "SLM":
        if event.get("event") == "term_request":
            return f"SLM mengusulkan revisi termin kepada Vendor {event['vendor']}."
        return f"SLM mengusulkan {event['mode']} dengan total {rp(event['total'])}."
    if event.get("event") == "cek_batasan":
        if event["consensus"]:
            return f"ENV menyatakan rencana layak dengan biaya {rp(event['total'])}."
        issues = ", ".join(VIOLATION.get(v, v) for v in event["violations"])
        return f"ENV menolak rencana: {issues}."
    return "Simulasi berhenti setelah mencapai batas langkah pengaman."
