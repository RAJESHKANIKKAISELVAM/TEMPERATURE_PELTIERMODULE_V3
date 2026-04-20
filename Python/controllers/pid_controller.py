"""
controllers/pid_controller.py
=============================
Single PID controller for Peltier temperature control.

All 15 audit bugs fixed. Key design decisions:

Signal separation:
  ramp_error  = current_temp - ramp_target    → P, I
  final_error = current_temp - final_target   → adaptive, FF, direction
  dT_dt       = (current_temp - prev_temp)/dt → D only (ramp-independent)

P conflict guard:
  When ramp lagging behind actual temp (opposite signs), P and I
  are zeroed so they don't fight the correct direction.
  Integral reset only fires ONCE per conflict episode (not every tick).

Feedforward disabled in hold zone:
  FF is zeroed when |final_error| < HOLD_BAND to prevent unnecessary
  current injection during stable holding.

Integral reset on HOLDING entry:
  Accumulated approach integral is cleared at HOLDING entry to prevent
  post-entry overshoot from stored integral energy.
"""

from config import (
    PID_KP, PID_KI, PID_KD,
    RAMP_RATE_DEG_PER_SEC,
    ADAPTIVE_FAR_THRESHOLD, ADAPTIVE_FAR_SCALE, ADAPTIVE_NEAR_SCALE,
    FF_GAIN, HOLD_BAND, NEAR_BAND,
)


class PIDController:

    def __init__(self,
                 Kp=0.3, Ki=0.02, Kd=0.5,
                 max_output=3.0, min_output=0.1,
                 integral_limit=5.0):

        self.Kp             = Kp
        self.Ki             = Ki
        self.Kd             = Kd
        self.max_output     = max_output
        self.min_output     = min_output
        self.integral_limit = integral_limit

        # Ramp
        self._final_target  = 0.0
        self._ramp_target   = 0.0
        self._ramp_active   = False
        self.ramp_rate      = RAMP_RATE_DEG_PER_SEC

        # Core PID state
        self.target         = 0.0
        self._integral      = 0.0
        self._prev_temp     = None

        # Anti-windup
        self._was_saturated = False

        # Adaptive gain
        self.adaptive_far_threshold = ADAPTIVE_FAR_THRESHOLD
        self.adaptive_far_scale     = ADAPTIVE_FAR_SCALE
        self.adaptive_near_scale    = ADAPTIVE_NEAR_SCALE

        # Feedforward
        self.ff_gain = FF_GAIN

        # P conflict guard — tracks episode so reset fires only once
        self._in_conflict    = False
        self._conflict_reset = False

        # Diagnostics
        self.last_P         = 0.0
        self.last_I         = 0.0
        self.last_D         = 0.0
        self.last_output    = 0.0
        self.last_error     = 0.0
        self.last_dT_dt     = 0.0
        self.last_ff        = 0.0
        self.last_mode      = "--"
        self.last_adaptive  = 1.0
        self.last_ramp_tgt  = 0.0
        self.ramp_remaining = 0.0
        self.last_conflict  = False

        # Legacy aliases
        self.Kp_cool = Kp; self.Ki_cool = Ki; self.Kd_cool = Kd
        self.Kp_heat = Kp; self.Ki_heat = Ki; self.Kd_heat = Kd

    # =================================================================
    #  PUBLIC API
    # =================================================================

    def set_target(self, target: float, current_temp: float = None):
        """Set new setpoint. Pass current_temp to seed ramp correctly."""
        self._final_target = target
        self._ramp_target  = current_temp if current_temp is not None else target
        self._ramp_active  = (
            self.ramp_rate > 0 and
            abs(target - self._ramp_target) > 0.5
        )
        # Reset conflict state for new step
        self._in_conflict    = False
        self._conflict_reset = False

    def reset(self):
        """Reset PID state. Called at start of each step."""
        self._integral       = 0.0
        self._prev_temp      = None
        self._was_saturated  = False
        self._in_conflict    = False
        self._conflict_reset = False
        self.last_conflict   = False
        self.last_P = self.last_I = self.last_D = 0.0
        self.last_output = self.last_error = self.last_dT_dt = self.last_ff = 0.0

    def reset_integral(self):
        """Called by control_loop when entering HOLDING to clear approach windup."""
        self._integral      = 0.0
        self._was_saturated = False

    def compute(self, current_temp: float, dt: float = 1.0):
        """
        Compute one PID tick.
        Returns: (current_A, direction)  direction: 'A'|'B'|'OFF'
        """
        if dt <= 0:
            dt = 1.0

        # ── Advance ramp ──────────────────────────────────────────────
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
        ramp_error  = current_temp - self._ramp_target    # for P, I
        final_error = current_temp - self._final_target   # for adaptive, FF, direction

        # Real temperature rate — independent of ramp movement
        dT_dt = (current_temp - self._prev_temp) / dt \
                if self._prev_temp is not None else 0.0
        self._prev_temp = current_temp
        self.last_dT_dt = dT_dt
        self.last_error = ramp_error
        self.last_mode  = "COOL" if final_error > 0 else "HEAT"

        # ── Adaptive gain by |final_error| ────────────────────────────
        abs_final = abs(final_error)
        if abs_final >= self.adaptive_far_threshold:
            adaptive_scale = self.adaptive_far_scale
        else:
            frac = abs_final / max(self.adaptive_far_threshold, 0.001)
            adaptive_scale = self.adaptive_near_scale + frac * (
                self.adaptive_far_scale - self.adaptive_near_scale)

        # Reduce D when far from setpoint — D should brake near setpoint,
        # not fight the approach from far away
        kd_scale = 0.3 if abs_final > NEAR_BAND else 1.0

        self.last_adaptive = round(adaptive_scale, 3)
        Kp = self.Kp * adaptive_scale
        Kd = self.Kd * adaptive_scale * kd_scale

        # ── P conflict guard ──────────────────────────────────────────
        # ramp_error and final_error have OPPOSITE signs when temp is
        # between ramp_target and final_target (ramp lagging behind).
        # Example: heating 20→25, ramp=20.99, temp=22.25
        #   ramp_error=+1.26 → P pushes COOL (wrong)
        #   final_error=-2.75 → correct direction is HEAT
        # Fix: zero P and I. Reset integral only ONCE per conflict episode.
        conflict_now = (ramp_error > 0) != (final_error > 0) and \
                       abs(final_error) > 0.1

        if conflict_now:
            if not self._in_conflict:
                # First tick of conflict — reset integral once
                self._integral       = 0.0
                self._was_saturated  = False
                self._in_conflict    = True
            P = 0.0; I = 0.0
            self.last_conflict = True
        else:
            self._in_conflict  = False
            self.last_conflict = False

            # ── P on ramp_error ───────────────────────────────────────
            P = Kp * ramp_error

            # ── I on ramp_error with anti-windup ─────────────────────
            if not self._was_saturated:
                self._integral += ramp_error * dt
            self._integral = max(-self.integral_limit,
                                 min(self.integral_limit, self._integral))
            I = self.Ki * self._integral

        # ── D on real dT_dt ───────────────────────────────────────────
        # dT_dt > 0 → rising → D > 0 → pushes cooling ✓
        # dT_dt < 0 → falling → D < 0 → pushes heating ✓
        # Frozen temp → dT_dt = 0 → D = 0 (no fake signal from ramp) ✓
        D = Kd * dT_dt

        self.last_P = round(P, 4)
        self.last_I = round(I, 4)
        self.last_D = round(D, 4)

        # ── Feedforward on final_error ────────────────────────────────
        # Disabled within HOLD_BAND — not needed for fine hold control
        # and prevents unnecessary current injection during stable hold
        if abs_final < HOLD_BAND:
            ff_clamped = 0.0
        else:
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
            direction = "OFF"; current_A = 0.0
        elif raw_output > 0:
            direction = "A"    # too hot → cool
        else:
            direction = "B"    # too cold → heat

        return current_A, direction

    # =================================================================
    #  RUNTIME TUNING
    # =================================================================

    def set_cool_gains(self, Kp, Ki, Kd):
        self.Kp = Kp; self.Ki = Ki; self.Kd = Kd
        self.Kp_cool = Kp; self.Ki_cool = Ki; self.Kd_cool = Kd
        self.Kp_heat = Kp; self.Ki_heat = Ki; self.Kd_heat = Kd

    def set_heat_gains(self, Kp, Ki, Kd):
        self.Kp = Kp; self.Ki = Ki; self.Kd = Kd
        self.Kp_cool = Kp; self.Ki_cool = Ki; self.Kd_cool = Kd
        self.Kp_heat = Kp; self.Ki_heat = Ki; self.Kd_heat = Kd

    # =================================================================
    #  DIAGNOSTICS
    # =================================================================

    def get_diagnostics(self) -> dict:
        return {
            "Kp": self.Kp, "Ki": self.Ki, "Kd": self.Kd,
            "error":          round(self.last_error, 4),
            "P":              self.last_P,
            "I":              self.last_I,
            "D":              self.last_D,
            "dT_dt":          round(self.last_dT_dt, 4),
            "output":         self.last_output,
            "ff":             self.last_ff,
            "mode":           self.last_mode,
            "adaptive":       self.last_adaptive,
            "ramp_target":    self.last_ramp_tgt,
            "ramp_remaining": self.ramp_remaining,
            "conflict":       self.last_conflict,
            "Kp_heat": self.Kp, "Ki_heat": self.Ki, "Kd_heat": self.Kd,
        }