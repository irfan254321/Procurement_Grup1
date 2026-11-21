"""Tax and financial reporting for the BIZ District simulation."""

SCALE = 10_000
VAT_RATE = .11  # PMK 131/2024: 12% × 11/12 for the non-luxury scenario
DAYS_PER_MONTH = 30
EXPENSE_BUDGETS = {"payroll": "payroll", "rent": "operations", "operations": "operations"}
CASH_MOVEMENTS = ("customer_receipts", "supplier_payments", "operating_payments", "tax_payments")
ASSESSMENTS = {
    "pbb": "PBB-P2",
    "pph_badan": "PPh Badan",
    "pph21": "PPh Pasal 21",
    "pph23": "PPh Pasal 23",
    "meterai": "Bea Meterai",
}


def vat(amount):
    # The simulator stores values in dataset units. Round VAT to whole rupiah.
    return round(round(amount * SCALE) * 11 / 100) / SCALE


def snapshot(world):
    return {"tick": world["tick"], "sales": world["sales"],
            "gross_profit": round(world["sales"] - world["cogs"], 2),
            "cash": world["cash"]}


def initialize_finance(world):
    world.setdefault("tax", {
        "since_tick": world["tick"], "rate": VAT_RATE, "input_vat": 0, "output_vat": 0,
        "assessed": dict.fromkeys(ASSESSMENTS, 0), "paid": dict.fromkeys(("vat", *ASSESSMENTS), 0),
        "payments": [],
    })
    world.setdefault("finance_series", [snapshot(world)])
    if "profit_report" not in world:
        world["profit_report"] = {
            "start_day": world.get("day", 0), "start_tick": world["tick"], "periods": [],
        }
        profit_period(world)
    if "cash_flow" not in world:
        world["cash_flow"] = {"start_day": world.get("day", 0), "start_tick": world["tick"], "periods": []}
        record_cash_flow(world, world["cash"])


def profit_period(world):
    month = world.get("day", 0) // DAYS_PER_MONTH + 1
    periods = world["profit_report"]["periods"]
    if not periods or periods[-1]["month"] != month:
        periods.append({"month": month, "sales": 0, "cogs": 0, "expenses": [], "income_tax": None})
    return periods[-1]


def record_trade_result(world, previous_sales, previous_cogs):
    period = profit_period(world)
    period["sales"] = round(period["sales"] + world["sales"] - previous_sales, 4)
    period["cogs"] = round(period["cogs"] + world["cogs"] - previous_cogs, 4)


def monthly_profit_report(world):
    report = world["profit_report"]
    periods = []
    for period in report["periods"]:
        totals = dict.fromkeys(EXPENSE_BUDGETS, 0)
        for expense in period["expenses"]:
            kind = expense["kind"]
            totals[kind] = round(totals[kind] + expense["amount"], 4)
        expenses = round(sum(totals.values()), 4)
        gross = round(period["sales"] - period["cogs"], 4)
        operating = round(gross - expenses, 4)
        periods.append({
            **period, "expense_totals": totals, "operating_expenses": expenses,
            "gross_profit": gross, "operating_profit": operating,
            "net_profit": round(operating - (period["income_tax"] or 0), 4),
        })
    return {**report, "days_per_month": DAYS_PER_MONTH, "periods": periods}


def record_cash_flow(world, previous_cash, category=None):
    month = world.get("day", 0) // DAYS_PER_MONTH + 1
    periods = world["cash_flow"]["periods"]
    if not periods or periods[-1]["month"] != month:
        periods.append({"month": month, "opening_cash": previous_cash, **dict.fromkeys(CASH_MOVEMENTS, 0)})
    period = periods[-1]
    if category:
        period[category] = round(period[category] + abs(world["cash"] - previous_cash), 4)
    period["closing_cash"] = world["cash"]


def balance_sheet(world):
    tax = world["tax"]
    vat_due = vat_balance(tax)
    case = world.get("case") or {}
    # Goods enter inventory at inspection. The matching payment clears the accrual.
    received = world["phase"] in {"invoice_check", "invoice_correction"}
    payable = case.get("expected_invoice", 0) if received else 0
    pending_input_vat = round(max(0, payable - case.get("accepted_cost", payable)), 4) if received else 0
    inventory = [{"name": item["name"], "units": item["units"], "value": round(item["units"] * item["cost"], 4)}
                 for item in world["products"]]
    inventory_value = round(sum(item["value"] for item in inventory), 4)
    current_tax = round(sum(tax["assessed"][kind] - tax["paid"][kind] for kind in ASSESSMENTS), 4)
    assets = round(world["cash"] + inventory_value + max(0, -vat_due) + pending_input_vat, 4)
    liabilities = round(payable + max(0, vat_due) + current_tax, 4)
    return {
        "cash": world["cash"], "inventory": inventory, "inventory_value": inventory_value,
        "vat_credit": max(0, -vat_due), "pending_input_vat": pending_input_vat,
        "supplier_payable": payable, "vat_due": max(0, vat_due), "assessed_tax_due": current_tax,
        "total_assets": assets, "total_liabilities": liabilities, "equity": round(assets - liabilities, 4),
    }


def company_finance(world):
    fields = ("tick", "day", "tax", "finance_series", "cash", "payroll", "operations", "reserve",
              "reserved", "fund", "reinvested", "last_purchase", "last_sale", "cash_flow")
    return {**{key: world.get(key) for key in fields},
            "profit_report": monthly_profit_report(world), "balance_sheet": balance_sheet(world)}


def record_operating_expense(world, payload):
    if not isinstance(payload, dict):
        raise ValueError("Data beban usaha tidak valid.")
    kind, amount = payload.get("kind"), payload.get("amount")
    if not isinstance(kind, str) or kind not in EXPENSE_BUDGETS:
        raise ValueError("Pilih jenis beban usaha.")
    if type(amount) is not int or not 0 < amount <= 1_000_000_000_000:
        raise ValueError("Isi nominal beban usaha dalam rupiah bulat, lebih dari nol.")
    budget = EXPENSE_BUDGETS[kind]
    amount /= SCALE
    spendable = round(free_cash(world) - world["reserved"] + world[budget], 4)
    if amount > spendable:
        raise ValueError("Kas tidak cukup setelah memperhitungkan cadangan dan kewajiban lain.")
    previous_cash = world["cash"]
    world["cash"] = round(world["cash"] - amount, 4)
    world[budget] = round(max(0, world[budget] - amount), 4)
    profit_period(world)["expenses"].append({
        "day": world["day"], "kind": kind, "amount": amount,
    })
    record_cash_flow(world, previous_cash, "operating_payments")


def track_finance(world):
    point = snapshot(world)
    series = world["finance_series"]
    if point["tick"] == series[-1]["tick"]:
        series[-1] = point
    elif point != {**series[-1], "tick": point["tick"]}:
        series.append(point)
        del series[:-120]


def vat_balance(tax):
    return round(tax["output_vat"] - tax["input_vat"] - tax["paid"]["vat"], 4)


def free_cash(world):
    assessed_due = sum(total - world["tax"]["paid"][key]
                       for key, total in world["tax"]["assessed"].items())
    return round(world["cash"] - world["payroll"] - world["operations"] -
                 world["reserve"] - max(0, vat_balance(world["tax"])) - assessed_due, 4)


def apply_tax_action(world, action, payload):
    if not isinstance(payload, dict):
        raise ValueError("Data pajak tidak valid.")
    kind = payload.get("kind")
    if not isinstance(kind, str):
        raise ValueError("Jenis pajak tidak valid.")
    tax = world["tax"]
    if action == "assessment":
        amount = payload.get("amount")
        if kind not in ASSESSMENTS or type(amount) is not int or not 0 <= amount <= 1_000_000_000_000:
            raise ValueError("Isi nominal tagihan dalam rupiah bulat.")
        total = amount / SCALE
        if total < tax["paid"][kind]:
            raise ValueError("Tagihan tidak boleh lebih kecil dari nominal yang sudah disetor.")
        if kind == "pph_badan":
            period = profit_period(world)
            delta = total - tax["assessed"][kind]
            period["income_tax"] = round((period["income_tax"] or 0) + delta, 4)
        tax["assessed"][kind] = total
        return

    if kind not in tax["paid"]:
        raise ValueError("Jenis pajak tidak valid.")
    due = vat_balance(tax) if kind == "vat" else round(tax["assessed"][kind] - tax["paid"][kind], 4)
    if due <= 0:
        raise ValueError("Jenis pajak ini tidak memiliki saldo yang perlu disetor.")
    spendable = round(world["cash"] - world["reserved"] - world["payroll"] -
                      world["operations"] - world["reserve"], 4)
    if due > spendable:
        raise ValueError("Kas bebas tidak cukup untuk setoran tanpa memakai dana yang sudah dicadangkan.")
    previous_cash = world["cash"]
    world["cash"] = round(world["cash"] - due, 4)
    tax["paid"][kind] = round(tax["paid"][kind] + due, 4)
    tax["payments"] = [{"kind": kind, "amount": due, "tick": world["tick"]}, *tax["payments"][:29]]
    record_cash_flow(world, previous_cash, "tax_payments")
