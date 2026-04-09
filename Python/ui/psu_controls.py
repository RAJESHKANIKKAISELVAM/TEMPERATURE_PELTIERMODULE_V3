"""
ui/psu_controls.py
==================
Card 2 — PSU Set-points.

Voltage is fixed by the user before START and never changed by code during a run.
Max current sets the PID output clamp.

Widget refs stored on state:
    state.entry_v, state.entry_i, state.setpt_lbl, state.btn_out
"""

import tkinter as tk
import threading

from config import (
    PANEL, PANEL2, BORDER, BG,
    ACCENT, ACCENT2, GREEN, ORANGE, TEXT_DIM,
    PURPLE, YLWDK,
    DEFAULT_V, DEFAULT_I,
)


def build(state, parent, fonts):
    """
    Build Card 2 and store widget refs on state.

    Parameters:
        state  : AppState
        parent : tk.Frame — the card content frame
        fonts  : dict of font objects
    """
    F_SM  = fonts["sm"]
    F_LBL = fonts["lbl"]
    F_ENT = fonts["ent"]
    F_STEP = fonts["step"]

    sp = tk.Frame(parent, bg=PANEL); sp.pack(fill="x", padx=10, pady=8)

    tk.Label(sp, text="Voltage (V):", font=F_SM, fg=TEXT_DIM,
             bg=PANEL).grid(row=0, column=0, sticky="e", padx=(0,4), pady=3)
    state.entry_v = tk.Entry(sp, font=F_ENT, width=7, bg=BG, fg=PURPLE,
                             relief="solid", highlightbackground=BORDER,
                             highlightthickness=1)
    state.entry_v.insert(0, str(DEFAULT_V))
    state.entry_v.grid(row=0, column=1, padx=4)

    tk.Label(sp, text="Max Current (A):", font=F_SM, fg=TEXT_DIM,
             bg=PANEL).grid(row=0, column=2, sticky="e", padx=(10,4))
    state.entry_i = tk.Entry(sp, font=F_ENT, width=7, bg=BG, fg=YLWDK,
                             relief="solid", highlightbackground=BORDER,
                             highlightthickness=1)
    state.entry_i.insert(0, str(DEFAULT_I))
    state.entry_i.grid(row=0, column=3, padx=4)

    state.setpt_lbl = tk.Label(
        sp, text=f"Set → {DEFAULT_V:.2f}V / {DEFAULT_I:.3f}A max",
        font=F_SM, fg=GREEN, bg=PANEL)
    state.setpt_lbl.grid(row=0, column=5, padx=(10, 0))

    def apply_sp():
        if not state.psu.connected:
            state.setpt_lbl.config(text="PSU not connected!", fg=ACCENT2); return
        if state.ctrl["state"] not in ("IDLE", "DONE"):
            state.setpt_lbl.config(text="Stop run before changing!", fg=ACCENT2); return
        try:
            v = float(state.entry_v.get())
            i = float(state.entry_i.get())
        except ValueError:
            state.setpt_lbl.config(text="Invalid!", fg=ACCENT2); return
        state.pid.max_output = i
        state.setpt_lbl.config(text="Applying...", fg=TEXT_DIM)
        def _do():
            v_ok = state.psu.set_voltage(v)
            i_ok = state.psu.set_current(i)
            def _upd():
                if v_ok and i_ok:
                    state.setpt_lbl.config(
                        text=f"Set → {v:.2f}V / {i:.3f}A max", fg=GREEN)
                else:
                    state.setpt_lbl.config(
                        text="Write failed — check PSU", fg=ACCENT2)
            state.root.after(0, _upd)
        threading.Thread(target=_do, daemon=True).start()

    tk.Button(sp, text="APPLY", font=F_LBL, bg=ACCENT, fg="white",
              relief="flat", padx=10, pady=2,
              command=apply_sp).grid(row=0, column=4, padx=6)

    def tog_out():
        if not state.psu.connected: return
        def _do():
            if state.manual_out[0]:
                state.psu.output_off()
                state.manual_out[0] = False
                state.root.after(0, lambda: state.btn_out.config(
                    text="OUTPUT: OFF", bg=ACCENT2))
            else:
                ok = state.psu.output_on()
                state.manual_out[0] = ok
                state.root.after(0, lambda: state.btn_out.config(
                    text="OUTPUT: ON" if ok else "WRITE FAIL",
                    bg=GREEN if ok else ACCENT2))
        threading.Thread(target=_do, daemon=True).start()

    state.btn_out = tk.Button(sp, text="OUTPUT: OFF", font=F_LBL,
                              bg=ACCENT2, fg="white", relief="flat",
                              padx=10, pady=2, command=tog_out)
    state.btn_out.grid(row=1, column=0, columnspan=3, pady=(5, 0), sticky="w")