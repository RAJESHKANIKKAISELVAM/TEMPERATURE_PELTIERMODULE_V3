"""
ui/auto_controller.py
======================
Card 4 — Peltier Auto Controller: 5 sequential setpoints.

Left side : table of target °C + hold seconds + status per step
Right side: controller status box (state, relay, zone, hold timer, step, target)
Bottom    : START / STOP buttons

Widget refs stored on state:
    state.step_entries  — list of (target_entry, hold_entry, status_label)
    state.state_lbl, state.relay_lbl, state.zone_lbl
    state.hold_lbl, state.step_lbl, state.target_lbl
    state.btn_start, state.btn_stop
"""

import tkinter as tk
from config import (
    PANEL, PANEL2, BORDER, BG,
    ACCENT, ACCENT2, GREEN, TEAL, ORANGE, TEXT_DIM, TEXT_MAIN,
    STEP_ACT, STEP_DONE, STEP_WAIT,
    NUM_STEPS,
)


# Default setpoints shown in the table at startup
_DEFAULTS = [(25.0, 60), (22.0, 60), (20.0, 60), (18.0, 60), (16.0, 60)]


def build(state, parent, fonts):
    """
    Build Card 4 and store widget refs on state.

    Parameters:
        state  : AppState
        parent : tk.Frame — the card content frame
        fonts  : dict of font objects
    """
    F_SM    = fonts["sm"]
    F_LBL   = fonts["lbl"]
    F_ENT   = fonts["ent"]
    F_STEP  = fonts["step"]
    F_STATE = fonts["state"]

    ac = tk.Frame(parent, bg=PANEL); ac.pack(fill="x", padx=10, pady=6)

    # ── Step table ───────────────────────────────────────────────────
    tbl = tk.Frame(ac, bg=PANEL); tbl.pack(side="left", fill="x")

    for ci, (txt, ww) in enumerate([("#", 3), ("TARGET °C", 9),
                                     ("HOLD s", 8), ("STATUS", 9)]):
        tk.Label(tbl, text=txt, font=F_STEP, fg=ACCENT,
                 bg=PANEL2, width=ww, anchor="w",
                 padx=4, pady=2).grid(row=0, column=ci, sticky="ew",
                                       padx=1, pady=(0, 2))

    state.step_entries = []
    for i in range(NUM_STEPS):
        r = i + 1
        tk.Label(tbl, text=f"#{i+1}", font=F_STEP,
                 fg=TEXT_MAIN, bg=PANEL).grid(row=r, column=0, padx=4, pady=2)

        te = tk.Entry(tbl, font=F_ENT, width=7, bg=BG, fg=TEAL,
                      relief="solid", highlightbackground=BORDER,
                      highlightthickness=1, justify="center")
        te.insert(0, str(_DEFAULTS[i][0]))
        te.grid(row=r, column=1, padx=3, pady=2)

        he = tk.Entry(tbl, font=F_ENT, width=6, bg=BG, fg=GREEN,
                      relief="solid", highlightbackground=BORDER,
                      highlightthickness=1, justify="center")
        he.insert(0, str(_DEFAULTS[i][1]))
        he.grid(row=r, column=2, padx=3, pady=2)

        sl = tk.Label(tbl, text="WAITING", font=F_STEP,
                      fg=STEP_WAIT, bg=PANEL, anchor="w", width=10)
        sl.grid(row=r, column=3, padx=6, sticky="w")

        state.step_entries.append((te, he, sl))

    # ── START / STOP buttons ─────────────────────────────────────────
    br = tk.Frame(tbl, bg=PANEL)
    br.grid(row=6, column=0, columnspan=4, pady=(6, 0), sticky="w")

    def _start():
        from core.control_loop import start_ctrl
        start_ctrl(state)

    def _stop():
        from core.control_loop import stop_ctrl
        stop_ctrl(state)

    state.btn_start = tk.Button(
        br, text="▶  START", font=F_LBL,
        bg=GREEN, fg="white", relief="flat",
        padx=12, pady=4, command=_start)
    state.btn_start.pack(side="left", padx=(0, 8))

    state.btn_stop = tk.Button(
        br, text="■  STOP", font=F_LBL,
        bg=ACCENT2, fg="white", relief="flat",
        padx=12, pady=4, command=_stop, state="disabled")
    state.btn_stop.pack(side="left")

    # ── Status box ───────────────────────────────────────────────────
    stbox = tk.Frame(ac, bg=PANEL2,
                     highlightbackground=BORDER, highlightthickness=1)
    stbox.pack(side="left", fill="both", expand=True, padx=(14, 0))

    tk.Label(stbox, text="CONTROLLER STATUS", font=F_STEP,
             fg=ACCENT, bg=PANEL2).pack(anchor="w", padx=10, pady=(6, 3))

    def _status_lbl(text, color, font=None):
        lbl = tk.Label(stbox, text=text, font=font or F_SM,
                       fg=color, bg=PANEL2)
        lbl.pack(anchor="w", padx=10, pady=1)
        return lbl

    state.state_lbl  = _status_lbl("◉  IDLE",    TEXT_DIM, font=F_STATE)
    state.relay_lbl  = _status_lbl("RELAY:  OFF", TEXT_DIM)
    state.zone_lbl   = _status_lbl("ZONE:   --",  TEXT_DIM)
    state.hold_lbl   = _status_lbl("HOLD:   --",  GREEN)
    state.step_lbl   = _status_lbl("STEP:   --",  TEAL)
    state.target_lbl = tk.Label(stbox, text="TARGET: --", font=F_SM,
                                fg=TEAL, bg=PANEL2)
    state.target_lbl.pack(anchor="w", padx=10, pady=(1, 8))