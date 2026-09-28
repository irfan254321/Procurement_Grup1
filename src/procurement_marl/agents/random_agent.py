"""Random policy that respects the action mask."""

import numpy as np


class RandomPolicy:
    def __init__(self, seed: int | None = None):
        self.rng = np.random.default_rng(seed)

    def act(self, env, agent: str) -> int:
        mask = env.observe(agent)["action_mask"]
        return int(self.rng.choice(np.flatnonzero(mask)))
