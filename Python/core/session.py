"""
core/session.py
===============
Session directory management and auto-save orchestration.

Functions:
    make_session_dir(state)  — creates timestamped Lab_Session_* folder
    session_path(state, f)   — returns full path for a file in session dir
    auto_save_all(state)     — saves all formats silently, shows one summary popup
"""

import os
from datetime import datetime
from tkinter import messagebox

from config import LAB_REPORTS_DIR


def make_session_dir(state):
    name = "Lab_Session_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(LAB_REPORTS_DIR, exist_ok=True)
    path = os.path.join(LAB_REPORTS_DIR, name)
    os.makedirs(path, exist_ok=True)
    state.SESSION_DIR[0] = path
    return path


def session_path(state, f):
    if state.SESSION_DIR[0] is None:
        make_session_dir(state)
    return os.path.join(state.SESSION_DIR[0], f)


def auto_save_all(state):
    """
    Called at end of session — saves all export formats silently,
    then shows exactly one summary popup to the user.
    """
    # Import here to avoid circular import at module load time
    from core.exports import (
        save_csv, save_json, save_txt, save_graph, save_pdf
    )

    errors = []
    saved  = []

    state._SILENT_SAVE[0] = True

    def _silent(fn, label):
        try:
            fn(state)
            saved.append(label)
        except Exception as e:
            errors.append(f"{label}: {e}")

    _silent(save_csv,   "CSV")
    _silent(save_json,  "JSON")
    _silent(save_txt,   "TXT")
    _silent(save_graph, "Graph PNG")
    _silent(save_pdf,   "PDF Report")

    state._SILENT_SAVE[0] = False

    msg  = f"Session saved to:\n{state.SESSION_DIR[0]}\n\n"
    msg += "Files saved: " + ", ".join(saved)
    if errors:
        msg += "\n\nErrors:\n" + "\n".join(errors)
    messagebox.showinfo("Session Complete", msg)