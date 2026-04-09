"""
controllers/pid_controller.py
=============================
Classic parallel PID controller for Peltier temperature control.

The PID output maps directly to PSU current magnitude.
Sign of output determines relay direction:
  output > 0  → temperature too high → COOL  → Relay A
  output < 0  → temperature too low  → HEAT  → Relay B
  |output| < min_output → coast (relay OFF)

Usage:
    from controllers import PIDController
    pid = PIDController(Kp=0.3, Ki=0.02, Kd=0.5, max_output=3.0)
    pid.set_target(25.0)
    pid.reset()
    current_A, direction = pid.compute(current_temp, dt=1.0)
    # direction: "A" (cool) | "B" (heat) | "OFF" (coast)
"""

import time


class PIDController:
    """
    PID controller that outputs PSU current magnitude
    and relay direction for Peltier temperature control.
    """

    def __init__(self,
                 Kp=0.3,
                 Ki=0.02,
                 Kd=0.5,
                 max_output=3.0,      # maximum PSU current (A)
                 min_output=0.1,      # below this → relay OFF (coast)
                 integral_limit=5.0   # anti-windup clamp
                 ):
        self.Kp             = Kp
        self.Ki             = Ki
        self.Kd             = Kd
        self.max_output     = max_output
        self.min_output     = min_output
        self.integral_limit = integral_limit

        self.target         = 0.0
        self._integral      = 0.0
        self._prev_error    = None
        self._prev_time     = None

        # Diagnostics — readable by GUI
        self.last_P         = 0.0
        self.last_I         = 0.0
        self.last_D         = 0.0
        self.last_output    = 0.0
        self.last_error     = 0.0
        self.last_dT_dt     = 0.0

    def set_target(self, target: float):
        self.target = target

    def reset(self):
        """Call when starting a new setpoint step."""
        self._integral   = 0.0
        self._prev_error = None
        self._prev_time  = None
        self.last_P = self.last_I = self.last_D = 0.0
        self.last_output = self.last_error = self.last_dT_dt = 0.0

    def compute(self, current_temp: float, dt: float = 1.0):
        """
        Compute PID output given current temperature.

        Parameters:
            current_temp : current measured temperature (°C)
            dt           : time since last call (seconds)

        Returns:
            (current_A, direction)
            current_A  : PSU current to set (0 → max_output A)
            direction  : "A" (cool) | "B" (heat) | "OFF" (coast)
        """
        if dt <= 0:
            dt = 1.0

        # Error: positive = too hot (need cooling), negative = too cold
        error = current_temp - self.target
        self.last_error = error

        # ── Proportional ────────────────────────────────────────────
        P = self.Kp * error

        # ── Integral (with anti-windup clamping) ────────────────────
        self._integral += error * dt
        self._integral  = max(-self.integral_limit,
                              min(self.integral_limit, self._integral))
        I = self.Ki * self._integral

        # ── Derivative (rate of change of error) ────────────────────
        if self._prev_error is not None:
            dE_dt = (error - self._prev_error) / dt
        else:
            dE_dt = 0.0
        D = self.Kd * dE_dt
        self.last_dT_dt = dE_dt

        # Store for diagnostics
        self.last_P = round(P, 4)
        self.last_I = round(I, 4)
        self.last_D = round(D, 4)

        # ── PID sum ─────────────────────────────────────────────────
        raw_output       = P + I + D
        self.last_output = round(raw_output, 4)

        self._prev_error = error

        # ── Map output to current + direction ────────────────────────
        current_A = min(abs(raw_output), self.max_output)
        current_A = round(current_A, 3)

        if current_A < self.min_output:
            direction = "OFF"
            current_A = 0.0
        elif raw_output > 0:
            direction = "A"    # too hot → cool
        else:
            direction = "B"    # too cold → heat

        return current_A, direction

    def get_diagnostics(self) -> dict:
        """Returns current PID state for GUI display."""
        return {
            "Kp":     self.Kp,
            "Ki":     self.Ki,
            "Kd":     self.Kd,
            "error":  round(self.last_error, 4),
            "P":      self.last_P,
            "I":      self.last_I,
            "D":      self.last_D,
            "dT_dt":  round(self.last_dT_dt, 4),
            "output": self.last_output,
        }