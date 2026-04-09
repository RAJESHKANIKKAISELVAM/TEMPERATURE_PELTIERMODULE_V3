"""
config.py
=========
Central configuration for the Peltier temperature control system.
ALL settings live here — edit this file only, never hardcode in other modules.

COM PORTS — change these to match your machine:
    TEMP_PORT : Arduino Uno R3  (DS18B20 + relay)
    PSU_PORT  : Hanmatek HM310T (Modbus RTU via RS-485)
"""

import os

# =================================================================
#  HARDWARE PORTS  ← change these if needed
# =================================================================
TEMP_PORT = "COM8"    # Arduino Uno R3  (DS18B20 + relay)
PSU_PORT  = "COM7"   # Hanmatek HM310T (Modbus RTU)

# =================================================================
#  PSU DEFAULTS
# =================================================================
DEFAULT_V = 12.0      # Voltage — fixed by user before START; never changed by code
DEFAULT_I = 3.0       # Max current — PID output is clamped to this value

# =================================================================
#  PID TUNING PARAMETERS
# =================================================================
# NOTE: Starting defaults — NOT yet tuned with real experimental data.
#       Adjust after open-loop step-response characterisation.
PID_KP    = 0.30      # Proportional gain  [A / °C]
PID_KI    = 0.02      # Integral gain      [A / (°C·s)]
PID_KD    = 0.50      # Derivative gain    [A / (°C/s)]
PID_MIN_I = 0.10      # Min output current — below this relay coasts (OFF)

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