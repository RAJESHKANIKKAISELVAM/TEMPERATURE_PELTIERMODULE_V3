"""
core/exports.py
===============
All export / save functions for the lab session.

Each function takes (state) as its only argument.
Respects state._SILENT_SAVE[0] — when True, success popups are suppressed
(used by auto_save_all which shows a single summary popup instead).

Functions:
    save_screenshot(state)
    save_graph(state)
    save_csv(state)
    save_json(state)
    save_txt(state)
    save_status(state)
    save_pdf(state)
"""

import os
import csv
import json
import statistics
from datetime import datetime
from tkinter import messagebox

from config import (
    HOLD_BAND, NEAR_BAND, MIN_RELAY_FLIP_SEC,
    DEFAULT_I, NUM_STEPS,
    TEMP_PORT, PSU_PORT,
    INTERVAL_MS,
    GRAPH_BG,
)
from core.session import session_path


# =================================================================
#  SCREENSHOT
# =================================================================
def save_screenshot(state):
    try:
        from PIL import ImageGrab
        path = session_path(
            state, f"screenshot_{datetime.now().strftime('%H-%M-%S')}.png")
        state.root.update_idletasks()
        img = ImageGrab.grab(bbox=(
            state.root.winfo_rootx(),
            state.root.winfo_rooty(),
            state.root.winfo_rootx() + state.root.winfo_width(),
            state.root.winfo_rooty() + state.root.winfo_height(),
        ))
        img.save(path)
        messagebox.showinfo("Saved", f"Screenshot:\n{path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))


# =================================================================
#  GRAPH PNG
# =================================================================
def save_graph(state):
    try:
        path = session_path(
            state, f"graphs_{datetime.now().strftime('%H-%M-%S')}.png")
        state.fig.savefig(path, bbox_inches="tight", dpi=150, facecolor=GRAPH_BG)
        if not state._SILENT_SAVE[0]:
            messagebox.showinfo("Saved", f"Graph:\n{path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))


# =================================================================
#  CSV
# =================================================================
def save_csv(state):
    try:
        path = session_path(
            state, f"data_{datetime.now().strftime('%H-%M-%S')}.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["#", "Timestamp", "Temp_C", "Voltage_V", "Current_A",
                        "Power_W", "Relay", "Step", "State", "PID_Output"])
            for row in state.log_rows:
                w.writerow(row)
        if not state._SILENT_SAVE[0]:
            messagebox.showinfo("Saved", f"CSV:\n{path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))


# =================================================================
#  JSON
# =================================================================
def save_json(state):
    try:
        path = session_path(
            state, f"data_{datetime.now().strftime('%H-%M-%S')}.json")
        keys = ["index", "timestamp", "temp_c", "voltage_v", "current_a",
                "power_w", "relay", "step", "state", "pid_output"]
        with open(path, "w") as f:
            json.dump({
                "session":  state.SESSION_DIR[0],
                "exported": datetime.now().isoformat(),
                "pid": {
                    "Kp": state.pid.Kp,
                    "Ki": state.pid.Ki,
                    "Kd": state.pid.Kd,
                },
                "records": [dict(zip(keys, r)) for r in state.log_rows],
            }, f, indent=2)
        if not state._SILENT_SAVE[0]:
            messagebox.showinfo("Saved", f"JSON:\n{path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))


# =================================================================
#  TXT
# =================================================================
def save_txt(state):
    try:
        path = session_path(
            state, f"data_{datetime.now().strftime('%H-%M-%S')}.txt")
        with open(path, "w") as f:
            f.write("LAB MONITOR — PID Session Log\n")
            f.write(f"PID: Kp={state.pid.Kp} Ki={state.pid.Ki} Kd={state.pid.Kd}\n")
            f.write(f"Exported: {datetime.now()}\n" + "-" * 90 + "\n")
            for row in state.log_rows:
                f.write("  ".join(str(x) for x in row) + "\n")
        if not state._SILENT_SAVE[0]:
            messagebox.showinfo("Saved", f"TXT:\n{path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))


# =================================================================
#  STATUS SNAPSHOT
# =================================================================
def save_status(state):
    try:
        path = session_path(
            state, f"status_{datetime.now().strftime('%H-%M-%S')}.txt")
        diag = state.pid.get_diagnostics()
        with open(path, "w") as f:
            f.write(f"Time:    {datetime.now()}\n")
            f.write(f"Temp:    {state.temp_label.cget('text')} °C\n")
            f.write(f"Relay:   {state.relay.get_state()}\n")
            f.write(f"State:   {state.ctrl['state']}\n")
            f.write(f"Step:    {state.ctrl['step']+1}/{NUM_STEPS}\n")
            f.write(f"Target:  {state.ctrl['target']} °C\n")
            f.write(f"PID Kp:  {diag['Kp']}\n")
            f.write(f"PID Ki:  {diag['Ki']}\n")
            f.write(f"PID Kd:  {diag['Kd']}\n")
            f.write(f"Error:   {diag['error']} °C\n")
            f.write(f"dT/dt:   {diag['dT_dt']} °C/s\n")
            f.write(f"Output:  {diag['output']} A\n")
        messagebox.showinfo("Saved", f"Status:\n{path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))


# =================================================================
#  PDF REPORT
# =================================================================
def save_pdf(state):
    """
    Research-grade PDF report.
    Identical logic to original lab_monitor.py — only references go through state.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            Image as RLImg, HRFlowable, PageBreak, KeepTogether)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        import tempfile
        import matplotlib.pyplot as plt2
        import matplotlib.gridspec as gs2

        path = session_path(
            state,
            f"Research_Report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf")

        doc = SimpleDocTemplate(
            path, pagesize=A4,
            topMargin=2.0*cm, bottomMargin=2.0*cm,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            title="Peltier PID Temperature Control — Research Report",
            author="Lab Monitor v5 / DS18B20 + HM310T"
        )
        styles = getSampleStyleSheet()

        C_BLUE  = colors.HexColor("#1a6fa8")
        C_TEAL  = colors.HexColor("#148f77")
        C_RED   = colors.HexColor("#c0392b")
        C_ORG   = colors.HexColor("#d35400")
        C_LB    = colors.HexColor("#eaf4fb")
        C_LT    = colors.HexColor("#e8f8f5")
        C_LR    = colors.HexColor("#fdf2f2")
        C_WHITE = colors.white
        C_DARK  = colors.HexColor("#1a252f")
        C_DIM   = colors.HexColor("#5d6d7e")
        C_WARN  = colors.HexColor("#f39c12")

        TITLE = ParagraphStyle("RPT_TITLE", parent=styles["Title"],
            textColor=C_BLUE, fontSize=22, spaceAfter=4, leading=26)
        SUBT  = ParagraphStyle("RPT_SUBT",  parent=styles["Normal"],
            textColor=C_DIM, fontSize=11, spaceAfter=2, leading=14)
        H1    = ParagraphStyle("RPT_H1",    parent=styles["Heading1"],
            textColor=C_BLUE, fontSize=13, spaceAfter=4, spaceBefore=10)
        H2    = ParagraphStyle("RPT_H2",    parent=styles["Heading2"],
            textColor=C_TEAL, fontSize=10, spaceAfter=3, spaceBefore=6)
        H3    = ParagraphStyle("RPT_H3",    parent=styles["Heading3"],
            textColor=C_DARK, fontSize=9, spaceAfter=2, spaceBefore=4,
            fontName="Helvetica-Bold")
        NM    = ParagraphStyle("RPT_NM",    parent=styles["Normal"],
            fontSize=9, textColor=C_DARK, spaceAfter=3, leading=13)
        DIM   = ParagraphStyle("RPT_DIM",   parent=styles["Normal"],
            fontSize=8, textColor=C_DIM, spaceAfter=2, leading=11)
        WARN  = ParagraphStyle("RPT_WARN",  parent=styles["Normal"],
            fontSize=8, textColor=C_ORG, spaceAfter=2, leading=11)
        EQ    = ParagraphStyle("RPT_EQ",    parent=styles["Code"],
            fontSize=9, leading=13, textColor=C_DARK,
            backColor=C_LB, borderPad=4, spaceAfter=4)

        def ts(hdr=1, hc=C_BLUE, ac=C_LB):
            return TableStyle([
                ("BACKGROUND",    (0,0),  (-1,hdr-1), hc),
                ("TEXTCOLOR",     (0,0),  (-1,hdr-1), C_WHITE),
                ("FONTNAME",      (0,0),  (-1,hdr-1), "Helvetica-Bold"),
                ("FONTSIZE",      (0,0),  (-1,-1),     7.5),
                ("ROWBACKGROUNDS",(0,hdr),(-1,-1),     [ac, C_WHITE]),
                ("GRID",          (0,0),  (-1,-1),     0.25,
                 colors.HexColor("#aed6f1")),
                ("VALIGN",        (0,0),  (-1,-1),     "MIDDLE"),
                ("TOPPADDING",    (0,0),  (-1,-1),     2.5),
                ("BOTTOMPADDING", (0,0),  (-1,-1),     2.5),
                ("LEFTPADDING",   (0,0),  (-1,-1),     4),
                ("RIGHTPADDING",  (0,0),  (-1,-1),     4),
            ])

        def hr1(): return HRFlowable(
            width="100%", thickness=1.0, color=C_BLUE, spaceAfter=6)
        def hr2(): return HRFlowable(
            width="100%", thickness=0.4,
            color=colors.HexColor("#aed6f1"), spaceAfter=4)

        # ── Compute metrics ──────────────────────────────────────────
        t_start   = state.SESSION_START_DT[0]
        t_end     = state.SESSION_END_DT[0] or datetime.now()
        total_s   = int((t_end - t_start).total_seconds()) if t_start else 0
        total_str = f"{total_s//3600:02d}h {(total_s%3600)//60:02d}m {total_s%60:02d}s"
        steps_done   = len(state.step_data)
        session_name = (os.path.basename(state.SESSION_DIR[0])
                        if state.SESSION_DIR[0] else "Unknown")

        approach_total = sum(sd["approach_time"] for sd in state.step_data
                             if sd.get("approach_time") is not None)
        hold_total = sum(sd["hold_secs"] for sd in state.step_data)

        metrics = []
        for sd in state.step_data:
            m = {"step": sd["step_num"], "target": sd["target"]}
            init = sd.get("initial_temp") or 0
            m["direction"] = "COOLING" if init > sd["target"] else "HEATING"
            m["delta_T"]   = round(abs(sd["target"] - init), 4)

            m["ss_error"] = (round(sd["hold_avg"] - sd["target"], 4)
                             if sd["hold_avg"] is not None else None)

            if sd["hold_temps"]:
                devs = [tv - sd["target"] for _, tv in sd["hold_temps"]]
                if m["direction"] == "COOLING":
                    worst = min(devs)
                    m["overshoot"] = round(abs(worst), 4) if worst < 0 else 0.0
                else:
                    worst = max(devs)
                    m["overshoot"] = round(worst, 4) if worst > 0 else 0.0
                m["overshoot_pct"] = (
                    round((m["overshoot"] / m["delta_T"]) * 100, 1)
                    if m["delta_T"] > 0 else 0.0)
            else:
                m["overshoot"] = None
                m["overshoot_pct"] = None

            m["approach_time"] = sd.get("approach_time")
            m["rise_rate"] = (round(m["delta_T"] / m["approach_time"], 4)
                              if m["approach_time"] and m["delta_T"] > 0 else None)

            m["hold_std"]   = sd.get("hold_std")
            m["hold_range"] = (round(sd["hold_max"] - sd["hold_min"], 4)
                               if sd["hold_min"] is not None else None)
            m["hold_avg"]   = sd.get("hold_avg")
            m["hold_min"]   = sd.get("hold_min")
            m["hold_max"]   = sd.get("hold_max")

            if sd["hold_temps"] and len(sd["hold_temps"]) >= 5:
                tail = sd["hold_temps"][int(len(sd["hold_temps"])*0.8):]
                tail_spread = max(tv for _, tv in tail) - min(tv for _, tv in tail)
                m["settled"] = tail_spread < 0.4
            else:
                m["settled"] = False

            m["peak_i"] = (round(max([row[3] for row in sd["pid_log"]], key=abs), 4)
                           if sd.get("pid_log") else None)

            max_i = state.ctrl.get("_max_i", DEFAULT_I)
            m["saturated"] = (any(abs(row[5]) >= max_i * 0.99
                                  for row in sd["pid_log"])
                              if sd.get("pid_log") else False)
            metrics.append(m)

        cooling_steps = [m for m in metrics if m["direction"] == "COOLING"]
        heating_steps = [m for m in metrics if m["direction"] == "HEATING"]
        avg_cool_std = (sum(m["hold_std"] for m in cooling_steps
                            if m["hold_std"] is not None) /
                        max(len(cooling_steps), 1))
        avg_heat_std = (sum(m["hold_std"] for m in heating_steps
                            if m["hold_std"] is not None) /
                        max(len(heating_steps), 1))

        ss_errors = [abs(m["ss_error"]) for m in metrics
                     if m["ss_error"] is not None]
        mean_ss = round(sum(ss_errors)/len(ss_errors), 4) if ss_errors else 0
        overshoot_vals = [m["overshoot_pct"] for m in metrics
                          if m["overshoot_pct"] is not None]
        max_os = round(max(overshoot_vals), 1) if overshoot_vals else 0

        story = []

        # ── Page 1: Cover + Abstract ─────────────────────────────────
        story.append(Spacer(1, 1.5*cm))
        story.append(Paragraph("Peltier Module Temperature Control", TITLE))
        story.append(Paragraph(
            "PID Closed-Loop Control — Research Session Report", TITLE))
        story.append(Spacer(1, 0.3*cm))
        story.append(hr1())
        story.append(Paragraph(
            f"Session: {session_name}    |    "
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}    |    "
            f"Instrument: DS18B20 + HM310T + SRD-05VDC-SL-C", DIM))
        story.append(Spacer(1, 0.8*cm))
        story.append(Paragraph("Abstract", H1))
        story.append(hr2())
        story.append(Paragraph(
            f"This report presents a closed-loop temperature control experiment "
            f"using a Peltier thermoelectric module driven by a Hanmatek HM310T "
            f"programmable power supply and controlled by a classic parallel PID "
            f"algorithm (Kp={state.pid.Kp}, Ki={state.pid.Ki}, Kd={state.pid.Kd}). "
            f"The experiment executed {steps_done} sequential temperature setpoints "
            f"over a total session duration of {total_str}. "
            f"Temperature acquisition was performed at 1 Hz using a DS18B20 digital "
            f"sensor at 12-bit resolution. "
            f"The mean absolute steady-state error across all steps was "
            f"{mean_ss:.4f} °C, with maximum overshoot of {max_os:.1f}%. "
            f"Cooling steps demonstrated better hold stability "
            f"(mean std = {avg_cool_std:.4f} °C) compared to heating steps "
            f"(mean std = {avg_heat_std:.4f} °C).", NM))
        story.append(Spacer(1, 0.5*cm))

        meta = [
            ["Parameter", "Value"],
            ["Session ID",          session_name],
            ["Start time",          t_start.strftime("%Y-%m-%d  %H:%M:%S") if t_start else "--"],
            ["End time",            t_end.strftime("%Y-%m-%d  %H:%M:%S")],
            ["Total run time",      total_str],
            ["Steps completed",     f"{steps_done} / {NUM_STEPS}"],
            ["Total approach time", f"{approach_total:.1f} s"],
            ["Total hold time",     f"{hold_total} s"],
        ]
        mt = Table(meta, colWidths=[6*cm, 10*cm], repeatRows=1)
        mt.setStyle(ts())
        story.append(mt)

        # ── Page 2: System + Hardware ────────────────────────────────
        story.append(PageBreak())
        story.append(Paragraph("1. System Architecture", H1))
        story.append(hr2())
        arch = [
            ["Layer", "Component", "Role"],
            ["Sensing",   "DS18B20 (COM8)",          "12-bit digital temperature at 1 Hz"],
            ["Actuation", f"HM310T PSU ({PSU_PORT})", "DC power — voltage fixed, current = PID output"],
            ["Direction", "SRD-05VDC-SL-C H-bridge",  "Reverses current polarity to Peltier"],
            ["Control",   "Software PID (Python)",     "1 Hz loop: sensor → PID → PSU + relay"],
            ["Interface", "Lab Monitor GUI (tkinter)",  "Live display, logging, PDF export"],
        ]
        at = Table(arch, colWidths=[2.5*cm, 4.5*cm, 9.2*cm], repeatRows=1)
        at.setStyle(ts())
        story.append(at)
        story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("2. Control Algorithm — PID", H1))
        story.append(hr2())
        story.append(Paragraph("Continuous-time PID:", H3))
        story.append(Paragraph(
            "u(t) = Kp·e(t)  +  Ki·∫e(τ)dτ  +  Kd·(de/dt)", EQ))
        story.append(Paragraph("Discrete implementation (T = 1 s):", H3))
        story.append(Paragraph(
            "e[k]  = T_target − T_measured[k]\n"
            "P[k]  = Kp · e[k]\n"
            "I[k]  = clamp( I[k-1] + Ki·T·e[k], −I_lim, +I_lim )\n"
            "D[k]  = Kd · (e[k] − e[k-1]) / T\n"
            "u[k]  = clamp( P[k] + I[k] + D[k], u_min, u_max )", EQ))
        pid_tbl = [
            ["Parameter", "Symbol", "Value", "Meaning"],
            ["Proportional gain", "Kp", str(state.pid.Kp), f"{state.pid.Kp} A per °C error"],
            ["Integral gain",     "Ki", str(state.pid.Ki), f"{state.pid.Ki} A per °C·s accumulated error"],
            ["Derivative gain",   "Kd", str(state.pid.Kd), f"{state.pid.Kd} A per °C/s rate"],
            ["Min output",       "u_min", f"{0.10} A", "Below this: relay OFF (coast)"],
            ["Max output",       "u_max", f"{state.ctrl.get('_max_i', DEFAULT_I):.3f} A", "Hardware saturation limit"],
            ["Integral limit",   "I_lim", "±5.0 A·s", "Anti-windup clamp"],
        ]
        ptt = Table(pid_tbl, colWidths=[3.5*cm, 1.8*cm, 1.5*cm, 9.4*cm], repeatRows=1)
        ptt.setStyle(ts())
        story.append(ptt)

        # ── Page 3: Performance Summary ──────────────────────────────
        story.append(PageBreak())
        story.append(Paragraph("3. Control Performance Summary", H1))
        story.append(hr2())
        perf_hdr = ["Step","Target\n°C","Dir","ΔT\n°C","Approach\ns",
                    "Rise\n°C/s","SS Error\n°C","Overshoot\n°C","OS%",
                    "Hold Std\n°C","Settled?","Sat?"]
        perf_rows = [perf_hdr]
        for m in metrics:
            perf_rows.append([
                str(m["step"]),
                f"{m['target']:.1f}",
                "COOL" if m["direction"] == "COOLING" else "HEAT",
                f"{m['delta_T']:.2f}",
                f"{m['approach_time']:.1f}" if m["approach_time"] else "--",
                f"{m['rise_rate']:.4f}"     if m["rise_rate"]     else "--",
                f"{m['ss_error']:+.4f}"     if m["ss_error"] is not None else "--",
                f"{m['overshoot']:.4f}"     if m["overshoot"] is not None else "--",
                f"{m['overshoot_pct']:.1f}" if m["overshoot_pct"] is not None else "--",
                f"{m['hold_std']:.4f}"      if m["hold_std"] is not None else "--",
                "YES" if m["settled"]   else "NO",
                "YES" if m["saturated"] else "no",
            ])
        cw2 = [1*cm,1.5*cm,1.2*cm,1.3*cm,1.8*cm,
               1.8*cm,1.8*cm,2*cm,1.2*cm,1.8*cm,1.4*cm,1.4*cm]
        perft = Table(perf_rows, colWidths=cw2, repeatRows=1)
        perft.setStyle(ts())
        story.append(perft)

        # ── Page 4+: Full session graphs ─────────────────────────────
        story.append(PageBreak())
        story.append(Paragraph("4. Session Overview Graphs", H1))
        story.append(hr2())

        with state.glock:
            _t  = list(state.g_times);  _tp = list(state.g_temps)
            _sp = list(state.g_setpts)
            _vo = list(state.g_volts);  _cu = list(state.g_currs)
            _pp = list(state.g_pid_p);  _pi = list(state.g_pid_i)
            _pd = list(state.g_pid_d)

        fig2 = plt2.figure(figsize=(16.5/2.54, 15/2.54), facecolor="#f4f9fd")
        gs3  = gs2.GridSpec(3, 1, figure=fig2, height_ratios=[2,1,1],
                            hspace=0.55, top=0.95, bottom=0.07,
                            left=0.09, right=0.93)
        ax2_t   = fig2.add_subplot(gs3[0])
        ax2_vi  = fig2.add_subplot(gs3[1])
        ax2_pid = fig2.add_subplot(gs3[2])
        ax2_vi2 = ax2_vi.twinx()

        BG2 = "#f4f9fd"
        for ax in [ax2_t, ax2_vi, ax2_pid]:
            ax.set_facecolor(BG2)
            ax.grid(True, color="#d6eaf8", linewidth=0.7, linestyle="--")

        if _t:
            ax2_t.plot(_t, _tp, color="#1a6fa8", lw=1.8, label="Temperature")
            ax2_t.plot(_t, _sp, color="#c0392b", lw=1.2,
                       linestyle="--", label="Setpoint")
            for reg in state.hold_regions:
                hs, he, snum = reg
                he2 = he if he is not None else _t[-1]
                ax2_t.axvspan(hs, he2, alpha=0.12, color="#1e8449")
                ax2_t.axvline(hs, color="#1e8449", lw=0.9, linestyle="--")
                if he is not None:
                    ax2_t.axvline(he, color="#c0392b", lw=0.9, linestyle="--")
            ax2_t.set_xlim(min(_t), max(_t)+5)
            mn = min(min(_tp), min(_sp)); mx = max(max(_tp), max(_sp))
            ax2_t.set_ylim(mn-2, mx+2)
            ax2_t.set_ylabel("Temp (°C)", fontsize=8)
            ax2_t.set_xlabel("Time (s)",  fontsize=8)
            ax2_t.legend(fontsize=7, loc="upper right")
            ax2_t.set_title("Temperature vs Time (full session)", fontsize=8, pad=2)

            ax2_vi.plot(_t, _vo, color="#6c3483", lw=1.5, label="Voltage (V)")
            ax2_vi2.plot(_t, _cu, color="#9a7d0a", lw=1.5, label="Current (A)")
            ax2_vi.set_xlim(min(_t), max(_t)+5)
            ax2_vi.set_ylabel("Voltage (V)", fontsize=8, color="#6c3483")
            ax2_vi2.set_ylabel("Current (A)", fontsize=8, color="#9a7d0a")
            ax2_vi.set_xlabel("Time (s)", fontsize=8)
            ax2_vi.set_title("Voltage & Current vs Time", fontsize=8, pad=2)
            lines1 = ax2_vi.get_lines() + ax2_vi2.get_lines()
            ax2_vi.legend(lines1, [l.get_label() for l in lines1],
                          fontsize=7, loc="upper right")

        if _pp:
            ax2_pid.plot(_t, _pp, color="#1a6fa8", lw=1.2, label="P")
            ax2_pid.plot(_t, _pi, color="#148f77", lw=1.2, label="I")
            ax2_pid.plot(_t, _pd, color="#d35400", lw=1.2, label="D")
            ax2_pid.set_xlim(min(_t), max(_t)+5)
            ax2_pid.set_ylabel("PID (A)", fontsize=8)
            ax2_pid.set_xlabel("Time (s)", fontsize=8)
            ax2_pid.legend(fontsize=7, loc="upper right")
            ax2_pid.set_title("PID Components vs Time", fontsize=8, pad=2)
            ax2_pid.axhline(0, color="#aab7b8", lw=0.6)

        tmp2 = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        fig2.savefig(tmp2.name, bbox_inches="tight", dpi=140, facecolor=BG2)
        tmp2.close()
        plt2.close(fig2)

        story.append(RLImg(tmp2.name, width=16.5*cm, height=15*cm))
        story.append(Paragraph(
            "Figure 1: Full-session data. Top: temperature and setpoint with hold regions "
            "(green). Middle: PSU voltage and current. Bottom: PID P, I, D components.", DIM))

        # ── Per-step detail pages ─────────────────────────────────────
        for i, sd in enumerate(state.step_data):
            m = metrics[i]
            story.append(PageBreak())
            story.append(Paragraph(
                f"5.{sd['step_num']}  Step {sd['step_num']} — "
                f"Target {sd['target']:.1f} °C  |  {m['direction']}  |  "
                f"ΔT = {m['delta_T']:.2f} °C", H1))
            story.append(hr1())

            rng = (round(sd["hold_max"]-sd["hold_min"], 4)
                   if sd["hold_min"] is not None else None)
            ovr = [
                ["Parameter", "Value"],
                ["Target temperature",  f"{sd['target']:.1f} °C"],
                ["Direction",           m["direction"]],
                ["Initial temperature", f"{sd['initial_temp']:.4f} °C" if sd["initial_temp"] else "--"],
                ["Approach time",       f"{m['approach_time']:.1f} s"  if m["approach_time"] else "--"],
                ["Rise rate",           f"{m['rise_rate']:.4f} °C/s"   if m["rise_rate"]     else "--"],
                ["Hold average",        f"{sd['hold_avg']:.4f} °C"     if sd["hold_avg"] is not None else "--"],
                ["Hold std deviation",  f"±{sd['hold_std']:.4f} °C"    if sd["hold_std"] is not None else "--"],
                ["Hold range",          f"{rng:.4f} °C"                 if rng is not None else "--"],
                ["Steady-state error",  f"{m['ss_error']:+.4f} °C"     if m["ss_error"] is not None else "--"],
                ["Overshoot",           f"{m['overshoot']:.4f} °C ({m['overshoot_pct']:.1f}%)"
                                        if m["overshoot"] is not None else "--"],
                ["Settled",             "YES" if m["settled"]   else "NO"],
                ["Saturated",           "YES" if m["saturated"] else "No"],
            ]
            ot = Table(ovr, colWidths=[5.5*cm, 10.7*cm], repeatRows=1)
            ot.setStyle(ts())
            story.append(ot)
            story.append(Spacer(1, 0.3*cm))

            # Hold trace
            if sd["hold_temps"]:
                story.append(Paragraph(
                    f"Hold Trace  ({len(sd['hold_temps'])} readings  |  "
                    f"target {sd['target']:.1f} °C  ±{HOLD_BAND} °C)", H2))
                hh = ["Hold Time (s)", "Temperature (°C)", "Deviation (°C)"]
                hr_rows = [hh]
                for et, tv in sd["hold_temps"]:
                    dev = round(tv - sd["target"], 4)
                    hr_rows.append([f"{et:.1f}", f"{tv:.4f}",
                                    f"{'+' if dev>=0 else ''}{dev:.4f}"])
                ht2 = Table(hr_rows, colWidths=[4*cm, 6*cm, 6*cm], repeatRows=1)
                ht2.setStyle(ts(hc=C_TEAL, ac=C_LT))
                for ri3, (et, tv) in enumerate(sd["hold_temps"], start=1):
                    if abs(tv - sd["target"]) > HOLD_BAND:
                        ht2.setStyle(TableStyle([
                            ("BACKGROUND", (2,ri3),(2,ri3), C_LR),
                            ("TEXTCOLOR",  (2,ri3),(2,ri3), C_RED),
                        ]))
                story.append(ht2)

        # ── Appendix: raw log ─────────────────────────────────────────
        story.append(PageBreak())
        story.append(Paragraph(
            f"Appendix A — Full Session Log  ({len(state.log_rows)} entries)", H1))
        story.append(hr2())
        rh = ["#","Timestamp","Temp (°C)","V","A","W","Relay","Step","State","PID Output"]
        rr = [rh] + [list(map(str, r)) for r in state.log_rows]
        rt = Table(rr, repeatRows=1,
                   colWidths=[0.9*cm,3.6*cm,1.9*cm,1.3*cm,
                              1.5*cm,1.7*cm,1.1*cm,1.1*cm,1.8*cm,2.3*cm])
        rt.setStyle(ts())
        story.append(rt)

        doc.build(story)
        os.unlink(tmp2.name)
        if not state._SILENT_SAVE[0]:
            messagebox.showinfo("Report Saved", f"Research report saved:\n{path}")

    except ImportError:
        messagebox.showerror("Missing library",
            "Run: pip install reportlab matplotlib")
    except Exception as e:
        import traceback
        messagebox.showerror("PDF Error",
            f"{str(e)}\n\n{traceback.format_exc()[-400:]}")