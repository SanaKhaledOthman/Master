"""DQN agent (paper Eq. 1-2, Table 3, Algorithm 1)."""
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn


@dataclass
class DQNConfig:
    lr: float = 1e-3
    gamma: float = 0.99
    batch_size: int = 64
    episodes: int = 10
    steps_per_episode: int = 20_000
    eps_start: float = 1.0
    eps_end: float = 0.1
    eps_decay: float = 0.995
    memory_size: int = 100_000
    hidden: int = 64


class QNetwork(nn.Module):
    """Q(s) = W3 f2(W2 f1(W1 s + b1) + b2) + b3, f1/f2 = ReLU (Eq. 2)."""

    def __init__(self, d, n_actions, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, x):
        return self.net(x)


class ReplayBuffer:
    def __init__(self, capacity, d):
        self.s = np.zeros((capacity, d), np.float32)
        self.s2 = np.zeros((capacity, d), np.float32)
        self.a = np.zeros(capacity, np.int64)
        self.r = np.zeros(capacity, np.float32)
        self.done = np.zeros(capacity, np.float32)
        self.cap, self.i, self.n = capacity, 0, 0

    def push(self, s, a, r, s2, done):
        self.s[self.i], self.a[self.i], self.r[self.i] = s, a, r
        self.s2[self.i], self.done[self.i] = s2, done
        self.i = (self.i + 1) % self.cap
        self.n = min(self.n + 1, self.cap)

    def sample(self, b, rng):
        j = rng.integers(0, self.n, size=b)
        return (torch.from_numpy(self.s[j]), torch.from_numpy(self.a[j]),
                torch.from_numpy(self.r[j]), torch.from_numpy(self.s2[j]),
                torch.from_numpy(self.done[j]))


class DQNAgent:
    def __init__(self, d, n_actions, cfg: DQNConfig, seed=0):
        torch.manual_seed(seed)
        self.cfg, self.n_actions = cfg, n_actions
        self.rng = np.random.default_rng(seed)
        self.policy = QNetwork(d, n_actions, cfg.hidden)
        self.target = QNetwork(d, n_actions, cfg.hidden)
        self.target.load_state_dict(self.policy.state_dict())
        self.opt = torch.optim.Adam(self.policy.parameters(), lr=cfg.lr)
        self.loss_fn = nn.MSELoss()
        self.memory = ReplayBuffer(cfg.memory_size, d)
        self.eps = cfg.eps_start

    def act(self, s):
        if self.rng.random() < self.eps:
            return int(self.rng.integers(self.n_actions))
        with torch.no_grad():
            return int(self.policy(torch.from_numpy(s)[None]).argmax(1))

    def learn(self):
        if self.memory.n < self.cfg.batch_size:
            return None
        s, a, r, s2, done = self.memory.sample(self.cfg.batch_size, self.rng)
        with torch.no_grad():
            y = r + self.cfg.gamma * (1 - done) * self.target(s2).max(1).values
        q = self.policy(s).gather(1, a[:, None]).squeeze(1)
        loss = self.loss_fn(q, y)
        self.opt.zero_grad()
        loss.backward()
        self.opt.step()
        return loss.item()

    def decay_epsilon(self):
        self.eps = max(self.eps * self.cfg.eps_decay, self.cfg.eps_end)

    def update_target(self):
        self.target.load_state_dict(self.policy.state_dict())

    @torch.no_grad()
    def predict(self, X, batch=8192):
        out = [self.policy(torch.from_numpy(X[i:i + batch])).argmax(1).numpy()
               for i in range(0, len(X), batch)]
        return np.concatenate(out)


def train(agent: DQNAgent, env, log=print):
    """Algorithm 1. Returns the mean TD loss of each episode."""
    cfg = agent.cfg
    losses = []
    for ep in range(cfg.episodes):
        s = env.reset()
        ep_loss, ep_reward, done = [], 0.0, False
        while not done:
            a = agent.act(s)
            s2, r, done = env.step(a)
            agent.memory.push(s, a, r, s2, float(done))
            l = agent.learn()
            if l is not None:
                ep_loss.append(l)
            agent.decay_epsilon()
            ep_reward += r
            s = s2
        agent.update_target()  # theta^- <- theta at the end of each episode
        losses.append(float(np.mean(ep_loss)))
        log(f"  episode {ep + 1}/{cfg.episodes}  loss={losses[-1]:.4f}  "
            f"reward={ep_reward:.1f}  eps={agent.eps:.3f}")
    return losses
