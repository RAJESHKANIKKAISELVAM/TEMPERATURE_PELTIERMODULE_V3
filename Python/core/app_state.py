"""
core/app_state.py
=================
AppState — single object that holds ALL shared state for the application.

Every module receives an AppState instance. Nothing is a bare global.

Sections:
    Hardware objects   — psu, relay, pid
    Control state      — ctrl dict (IDLE/APPROACH/HOLDING/DONE, step, target …)
    Graph data         — g_times, g_temps, g_setpts, g_volts, g_currs, g_pid_*
    PSU live readings  — psu_live dict + psu_lock
    Research data      — step_data, _current_step_data, hold_regions, _active_hold
    Session            — SESSION_DIR, SESSION_START_DT, SESSION_END_DT
    UI widget refs     — set by each ui/ module after widgets are built
    Misc flags         — _SILENT_SAVE, manual_out, reading_count, _hold_artists
    Prediction state   — pred_braking, pred_flip_count
"""

import threading
import time

from config import (
    DEFAULT_V, DEFAULT_I,
    PID_KP, PID_KI, PID_KD, PID_MIN_I,
    TEMP_PORT, PSU_PORT,
)
from controllers import HM310T, RelayController, PIDController


class AppState:
    def __init__(self):

        # ── Hardware ─────────────────────────────────────────────────
        self.psu   = HM310T(PSU_PORT)
        self.relay = RelayController(TEMP_PORT)
        self.pid   = PIDController(
            Kp         = PID_KP,
            Ki         = PID_KI,
            Kd         = PID_KD,
            max_output = DEFAULT_I,
            min_output = PID_MIN_I,
        )

        # ── Control state ─────────────────────────────────────────────
        self.ctrl = {
            "state":      "IDLE",   # IDLE | APPROACH | HOLDING | DONE
            "step":       0,
            "target":     0.0,
            "hold_secs":  0,
            "hold_end":   None,
            "_steps":     [],
            "_t0":        None,
            "_last_flip": 0.0,
            "_voltage":   DEFAULT_V,
            "_max_i":     DEFAULT_I,
        }

        # ── Graph data ────────────────────────────────────────────────
        self.glock   = threading.Lock()
        self.g_times = []; self.g_temps  = []; self.g_setpts = []
        self.g_volts = []; self.g_currs  = []
        self.g_pid_p = []; self.g_pid_i  = []; self.g_pid_d  = []

        # ── PSU live readings ─────────────────────────────────────────
        self.psu_lock = threading.Lock()
        self.psu_live = {
            "voltage": 0.0,
            "current": 0.0,
            "power":   0.0,
            "protect": [],
        }

        # ── Research / step data ──────────────────────────────────────
        self.step_data          = []
        self._current_step_data = [None]

        # Hold region markers for temperature graph shading
        # Each entry: [elapsed_start, elapsed_end_or_None, step_num]
        self.hold_regions  = []
        self._active_hold  = [None]   # index into hold_regions
        self._hold_artists = []       # (span_patch, vline_s, vline_e, text)

        # ── Session ───────────────────────────────────────────────────
        self.SESSION_DIR      = [None]
        self.SESSION_START_DT = [None]
        self.SESSION_END_DT   = [None]

        # ── Misc flags ────────────────────────────────────────────────
        self._SILENT_SAVE   = [False]
        self.manual_out     = [False]
        self.reading_count  = [0]
        self.log_rows       = []
        self._last_update_t = [time.time()]
        self._psu_was_connected = [False]

        # ── Predictive relay flip state ───────────────────────────────
        # pred_braking    : True on ticks where prediction fired a relay flip
        # pred_flip_count : total early flips this step (shown in GUI as ×N)
        # Both reset to zero at start_ctrl() and each _load_step()
        self.pred_braking    = [False]
        self.pred_flip_count = [0]

        # ── UI widget references (set by ui/ modules after build) ─────
        # live_readings.py
        self.temp_label  = None
        self.temp_status = None
        self.temp_dot    = None
        self.temp_ts     = None
        self.lbl_v       = None
        self.lbl_i       = None
        self.lbl_w       = None
        self.psu_dot     = None
        self.psu_status  = None
        self.psu_prot    = None

        # psu_controls.py
        self.entry_v    = None
        self.entry_i    = None
        self.setpt_lbl  = None
        self.btn_out    = None

        # pid_panel.py
        self.pid_err_lbl  = None
        self.pid_p_lbl    = None
        self.pid_i_lbl    = None
        self.pid_d_lbl    = None
        self.pid_out_lbl  = None
        self.pid_dir_lbl  = None
        self.pid_tune_lbl = None
        self.entry_kp     = None
        self.entry_ki     = None
        self.entry_kd     = None
        # Enhancement diagnostic labels
        self.pid_mode_lbl  = None
        self.pid_ff_lbl    = None
        self.pid_adp_lbl   = None
        self.pid_rmp_lbl   = None
        self.entry_kp_heat = None
        self.entry_ki_heat = None
        self.entry_kd_heat = None

        # auto_controller.py
        self.state_lbl    = None
        self.relay_lbl    = None
        self.zone_lbl     = None
        self.hold_lbl     = None
        self.step_lbl     = None
        self.target_lbl   = None
        self.btn_start    = None
        self.btn_stop     = None
        self.step_entries = []   # list of (target_entry, hold_entry, status_label)

        # log_panel.py
        self.log_box  = None
        self.log_cnt  = None
        self.auto_scr = [True]

        # graphs.py
        self.fig          = None
        self.ax_t         = None
        self.ax_vi        = None
        self.ax_vi2       = None
        self.ax_pid       = None
        self.mpl_canvas   = None
        self.line_temp    = None
        self.line_setp    = None
        self.line_volt    = None
        self.line_curr    = None
        self.line_p       = None
        self.line_i       = None
        self.line_d       = None
        self.graph_live   = [True]
        self.graph_window = [300]   # active live window seconds
        self.btn_live     = None
        self.ani          = None

        # root window — set by lab_monitor.py
        self.root = None