"""
controllers/hm310t_controller.py
=================================
HM310T Power Supply — minimalmodbus controller.

DESIGN RULES (to prevent GUI lag and deadlocks):
  - _write() and _read() are fast — no sleep, no retry loops
  - output_on() does ONE write — no retry loop (caller retries if needed)
  - All sleeps removed from hot paths — only reconnect() sleeps, on bg thread only
  - threading.Lock() protects the serial port from concurrent access
  - connected flag is updated in real time based on failure count
"""

try:
    import minimalmodbus
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False

import time
import threading

REG_OUTPUT  = 0x0001
REG_PROT    = 0x0002
REG_DISP_V  = 0x0010
REG_DISP_I  = 0x0011
REG_DISP_WH = 0x0012
REG_DISP_WL = 0x0013
REG_SET_V   = 0x0030
REG_SET_I   = 0x0031

_FAIL_THRESHOLD = 6   # consecutive failures before marking disconnected


class HM310T:
    def __init__(self, port, baudrate=9600, slave=1):
        self.port        = port
        self.baudrate    = baudrate
        self.slave       = slave
        self.inst        = None
        self.connected   = False
        self.error       = ""
        self._lock       = threading.Lock()
        self._fail_count = 0
        self._connect()

    # ─────────────────────────────────────────────────────────────────
    #  Internal connection
    # ─────────────────────────────────────────────────────────────────
    def _connect(self):
        if not MODBUS_AVAILABLE:
            self.error = "minimalmodbus not installed"
            return
        try:
            with self._lock:
                if self.inst:
                    try: self.inst.serial.close()
                    except Exception: pass
                inst = minimalmodbus.Instrument(self.port, self.slave)
                inst.serial.baudrate                       = self.baudrate
                inst.serial.timeout                        = 0.5
                inst.mode                                  = minimalmodbus.MODE_RTU
                inst.close_port_after_each_call            = False
                inst.precalculate_read_size                = False
                inst.clear_buffers_before_each_transaction = True
                self.inst = inst

            test = self._read_nolock(REG_OUTPUT)
            if test is not None:
                self.connected   = True
                self._fail_count = 0
                self.error       = ""
            else:
                self.connected = False
                self.error     = "No Modbus response from HM310T"
        except Exception as e:
            self.error     = str(e)
            self.connected = False

    def reconnect(self):
        """Called by poll background thread only — may sleep briefly."""
        self.connected = False
        time.sleep(0.3)
        self._connect()

    def close(self):
        with self._lock:
            if self.inst:
                try:
                    self.inst.write_register(REG_OUTPUT, 0, 0, functioncode=6)
                    self.inst.serial.close()
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────────────
    #  Low-level read/write — fast, no sleep, no retry
    # ─────────────────────────────────────────────────────────────────
    def _write_nolock(self, reg, value, decimals=0):
        if not self.inst:
            return False
        try:
            self.inst.write_register(reg, value, decimals, functioncode=6)
            return True
        except Exception:
            try:
                self.inst.write_register(reg, value, decimals, functioncode=16)
                return True
            except Exception as ex:
                print(f"[PSU write] reg={hex(reg)} val={value}: {ex}")
                return False

    def _read_nolock(self, reg, decimals=0):
        if not self.inst:
            return None
        try:
            return self.inst.read_register(reg, decimals, functioncode=3)
        except Exception:
            return None

    def _write(self, reg, value, decimals=0):
        with self._lock:
            ok = self._write_nolock(reg, value, decimals)
        if ok:
            self._fail_count = 0
        else:
            self._fail_count += 1
            if self._fail_count >= _FAIL_THRESHOLD:
                self.connected = False
        return ok

    def _read(self, reg, decimals=0):
        with self._lock:
            v = self._read_nolock(reg, decimals)
        if v is None:
            self._fail_count += 1
            if self._fail_count >= _FAIL_THRESHOLD:
                self.connected = False
        else:
            self._fail_count = 0
        return v

    # ─────────────────────────────────────────────────────────────────
    #  Public API — all fast, no sleep
    # ─────────────────────────────────────────────────────────────────
    def set_voltage(self, v):
        return self._write(REG_SET_V, round(max(0.0, min(30.0, v)), 2), decimals=2)

    def set_current(self, i):
        return self._write(REG_SET_I, round(max(0.0, min(10.0, i)), 3), decimals=3)

    def output_on(self):
        return self._write(REG_OUTPUT, 1)

    def output_off(self):
        self._write(REG_OUTPUT, 0)

    def is_output_on(self):
        v = self._read(REG_OUTPUT)
        return bool(v) if v is not None else False

    def get_voltage(self):
        v = self._read(REG_DISP_V, decimals=2)
        return float(v) if v is not None else 0.0

    def get_current(self):
        v = self._read(REG_DISP_I, decimals=3)
        return float(v) if v is not None else 0.0

    def get_power(self):
        with self._lock:
            wh = self._read_nolock(REG_DISP_WH)
            wl = self._read_nolock(REG_DISP_WL)
        if wh is not None and wl is not None:
            self._fail_count = 0
            return ((int(wh) << 16) | int(wl)) / 1000.0
        self._fail_count += 1
        if self._fail_count >= _FAIL_THRESHOLD:
            self.connected = False
        return 0.0

    def get_protection_status(self):
        v = self._read(REG_PROT)
        if v is None:
            return []
        bits  = int(v)
        flags = []
        if bits & 0x01: flags.append("OVP")
        if bits & 0x02: flags.append("OCP")
        if bits & 0x04: flags.append("OPP")
        if bits & 0x08: flags.append("OTP")
        if bits & 0x10: flags.append("SCP")
        return flags