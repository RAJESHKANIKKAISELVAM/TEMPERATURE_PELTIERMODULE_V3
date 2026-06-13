"""
controllers/relay_controller.py
================================
Controls the 2-channel relay module via Arduino serial.
Also reads DS18B20 temperature from the same Arduino.

Audit fixes:
  - Added threading.Lock() for serial port protection
  - relay.state is now only set after confirmed send
  - RELAY_DIRECTION_SWAPPED in config.py swaps A/B without rewiring
"""

import serial
import time
import threading


class RelayController:

    def __init__(self, port, baudrate=9600):
        self.port      = port
        self.baudrate  = baudrate
        self.ser       = None
        self.connected = False
        self.error     = ""
        self.state     = "OFF"
        self._lock     = threading.Lock()
        self._connect()

    def _connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(2)   # Arduino resets on serial open — wait for it
            self.connected = True
            self.set_off()
        except Exception as e:
            self.error     = str(e)
            self.connected = False

    def close(self):
        if self.ser:
            try:
                self.set_off()
                self.ser.close()
            except Exception:
                pass

    def _send(self, cmd):
        """Send command to Arduino. Thread-safe via lock."""
        if not self.ser:
            return False
        try:
            with self._lock:
                self.ser.write((cmd + "\n").encode("utf-8"))
            return True
        except Exception as ex:
            print(f"[Relay] send '{cmd}' failed: {ex}")
            return False

    def set_state_a(self):
        """
        Set relay to A direction (cooling by default).
        If RELAY_DIRECTION_SWAPPED = True in config.py,
        sends RELAY_B command instead — fixes reversed wiring
        without any physical hardware change.
        """
        from config import RELAY_DIRECTION_SWAPPED
        cmd = "RELAY_B" if RELAY_DIRECTION_SWAPPED else "RELAY_A"
        if self._send(cmd):
            self.state = "A"

    def set_state_b(self):
        """
        Set relay to B direction (heating by default).
        If RELAY_DIRECTION_SWAPPED = True in config.py,
        sends RELAY_A command instead.
        """
        from config import RELAY_DIRECTION_SWAPPED
        cmd = "RELAY_A" if RELAY_DIRECTION_SWAPPED else "RELAY_B"
        if self._send(cmd):
            self.state = "B"

    def set_off(self):
        if self._send("RELAY_OFF"):
            self.state = "OFF"

    def get_state(self):
        return self.state

    def read_temperature(self):
        """
        Read latest temperature from Arduino serial buffer.
        Thread-safe via lock — prevents corruption with concurrent _send calls.
        Returns: float | 'ERROR' | None (None = no new data)
        """
        if not self.ser:
            return None
        lines = []
        try:
            with self._lock:
                while self.ser.in_waiting > 0:
                    raw = self.ser.readline().decode("utf-8").strip()
                    if raw:
                        lines.append(raw)
        except Exception:
            return None
        for line in reversed(lines):
            if line == "ERROR":
                return "ERROR"
            try:
                return float(line)
            except ValueError:
                continue
        return None