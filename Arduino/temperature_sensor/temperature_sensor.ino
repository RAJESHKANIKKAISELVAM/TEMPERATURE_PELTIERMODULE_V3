// ============================================================
//  temperature_sensor.ino
//  DS18B20 Temperature Sensor + 2-Channel Relay Control
//  Arduino Uno R3  —  Fixed version with internal pull-up
// ------------------------------------------------------------
//  WIRING:
//    DS18B20 DATA (Yellow) → D2
//    DS18B20 VCC  (Red)    → 5V
//    DS18B20 GND  (Black)  → GND
//    Relay IN1             → D7  (Relay A — Cooling)
//    Relay IN2             → D8  (Relay B — Heating)
//    Relay VCC             → 5V
//    Relay GND             → GND
//
//  SERIAL COMMANDS (Python → Arduino):
//    "RELAY_A\n"    → Cooling  (IN1 ON,  IN2 OFF)
//    "RELAY_B\n"    → Heating  (IN2 ON,  IN1 OFF)
//    "RELAY_OFF\n"  → Both OFF (safe idle)
//
//  SERIAL OUTPUT (Arduino → Python):
//    "23.4375\n"    → Temperature in degrees C
//    "ERROR\n"      → Sensor fault
// ============================================================

#include <OneWire.h>
#include <DallasTemperature.h>

// ── Pin definitions ──────────────────────────────────────────
#define DATA_PIN   2    // DS18B20 yellow wire
#define RELAY_IN1  7    // Relay A = Cooling
#define RELAY_IN2  8    // Relay B = Heating

// Active LOW relay module:
//   LOW  = relay coil ON  = contact CLOSED
//   HIGH = relay coil OFF = contact OPEN
#define RELAY_ON   LOW
#define RELAY_OFF  HIGH

OneWire           oneWire(DATA_PIN);
DallasTemperature sensors(&oneWire);

String        cmdBuffer = "";
unsigned long lastRead  = 0;

// ── Relay control ────────────────────────────────────────────
void setRelayA() {
  // Cooling: turn B off first then A on
  digitalWrite(RELAY_IN2, RELAY_OFF);
  delay(20);
  digitalWrite(RELAY_IN1, RELAY_ON);
}

void setRelayB() {
  // Heating: turn A off first then B on
  digitalWrite(RELAY_IN1, RELAY_OFF);
  delay(20);
  digitalWrite(RELAY_IN2, RELAY_ON);
}

void setRelayOff() {
  // Both relays off — safe idle
  digitalWrite(RELAY_IN1, RELAY_OFF);
  digitalWrite(RELAY_IN2, RELAY_OFF);
}

// ── Setup ────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);

  // Internal pull-up on data pin — replaces external 4.7k resistor
  pinMode(DATA_PIN, INPUT_PULLUP);

  // Relay pins
  pinMode(RELAY_IN1, OUTPUT);
  pinMode(RELAY_IN2, OUTPUT);
  setRelayOff();   // always start safe

  // DS18B20 init
  sensors.begin();
  sensors.setResolution(12);          // 12-bit = 0.0625°C precision
  sensors.setWaitForConversion(false); // non-blocking mode

  // Request first conversion and wait for it
  sensors.requestTemperatures();
  delay(800);   // 12-bit conversion takes 750ms

  lastRead = millis();
}

// ── Main loop ────────────────────────────────────────────────
void loop() {

  // 1. Read serial commands from Python — non-blocking
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

    // Read result from previous conversion
    float t = sensors.getTempCByIndex(0);

    // Start next conversion immediately
    sensors.requestTemperatures();

    // Send reading to Python
    if (t == DEVICE_DISCONNECTED_C || t < -55.0 || t > 125.0) {
      Serial.println("ERROR");
    } else {
      Serial.println(t, 4);   // e.g. "23.4375"
    }
  }

  // No delay — loop runs freely so relay commands respond instantly
}