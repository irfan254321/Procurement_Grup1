"""Executable reconstruction of Bab 6.4–6.5, with six coordination stages.

The initial proposal is preparation (stage 0). The revised proposal is processed
by department: VMI evaluates both batches, DA negotiates both, then SLM checks
both schedules. All amounts and violations are calculated by ProcurementEnv.
This demonstration is separate from the general MARL simulation/training loop.
"""

from .agents.rule_based import RuleBasedPolicy
from .env import ProcurementEnv
from .evaluate import run_episode


COORDINATION_STAGES = {
    0: "Usulan awal 1.000 unit",
    1: "SLM mendeteksi kekurangan kas",
    2: "IRE mengevaluasi prioritas kebutuhan",
    3: "VMI mengevaluasi alternatif pemasok",
    4: "DA melakukan negosiasi ulang",
    5: "SLM memeriksa biaya dan arus kas",
    6: "Evaluasi bersama dan permintaan revisi",
}


class ReportReplayEnv(ProcurementEnv):
    """Report fixture only; use run_report_episode rather than training here."""

    def __init__(self):
        super().__init__(scenario="report")

    def _log(self, **entry) -> None:
        if entry.get("event") == "cek_batasan":
            step = 1 if self.round == 1 else 6
            entry["reviewer"] = "SLM" if step == 1 else "BERSAMA"
        elif self.round == 1:
            step = 0
        else:
            step = {"IRE": 2, "VMI": 3, "DA": 4, "SLM": 5}.get(entry["agent"], 6)
        super()._log(**entry, coordination_step=step, coordination_label=COORDINATION_STAGES[step])

    def _after_vendor_selection(self) -> None:
        if self.round == 1:
            return super()._after_vendor_selection()
        self.batch_idx += 1
        if self.batch_idx < len(self.batches):
            self._begin_batch()
        else:
            self.batch_idx = 0
            self.stage = self.agent_selection = "DA"

    def _after_price_agreement(self) -> None:
        if self.round == 1:
            return super()._after_price_agreement()
        self.batch_idx += 1
        if self.batch_idx < len(self.batches):
            self.stage = self.agent_selection = "DA"
        else:
            self.batch_idx = 0
            self.stage = self.agent_selection = "SLM"

    def _after_payment_plan(self) -> None:
        if self.round == 1:
            return super()._after_payment_plan()
        self.batch_idx += 1
        if self.batch_idx < len(self.batches):
            self.stage = self.agent_selection = "SLM"
        else:
            self._end_round()

    def _round_stop_reason(self, consensus: bool, signature: tuple) -> str | None:
        if consensus:
            return "consensus"
        return "report_revision_required" if self.round >= 2 else None


def run_report_episode(seed: int = 0) -> dict:
    """Initial proposal plus one revision; ends with the report's joint review."""
    return run_episode(ReportReplayEnv(), RuleBasedPolicy(), seed=seed)
