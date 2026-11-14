"""Finance checks for one simulated procurement decision."""
from decimal import Decimal, InvalidOperation


def evaluate_finance(result, inputs):
    def money(key):
        try:
            value = Decimal(str(inputs[key]))
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise ValueError("Lengkapi asumsi Agent Keuangan.") from exc
        if not value.is_finite() or not 0 <= value <= Decimal("1e15"):
            raise ValueError("Nilai keuangan harus antara 0 dan 10^15.")
        return value.quantize(Decimal(".01"))

    amounts = {key: money(key) for key in (
        "cash", "receipts", "payroll", "operations", "commitments",
        "reserve", "procurement_funds", "revenue", "period_expenses",
    )}
    candidate = result["recommended"]
    cost = Decimal(str(candidate["final_offer"])) if candidate else Decimal(0)
    available = sum(amounts[key] for key in ("cash", "receipts")) - sum(
        amounts[key] for key in ("payroll", "operations", "commitments")
    )
    remaining = available - cost
    profit_before = amounts["revenue"] - amounts["period_expenses"]
    profit = profit_before - cost
    funds_left = amounts["procurement_funds"] - cost

    reasons = []
    if candidate is None:
        if result["status"] == "budget_conflict":
            reasons.append(f"Anggaran permintaan kurang {result['minimum_budget_gap']}.")
        else:
            reasons.append("Tidak ada vendor yang memenuhi syarat negosiasi.")
    if funds_left < 0:
        reasons.append(f"Dana kategori pengadaan kurang {-funds_left:.2f}.")
    if remaining < amounts["reserve"]:
        reasons.append(f"Kas kurang {amounts['reserve'] - remaining:.2f} setelah melindungi gaji, operasional, komitmen, dan cadangan minimum.")
    if profit < 0:
        reasons.append(f"Proyeksi rugi setelah pembelian {-profit:.2f}.")

    return {
        "approved": not reasons,
        "reasons": reasons,
        "vendor": candidate["vendor"] if candidate else None,
        "due_days": result["payment_days"] if candidate else None,
        **{key: float(value) for key, value in amounts.items()},
        "cost": float(cost),
        "available": float(available),
        "remaining": float(remaining),
        "funds_left": float(funds_left),
        "profit_before": float(profit_before),
        "profit": float(profit),
    }
