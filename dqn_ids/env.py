"""Classification-as-RL environment (paper Sec. IV-A and V-A).

State  s_t = x_t (one flow's feature vector)
Action a_t = predicted class
Reward r_t from the asymmetric scheme in Table 2
Transition s_{t+1} = x_{t+1} (next sample); episode ends after `steps` samples.
"""
import numpy as np

# Table 2 (binary; 1 = ransomware, 0 = benign)
BINARY_REWARD = {"TP": 1.0, "TN": 0.1, "FP": -0.5, "FN": -1.0}


def reward_matrix(task, multiclass_scheme="symmetric"):
    """R[true, pred] reward lookup."""
    if task == "binary":
        r = BINARY_REWARD
        return np.array([[r["TN"], r["FP"]],
                         [r["FN"], r["TP"]]], dtype=np.float32)
    # Multiclass (A=0, S=1, SS=2). The paper only says "positive for correct
    # predictions and negative for misclassifications".
    if multiclass_scheme == "symmetric":
        return np.where(np.eye(3, dtype=bool), 1.0, -1.0).astype(np.float32)
    if multiclass_scheme == "asymmetric":
        # Table 2 generalised: S is benign, A/SS are ransomware.
        R = np.full((3, 3), -0.5, dtype=np.float32)   # wrong ransomware class / FP
        R[0, 0] = R[2, 2] = 1.0                         # TP
        R[1, 1] = 0.1                                   # TN
        R[0, 1] = R[2, 1] = -1.0                        # FN (ransomware -> S)
        return R
    raise ValueError(multiclass_scheme)


class FlowClassificationEnv:
    def __init__(self, X, y, R, steps_per_episode, rng):
        self.X, self.y, self.R = X, y, R
        self.steps = steps_per_episode
        self.rng = rng

    def reset(self):
        self.order = self.rng.integers(0, len(self.X), size=self.steps + 1)
        self.t = 0
        return self.X[self.order[0]]

    def step(self, action):
        i = self.order[self.t]
        r = float(self.R[self.y[i], action])
        self.t += 1
        done = self.t >= self.steps
        return self.X[self.order[self.t]], r, done
