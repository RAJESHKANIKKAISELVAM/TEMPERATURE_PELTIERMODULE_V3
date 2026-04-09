"""
ui/log_panel.py
===============
Card 5 — Reading Log.

Scrollable colour-coded log of every 1 Hz reading.
Column headers: # | Timestamp | Temp | V | A | W | RLY | STP | STATE | PID OUT

Public functions:
    build(state, parent, fonts)  — builds the log card
    add_log(state, ...)          — appends one row (called from control_loop.py)

Widget refs stored on state:
    state.log_box, state.log_cnt, state.auto_scr
"""

import tkinter as tk
from tkinter import messagebox

from config import (
    PANEL, PANEL2, BORDER, BG,
    ACCENT, ACCENT2, GREEN, TEAL, ORANGE, PURPLE, YLWDK, PINKDK,
    TEXT_DIM, TEXT_LOG, TEXT_MAIN,
    MAX_LOG,
)


def build(state, parent, fonts):
    """
    Build Card 5 (log panel) into parent frame.
    parent is the log_outer frame (row=4 of left panel, sticky="nsew").
    """
    F_SM   = fonts["sm"]
    F_LBL  = fonts["lbl"]
    F_LOG  = fonts["log"]
    F_STEP = fonts["step"]

    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)

    # ── Header bar ───────────────────────────────────────────────────
    tb4 = tk.Frame(parent, bg=PANEL2)
    tb4.grid(row=0, column=0, sticky="ew")
    tk.Label(tb4, text="  READING LOG", font=F_LBL,
             fg=ACCENT, bg=PANEL2, anchor="w",
             pady=3).pack(side="left", fill="x", expand=True)
    state.log_cnt = tk.Label(tb4, text="0 entries",
                              font=F_SM, fg=TEXT_DIM, bg=PANEL2)
    state.log_cnt.pack(side="right", padx=8)

    # ── Column header strip ──────────────────────────────────────────
    lch = tk.Frame(parent, bg=PANEL2,
                   highlightbackground=BORDER, highlightthickness=1)
    lch.grid(row=1, column=0, sticky="new")
    for txt, w in [("#", 4), ("TIMESTAMP", 16), ("TEMP", 9), ("V", 6),
                   ("A", 7), ("W", 7), ("RLY", 5), ("STP", 4),
                   ("STATE", 8), ("PID OUT", 8)]:
        tk.Label(lch, text=txt, font=F_STEP, fg=ACCENT,
                 bg=PANEL2, width=w, anchor="w",
                 padx=3, pady=2).pack(side="left")

    # ── Scrollable text widget ───────────────────────────────────────
    logwrap = tk.Frame(parent, bg=PANEL,
                       highlightbackground=BORDER, highlightthickness=1)
    logwrap.grid(row=1, column=0, sticky="nsew", pady=(22, 0))
    parent.rowconfigure(1, weight=1)

    llsb = tk.Scrollbar(logwrap); llsb.pack(side="right", fill="y")
    state.log_box = tk.Text(
        logwrap, font=F_LOG, bg="#f8fbff", fg=TEXT_LOG,
        bd=0, highlightthickness=0, state="disabled",
        yscrollcommand=llsb.set, spacing1=2, spacing3=2)
    state.log_box.pack(fill="both", expand=True)
    llsb.config(command=state.log_box.yview)

    # Colour tags
    for tag, fg in [
        ("idx",   "#aab7b8"), ("ts",   TEXT_DIM),
        ("ok",    ACCENT),    ("warm", ORANGE),
        ("hot",   ACCENT2),   ("mild", ORANGE),
        ("cool",  TEAL),      ("cold", PURPLE),
        ("err",   ACCENT2),
        ("volt",  PURPLE),    ("curr", YLWDK),    ("power", PINKDK),
        ("ra",    ACCENT),    ("rb",   TEAL),      ("roff",  TEXT_DIM),
        ("appr",  ACCENT),    ("hold", TEAL),
        ("idle",  TEXT_DIM),  ("done", GREEN),     ("step",  TEAL),
        ("pid",   YLWDK),
    ]:
        state.log_box.tag_config(tag, foreground=fg)

    state.auto_scr = [True]


def add_log(state, idx, ts, tmp, ttag, v, i, w, rs, rtag,
            stp, st, stag, pid_out):
    """Append one row to the log widget. Called from core/control_loop.py."""
    lb = state.log_box
    lb.config(state="normal")
    lb.insert("end", f" {idx:<4} ",  "idx")
    lb.insert("end", f"{ts:<18}",    "ts")
    lb.insert("end", f"{tmp:<10}",   ttag)
    lb.insert("end", f"{v:<7}",      "volt")
    lb.insert("end", f"{i:<8}",      "curr")
    lb.insert("end", f"{w:<8}",      "power")
    lb.insert("end", f"{rs:<6}",     rtag)
    lb.insert("end", f"{stp:<5}",    "step")
    lb.insert("end", f"{st:<9}",     stag)
    lb.insert("end", f"{pid_out}\n", "pid")
    total = int(lb.index("end-1c").split(".")[0])
    if total > MAX_LOG + 20:
        lb.delete("1.0", f"{total - MAX_LOG}.0")
    lb.config(state="disabled")
    if state.auto_scr[0]:
        lb.see("end")


def clear_log(state):
    """Clear all log entries. Called from Tools menu."""
    if messagebox.askyesno("Clear", "Clear all log entries?"):
        state.log_box.config(state="normal")
        state.log_box.delete("1.0", "end")
        state.log_box.config(state="disabled")
        state.log_rows.clear()
        state.reading_count[0] = 0
        state.log_cnt.config(text="0 entries")