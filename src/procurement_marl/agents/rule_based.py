"""Fixed baseline using the choices illustrated in Bab 6.

IRE forwards in round 1 and asks for clarification after a conflict. VMI picks the eligible
vendor with the lowest estimated total cost (last agreed price, else list price), and for a later batch prefers a different
vendor as backup (risk note 6.3.1). DA always takes the initial offer. SLM always pays fast.
It reads the environment directly because it is a hand-written baseline, not a learner.
The six-stage report demonstration uses ReportReplayEnv; the general environment
stops this baseline when its plan and relevant state repeat without progress.
"""

from ..env import VENDORS


class RuleBasedPolicy:
    # Deterministic baseline: repeating the full plan/state cannot resolve a conflict.
    stop_on_repeat = True

    def act(self, env, agent: str) -> int:
        mask = env.observe(agent)["action_mask"]
        if agent == "IRE":
            wanted = 0 if env.round == 1 else 1
            return wanted if mask[wanted] else 0
        if agent == "VMI":
            allowed = [i for i in range(3) if mask[i]]
            used = {b["vendor"] for b in env.batches[:env.batch_idx]}
            fresh = [i for i in allowed if VENDORS[i] not in used]
            estimates = env._estimates(env.batch["qty"])
            return min(fresh or allowed, key=lambda i: estimates[VENDORS[i]])
        return 0   # DA: penawaran_awal, SLM: bayar_cepat
