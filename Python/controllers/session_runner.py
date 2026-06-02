"""
controllers/session_runner.py
==============================
AutoSessionRunner — manages automated 300-session Q-learning training loop.

Workflow per session:
  1. Generate diverse setpoint sequence
  2. Inject into GUI step entries
  3. Wait 30s inter-session cooling
  4. Trigger start_ctrl(state)
  5. Wait for _done_all() callback
  6. RL updates Q-table, saves, decrements epsilon
  7. Repeat until target session count reached
"""

import random
import time
import threading
from datetime import datetime, timedelta

from config import HOLD_BAND, NEAR_BAND

TEMP_MIN        = 16.0
TEMP_MAX        = 32.0
TEMP_EMERGENCY  = 38.0
INTER_SESSION_WAIT = 30

_SEQUENCES = [
    [20.0, 22.0, 24.0, 26.0, 28.0],
    [18.0, 21.0, 24.0, 27.0, 30.0],
    [20.0, 23.0, 26.0, 29.0, 32.0],
    [28.0, 25.0, 22.0, 20.0, 18.0],
    [30.0, 26.0, 23.0, 20.0, 17.0],
    [32.0, 28.0, 24.0, 20.0, 16.0],
    [22.0, 25.0, 20.0, 23.0, 19.0],
    [24.0, 20.0, 26.0, 22.0, 28.0],
    [18.0, 25.0, 20.0, 28.0, 22.0],
    [25.0, 19.0, 27.0, 21.0, 24.0],
    [18.0, 24.0, 20.0, 28.0, 22.0],
    [20.0, 28.0, 18.0, 26.0, 22.0],
]


class AutoSessionRunner:

    def __init__(self):
        self.active          = False
        self.paused          = False
        self.target_sessions = 300
        self.hold_seconds    = 60

        self.sessions_this_run  = 0
        self.start_time         = None
        self.pause_time         = None
        self.total_paused_secs  = 0

        self.status             = "IDLE"
        self.status_msg         = ""
        self.cooldown_remaining = 0
        self.emergency_stop     = False

        self.on_status_change = None
        self.on_session_start = None
        self.on_cooldown_tick = None

        self.current_sequence = []

    # =================================================================
    #  PUBLIC CONTROL
    # =================================================================

    def start_training(self, state, target_sessions=300, hold_seconds=60):
        if self.active:
            return
        self.active          = True
        self.paused          = False
        self.target_sessions = target_sessions
        self.hold_seconds    = hold_seconds
        self.start_time      = datetime.now()
        self.emergency_stop  = False
        self.status          = "WAITING"

        t = threading.Thread(
            target=self._training_loop, args=(state,), daemon=True)
        t.start()

    def pause(self):
        if self.active and not self.paused:
            self.paused     = True
            self.pause_time = datetime.now()
            self._set_status("PAUSED", "Pausing after current session...")

    def resume(self, state):
        if self.active and self.paused:
            if self.pause_time:
                self.total_paused_secs += (
                    datetime.now() - self.pause_time).seconds
                self.pause_time = None
            self.paused = False
            self._set_status("WAITING", "Resuming...")
            t = threading.Thread(
                target=self._training_loop, args=(state,), daemon=True)
            t.start()

    def stop(self, state):
        self.active         = False
        self.paused         = False
        self.emergency_stop = True
        self._set_status("IDLE", "Training stopped by user.")

    # =================================================================
    #  TRAINING LOOP
    # =================================================================

    def _training_loop(self, state):
        rl = state.rl

        while self.active and not self.paused:

            if rl.session_count >= self.target_sessions:
                self._set_status(
                    "DONE",
                    f"Training complete! {self.target_sessions} sessions.")
                self.active = False
                break

            # Emergency temperature check
            temp = state.last_known_temp[0]
            if temp is not None and temp > TEMP_EMERGENCY:
                self._set_status(
                    "ERROR",
                    f"Emergency: temp={temp:.1f}°C > {TEMP_EMERGENCY}°C.")
                self.paused = True
                break

            # Generate next sequence
            seq = self._next_sequence(rl.session_count)
            self.current_sequence = seq

            if self.on_session_start:
                self.on_session_start(rl.session_count + 1, seq)

            # Inject into GUI
            state.root.after(
                0, lambda s=seq: self._inject_sequence(state, s))
            time.sleep(0.3)

            # Inter-session cooling
            self._set_status(
                "COOLING",
                f"Cooling... session "
                f"{rl.session_count + 1}/{self.target_sessions}")

            for i in range(INTER_SESSION_WAIT, 0, -1):
                if not self.active or self.paused:
                    return
                self.cooldown_remaining = i
                if self.on_cooldown_tick:
                    self.on_cooldown_tick(i)
                time.sleep(1)
            self.cooldown_remaining = 0

            if not self.active or self.paused:
                return

            # Start session
            self._set_status(
                "RUNNING",
                f"Session {rl.session_count + 1}/{self.target_sessions}"
                f"  ε={rl.epsilon:.3f}")
            state.root.after(0, lambda: self._trigger_start(state))

            # Wait for session to complete
            state._runner_session_done.clear()
            state._runner_session_done.wait(timeout=900)

            if not self.active:
                return

        if self.paused:
            self._set_status("PAUSED", "Training paused.")

    def _inject_sequence(self, state, seq):
        for i, (te, he, sl) in enumerate(state.step_entries):
            te.delete(0, "end")
            te.insert(0, str(seq[i]))
            he.delete(0, "end")
            he.insert(0, str(self.hold_seconds))

    def _trigger_start(self, state):
        from core.control_loop import start_ctrl
        start_ctrl(state)

    def _next_sequence(self, session_num):
        if session_num < len(_SEQUENCES):
            return list(_SEQUENCES[session_num])

        r = random.random()
        if r < 0.33:
            start = random.uniform(TEMP_MIN, TEMP_MIN + 6)
            return [round(start + i * random.uniform(1.5, 3.0), 1)
                    for i in range(5)]
        elif r < 0.66:
            start = random.uniform(TEMP_MAX - 6, TEMP_MAX)
            return [round(start - i * random.uniform(1.5, 3.0), 1)
                    for i in range(5)]
        else:
            return [round(random.uniform(TEMP_MIN, TEMP_MAX), 1)
                    for _ in range(5)]

    def _set_status(self, status, msg=""):
        self.status     = status
        self.status_msg = msg
        if self.on_status_change:
            self.on_status_change(status, msg)

    # =================================================================
    #  PROGRESS
    # =================================================================

    def get_progress(self, rl):
        sessions_done = rl.session_count
        sessions_left = max(0, self.target_sessions - sessions_done)

        eta_str = "--"
        if self.start_time and sessions_done > 0:
            elapsed = ((datetime.now() - self.start_time).seconds
                       - self.total_paused_secs)
            secs_per = elapsed / max(sessions_done, 1)
            eta_dt   = datetime.now() + timedelta(seconds=secs_per * sessions_left)
            eta_str  = eta_dt.strftime("%H:%M %d/%m")

        return {
            "sessions_done":   sessions_done,
            "sessions_target": self.target_sessions,
            "sessions_left":   sessions_left,
            "pct":             round(
                100 * sessions_done / max(self.target_sessions, 1), 1),
            "eta":             eta_str,
            "status":          self.status,
            "status_msg":      self.status_msg,
            "cooldown":        self.cooldown_remaining,
            "sequence":        self.current_sequence,
        }