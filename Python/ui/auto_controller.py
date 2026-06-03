"""
ui/auto_controller.py
======================
Card 4 — Peltier Auto Controller.
Compact professional layout — no wasted space.

Layout:
  Top bar  : MODE toggle + RL:ON/OFF (full width, no gap)
  Left col : Step table + START/STOP
  Right col: Controller status (grid) + Q-Learning section
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

    state.op_mode = tk.StringVar(value="experiment")

    # ── TOP BAR: mode + RL toggle ─────────────────────────────────
    top = tk.Frame(parent, bg=PANEL2)
    top.pack(fill="x")

    tk.Label(top, text="MODE:", font=F_STEP,
             fg=TEXT_DIM, bg=PANEL2, padx=8).pack(side="left")

    def _set_training():
        state.op_mode.set("training")
        _apply_mode()

    def _set_experiment():
        state.op_mode.set("experiment")
        _apply_mode()

    state._btn_train_mode = tk.Button(
        top, text="⚙  TRAINING", font=F_STEP,
        bg=PANEL2, fg=TEXT_DIM, relief="flat",
        padx=10, pady=3, command=_set_training)
    state._btn_train_mode.pack(side="left", padx=2, pady=2)

    state._btn_exp_mode = tk.Button(
        top, text="🔬  EXPERIMENT", font=F_STEP,
        bg=TEAL, fg="white", relief="flat",
        padx=10, pady=3, command=_set_experiment)
    state._btn_exp_mode.pack(side="left", padx=2, pady=2)

    state.rl_toggle_var = tk.BooleanVar(value=False)

    def _toggle_rl():
        state.rl.enabled = state.rl_toggle_var.get()
        col   = GREEN if state.rl.enabled else ACCENT2
        label = "RL:ON" if state.rl.enabled else "RL:OFF"
        state.rl_toggle_btn.config(text=label, fg=col)

    state.rl_toggle_btn = tk.Button(
        top, text="RL:OFF", font=F_STEP,
        fg=ACCENT2, bg=PANEL2, relief="flat",
        padx=6, pady=3, command=_toggle_rl)
    state.rl_toggle_btn.pack(side="right", padx=8, pady=2)

    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x")

    # ── BODY: left + right columns ────────────────────────────────
    body = tk.Frame(parent, bg=PANEL)
    body.pack(fill="both", expand=True)

    # ── LEFT: step table ──────────────────────────────────────────
    left = tk.Frame(body, bg=PANEL)
    left.pack(side="left", fill="y", padx=(8, 4), pady=6)

    for ci, (txt, ww) in enumerate([
            ("#", 3), ("TARGET °C", 9), ("HOLD s", 7), ("STATUS", 9)]):
        tk.Label(left, text=txt, font=F_STEP, fg=ACCENT,
                 bg=PANEL2, width=ww, anchor="w",
                 padx=4, pady=2).grid(row=0, column=ci, sticky="ew",
                                       padx=1, pady=(0, 2))

    state.step_entries = []
    for i in range(NUM_STEPS):
        r = i + 1
        tk.Label(left, text=f"#{i+1}", font=F_STEP,
                 fg=TEXT_MAIN, bg=PANEL).grid(
                     row=r, column=0, padx=4, pady=1)

        te = tk.Entry(left, font=F_ENT, width=7, bg=BG, fg=TEAL,
                      relief="solid", highlightbackground=BORDER,
                      highlightthickness=1, justify="center")
        te.insert(0, str(_DEFAULTS[i][0]))
        te.grid(row=r, column=1, padx=2, pady=1)

        he = tk.Entry(left, font=F_ENT, width=5, bg=BG, fg=GREEN,
                      relief="solid", highlightbackground=BORDER,
                      highlightthickness=1, justify="center")
        he.insert(0, str(_DEFAULTS[i][1]))
        he.grid(row=r, column=2, padx=2, pady=1)

        sl = tk.Label(left, text="WAITING", font=F_STEP,
                      fg=STEP_WAIT, bg=PANEL, anchor="w", width=9)
        sl.grid(row=r, column=3, padx=4, sticky="w")

        state.step_entries.append((te, he, sl))

    br = tk.Frame(left, bg=PANEL)
    br.grid(row=6, column=0, columnspan=4, pady=(5, 0), sticky="w")
    state._manual_btn_frame = br

    def _start():
        from core.control_loop import start_ctrl
        start_ctrl(state)

    def _stop():
        from core.control_loop import stop_ctrl
        stop_ctrl(state)

    state.btn_start = tk.Button(
        br, text="▶  START", font=F_LBL,
        bg=GREEN, fg="white", relief="flat",
        padx=10, pady=3, command=_start)
    state.btn_start.pack(side="left", padx=(0, 6))

    state.btn_stop = tk.Button(
        br, text="■  STOP", font=F_LBL,
        bg=ACCENT2, fg="white", relief="flat",
        padx=10, pady=3, command=_stop, state="disabled")
    state.btn_stop.pack(side="left")

    # ── SEPARATOR ─────────────────────────────────────────────────
    tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y", pady=4)

    # ── RIGHT: status + RL ────────────────────────────────────────
    right = tk.Frame(body, bg=PANEL2)
    right.pack(side="left", fill="both", expand=True, padx=(4, 6), pady=4)
    right.columnconfigure(1, weight=1)

    # State label (full width)
    state.state_lbl = tk.Label(right, text="◉  IDLE",
                                font=F_STATE, fg=TEXT_DIM, bg=PANEL2)
    state.state_lbl.grid(row=0, column=0, columnspan=2,
                          sticky="w", padx=6, pady=(4, 2))

    # Status rows: label | value
    def _row(label, val_color, r):
        tk.Label(right, text=label, font=F_STEP,
                 fg=TEXT_DIM, bg=PANEL2, anchor="w",
                 width=7).grid(row=r, column=0, sticky="w", padx=(6, 0), pady=1)
        v = tk.Label(right, text="--", font=F_STEP,
                     fg=val_color, bg=PANEL2, anchor="w")
        v.grid(row=r, column=1, sticky="w", padx=2, pady=1)
        return v

    state.relay_lbl    = _row("RELAY:", TEXT_DIM, 1)
    state.zone_lbl     = _row("ZONE:",  TEXT_DIM, 2)
    state.hold_lbl     = _row("HOLD:",  GREEN,     3)
    state.hold_dev_lbl = _row("DEV:",   TEXT_DIM, 4)

    # Step + Target on one row
    st_row = tk.Frame(right, bg=PANEL2)
    st_row.grid(row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=1)
    tk.Label(st_row, text="STEP:", font=F_STEP,
             fg=TEXT_DIM, bg=PANEL2, width=5, anchor="w").pack(side="left")
    state.step_lbl = tk.Label(st_row, text="--", font=F_STEP,
                               fg=TEAL, bg=PANEL2)
    state.step_lbl.pack(side="left", padx=(2, 10))
    tk.Label(st_row, text="TGT:", font=F_STEP,
             fg=TEXT_DIM, bg=PANEL2).pack(side="left")
    state.target_lbl = tk.Label(st_row, text="--", font=F_STEP,
                                 fg=TEAL, bg=PANEL2)
    state.target_lbl.pack(side="left", padx=2)

    # ── RL divider ────────────────────────────────────────────────
    tk.Frame(right, bg=BORDER, height=1).grid(
        row=6, column=0, columnspan=2, sticky="ew", padx=4, pady=(3, 1))

    # RL header + session progress
    rl_h = tk.Frame(right, bg=PANEL2)
    rl_h.grid(row=7, column=0, columnspan=2, sticky="ew", padx=4, pady=1)
    tk.Label(rl_h, text="Q-LEARNING", font=F_STEP,
             fg=PURPLE, bg=PANEL2).pack(side="left")
    state.rl_progress_lbl = tk.Label(rl_h, text="0/300",
                                      font=F_STEP, fg=PURPLE, bg=PANEL2)
    state.rl_progress_lbl.pack(side="left", padx=6)
    state.rl_eta_lbl = tk.Label(rl_h, text="ETA:--",
                                 font=F_STEP, fg=TEXT_DIM, bg=PANEL2)
    state.rl_eta_lbl.pack(side="right")

    # RL stats
    rl_s = tk.Frame(right, bg=PANEL2)
    rl_s.grid(row=8, column=0, columnspan=2, sticky="ew", padx=4, pady=1)
    state.rl_eps_lbl    = tk.Label(rl_s, text="e:0.900",
                                    font=F_STEP, fg=ORANGE, bg=PANEL2)
    state.rl_reward_lbl = tk.Label(rl_s, text="R:--",
                                    font=F_STEP, fg=GREEN,  bg=PANEL2)
    state.rl_action_lbl = tk.Label(rl_s, text="A:--",
                                    font=F_STEP, fg=PURPLE, bg=PANEL2)
    state.rl_eps_lbl.pack(side="left",    padx=(0, 6))
    state.rl_reward_lbl.pack(side="left", padx=(0, 6))
    state.rl_action_lbl.pack(side="left")

    # RL status
    state.rl_status_lbl = tk.Label(
        right, text="◉ EXPERIMENT — RL off",
        font=F_STEP, fg=TEXT_DIM, bg=PANEL2, anchor="w")
    state.rl_status_lbl.grid(
        row=9, column=0, columnspan=2, sticky="ew", padx=6, pady=1)

    state.rl_cooldown_lbl = tk.Label(right, text="",
                                      font=F_STEP, fg=ORANGE, bg=PANEL2,
                                      anchor="w")
    state.rl_cooldown_lbl.grid(
        row=10, column=0, columnspan=2, sticky="ew", padx=6)

    # RL buttons
    rb = tk.Frame(right, bg=PANEL2)
    rb.grid(row=11, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 4))

    state.rl_pct_lbl    = None
    state.rl_pb_canvas  = None
    state.rl_states_lbl = None
    state.rl_q_lbl      = None

    def _start_training():
        if not state.runner.active:
            state.runner.start_training(state, target_sessions=300,
                                         hold_seconds=60)
            state.rl_start_btn.config(state="disabled")
            state.rl_pause_btn.config(state="normal")
            state.rl_stop_btn.config(state="normal")

    def _pause_training():
        if state.runner.active and not state.runner.paused:
            state.runner.pause()
            state.rl_pause_btn.config(text="RESUME", command=_resume_training)

    def _resume_training():
        if state.runner.paused:
            state.runner.resume(state)
            state.rl_pause_btn.config(text="PAUSE", command=_pause_training)

    def _stop_training():
        state.runner.stop(state)
        state.rl.save()
        state.rl_start_btn.config(state="normal")
        state.rl_pause_btn.config(
            state="disabled", text="PAUSE", command=_pause_training)
        state.rl_stop_btn.config(state="disabled")
        state.rl_status_lbl.config(text="◉ STOPPED — saved", fg=ACCENT2)

    state.rl_start_btn = tk.Button(
        rb, text="▶ START", font=F_STEP,
        bg=PURPLE, fg="white", relief="flat",
        padx=6, pady=2, command=_start_training, state="disabled")
    state.rl_start_btn.pack(side="left", padx=(0, 2))

    state.rl_pause_btn = tk.Button(
        rb, text="PAUSE", font=F_STEP,
        bg=ORANGE, fg="white", relief="flat",
        padx=6, pady=2, state="disabled", command=_pause_training)
    state.rl_pause_btn.pack(side="left", padx=2)

    state.rl_stop_btn = tk.Button(
        rb, text="■ STOP", font=F_STEP,
        bg=ACCENT2, fg="white", relief="flat",
        padx=6, pady=2, state="disabled", command=_stop_training)
    state.rl_stop_btn.pack(side="left", padx=2)

    # Runner callbacks
    def _on_status_change(status, msg):
        color_map = {
            "RUNNING": GREEN, "COOLING": ORANGE, "WAITING": TEAL,
            "PAUSED":  ORANGE, "DONE":   GREEN,  "ERROR":   ACCENT2,
            "IDLE":    TEXT_DIM,
        }
        col   = color_map.get(status, TEXT_DIM)
        short = msg[:28] + "…" if len(msg) > 28 else msg
        state.root.after(0, lambda: state.rl_status_lbl.config(
            text=f"◉ {status} — {short}", fg=col))

    def _on_cooldown_tick(secs):
        state.root.after(0, lambda: state.rl_cooldown_lbl.config(
            text=f"Next in {secs}s..." if secs > 0 else ""))

    state.runner.on_status_change = _on_status_change
    state.runner.on_cooldown_tick = _on_cooldown_tick

    # ── Mode logic ────────────────────────────────────────────────
    def _apply_mode():
        mode = state.op_mode.get()
        if mode == "training":
            state._btn_train_mode.config(bg=PURPLE, fg="white")
            state._btn_exp_mode.config(bg=PANEL2,  fg=TEXT_DIM)
            for te, he, _ in state.step_entries:
                te.config(state="disabled", bg=PANEL2)
                he.config(state="disabled", bg=PANEL2)
            state._manual_btn_frame.grid_remove()
            state.rl.enabled = True
            state.rl_toggle_var.set(True)
            state.rl_toggle_btn.config(text="RL:ON", fg=GREEN)
            state.rl_start_btn.config(state="normal")
            state.rl_status_lbl.config(
                text="◉ TRAINING — press START", fg=PURPLE)
        else:
            state._btn_exp_mode.config(bg=TEAL,    fg="white")
            state._btn_train_mode.config(bg=PANEL2, fg=TEXT_DIM)
            if state.runner.active:
                state.runner.active = False
                state.runner.paused = False
            for te, he, _ in state.step_entries:
                te.config(state="normal", bg=BG)
                he.config(state="normal", bg=BG)
            state._manual_btn_frame.grid()
            state.rl.enabled = False
            state.rl_toggle_var.set(False)
            state.rl_toggle_btn.config(text="RL:OFF", fg=ACCENT2)
            state.rl_start_btn.config(state="disabled")
            state.rl_pause_btn.config(state="disabled")
            state.rl_stop_btn.config(state="disabled")
            state.rl_status_lbl.config(
                text="◉ EXPERIMENT — RL off", fg=TEXT_DIM)

    state._apply_mode = _apply_mode
    _apply_mode()