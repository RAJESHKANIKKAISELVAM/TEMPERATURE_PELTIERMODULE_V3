"""
controllers/pid_controller.py
=============================
Enhanced parallel PID controller for Peltier temperature control.

Features:
  1. Gain-Scheduled Dual PID  — separate Kp/Ki/Kd for HEAT vs COOL direction
  2. Setpoint Ramp Generator  — smooth intermediate targets, seeded from current temp
  3. Back-calc Anti-Windup    — integral freezes when output saturates
  4. Adaptive Gain Control    — aggressive far from final target, gentle near it
  5. Feedforward              — pre-emptive current push toward final target

Signal separation (the key architectural decision):
  ramp_error  = current_temp - ramp_target    → P term, I term
  final_error = current_temp - final_target   → gain selection, adaptive scale, FF
  dT_dt       = (current_temp - prev_temp)/dt → D term only (ramp-independent)

This separation fixes 3 bugs present in the single-error design:
  Bug 1: Gain selection by ramp_error flips wrong when temp overshoots ramp
  Bug 2: Adaptive threshold vs ramp_error never fires (ramp keeps error tiny)
  Bug 3: Derivative on ramp_error produces fake signal from ramp advancement

Sign convention (unchanged from original):
  final_error > 0  → too hot  → COOL → Relay A
  final_error < 0  → too cold → HEAT → Relay B
  |output| < min_output → relay OFF (coast)
"""

from config import (
    PID_KP_COOL, PID_KI_COOL, PID_KD_COOL,
    PID_KP_HEAT, PID_KI_HEAT, PID_KD_HEAT,
    RAMP_RATE_DEG_PER_SEC,
    ADAPTIVE_FAR_THRESHOLD, ADAPTIVE_FAR_SCALE, ADAPTIVE_NEAR_SCALE,
    FF_GAIN,
)


class PIDController:
    """
    Enhanced PID controller with signal separation, gain scheduling,
    ramp generator, back-calculation anti-windup, adaptive gain,
    and feedforward.
    """

    def __init__(self,
                 Kp=0.3,
                 Ki=0.02,
                 Kd=0.5,
                 max_output=3.0,
                 min_output=0.1,
                 integral_limit=5.0):

        # Legacy attrs (backward compat with app_state.py)
        self.Kp             = Kp
        self.Ki             = Ki
        self.Kd             = Kd
        self.max_output     = max_output
        self.min_output     = min_output
        self.integral_limit = integral_limit

        # Feature 1: Dual gain sets
        self.Kp_cool = PID_KP_COOL
        self.Ki_cool = PID_KI_COOL
        self.Kd_cool = PID_KD_COOL
        self.Kp_heat = PID_KP_HEAT
        self.Ki_heat = PID_KI_HEAT
        self.Kd_heat = PID_KD_HEAT

        # Feature 2: Ramp generator state
        self._final_target  = 0.0
        self._ramp_target   = 0.0
        self._ramp_active   = False
        self.ramp_rate      = RAMP_RATE_DEG_PER_SEC

        # Core PID state
        self.target         = 0.0
        self._integral      = 0.0
        self._prev_temp     = None  # previous temperature for real dT/dt

        # Feature 3: Anti-windup saturation flag
        self._was_saturated = False

        # Feature 4: Adaptive gain thresholds
        self.adaptive_far_threshold = ADAPTIVE_FAR_THRESHOLD
        self.adaptive_far_scale     = ADAPTIVE_FAR_SCALE
        self.adaptive_near_scale    = ADAPTIVE_NEAR_SCALE

        # Feature 5: Feedforward gain
        self.ff_gain = FF_GAIN

        # Diagnostics
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
        Set new final setpoint. Always pass current_temp so ramp
        seeds from actual temperature, not 0.0.
        """
        self._final_target = target

        if current_temp is not None:
            self._ramp_target = current_temp
        else:
            self._ramp_target = target

        self._ramp_active = (
            self.ramp_rate > 0 and
            abs(target - self._ramp_target) > 0.5
        )

    def reset(self):
        """
        Reset integral, derivative memory, and saturation flag.
        Does NOT touch ramp state.
        """
        self._integral      = 0.0
        self._prev_temp     = None
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
        Compute one PID tick.

        Returns:
            (current_A, direction)
            current_A : PSU current magnitude (A)
            direction : 'A' (cool) | 'B' (heat) | 'OFF' (coast)
        """
        if dt <= 0:
            dt = 1.0

        # ── Feature 2: Advance ramp ───────────────────────────────────
        if self._ramp_active:
            step = self.ramp_rate * dt
            diff = self._final_target - self._ramp_target
            if abs(diff) <= step:
                self._ramp_target = self._final_target
                self._ramp_active = False
            else:
                self._ramp_target += step if diff > 0 else -step

        self.target         = self._ramp_target
        self.last_ramp_tgt  = round(self._ramp_target, 3)
        self.ramp_remaining = round(
            abs(self._final_target - self._ramp_target), 3)

        # ── Signal separation ─────────────────────────────────────────
        ramp_error  = current_temp - self._ramp_target   # P, I
        final_error = current_temp - self._final_target  # gain select, adaptive, FF

        # Real temperature rate — ramp movement does NOT contaminate this
        if self._prev_temp is not None:
            dT_dt = (current_temp - self._prev_temp) / dt
        else:
            dT_dt = 0.0
        self._prev_temp  = current_temp
        self.last_dT_dt  = dT_dt
        self.last_error  = ramp_error   # GUI shows ramp tracking error

        # ── Feature 1: Gain selection by final_error ──────────────────
        # Stable signal — never flips incorrectly when temp overshoots ramp
        if final_error > 0:
            Kp, Ki, Kd     = self.Kp_cool, self.Ki_cool, self.Kd_cool
            self.last_mode = "COOL"
        else:
            Kp, Ki, Kd     = self.Kp_heat, self.Ki_heat, self.Kd_heat
            self.last_mode = "HEAT"

        # ── Feature 4: Adaptive scale by |final_error| ───────────────
        # Now fires correctly — 11°C from setpoint gives FAR boost
        # Previously abs_err was 0-0.5 with ramp, boost never triggered
        abs_final = abs(final_error)
        if abs_final >= self.adaptive_far_threshold:
            adaptive_scale = self.adaptive_far_scale
        else:
            frac = abs_final / max(self.adaptive_far_threshold, 0.001)
            adaptive_scale = (
                self.adaptive_near_scale +
                frac * (self.adaptive_far_scale - self.adaptive_near_scale)
            )
        self.last_adaptive = round(adaptive_scale, 3)
        Kp = Kp * adaptive_scale
        Kd = Kd * adaptive_scale   # Ki NOT scaled — keeps integral consistent

        # ── P on ramp_error ───────────────────────────────────────────
        P = Kp * ramp_error

        # ── Feature 3: Anti-windup ────────────────────────────────────
        if not self._was_saturated:
            self._integral += ramp_error * dt
        self._integral = max(-self.integral_limit,
                             min(self.integral_limit, self._integral))
        I = Ki * self._integral

        # ── D on real dT_dt ───────────────────────────────────────────
        # dT_dt > 0 → temp rising → D > 0 → pushes cooling ✓
        # dT_dt < 0 → temp falling → D < 0 → pushes heating ✓
        # Frozen temp → dT_dt = 0 → D = 0 ✓ (no fake signal)
        D = Kd * dT_dt

        self.last_P = round(P, 4)
        self.last_I = round(I, 4)
        self.last_D = round(D, 4)

        # ── Feature 5: Feedforward on final_error ─────────────────────
        # final_error > 0 → FF > 0 → pushes cooling ✓
        # final_error < 0 → FF < 0 → pushes heating ✓
        ff_raw     = self.ff_gain * final_error
        ff_clamped = max(-self.max_output, min(self.max_output, ff_raw))
        self.last_ff = round(ff_clamped, 4)

        # ── Total output ──────────────────────────────────────────────
        raw_output       = P + I + D + ff_clamped
        self.last_output = round(raw_output, 4)

        self._was_saturated = abs(raw_output) >= self.max_output

        # ── Map to current + direction ────────────────────────────────
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
        """Backward-compatible diagnostics — original keys unchanged."""
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
            # Enhancement keys
            "ff":             self.last_ff,
            "mode":           self.last_mode,
            "adaptive":       self.last_adaptive,
            "ramp_target":    self.last_ramp_tgt,
            "ramp_remaining": self.ramp_remaining,
            "Kp_heat":        self.Kp_heat,
            "Ki_heat":        self.Ki_heat,
            "Kd_heat":        self.Kd_heat,
        }