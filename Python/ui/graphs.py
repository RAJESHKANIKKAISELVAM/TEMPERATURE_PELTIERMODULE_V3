"""
ui/graphs.py — Right panel: 3 graphs + toolbar (FULL VIEW + LIVE only)
Steps-post drawstyle for honest 1Hz DS18B20 representation.
Animation interval 500ms for snappy updates.
"""

import tkinter as tk
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle

from config import (
    PANEL, PANEL2, BORDER, GRAPH_BG,
    ACCENT, ACCENT2, GREEN, ORANGE, TEAL, PURPLE, YLWDK, TEXT_DIM,
)


def build(state, parent, fonts):
    F_STEP = fonts["step"]

    parent.rowconfigure(0, weight=0)
    parent.rowconfigure(1, weight=1)
    parent.columnconfigure(0, weight=1)

    # ── Figure ───────────────────────────────────────────────────────
    fig = plt.figure(facecolor=GRAPH_BG)
    gs  = gridspec.GridSpec(3, 1, figure=fig, height_ratios=[2,1,1],
                            hspace=0.55, top=0.96, bottom=0.05,
                            left=0.07, right=0.93)

    ax_t = fig.add_subplot(gs[0])
    ax_t.set_facecolor(GRAPH_BG)
    ax_t.set_ylabel("Temp (°C)", fontsize=9, color=TEXT_DIM)
    ax_t.set_xlabel("Time (s)",  fontsize=9, color=TEXT_DIM)
    ax_t.tick_params(colors=TEXT_DIM, labelsize=8)
    ax_t.grid(True, color="#d6eaf8", linewidth=0.8, linestyle="--")
    for s in ax_t.spines.values(): s.set_edgecolor(BORDER)
    # steps-post: flat for 1s then vertical jump — honest 1Hz sensor display
    line_temp, = ax_t.plot([], [], color=ACCENT, lw=1.5,
                            drawstyle="steps-post", label="Temperature")
    line_setp, = ax_t.plot([], [], color=ACCENT2, lw=1.5,
                            linestyle="--", label="Setpoint")
    ax_t.legend(fontsize=8, loc="upper right",
                facecolor=PANEL, edgecolor=BORDER)
    ax_t.set_title("Temperature vs Time", fontsize=9, color=TEXT_DIM, pad=3)

    ax_vi = fig.add_subplot(gs[1])
    ax_vi.set_facecolor(GRAPH_BG)
    ax_vi.set_ylabel("Voltage (V)", fontsize=9, color=PURPLE)
    ax_vi.set_xlabel("Time (s)",    fontsize=9, color=TEXT_DIM)
    ax_vi.tick_params(colors=TEXT_DIM, labelsize=8)
    ax_vi.yaxis.set_major_formatter(plt.FormatStrFormatter("%.2f"))
    ax_vi.grid(True, color="#d6eaf8", linewidth=0.8, linestyle="--")
    for s in ax_vi.spines.values(): s.set_edgecolor(BORDER)
    line_volt, = ax_vi.plot([], [], color=PURPLE, lw=1.5,
                             drawstyle="steps-post", label="Voltage")
    ax_vi2 = ax_vi.twinx()
    ax_vi2.set_facecolor(GRAPH_BG)
    ax_vi2.set_ylabel("Current (A)", fontsize=9, color=YLWDK)
    ax_vi2.tick_params(colors=YLWDK, labelsize=8)
    ax_vi2.yaxis.set_major_formatter(plt.FormatStrFormatter("%.3f"))
    line_curr, = ax_vi2.plot([], [], color=YLWDK, lw=1.5,
                              drawstyle="steps-post", label="Current")
    ax_vi.legend([line_volt, line_curr], ["Voltage (V)", "Current (A)"],
                 fontsize=8, loc="upper right",
                 facecolor=PANEL, edgecolor=BORDER)
    ax_vi.set_title("Voltage & Current vs Time", fontsize=9,
                    color=TEXT_DIM, pad=3)

    ax_pid = fig.add_subplot(gs[2])
    ax_pid.set_facecolor(GRAPH_BG)
    ax_pid.set_ylabel("PID (A)", fontsize=9, color=TEXT_DIM)
    ax_pid.set_xlabel("Time (s)", fontsize=9, color=TEXT_DIM)
    ax_pid.tick_params(colors=TEXT_DIM, labelsize=8)
    ax_pid.grid(True, color="#d6eaf8", linewidth=0.8, linestyle="--")
    for s in ax_pid.spines.values(): s.set_edgecolor(BORDER)
    line_p, = ax_pid.plot([], [], color=ACCENT,  lw=1.5,
                           drawstyle="steps-post", label="P")
    line_i, = ax_pid.plot([], [], color=TEAL,    lw=1.5,
                           drawstyle="steps-post", label="I")
    line_d, = ax_pid.plot([], [], color=ORANGE,  lw=1.5,
                           drawstyle="steps-post", label="D")
    ax_pid.legend(fontsize=8, loc="upper right",
                  facecolor=PANEL, edgecolor=BORDER)
    ax_pid.set_title("PID Components vs Time", fontsize=9,
                     color=TEXT_DIM, pad=3)

    state.fig     = fig
    state.ax_t    = ax_t
    state.ax_vi   = ax_vi
    state.ax_vi2  = ax_vi2
    state.ax_pid  = ax_pid
    state.line_temp = line_temp
    state.line_setp = line_setp
    state.line_volt = line_volt
    state.line_curr = line_curr
    state.line_p    = line_p
    state.line_i    = line_i
    state.line_d    = line_d

    # ── Canvas ───────────────────────────────────────────────────────
    mpl_canvas = FigureCanvasTkAgg(fig, master=parent)
    mpl_canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
    state.mpl_canvas = mpl_canvas

    # ── Toolbar ──────────────────────────────────────────────────────
    toolbar_frame = tk.Frame(parent, bg=PANEL2,
                             highlightbackground=BORDER,
                             highlightthickness=1)
    toolbar_frame.grid(row=0, column=0, sticky="ew")
    toolbar_frame.columnconfigure(0, weight=1)

    nav_toolbar = NavigationToolbar2Tk(mpl_canvas, toolbar_frame)
    nav_toolbar.config(bg=PANEL2)
    nav_toolbar.update()
    nav_toolbar.pack(side="left")

    state.graph_live   = [True]
    state.graph_window = [300]

    def _toggle_live():
        state.graph_live[0] = not state.graph_live[0]
        state.btn_live.config(
            text="● LIVE"  if state.graph_live[0] else "❚❚ FROZEN",
            bg=GREEN       if state.graph_live[0] else ORANGE)

    state.btn_live = tk.Button(
        toolbar_frame, text="● LIVE",
        font=F_STEP, bg=GREEN, fg="white", relief="flat",
        padx=10, pady=3, command=_toggle_live)
    state.btn_live.pack(side="right", padx=6, pady=3)

    def _reset_view():
        with state.glock:
            if not state.g_times:
                return
            t0     = state.g_times[0]
            t1     = state.g_times[-1]
            tp_all = list(state.g_temps)
            sp_all = list(state.g_setpts)
        pad_x = max((t1 - t0) * 0.02, 5)
        pad_y = 2
        ax_t.set_xlim(t0 - pad_x, t1 + pad_x)
        ax_t.set_ylim(min(min(tp_all), min(sp_all)) - pad_y,
                      max(max(tp_all), max(sp_all)) + pad_y)
        ax_vi.set_xlim(t0 - pad_x, t1 + pad_x)
        ax_vi2.set_xlim(t0 - pad_x, t1 + pad_x)
        ax_pid.set_xlim(t0 - pad_x, t1 + pad_x)
        state.graph_live[0] = False
        state.btn_live.config(text="❚❚ FROZEN", bg=ORANGE)
        mpl_canvas.draw_idle()

    tk.Button(toolbar_frame, text="⤢  FULL VIEW",
              font=F_STEP, bg=TEAL, fg="white", relief="flat",
              padx=10, pady=3,
              command=_reset_view).pack(side="right", padx=2, pady=3)

    def _on_toolbar_action(event):
        if str(nav_toolbar.mode) in ("pan/zoom", "zoom rect"):
            state.graph_live[0] = False
            state.btn_live.config(text="❚❚ FROZEN", bg=ORANGE)

    mpl_canvas.mpl_connect("button_press_event",   _on_toolbar_action)
    mpl_canvas.mpl_connect("button_release_event", _on_toolbar_action)

    def _on_scroll(event):
        if event.inaxes is None:
            return
        state.graph_live[0] = False
        state.btn_live.config(text="❚❚ FROZEN", bg=ORANGE)
        factor = 0.85 if event.button == "up" else 1.15
        xdata  = event.xdata or 0
        ydata  = event.ydata or 0
        for a in [ax_t, ax_vi, ax_vi2, ax_pid]:
            xl = a.get_xlim()
            a.set_xlim(xdata + (xl[0] - xdata) * factor,
                       xdata + (xl[1] - xdata) * factor)
        if not (event.key and "control" in event.key):
            yl = event.inaxes.get_ylim()
            event.inaxes.set_ylim(
                ydata + (yl[0] - ydata) * factor,
                ydata + (yl[1] - ydata) * factor)
        mpl_canvas.draw_idle()

    mpl_canvas.mpl_connect("scroll_event", _on_scroll)

    # ── Animation — 500ms catches every 1Hz reading within half second
    def _upd(frame):
        with state.glock:
            if len(state.g_times) < 2:
                return
            t  = list(state.g_times)
            tp = list(state.g_temps)
            sp = list(state.g_setpts)
            vo = list(state.g_volts)
            cu = list(state.g_currs)
            pp = list(state.g_pid_p)
            pi = list(state.g_pid_i)
            pd = list(state.g_pid_d)

        # ── Temperature ───────────────────────────────────────────────
        line_temp.set_data(t, tp)
        line_setp.set_data(t, sp)

        if t:
            if state.graph_live[0]:
                w     = state.graph_window[0]
                x_min = max(0, t[-1] - w)
                x_max = t[-1] + 5
                ax_t.set_xlim(x_min, x_max)
                ax_t.set_ylim(min(min(tp), min(sp)) - 2,
                               max(max(tp), max(sp)) + 2)
            else:
                x_min, x_max = ax_t.get_xlim()

            # Hold region shading
            for artists in state._hold_artists:
                for a in artists:
                    if a is not None:
                        try:
                            a.remove()
                        except Exception:
                            pass
            state._hold_artists.clear()

            if state.hold_regions:
                y_lo, y_hi = ax_t.get_ylim()
                for region in state.hold_regions:
                    h_start, h_end, step_num = region
                    h_end_draw = h_end if h_end is not None else t[-1]
                    if h_end_draw <= x_min or h_start >= x_max:
                        continue
                    span = Rectangle(
                        (h_start, y_lo),
                        h_end_draw - h_start,
                        y_hi - y_lo,
                        linewidth=0, facecolor="#1e8449", alpha=0.13,
                        zorder=0, transform=ax_t.transData, clip_on=True)
                    ax_t.add_patch(span)
                    vl_s, = ax_t.plot(
                        [h_start, h_start], [y_lo, y_hi],
                        color="#1e8449", linestyle="--", linewidth=1.2,
                        zorder=2, transform=ax_t.transData)
                    vl_e = None
                    if h_end is not None:
                        vl_e, = ax_t.plot(
                            [h_end, h_end], [y_lo, y_hi],
                            color="#c0392b", linestyle="--", linewidth=1.2,
                            zorder=2, transform=ax_t.transData)
                    txt = None
                    lx = max(h_start + 0.5, x_min + 0.5)
                    if lx < x_max and lx < h_end_draw:
                        suffix = "" if h_end is None else " ✓"
                        txt = ax_t.text(
                            lx, y_hi - (y_hi - y_lo) * 0.05,
                            f"Hold {step_num}{suffix}",
                            fontsize=7.5, color="#1e8449",
                            va="top", ha="left", zorder=3,
                            transform=ax_t.transData,
                            bbox=dict(boxstyle="round,pad=0.2",
                                      facecolor="#eafaf1",
                                      edgecolor="#1e8449",
                                      alpha=0.80, linewidth=0.7))
                    state._hold_artists.append((span, vl_s, vl_e, txt))

        # ── Voltage / Current ─────────────────────────────────────────
        line_volt.set_data(t, vo)
        line_curr.set_data(t, cu)
        if t and state.graph_live[0]:
            w = state.graph_window[0]
            ax_vi.set_xlim(max(0, t[-1] - w), t[-1] + 5)
            ax_vi2.set_xlim(max(0, t[-1] - w), t[-1] + 5)
            if vo:
                v_lo = min(vo); v_hi = max(vo)
                vr   = max(v_hi - v_lo, 0.5)
                ax_vi.set_ylim(v_lo - vr * 0.2, v_hi + vr * 0.2)
            if cu:
                i_lo = min(cu); i_hi = max(cu)
                ir   = max(i_hi - i_lo, 0.05)
                ax_vi2.set_ylim(i_lo - ir * 0.2, i_hi + ir * 0.2)

        # ── PID components ────────────────────────────────────────────
        line_p.set_data(t, pp)
        line_i.set_data(t, pi)
        line_d.set_data(t, pd)
        if t and pp and state.graph_live[0]:
            ax_pid.set_xlim(
                max(0, t[-1] - state.graph_window[0]), t[-1] + 5)
            all_pid = pp + pi + pd
            p_lo = min(all_pid); p_hi = max(all_pid)
            pr   = max(p_hi - p_lo, 0.1)
            ax_pid.set_ylim(p_lo - pr * 0.2, p_hi + pr * 0.2)

        mpl_canvas.draw_idle()

    # 500ms refresh — catches every 1Hz reading within half a second
    state.ani = FuncAnimation(fig, _upd, interval=500,
                               blit=False, cache_frame_data=False)