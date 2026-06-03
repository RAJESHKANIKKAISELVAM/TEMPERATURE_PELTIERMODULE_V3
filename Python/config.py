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
#  PID GAINS — base values (RL scales these, adaptive compounds)
# =================================================================
PID_KP    = 0.30
PID_KI    = 0.02
PID_KD    = 0.50
PID_MIN_I = 0.10   # min PSU current — below this relay coasts OFF

# =================================================================
#  RAMP GENERATOR
# =================================================================
RAMP_RATE_DEG_PER_SEC = 0.2

# =================================================================
#  ADAPTIVE GAIN
# =================================================================
ADAPTIVE_FAR_THRESHOLD = 5.0
ADAPTIVE_FAR_SCALE     = 1.4
ADAPTIVE_NEAR_SCALE    = 1.0

# =================================================================
#  FEEDFORWARD
# =================================================================
FF_GAIN = 0.05

# =================================================================
#  PREDICTIVE RELAY BRAKING
# =================================================================
PREDICT_RELAY_FLIP  = False
PREDICT_SECONDS     = 5
PREDICT_MIN_DTDT    = 0.10
BRAKE_CHECK_ZONE    = 6.0
BRAKE_CURRENT_SCALE = 0.5

# =================================================================
#  CONTROL ZONES
# =================================================================
HOLD_BAND          = 1.0
NEAR_BAND          = 3.0
MIN_RELAY_FLIP_SEC = 2.0

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

# Legacy aliases
PID_KP_COOL = PID_KP; PID_KI_COOL = PID_KI; PID_KD_COOL = PID_KD
PID_KP_HEAT = PID_KP; PID_KI_HEAT = PID_KI; PID_KD_HEAT = PID_KD

# =================================================================
#  Q-LEARNING / RL CONSTANTS
# =================================================================
RL_ENABLED        = True
RL_TICK_INTERVAL  = 1       # seconds between RL gain adjustments
RL_ALPHA          = 0.1     # Q-learning rate
RL_GAMMA          = 0.95    # discount factor
RL_EPSILON_START  = 0.9     # initial exploration rate
RL_EPSILON_END    = 0.05    # final exploration rate
RL_TOTAL_SESSIONS = 300     # training target
RL_HOLD_SECONDS   = 60      # hold time per step during training

# RL gain bounds — prevents compounding of RL × adaptive gain
# Effective Kp = PID_KP × kp_scale_RL (adaptive applied INSIDE pid.compute separately)
RL_MAX_KP_SCALE   = 1.5     # RL cannot scale Kp above this × PID_KP = 0.45 max
RL_MAX_CURRENT    = 3.0     # RL cannot set current above this (hardware safety)
# =================================================================
#  TRAINING MODE — skip heavy exports (PDF/PNG) during 300 sessions
# =================================================================
TRAINING_MODE_LITE_SAVE = True   # set False to re-enable full exports