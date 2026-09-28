"""Orkestrasi enam putaran sesuai BAB 6 laporan."""
from dataclasses import dataclass
from .agents import ire, vmi, da, slm
from .environment import Assessment, assess
from .models import Scenario, VENDORS


@dataclass(frozen=True)
class Simulation:
    initial: Assessment
    staged: Assessment
    log: tuple[dict, ...]
    ranking: tuple[dict, ...]
    illustrative_rewards: dict


def run(s: Scenario) -> Simulation:
    """Menjalankan agen secara berurutan; semua hasil dihitung ulang dari input."""
    need = ire(s)
    ranking = vmi(s, VENDORS)
    prices = da(s)
    a, b, _ = VENDORS
    initial = assess(s, ((b, s.quantity, 1, prices["B"], s.discount_b),), VENDORS)
    staged = assess(s, ((b, need["urgent"], 1, prices["B"], s.discount_b),
                        (a, need["later"], 2, prices["A"], 0)), VENDORS)
    gap = slm(initial.cash_month_1, s.minimum_cash)
    log = (
        {"putaran": 1, "agen": "SLM", "aksi": "Deteksi konflik kas", "hasil": f"Kas akhir Rp {initial.cash_month_1:,.0f}; defisit terhadap minimum Rp {gap['shortfall']:,.0f}."},
        {"putaran": 2, "agen": "IRE", "aksi": "Tinjau prioritas", "hasil": f"{need['urgent']} unit mendesak; {need['later']} unit dapat ditunda."},
        {"putaran": 3, "agen": "VMI", "aksi": "Bandingkan pemasok", "hasil": f"Usulan {need['urgent']} B bulan 1 + {need['later']} A bulan 2; cek kapasitas dan tenggat."},
        {"putaran": 4, "agen": "DA", "aksi": "Negosiasi ulang", "hasil": f"Harga B Rp {prices['B']:,.0f}/unit; A Rp {prices['A']:,.0f}/unit (diskon A sudah termasuk)."},
        {"putaran": 5, "agen": "SLM", "aksi": "Periksa biaya dan kas", "hasil": f"Total Rp {staged.total_cost:,.0f}; kas bulan 1 Rp {staged.cash_month_1:,.0f}; bulan 2 Rp {staged.cash_month_2:,.0f}."},
        {"putaran": 6, "agen": "IRE + VMI + DA + SLM", "aksi": "Evaluasi konsensus", "hasil": "Layak disetujui." if staged.feasible else "Revisi diperlukan: " + "; ".join(staged.violations)},
    )
    # Reward berikut angka contoh pada laporan, bukan hasil training atau bukti kelayakan.
    reward = {"tanpa_konsensus": {"IRE": 10, "VMI": 50, "DA": 30, "SLM": -100},
              "dengan_konsensus": {"IRE": 25, "VMI": 35, "DA": 40, "SLM": 50}}
    return Simulation(initial, staged, log, tuple(ranking), reward)
