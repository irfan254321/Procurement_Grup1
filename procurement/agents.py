# PANDUAN MAHASISWA: Empat fungsi agen aturan lama dipakai oleh alur pembanding; kebijakan IQL/CTDE terlatih berada di src/procurement_marl/agents.
"""Empat agen sebagai fungsi keputusan yang mudah diaudit mahasiswa."""
from .models import Scenario, Vendor


def ire(s: Scenario) -> dict:
    """IRE memvalidasi kebutuhan dan membagi kebutuhan mendesak."""
    if not 0 <= s.urgent_quantity <= s.quantity:
        raise ValueError("Unit mendesak harus antara 0 dan total unit")
    return {"priority": 95 if s.deadline_days <= 10 else 70,
            "urgent": s.urgent_quantity, "later": s.quantity - s.urgent_quantity}


def vmi(s: Scenario, vendors: tuple[Vendor, ...]) -> list[dict]:
    """Skor ilustratif; angka 6,60/7,19/5,41 laporan dipertahankan sebagai kalibrasi contoh."""
    report_scores = {"A": 6.60, "B": 7.19, "C": 5.41}
    rows = []
    for v in vendors:
        # Jika input vendor diubah, gunakan proksi transparan, bukan klaim model terlatih.
        score = report_scores[v.name] if v in DEFAULT_VENDORS else (
            0.4 * v.quality + 0.3 * max(0, 10 - v.lead_days / 2)
            + 0.2 * v.reputation + 0.1 * max(0, 10 - v.price / 20_000))
        rows.append({"vendor": v.name, "score": round(score, 2), "capacity": v.capacity,
                     "lead_days": v.lead_days, "eligible": v.lead_days <= s.deadline_days})
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def da(s: Scenario) -> dict:
    """DA mengembalikan harga negosiasi yang dapat diubah lewat dashboard."""
    return {"B": s.negotiated_b, "A": s.negotiated_a}


def slm(cash_after: int, minimum: int) -> dict:
    """SLM melaporkan posisi kas dan defisit terhadap batas minimum."""
    return {"cash_after": cash_after, "shortfall": max(0, minimum - cash_after)}


from .models import VENDORS as DEFAULT_VENDORS
