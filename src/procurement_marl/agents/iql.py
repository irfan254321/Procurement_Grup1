# PANDUAN MAHASISWA: Independent Q learning: setiap agen memiliki tabel Q sendiri dan belajar dari reward tim.
"""Independent tabular Q-learning with a shared reward.

Each agent (IRE, VMI, DA, SLM) has its own Q-table over its discrete local observation
(see `ProcurementEnv.discrete_obs`). Agents do not see each other's
actions or Q-tables. The reward is the same for all: the weighted sum of all agents' rewards.

Because agents take turns, the transition of an agent runs from its own turn to its next turn:
the reward is the sum of the shared reward received in between, and the next state is what it
observes on its next turn.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..env import ACTION_DIMS, AGENTS, ProcurementEnv


class IQL:
    def __init__(self, alpha: float = 0.1, gamma: float = 0.99, epsilon: float = 0.0, seed: int = 0):
        self.alpha, self.gamma, self.epsilon = alpha, gamma, epsilon
        self.rng = np.random.default_rng(seed)
        self.q: dict[str, dict[tuple, np.ndarray]] = {a: {} for a in AGENTS}

    # ---------------------------------------------------------------- acting
    def q_values(self, agent: str, state: tuple) -> np.ndarray:
        """Ambil nilai aksi pada state lokal; state baru mulai dengan semua nilai nol."""
        # setdefault mengembalikan isi lama, atau menyimpan array nol jika belum ada.
        return self.q[agent].setdefault(state, np.zeros(ACTION_DIMS[agent]))

    def select(self, agent: str, state: tuple, mask: np.ndarray, epsilon: float) -> int:
        """Epsilon-greedy over the valid actions only."""
        # flatnonzero menghasilkan indeks aksi yang lolos mask kendala.
        valid = np.flatnonzero(mask)
        if self.rng.random() < epsilon:
            return int(self.rng.choice(valid))
        q = self.q_values(agent, state)
        return int(valid[np.argmax(q[valid])])

    def act(self, env: ProcurementEnv, agent: str) -> int:
        """Policy interface used by `evaluate.run_episode` (uses self.epsilon, 0 = greedy)."""
        return self.select(agent, env.discrete_obs(agent), env.observe(agent)["action_mask"], self.epsilon)

    # -------------------------------------------------------------- learning
    def update(self, agent: str, state: tuple, action: int, reward: float,
               next_state: tuple | None, next_mask: np.ndarray | None) -> None:
        """Q(s,a) += alpha * (r + gamma * max_a' Q(s',a') - Q(s,a)). No bootstrap at the end."""
        # Target Bellman: reward yang didapat sejak giliran agen terakhir,
        # ditambah nilai terbaik giliran berikutnya setelah diskon gamma.
        target = reward
        if next_state is not None:
            valid = np.flatnonzero(next_mask)
            target += self.gamma * self.q_values(agent, next_state)[valid].max()
        q = self.q_values(agent, state)
        # alpha mengatur besar koreksi; saat episode selesai next_state=None.
        q[action] += self.alpha * (target - q[action])

    def train_episode(self, env: ProcurementEnv, seed: int) -> tuple[float, bool]:
        """Play one training episode. Returns (shared return, consensus)."""
        env.reset(seed=seed)
        # AEC memberi giliran bergantian; pending menunda pembaruan Q sampai
        # agen yang sama mendapat observasi berikutnya.
        pending: dict[str, list] = {}      # agent -> [state, action, reward collected since]
        total = 0.0
        while True:
            agent = env.agent_selection
            state, mask = env.discrete_obs(agent), env.observe(agent)["action_mask"]
            if agent in pending:
                s, a, r = pending.pop(agent)
                self.update(agent, s, a, r, state, mask)
            action = self.select(agent, state, mask, self.epsilon)
            pending[agent] = [state, action, 0.0]
            env.step(action)
            shared = sum(env.weights[x] * env.rewards[x] for x in env.rewards)
            total += shared
            for p in pending.values():
                p[2] += shared
            if any(env.terminations.values()) or any(env.truncations.values()):
                break
        for agent, (s, a, r) in pending.items():
            self.update(agent, s, a, r, None, None)
        return total, env.stop_reason == "consensus"

    # ------------------------------------------------------------ checkpoint
    def save(self, path: str | Path) -> None:
        data = {a: {",".join(map(str, s)): q.tolist() for s, q in table.items()} for a, table in self.q.items()}
        Path(path).write_text(json.dumps({"alpha": self.alpha, "gamma": self.gamma, "q": data}))

    @classmethod
    def load(cls, path: str | Path, seed: int = 0) -> "IQL":
        raw = json.loads(Path(path).read_text())
        agent = cls(alpha=raw["alpha"], gamma=raw["gamma"], seed=seed)
        for a, table in raw["q"].items():
            agent.q[a] = {tuple(int(x) for x in k.split(",")): np.array(v) for k, v in table.items()}
        return agent
