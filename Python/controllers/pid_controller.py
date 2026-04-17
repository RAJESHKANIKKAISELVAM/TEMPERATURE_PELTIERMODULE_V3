"""
controllers/pid_controller.py
=============================
Enhanced parallel PID controller for Peltier temperature control.

Features:
  1. Gain-Scheduled Dual PID  — separate Kp/Ki/Kd for HEAT vs COOL direction
  2. Setpoint Ramp Generator  — smooth intermediate targets, seeded from current temp
  3. Back-calc Anti-Windup    — integral freezes when output saturates
  4. Adaptive Gain Control    — aggressive far from target, gentle near it
  5. Feedforward              — pre-emptive current push in correct direction

Sign convention (unchanged from original):
  error = current_temp - ramp_target
  error > 0  → too hot  → COOL → Relay A
  error < 0  → too cold → HEAT → Relay B
  |output| < min_output → relay OFF (coast)

Bugs fixed vs previous version:
  - Ramp seeded from current_temp (not 0.0) via set_target(t, current_temp)
  - FF sign corrected: FF = ff_gain * (current_temp - final_target) [same sign as error]
  - Adaptive near-scale raised to 1.0 so holding is not sluggish
  - _load_step in control_loop passes current_temp to set_target()
"""

from config import (
    PID_KP_COOL, PID_KI_COOL, PID_KD_COOL,
    PID_KP_HEAT, PID_KI_HEAT, PID_KD_HEAT,
    RAMP_RATE_DEG_PER_SEC,
    ADAPTIVE_FAR_THRESHOLD, ADAPTIVE_FAR_SCALE, ADAPTIVE_NEAR_SCALE,
    FF_GAIN,
)


class PIDController:

    def __init__(self,
                 Kp=0.3,
                 Ki=0.02,
                 Kd=0.5,
                 max_output=3.0,
                 min_output=0.1,
                 integral_limit=5.0):

        # Legacy attrs (backward compat)
        self.Kp             = Kp
        self.Ki             = Ki
        self.Kd             = Kd
        self.max_output     = max_output
        self.min_output     = min_output
        self.integral_limit = integral_limit

        # Feature 1: Dual gain sets (loaded from config, tunable at runtime)
        self.Kp_cool = PID_KP_COOL
        self.Ki_cool = PID_KI_COOL
        self.Kd_cool = PID_KD_COOL
        self.Kp_heat = PID_KP_HEAT
        self.Ki_heat = PID_KI_HEAT
        self.Kd_heat = PID_KD_HEAT

        # Feature 2: Ramp generator
        self._final_target  = 0.0
        self._ramp_target   = 0.0
        self._ramp_active   = False
        self.ramp_rate      = RAMP_RATE_DEG_PER_SEC   # °C / s

        # Core PID state
        self.target         = 0.0    # always mirrors _ramp_target (read externally)
        self._integral      = 0.0
        self._prev_error    = None

        # Feature 3: Anti-windup flag
        self._was_saturated = False

        # Feature 4: Adaptive gain thresholds
        self.adaptive_far_threshold = ADAPTIVE_FAR_THRESHOLD
        self.adaptive_far_scale     = ADAPTIVE_FAR_SCALE
        self.adaptive_near_scale    = ADAPTIVE_NEAR_SCALE

        # Feature 5: Feedforward gain
        self.ff_gain = FF_GAIN

        # Diagnostics (read by GUI)
        self.last_P         = 0.0
        self.last_I         = 0.0
        self.last_D         = 0.0
        self.last_output    = 0.0
        self.last_error     = 0.0
        self.last_dT_dt     = 0.0
        self.last_ff        = 0.0
        self.last_mode      = "HEAT"
        self.last_adaptive  = 1.0
        self.last_ramp_tgt  = 0.0
        self.ramp_remaining = 0.0

    # =================================================================
    #  PUBLIC API
    # =================================================================

    def set_target(self, target: float, current_temp: float = None):
        """
        Set new final setpoint.

        MUST pass current_temp so the ramp generator starts from the actual
        measured temperature, not from 0.0 or a stale internal value.

        Args:
            target       : final desired temperature (°C)
            current_temp : latest measured temperature (°C) — seeds the ramp
        """
        self._final_target = target

        # Seed ramp from actual current temperature so the ramp direction
        # matches reality from tick 1. Without this, ramp starts from 0°C
        # and the error sign is wrong for ~100 seconds.
        if current_temp is not None:
            self._ramp_target = current_temp
        else:
            # Fallback: if caller forgot, seed from final target (no ramp)
            self._ramp_target = target

        self._ramp_active = (
            self.ramp_rate > 0 and
            abs(target - self._ramp_target) > 0.5
        )

    def reset(self):
        """
        Reset integral, derivative memory, and saturation flag.
        Does NOT touch ramp state — ramp is already seeded by set_target().
        """
        self._integral      = 0.0
        self._prev_error    = None
        self._was_saturated = False
        self.last_P         = 0.0
        self.last_I         = 0.0
        self.last_D         = 0.0
        self.last_output    = 0.0
        self.last_error     = 0.0
        self.last_dT_dt     = 0.0
        self.last_ff        = 0.0

    def compute(self, current_temp: float, dt: float = 1.0):
        """
        Compute PID output for one tick.

        Returns:
            (current_A, direction)
            current_A  : PSU current magnitude to set (A)
            direction  : "A" (cool) | "B" (heat) | "OFF" (coast)
        """
        if dt <= 0:
            dt = 1.0

        # ── Feature 2: Advance ramp toward final target ───────────────
        if self._ramp_active:
            step = self.ramp_rate * dt
            diff = self._final_target - self._ramp_target
            if abs(diff) <= step:
                self._ramp_target = self._final_target
                self._ramp_active = False
            else:
                self._ramp_target += step if diff > 0 else -step

        # Update public .target so external code (graphs, hold detection)
        # always sees the correct intermediate target
        self.target         = self._ramp_target
        self.last_ramp_tgt  = round(self._ramp_target, 3)
        self.ramp_remaining = round(
            abs(self._final_target - self._ramp_target), 3)

        # ── Error: positive = too hot, negative = too cold ────────────
        error           = current_temp - self.target
        self.last_error = error

        # ── Feature 1: Select gain set by error sign ──────────────────
        if error > 0:
            # Temperature above ramp target → need to COOL
            Kp, Ki, Kd     = self.Kp_cool, self.Ki_cool, self.Kd_cool
            self.last_mode = "COOL"
        else:
            # Temperature below ramp target → need to HEAT
            Kp, Ki, Kd     = self.Kp_heat, self.Ki_heat, self.Kd_heat
            self.last_mode = "HEAT"

        # ── Feature 4: Adaptive gain scale ────────────────────────────
        # Far from target: scale up for fast approach
        # Near target: stays at 1.0 for stable holding (no reduction)
        abs_err = abs(error)
        if abs_err >= self.adaptive_far_threshold:
            adaptive_scale = self.adaptive_far_scale
        else:
            frac = abs_err / max(self.adaptive_far_threshold, 0.001)
            adaptive_scale = (
                self.adaptive_near_scale +
                frac * (self.adaptive_far_scale - self.adaptive_near_scale)
            )
        self.last_adaptive = round(adaptive_scale, 3)

        # Scale Kp and Kd only — Ki kept constant for integral consistency
        Kp = Kp * adaptive_scale
        Kd = Kd * adaptive_scale

        # ── Proportional ──────────────────────────────────────────────
        P = Kp * error

        # ── Feature 3: Anti-windup — freeze integral when saturated ───
        if not self._was_saturated:
            self._integral += error * dt

        # Absolute clamp as secondary guard
        self._integral = max(-self.integral_limit,
                             min(self.integral_limit, self._integral))
        I = Ki * self._integral

        # ── Derivative on error ───────────────────────────────────────
        if self._prev_error is not None:
            dE_dt = (error - self._prev_error) / dt
        else:
            dE_dt = 0.0
        D = Kd * dE_dt
        self.last_dT_dt = dE_dt

        self.last_P = round(P, 4)
        self.last_I = round(I, 4)
        self.last_D = round(D, 4)

        # ── Feature 5: Feedforward ────────────────────────────────────
        # FF has the SAME sign as error:
        #   heating needed (error < 0): FF = ff_gain*(current-final) < 0 ✓
        #   cooling needed (error > 0): FF = ff_gain*(current-final) > 0 ✓
        ff_raw     = self.ff_gain * (current_temp - self._final_target)
        ff_clamped = max(-self.max_output, min(self.max_output, ff_raw))
        self.last_ff = round(ff_clamped, 4)

        # ── Total output ──────────────────────────────────────────────
        raw_output       = P + I + D + ff_clamped
        self.last_output = round(raw_output, 4)

        self._prev_error    = error
        self._was_saturated = abs(raw_output) >= self.max_output

        # ── Map to current magnitude + relay direction ────────────────
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

    # =================================================================
    #  RUNTIME TUNING
    # =================================================================

    def set_cool_gains(self, Kp, Ki, Kd):
        self.Kp_cool = Kp
        self.Ki_cool = Ki
        self.Kd_cool = Kd

    def set_heat_gains(self, Kp, Ki, Kd):
        self.Kp_heat = Kp
        self.Ki_heat = Ki
        self.Kd_heat = Kd

    # =================================================================
    #  DIAGNOSTICS
    # =================================================================

    def get_diagnostics(self) -> dict:
        """Backward-compatible diagnostics dict — original keys unchanged."""
        return {
            # Original keys
            "Kp":             self.Kp_cool,
            "Ki":             self.Ki_cool,
            "Kd":             self.Kd_cool,
            "error":          round(self.last_error, 4),
            "P":              self.last_P,
            "I":              self.last_I,
            "D":              self.last_D,
            "dT_dt":          round(self.last_dT_dt, 4),
            "output":         self.last_output,
            # New keys
            "ff":             self.last_ff,
            "mode":           self.last_mode,
            "adaptive":       self.last_adaptive,
            "ramp_target":    self.last_ramp_tgt,
            "ramp_remaining": self.ramp_remaining,
            "Kp_heat":        self.Kp_heat,
            "Ki_heat":        self.Ki_heat,
            "Kd_heat":        self.Kd_heat,
        }