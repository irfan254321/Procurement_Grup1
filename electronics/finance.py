"""Tax and financial reporting for the BIZ District simulation."""

SCALE = 10_000
VAT_RATE = .11  # PMK 131/2024: 12% × 11/12 for the non-luxury scenario
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
    world["cash"] = round(world["cash"] - due, 4)
    tax["paid"][kind] = round(tax["paid"][kind] + due, 4)
    tax["payments"] = [{"kind": kind, "amount": due, "tick": world["tick"]}, *tax["payments"][:29]]
