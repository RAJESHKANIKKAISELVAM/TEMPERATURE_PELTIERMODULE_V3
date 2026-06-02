"""
controllers/rl_controller.py
============================
Q-Learning controller — master gain supervisor over PID.

State space (160 discrete states):
  error_bin  : 8 levels  (-inf,-5,-3,-1,0,1,3,5,+inf)
  dT_dt_bin  : 5 levels  (-inf,-0.3,-0.1,0.1,0.3,+inf)
  phase_bin  : 4 levels  (APPROACH_FAR, APPROACH_NEAR, HOLD_OK, HOLD_VIO)

Action space (25 discrete actions):
  Kp_scale × {0.5, 0.75, 1.0, 1.25, 1.5}
  max_I    × {1.0, 1.5, 2.0, 2.5, 3.0} A

Reward (Lee et al. 2026):
  APPROACH:  r = -abs(error) / 10.0
  HOLD OK:   r = exp(-0.8 * error²)
  HOLD VIO:  r = -10.0
  FLIP:      r -= 0.5 per relay flip
"""

import json
import math
import os
import random
import csv
from datetime import datetime

from config import BASE_DIR

# =================================================================
#  PATHS
# =================================================================
RL_DATA_DIR    = os.path.join(BASE_DIR, "rl_data")
QTABLE_PATH    = os.path.join(RL_DATA_DIR, "rl_qtable.json")
TRAIN_LOG_PATH = os.path.join(RL_DATA_DIR, "rl_training_log.csv")

os.makedirs(RL_DATA_DIR, exist_ok=True)

# =================================================================
#  STATE DISCRETISATION
# =================================================================
ERROR_BINS = [-5.0, -3.0, -1.0, 0.0, 1.0, 3.0, 5.0]   # 8 buckets
DTDT_BINS  = [-0.3, -0.1, 0.1, 0.3]                    # 5 buckets

PHASE_APPROACH_FAR  = 0
PHASE_APPROACH_NEAR = 1
PHASE_HOLD_OK       = 2
PHASE_HOLD_VIO      = 3

# =================================================================
#  ACTION SPACE (25 actions)
# =================================================================
KP_SCALES    = [0.5, 0.75, 1.0, 1.25, 1.5]
MAX_CURRENTS = [1.0, 1.5, 2.0, 2.5, 3.0]

ACTIONS   = [(kp, mi) for kp in KP_SCALES for mi in MAX_CURRENTS]
N_ACTIONS = len(ACTIONS)   # 25


def _discretise(value, bins):
    for i, b in enumerate(bins):
        if value < b:
            return i
    return len(bins)


def get_state(error, dT_dt, ctrl_state, hold_band, near_band, violation=False):
    """Convert continuous measurements to a discrete state tuple."""
    eb = _discretise(error, ERROR_BINS)
    db = _discretise(dT_dt, DTDT_BINS)

    if ctrl_state == "HOLDING":
        pb = PHASE_HOLD_VIO if violation else PHASE_HOLD_OK
    else:
        pb = PHASE_APPROACH_NEAR if abs(error) <= near_band else PHASE_APPROACH_FAR

    return (eb, db, pb)


# =================================================================
#  Q-LEARNING CONTROLLER
# =================================================================
class RLController:

    def __init__(self,
                 alpha=0.1,
                 gamma=0.95,
                 epsilon_start=0.9,
                 epsilon_end=0.05,
                 total_sessions=300):

        self.alpha          = alpha
        self.gamma          = gamma
        self.epsilon        = epsilon_start
        self.epsilon_start  = epsilon_start
        self.epsilon_end    = epsilon_end
        self.total_sessions = total_sessions

        self.qtable       = {}
        self.visit_counts = {}

        self.session_count        = 0
        self.training_started     = None
        self.last_updated         = None
        self.best_session_reward  = -float("inf")

        self.last_state      = None
        self.last_action     = None
        self.step_rewards    = []
        self.session_rewards = []
        self.flip_count_prev = 0

        self.enabled = True
        self._load()

    # =================================================================
    #  STATE KEY
    # =================================================================
    def _key(self, state):
        return f"{state[0]},{state[1]},{state[2]}"

    def _ensure(self, state):
        k = self._key(state)
        if k not in self.qtable:
            self.qtable[k]       = [0.0] * N_ACTIONS
            self.visit_counts[k] = [0]   * N_ACTIONS
        return k

    # =================================================================
    #  ACTION SELECTION
    # =================================================================
    def get_action(self, state):
        if not self.enabled:
            return 10   # neutral: Kp×1.0, I=2.0A

        k = self._ensure(state)
        if random.random() < self.epsilon:
            return random.randint(0, N_ACTIONS - 1)
        else:
            return int(max(range(N_ACTIONS), key=lambda a: self.qtable[k][a]))

    def get_action_params(self, action_idx):
        return ACTIONS[action_idx]

    # =================================================================
    #  Q-TABLE UPDATE
    # =================================================================
    def update(self, state, action, reward, next_state):
        if not self.enabled or state is None or action is None:
            return

        k  = self._ensure(state)
        k2 = self._ensure(next_state)

        old_q    = self.qtable[k][action]
        max_next = max(self.qtable[k2])
        new_q    = old_q + self.alpha * (reward + self.gamma * max_next - old_q)

        self.qtable[k][action]       = round(new_q, 6)
        self.visit_counts[k][action] += 1

    # =================================================================
    #  REWARD
    # =================================================================
    def compute_reward(self, error, ctrl_state, violation,
                       relay_flips_delta, hold_band):
        if ctrl_state == "APPROACH":
            r = -abs(error) / 10.0
        elif ctrl_state == "HOLDING":
            r = -10.0 if violation else math.exp(-0.8 * error ** 2)
        else:
            r = 0.0

        r -= 0.5 * relay_flips_delta
        return round(r, 6)

    # =================================================================
    #  EPISODE MANAGEMENT
    # =================================================================
    def on_step_complete(self, step_data, hold_band, near_band):
        if not step_data:
            return 0.0

        hold_temps = [t for _, t in step_data.get("hold_temps", [])]
        violations = step_data.get("hold_violations", 0)
        target     = step_data.get("target", 0.0)

        if not hold_temps:
            return -1.0

        avg_temp    = sum(hold_temps) / len(hold_temps)
        avg_error   = avg_temp - target
        hold_secs   = step_data.get("hold_secs", 60)

        if violations == 0:
            step_reward = math.exp(-0.8 * avg_error ** 2) * hold_secs
        else:
            vio_frac    = violations / max(len(hold_temps), 1)
            step_reward = -10.0 * vio_frac * hold_secs

        step_reward = round(step_reward, 4)
        self.step_rewards.append(step_reward)
        return step_reward

    def on_session_complete(self):
        self.session_count += 1
        self.last_updated   = datetime.now().isoformat()

        if self.training_started is None:
            self.training_started = datetime.now().isoformat()

        avg_reward = (sum(self.step_rewards) / len(self.step_rewards)
                      if self.step_rewards else 0.0)
        self.session_rewards.append(avg_reward)

        if avg_reward > self.best_session_reward:
            self.best_session_reward = avg_reward

        self.epsilon = max(
            self.epsilon_end,
            self.epsilon_start - (self.epsilon_start - self.epsilon_end)
            * self.session_count / self.total_sessions
        )
        self.epsilon   = round(self.epsilon, 4)
        self.step_rewards = []
        return avg_reward

    # =================================================================
    #  DIAGNOSTICS
    # =================================================================
    def get_stats(self):
        states_visited = sum(1 for v in self.visit_counts.values()
                             if any(n > 0 for n in v))

        last_action_str = "--"
        if self.last_action is not None:
            kp_s, mi = self.get_action_params(self.last_action)
            last_action_str = f"Kp×{kp_s} I={mi}A"

        last_q = "--"
        if self.last_state is not None and self.last_action is not None:
            k = self._key(self.last_state)
            if k in self.qtable:
                last_q = f"{self.qtable[k][self.last_action]:.4f}"

        avg10 = (sum(self.session_rewards[-10:]) / len(self.session_rewards[-10:])
                 if self.session_rewards else 0.0)

        return {
            "session":        self.session_count,
            "epsilon":        round(self.epsilon, 3),
            "avg_reward_10":  round(avg10, 4),
            "best_reward":    round(self.best_session_reward, 4),
            "states_visited": states_visited,
            "last_action":    last_action_str,
            "last_q":         last_q,
            "enabled":        self.enabled,
        }

    # =================================================================
    #  PERSISTENCE
    # =================================================================
    def save(self):
        data = {
            "version":          1,
            "session_count":    self.session_count,
            "epsilon":          self.epsilon,
            "best_reward":      self.best_session_reward,
            "training_started": self.training_started,
            "last_updated":     datetime.now().isoformat(),
            "qtable":           self.qtable,
            "visit_counts":     self.visit_counts,
            "session_rewards":  self.session_rewards[-300:],
        }
        try:
            with open(QTABLE_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[RL] Save failed: {e}")

    def _load(self):
        if not os.path.exists(QTABLE_PATH):
            return
        try:
            with open(QTABLE_PATH) as f:
                data = json.load(f)
            self.session_count       = data.get("session_count", 0)
            self.epsilon             = data.get("epsilon", self.epsilon_start)
            self.best_session_reward = data.get("best_reward", -float("inf"))
            self.training_started    = data.get("training_started")
            self.qtable              = data.get("qtable", {})
            self.visit_counts        = data.get("visit_counts", {})
            self.session_rewards     = data.get("session_rewards", [])
            print(f"[RL] Loaded: session {self.session_count}, "
                  f"ε={self.epsilon:.3f}, {len(self.qtable)} states")
        except Exception as e:
            print(f"[RL] Load failed (starting fresh): {e}")

    def log_session(self, avg_reward, violations, best_step):
        states_visited = sum(1 for v in self.visit_counts.values()
                             if any(n > 0 for n in v))
        write_header = not os.path.exists(TRAIN_LOG_PATH)
        try:
            with open(TRAIN_LOG_PATH, "a", newline="") as f:
                w = csv.writer(f)
                if write_header:
                    w.writerow(["session", "timestamp", "epsilon",
                                "avg_reward", "violations", "best_step",
                                "qtable_states_visited"])
                w.writerow([
                    self.session_count,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    round(self.epsilon, 4),
                    round(avg_reward, 4),
                    violations,
                    round(best_step, 4),
                    states_visited,
                ])
        except Exception as e:
            print(f"[RL] Log failed: {e}")