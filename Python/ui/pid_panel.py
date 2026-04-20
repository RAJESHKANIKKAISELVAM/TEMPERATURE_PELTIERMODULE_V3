"""
ui/pid_panel.py
===============
Card 3 — PID Controller Live Diagnostics + Tuning.
Single PID — dual gain rows removed.

Row 1 : ERROR / P / I / D / OUTPUT / DIRECTION
Row 2 : MODE / FF / ADAPT× / RAMP °C
Row 3 : Kp / Ki / Kd entry + APPLY PID button
"""

import tkinter as tk
from config import (
    PANEL, PANEL2, BORDER, BG,
    ACCENT, ACCENT2, GREEN, TEAL, ORANGE, YLWDK, PURPLE, TEXT_DIM,
    PID_KP, PID_KI, PID_KD,
)


def build(state, parent, fonts):
    F_SM   = fonts["sm"]
    F_LBL  = fonts["lbl"]
    F_ENT  = fonts["ent"]
    F_STEP = fonts["step"]
    F_PID  = fonts["pid"]

    # ── Row 1: Core PID diagnostics ──────────────────────────────────
    pd = tk.Frame(parent, bg=PANEL)
    pd.pack(fill="x", padx=10, pady=(6, 2))

    def _pid_col(label, color, frame):
        r = tk.Frame(frame, bg=PANEL); r.pack(side="left", padx=7)
        tk.Label(r, text=label, font=F_PID, fg=TEXT_DIM, bg=PANEL).pack()
        val = tk.Label(r, text="0.000", font=F_PID, fg=color, bg=PANEL)
        val.pack()
        return val

    state.pid_err_lbl = _pid_col("ERROR (°C)", ACCENT2, pd)
    state.pid_p_lbl   = _pid_col("P",          ACCENT,  pd)
    state.pid_i_lbl   = _pid_col("I",          TEAL,    pd)
    state.pid_d_lbl   = _pid_col("D (dT/dt)",  ORANGE,  pd)
    state.pid_out_lbl = _pid_col("OUTPUT (A)", YLWDK,   pd)
    state.pid_dir_lbl = _pid_col("DIRECTION",  GREEN,   pd)

    # ── Row 2: Enhancement diagnostics ───────────────────────────────
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x")
    pe = tk.Frame(parent, bg=PANEL)
    pe.pack(fill="x", padx=10, pady=(3, 2))

    def _enh_col(label, color, frame):
        r = tk.Frame(frame, bg=PANEL); r.pack(side="left", padx=7)
        tk.Label(r, text=label, font=F_PID, fg=TEXT_DIM, bg=PANEL).pack()
        val = tk.Label(r, text="--", font=F_PID, fg=color, bg=PANEL)
        val.pack()
        return val

    state.pid_mode_lbl = _enh_col("MODE",    PURPLE, pe)
    state.pid_ff_lbl   = _enh_col("FF (A)",  YLWDK,  pe)
    state.pid_adp_lbl  = _enh_col("ADAPT×",  TEAL,   pe)
    state.pid_rmp_lbl  = _enh_col("RAMP °C", ORANGE, pe)

    # ── Separator ────────────────────────────────────────────────────
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x")

    # ── Row 3: Single gain tuning ─────────────────────────────────────
    pt = tk.Frame(parent, bg=PANEL)
    pt.pack(fill="x", padx=10, pady=(4, 4))
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

    # Legacy attrs — kept so other modules don't crash
    state.entry_kp_heat = state.entry_kp
    state.entry_ki_heat = state.entry_ki
    state.entry_kd_heat = state.entry_kd

    def apply_pid():
        try:
            kp = float(state.entry_kp.get())
            ki = float(state.entry_ki.get())
            kd = float(state.entry_kd.get())
            state.pid.Kp = kp
            state.pid.Ki = ki
            state.pid.Kd = kd
            # Keep legacy attrs in sync
            state.pid.Kp_cool = kp; state.pid.Ki_cool = ki; state.pid.Kd_cool = kd
            state.pid.Kp_heat = kp; state.pid.Ki_heat = ki; state.pid.Kd_heat = kd
            state.pid_tune_lbl.config(
                text=f"Applied: Kp={kp}  Ki={ki}  Kd={kd}",
                fg=GREEN)
        except ValueError:
            state.pid_tune_lbl.config(text="Invalid values!", fg=ACCENT2)

    tk.Button(pt, text="APPLY PID", font=F_STEP, bg=TEAL, fg="white",
              relief="flat", padx=8, pady=2,
              command=apply_pid).pack(side="left", padx=8)

    state.pid_tune_lbl = tk.Label(parent, text="", font=F_SM, fg=GREEN, bg=PANEL)
    state.pid_tune_lbl.pack(anchor="w", padx=10, pady=(0, 4))