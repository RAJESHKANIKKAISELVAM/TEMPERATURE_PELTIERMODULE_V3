"""
config.py
=========
Central configuration for the Peltier temperature control system.
ALL settings live here — edit this file only, never hardcode in other modules.

COM PORTS — change these to match your machine:
    TEMP_PORT : Arduino Uno R3  (DS18B20 + relay)
    PSU_PORT  : Hanmatek HM310T (Modbus RTU via RS-485)

TWO-STEP OVERSHOOT CALIBRATION WORKFLOW
========================================
STEP 1 — Measure your real overshoot:
    Set RAMP_RATE_DEG_PER_SEC = 0.0   (disable ramp — raw step response)
    Set PREDICT_RELAY_FLIP    = False  (disable prediction — baseline run)
    Run a session. Look at the temperature graph.
    Measure how many °C the temperature overshoots past the setpoint.
    Note that number — that is your real hardware overshoot distance.

STEP 2 — Enable predictive relay flip:
    Set RAMP_RATE_DEG_PER_SEC = 0.2   (re-enable ramp for smooth approach)
    Set PREDICT_RELAY_FLIP    = True   (enable prediction)
    Set PREDICT_SECONDS       = measured_overshoot / typical_dT_dt
        Example: overshoot=1.5°C, dT/dt=0.18°C/s → PREDICT_SECONDS = 8
    Run again and compare. Tune PREDICT_SECONDS until overshoot stays ±1°C.
"""

import os

# =================================================================
#  HARDWARE PORTS  ← change these if needed
# =================================================================
TEMP_PORT = "COM8"    # Arduino Uno R3  (DS18B20 + relay)
PSU_PORT  = "COM7"    # Hanmatek HM310T (Modbus RTU)

# =================================================================
#  PSU DEFAULTS
# =================================================================
DEFAULT_V = 12.0      # Voltage — fixed by user before START; never changed by code
DEFAULT_I = 3.0       # Max current — PID output is clamped to this value

# =================================================================
#  PID TUNING PARAMETERS  (legacy — kept for backward compat)
# =================================================================
PID_KP    = 0.30
PID_KI    = 0.02
PID_KD    = 0.50
PID_MIN_I = 0.10      # Min output current — below this relay coasts (OFF)

# =================================================================
#  ENHANCEMENT 1 — GAIN-SCHEDULED DUAL PID
# =================================================================
# Peltiers cool more efficiently than they heat (COP asymmetry).
# Use slightly higher gains for cooling, lower for heating.
# Tune these after your first real experimental session.
PID_KP_COOL = 0.35    # Cooling Kp  [A / °C]
PID_KI_COOL = 0.02    # Cooling Ki  [A / (°C·s)]
PID_KD_COOL = 0.55    # Cooling Kd  [A / (°C/s)]

PID_KP_HEAT = 0.25    # Heating Kp  [A / °C]
PID_KI_HEAT = 0.02    # Heating Ki  [A / (°C·s)]
PID_KD_HEAT = 0.45    # Heating Kd  [A / (°C/s)]

# =================================================================
#  ENHANCEMENT 2 — SETPOINT TRAJECTORY / RAMP GENERATOR
# =================================================================
# Ramp smooths large setpoint jumps into a gradual trajectory.
# Ramp always seeds from the actual measured temperature (not 0).
#
# STEP 1: Set to 0.0 to measure raw overshoot (no ramp, raw step)
# STEP 2: Set back to 0.2 after measuring overshoot
RAMP_RATE_DEG_PER_SEC = 0.0   # °C/s  ← SET TO 0.0 FOR STEP 1 MEASUREMENT

# =================================================================
#  ENHANCEMENT 4 — ADAPTIVE GAIN CONTROL
# =================================================================
ADAPTIVE_FAR_THRESHOLD = 5.0  # °C — beyond this distance, use FAR scale
ADAPTIVE_FAR_SCALE     = 1.4  # multiplier applied when far from setpoint
ADAPTIVE_NEAR_SCALE    = 1.0  # multiplier applied when near setpoint (no reduction)

# =================================================================
#  ENHANCEMENT 5 — FEEDFORWARD POWER ESTIMATION
# =================================================================
# FF = FF_GAIN × (current_temp − final_target)  [same sign as error]
FF_GAIN = 0.05        # A / °C  (0.0 = disabled)

# =================================================================
#  PREDICTIVE RELAY FLIP  (overshoot prevention)
# =================================================================
# How it works:
#   Every tick, the system predicts where temperature will be in
#   PREDICT_SECONDS seconds using current dT/dt (rate of change).
#   If the predicted temperature will cross setpoint ± HOLD_BAND,
#   the relay direction is flipped early to start braking NOW.
#   This gives the Peltier's thermal inertia time to slow down.
#
# STEP 1: Set PREDICT_RELAY_FLIP = False
#         Run session, measure overshoot on graph (e.g. 1.8°C)
#         Measure typical dT/dt during approach from graph (e.g. 0.20°C/s)
#         Calculate: PREDICT_SECONDS = overshoot / dT_dt = 1.8 / 0.20 = 9
#
# STEP 2: Set PREDICT_RELAY_FLIP = True
#         Set PREDICT_SECONDS to your calculated value
#         Run again — overshoot should now stay within ±1°C
#         Fine-tune PREDICT_SECONDS up/down by 1-2s if needed
#
# Safety guards:
#   - Only activates within NEAR_BAND (3°C) of setpoint
#   - Only activates if approaching fast enough (PREDICT_MIN_DTDT)
#   - Respects MIN_RELAY_FLIP_SEC to prevent chatter
#   - GUI shows BRAKING in red when active

PREDICT_RELAY_FLIP  = False  # ← False for STEP 1, True for STEP 2
PREDICT_SECONDS     = 8      # ← Tune this from your measured overshoot data
PREDICT_MIN_DTDT    = 0.05   # °C/s — minimum approach speed to trigger prediction
                              # (prevents false triggers when temperature is stable)

# =================================================================
#  CONTROL ZONES
# =================================================================
HOLD_BAND          = 1.0    # ±°C — within this window, HOLDING state begins
NEAR_BAND          = 3.0    # ±°C — inner approach / brake zone
MIN_RELAY_FLIP_SEC = 5.0    # Minimum seconds between relay direction changes

# =================================================================
#  GUI / LOGGING
# =================================================================
INTERVAL_MS = 1000    # Main update interval ms — also PID sample period dt = 1 s
MAX_LOG     = 500     # Maximum rows kept in the on-screen log widget
NUM_STEPS   = 5       # Number of sequential setpoint steps
MAX_GRAPH   = 600     # Maximum data points kept in live graph buffers

# =================================================================
#  PATHS
# =================================================================
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
LAB_REPORTS_DIR = os.path.join(BASE_DIR, "lab_reports")

# =================================================================
#  COLOUR PALETTE  (light-blue scientific theme)
# =================================================================
BG        = "#eaf4fb"
PANEL     = "#ffffff"
PANEL2    = "#d6eaf8"
HDR_BG    = "#1a6fa8"
HDR_FG    = "#ffffff"
ACCENT    = "#1a6fa8"
ACCENT2   = "#c0392b"
GREEN     = "#1e8449"
ORANGE    = "#d35400"
TEAL      = "#148f77"
PURPLE    = "#6c3483"
YLWDK     = "#9a7d0a"
PINKDK    = "#943126"
TEXT_MAIN = "#1a252f"
TEXT_DIM  = "#5d6d7e"
TEXT_LOG  = "#2e4057"
BORDER    = "#aed6f1"
GRAPH_BG  = "#f4f9fd"
STEP_ACT  = "#1a6fa8"
STEP_DONE = "#1e8449"
STEP_WAIT = "#aab7b8"