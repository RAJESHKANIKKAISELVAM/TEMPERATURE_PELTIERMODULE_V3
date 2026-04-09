"""
core/__init__.py
================
Core application logic package.

Modules:
    app_state     — AppState class: single shared-state object passed to all modules
    session       — Session directory management and auto-save orchestration
    control_loop  — 1 Hz update loop, PID execution, state machine transitions
    exports       — CSV, JSON, TXT, PNG graph, PDF report, status snapshot saves
"""