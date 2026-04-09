"""
lab_monitor.py  —  PID CONTROL VERSION (v5)  —  Restructured
=============================================================
Entry point. Creates AppState, builds the GUI, wires all modules, starts loops.

Project layout:
    Python/
    ├── lab_monitor.py          ← this file (entry point only)
    ├── config.py               ← all constants (ports, PID gains, colours)
    ├── core/
    │   ├── app_state.py        ← AppState: all shared state
    │   ├── session.py          ← session dir + auto_save_all
    │   ├── control_loop.py     ← 1 Hz update loop + PID + state machine
    │   └── exports.py          ← CSV / JSON / TXT / PNG / PDF / status saves
    ├── ui/
    │   ├── live_readings.py    ← Card 1: temperature + PSU metrics
    │   ├── psu_controls.py     ← Card 2: voltage/current setpoints
    │   ├── pid_panel.py        ← Card 3: PID diagnostics + live tuning
    │   ├── auto_controller.py  ← Card 4: 5-step sequencer + START/STOP
    │   ├── log_panel.py        ← Card 5: reading log
    │   └── graphs.py           ← Right panel: 3 graphs + toolbar
    └── controllers/
        ├── pid_controller.py
        ├── hm310t_controller.py
        └── relay_controller.py

Install:
    pip install pyserial minimalmodbus matplotlib pillow reportlab
Run:
    python lab_monitor.py
"""

import tkinter as tk
from tkinter import font as tkfont, messagebox
import threading

from config import (
    BG, PANEL, PANEL2, HDR_BG, HDR_FG,
    ACCENT, ACCENT2, GREEN, ORANGE, TEAL, BORDER, TEXT_DIM,
    TEMP_PORT, PSU_PORT,
    PID_KP, PID_KI, PID_KD,
    INTERVAL_MS,
)
from core.app_state    import AppState
from core.control_loop import start_psu_poll, update
from core.exports      import (save_screenshot, save_graph, save_csv,
                               save_json, save_txt, save_status, save_pdf)
from ui.log_panel      import clear_log
import ui.live_readings   as live_readings
import ui.psu_controls    as psu_controls
import ui.pid_panel       as pid_panel
import ui.auto_controller as auto_controller
import ui.log_panel       as log_panel
import ui.graphs          as graphs


# =================================================================
#  INITIALISE STATE  (hardware connects here)
# =================================================================
state = AppState()

# =================================================================
#  ROOT WINDOW
# =================================================================
root = tk.Tk()
root.title("Lab Monitor — DS18B20 + HM310T + PID")
root.configure(bg=BG)
root.state("zoomed")
root.update()
state.root = root

# ── Font dictionary (passed to every ui/ module) ─────────────────
fonts = {
    "hdr":   tkfont.Font(family="Helvetica", size=12, weight="bold"),
    "big":   tkfont.Font(family="Helvetica", size=46, weight="bold"),
    "med":   tkfont.Font(family="Helvetica", size=19, weight="bold"),
    "sm":    tkfont.Font(family="Helvetica", size=10),
    "lbl":   tkfont.Font(family="Helvetica", size=10, weight="bold"),
    "log":   tkfont.Font(family="Courier New", size=9),
    "unit":  tkfont.Font(family="Helvetica", size=14),
    "ent":   tkfont.Font(family="Helvetica", size=11),
    "state": tkfont.Font(family="Helvetica", size=11, weight="bold"),
    "step":  tkfont.Font(family="Helvetica", size=9,  weight="bold"),
    "tool":  tkfont.Font(family="Helvetica", size=10),
    "pid":   tkfont.Font(family="Courier New", size=9),
}

# =================================================================
#  HEADER
# =================================================================
hdr = tk.Frame(root, bg=HDR_BG)
hdr.pack(fill="x", side="top")
tk.Label(hdr,
    text="  ◈  LAB MONITOR — DS18B20 + HM310T + PID CONTROLLER",
    font=fonts["hdr"], fg=HDR_FG, bg=HDR_BG).pack(side="left", padx=8, pady=8)
tk.Label(hdr,
    text=f"TEMP:{TEMP_PORT}  PSU:{PSU_PORT}  "
         f"Kp={PID_KP}  Ki={PID_KI}  Kd={PID_KD}",
    font=fonts["sm"], fg="#aed6f1", bg=HDR_BG).pack(side="right", padx=12)
tk.Frame(root, bg=BORDER, height=2).pack(fill="x", side="top")

# =================================================================
#  LAYOUT — 2K no-scroll
# =================================================================
body = tk.Frame(root, bg=BG)
body.pack(fill="both", expand=True, side="top")
body.columnconfigure(0, minsize=530, weight=0)
body.columnconfigure(1, weight=1)
body.rowconfigure(0, weight=1)

left = tk.Frame(body, bg=BG)
left.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
right = tk.Frame(body, bg=PANEL,
                 highlightbackground=BORDER, highlightthickness=1)
right.grid(row=0, column=1, sticky="nsew", padx=(3, 6), pady=6)

left.columnconfigure(0, weight=1)
left.rowconfigure(0, weight=0)
left.rowconfigure(1, weight=0)
left.rowconfigure(2, weight=0)
left.rowconfigure(3, weight=0)
left.rowconfigure(4, weight=1)   # log fills remaining height


# ── Card helper ──────────────────────────────────────────────────
def card(parent, title, row, pady=(0, 2)):
    f = tk.Frame(parent, bg=BG)
    f.grid(row=row, column=0, sticky="ew", pady=pady)
    f.columnconfigure(0, weight=1)
    tb = tk.Frame(f, bg=PANEL2)
    tb.grid(row=0, column=0, sticky="ew")
    tk.Label(tb, text=f"  {title}", font=fonts["lbl"],
             fg=ACCENT, bg=PANEL2, anchor="w", pady=3).pack(fill="x")
    c = tk.Frame(f, bg=PANEL,
                 highlightbackground=BORDER, highlightthickness=1)
    c.grid(row=1, column=0, sticky="nsew")
    f.rowconfigure(1, weight=1)
    return c


# =================================================================
#  BUILD LEFT PANEL — 5 cards
# =================================================================
live_readings.build(
    state, card(left, "LIVE READINGS", row=0), fonts)

psu_controls.build(
    state,
    card(left, "PSU SET-POINTS  (set before START — locked during run)", row=1),
    fonts)

pid_panel.build(
    state, card(left, "PID CONTROLLER — LIVE DIAGNOSTICS", row=2), fonts)

auto_controller.build(
    state,
    card(left, "PELTIER AUTO CONTROLLER — 5 SEQUENTIAL SETPOINTS", row=3),
    fonts)

# Card 5 — log gets a raw frame so it can expand
log_outer = tk.Frame(left, bg=BG)
log_outer.grid(row=4, column=0, sticky="nsew")
log_panel.build(state, log_outer, fonts)

# =================================================================
#  BUILD RIGHT PANEL — graphs
# =================================================================
graphs.build(state, right, fonts)

# =================================================================
#  TOOLS MENU
# =================================================================
tools_win = [None]


def show_tools():
    if tools_win[0]:
        try: tools_win[0].destroy()
        except: pass
        tools_win[0] = None
        return

    tw = tk.Toplevel(root)
    tw.overrideredirect(True)
    tw.configure(bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    bx = btn_tools.winfo_rootx()
    by = btn_tools.winfo_rooty() + btn_tools.winfo_height()
    tw.geometry(f"+{bx}+{by}")
    tools_win[0] = tw

    def _sec(t):
        tk.Label(tw, text=t, font=fonts["step"], fg=ACCENT,
                 bg=PANEL2, anchor="w", padx=12, pady=3).pack(fill="x")

    def _tbtn(t, cmd, col=TEXT_DIM):
        def _a():
            try: tw.destroy()
            except: pass
            tools_win[0] = None
            cmd()
        tk.Button(tw, text=t, font=fonts["tool"], fg=col, bg=PANEL,
                  activebackground=PANEL2, relief="flat",
                  anchor="w", padx=16, pady=5, command=_a).pack(fill="x")
        tk.Frame(tw, bg=BORDER, height=1).pack(fill="x")

    tk.Label(tw, text="Tools & Actions", font=fonts["lbl"],
             fg=HDR_FG, bg=HDR_BG, padx=14, pady=7).pack(fill="x")

    _sec("CAPTURE")
    _tbtn("📷  Screenshot (PNG)",     lambda: save_screenshot(state))
    _tbtn("📈  Save Graphs (PNG)",    lambda: save_graph(state))

    _sec("EXPORT DATA")
    _tbtn("📊  Save as CSV",          lambda: save_csv(state))
    _tbtn("📄  Save as PDF Report",   lambda: save_pdf(state))
    _tbtn("{ }  Save as JSON",        lambda: save_json(state))
    _tbtn("📝  Save as TXT",          lambda: save_txt(state))
    _tbtn("ℹ  Save Status Snapshot", lambda: save_status(state))

    _sec("LOG CONTROLS")
    _tbtn("🗑  Clear Data Log",       lambda: clear_log(state), ACCENT2)

    tw.bind("<FocusOut>", lambda e: (tw.destroy(),
                                     tools_win.__setitem__(0, None)))
    tw.focus_set()


btn_tools = tk.Button(hdr, text="⚙  Tools & Actions",
                      font=fonts["lbl"], bg="#145882", fg="white",
                      activebackground="#0f3f60", relief="flat",
                      padx=12, pady=5, command=show_tools)
btn_tools.pack(side="right", padx=(0, 8), pady=5)

# =================================================================
#  START BACKGROUND THREADS + MAIN LOOP
# =================================================================
start_psu_poll(state)
root.after(INTERVAL_MS, lambda: update(state))


# =================================================================
#  SHUTDOWN
# =================================================================
def on_close():
    state.ctrl["state"] = "IDLE"
    try:
        state.ani.event_source.stop()
    except Exception:
        pass
    state.relay.set_off()
    t = threading.Thread(target=state.psu.close, daemon=True)
    t.start(); t.join(timeout=1.5)
    state.relay.close()
    import matplotlib.pyplot as plt
    plt.close("all")
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()