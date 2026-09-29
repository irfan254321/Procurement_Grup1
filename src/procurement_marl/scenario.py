# PANDUAN MAHASISWA: Mendefinisikan Vendor/Scenario, memuat YAML BAB 6, menghitung skor dan membuat sampel latihan.
"""Vendor and Scenario dataclasses, composite vendor score, random scenario generator."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import yaml

from .costs import batch_total

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@dataclass(frozen=True)
class Vendor:
    """Satu pemasok; frozen mencegah perubahan data awal di tengah episode."""
    name: str
    list_price: int
    transport: int
    risk: int
    quality: int            # 0-10
    lead_time: int          # days
    capacity: int           # units
    initial_offer: int      # price after DA "penawaran_awal"
    floor_price: int        # price after an accepted "penawaran_balik"
    discount_pct: int       # fast-payment discount, in percent
    reputation: float       # 0-10
    relation: float         # 0-1, changes during an episode


@dataclass(frozen=True)
class Scenario:
    """Input lengkap untuk satu episode, termasuk arus kas dan batas vendor."""
    quantity: int
    urgent_quantity: int
    budget: int
    deadline_days: int
    vendors: tuple[Vendor, ...]
    initial_cash: int
    other_needs: tuple[int, ...]    # per month
    inflows: tuple[int, ...]        # per month
    min_cash: int
    enforce_min_cash: bool
    min_composite_score: float
    score_weights: dict[str, float]

    @property
    def horizon(self) -> int:
        return len(self.other_needs)

    def vendor(self, name: str) -> Vendor:
        return next(v for v in self.vendors if v.name == name)


def _read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_scenario(path: str | Path = CONFIG_DIR / "report_scenario.yaml") -> Scenario:
    """Load a scenario from YAML (default: the report fixture)."""
    d = _read_yaml(Path(path))
    vendors = tuple(Vendor(name=name, **v) for name, v in d["vendors"].items())
    return Scenario(
        quantity=d["request"]["quantity"],
        urgent_quantity=d["request"]["urgent_quantity"],
        budget=d["request"]["budget"],
        deadline_days=d["request"]["deadline_days"],
        vendors=vendors,
        initial_cash=d["cash"]["initial"],
        other_needs=tuple(d["cash"]["other_needs"]),
        inflows=tuple(d["cash"]["inflow"]),
        min_cash=d["cash"]["min_cash"],
        enforce_min_cash=d["cash"]["enforce_min_cash"],
        min_composite_score=d["scoring"]["min_composite_score"],
        score_weights=d["scoring"]["weights"],
    )


def composite_scores(scenario: Scenario) -> dict[str, float]:
    """Composite score per vendor, 0-10. Scored over all vendors, before any masking."""
    # Harga dinormalisasi relatif terhadap daftar vendor pada skenario ini;
    # skor komposit bukan biaya transaksi setelah negosiasi.
    w = scenario.score_weights
    prices = [v.list_price for v in scenario.vendors]
    p_min, p_max = min(prices), max(prices)
    scores = {}
    for v in scenario.vendors:
        delivery = min(10.0, max(0.0, 10 * (1 - v.lead_time / scenario.deadline_days)))
        price = 10.0 if p_max == p_min else 10 * (p_max - v.list_price) / (p_max - p_min)
        scores[v.name] = (
            w["quality"] * v.quality
            + w["delivery"] * delivery
            + w["reputation"] * v.reputation
            + w["price"] * price
        )
    return scores


def eligible_vendors(scenario: Scenario) -> list[str]:
    """Vendors whose score is at least the threshold. If none, keep the best one."""
    scores = composite_scores(scenario)
    keep = [name for name, s in scores.items() if s >= scenario.min_composite_score]
    return keep or [max(scores, key=scores.get)]


def score_fallback(scenario: Scenario) -> bool:
    """True if no vendor reaches the score threshold, so `eligible_vendors` keeps the best one anyway."""
    return all(s < scenario.min_composite_score for s in composite_scores(scenario).values())


def cash_diagnosis(scenario: Scenario) -> dict[str, int | str | bool]:
    """Cash-only lower bound: can the request be paid for at all within the cash horizon?

    The cheapest possible bill is the whole request at the best vendor's floor price with the fast-payment
    discount (capacity and lead time ignored, so it is a true lower bound). Every payment falls inside the
    horizon, so if cash over the whole horizon is below that bill plus the required reserve,
    the last month must end below the minimum.
    `shortfall > 0` proves the scenario cannot reach consensus; `shortfall <= 0` proves nothing.
    """
    # Batas bawah boleh mengabaikan kapasitas/tenggat, sebab tujuannya hanya
    # membuktikan kekurangan dana: jika harga paling murah pun tak terbayar,
    # semua rencana yang lebih mahal juga tak terbayar.
    def bill(v: Vendor) -> int:
        return batch_total(scenario.quantity, v.floor_price, v.transport, v.risk, v.discount_pct)

    cheapest = min(scenario.vendors, key=bill)
    # Dana untuk pembelian harus menyisakan saldo minimum bila itu syarat wajib.
    reserve = scenario.min_cash if scenario.enforce_min_cash else 0
    available = scenario.initial_cash + sum(scenario.inflows) - sum(scenario.other_needs) - reserve
    lower_bound = bill(cheapest)
    return {"vendor": cheapest.name, "lower_bound": lower_bound, "available": available,
            "shortfall": max(0, lower_bound - available), "infeasible": lower_bound > available}


def sample_scenario(seed: int, config_path: str | Path = CONFIG_DIR / "env_default.yaml") -> Scenario:
    """Random training scenario around the report fixture. Same seed, same scenario.

    The feasibility filter (>= 80% feasible) is added in phase 2 with oracle.py.
    """
    # random.Random(seed) membuat profil latihan yang sama muncul lagi
    # pada seed sama; perubahan vendor tidak diketik manual setiap episode.
    rng = random.Random(seed)
    cfg = _read_yaml(Path(config_path))["randomization"]
    base = load_scenario()
    jitter = cfg["vendor_jitter"]

    def j(x: int, minimum: int = 1) -> int:
        return max(minimum, round(x * rng.uniform(1 - jitter, 1 + jitter)))

    vendors = []
    for v in base.vendors:
        f = rng.uniform(1 - jitter, 1 + jitter)   # same factor keeps floor <= offer <= list
        vendors.append(Vendor(
            name=v.name,
            list_price=round(v.list_price * f),
            transport=j(v.transport),
            risk=j(v.risk),
            quality=v.quality,
            lead_time=j(v.lead_time),
            capacity=j(v.capacity),
            initial_offer=round(v.initial_offer * f),
            floor_price=round(v.floor_price * f),
            discount_pct=v.discount_pct,
            reputation=v.reputation,
            relation=round(rng.uniform(*cfg["relation"]), 2),
        ))

    quantity = rng.randint(*cfg["quantity"])
    other_month1 = rng.randrange(cfg["other_needs_month1"][0], cfg["other_needs_month1"][1] + 1, 1_000_000)
    force_infeasible = rng.random() < cfg.get("infeasible_share", 0.0)
    if force_infeasible:
        # Batas bawah dihitung dengan asumsi paling optimistis. Kas sengaja
        # dibuat lebih rendah 5–30 juta agar label latihan benar-benar terbukti.
        lower_bound = min(batch_total(quantity, v.floor_price, v.transport, v.risk, v.discount_pct)
                          for v in vendors)
        shortfall = rng.randrange(5_000_000, 30_000_001, 1_000_000)
        reserve = cfg["min_cash"] if cfg["enforce_min_cash"] else 0
        initial_cash = max(1_000_000, other_month1 + lower_bound + reserve - shortfall)
        inflows = (0, 0, 0, 0)
    else:
        initial_cash = rng.randrange(cfg["initial_cash"][0], cfg["initial_cash"][1] + 1, 1_000_000)
        inflows = (0,) + tuple(
            rng.randrange(cfg["inflow_months_2_to_4"][0], cfg["inflow_months_2_to_4"][1] + 1, 1_000_000)
            for _ in range(3)
        )
    return Scenario(
        quantity=quantity,
        urgent_quantity=round(quantity * rng.uniform(*cfg["urgent_share"])),
        budget=quantity * rng.randrange(cfg["budget_per_unit"][0], cfg["budget_per_unit"][1] + 1, 1000),
        deadline_days=rng.randint(*cfg["deadline_days"]),
        vendors=tuple(vendors),
        initial_cash=initial_cash,
        other_needs=(other_month1, 0, 0, 0),
        inflows=inflows,
        min_cash=cfg["min_cash"],
        enforce_min_cash=cfg["enforce_min_cash"],
        min_composite_score=base.min_composite_score,
        score_weights=base.score_weights,
    )
