"""Play episodes with a policy and compare policies on the same random scenarios.

Run `python scripts/evaluate.py` for the comparison table (writes runs/comparison.csv and .md).
Evaluation scenarios are `sample_scenario(seed)` for seed 0..n-1, fixed for every policy.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .env import ProcurementEnv


def make_env(override: float | None = None) -> ProcurementEnv:
    """Random-scenario env. `override` fixes p_accept and p_termin (sensitivity analysis)."""
    env = ProcurementEnv("random")
    env.stoch["p_accept_override"] = override
    env.stoch["p_termin_override"] = override
    return env


def run_episode(env: ProcurementEnv, policy, seed: int | None = None, options: dict | None = None,
                stop_at_first_check: bool = False) -> dict:
    """Play one episode. `policy.act(env, agent)` returns an action index."""
    options = dict(options or {})
    options.setdefault("stop_on_repeat", True)
    if stop_at_first_check:
        options["stop_after_round"] = 1
    env.reset(seed=seed, options=options)
    returns = dict.fromkeys(env.possible_agents, 0.0)
    for agent in env.agent_iter():
        _, reward, terminated, truncated, _ = env.last()
        returns[agent] += reward
        env.step(None if terminated or truncated else policy.act(env, agent))
    team = sum(env.weights[a] * r for a, r in returns.items())
    last = next((e for e in reversed(env.log) if e.get("event") in ("cek_batasan", "diagnosis")), None)
    return {"returns": returns, "team_return": team, "log": env.log, "steps": env.steps,
            "truncated": env.was_truncated,
            "stop_reason": env.stop_reason,
            "coordination_steps": max((e.get("coordination_step", 0) for e in env.log), default=0),
            "consensus": bool(last and last["consensus"]), "rounds": last["round"] if last else env.round,
            "outcome": "LAYAK" if env.stop_reason == "consensus" else
                       "TIDAK FEASIBLE" if env.stop_reason == "infeasible_proven" else "PERLU REVISI",
            "cash_diagnosis": dict(env.cash_diagnosis),
            "violations": last["violations"] if last else env.violations,
            "total": last["total"] if last else 0}


def evaluate_policy(policy, n: int = 500, override: float | None = None, seed_offset: int = 0) -> dict[str, float]:
    """Average metrics over n episodes on scenarios seed_offset .. seed_offset+n-1."""
    from .scenario import sample_scenario

    env = make_env(override)
    rows, counter, da_turns, termin, slm_turns = [], 0, 0, 0, 0
    revision_requests, false_revision_requests = 0, 0
    for s in range(seed_offset, seed_offset + n):
        r = run_episode(env, policy, seed=s, options={"scenario": sample_scenario(s)})
        rows.append(r)
        requested = any(e.get("event") == "revision_request" for e in r["log"])
        revision_requests += requested
        false_revision_requests += requested and not r["cash_diagnosis"]["infeasible"]
        for e in r["log"]:
            if e["agent"] == "DA" and e.get("event") != "term_response":
                da_turns += 1
                counter += e["action"] == "penawaran_balik"
            elif e["agent"] == "SLM" and e.get("event") == "payment_plan":
                slm_turns += 1
                termin += e["action"] == "revisi_termin"
    return summarize(rows) | {"counter_offer_rate": counter / max(da_turns, 1),
                              "term_revision_rate": termin / max(slm_turns, 1),
                              "revision_request_rate": revision_requests / max(n, 1),
                              "false_revision_rate": false_revision_requests / max(n, 1)}


def summarize(rows: list[dict]) -> dict[str, float]:
    n = len(rows)
    mean = lambda f: sum(f(r) for r in rows) / n
    return {
        "team_return": mean(lambda r: r["team_return"]),
        "consensus": mean(lambda r: r["consensus"]),
        "infeasible_detected": mean(lambda r: r["stop_reason"] == "infeasible_proven"),
        "budget_violation": mean(lambda r: "anggaran" in r["violations"]),
        "cash_violation": mean(lambda r: bool({"kas_negatif", "kas_minimum"} & set(r["violations"]))),
        "urgent_met": mean(lambda r: "unit_mendesak" not in r["violations"]),
        "avg_cost": mean(lambda r: r["total"]),
        "rounds": mean(lambda r: r["rounds"]),
    }


def single_round_plan_row(n: int = 500, cache: Path | None = None) -> dict[str, float]:
    """Metrics of the best single-round plan (rencana optimal satu putaran).

    Its return is the expected value from the plan search; the other columns come from
    playing that plan in the environment. Results are cached (the search takes a few minutes).
    """
    from .oracle import PlanPolicy, best_single_round_plan
    from .scenario import sample_scenario

    if cache and cache.exists():
        saved = json.loads(cache.read_text())
        if saved["n"] == n and saved.get("evaluation_version") == 2:
            return saved["row"]
    env = make_env()
    rows, values = [], []
    for s in range(n):
        sc = sample_scenario(s)
        value, plan = best_single_round_plan(sc, env)
        r = run_episode(env, PlanPolicy(plan), seed=s, options={"scenario": sc}, stop_at_first_check=True)
        rows.append(r)
        values.append(value)
    row = summarize(rows) | {"team_return": sum(values) / n, "counter_offer_rate": 0.0, "term_revision_rate": 0.0}
    if cache:
        cache.write_text(json.dumps({"n": n, "row": row, "evaluation_version": 2}))
    return row


COLUMNS = [("team_return", "Return tim"), ("consensus", "Konsensus"), ("budget_violation", "Pelanggaran anggaran"),
           ("cash_violation", "Pelanggaran kas"), ("urgent_met", "Unit mendesak terpenuhi"),
           ("avg_cost", "Biaya rata-rata (juta Rp)"), ("rounds", "Rata-rata siklus simulasi"), ("ratio", "Rasio thd rencana optimal 1 putaran")]


def comparison_table(results: dict[str, dict[str, float]], plan_name: str) -> tuple[list[str], list[list[str]]]:
    plan_return = results[plan_name]["team_return"]
    header = ["Kebijakan"] + [label for _, label in COLUMNS]
    body = []
    for name, m in results.items():
        m = m | {"ratio": m["team_return"] / plan_return}
        cells = [f"{m['team_return']:.2f}", f"{m['consensus']:.1%}", f"{m['budget_violation']:.1%}",
                 f"{m['cash_violation']:.1%}", f"{m['urgent_met']:.1%}", f"{m['avg_cost'] / 1e6:.1f}", f"{m['rounds']:.2f}", f"{m['ratio']:.2f}"]
        body.append([name] + cells)
    return header, body


def main(n: int = 500, runs: Path | None = None) -> None:
    from .agents.ctde_ac import CTDEActorCritic
    from .agents.iql import IQL
    from .agents.random_agent import RandomPolicy
    from .agents.rule_based import RuleBasedPolicy

    runs = runs or Path(__file__).resolve().parents[2] / "runs"
    plan_name = "Rencana optimal satu putaran"
    policies = {"Random": RandomPolicy(0), "Rule-based": RuleBasedPolicy(),
                "IQL": IQL.load(runs / "iql" / "checkpoint.json"),
                "CTDE actor-critic": CTDEActorCritic.load(runs / "ctde" / "checkpoint.pt")}
    results = {name: evaluate_policy(p, n) for name, p in policies.items()}
    results[plan_name] = single_round_plan_row(n, runs / "single_round_plan.json")
    header, body = comparison_table(results, plan_name)
    with open(runs / "comparison.csv", "w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows([header] + body)
    md = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(r) + " |" for r in body]
    text = "\n".join(md)
    (runs / "comparison.md").write_text(text + "\n")
    (runs / "comparison.meta.json").write_text(json.dumps({"evaluation_version": 2, "n": n}))
    print(f"Perbandingan kebijakan, rata-rata {n} skenario acak (seed 0-{n - 1}):\n")
    print(text)
    print("\nCatatan: return tim baris rencana optimal = nilai harapan satu putaran; kolom lain dari menjalankan rencana itu. "
          "Rasio > 1 mungkin karena kebijakan multi-putaran bisa melampauinya.")
