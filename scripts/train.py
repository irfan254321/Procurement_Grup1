"""Train a policy on random scenarios: independent Q-learning (iql) or CTDE actor-critic (ctde).

Usage: python scripts/train.py --algo iql|ctde [--episodes 20000] [--seed 0] [--out runs/<algo>]
Writes curve.csv (training curve), checkpoint.json and config.json into the output folder.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from procurement_marl.agents.ctde_ac import CTDEActorCritic
from procurement_marl.agents.iql import IQL
from procurement_marl.agents.random_agent import RandomPolicy
from procurement_marl.agents.rule_based import RuleBasedPolicy
from procurement_marl.env import ProcurementEnv
from procurement_marl.evaluate import make_env, run_episode
from procurement_marl.scenario import sample_scenario

TRAIN_SEED_OFFSET = 1_000_000
MODEL_VERSION = 7


def quick_eval(policy, n: int = 500, override: float | None = None) -> dict[str, float]:
    """Mean team return and consensus rate on the fixed evaluation scenarios (seeds 0..n-1)."""
    env = make_env(override)
    results = [run_episode(env, policy, seed=s, options={"scenario": sample_scenario(s)}) for s in range(n)]
    requests = [any(e.get("event") == "revision_request" for e in r["log"]) for r in results]
    false_requests = [asked and not r["cash_diagnosis"]["infeasible"]
                      for asked, r in zip(requests, results)]
    return {"team_return": sum(r["team_return"] for r in results) / n,
            "consensus": sum(r["consensus"] for r in results) / n,
            "infeasible": sum(r["outcome"] == "TIDAK FEASIBLE" for r in results) / n,
            "revision_request": sum(requests) / n,
            "false_revision": sum(false_requests) / n}


def train_iql(episodes: int, seed: int, out: Path, block: int = 500, alpha: float = 0.1,
              gamma: float = 0.99, eps_start: float = 1.0, eps_end: float = 0.05, decay_share: float = 0.7,
              override: float | None = None) -> IQL:
    out.mkdir(parents=True, exist_ok=True)
    env = make_env(override)
    agent = IQL(alpha=alpha, gamma=gamma, seed=seed)
    decay_episodes = int(episodes * decay_share)
    returns, consensus = [], []
    start = time.time()
    with open(out / "curve.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["episode", "epsilon", "mean_team_return", "consensus_rate", "seconds"])
        for ep in range(1, episodes + 1):
            agent.epsilon = max(eps_end, eps_start - (eps_start - eps_end) * ep / decay_episodes)
            ret, ok = agent.train_episode(env, seed=TRAIN_SEED_OFFSET + seed * 10_000_000 + ep)
            returns.append(ret)
            consensus.append(ok)
            if ep % block == 0:
                writer.writerow([ep, round(agent.epsilon, 3), round(sum(returns) / block, 4),
                                 round(sum(consensus) / block, 4), round(time.time() - start, 1)])
                f.flush()
                returns, consensus = [], []
    agent.epsilon = 0.0
    agent.save(out / "checkpoint.json")
    (out / "config.json").write_text(json.dumps(
        {"algo": "iql", "model_version": MODEL_VERSION, "episodes": episodes, "seed": seed,
         "p_override": override, "alpha": alpha, "gamma": gamma,
         "eps_start": eps_start, "eps_end": eps_end, "decay_share": decay_share,
         "states": {a: len(t) for a, t in agent.q.items()}}, indent=2))
    return agent


def train_ctde(episodes: int, seed: int, out: Path, block: int = 500, batch: int = 32,
               override: float | None = None, **hp) -> CTDEActorCritic:
    """Train the CTDE actor-critic. One gradient step per `batch` episodes."""
    out.mkdir(parents=True, exist_ok=True)
    env = make_env(override)
    agent = CTDEActorCritic(seed=seed, greedy=False, **hp)
    returns, consensus, done_eps = [], [], 0
    start = time.time()
    with open(out / "curve.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["episode", "entropy", "mean_team_return", "consensus_rate", "seconds"])
        while done_eps < episodes:
            batch_eps = []
            for _ in range(batch):
                done_eps += 1
                steps, ok = agent.collect_episode(env, seed=TRAIN_SEED_OFFSET + seed * 10_000_000 + done_eps)
                batch_eps.append(steps)
                returns.append(sum(s["reward"] for s in steps))
                consensus.append(ok)
            info = agent.update(batch_eps)
            if len(returns) >= block:
                writer.writerow([done_eps, round(info["entropy"], 4), round(sum(returns) / len(returns), 4),
                                 round(sum(consensus) / len(consensus), 4), round(time.time() - start, 1)])
                f.flush()
                returns, consensus = [], []
    agent.greedy = True
    agent.save(out / "checkpoint.pt")
    (out / "config.json").write_text(json.dumps(
        {"algo": "ctde", "model_version": MODEL_VERSION, "episodes": episodes, "seed": seed,
         "batch": batch, "p_override": override, **agent.hp}, indent=2))
    return agent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--algo", choices=["iql", "ctde"], default="iql")
    parser.add_argument("--episodes", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--override", type=float, default=None, help="fixed p_accept = p_termin (sensitivity)")
    args = parser.parse_args()
    args.out = args.out or ROOT / "runs" / args.algo

    t = time.time()
    if args.algo == "iql":
        agent = train_iql(args.episodes, args.seed, args.out, override=args.override)
    else:
        agent = train_ctde(args.episodes, args.seed, args.out, override=args.override)
    print(f"Training {args.algo} selesai: {args.episodes} episode dalam {time.time() - t:.0f} detik -> {args.out}")
    print("Evaluasi 500 skenario acak (seed 0-499), kebijakan greedy:")
    for name, policy in [(args.algo.upper(), agent), ("rule-based", RuleBasedPolicy()), ("random", RandomPolicy(0))]:
        m = quick_eval(policy, override=args.override)
        print(f"  {name:11s} return {m['team_return']:7.2f}  konsensus {m['consensus']:.1%}  "
              f"tidak feasible {m['infeasible']:.1%}  minta revisi {m['revision_request']:.1%}  "
              f"revisi keliru {m['false_revision']:.1%}")


if __name__ == "__main__":
    main()
