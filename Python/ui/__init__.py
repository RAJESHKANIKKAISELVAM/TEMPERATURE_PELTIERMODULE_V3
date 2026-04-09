"""
ui/__init__.py
==============
UI panel package — each module builds one card/panel of the GUI.

Modules:
    live_readings   — Card 1: live temperature + PSU V/I/W metrics
    psu_controls    — Card 2: voltage/current setpoints + OUTPUT button
    pid_panel       — Card 3: PID diagnostics display + live Kp/Ki/Kd tuning
    auto_controller — Card 4: 5-step sequencer table + START/STOP + status box
    log_panel       — Card 5: reading log text widget
    graphs          — Right panel: 3 matplotlib graphs + toolbar + zoom
"""