"""
controllers/relay_controller.py
================================
Controls the 2-channel relay module via Arduino serial.
Also reads DS18B20 temperature from the same Arduino.

Relay wiring (SRD-05VDC-SL-C):
    IN1 → D7,  IN2 → D8
    Peltier A → COM(2),  Peltier B → COM(5)
    PSU(+) → NO(3) + NC(4)
    PSU(-) → NC(1) + NO(6)

Commands sent to Arduino:
    RELAY_A   → D7=HIGH, D8=LOW  (cooling)
    RELAY_B   → D7=LOW,  D8=HIGH (heating/reverse)
    RELAY_OFF → D7=LOW,  D8=LOW  (idle/safe)
"""

import serial
import time


class RelayController:

    def __init__(self, port, baudrate=9600):
        self.port      = port
        self.baudrate  = baudrate
        self.ser       = None
        self.connected = False
        self.error     = ""
        self.state     = "OFF"
        self._connect()

    def _connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(2)
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
        if not self.ser:
            return
        try:
            self.ser.write((cmd + "\n").encode("utf-8"))
        except Exception as ex:
            print(f"[Relay] send '{cmd}' failed: {ex}")

    def set_state_a(self):
        self._send("RELAY_A")
        self.state = "A"

    def set_state_b(self):
        self._send("RELAY_B")
        self.state = "B"

    def set_off(self):
        self._send("RELAY_OFF")
        self.state = "OFF"

    def get_state(self):
        return self.state

    def read_temperature(self):
        if not self.ser:
            return None
        lines = []
        try:
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