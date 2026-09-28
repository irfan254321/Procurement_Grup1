"""Pure cost and cash-flow formulas. Money is always integer rupiah."""

from __future__ import annotations

# Payment modes chosen by SLM.
PAY_FAST = "bayar_cepat"        # goods paid in the batch month, discount if offered
PAY_DUE = "bayar_jatuh_tempo"   # goods paid next month, no discount
PAY_SPLIT = "revisi_termin"     # 50% next month, 50% two months later, no discount


def goods_value(quantity: int, price: int) -> int:
    """Value of the goods before any discount."""
    return quantity * price


def discount_amount(value: int, discount_pct: int) -> int:
    """Payment discount on goods only, rounded to the nearest rupiah (half up)."""
    return (value * discount_pct + 50) // 100


def logistics_cost(quantity: int, transport: int, risk: int) -> int:
    """Transport (c1) and risk (c2) cost, paid in the batch month."""
    return quantity * (transport + risk)


def batch_total(quantity: int, price: int, transport: int, risk: int, discount_pct: int = 0) -> int:
    """C = q * (p * (1 - d) + c1 + c2)."""
    value = goods_value(quantity, price)
    return value - discount_amount(value, discount_pct) + logistics_cost(quantity, transport, risk)


def payment_schedule(
    mode: str,
    month: int,
    quantity: int,
    price: int,
    transport: int,
    risk: int,
    discount_pct: int = 0,
) -> dict[int, int]:
    """Return {month: amount paid} for one batch bought in `month` (1-based)."""
    value = goods_value(quantity, price)
    logistics = logistics_cost(quantity, transport, risk)
    if mode == PAY_FAST:
        return {month: value - discount_amount(value, discount_pct) + logistics}
    if mode == PAY_DUE:
        return {month: logistics, month + 1: value}
    if mode == PAY_SPLIT:
        first = value // 2
        return {month: logistics, month + 1: first, month + 2: value - first}
    raise ValueError(f"unknown payment mode: {mode}")


def cash_after(previous_cash: int, inflow: int, payment: int, other_need: int) -> int:
    """K_m = K_{m-1} + inflow_m - payment_m - other_need_m."""
    return previous_cash + inflow - payment - other_need


def cash_balances(
    initial_cash: int,
    inflows: list[int],
    other_needs: list[int],
    payments: dict[int, int],
) -> list[int]:
    """Cash at the end of each month 1..len(inflows). `payments` is {month: amount}."""
    balances = []
    cash = initial_cash
    for month, (inflow, need) in enumerate(zip(inflows, other_needs), start=1):
        cash = cash_after(cash, inflow, payments.get(month, 0), need)
        balances.append(cash)
    return balances
