# PANDUAN MAHASISWA: Lingkungan PettingZoo AEC: IRE, VMI, DA, dan SLM bergiliran; setiap aksi menghasilkan event dan reward.
"""PettingZoo AEC environment: four agents (IRE, VMI, DA, SLM) take turns.

One round = IRE picks how to split the request. Every eligible vendor then responds
to the same buyer request before VMI selects one, DA confirms or renegotiates its
price, and SLM picks the payment mode. After the last batch the
environment checks budget, cash and urgent units. If something is violated a new round
starts, subject to a configurable simulation limit. A simulation cycle is not one of
the six coordination stages in the report. Payment entries are proposed schedules,
not executed ERP payments. Every step is written to `env.log`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from gymnasium import spaces
from pettingzoo import AECEnv

from .costs import PAY_DUE, PAY_FAST, PAY_SPLIT, cash_balances, discount_amount, goods_value, payment_schedule
from .rewards import da_reward, ire_reward, slm_reward, team_reward, vmi_reward
from .scenario import (CONFIG_DIR, Scenario, cash_diagnosis, composite_scores, eligible_vendors,
                       ire_action_for_scenario, load_scenario, sample_scenario, score_fallback)
from .vendor_agents import VendorNegotiator

AGENTS = ["IRE", "VMI", "DA", "SLM"]
# Indeks dalam daftar aksi dipakai model sebagai angka 0, 1, ...; ubah urutan
# hanya jika model dilatih ulang, karena checkpoint menyimpan arti indeks lama.
VENDORS = ["A", "B", "C"]
IRE_ACTIONS = ["teruskan", "bagi_pesanan", "tunda", "minta_revisi"]
# Display labels (dashboard, trace). The internal action name stays so tests and checkpoints keep working.
IRE_LABELS = {"teruskan": "teruskan (semua unit mendesak bulan ini)",
              "bagi_pesanan": "bagi pesanan (tepat mendesak bulan ini, sisanya bulan depan)",
              "tunda": "tunda (seluruh permintaan ke bulan depan)",
              "minta_revisi": "minta revisi kebutuhan/pendanaan"}
DA_ACTIONS = ["penawaran_awal", "penawaran_balik", "minta_alternatif"]
SLM_ACTIONS = [PAY_FAST, PAY_DUE, PAY_SPLIT, "minta_revisi"]
ACTION_DIMS = {"IRE": 4, "VMI": 3, "DA": 3, "SLM": 4}
CONFLICT_KEYS = ["any", "budget", "cash", "urgent"]
DIMS = {"IRE": 8, "VMI": 22, "DA": 12, "SLM": 19}
STATE_DIM = sum(DIMS.values()) + 4 + 2
CASH_SCALE = 250_000_000
PRICE_SCALE = 150_000


def _clip01(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(min(hi, max(lo, x)))


def _bin5(x: float, lo: float, hi: float) -> int:
    """Discretize x into 5 levels (0..4) between lo and hi."""
    return int(_clip01((x - lo) / (hi - lo), 0.0, 0.999) * 5)


class ProcurementEnv(AECEnv):
    metadata = {"name": "procurement_v0", "is_parallelizable": False, "render_modes": []}

    def __init__(self, scenario: str | Scenario = "report", config_path: str | Path = CONFIG_DIR / "env_default.yaml"):
        super().__init__()
        self.scenario_mode = scenario
        self.config_path = Path(config_path)
        with open(self.config_path, encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.max_rounds = self.cfg["max_rounds"]
        self.max_steps = self.cfg["max_steps"]      # safety net: truncate the episode after this many steps
        self.stoch = dict(self.cfg["stochastic"])
        self.reward_cfg = self.cfg["reward"]
        self.weights = self.reward_cfg["weights"]
        self.possible_agents = list(AGENTS)
        self._obs_spaces = {
            a: spaces.Dict({
                "observation": spaces.Box(-1.0, 1.0, (DIMS[a],), dtype=np.float32),
                "action_mask": spaces.Box(0, 1, (ACTION_DIMS[a],), dtype=np.int8),
            })
            for a in AGENTS
        }
        self._act_spaces = {a: spaces.Discrete(ACTION_DIMS[a]) for a in AGENTS}
        self.state_space = spaces.Box(-1.0, 1.0, (STATE_DIM,), dtype=np.float32)
        self.rng = np.random.default_rng()

    def observation_space(self, agent: str):
        return self._obs_spaces[agent]

    def action_space(self, agent: str):
        return self._act_spaces[agent]

    # ------------------------------------------------------------------ reset
    def reset(self, seed: int | None = None, options: dict | None = None) -> None:
        """Mulai episode baru dan kosongkan keputusan, saldo, reward, serta jejak lama."""
        options = options or {}
        # Generator RNG lokal membuat respons acak dapat direproduksi dari seed.
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.scenario = options.get("scenario") or self._make_scenario()
        self.cash_diagnosis = cash_diagnosis(self.scenario)
        self.forced_draws = options.get("forced_draws")   # used by oracle.py
        self.draw_probs: list[float] = []
        self.relation = {v.name: v.relation for v in self.scenario.vendors}
        self.vendor_negotiator = VendorNegotiator(
            self.scenario, int(self.cfg.get("vendor_negotiation", {}).get("max_rounds", 3)))
        self.round = 1
        self.steps = 0
        self.was_truncated = False
        self.stop_reason: str | None = None
        self.stop_after_round = options.get("stop_after_round")
        self.stop_on_repeat = options.get("stop_on_repeat", True)
        self._previous_round_signature = None
        self.agreed_price: dict[str, int] = {}     # last price agreed with each vendor in this episode
        self.log: list[dict] = []
        self.conflict = dict.fromkeys(CONFLICT_KEYS, False)
        self.violations: list[str] = []
        self.agents = list(self.possible_agents)
        self.rewards = dict.fromkeys(self.agents, 0.0)
        self._cumulative_rewards = dict.fromkeys(self.agents, 0.0)
        self.terminations = dict.fromkeys(self.agents, False)
        self.truncations = dict.fromkeys(self.agents, False)
        self.infos = {a: {} for a in self.agents}
        self._skip_agent_selection = None
        self._start_round()

    def _make_scenario(self) -> Scenario:
        if isinstance(self.scenario_mode, Scenario):
            return self.scenario_mode
        if self.scenario_mode == "report":
            return load_scenario()
        return sample_scenario(int(self.rng.integers(2**31 - 1)), self.config_path)

    def _start_round(self) -> None:
        self.batches: list[dict] = []
        self.batch_idx = 0
        self.stage = "IRE"
        self.committed: dict[int, int] = {}     # month -> payments of finished batches this round
        self.agent_selection = "IRE"

    # ---------------------------------------------------------------- helpers
    @property
    def batch(self) -> dict | None:
        return self.batches[self.batch_idx] if self.batches and self.batch_idx < len(self.batches) else None

    def _p_accept(self, vendor: str) -> float:
        s = self.stoch
        if s["p_accept_override"] is not None:
            return s["p_accept_override"]
        return _clip01(s["accept_base"] + s["accept_slope"] * self.relation[vendor])

    def _p_termin(self, vendor: str) -> float:
        s = self.stoch
        if s["p_termin_override"] is not None:
            return s["p_termin_override"]
        return _clip01(s["termin_base"] + s["termin_slope"] * self.relation[vendor])

    def _draw(self, p: float) -> bool:
        """One random accept/reject draw. `forced_draws` lets the oracle enumerate outcomes."""
        self.draw_probs.append(p)
        if self.forced_draws is not None:
            i = len(self.draw_probs) - 1
            result = bool(self.forced_draws[i]) if i < len(self.forced_draws) else False
            self.last_draw = {"probability": p, "random_value": None,
                              "forced": True, "result": result}
            return result
        value = float(self.rng.random())
        result = value < p
        self.last_draw = {"probability": p, "random_value": value,
                          "forced": False, "result": result}
        return result

    def _vendor_mask(self, batch: dict, extra_excluded: tuple[str, ...] = ()) -> tuple[list[bool], dict[str, str]]:
        """Which vendors VMI may pick for this batch, and why the others are masked."""
        sc = self.scenario
        eligible = eligible_vendors(sc)
        reasons: dict[str, str] = {}
        for v in sc.vendors:
            if v.name not in eligible:
                reasons[v.name] = "skor"
            elif v.capacity < batch["qty"]:
                reasons[v.name] = "kapasitas"
            elif batch["month"] == 1 and v.lead_time > sc.deadline_days:
                reasons[v.name] = "lead_time"
            elif v.name in batch["excluded"] or v.name in extra_excluded:
                reasons[v.name] = "dikecualikan"
        return [v.name not in reasons for v in sc.vendors], reasons

    def _fallback_vendor(self) -> str:
        """Vendor VMI is forced to take when no vendor fits a batch: the largest capacity (ties: first listed)."""
        return max(self.scenario.vendors, key=lambda v: v.capacity).name

    def _estimates(self, qty: int) -> dict[str, int]:
        """Bandingkan biaya total berdasarkan penawaran yang sudah diterima per batch."""
        return {
            v.name: qty * (self.batch["quotes"].get(v.name, {}).get(
                "price", self.agreed_price.get(v.name, v.initial_offer)) + v.transport + v.risk)
            for v in self.scenario.vendors
        }

    def _list_costs(self, qty: int) -> dict[str, int]:
        """Cost at list price, used as the reference in the VMI reward."""
        return {v.name: qty * (v.list_price + v.transport + v.risk) for v in self.scenario.vendors}

    def _projected_cash(self) -> list[int]:
        sc = self.scenario
        return cash_balances(sc.initial_cash, list(sc.inflows), list(sc.other_needs), self.committed)

    # ------------------------------------------------------------------- step
    def step(self, action: int | None) -> None:
        """Terima satu aksi dari agen yang sedang bergiliran, lalu pindah tahap."""
        agent = self.agent_selection
        if self.terminations[agent] or self.truncations[agent]:
            self._was_dead_step(action)
            return
        assert self.observe(agent)["action_mask"][action], f"{agent} took a masked action: {action}"
        self._cumulative_rewards[agent] = 0
        self._clear_rewards()
        getattr(self, f"_step_{self.stage.lower()}")(int(action))
        self.steps += 1
        if self.steps >= self.max_steps and not any(self.terminations.values()):
            self.truncations = dict.fromkeys(self.agents, True)
            self.was_truncated = True
            self.stage = "END"
            self.stop_reason = "step_limit"
            self._log(agent="ENV", event="episode_stopped", stop_reason=self.stop_reason)
        self._accumulate_rewards()

    def _log(self, **entry) -> None:
        self.log.append({"round": self.round, **entry})

    def _step_ire(self, a: int) -> None:
        sc = self.scenario
        rest = sc.quantity - sc.urgent_quantity

        if a == 3:
            # IRE tetap memiliki keputusan yang dipelajari: melanjutkan
            # pembagian wajib atau mengeskalasi bila kebutuhan/dana mustahil.
            self._finish_revision_request(None, requester="IRE")
            return

        def new(qty: int, month: int, urgent: int) -> dict:
            return {"qty": qty, "month": month, "urgent": urgent, "vendor": None, "price": None,
                    "excluded": set(), "alt_used": False, "counter_used": False, "da_failed": False, "cheapest": None,
                    "mode": None, "discount": 0, "schedule": {}, "no_vendor": False,
                    "alternative_reference": None, "alternative_no_benefit": False,
                    "quotes": {}}

        # Aksi IRE dibatasi oleh kebutuhan operasional, bukan preferensi
        # harga model: untuk input 600/500, tepat 500 unit bulan 1 dan 100
        # bulan 2. Model tetap berjalan pada tahap IRE, tetapi tak dapat
        # menggeser unit nonmendesak ke bulan 1 pada skenario ini.
        if a == 0:
            self.batches = [new(sc.quantity, 1, sc.urgent_quantity)]
        elif a == 1:
            self.batches = [new(sc.urgent_quantity, 1, sc.urgent_quantity), new(rest, 2, 0)]
        else:
            self.batches = [new(sc.quantity, 2, sc.urgent_quantity)]
        self._log(agent="IRE", action=IRE_ACTIONS[a],
                  batches=[{"qty": b["qty"], "month": b["month"]} for b in self.batches])
        self.batch_idx = 0
        self._begin_batch()

    def _begin_batch(self) -> None:
        self.stage, self.agent_selection = "VMI", "VMI"
        b = self.batch
        mask, _ = self._vendor_mask(b)
        self._log_vendor_screening(b)
        # Semua pemasok yang lolos menghadapi permintaan pembeli yang sama.
        # Simpan setiap respons sebelum VMI mengambil keputusan; urutan daftar
        # vendor tidak boleh membuat vendor yang tidak dipilih kehilangan kesempatan.
        for vendor, allowed in zip(self.scenario.vendors, mask):
            if not allowed:
                continue
            competitors = sum(mask) - 1
            opening = self.vendor_negotiator.opening_offer(
                vendor, b["qty"], self.relation[vendor.name], competitors)
            self._log(agent=f"VENDOR {vendor.name}", batch=self.batch_idx, **opening)
            price, accepted, transcript = self.vendor_negotiator.negotiate_price(
                vendor, b["qty"], self.relation[vendor.name], competitors,
                self.scenario.urgent_quantity / self.scenario.quantity)
            for response in transcript:
                self._log(agent=f"VENDOR {vendor.name}", batch=self.batch_idx, **response)
            b["quotes"][vendor.name] = {"price": price, "accepted": accepted,
                                           "opening": opening["offer"]}
            self._log(agent="DA", event="vendor_quote_ready", batch=self.batch_idx,
                      vendor=vendor.name, price=price, accepted=accepted,
                      landed_cost=b["qty"] * (price + vendor.transport + vendor.risk))
        if b["cheapest"] is None:
            costs = list(self._estimates(b["qty"]).values())
            b["cheapest"] = min([c for c, ok in zip(costs, mask) if ok] or costs)

    def _log_vendor_screening(self, batch: dict) -> None:
        """Catat pemeriksaan A/B/C satu per satu sebelum kebijakan VMI memilih."""
        scores = composite_scores(self.scenario)
        score_eligible = set(eligible_vendors(self.scenario))
        _, reasons = self._vendor_mask(batch)
        for vendor in self.scenario.vendors:
            checks = {
                "score": vendor.name in score_eligible,
                "capacity": vendor.capacity >= batch["qty"],
                "deadline": batch["month"] != 1 or vendor.lead_time <= self.scenario.deadline_days,
                "not_excluded": vendor.name not in batch["excluded"],
            }
            self._log(agent="VMI", event="vendor_check_start", batch=self.batch_idx,
                      vendor=vendor.name, checks=checks, score=scores[vendor.name])
            reason = reasons.get(vendor.name)
            failed_checks = [name for name, passed in checks.items() if not passed]
            self._log(agent="VMI", event="vendor_screening", batch=self.batch_idx,
                      vendor=vendor.name, passed=reason is None, reason=reason,
                      failed_checks=failed_checks, checks=checks, score=scores[vendor.name])

    def _step_vmi(self, a: int) -> None:
        b, v = self.batch, self.scenario.vendors[a]
        mask, reasons = self._vendor_mask(b)
        est = self._estimates(b["qty"])
        b["vendor"] = v.name
        b["no_vendor"] = not any(mask)
        self._log(agent="VMI", batch=self.batch_idx, action=f"vendor_{v.name}", vendor=v.name,
                  mask=mask, masked=reasons, estimates=est, estimate=est[v.name],
                  no_vendor_fits=b["no_vendor"], score_fallback=score_fallback(self.scenario))
        competitors = max(0, sum(mask) - 1)
        self._after_vendor_selection()

    def _after_vendor_selection(self) -> None:
        self.stage, self.agent_selection = "DA", "DA"

    def _step_da(self, a: int) -> None:
        b = self.batch
        v = self.scenario.vendor(b["vendor"])
        entry = dict(agent="DA", batch=self.batch_idx, action=DA_ACTIONS[a], vendor=v.name)
        if a == 2:   # ask VMI for an alternative, once per batch
            b["alt_used"] = True
            b["alternative_reference"] = b["qty"] * (
                b["quotes"].get(v.name, {}).get("price", v.initial_offer) + v.transport + v.risk)
            b["excluded"].add(v.name)
            b["vendor"] = None
            self._log(**entry, price=None)
            self._begin_batch()
            return
        if a == 0:
            b["price"] = b["quotes"].get(v.name, {}).get("price", v.initial_offer)
            self._log(**entry, price=b["price"], accepted=None, relation=self.relation[v.name])
        else:
            b["counter_used"] = True
            mask, _ = self._vendor_mask(b)
            competitors = max(0, sum(mask) - 1)
            price, accepted, transcript = self.vendor_negotiator.negotiate_price(
                v, b["qty"], self.relation[v.name], competitors,
                self.scenario.urgent_quantity / self.scenario.quantity,
                opening_override=b["quotes"].get(v.name, {}).get("price"))
            for response in transcript:
                self._log(agent=f"VENDOR {v.name}", batch=self.batch_idx, **response)
            b["price"] = price
            b["da_failed"] = not accepted
            if accepted:
                self.relation[v.name] = round(min(1.0, self.relation[v.name] + 0.02), 4)
            else:
                self.relation[v.name] = round(max(0.0, self.relation[v.name] - self.stoch["accept_relation_drop"] / 2), 4)
            # a vendor only walks away if another vendor can take the batch (avoids endless loops)
            can_replace = any(self._vendor_mask(b, extra_excluded=(v.name,))[0])
            withdrew = (not accepted) and self.relation[v.name] < self.stoch["withdraw_below"] and can_replace
            self._log(**entry, price=b["price"], accepted=accepted, relation=self.relation[v.name], withdrew=withdrew)
            if withdrew:   # vendor walks away, batch goes back to VMI
                b["excluded"].add(v.name)
                b["vendor"] = None
                b["price"] = None
                self._begin_batch()
                return
        self.agreed_price[v.name] = b["price"]
        if b.get("alternative_reference") is not None:
            selected_cost = b["qty"] * (b["price"] + v.transport + v.risk)
            b["alternative_no_benefit"] = selected_cost >= b["alternative_reference"]
        self._after_price_agreement()

    def _after_price_agreement(self) -> None:
        self.stage, self.agent_selection = "SLM", "SLM"

    def _negotiate_terms(self, vendor) -> tuple[str, bool]:
        """Vendor menilai permintaan SLM sebelum SLM membuat rekomendasi pembayaran.

        These delegated protocol events remain inside one AEC transition: the
        existing three policy actions and checkpoint observations stay compatible.
        Nilai utilitas, peluang penerimaan, dan proposal 50/50 adalah asumsi simulator.
        """
        probability, utility = self.vendor_negotiator.term_probability(
            vendor, self.batch["qty"], self.relation[vendor.name], self._p_termin(vendor.name))
        accepted = self._draw(probability)
        draw = dict(self.last_draw)
        mode = PAY_SPLIT if accepted else PAY_DUE
        if not accepted:
            self.relation[vendor.name] = round(
                max(0.0, self.relation[vendor.name] - self.stoch["termin_relation_drop"]), 4)
        self._log(agent=f"VENDOR {vendor.name}", event="term_response", action="negosiasi_termin",
                  batch=self.batch_idx, vendor=vendor.name, accepted=accepted,
                  mode=mode, relation=self.relation[vendor.name], utility=round(utility, 4),
                  probability=round(probability, 4), random_value=draw["random_value"],
                  forced_draw=draw["forced"])
        return mode, accepted

    def _step_slm(self, a: int) -> None:
        b = self.batch
        v = self.scenario.vendor(b["vendor"])
        if a == 3:
            self._finish_revision_request(v.name)
            return
        mode, accepted = SLM_ACTIONS[a], None
        if mode == PAY_SPLIT:
            self._log(agent="SLM", event="term_request", action=PAY_SPLIT,
                      batch=self.batch_idx, vendor=v.name)
            mode, accepted = self._negotiate_terms(v)
        pct = v.discount_pct if mode == PAY_FAST else 0
        value = goods_value(b["qty"], b["price"])
        disc = discount_amount(value, pct)
        b["mode"], b["discount"] = mode, disc
        b["schedule"] = payment_schedule(mode, b["month"], b["qty"], b["price"], v.transport, v.risk, pct)
        for m, amount in b["schedule"].items():
            self.committed[m] = self.committed.get(m, 0) + amount
        self._log(agent="SLM", event="payment_plan", batch=self.batch_idx,
                  action=SLM_ACTIONS[a], mode=mode, term_accepted=accepted,
                  vendor=v.name, price=b["price"], goods_value=value, discount=disc,
                  goods_after_discount=value - disc, logistics=b["qty"] * (v.transport + v.risk),
                  total=sum(b["schedule"].values()), schedule=dict(b["schedule"]),
                  cash=self._projected_cash())
        self._after_payment_plan()

    def _finish_revision_request(self, vendor: str | None, requester: str = "SLM") -> None:
        """IRE/SLM menghentikan rencana bila revisi input bisnis diperlukan."""
        diagnosis = self.cash_diagnosis
        proven = bool(diagnosis["infeasible"])
        self.stop_reason = "infeasible_proven" if proven else "revision_requested"
        violations = ["dana_tidak_cukup"] if proven else ["revisi_diminta"]
        rc = self.reward_cfg["team"]
        team = (rc["correct_infeasible"] + rc.get("agent_revision_bonus", 0.0)
                if proven else rc["premature_revision"])
        self.rewards = dict.fromkeys(self.agents, team)
        self.violations = violations
        self._log(agent=requester, event="revision_request", action="minta_revisi", vendor=vendor,
                  proven_infeasible=proven, available=diagnosis["available"],
                  lower_bound=diagnosis["lower_bound"], shortfall=diagnosis["shortfall"])
        self._log(agent="ENV", event="diagnosis", total=diagnosis["lower_bound"], cash=[],
                  violations=violations, warnings=[], consensus=False, done=True,
                  stop_reason=self.stop_reason, rewards=dict(self.rewards),
                  available=diagnosis["available"], shortfall=diagnosis["shortfall"])
        self.terminations = dict.fromkeys(self.agents, True)
        self.stage = "END"

    def _after_payment_plan(self) -> None:
        self.batch_idx += 1
        if self.batch_idx < len(self.batches):
            self._begin_batch()
        else:
            self._end_round()

    # ------------------------------------------------------------ round check
    def _round_stop_reason(self, consensus: bool, signature: tuple) -> str | None:
        if consensus:
            return "consensus"
        if self.cash_diagnosis["infeasible"]:
            return "infeasible_proven"
        if self.stop_after_round is not None and self.round >= self.stop_after_round:
            return "single_round_limit"
        if self.stop_on_repeat and signature == self._previous_round_signature:
            return "no_progress"
        if self.round >= self.max_rounds:
            return "cycle_limit"
        return None

    def _end_round(self) -> None:
        """Periksa rencana lengkap, catat pelanggaran, lalu putuskan lanjut/berhenti."""
        sc = self.scenario
        cash = self._projected_cash()
        total = sum(self.committed.values())
        urgent_met = all(
            b["month"] == 1 and sc.vendor(b["vendor"]).lead_time <= sc.deadline_days
            for b in self.batches if b["urgent"] > 0
        )
        below_min = any(k < sc.min_cash for k in cash)
        negative = any(k < 0 for k in cash)
        violations = []
        if negative:
            violations.append("kas_negatif")
        if total > sc.budget:
            violations.append("anggaran")
        if not urgent_met:
            violations.append("unit_mendesak")
        if any(b["no_vendor"] for b in self.batches):
            violations.append("tanpa_pemasok_layak")   # VMI was forced to take a vendor that does not fit
        if any(b["qty"] > sc.vendor(b["vendor"]).capacity for b in self.batches):
            violations.append("kapasitas")     # VMI mask is relaxed when nobody fits, so check here
        if sc.enforce_min_cash and below_min:
            violations.append("kas_minimum")
        warnings = ["kas_di_bawah_minimum"] if below_min and not sc.enforce_min_cash else []
        consensus = not violations
        signature = (
            tuple((b["qty"], b["month"], b["vendor"], b["price"], b["mode"],
                   b["discount"], b["no_vendor"], b["da_failed"]) for b in self.batches),
            tuple(sorted(self.committed.items())), tuple(violations),
        )
        self.stop_reason = self._round_stop_reason(consensus, signature)
        self._previous_round_signature = signature
        done = self.stop_reason is not None

        rc = self.reward_cfg
        n = len(self.batches)
        rew = {
            "IRE": ire_reward(urgent_met, 1 if self.round > 1 else 0, rc["ire"]["per_revision"]),
            "VMI": sum(vmi_reward(sc.vendor(b["vendor"]).quality,
                                  b["qty"] * (b["price"] + sc.vendor(b["vendor"]).transport
                                              + sc.vendor(b["vendor"]).risk), b["cheapest"])
                       for b in self.batches) / n,
            "DA": sum(da_reward(sc.vendor(b["vendor"]).list_price, b["price"], b["da_failed"],
                                rc["da"]["saving_scale"], rc["da"]["failed_negotiation"])
                      + (rc["da"].get("alternative_without_benefit", 0.0)
                         if b.get("alternative_no_benefit") else 0.0)
                      for b in self.batches) / n,
            "SLM": slm_reward(sum(b["discount"] for b in self.batches), sc.budget,
                              sc.enforce_min_cash and below_min, negative,
                              rc["slm"]["below_min_cash"], rc["slm"]["negative_cash"]),
        }
        cycle_penalty = rc["team"]["per_round"] * max(0, self.round - 1)
        rew = {a: r + cycle_penalty for a, r in rew.items()}
        if done:
            if consensus:
                team = rc["team"]["consensus"]
            elif self.stop_reason == "infeasible_proven":
                team = rc["team"]["correct_infeasible"]
            else:
                team = rc["team"]["no_consensus"]
            if total > sc.budget:
                team += rc["team"]["over_budget"]
            if self.stop_reason == "no_progress":
                team += rc["team"]["no_progress"]
            rew = {a: r + team for a, r in rew.items()}
        self.rewards = rew

        self._log(agent="ENV", event="cek_batasan", cash=cash, total=total, budget_left=sc.budget - total,
                  urgent_met=urgent_met, violations=violations, warnings=warnings, consensus=consensus,
                  done=done, stop_reason=self.stop_reason, rewards=dict(rew))
        self.violations = violations
        if done:
            self.terminations = dict.fromkeys(self.agents, True)
            self.stage = "END"
            return
        self.round += 1
        self.conflict = {"any": True, "budget": "anggaran" in violations,
                         "cash": "kas_negatif" in violations or "kas_minimum" in violations,
                         "urgent": "unit_mendesak" in violations}
        self._start_round()

    # ----------------------------------------------------------- observations
    def _conflict_vec(self) -> list[float]:
        return [float(self.conflict[k]) for k in CONFLICT_KEYS]

    def _mask(self, agent: str) -> list[bool]:
        if agent != self.stage_agent():
            return [True] * ACTION_DIMS[agent]
        sc, b = self.scenario, self.batch
        if agent == "IRE":
            required = ire_action_for_scenario(sc)
            # Pada kasus yang masih mungkin layak, IRE wajib menjadwalkan tepat
            # unit mendesak di bulan 1. Revisi baru boleh diminta jika batas
            # biaya/kas memang mustahil atau siklus sebelumnya bermasalah.
            can_request_revision = self.cash_diagnosis["infeasible"] or self.round > 1
            return [action == required or (action == 3 and can_request_revision)
                    for action in range(ACTION_DIMS["IRE"])]
        if agent == "VMI":
            mask, _ = self._vendor_mask(b)
            if any(mask):
                return mask
            fallback = self._fallback_vendor()          # nobody fits: allow one vendor only, the round ends in conflict
            return [v.name == fallback for v in sc.vendors]
        if agent == "DA":
            others, _ = self._vendor_mask(b, extra_excluded=(b["vendor"],))
            return [True, not b["counter_used"], (not b["alt_used"]) and any(others)]
        # SLM boleh meminta revisi. Aksi ini sangat relevan bila diagnosis kas
        # membuktikan skenario mustahil, tetapi tetap tersedia sebagai eskalasi.
        return [True, True, True, True]

    def stage_agent(self) -> str | None:
        return self.stage if self.stage in AGENTS else None

    def _local_vec(self, agent: str) -> list[float]:
        sc, b = self.scenario, self.batch
        conflict = self._conflict_vec()
        if agent == "IRE":
            return [sc.quantity / 1500, sc.urgent_quantity / sc.quantity, sc.deadline_days / 20,
                    self.round / self.max_rounds] + conflict
        if agent == "VMI":
            scores = composite_scores(sc)
            vec = [b["qty"] / 1500 if b else 0.0, (b["month"] - 1) if b else 0.0, sc.deadline_days / 20]
            for v in sc.vendors:
                quoted = b["quotes"].get(v.name, {}).get("price", v.initial_offer) if b else v.initial_offer
                vec += [quoted / PRICE_SCALE, v.quality / 10, v.lead_time / 20,
                        v.capacity / 1500, scores[v.name] / 10]
            return vec + conflict
        if agent == "DA":
            chosen = b["vendor"] if b else None
            v = sc.vendor(chosen) if chosen else None
            left = (sc.budget - sum(self.committed.values())) / sc.budget
            return ([float(n == chosen) for n in VENDORS]
                    + [v.list_price / PRICE_SCALE if v else 0.0,
                       b["quotes"].get(chosen, {}).get("price", v.initial_offer) / PRICE_SCALE if v else 0.0,
                       self.relation[chosen] if chosen else 0.0, _clip01(left, -1, 1),
                       float(b["alt_used"]) if b else 0.0] + conflict)
        # SLM
        chosen = b["vendor"] if b else None
        v = sc.vendor(chosen) if chosen else None
        bill = b["qty"] * ((b["price"] or 0) + v.transport + v.risk) if v and b["price"] else 0
        cash = self._projected_cash()
        diagnosis = self.cash_diagnosis
        return ([_clip01(bill / sc.budget, 0, 1), (v.discount_pct / 10) if v else 0.0,
                 self.relation[chosen] if chosen else 0.0]
                + [_clip01(k / CASH_SCALE, -1, 1) for k in cash]
                + [_clip01(n / 100_000_000, 0, 1) for n in sc.other_needs]
                + [_clip01(sc.min_cash / 100_000_000, 0, 1), ((b["month"] - 1) / 3) if b else 0.0,
                   _clip01(diagnosis["shortfall"] / CASH_SCALE, 0, 1), float(diagnosis["infeasible"])]
                + conflict)

    def observe(self, agent: str) -> dict:
        """Berikan vektor lokal dan mask aksi yang boleh dipilih agen ini."""
        vec = np.clip(np.array(self._local_vec(agent), dtype=np.float32), -1.0, 1.0)
        return {"observation": vec, "action_mask": np.array(self._mask(agent), dtype=np.int8)}

    def state(self) -> np.ndarray:
        """Gabungkan vektor lokal, tahap, dan putaran untuk critic CTDE saat latihan."""
        parts = [np.array(self._local_vec(a), dtype=np.float32) for a in AGENTS]
        stage = [float(self.stage == a) for a in AGENTS]
        extra = [self.round / self.max_rounds, self.batch_idx / 2]
        return np.clip(np.concatenate(parts + [np.array(stage + extra, dtype=np.float32)]), -1.0, 1.0)

    def discrete_obs(self, agent: str) -> tuple[int, ...]:
        """Observasi diskret ringkas untuk Q-table IQL."""
        sc, b = self.scenario, self.batch
        if agent == "IRE":
            kinds = [k for k in ("budget", "cash", "urgent") if self.conflict[k]]
            code = 0 if not kinds else (4 if len(kinds) > 1 else ["budget", "cash", "urgent"].index(kinds[0]) + 1)
            return (_bin5(sc.urgent_quantity / sc.quantity, 0.5, 0.9), _bin5(sc.deadline_days, 5, 14),
                    min(self.round - 1, 4), code)
        if agent == "VMI":
            mask = self._mask("VMI")
            est = self._estimates(b["qty"]) if b else {}
            allowed = [i for i, ok in enumerate(mask) if ok]
            cheapest = min(allowed, key=lambda i: est[VENDORS[i]]) if est else 0
            return (_bin5(b["qty"] if b else 0, 0, 1400), _bin5(sc.deadline_days, 5, 14),
                    len(allowed) - 1, cheapest)
        if agent == "DA":
            chosen = b["vendor"] if b else None
            left = (sc.budget - sum(self.committed.values())) / sc.budget
            return (VENDORS.index(chosen) if chosen else 0,
                    _bin5(self.relation[chosen], 0, 1) if chosen else 0,
                    _bin5(left, -0.2, 1.0), int(b["alt_used"]) if b else 0)
        v = sc.vendor(b["vendor"]) if b and b["vendor"] else None
        bill = b["qty"] * (b["price"] + v.transport + v.risk) if v and b["price"] else 0
        return (_bin5(bill / sc.budget, 0, 1.2), min(v.discount_pct, 4) if v else 0,
                _bin5(min(self._projected_cash()), -100_000_000, CASH_SCALE),
                (b["month"] - 1) if b else 0, int(self.cash_diagnosis["infeasible"]))
