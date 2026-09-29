# PANDUAN MAHASISWA: Pengatur tahapan simulator lama: membuat keadaan pasar, melangkah antar agen, lalu menyelesaikan laporan.
"""Mesin tahap: satu pemanggilan advance() mengeksekusi tepat satu keputusan."""
import json
import random
from dataclasses import asdict

from .agents import ire, vmi
from .environment import assess
from .models import Scenario, Vendor, VENDORS
from .reporting import make_summary
from .storage import get_run


STAGES = (
    ("Intake", "IRE"),
    ("Pembaruan pasar", "VMI"),
    ("Pilihan awal", "VMI"),
    ("Negosiasi", "DA"),
    ("Pemeriksaan awal", "SLM"),
    ("Deteksi konflik", "SLM + IRE"),
    ("Pembaruan pasar dan usulan bertahap", "VMI + DA"),
    ("Konsensus akhir", "IRE + VMI + DA + SLM"),
)


def market(vendors: tuple[Vendor, ...], seed: int, volatility: float, round_no: int) -> tuple[Vendor, ...]:
    """Setiap vendor mendapat perubahan harga/kapasitas/waktu sendiri; seed menjamin hasil ulang sama."""
    if not 0 <= volatility <= 0.5:
        raise ValueError("Volatilitas harus di antara 0 dan 0,5")
    if volatility == 0:
        return vendors
    result = []
    for index, v in enumerate(vendors):
        rng = random.Random(f"{seed}:{round_no}:{index}")
        price = round(v.price * (1 + rng.uniform(-volatility, volatility)))
        capacity = max(0, round(v.capacity * (1 + rng.uniform(-volatility, volatility))))
        lead = max(1, v.lead_days + rng.choice((-1, 0, 1)))
        result.append(Vendor(v.name, price, v.transport, v.risk, v.quality,
                             lead, capacity, v.reputation))
    return tuple(result)


def _vendors(db, run_id: int, round_no: int) -> tuple[Vendor, ...]:
    rows = db.execute("SELECT * FROM vendor_snapshots WHERE run_id=? AND round=? ORDER BY vendor",
                      (run_id, round_no)).fetchall()
    if len(rows) != len(VENDORS):
        raise RuntimeError("Snapshot vendor belum tersedia")
    base = {v.name: v for v in VENDORS}
    return tuple(Vendor(r["vendor"], r["price"], base[r["vendor"]].transport,
                        base[r["vendor"]].risk, base[r["vendor"]].quality,
                        r["lead_days"], r["capacity"], base[r["vendor"]].reputation)
                 for r in rows)


def _assessment_data(item):
    return {**asdict(item), "feasible": item.feasible}


def advance(db, run_id: int) -> dict:
    """Ambil state dari database, hitung satu tahap, simpan event dan lanjutkan posisi."""
    run = get_run(db, run_id)
    if run is None:
        raise ValueError("Run tidak ditemukan")
    step = run["step"] + 1
    if step > len(STAGES):
        raise ValueError("Run sudah selesai")
    s = Scenario(**json.loads(run["scenario_json"]))
    stage, agent = STAGES[step - 1]
    data = {}
    if step == 1:
        data = ire(s)
        explanation = (f"IRE memvalidasi {s.quantity} unit; {s.urgent_quantity} perlu bulan pertama. "
                       f"Prioritas {data['priority']}/100.")
    elif step == 2:
        offers = market(VENDORS, run["seed"], run["volatility"], 1)
        data = {"ranking": vmi(s, offers), "offers": [asdict(v) for v in offers]}
        explanation = "VMI memotret penawaran tiap vendor dan memeriksa peringkat, kapasitas, serta waktu kirim."
    elif step == 3:
        offers = _vendors(db, run_id, 1)
        eligible = [v for v in offers if v.capacity >= s.quantity and v.lead_days <= s.deadline_days]
        chosen = min(eligible, key=lambda v: v.price + v.transport + v.risk) if eligible else None
        data = {"chosen": chosen.name if chosen else None}
        explanation = (f"VMI memilih Vendor {chosen.name} untuk seluruh unit berdasarkan biaya sebelum negosiasi."
                       if chosen else "Tidak ada vendor tunggal yang memenuhi kapasitas dan tenggat; perlu alokasi alternatif.")
    elif step == 4:
        offers = _vendors(db, run_id, 1)
        chosen = json.loads(db.execute("SELECT data_json FROM events WHERE run_id=? AND step=3", (run_id,)).fetchone()[0])["chosen"]
        vendor = next((v for v in offers if v.name == chosen), None)
        base = next((v for v in VENDORS if v.name == chosen), None)
        target = {"A": s.negotiated_a, "B": s.negotiated_b}.get(chosen, base.price if base else 0)
        price = max(0, target + vendor.price - base.price) if vendor else None
        discount = s.discount_b if chosen == "B" else 0
        data = {"chosen": chosen, "price": price, "discount": discount}
        explanation = (f"DA menawar {chosen} menjadi Rp {price:,.0f}/unit; diskon bayar cepat {discount:.1%}."
                       if chosen else "Tidak ada vendor tunggal untuk dinegosiasikan; proses lanjut ke evaluasi revisi.")
    elif step == 5:
        offers = _vendors(db, run_id, 1)
        deal = json.loads(db.execute("SELECT data_json FROM events WHERE run_id=? AND step=4", (run_id,)).fetchone()[0])
        vendor = next((v for v in offers if v.name == deal["chosen"]), None)
        allocations = ((vendor, s.quantity, 1, deal["price"], deal["discount"]),) if vendor else ()
        item = assess(s, allocations, offers)
        data = _assessment_data(item)
        explanation = f"SLM menghitung total Rp {item.total_cost:,.0f} dan kas bulan 1 Rp {item.cash_month_1:,.0f}."
    elif step == 6:
        prior = db.execute("SELECT data_json FROM events WHERE run_id=? AND step=5", (run_id,)).fetchone()
        initial = json.loads(prior[0])
        data = {"initial_violations": initial["violations"], "revision_needed": not initial["feasible"]}
        explanation = ("Konflik ditemukan: " + "; ".join(initial["violations"])
                       if data["revision_needed"] else "Usulan awal memenuhi kendala; evaluasi alternatif tetap dicatat.")
    elif step == 7:
        offers = market(VENDORS, run["seed"], run["volatility"], 2)
        a, b, _ = offers
        price_b = max(0, s.negotiated_b + b.price - VENDORS[1].price)
        price_a = max(0, s.negotiated_a + a.price - VENDORS[0].price)
        item = assess(s, ((b, s.urgent_quantity, 1, price_b, s.discount_b),
                          (a, s.quantity - s.urgent_quantity, 2, price_a, 0)), offers)
        data = {"assessment": _assessment_data(item), "offers": [asdict(v) for v in offers],
                "price_a": price_a, "price_b": price_b}
        explanation = (f"VMI/DA menguji {s.urgent_quantity} B bulan 1 + "
                       f"{s.quantity-s.urgent_quantity} A bulan 2; total Rp {item.total_cost:,.0f}.")
    else:
        initial = json.loads(db.execute("SELECT data_json FROM events WHERE run_id=? AND step=5", (run_id,)).fetchone()[0])
        staged = json.loads(db.execute("SELECT data_json FROM events WHERE run_id=? AND step=7", (run_id,)).fetchone()[0])["assessment"]
        chosen = "bertahap" if staged["feasible"] else "awal" if initial["feasible"] else None
        data = {"approved": chosen is not None, "chosen": chosen,
                "initial_violations": initial["violations"], "staged_violations": staged["violations"]}
        explanation = (f"Konsensus: skenario {chosen} layak sebagai rekomendasi."
                       if chosen else "Belum ada skenario layak. Agen meminta revisi; pengadaan belum disetujui.")
    with db:
        if step in (2, 7):
            for offer in data["offers"]:
                db.execute("INSERT INTO vendor_snapshots VALUES (?, ?, ?, ?, ?, ?)",
                           (run_id, 1 if step == 2 else 2, offer["name"], offer["price"],
                            offer["capacity"], offer["lead_days"]))
        db.execute("INSERT INTO events(run_id,step,stage,agent,explanation,data_json) VALUES (?,?,?,?,?,?)",
                   (run_id, step, stage, agent, explanation, json.dumps(data)))
        db.execute("UPDATE runs SET step=?, status=? WHERE id=?",
                   (step, "selesai" if step == len(STAGES) else "berjalan", run_id))
        if step == len(STAGES):
            summary = make_summary(initial, staged, data)
            db.execute("INSERT OR REPLACE INTO reports(run_id, summary_json) VALUES (?, ?)",
                       (run_id, json.dumps(summary)))
    return {"step": step, "stage": stage, "agent": agent, "explanation": explanation, "data": data}


def finish(db, run_id: int) -> list[dict]:
    """Jalankan semua tahap tersisa secara otomatis."""
    results = []
    while get_run(db, run_id)["step"] < len(STAGES):
        results.append(advance(db, run_id))
    return results
