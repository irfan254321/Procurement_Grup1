"""Agen vendor berbasis utilitas untuk negosiasi harga dan termin.

Vendor bukan policy MARL pembeli. Mereka merupakan lawan negosiasi otonom
yang menjaga harga minimum, menghitung tekanan kapasitas, relasi, volume,
dan kompetisi sebelum memberi counter offer atau bertahan.
"""
from __future__ import annotations

from dataclasses import dataclass

from .scenario import Scenario, Vendor


@dataclass(frozen=True)
class VendorProfile:
    concession_speed: float
    capacity_pressure: float
    competition_response: float
    relationship_weight: float
    term_flexibility: float


DEFAULT_PROFILES = {
    "A": VendorProfile(0.45, 0.30, 0.20, 0.25, 0.55),
    "B": VendorProfile(0.28, 0.45, 0.12, 0.30, 0.45),
    "C": VendorProfile(0.60, 0.20, 0.30, 0.20, 0.70),
}


class VendorNegotiator:
    """Menghasilkan keputusan vendor yang dapat dijelaskan dan direproduksi."""

    def __init__(self, scenario: Scenario, max_rounds: int = 3):
        self.scenario = scenario
        self.max_rounds = max_rounds

    def profile(self, vendor: Vendor) -> VendorProfile:
        return DEFAULT_PROFILES.get(vendor.name, VendorProfile(0.4, 0.3, 0.2, 0.25, 0.5))

    def opening_offer(self, vendor: Vendor, qty: int, relation: float,
                      competitors: int) -> dict:
        """Vendor memberi penawaran awal sendiri, tetap di atas harga minimum."""
        offer = max(vendor.floor_price, min(vendor.list_price, vendor.initial_offer))
        margin = max(vendor.list_price - vendor.floor_price, 1)
        utility = ((offer - vendor.floor_price) / margin * 0.55
                   + relation * 0.25
                   + min(qty / max(vendor.capacity, 1), 1.0) * 0.10
                   + max(0, 2 - competitors) * 0.05)
        return {
            "event": "vendor_opening_offer", "vendor": vendor.name,
            "list_price": vendor.list_price, "offer": offer,
            "floor_price": vendor.floor_price, "utility": round(utility, 4),
            "decision": "beri_penawaran_awal",
        }

    def negotiate_price(self, vendor: Vendor, qty: int, relation: float,
                        competitors: int, urgent_share: float,
                        opening_override: int | None = None) -> tuple[int, bool, list[dict]]:
        """Jalankan beberapa ronde tawar-menawar sampai sepakat atau bertahan.

        ``floor_price`` selalu menjadi batas keras. Harga reservasi dapat lebih
        tinggi saat kapasitas penuh atau relasi lemah, sehingga vendor tidak
        otomatis memberikan harga terendahnya.
        """
        p = self.profile(vendor)
        opening = max(vendor.floor_price, min(vendor.list_price,
                     vendor.initial_offer if opening_override is None else opening_override))
        margin = max(opening - vendor.floor_price, 0)
        load = min(qty / max(vendor.capacity, 1), 1.5)
        pressure = (p.capacity_pressure * load + p.relationship_weight * (1 - relation)
                    - p.competition_response * min(competitors, 2) / 2)
        reservation = vendor.floor_price + round(margin * min(0.90, max(0.05, pressure)))
        reservation = max(vendor.floor_price, min(opening, reservation))

        transcript: list[dict] = []
        if margin == 0:
            transcript.append({
                "event": "vendor_counter_offer", "vendor": vendor.name,
                "negotiation_round": 1, "buyer_offer": vendor.floor_price,
                "vendor_offer": opening, "reservation_price": reservation,
                "utility": round(relation * p.relationship_weight + load * 0.1, 4),
                "decision": "sepakat", "accepted": True,
            })
            return opening, True, transcript

        final_offer = opening
        accepted = False
        for negotiation_round in range(1, self.max_rounds + 1):
            progress = negotiation_round / self.max_rounds
            concession_progress = min(1.0, progress * (0.65 + p.concession_speed))
            vendor_offer = round(opening - (opening - reservation) * concession_progress)
            buyer_progress = min(1.0, progress * (0.70 + 0.25 * urgent_share))
            buyer_offer = round(vendor.floor_price + (opening - vendor.floor_price) * buyer_progress)
            agreed = buyer_offer >= vendor_offer
            final_offer = max(reservation, min(opening, vendor_offer))
            price_utility = (final_offer - vendor.floor_price) / max(vendor.list_price - vendor.floor_price, 1)
            utility = (price_utility * 0.55 + relation * p.relationship_weight
                       + min(load, 1.0) * 0.10 + p.competition_response * min(competitors, 2) * 0.05)
            transcript.append({
                "event": "vendor_counter_offer", "vendor": vendor.name,
                "negotiation_round": negotiation_round, "buyer_offer": buyer_offer,
                "vendor_offer": final_offer, "reservation_price": reservation,
                "utility": round(utility, 4),
                "decision": "sepakat" if agreed else "counter_offer", "accepted": agreed,
            })
            if agreed:
                accepted = True
                break
        return final_offer, accepted, transcript

    def term_probability(self, vendor: Vendor, qty: int, relation: float,
                         base_probability: float) -> tuple[float, float]:
        """Nilai utilitas termin lalu ubah menjadi peluang penerimaan."""
        p = self.profile(vendor)
        load = min(qty / max(vendor.capacity, 1), 1.0)
        utility = (0.45 * relation + 0.25 * p.term_flexibility
                   + 0.15 * (1 - load) + 0.15 * min(qty / 1000, 1.0))
        probability = min(0.95, max(0.05, 0.45 * base_probability + 0.55 * utility))
        return probability, utility
