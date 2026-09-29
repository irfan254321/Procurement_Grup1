"""Bandingkan kebijakan terlatih dengan pencarian rencana feasible satu siklus.

Pembanding mencoba semua kombinasi IRE, VMI, DA, dan pembayaran cepat/jatuh
tempo. Revisi termin yang stokastik dan perbaikan lintas siklus tidak dicakup;
hasilnya pembanding transparan, bukan bukti optimum global.
"""

import argparse
import json
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from procurement.rl_service import policy_from_checkpoint
from procurement_marl.agents.iql import IQL
from procurement_marl.agents.ctde_ac import CTDEActorCritic
from procurement_marl.env import ProcurementEnv
from procurement_marl.evaluate import run_episode
from procurement_marl.oracle import PlanPolicy
from procurement_marl.scenario import sample_scenario


def plans():
    """Semua pilihan dengan pembayaran deterministik; tiap batch punya 12 opsi."""
    batch_actions = list(product(range(3), range(2), range(2)))
    for ire, batches in ((0, 1), (1, 2), (2, 1)):
        for combo in product(batch_actions, repeat=batches):
            yield (ire, combo)


def cheapest_feasible(scenario, seed: int) -> int | None:
    """Biaya terendah di antara kandidat yang benar-benar lolos pemeriksaan ENV."""
    env = ProcurementEnv(scenario)
    best = None
    for plan in plans():
        result = run_episode(env, PlanPolicy(plan), seed=seed,
                             options={"scenario": scenario}, stop_at_first_check=True)
        if result["consensus"]:
            best = result["total"] if best is None else min(best, result["total"])
    return best


def evaluate(n: int, start_seed: int, iql_path: Path | None = None,
             ctde_path: Path | None = None) -> dict:
    policies = {
        "IQL": IQL.load(iql_path) if iql_path else policy_from_checkpoint("IQL"),
        "CTDE": CTDEActorCritic.load(ctde_path) if ctde_path else policy_from_checkpoint("CTDE"),
    }
    envs = {name: ProcurementEnv("random") for name in policies}
    rows = {name: {"consensus": 0, "feasible_found": 0, "feasible_missed": 0,
                   "cost_gap_fraction": [], "better_than_restricted": 0}
            for name in policies}
    proven_infeasible = 0
    for seed in range(start_seed, start_seed + n):
        scenario = sample_scenario(seed)
        reference = cheapest_feasible(scenario, seed)
        proven_infeasible += int(reference is None)
        for name, policy in policies.items():
            result = run_episode(envs[name], policy, seed=seed, options={"scenario": scenario})
            row = rows[name]
            row["consensus"] += int(result["consensus"])
            row["feasible_found"] += int(reference is not None and result["consensus"])
            row["feasible_missed"] += int(reference is not None and not result["consensus"])
            if reference is not None and result["consensus"]:
                gap = (result["total"] - reference) / reference
                row["cost_gap_fraction"].append(gap)
                row["better_than_restricted"] += int(gap < 0)
    summary = {}
    for name, row in rows.items():
        gaps = row.pop("cost_gap_fraction")
        summary[name] = row | {"consensus_rate": row["consensus"] / n,
                               "mean_cost_gap_when_both_feasible": sum(gaps) / len(gaps) if gaps else None,
                               "cost_gap_sample_size": len(gaps)}
    return {"model_version": 7, "n": n, "seed_start": start_seed,
            "restricted_benchmark_no_feasible": proven_infeasible,
            "benchmark_scope": "satu siklus, DA terima/tawar balik, SLM cepat/jatuh tempo",
            "results": summary}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=2000)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "quality_v6.json")
    parser.add_argument("--iql", type=Path, default=None)
    parser.add_argument("--ctde", type=Path, default=None)
    args = parser.parse_args()
    result = evaluate(args.scenarios, args.seed_start, args.iql, args.ctde)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
