"""
ui/pid_panel.py
===============
Card 3 — PID Controller Live Diagnostics + Tuning.

Top row   : live P / I / D / error / output / direction values (updated by control_loop)
Bottom row: Kp / Ki / Kd entry fields + APPLY PID button

Widget refs stored on state:
    state.pid_err_lbl, state.pid_p_lbl, state.pid_i_lbl
    state.pid_d_lbl, state.pid_out_lbl, state.pid_dir_lbl
    state.entry_kp, state.entry_ki, state.entry_kd
    state.pid_tune_lbl
"""

import tkinter as tk
from config import (
    PANEL, PANEL2, BORDER, BG,
    ACCENT, ACCENT2, GREEN, TEAL, ORANGE, YLWDK, TEXT_DIM,
    PID_KP, PID_KI, PID_KD,
)


def build(state, parent, fonts):
    """
    Build Card 3 and store widget refs on state.

    Parameters:
        state  : AppState
        parent : tk.Frame — the card content frame
        fonts  : dict of font objects
    """
    F_SM   = fonts["sm"]
    F_LBL  = fonts["lbl"]
    F_ENT  = fonts["ent"]
    F_STEP = fonts["step"]
    F_PID  = fonts["pid"]

    # ── Diagnostics row ──────────────────────────────────────────────
    pd = tk.Frame(parent, bg=PANEL); pd.pack(fill="x", padx=10, pady=6)

    def _pid_col(label, color):
        r = tk.Frame(pd, bg=PANEL); r.pack(side="left", padx=8)
        tk.Label(r, text=label, font=F_PID, fg=TEXT_DIM, bg=PANEL).pack()
        val = tk.Label(r, text="0.000", font=F_PID, fg=color, bg=PANEL)
        val.pack()
        return val

    state.pid_err_lbl = _pid_col("ERROR (°C)", ACCENT2)
    state.pid_p_lbl   = _pid_col("P",          ACCENT)
    state.pid_i_lbl   = _pid_col("I",          TEAL)
    state.pid_d_lbl   = _pid_col("D (dT/dt)",  ORANGE)
    state.pid_out_lbl = _pid_col("OUTPUT (A)", YLWDK)
    state.pid_dir_lbl = _pid_col("DIRECTION",  GREEN)

    # ── Tuning row ───────────────────────────────────────────────────
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x")
    pt = tk.Frame(parent, bg=PANEL); pt.pack(fill="x", padx=10, pady=4)
    tk.Label(pt, text="Tune:", font=F_SM, fg=TEXT_DIM, bg=PANEL).pack(side="left")

    def _entry(label, default, color):
        tk.Label(pt, text=f"  {label}=", font=F_SM,
                 fg=TEXT_DIM, bg=PANEL).pack(side="left")
        e = tk.Entry(pt, font=F_ENT, width=6, bg=BG, fg=color,
                     relief="solid", highlightbackground=BORDER,
                     highlightthickness=1)
        e.insert(0, str(default))
        e.pack(side="left", padx=2)
        return e

    state.entry_kp = _entry("Kp", PID_KP, ACCENT)
    state.entry_ki = _entry("Ki", PID_KI, TEAL)
    state.entry_kd = _entry("Kd", PID_KD, ORANGE)

    def apply_pid():
        try:
            state.pid.Kp = float(state.entry_kp.get())
            state.pid.Ki = float(state.entry_ki.get())
            state.pid.Kd = float(state.entry_kd.get())
            state.pid_tune_lbl.config(
                text=f"Applied: Kp={state.pid.Kp} Ki={state.pid.Ki} Kd={state.pid.Kd}",
                fg=GREEN)
        except ValueError:
            state.pid_tune_lbl.config(text="Invalid values!", fg=ACCENT2)

    tk.Button(pt, text="APPLY PID", font=F_STEP, bg=TEAL, fg="white",
              relief="flat", padx=8, pady=2,
              command=apply_pid).pack(side="left", padx=8)

    state.pid_tune_lbl = tk.Label(pt, text="", font=F_SM, fg=GREEN, bg=PANEL)
    state.pid_tune_lbl.pack(side="left")