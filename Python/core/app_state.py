"""
core/app_state.py
=================
AppState — single object that holds ALL shared state for the application.
"""

import threading
import time

from config import (
    DEFAULT_V, DEFAULT_I,
    PID_KP, PID_KI, PID_KD, PID_MIN_I,
    TEMP_PORT, PSU_PORT,
    RL_ENABLED, RL_ALPHA, RL_GAMMA,
    RL_EPSILON_START, RL_EPSILON_END, RL_TOTAL_SESSIONS,
)
from controllers import HM310T, RelayController, PIDController
from controllers.rl_controller  import RLController
from controllers.session_runner import AutoSessionRunner


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
            "state":      "IDLE",
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
        self.hold_regions       = []
        self._active_hold       = [None]
        self._hold_artists      = []

        # ── Session ───────────────────────────────────────────────────
        self.SESSION_DIR      = [None]
        self.SESSION_START_DT = [None]
        self.SESSION_END_DT   = [None]

        # ── Misc flags ────────────────────────────────────────────────
        self._SILENT_SAVE       = [False]
        self.manual_out         = [False]
        self.reading_count      = [0]
        self.log_rows           = []
        self._last_update_t     = [time.time()]
        self._psu_was_connected = [False]
        self._after_id          = [None]
        self._shutting_down     = [False]

        # Last valid temperature reading cache
        self.last_known_temp = [None]

        # Predictive relay flip state
        self.pred_braking    = [False]
        self.pred_flip_count = [0]

        # ── Q-Learning RL master controller ──────────────────────────
        self.rl = RLController(
            alpha          = RL_ALPHA,
            gamma          = RL_GAMMA,
            epsilon_start  = RL_EPSILON_START,
            epsilon_end    = RL_EPSILON_END,
            total_sessions = RL_TOTAL_SESSIONS,
        )
        self.rl.enabled = RL_ENABLED

        # Automated session runner
        self.runner = AutoSessionRunner()

        # Event used by runner to detect session completion
        self._runner_session_done = threading.Event()

        # RL tick counter — RL makes decisions every RL_TICK_INTERVAL seconds
        self.rl_tick_count = [0]

        # ── UI widget references ──────────────────────────────────────

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
        self.entry_v   = None
        self.entry_i   = None
        self.setpt_lbl = None
        self.btn_out   = None

        # pid_panel.py
        self.pid_err_lbl   = None
        self.pid_p_lbl     = None
        self.pid_i_lbl     = None
        self.pid_d_lbl     = None
        self.pid_out_lbl   = None
        self.pid_dir_lbl   = None
        self.pid_tune_lbl  = None
        self.entry_kp      = None
        self.entry_ki      = None
        self.entry_kd      = None
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
        self.hold_dev_lbl = None
        self.step_lbl     = None
        self.target_lbl   = None
        self.btn_start    = None
        self.btn_stop     = None
        self.step_entries = []

        # rl_panel widgets (built inside auto_controller status box)
        self.rl_progress_lbl = None
        self.rl_pct_lbl      = None
        self.rl_eta_lbl      = None
        self.rl_pb_canvas    = None
        self.rl_eps_lbl      = None
        self.rl_reward_lbl   = None
        self.rl_states_lbl   = None
        self.rl_action_lbl   = None
        self.rl_q_lbl        = None
        self.rl_status_lbl   = None
        self.rl_cooldown_lbl = None
        self.rl_start_btn    = None
        self.rl_pause_btn    = None
        self.rl_stop_btn     = None
        self.rl_toggle_btn   = None
        self.rl_toggle_var   = None

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
        self.graph_window = [300]
        self.btn_live     = None
        self.ani          = None

        # root window
        self.root = None