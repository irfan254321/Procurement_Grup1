"""Pure reward functions. Our own design, not from the report (see DECISIONS.md)."""

from __future__ import annotations

from typing import Mapping, Sequence


def ire_reward(urgent_met: bool, revision_rounds: int, per_revision: float = -0.1) -> float:
    """+1 if urgent units arrive on time, -1 if not, -0.1 per revision round."""
    return (1.0 if urgent_met else -1.0) + per_revision * revision_rounds


def vmi_reward(quality: int, cost: int, cheapest_cost: int) -> float:
    """Quality / 10 minus the cost relative to the cheapest eligible vendor."""
    return quality / 10 - (cost - cheapest_cost) / cheapest_cost


def da_reward(list_price: int, price: int, failed: bool, saving_scale: float = 10.0,
              failure_penalty: float = -0.5) -> float:
    """Saving versus list price (as a fraction) x 10, minus 0.5 if the negotiation failed."""
    saving = (list_price - price) / list_price
    return saving_scale * saving + (failure_penalty if failed else 0.0)


def slm_reward(discount: int, budget: int, below_min_cash: bool, negative_cash: bool,
               below_min_penalty: float = -1.0, negative_penalty: float = -2.0) -> float:
    """Discount relative to budget, -1 if cash < minimum, -2 if cash < 0."""
    reward = discount / budget
    if below_min_cash:
        reward += below_min_penalty
    if negative_cash:
        reward += negative_penalty
    return reward


def team_reward(over_budget: bool, consensus: bool,
                over_budget_penalty: float = -1.0, no_consensus_penalty: float = -2.0) -> float:
    """Shared component received by every agent when the episode ends."""
    return (over_budget_penalty if over_budget else 0.0) + (0.0 if consensus else no_consensus_penalty)


def collective_objective(
    rewards: Sequence[Mapping[str, float]],
    weights: Mapping[str, float],
    gamma: float = 1.0,
) -> float:
    """J(pi) = sum_t gamma^t * sum_i w_i * R_i. `rewards[t]` maps agent name -> reward."""
    return sum(
        gamma**t * sum(weights[agent] * r for agent, r in step.items())
        for t, step in enumerate(rewards)
    )
