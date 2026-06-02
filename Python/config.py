"""
config.py — Peltier Temperature Control System
All constants here. Never hardcode in other modules.
"""
import os

# =================================================================
#  HARDWARE PORTS
# =================================================================
TEMP_PORT = "COM4"   # Arduino Uno R3 (DS18B20 + relay)
PSU_PORT  = "COM3"   # Hanmatek HM310T (Modbus RTU)

# =================================================================
#  PSU DEFAULTS
# =================================================================
DEFAULT_V = 12.0
DEFAULT_I = 3.0

# =================================================================
#  PID GAINS
# =================================================================
PID_KP    = 0.30
PID_KI    = 0.02
PID_KD    = 0.50
PID_MIN_I = 0.10   # min PSU current — below this relay coasts OFF

# =================================================================
#  RAMP GENERATOR
# =================================================================
# 0.0 = disabled (Step 1 measurement mode — raw step response)
# 0.2 = normal operation (smooth approach)
RAMP_RATE_DEG_PER_SEC = 0.2   # deg/s

# =================================================================
#  ADAPTIVE GAIN
# =================================================================
ADAPTIVE_FAR_THRESHOLD = 5.0   # deg — beyond this use FAR scale
ADAPTIVE_FAR_SCALE     = 1.4   # multiplier far from setpoint
ADAPTIVE_NEAR_SCALE    = 1.0   # multiplier near setpoint (no reduction)

# =================================================================
#  FEEDFORWARD
# =================================================================
# FF = FF_GAIN x final_error — pre-emptive push toward target
# Automatically disabled when within HOLD_BAND (no overshoot risk)
FF_GAIN = 0.05   # A/deg

# =================================================================
#  PREDICTIVE RELAY BRAKING
# =================================================================
# remaining  = abs(final_target - current_temp)
# brake_dist = abs(dT_dt) * PREDICT_SECONDS
# Brake when remaining <= brake_dist AND approaching
#
# STEP 1: PREDICT_RELAY_FLIP=False, RAMP_RATE=0.0 — measure overshoot
# STEP 2: PREDICT_RELAY_FLIP=True,  RAMP_RATE=0.2 — enable braking
#         PREDICT_SECONDS = measured_overshoot / approach_dT_dt

PREDICT_RELAY_FLIP  = False  # False=Step1, True=Step2
PREDICT_SECONDS     = 8      # tune: overshoot_deg / dT_dt
PREDICT_MIN_DTDT    = 0.10   # deg/s — min speed (>= 2x DS18B20 resolution)
BRAKE_CHECK_ZONE    = 6.0    # deg — start checking this far from setpoint
BRAKE_CURRENT_SCALE = 0.5    # fraction of current during braking

# =================================================================
#  CONTROL ZONES
# =================================================================
HOLD_BAND          = 1.0   # ±deg — HOLDING state valid within this
NEAR_BAND          = 3.0   # ±deg — NEAR zone label
MIN_RELAY_FLIP_SEC = 5.0   # minimum seconds between relay direction changes

# =================================================================
#  GUI / LOGGING
# =================================================================
INTERVAL_MS = 1000
MAX_LOG     = 500
NUM_STEPS   = 5
MAX_GRAPH   = 600

# =================================================================
#  PATHS
# =================================================================
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
LAB_REPORTS_DIR = os.path.join(BASE_DIR, "lab_reports")

# =================================================================
#  COLOUR PALETTE
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

# Legacy aliases — keep old imports working
PID_KP_COOL = PID_KP; PID_KI_COOL = PID_KI; PID_KD_COOL = PID_KD
PID_KP_HEAT = PID_KP; PID_KI_HEAT = PID_KI; PID_KD_HEAT = PID_KD