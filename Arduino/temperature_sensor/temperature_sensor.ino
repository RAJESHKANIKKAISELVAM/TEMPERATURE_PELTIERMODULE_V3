// ============================================================
//  temperature_sensor.ino
//  DS18B20 Temperature Sensor + 2-Channel Relay Control
//  Arduino Uno R3  —  Fixed version
// ------------------------------------------------------------
//  WIRING:
//    DS18B20 DATA → D2  (with 4.7kΩ pull-up to 5V)
//    Relay IN1    → D7  (Relay A — Cooling direction)
//    Relay IN2    → D8  (Relay B — Heating direction)
//    Relay VCC    → 5V
//    Relay GND    → GND
//
//  SERIAL COMMANDS (Python → Arduino):
//    "RELAY_A\n"    → Cooling  (IN1 energised, IN2 off)
//    "RELAY_B\n"    → Heating  (IN2 energised, IN1 off)
//    "RELAY_OFF\n"  → Both off (safe idle)
//
//  SERIAL OUTPUT (Arduino → Python):
//    "23.4375\n"    → Temperature in °C (4 decimal places)
//    "ERROR\n"      → Sensor fault
// ============================================================

#include <OneWire.h>
#include <DallasTemperature.h>

// ── Pins ─────────────────────────────────────────────────────
#define DATA_PIN   2
#define RELAY_IN1  7    // Relay A = Cooling
#define RELAY_IN2  8    // Relay B = Heating

// Active LOW relay module:
//   LOW  = relay coil energised = relay contact CLOSED
//   HIGH = relay coil off       = relay contact OPEN
#define RELAY_ON  LOW
#define RELAY_OFF HIGH

OneWire           oneWire(DATA_PIN);
DallasTemperature sensors(&oneWire);

String cmdBuffer       = "";
unsigned long lastRead = 0;

// ── Relay functions ───────────────────────────────────────────
void setRelayA() {
  // Cooling: A ON, B OFF — B off first for safety
  digitalWrite(RELAY_IN2, RELAY_OFF);
  delay(20);
  digitalWrite(RELAY_IN1, RELAY_ON);
}

void setRelayB() {
  // Heating: B ON, A OFF — A off first for safety
  digitalWrite(RELAY_IN1, RELAY_OFF);
  delay(20);
  digitalWrite(RELAY_IN2, RELAY_ON);
}

void setRelayOff() {
  // Both off — Peltier coasts
  digitalWrite(RELAY_IN1, RELAY_OFF);
  digitalWrite(RELAY_IN2, RELAY_OFF);
}

// ── Setup ─────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);

  pinMode(RELAY_IN1, OUTPUT);
  pinMode(RELAY_IN2, OUTPUT);
  setRelayOff();   // always start safe

  sensors.begin();
  sensors.setResolution(12);   // 12-bit = 0.0625°C

  // Request first conversion
  sensors.setWaitForConversion(false);
  sensors.requestTemperatures();

  delay(800);      // wait for first 12-bit conversion (750ms)
  lastRead = millis();
}

// ── Main loop ─────────────────────────────────────────────────
void loop() {

  // 1. Read serial commands from Python (non-blocking)
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      cmdBuffer.trim();
      if      (cmdBuffer == "RELAY_A")   setRelayA();
      else if (cmdBuffer == "RELAY_B")   setRelayB();
      else if (cmdBuffer == "RELAY_OFF") setRelayOff();
      cmdBuffer = "";
    } else {
      cmdBuffer += c;
    }
  }

  // 2. Send temperature every 1 second
  unsigned long now = millis();
  if (now - lastRead >= 1000) {
    lastRead = now;

    // Read result of previous conversion
    float t = sensors.getTempCByIndex(0);

    // Start next conversion immediately (non-blocking)
    sensors.requestTemperatures();

    // Send result
    if (t == DEVICE_DISCONNECTED_C || t < -55.0 || t > 125.0) {
      Serial.println("ERROR");
    } else {
      Serial.println(t, 4);
    }
  }

  // No delay here — loop runs freely for responsive relay commands
}
