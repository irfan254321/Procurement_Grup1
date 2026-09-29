# PANDUAN MAHASISWA: Meringkas hasil simulator aturan lama menjadi teks pelaporan yang mudah dibaca pengguna.
"""Laporan pendek: hanya keputusan, angka penting, dan tindak lanjut."""


def make_summary(initial: dict, staged: dict, decision: dict) -> dict:
    """Bangun ringkasan deterministik agar konsisten dengan hasil pemeriksaan."""
    approved = decision["approved"]
    chosen = decision["chosen"]
    selected = staged if chosen == "bertahap" else initial if chosen == "awal" else None
    # Saat satu rencana layak, jangan mencampur pelanggaran rencana lain ke keputusan terpilih.
    issues = (selected["violations"] if selected else
              list(dict.fromkeys(initial["violations"] + staged["violations"])))
    return {
        "status": "LAYAK" if approved else "PERLU REVISI",
        "recommended_plan": chosen,
        "initial_cost": initial["total_cost"],
        "initial_cash_month_1": initial["cash_month_1"],
        "staged_cost": staged["total_cost"],
        "staged_cash_month_1": staged["cash_month_1"],
        "staged_cash_month_2": staged["cash_month_2"],
        "selected_cost": selected["total_cost"] if selected else None,
        "key_issues": issues[:3],
        "next_action": ("Rencana dapat diteruskan ke proses persetujuan manusia."
                        if approved else "Ubah pendanaan, jumlah, harga, atau termin; lalu jalankan skenario baru."),
    }
