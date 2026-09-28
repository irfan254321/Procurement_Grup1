"""Struktur data yang dipakai bersama oleh lingkungan dan agen."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Vendor:
    name: str
    price: int
    transport: int
    risk: int
    quality: int
    lead_days: int
    capacity: int
    reputation: float


@dataclass(frozen=True)
class Scenario:
    quantity: int = 1000
    urgent_quantity: int = 700
    budget: int = 100_000_000
    deadline_days: int = 10
    cash: int = 150_000_000
    other_payment_1: int = 40_000_000
    other_payment_2: int = 30_000_000
    minimum_cash: int = 0
    new_cash_month_2: int = 0
    discount_b: float = 0.02
    negotiated_b: int = 89_500
    negotiated_a: int = 95_000
    discount_window_days: int = 7


VENDORS = (
    Vendor("A", 100_000, 5_000, 2_000, 8, 5, 800, 8),
    Vendor("B", 90_000, 7_000, 5_000, 9, 7, 1200, 8),
    Vendor("C", 110_000, 4_000, 1_000, 7, 3, 600, 6),
)
