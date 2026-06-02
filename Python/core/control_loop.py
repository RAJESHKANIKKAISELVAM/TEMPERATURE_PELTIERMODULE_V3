"""
core/control_loop.py — 1 Hz control loop, PID, state machine, PSU poll.

All audit fixes applied:
  - RL uses pid.set_kp_scale() — prevents base_Kp loss and gain compounding
  - RL uses smoothed dT_dt from pid._dtdt_smooth (not raw 1Hz noise)
  - _finalise_step: RL reward computed before step_data.append (correct order)
  - _done_all: auto_save_all runs in background thread (doesn't block runner)
  - _done_all: Kp restored via set_kp_scale(1.0) not direct assignment
  - Hold timer extension uses fixed INTERVAL_MS/1000 (deterministic)
"""

import time
import threading
import statistics
from datetime import datetime

from config import (
    INTERVAL_MS, MAX_GRAPH, NUM_STEPS,
    HOLD_BAND, NEAR_BAND, MIN_RELAY_FLIP_SEC,
    ACCENT, ACCENT2, GREEN, ORANGE, TEAL, PURPLE, TEXT_DIM,
    STEP_ACT, STEP_DONE, STEP_WAIT,
    PREDICT_RELAY_FLIP, PREDICT_SECONDS, PREDICT_MIN_DTDT,
    BRAKE_CHECK_ZONE, BRAKE_CURRENT_SCALE,
    RL_TICK_INTERVAL, RL_MAX_CURRENT,
)
from controllers.rl_controller import get_state as rl_get_state


def _safe_after(state, delay, callback, *args):
    if state._shutting_down[0] or state.root is None:
        return
    try:
        state.root.after(delay, callback, *args)
    except Exception:
        pass


# =================================================================
#  PSU POLL THREAD
# =================================================================
def start_psu_poll(state):
    def _poll():
        idx = 0
        reconnect_wait = [0]
        while True:
            if not state.psu.connected:
                if state._psu_was_connected[0]:
                    state._psu_was_connected[0] = False
                    _safe_after(state, 0, lambda: (
                        state.psu_dot.config(fg=ACCENT2),
                        state.psu_status.config(
                            text="PSU lost — reconnecting...", fg=ACCENT2)))
                reconnect_wait[0] -= 1
                if reconnect_wait[0] <= 0:
                    state.psu.reconnect()
                    reconnect_wait[0] = 12
                    if state.psu.connected:
                        state._psu_was_connected[0] = True
                        _safe_after(state, 0, lambda: (
                            state.psu_dot.config(fg=GREEN),
                            state.psu_status.config(text="Connected", fg=GREEN)))
            else:
                state._psu_was_connected[0] = True
                try:
                    if   idx == 0:
                        v = state.psu.get_voltage()
                        with state.psu_lock: state.psu_live["voltage"] = v
                    elif idx == 1:
                        i = state.psu.get_current()
                        with state.psu_lock: state.psu_live["current"] = i
                    elif idx == 2:
                        w = state.psu.get_power()
                        with state.psu_lock: state.psu_live["power"] = w
                    elif idx == 3:
                        f = state.psu.get_protection_status()
                        with state.psu_lock: state.psu_live["protect"] = f
                        # Auto-clear OCP latch — spawn separate thread
                        # so poll loop doesn't block on 0.8s sleep
                        if f and state.ctrl["state"] in ("APPROACH", "HOLDING"):
                            threading.Thread(
                                target=_clear_ocp, args=(state,),
                                daemon=True).start()
                except Exception:
                    pass
                idx = (idx + 1) % 4
            time.sleep(0.25)
    threading.Thread(target=_poll, daemon=True).start()


def _clear_ocp(state):
    """Called from poll thread on separate thread — clears OCP latch."""
    try:
        state.psu.output_off()
        time.sleep(0.8)
        state.psu.set_voltage(state.ctrl.get("_voltage", 12.0))
        state.psu.set_current(state.ctrl.get("_max_i", 3.0))
        state.psu.output_on()
        with state.psu_lock:
            state.psu_live["protect"] = []
    except Exception:
        pass


# =================================================================
#  STEP LOADER
# =================================================================
def _load_step(state, idx, current_temp=None):
    if idx >= len(state.ctrl["_steps"]):
        _done_all(state)
        return

    t, h = state.ctrl["_steps"][idx]
    state.ctrl.update({
        "step":       idx,
        "target":     t,
        "hold_secs":  h,
        "hold_end":   None,
        "state":      "APPROACH",
        "_last_flip": 0.0,
    })

    seed_temp = current_temp or (state.g_temps[-1] if state.g_temps else t)
    state.pid.set_target(t, current_temp=seed_temp)
    state.pid.reset()

    state.pred_braking[0]    = False
    state.pred_flip_count[0] = 0
    state.rl_tick_count[0]   = 0

    now = time.time()
    sd = {
        "step_num":             idx + 1,
        "target":               t,
        "hold_secs":            h,
        "initial_temp":         None,
        "approach_start":       now,
        "approach_end":         None,
        "approach_time":        None,
        "approach_temps":       [],
        "hold_start":           None,
        "hold_end_ts":          None,
        "hold_temps":           [],
        "hold_min":             None,
        "hold_max":             None,
        "hold_avg":             None,
        "hold_std":             None,
        "hold_violations":      0,
        "hold_peak_deviation":  0.0,
        "hold_violation_times": [],
        "derivatives":          [],
        "pid_log":              [],
    }
    state._current_step_data[0] = sd

    for i, (_, _, sl) in enumerate(state.step_entries):
        if i < idx:    sl.config(text="✓ DONE",   fg=STEP_DONE)
        elif i == idx: sl.config(text="▶ ACTIVE", fg=STEP_ACT)
        else:          sl.config(text="WAITING",  fg=STEP_WAIT)

    state.step_lbl.config(  text=f"STEP:   {idx+1}/{NUM_STEPS}", fg=TEAL)
    state.target_lbl.config(text=f"TARGET: {t:.1f}°C",           fg=TEAL)
    state.hold_lbl.config(  text=f"HOLD:   {h}s pending",        fg=TEXT_DIM)
    state.state_lbl.config( text="◉  APPROACHING",               fg=ACCENT)
    state.relay_lbl.config( text="RELAY:  PID deciding...",       fg=TEXT_DIM)
    state.zone_lbl.config(  text="ZONE:   FAR",                   fg=ACCENT)
    if state.hold_dev_lbl is not None:
        state.hold_dev_lbl.config(text="DEV:    --", fg=TEXT_DIM)

    def _psu_start():
        if not state.psu.connected:
            _safe_after(state, 0, lambda: state.btn_out.config(
                text="PSU OFF-LINE", bg=ORANGE))
            return
        state.psu.output_off()
        time.sleep(0.6)
        state.psu.set_voltage(state.ctrl["_voltage"])
        state.psu.set_current(state.ctrl["_max_i"])
        on_ok = state.psu.output_on()
        state.manual_out[0] = on_ok
        _safe_after(state, 0, lambda: state.btn_out.config(
            text="OUTPUT: ON" if on_ok else "PSU WRITE FAIL",
            bg=GREEN if on_ok else ACCENT2))

    threading.Thread(target=_psu_start, daemon=True).start()


# =================================================================
#  FINALISE STEP
# =================================================================
def _finalise_step(state):
    sd = state._current_step_data[0]
    if sd is None:
        return

    # Fix: compute RL reward BEFORE appending sd to step_data
    # so on_step_complete reads the correct sd and step_rewards is populated
    rl_step_reward = 0.0
    if state.rl.enabled and sd is not None:
        rl_step_reward = state.rl.on_step_complete(sd, HOLD_BAND, NEAR_BAND)

    sd["hold_end_ts"] = time.time()
    if state._active_hold[0] is not None:
        elapsed_end = round(
            sd["hold_end_ts"] - state.ctrl["_t0"], 1) if state.ctrl["_t0"] else 0
        state.hold_regions[state._active_hold[0]][1] = elapsed_end
        state._active_hold[0] = None
    temps = [t for _, t in sd["hold_temps"]]
    if temps:
        sd["hold_min"] = round(min(temps), 4)
        sd["hold_max"] = round(max(temps), 4)
        sd["hold_avg"] = round(sum(temps) / len(temps), 4)
        sd["hold_std"] = round(
            statistics.stdev(temps), 4) if len(temps) > 1 else 0.0
    state.step_data.append(sd)
    state._current_step_data[0] = None


# =================================================================
#  DONE ALL STEPS
# =================================================================
def _done_all(state):
    state.ctrl["state"] = "DONE"
    state.SESSION_END_DT[0] = datetime.now()
    state.relay.set_off()
    state.manual_out[0] = False
    threading.Thread(target=state.psu.output_off, daemon=True).start()
    state.btn_out.config(text="OUTPUT: OFF", bg=ACCENT2)
    state.state_lbl.config( text="◉  ALL DONE ✓",             fg=GREEN)
    state.relay_lbl.config( text="RELAY:  OFF",                fg=TEXT_DIM)
    state.zone_lbl.config(  text="ZONE:   --",                 fg=TEXT_DIM)
    state.hold_lbl.config(  text="HOLD:   complete ✓",         fg=GREEN)
    state.step_lbl.config(  text=f"STEP:   {NUM_STEPS}/{NUM_STEPS}", fg=GREEN)
    for _, _, sl in state.step_entries:
        sl.config(text="✓ DONE", fg=STEP_DONE)
    state.btn_start.config(state="normal")
    state.btn_stop.config(state="disabled")

    # Fix: auto_save_all in background thread so it doesn't block runner signal
    def _save_and_signal():
        from core.session import auto_save_all
        try:
            auto_save_all(state)
        except Exception as e:
            print(f"[Session] auto_save_all failed: {e}")

        # RL: complete episode, save Q-table
        if state.rl.enabled:
            avg_reward = state.rl.on_session_complete()
            violations = sum(
                sd.get("hold_violations", 0) for sd in state.step_data)
            best_step  = (max(state.rl.step_rewards)
                          if state.rl.step_rewards else
                          max(state.rl.session_rewards[-1:] or [0.0]))
            state.rl.log_session(avg_reward, violations, best_step)
            state.rl.save()
            # Fix: restore base Kp via set_kp_scale(1.0) — preserves base_Kp
            state.pid.set_kp_scale(1.0)
            state.pid.max_output = state.ctrl.get("_max_i", 3.0)

        # Signal runner — AFTER saves complete
        state._runner_session_done.set()

    threading.Thread(target=_save_and_signal, daemon=True).start()


# =================================================================
#  START / STOP
# =================================================================
def start_ctrl(state):
    if not state.psu.connected or not state.relay.connected:
        state.state_lbl.config(text="◉  NOT CONNECTED", fg=ACCENT2)
        return
    parsed = []
    for i, (te, he, _) in enumerate(state.step_entries):
        try:
            t = float(te.get()); h = int(float(he.get()))
            if h <= 0: raise ValueError
            parsed.append((t, h))
        except ValueError:
            state.state_lbl.config(text=f"◉  INVALID #{i+1}", fg=ACCENT2)
            return
    try:
        state.ctrl["_voltage"] = float(state.entry_v.get())
        state.ctrl["_max_i"]   = float(state.entry_i.get())
        state.pid.max_output   = state.ctrl["_max_i"]
    except ValueError:
        state.state_lbl.config(text="◉  INVALID V/I", fg=ACCENT2)
        return

    state.ctrl["_steps"] = parsed
    state.ctrl["step"]   = 0
    state.ctrl["_t0"]    = time.time()
    state.SESSION_START_DT[0] = datetime.now()
    state.SESSION_END_DT[0]   = None
    state.step_data.clear()
    state._current_step_data[0] = None
    state.hold_regions.clear()
    state._active_hold[0]    = None
    state.pred_braking[0]    = False
    state.pred_flip_count[0] = 0
    state.rl_tick_count[0]   = 0

    for artists in state._hold_artists:
        for a in artists:
            if a is not None:
                try: a.remove()
                except Exception: pass
    state._hold_artists.clear()

    from core.session import make_session_dir
    make_session_dir(state)

    with state.glock:
        state.g_times.clear(); state.g_temps.clear();  state.g_setpts.clear()
        state.g_volts.clear(); state.g_currs.clear()
        state.g_pid_p.clear(); state.g_pid_i.clear();  state.g_pid_d.clear()

    for _, _, sl in state.step_entries:
        sl.config(text="WAITING", fg=STEP_WAIT)

    _load_step(state, 0)
    state.btn_start.config(state="disabled")
    state.btn_stop.config(state="normal")


def stop_ctrl(state):
    state.ctrl["state"]      = "IDLE"
    state.pred_braking[0]    = False
    state.pred_flip_count[0] = 0
    state.relay.set_off()
    state.manual_out[0] = False
    state.btn_out.config(text="OUTPUT: OFF", bg=ACCENT2)
    threading.Thread(target=state.psu.output_off, daemon=True).start()
    state.state_lbl.config(text="◉  STOPPED",  fg=ORANGE)
    state.relay_lbl.config(text="RELAY:  OFF", fg=TEXT_DIM)
    state.zone_lbl.config( text="ZONE:   --",  fg=TEXT_DIM)
    state.hold_lbl.config( text="HOLD:   --")
    state.step_lbl.config( text="STEP:   --")
    for _, _, sl in state.step_entries:
        sl.config(text="STOPPED", fg=ORANGE)
    state.btn_start.config(state="normal")
    state.btn_stop.config(state="disabled")


# =================================================================
#  PREDICTIVE RELAY BRAKING
# =================================================================
def _check_predictive_flip(state, current_temp, dT_dt, pid_direction,
                            pid_current_A, now):
    if not PREDICT_RELAY_FLIP:
        return pid_direction, pid_current_A, False
    if state.ctrl["state"] != "APPROACH":
        return pid_direction, pid_current_A, False

    final_target = state.pid._final_target
    remaining    = abs(final_target - current_temp)

    if remaining > BRAKE_CHECK_ZONE:
        return pid_direction, pid_current_A, False
    if remaining <= HOLD_BAND:
        return pid_direction, pid_current_A, False
    if abs(dT_dt) < PREDICT_MIN_DTDT:
        return pid_direction, pid_current_A, False

    heating_approach = (dT_dt > 0) and (final_target > current_temp)
    cooling_approach = (dT_dt < 0) and (final_target < current_temp)
    if not (heating_approach or cooling_approach):
        return pid_direction, pid_current_A, False

    brake_dist = abs(dT_dt) * PREDICT_SECONDS
    if remaining > brake_dist:
        return pid_direction, pid_current_A, False

    if (now - state.ctrl["_last_flip"]) < MIN_RELAY_FLIP_SEC:
        return pid_direction, pid_current_A, False

    braking_dir = "A" if pid_direction == "B" else "B"
    braking_cur = max(round(pid_current_A * BRAKE_CURRENT_SCALE, 3),
                      state.pid.min_output)
    state.pred_flip_count[0] += 1
    return braking_dir, braking_cur, True


# =================================================================
#  RUN PID
# =================================================================
def run_pid(state, temp, dt):
    current_A, direction = state.pid.compute(temp, dt)
    diag  = state.pid.get_diagnostics()
    # Use smoothed dT_dt for braking and RL (reduces 1Hz noise)
    dT_dt = state.pid._dtdt_smooth
    now   = time.time()

    direction, current_A, braking = _check_predictive_flip(
        state, temp, dT_dt, direction, current_A, now)
    state.pred_braking[0] = braking

    # ── Q-Learning: adjust Kp_scale and max_current every RL_TICK_INTERVAL ─
    state.rl_tick_count[0] += 1
    if state.rl.enabled and state.rl_tick_count[0] % RL_TICK_INTERVAL == 0:
        final_error = temp - state.pid._final_target
        violation   = (state.ctrl["state"] == "HOLDING" and
                       abs(final_error) > HOLD_BAND)

        rl_state = rl_get_state(
            error      = final_error,
            dT_dt      = dT_dt,   # smoothed
            ctrl_state = state.ctrl["state"],
            hold_band  = HOLD_BAND,
            near_band  = NEAR_BAND,
            violation  = violation,
        )

        flips_now  = state.pred_flip_count[0]
        flip_delta = max(0, flips_now - state.rl.flip_count_prev)
        state.rl.flip_count_prev = flips_now

        if state.rl.last_state is not None and state.rl.last_action is not None:
            reward = state.rl.compute_reward(
                error             = final_error,
                ctrl_state        = state.ctrl["state"],
                violation         = violation,
                relay_flips_delta = flip_delta,
                hold_band         = HOLD_BAND,
            )
            state.rl.update(state.rl.last_state, state.rl.last_action,
                            reward, rl_state)

        action_idx      = state.rl.get_action(rl_state)
        kp_scale, max_i = state.rl.get_action_params(action_idx)

        # Fix: use set_kp_scale() — applies to base_Kp only, no adaptive compounding
        state.pid.set_kp_scale(kp_scale)
        # Fix: clamp max_i to RL_MAX_CURRENT hardware safety limit
        state.pid.max_output = min(max_i, RL_MAX_CURRENT)

        state.rl.last_state  = rl_state
        state.rl.last_action = action_idx

        from ui.rl_panel import update_display
        update_display(state)

    # ── GUI: core diagnostics ─────────────────────────────────────────
    state.pid_err_lbl.config(text=f"{diag['error']:+.3f}")
    state.pid_p_lbl.config(  text=f"{diag['P']:+.3f}")
    state.pid_i_lbl.config(  text=f"{diag['I']:+.3f}")
    state.pid_d_lbl.config(  text=f"{diag['dT_dt']:+.3f}")
    state.pid_out_lbl.config(text=f"{current_A:.3f}")
    state.pid_dir_lbl.config(text=direction,
                             fg=ACCENT if direction == "A" else
                                TEAL   if direction == "B" else TEXT_DIM)

    from config import ORANGE as _ORG, TEAL as _TEAL
    mode = diag.get("mode", "--")
    if state.pid_mode_lbl is not None:
        state.pid_mode_lbl.config(
            text=mode, fg=ACCENT if mode == "COOL" else _ORG)
    if state.pid_ff_lbl is not None:
        state.pid_ff_lbl.config(text=f"{diag.get('ff', 0.0):+.3f}")
    if state.pid_adp_lbl is not None:
        state.pid_adp_lbl.config(text=f"{diag.get('adaptive', 1.0):.2f}")
    if state.pid_rmp_lbl is not None:
        rem = diag.get("ramp_remaining", 0.0)
        state.pid_rmp_lbl.config(
            text=f"{rem:.2f}", fg=_ORG if rem > 0.5 else _TEAL)

    current_dir  = state.relay.get_state()
    first_flip   = (state.ctrl["_last_flip"] == 0.0)
    flip_allowed = first_flip or \
                   (now - state.ctrl["_last_flip"]) >= MIN_RELAY_FLIP_SEC

    if direction != current_dir and flip_allowed:
        if   direction == "A": state.relay.set_state_a()
        elif direction == "B": state.relay.set_state_b()
        else:                  state.relay.set_off()
        state.ctrl["_last_flip"] = now

    if current_A > 0 and state.psu.connected:
        try:
            state.psu.set_current(current_A)
        except Exception:
            pass

    rs        = state.relay.get_state()
    brake_tag = " [BRAKE]" if braking else ""
    relay_colors = {"A": ACCENT, "B": TEAL, "OFF": TEXT_DIM}
    relay_texts  = {
        "A":   f"RELAY:  A (cooling)  {current_A:.2f}A{brake_tag}",
        "B":   f"RELAY:  B (heating)  {current_A:.2f}A{brake_tag}",
        "OFF": f"RELAY:  OFF (coast)",
    }
    state.relay_lbl.config(
        text=relay_texts.get(rs, "--"),
        fg=ACCENT2 if braking else relay_colors.get(rs, TEXT_DIM))

    abs_err = abs(diag["error"])
    if braking:
        state.zone_lbl.config(
            text=f"ZONE:   BRAKING ×{state.pred_flip_count[0]}", fg=ACCENT2)
    elif abs_err <= 0.3:
        state.zone_lbl.config(text="ZONE:   COAST", fg=TEAL)
    elif abs_err <= HOLD_BAND:
        state.zone_lbl.config(text="ZONE:   HOLD",  fg=TEAL)
    elif abs_err <= NEAR_BAND:
        state.zone_lbl.config(text="ZONE:   NEAR",  fg=ORANGE)
    else:
        state.zone_lbl.config(text="ZONE:   FAR",   fg=ACCENT)

    return current_A, direction, diag


# =================================================================
#  MAIN 1 Hz UPDATE LOOP
# =================================================================
def update(state):
    now = time.time()
    dt  = now - state._last_update_t[0]
    state._last_update_t[0] = now

    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    idx = state.reading_count[0] + 1

    result      = state.relay.read_temperature()
    ts_s        = "--"
    ttag        = "idle"
    pid_out_str = "--"

    if result is None:
        result = state.last_known_temp[0]

    if result is None:
        state._after_id[0] = state.root.after(INTERVAL_MS, update, state)
        return

    if result == "ERROR":
        ts_s, ttag = "ERROR", "err"
        state.temp_label.config( text="ERR",          fg=ACCENT2)
        state.temp_status.config(text="Sensor error", fg=ACCENT2)
        state.temp_dot.config(fg=ACCENT2)
    else:
        temp = result
        state.last_known_temp[0] = temp
        ts_s = f"{temp:.4f}"

        if   temp >= 35.0: col, ttag = ACCENT2, "hot"
        elif temp >= 25.0: col, ttag = ACCENT,  "warm"
        elif temp >= 20.0: col, ttag = "#d35400","mild"
        elif temp >= 15.0: col, ttag = TEAL,    "cool"
        else:              col, ttag = PURPLE,  "cold"

        state.temp_label.config( text=f"{temp:.2f}", fg=col)
        state.temp_status.config(text="Receiving data", fg=GREEN)
        state.temp_dot.config(fg=GREEN)
        state.temp_ts.config(text=ts)

        sd        = state._current_step_data[0]
        current_A = 0.0
        diag_data = {}

        with state.psu_lock:
            prot_flags = list(state.psu_live["protect"])
        psu_fault = "OVP" in prot_flags

        if state.ctrl["state"] in ("APPROACH", "HOLDING") and not psu_fault:
            current_A, direction, diag_data = run_pid(state, temp, dt)
            brake_tag   = " [BRAKING]" if state.pred_braking[0] else ""
            pid_out_str = f"{current_A:.3f}A/{direction}{brake_tag}"

            if sd is not None:
                elapsed = round(now - state.ctrl["_t0"], 2) if state.ctrl["_t0"] else 0

                if sd["initial_temp"] is None:
                    sd["initial_temp"] = round(temp, 4)

                if state.ctrl["state"] == "APPROACH":
                    sd["approach_temps"].append((elapsed, round(temp, 4)))
                    ap = sd["approach_temps"]
                    if len(ap) >= 2:
                        dt2 = ap[-1][0] - ap[-2][0]
                        dT  = ap[-1][1] - ap[-2][1]
                        if dt2 > 0:
                            sd["derivatives"].append(
                                (elapsed, round(dT / dt2, 4)))
                    sd["pid_log"].append((
                        elapsed,
                        round(diag_data.get("error", 0), 4),
                        round(diag_data.get("P", 0), 4),
                        round(diag_data.get("I", 0), 4),
                        round(diag_data.get("D", 0), 4),
                        round(diag_data.get("output", 0), 4),
                        current_A,
                    ))

                elif state.ctrl["state"] == "HOLDING":
                    if sd["hold_start"] is None:
                        sd["hold_start"] = now
                    hold_el   = round(now - sd["hold_start"], 2)
                    deviation = round(temp - state.pid._final_target, 4)
                    sd["hold_temps"].append((hold_el, round(temp, 4)))

                    if abs(deviation) > HOLD_BAND:
                        sd["hold_violations"] += 1
                        sd["hold_violation_times"].append(
                            (hold_el, round(temp, 4), deviation))
                        if abs(deviation) > abs(sd["hold_peak_deviation"]):
                            sd["hold_peak_deviation"] = deviation
                        # Fix: deterministic hold extension (not variable dt)
                        state.ctrl["hold_end"] += INTERVAL_MS / 1000.0
                        if state.hold_dev_lbl is not None:
                            vtype = "OVER" if deviation > 0 else "UNDR"
                            state.hold_dev_lbl.config(
                                text=f"DEV:  {vtype} {deviation:+.3f}°C"
                                     f"  ×{sd['hold_violations']}",
                                fg=ACCENT2)
                    else:
                        if state.hold_dev_lbl is not None:
                            state.hold_dev_lbl.config(
                                text=f"DEV:    {deviation:+.3f}°C  OK",
                                fg=GREEN)

        elif psu_fault and state.ctrl["state"] in ("APPROACH", "HOLDING"):
            pid_out_str = "PSU FAULT"
            state.state_lbl.config(
                text=f"◉  PSU FAULT: {' '.join(prot_flags)}", fg=ACCENT2)

        if state.ctrl["state"] in ("APPROACH", "HOLDING") and not psu_fault:
            abs_err = abs(temp - state.pid._final_target)

            if state.ctrl["state"] == "APPROACH" and abs_err <= HOLD_BAND:
                if sd is not None:
                    sd["approach_end"]  = now
                    sd["approach_time"] = round(now - sd["approach_start"], 1)
                    sd["hold_start"]    = now
                state.ctrl["hold_end"] = now + state.ctrl["hold_secs"]
                state.ctrl["state"]    = "HOLDING"
                state.pred_braking[0]  = False
                state.pid.reset_integral()
                elapsed_start = round(
                    now - state.ctrl["_t0"], 1) if state.ctrl["_t0"] else 0
                state.hold_regions.append(
                    [elapsed_start, None, state.ctrl["step"] + 1])
                state._active_hold[0] = len(state.hold_regions) - 1
                state.state_lbl.config(text="◉  HOLDING", fg=TEAL)
                state.hold_lbl.config(
                    text=f"HOLD:   {state.ctrl['hold_secs']//60:02d}:"
                         f"{state.ctrl['hold_secs']%60:02d} left",
                    fg=TEAL)
                if state.hold_dev_lbl is not None:
                    state.hold_dev_lbl.config(
                        text="DEV:    0.000°C  OK", fg=GREEN)

            elif state.ctrl["state"] == "HOLDING":
                rem = state.ctrl["hold_end"] - now
                if rem <= 0:
                    _finalise_step(state)
                    state.step_entries[state.ctrl["step"]][2].config(
                        text="✓ DONE", fg=STEP_DONE)
                    _load_step(state, state.ctrl["step"] + 1,
                               current_temp=temp)
                else:
                    secs = int(rem)
                    state.hold_lbl.config(
                        text=f"HOLD:   {secs//60:02d}:{secs%60:02d} left",
                        fg=TEAL)
                    state.state_lbl.config(
                        text=f"◉  HOLDING  {temp:.2f}°C", fg=TEAL)

            elif state.ctrl["state"] == "APPROACH":
                err = temp - state.pid._final_target
                if state.pred_braking[0]:
                    state.state_lbl.config(
                        text=f"◉  BRAKING  "
                             f"{temp:.1f}→{state.ctrl['target']:.1f}°C",
                        fg=ACCENT2)
                else:
                    state.state_lbl.config(
                        text=f"◉  {'COOLING' if err > 0 else 'HEATING'}  "
                             f"{temp:.1f}→{state.ctrl['target']:.1f}°C",
                        fg=ACCENT if err > 0 else ORANGE)

        if state.ctrl["_t0"] is not None:
            el = round(now - state.ctrl["_t0"], 1)
            with state.glock:
                state.g_times.append(el)
                state.g_temps.append(round(temp, 4))
                state.g_setpts.append(round(state.pid._ramp_target, 3))
                with state.psu_lock:
                    state.g_volts.append(state.psu_live["voltage"])
                    state.g_currs.append(state.psu_live["current"])
                state.g_pid_p.append(round(diag_data.get("P", 0), 4))
                state.g_pid_i.append(round(diag_data.get("I", 0), 4))
                state.g_pid_d.append(round(diag_data.get("D", 0), 4))
                if len(state.g_times) > MAX_GRAPH:
                    for gl in [state.g_times, state.g_temps, state.g_setpts,
                               state.g_volts, state.g_currs,
                               state.g_pid_p, state.g_pid_i, state.g_pid_d]:
                        gl.pop(0)

    with state.psu_lock:
        v_s   = f"{state.psu_live['voltage']:.2f}"
        i_s   = f"{state.psu_live['current']:.3f}"
        w_s   = f"{state.psu_live['power']:.3f}"
        flags = list(state.psu_live["protect"])

    state.lbl_v.config(text=v_s)
    state.lbl_i.config(text=i_s)
    state.lbl_w.config(text=w_s)
    state.psu_prot.config(
        text=f"PROTECT: {' '.join(flags) if flags else 'OK'}",
        fg=ACCENT2 if flags else TEXT_DIM)

    rs   = state.relay.get_state()
    rtag = {"A": "ra", "B": "rb", "OFF": "roff"}.get(rs, "roff")
    st   = state.ctrl["state"]
    stag = {"IDLE": "idle", "APPROACH": "appr",
            "HOLDING": "hold", "DONE": "done"}.get(st, "idle")
    stp  = f"#{state.ctrl['step']+1}" \
           if st not in ("IDLE", "DONE") else "--"

    state.reading_count[0] = idx
    state.log_cnt.config(text=f"{idx} entries")
    state.log_rows.append(
        [idx, ts, ts_s, v_s, i_s, w_s, rs, stp, st, pid_out_str])

    from ui.log_panel import add_log
    add_log(state, idx, ts, ts_s, ttag, v_s, i_s, w_s,
            rs, rtag, stp, st, stag, pid_out_str)

    state._after_id[0] = state.root.after(INTERVAL_MS, update, state)
