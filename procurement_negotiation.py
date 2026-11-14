"""Deterministic offer simulation. Assumed costs and rules never come from BPI labels."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, localcontext

CENT = Decimal('0.01')
ONE = Decimal(1)
BASE_WEIGHTS = {'price': Decimal('.45'), 'delivery': Decimal('.20'),
                'quality': Decimal('.20'), 'risk': Decimal('.15')}


def _number(value, field, minimum=0):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f'{field} bukan angka yang valid.') from exc
    if not n.is_finite() or n < minimum or n > Decimal('1e15'):
        raise ValueError(f'{field} di luar rentang.')
    return n


def _integer(value, field, minimum=0, maximum=1000000):
    n = _number(value, field, minimum)
    if n != int(n) or n > maximum:
        raise ValueError(f'{field} harus bilangan bulat dalam rentang {minimum}–{maximum}.')
    return int(n)


def _money(value, rounding=ROUND_HALF_UP):
    return value.quantize(CENT, rounding=rounding)


def _fraction(value, field, maximum=ONE):
    n = _number(value, field)
    if n > maximum:
        raise ValueError(f'{field} harus antara 0 dan {maximum}.')
    return n


def _offer_trace(opening, floor, buyer_cap, concession_fraction):
    """A seller considers its own floor; each buyer bid stays within its own ceiling."""
    events = []

    def add(round_no, speaker, action, amount, reason):
        events.append({'round': round_no, 'speaker': speaker, 'action': action,
                       'amount': float(amount), 'reason': reason})

    ask = opening
    last_bid = Decimal(0)
    add(0, 'vendor', 'opening', ask, 'Penawaran awal berdasarkan biaya dan aturan margin vendor.')
    for round_no, buyer_factor in enumerate((Decimal('.90'), Decimal('.96'), ONE), 1):
        bid = max(last_bid, min(buyer_cap, _money(ask * buyer_factor, ROUND_FLOOR)))
        last_bid = bid
        add(round_no, 'buyer', 'counter', bid, 'Tawar balik pembeli dibatasi anggaran pengadaan.')
        if bid >= floor:
            add(round_no, 'vendor', 'accept', bid, 'Tawaran memenuhi batas harga vendor.')
            return events, bid
        # Progressive concession: preserve the configured commercial floor.
        ask = floor if round_no == 3 else max(floor, _money(floor + (ask - floor) * concession_fraction, ROUND_CEILING))
        add(round_no, 'vendor', 'counter', ask, 'Tawaran pembeli belum memenuhi lantai harga; vendor mengajukan harga balik.')
        if round_no == 3:
            if ask <= buyer_cap:
                add(round_no, 'buyer', 'accept', ask, 'Tawaran balik terakhir masih dalam anggaran pembeli.')
                return events, ask
            add(round_no, 'buyer', 'reject', ask, 'Anggaran pembeli lebih rendah daripada harga minimum vendor.')
    return events, None


def negotiate(vendors, budget, quantity, horizon_months=0, *, deadline_days=None,
              payment_days=30, weights=None):
    """Calculate compliant offers, forecast costs, trace negotiations and rank agreements.

    Currency is the configured simulation currency. `shipping_cost` and
    `overhead_cost` are order totals; labor and material are per-unit.
    `min_margin` is gross contribution / revenue, not markup on cost.
    Working capital assumes the vendor advances the full cost before payment.
    Forecasts use a fixed monthly compound change; no real-world prices are queried.
    """
    with localcontext() as ctx:
        ctx.prec = 60
        return _negotiate(vendors, budget, quantity, horizon_months, deadline_days, payment_days, weights)


def _negotiate(vendors, budget, quantity, horizon_months, deadline_days, payment_days, weights):
    qty = _integer(quantity, 'quantity', 1)
    horizon = _integer(horizon_months, 'horizon_months', 0, 24)
    payment = _integer(payment_days, 'payment_days', 0, 365)
    deadline = None if deadline_days is None else _integer(deadline_days, 'deadline_days', 1, 365)
    buyer_cap = _money(_number(budget, 'budget'), ROUND_FLOOR)
    if buyer_cap <= 0:
        raise ValueError('Anggaran harus lebih besar dari nol.')
    if weights is None:
        weights = BASE_WEIGHTS
    if set(weights) != set(BASE_WEIGHTS):
        raise ValueError('Bobot harus mencakup harga, pengiriman, kualitas, dan risiko.')
    weights = {k: _number(v, f'weights.{k}') for k, v in weights.items()}
    total_weight = sum(weights.values())
    if not total_weight:
        raise ValueError('Bobot harus memiliki jumlah positif.')
    weights = {k: v / total_weight for k, v in weights.items()}
    rows, floors, agreements = [], [], []
    seen = set()
    for v in vendors:
        vendor_id = str(v['vendor_id'])
        if not vendor_id or vendor_id in seen:
            raise ValueError('ID vendor harus berbeda dan tidak kosong.')
        seen.add(vendor_id)
        unit_now = _money(_number(v['unit_cost_now'], 'unit_cost_now'))
        change = _number(v['monthly_cost_change'], 'monthly_cost_change', Decimal('-.95'))
        if change > ONE:
            raise ValueError('Kenaikan biaya bulanan melebihi batas skenario.')
        labor_unit = _money(_number(v['labor_cost_per_unit'], 'labor_cost_per_unit'))
        shipping = _money(_number(v['shipping_cost'], 'shipping_cost'))
        overhead = _money(_number(v.get('overhead_cost', 0), 'overhead_cost'))
        margin = _fraction(v['min_margin'], 'min_margin', Decimal('.95'))
        open_margin = _fraction(v['opening_margin'], 'opening_margin', Decimal('.95'))
        discount = _fraction(v.get('max_discount', 1), 'max_discount')
        concession = _fraction(v.get('concession_fraction', '.45'), 'concession_fraction')
        if open_margin < margin:
            raise ValueError('Margin penawaran awal tidak boleh lebih rendah dari margin minimum.')
        working_capital = _money(_number(v['working_capital'], 'working_capital'))
        capacity = _integer(v['capacity'], 'capacity')
        delivery_days = _integer(v['delivery_days'], 'delivery_days', 1, 365)
        max_payment = _integer(v['max_payment_days'], 'max_payment_days', 0, 365)
        min_payment = _integer(v.get('min_payment_days', 0), 'min_payment_days', 0, max_payment)
        quality = _fraction(v['quality'], 'quality')
        risk = _fraction(v['risk'], 'risk')
        # Round each total cost component first so displayed components reconcile exactly.
        future_unit = _money(unit_now * ((ONE + change) ** horizon))
        goods = _money(future_unit * qty)
        wages = _money(labor_unit * qty)
        total_cost = goods + wages + shipping + overhead
        if total_cost <= 0:
            raise ValueError('Biaya vendor harus positif.')
        vendor_floor = _money(total_cost / (ONE - margin), ROUND_CEILING)
        opening = _money(total_cost / (ONE - open_margin), ROUND_CEILING)
        floor = max(vendor_floor, _money(opening * (ONE - discount), ROUND_CEILING))
        constraints = []
        if qty > capacity:
            constraints.append('Kapasitas vendor kurang.')
        if total_cost > working_capital:
            constraints.append('Modal kerja vendor kurang untuk mendanai biaya pesanan.')
        if deadline is not None and delivery_days > deadline:
            constraints.append('Waktu kirim melampaui tenggat pembeli.')
        if not min_payment <= payment <= max_payment:
            constraints.append('Usulan termin di luar batas vendor.')
        row = {**v, 'vendor_id': vendor_id, 'vendor': str(v['vendor']),
               'costs': {'unit_cost_now': float(unit_now), 'unit_cost_forecast': float(future_unit),
                         'monthly_cost_change': float(change), 'goods_total': float(goods),
                         'labor_cost_per_unit': float(labor_unit), 'labor_total': float(wages),
                         'shipping_cost': float(shipping), 'overhead_cost': float(overhead), 'total_cost': float(total_cost)},
               'vendor_floor': float(vendor_floor), 'effective_floor': float(floor), 'opening_offer': float(opening),
               'final_offer': None, 'constraints': constraints, 'rounds': [], 'score': None, 'score_components': None,
               'status': 'ineligible', 'profit': None, 'realized_margin': None, 'budget_gap': None,
               'concession_fraction': float(concession)}
        if not constraints:
            floors.append(floor)
            row['budget_gap'] = float(max(Decimal(0), floor - buyer_cap))
            trace, final = _offer_trace(opening, floor, buyer_cap, concession)
            row['rounds'] = trace
            row['status'] = 'budget_conflict' if final is None else 'accepted'
            if final is not None:
                row['final_offer'] = float(final)
                row['profit'] = float(final - total_cost)
                row['realized_margin'] = float((final - total_cost) / final)
                agreements.append((row, final, delivery_days, quality, risk))
        rows.append(row)

    recommended = None
    if agreements:
        cheapest = min(a[1] for a in agreements)
        fastest = min(a[2] for a in agreements)
        for row, final, lead, quality, risk in agreements:
            components = {'price': cheapest / final, 'delivery': Decimal(fastest) / Decimal(lead),
                          'quality': quality, 'risk': ONE - risk}
            row['score_components'] = {k: float(v) for k, v in components.items()}
            row['weighted_components'] = {k: float(weights[k] * v * 100) for k, v in components.items()}
            row['score'] = float(sum(weights[k] * v for k, v in components.items()) * 100)
        recommended = min((a[0] for a in agreements), key=lambda r: (-r['score'], r['final_offer'], r['vendor_id']))
    minimum = min(floors) if floors else None
    return {'budget': float(buyer_cap), 'quantity': qty, 'horizon_months': horizon,
            'deadline_days': deadline, 'payment_days': payment,
            'minimum_budget': float(minimum) if minimum is not None else None,
            'minimum_budget_gap': float(max(Decimal(0), minimum - buyer_cap)) if minimum is not None else None,
            'weights': {k: float(v) for k, v in weights.items()},
            'status': 'agreement' if recommended else ('budget_conflict' if minimum is not None else 'no_feasible_vendor'),
            'recommended': recommended, 'vendors': rows}
