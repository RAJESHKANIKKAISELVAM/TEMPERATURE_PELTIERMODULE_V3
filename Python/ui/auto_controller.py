"""
ui/auto_controller.py
======================
Card 4 — Peltier Auto Controller: 5 sequential setpoints.
RL Training controls embedded inside the CONTROLLER STATUS box.
"""

import tkinter as tk
from config import (
    PANEL, PANEL2, BORDER, BG,
    ACCENT, ACCENT2, GREEN, TEAL, ORANGE, TEXT_DIM, TEXT_MAIN,
    STEP_ACT, STEP_DONE, STEP_WAIT,
    NUM_STEPS, PURPLE, YLWDK,
)

_DEFAULTS = [(25.0, 60), (22.0, 60), (20.0, 60), (18.0, 60), (16.0, 60)]


def build(state, parent, fonts):
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

    state.state_lbl    = _status_lbl("◉  IDLE",    TEXT_DIM, font=F_STATE)
    state.relay_lbl    = _status_lbl("RELAY:  OFF", TEXT_DIM)
    state.zone_lbl     = _status_lbl("ZONE:   --",  TEXT_DIM)
    state.hold_lbl     = _status_lbl("HOLD:   --",  GREEN)
    state.hold_dev_lbl = _status_lbl("DEV:    --",  TEXT_DIM)
    state.step_lbl     = _status_lbl("STEP:   --",  TEAL)
    state.target_lbl   = tk.Label(stbox, text="TARGET: --", font=F_SM,
                                   fg=TEAL, bg=PANEL2)
    state.target_lbl.pack(anchor="w", padx=10, pady=(1, 4))

    # ── RL Training compact panel ─────────────────────────────────────
    tk.Frame(stbox, bg=BORDER, height=1).pack(fill="x", padx=4)

    rl_hdr = tk.Frame(stbox, bg=PANEL2)
    rl_hdr.pack(fill="x", padx=4, pady=(3, 1))
    tk.Label(rl_hdr, text="Q-LEARNING", font=F_STEP,
             fg=PURPLE, bg=PANEL2).pack(side="left")

    state.rl_toggle_var = tk.BooleanVar(value=True)

    def _toggle_rl():
        state.rl.enabled = state.rl_toggle_var.get()
        col   = GREEN if state.rl.enabled else ACCENT2
        label = "RL:ON" if state.rl.enabled else "RL:OFF"
        state.rl_toggle_btn.config(text=label, fg=col)

    state.rl_toggle_btn = tk.Button(
        rl_hdr, text="RL:ON", font=F_STEP,
        fg=GREEN, bg=PANEL2, relief="flat", command=_toggle_rl)
    state.rl_toggle_btn.pack(side="right")

    # Progress row
    pr = tk.Frame(stbox, bg=PANEL2)
    pr.pack(fill="x", padx=4, pady=1)
    state.rl_progress_lbl = tk.Label(pr, text="Session: 0/300",
                                      font=F_STEP, fg=PURPLE, bg=PANEL2)
    state.rl_progress_lbl.pack(side="left")
    state.rl_eta_lbl = tk.Label(pr, text="ETA:--",
                                 font=F_STEP, fg=TEXT_DIM, bg=PANEL2)
    state.rl_eta_lbl.pack(side="right")

    # Stats row
    sr = tk.Frame(stbox, bg=PANEL2)
    sr.pack(fill="x", padx=4, pady=1)
    state.rl_eps_lbl    = tk.Label(sr, text="ε:0.900",
                                    font=F_STEP, fg=ORANGE, bg=PANEL2)
    state.rl_reward_lbl = tk.Label(sr, text="R:--",
                                    font=F_STEP, fg=GREEN,  bg=PANEL2)
    state.rl_action_lbl = tk.Label(sr, text="A:--",
                                    font=F_STEP, fg=PURPLE, bg=PANEL2)
    state.rl_eps_lbl.pack(side="left",   padx=2)
    state.rl_reward_lbl.pack(side="left", padx=2)
    state.rl_action_lbl.pack(side="left", padx=2)

    # Unused attrs — expected by rl_panel.update_display
    state.rl_pct_lbl    = None
    state.rl_pb_canvas  = None
    state.rl_states_lbl = None
    state.rl_q_lbl      = None

    # Status + cooldown
    state.rl_status_lbl = tk.Label(
        stbox, text="◉ IDLE — press START TRAINING",
        font=F_STEP, fg=TEXT_DIM, bg=PANEL2)
    state.rl_status_lbl.pack(anchor="w", padx=8, pady=(1, 1))

    state.rl_cooldown_lbl = tk.Label(stbox, text="",
                                      font=F_STEP, fg=ORANGE, bg=PANEL2)
    state.rl_cooldown_lbl.pack(anchor="w", padx=8)

    # RL Buttons
    rb = tk.Frame(stbox, bg=PANEL2)
    rb.pack(fill="x", padx=4, pady=(2, 6))

    def _start_training():
        if not state.runner.active:
            state.runner.start_training(
                state, target_sessions=300, hold_seconds=60)
            state.rl_start_btn.config(state="disabled")
            state.rl_pause_btn.config(state="normal")
            state.rl_stop_btn.config(state="normal")

    def _pause_training():
        if state.runner.active and not state.runner.paused:
            state.runner.pause()
            state.rl_pause_btn.config(
                text="RESUME", command=_resume_training)

    def _resume_training():
        if state.runner.paused:
            state.runner.resume(state)
            state.rl_pause_btn.config(
                text="PAUSE", command=_pause_training)

    def _stop_training():
        state.runner.stop(state)
        state.rl.save()
        state.rl_start_btn.config(state="normal")
        state.rl_pause_btn.config(
            state="disabled", text="PAUSE", command=_pause_training)
        state.rl_stop_btn.config(state="disabled")
        state.rl_status_lbl.config(
            text="◉ STOPPED — Q-table saved", fg=ACCENT2)

    state.rl_start_btn = tk.Button(
        rb, text="▶ START TRAINING", font=F_STEP,
        bg=PURPLE, fg="white", relief="flat", padx=6, pady=2,
        command=_start_training)
    state.rl_start_btn.pack(side="left", padx=(0, 3))

    state.rl_pause_btn = tk.Button(
        rb, text="PAUSE", font=F_STEP,
        bg=ORANGE, fg="white", relief="flat", padx=6, pady=2,
        state="disabled", command=_pause_training)
    state.rl_pause_btn.pack(side="left", padx=3)

    state.rl_stop_btn = tk.Button(
        rb, text="■ STOP", font=F_STEP,
        bg=ACCENT2, fg="white", relief="flat", padx=6, pady=2,
        state="disabled", command=_stop_training)
    state.rl_stop_btn.pack(side="left", padx=3)

    # Wire runner callbacks
    def _on_status_change(status, msg):
        color_map = {
            "RUNNING": GREEN, "COOLING": ORANGE, "WAITING": TEAL,
            "PAUSED":  ORANGE, "DONE":   GREEN,  "ERROR":   ACCENT2,
            "IDLE":    TEXT_DIM,
        }
        col = color_map.get(status, TEXT_DIM)
        state.root.after(0, lambda: state.rl_status_lbl.config(
            text=f"◉ {status} — {msg}", fg=col))

    def _on_cooldown_tick(secs):
        state.root.after(0, lambda: state.rl_cooldown_lbl.config(
            text=f"Next session in {secs}s..." if secs > 0 else ""))

    state.runner.on_status_change = _on_status_change
    state.runner.on_cooldown_tick = _on_cooldown_tick