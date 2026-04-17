"""
ui/pid_panel.py
===============
Card 3 — PID Controller Live Diagnostics + Tuning.

Row 1 : live P / I / D / error / output / direction   (original)
Row 2 : mode (HEAT/COOL) / FF / adaptive / ramp       (new)
Row 3 : COOL gain entry fields
Row 4 : HEAT gain entry fields + APPLY PID button
"""

import tkinter as tk
from config import (
    PANEL, PANEL2, BORDER, BG,
    ACCENT, ACCENT2, GREEN, TEAL, ORANGE, YLWDK, PURPLE, TEXT_DIM,
    PID_KP_COOL, PID_KI_COOL, PID_KD_COOL,
    PID_KP_HEAT, PID_KI_HEAT, PID_KD_HEAT,
)


def build(state, parent, fonts):
    F_SM   = fonts["sm"]
    F_LBL  = fonts["lbl"]
    F_ENT  = fonts["ent"]
    F_STEP = fonts["step"]
    F_PID  = fonts["pid"]

    # ── Row 1: Core PID diagnostics (original) ───────────────────────
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

    # ── Row 2: Enhancement diagnostics (new) ─────────────────────────
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

    # ── Row 3: COOL gains ─────────────────────────────────────────────
    pt_cool = tk.Frame(parent, bg=PANEL)
    pt_cool.pack(fill="x", padx=10, pady=(4, 1))
    tk.Label(pt_cool, text="COOL:", font=F_SM, fg=ACCENT, bg=PANEL).pack(side="left")

    def _entry(frame, label, default, color):
        tk.Label(frame, text=f"  {label}=", font=F_SM,
                 fg=TEXT_DIM, bg=PANEL).pack(side="left")
        e = tk.Entry(frame, font=F_ENT, width=6, bg=BG, fg=color,
                     relief="solid", highlightbackground=BORDER,
                     highlightthickness=1)
        e.insert(0, str(default))
        e.pack(side="left", padx=2)
        return e

    state.entry_kp = _entry(pt_cool, "Kp", PID_KP_COOL, ACCENT)
    state.entry_ki = _entry(pt_cool, "Ki", PID_KI_COOL, TEAL)
    state.entry_kd = _entry(pt_cool, "Kd", PID_KD_COOL, ORANGE)

    # ── Row 4: HEAT gains + APPLY button ─────────────────────────────
    pt_heat = tk.Frame(parent, bg=PANEL)
    pt_heat.pack(fill="x", padx=10, pady=(1, 4))
    tk.Label(pt_heat, text="HEAT:", font=F_SM, fg=ORANGE, bg=PANEL).pack(side="left")

    state.entry_kp_heat = _entry(pt_heat, "Kp", PID_KP_HEAT, ACCENT)
    state.entry_ki_heat = _entry(pt_heat, "Ki", PID_KI_HEAT, TEAL)
    state.entry_kd_heat = _entry(pt_heat, "Kd", PID_KD_HEAT, ORANGE)

    def apply_pid():
        try:
            kp_c = float(state.entry_kp.get())
            ki_c = float(state.entry_ki.get())
            kd_c = float(state.entry_kd.get())
            kp_h = float(state.entry_kp_heat.get())
            ki_h = float(state.entry_ki_heat.get())
            kd_h = float(state.entry_kd_heat.get())

            state.pid.set_cool_gains(kp_c, ki_c, kd_c)
            state.pid.set_heat_gains(kp_h, ki_h, kd_h)
            # Keep legacy attrs in sync
            state.pid.Kp = kp_c
            state.pid.Ki = ki_c
            state.pid.Kd = kd_c

            state.pid_tune_lbl.config(
                text=(f"Applied  COOL Kp={kp_c} Ki={ki_c} Kd={kd_c} | "
                      f"HEAT Kp={kp_h} Ki={ki_h} Kd={kd_h}"),
                fg=GREEN)
        except ValueError:
            state.pid_tune_lbl.config(text="Invalid values!", fg=ACCENT2)

    tk.Button(pt_heat, text="APPLY PID", font=F_STEP, bg=TEAL, fg="white",
              relief="flat", padx=8, pady=2,
              command=apply_pid).pack(side="left", padx=8)

    state.pid_tune_lbl = tk.Label(parent, text="", font=F_SM, fg=GREEN, bg=PANEL)
    state.pid_tune_lbl.pack(anchor="w", padx=10, pady=(0, 4))