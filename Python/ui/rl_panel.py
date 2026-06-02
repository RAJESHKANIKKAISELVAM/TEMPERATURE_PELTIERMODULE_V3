"""
ui/rl_panel.py
==============
RL panel update_display function.
The actual widgets are built inside auto_controller.py status box.
This module only provides the update_display() function called every tick.
"""

from config import GREEN, ACCENT2, ORANGE, PURPLE, TEAL, TEXT_DIM


def build(state, parent, fonts):
    """
    No-op — RL widgets are built inside auto_controller.py.
    This function exists so lab_monitor.py import does not break.
    """
    pass


def update_display(state):
    """
    Refresh RL widgets every tick.
    Safe to call even if widgets not built — all accesses guarded.
    """
    try:
        if not hasattr(state, 'rl_eps_lbl') or state.rl_eps_lbl is None:
            return

        stats    = state.rl.get_stats()
        progress = state.runner.get_progress(state.rl)

        # Progress label
        if state.rl_progress_lbl is not None:
            state.rl_progress_lbl.config(
                text=f"Session: {progress['sessions_done']}"
                     f"/{progress['sessions_target']}")

        if state.rl_eta_lbl is not None:
            state.rl_eta_lbl.config(text=f"ETA:{progress['eta']}")

        # Optional full-panel widgets
        if state.rl_pct_lbl is not None:
            state.rl_pct_lbl.config(text=f"{progress['pct']:.1f}%")

        if state.rl_pb_canvas is not None:
            w = state.rl_pb_canvas.winfo_width()
            if w > 10:
                pct    = progress['pct'] / 100.0
                fill_w = int(w * pct)
                state.rl_pb_canvas.delete('all')
                if fill_w > 0:
                    state.rl_pb_canvas.create_rectangle(
                        0, 0, fill_w, 8, fill=PURPLE, outline='')

        # Core stats — always present
        state.rl_eps_lbl.config(
            text=f"ε:{stats['epsilon']:.3f}")
        state.rl_reward_lbl.config(
            text=f"R:{stats['avg_reward_10']:.3f}",
            fg=GREEN if stats['avg_reward_10'] >= 0 else ACCENT2)
        state.rl_action_lbl.config(
            text=f"A:{stats['last_action']}")

        if state.rl_states_lbl is not None:
            state.rl_states_lbl.config(
                text=f"{stats['states_visited']}/160")

        if state.rl_q_lbl is not None:
            state.rl_q_lbl.config(text=stats['last_q'])

        # Cooldown
        cd = progress['cooldown']
        if state.rl_cooldown_lbl is not None:
            state.rl_cooldown_lbl.config(
                text=f"Next session in {cd}s..." if cd > 0 else "")

    except Exception:
        pass