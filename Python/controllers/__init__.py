"""
controllers/__init__.py
=======================
Hardware and algorithm controller package.

Exports:
    HM310T          — Hanmatek HM310T PSU Modbus RTU driver
    RelayController — SRD-05VDC-SL-C relay + DS18B20 temperature reader
    PIDController   — Classic parallel PID with anti-windup
"""

from .hm310t_controller import HM310T
from .relay_controller  import RelayController
from .pid_controller    import PIDController

__all__ = ["HM310T", "RelayController", "PIDController"]