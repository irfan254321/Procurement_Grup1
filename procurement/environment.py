"""Perhitungan deterministik untuk biaya, kas, dan kendala."""
from dataclasses import dataclass
from .models import Scenario, Vendor


@dataclass(frozen=True)
class Assessment:
    cost_month_1: int
    cost_month_2: int
    total_cost: int
    cash_month_1: int
    cash_month_2: int
    violations: tuple[str, ...]

    @property
    def feasible(self) -> bool:
        # all() tidak cukup bila kuantitas belum lengkap; pelanggaran dicatat eksplisit.
        return not self.violations


def cost(vendor: Vendor, quantity: int, price: int, discount: float = 0.0) -> int:
    """Diskon hanya mengenai harga barang, bukan ongkos transport dan risiko."""
    return round(quantity * (price * (1 - discount) + vendor.transport + vendor.risk))


def assess(s: Scenario, allocations: tuple[tuple[Vendor, int, int, int, float], ...], vendors: tuple[Vendor, ...]) -> Assessment:
    """Tiap alokasi: vendor, unit, bulan (1/2), harga negosiasi, diskon."""
    issues: list[str] = []
    if sum(q for _, q, _, _, _ in allocations) != s.quantity:
        issues.append("Jumlah unit tidak memenuhi permintaan")
    month_cost = {1: 0, 2: 0}
    by_vendor: dict[str, int] = {}
    for vendor, qty, month, price, discount in allocations:
        by_vendor[vendor.name] = by_vendor.get(vendor.name, 0) + qty
        if qty < 0 or month not in (1, 2) or price < 0 or not 0 <= discount <= 1:
            issues.append("Alokasi memiliki nilai tidak valid")
            continue
        month_cost[month] += cost(vendor, qty, price, discount)
        if vendor.lead_days > s.deadline_days and month == 1:
            issues.append(f"Vendor {vendor.name} melewati tenggat")
    for vendor in vendors:
        if by_vendor.get(vendor.name, 0) > vendor.capacity:
            issues.append(f"Kapasitas Vendor {vendor.name} terlampaui")
    first_units = sum(q for _, q, m, _, _ in allocations if m == 1)
    if first_units < s.urgent_quantity:
        issues.append("Unit mendesak bulan pertama tidak terpenuhi")
    total = month_cost[1] + month_cost[2]
    cash_1 = s.cash - month_cost[1] - s.other_payment_1 - s.other_payment_2
    cash_2 = cash_1 + s.new_cash_month_2 - month_cost[2]
    if total > s.budget:
        issues.append(f"Anggaran terlampaui Rp {total - s.budget:,.0f}")
    if cash_1 < s.minimum_cash:
        issues.append(f"Kas bulan pertama di bawah minimum Rp {s.minimum_cash - cash_1:,.0f}")
    if cash_2 < s.minimum_cash:
        issues.append(f"Kas bulan kedua di bawah minimum Rp {s.minimum_cash - cash_2:,.0f}")
    return Assessment(month_cost[1], month_cost[2], total, cash_1, cash_2, tuple(issues))
