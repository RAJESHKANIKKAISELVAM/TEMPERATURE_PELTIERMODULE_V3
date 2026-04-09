"""
ui/live_readings.py
====================
Card 1 — Live Readings.

Builds:
  Left column : large temperature display + sensor status dot
  Right column: PSU voltage / current / power metrics + PSU status dot

Widget refs stored on state:
    state.temp_label, state.temp_status, state.temp_dot, state.temp_ts
    state.lbl_v, state.lbl_i, state.lbl_w
    state.psu_dot, state.psu_status, state.psu_prot
"""

import tkinter as tk
from config import (
    PANEL, PANEL2, BORDER, ACCENT, ACCENT2, GREEN, TEXT_DIM,
    PURPLE, YLWDK, PINKDK,
)


def build(state, parent, fonts):
    """
    Build Card 1 and store widget refs on state.

    Parameters:
        state  : AppState
        parent : tk.Frame — the card content frame returned by card()
        fonts  : dict of font objects from lab_monitor.py
    """
    F_BIG  = fonts["big"]
    F_MED  = fonts["med"]
    F_SM   = fonts["sm"]
    F_LBL  = fonts["lbl"]
    F_UNIT = fonts["unit"]

    r1    = tk.Frame(parent, bg=PANEL); r1.pack(fill="x", padx=10, pady=8)
    col_t = tk.Frame(r1, bg=PANEL);    col_t.pack(side="left", fill="both", expand=True)
    tk.Frame(r1, bg=BORDER, width=1).pack(side="left", fill="y", padx=10)
    col_p = tk.Frame(r1, bg=PANEL);    col_p.pack(side="right", fill="both", expand=True)

    # ── Temperature column ───────────────────────────────────────────
    tk.Label(col_t, text="LIVE TEMPERATURE", font=F_SM,
             fg=TEXT_DIM, bg=PANEL, anchor="w").pack(fill="x")

    tr = tk.Frame(col_t, bg=PANEL); tr.pack(anchor="w")
    state.temp_label = tk.Label(tr, text="--.-", font=F_BIG, fg=ACCENT, bg=PANEL)
    state.temp_label.pack(side="left")
    tk.Label(tr, text="°C", font=F_UNIT, fg=TEXT_DIM,
             bg=PANEL, pady=14).pack(side="left", anchor="s")

    tst = tk.Frame(col_t, bg=PANEL); tst.pack(fill="x")
    state.temp_dot = tk.Label(
        tst, text="●", font=F_SM,
        fg=GREEN if state.relay.connected else ACCENT2, bg=PANEL)
    state.temp_dot.pack(side="left")
    state.temp_status = tk.Label(
        tst,
        text="Connected" if state.relay.connected else f"Error: {state.relay.error}",
        font=F_SM,
        fg=GREEN if state.relay.connected else ACCENT2, bg=PANEL)
    state.temp_status.pack(side="left", padx=4)
    state.temp_ts = tk.Label(tst, text="", font=F_SM, fg=TEXT_DIM, bg=PANEL)
    state.temp_ts.pack(side="right")

    # ── PSU column ───────────────────────────────────────────────────
    tk.Label(col_p, text="PSU OUTPUT", font=F_SM,
             fg=TEXT_DIM, bg=PANEL, anchor="w").pack(fill="x")

    def _metric(p, ltext, color, unit):
        r = tk.Frame(p, bg=PANEL); r.pack(fill="x", pady=1)
        tk.Label(r, text=ltext, font=F_LBL, fg=TEXT_DIM,
                 bg=PANEL, width=10, anchor="w").pack(side="left")
        v = tk.Label(r, text="---", font=F_MED, fg=color, bg=PANEL)
        v.pack(side="left")
        tk.Label(r, text=f" {unit}", font=F_SM, fg=TEXT_DIM,
                 bg=PANEL, anchor="sw").pack(side="left", pady=2)
        return v

    state.lbl_v = _metric(col_p, "VOLTAGE", PURPLE, "V")
    state.lbl_i = _metric(col_p, "CURRENT", YLWDK,  "A")
    state.lbl_w = _metric(col_p, "POWER",   PINKDK, "W")

    pst = tk.Frame(col_p, bg=PANEL); pst.pack(fill="x", pady=(2, 0))
    state.psu_dot = tk.Label(
        pst, text="●", font=F_SM,
        fg=GREEN if state.psu.connected else ACCENT2, bg=PANEL)
    state.psu_dot.pack(side="left")
    state.psu_status = tk.Label(
        pst,
        text="Connected" if state.psu.connected else f"Error: {state.psu.error}",
        font=F_SM,
        fg=GREEN if state.psu.connected else ACCENT2, bg=PANEL)
    state.psu_status.pack(side="left", padx=4)
    state.psu_prot = tk.Label(pst, text="PROTECT: OK", font=F_SM,
                               fg=TEXT_DIM, bg=PANEL)
    state.psu_prot.pack(side="right")