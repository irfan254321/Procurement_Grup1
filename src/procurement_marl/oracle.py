"""Best single-round plan ("rencana optimal satu putaran"): try every plan, keep the best expected return.

A plan = IRE action + (vendor, DA action, SLM action) for each batch, played in one round.
Chance events (counter offer, term revision) are enumerated with their probabilities.
A plan that ends in conflict is scored as an episode that stops there with the team penalty,
so the value is the best a policy can do when it plans a single round well. It is NOT an upper
bound: a multi-round policy can exceed it (for example by recovering after a rejected offer),
so ratios above 1 are allowed in the evaluation.
The feasibility check only uses deterministic actions, so "feasible" never depends on luck.
"""

from __future__ import annotations

from itertools import product

from .env import ProcurementEnv
from .evaluate import run_episode
from .scenario import Scenario, sample_scenario


class PlanPolicy:
    """Plays a fixed plan; if a planned action is masked it takes the first valid one."""

    def __init__(self, plan: tuple):
        self.ire, self.batches = plan

    def act(self, env, agent: str) -> int:
        mask = env.observe(agent)["action_mask"]
        if agent == "IRE":
            wanted = self.ire
        else:
            i = min(env.batch_idx, len(self.batches) - 1)
            vendor, da, slm = self.batches[i]
            wanted = {"VMI": vendor, "DA": da, "SLM": slm}[agent]
        return wanted if mask[wanted] else int(mask.argmax())


def all_plans(deterministic_only: bool = False) -> list[tuple]:
    da_options = [0] if deterministic_only else [0, 1]
    slm_options = [0, 1] if deterministic_only else [0, 1, 2]
    per_batch = list(product(range(3), da_options, slm_options))
    plans = []
    for ire, n_batches in ((0, 1), (1, 2), (2, 1)):
        plans += [(ire, combo) for combo in product(per_batch, repeat=n_batches)]
    return plans


def is_feasible(scenario: Scenario) -> bool:
    """True if some deterministic plan reaches consensus in round 1."""
    env = ProcurementEnv(scenario=scenario)
    for plan in all_plans(deterministic_only=True):
        result = run_episode(env, PlanPolicy(plan), seed=0, options={"scenario": scenario}, stop_at_first_check=True)
        if result["consensus"]:
            return True
    return False


def feasible_share(n: int, seed: int = 0) -> float:
    """Share of random scenarios (seeds seed..seed+n-1) that have a feasible plan."""
    return sum(is_feasible(sample_scenario(seed + i)) for i in range(n)) / n


def expected_return(env: ProcurementEnv, scenario: Scenario, plan: tuple) -> float:
    """Team return of a plan, averaged over all accept/reject outcomes."""
    def visit(forced: list[bool], prob: float) -> float:
        result = run_episode(env, PlanPolicy(plan), seed=0, options={"scenario": scenario, "forced_draws": forced},
                             stop_at_first_check=True)
        probs = list(env.draw_probs)
        if len(probs) <= len(forced):     # no new chance events were needed
            value = result["team_return"]
            return prob * value
        p = probs[len(forced)]
        return visit(forced + [True], prob * p) + visit(forced + [False], prob * (1 - p))
    return visit([], 1.0)


def best_single_round_plan(scenario: Scenario, env: ProcurementEnv | None = None) -> tuple[float, tuple]:
    """Best expected single-round team return over all plans, and the plan that reaches it."""
    env = env or ProcurementEnv(scenario=scenario)
    return max(((expected_return(env, scenario, plan), plan) for plan in all_plans()), key=lambda x: x[0])
