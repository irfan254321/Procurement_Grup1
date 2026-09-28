"""Kalimat singkat untuk keputusan agen; log lengkap tetap tersedia di pelaporan."""
from procurement_marl.presentation import REASON, VIOLATION, rp


def brief_event(event: dict) -> str:
    agent = event["agent"]
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
        if event.get("event") == "term_response":
            return "DA menyetujui revisi termin." if event["accepted"] else "DA menolak revisi termin; pembayaran jatuh tempo."
        if event.get("price") is None:
            return f"DA meminta VMI mencari alternatif untuk vendor {event['vendor']}."
        response = " diterima" if event.get("accepted") is True else " ditolak" if event.get("accepted") is False else ""
        return f"DA memilih {event['action']}{response}; harga {rp(event['price'])} per unit."
    if agent == "SLM":
        if event.get("event") == "term_request":
            return "SLM mengusulkan revisi termin kepada DA."
        return f"SLM mengusulkan {event['mode']} dengan total {rp(event['total'])}."
    if event.get("event") == "cek_batasan":
        if event["consensus"]:
            return f"ENV menyatakan rencana layak dengan biaya {rp(event['total'])}."
        issues = ", ".join(VIOLATION.get(v, v) for v in event["violations"])
        return f"ENV menolak rencana: {issues}."
    return "Simulasi berhenti setelah mencapai batas langkah pengaman."
