/*
 * ==============================================================================
 * Smart LPG Leak Detection & Automatic Shut-Off System
 * NodeMCU ESP8266 / Arduino Implementation (Academic Demonstration Prototype)
 * ==============================================================================
 * 
 * IMPORTANT SAFETY NOTICE:
 * This sketch is designed for laboratory/educational bench-top demonstration.
 * DO NOT CONNECT THIS PROTOTYPE TO REAL PRESSURIZED LPG CYLINDERS OR GAS LINES.
 * Real LPG systems require ATEX/IECEx explosion-proof certified safety shut-offs.
 * 
 * Required Arduino Libraries:
 *   - Servo.h (Built-in)
 *   - Wire.h & Adafruit_SSD1306.h (Optional for OLED display)
 * ==============================================================================
 */

#include <Servo.h>
#include <Wire.h>

// ------------------------------------------------------------------------------
// Hardware Pin Assignments (NodeMCU ESP8266 GPIO mapping)
// ------------------------------------------------------------------------------
const int PIN_MQ_ANALOG     = A0;    // MQ-5 or MQ-6 Analog Input
const int PIN_SERVO         = D4;    // GPIO2  - Servo PWM signal
const int PIN_BUZZER        = D5;    // GPIO14 - Active Buzzer
const int PIN_LED_SAFE      = D6;    // GPIO12 - Green LED (Nominal Safe)
const int PIN_LED_DANGER    = D7;    // GPIO13 - Red LED (Hazard / Danger)

// ------------------------------------------------------------------------------
// Demonstration Calibration & Thresholds
// ------------------------------------------------------------------------------
// Demonstration ADC thresholds (0 to 1023 range on ESP8266 ADC)
const float THRESH_WARNING  = 300.0; // Demonstration warning threshold
const float THRESH_DANGER   = 550.0; // Demonstration danger threshold
const float THRESH_CRITICAL = 750.0; // Demonstration critical shut-off threshold
const float THRESH_ROR      = 40.0;  // Rate-of-Rise threshold (ADC change / second)
const float HYSTERESIS      = 35.0;  // Deadband hysteresis

// EMA smoothing constant: 0.0 < alpha <= 1.0
const float EMA_ALPHA       = 0.25;

// Actuator Positions (SG90 Servo Degrees)
const int VALVE_OPEN_ANGLE   = 90;
const int VALVE_CLOSED_ANGLE = 0;

// ------------------------------------------------------------------------------
// Global State Variables
// ------------------------------------------------------------------------------
Servo valveServo;

float filteredGas       = 100.0;
float previousGas       = 100.0;
unsigned long lastSampleTime = 0;
bool safetyLockoutActive     = false;

enum RiskLevel {
  STATE_SAFE,
  STATE_WARNING,
  STATE_DANGER,
  STATE_CRITICAL
};

RiskLevel currentRisk = STATE_SAFE;

// ------------------------------------------------------------------------------
// Setup
// ------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println(F("\n=================================================="));
  Serial.println(F(" Smart LPG Safety System - Physical Prototype "));
  Serial.println(F("=================================================="));

  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_SAFE, OUTPUT);
  pinMode(PIN_LED_DANGER, OUTPUT);

  digitalWrite(PIN_BUZZER, LOW);
  digitalWrite(PIN_LED_SAFE, HIGH);
  digitalWrite(PIN_LED_DANGER, LOW);

  valveServo.attach(PIN_SERVO);
  valveServo.write(VALVE_OPEN_ANGLE); // Start in OPEN position
  Serial.println(F("[INIT] Valve actuator set to OPEN (90 deg)."));

  lastSampleTime = millis();
}

// ------------------------------------------------------------------------------
// Main Control Loop
// ------------------------------------------------------------------------------
void loop() {
  unsigned long now = millis();
  float dt = (now - lastSampleTime) / 1000.0; // Elapsed time in seconds

  if (dt >= 0.5) { // Sample every 500ms
    int rawAdc = analogRead(PIN_MQ_ANALOG);

    // 1. Exponential Moving Average (EMA) Filter
    filteredGas = (EMA_ALPHA * (float)rawAdc) + ((1.0 - EMA_ALPHA) * filteredGas);

    // 2. Rate-of-Rise (RoR) Calculation
    float rateOfChange = (filteredGas - previousGas);
    float ratePerSecond = rateOfChange / dt;

    bool rapidRiseDetected = (ratePerSecond >= THRESH_ROR);

    // 3. Safety Risk Classification with Hysteresis
    RiskLevel evaluatedRisk = currentRisk;

    if (currentRisk == STATE_SAFE) {
      if (filteredGas >= THRESH_CRITICAL) {
        evaluatedRisk = STATE_CRITICAL;
      } else if (filteredGas >= THRESH_DANGER) {
        evaluatedRisk = STATE_DANGER;
      } else if (filteredGas >= THRESH_WARNING) {
        evaluatedRisk = STATE_WARNING;
      }
    } else if (currentRisk == STATE_WARNING) {
      if (filteredGas >= THRESH_CRITICAL) {
        evaluatedRisk = STATE_CRITICAL;
      } else if (filteredGas >= THRESH_DANGER) {
        evaluatedRisk = STATE_DANGER;
      } else if (filteredGas < (THRESH_WARNING - HYSTERESIS)) {
        evaluatedRisk = STATE_SAFE;
      }
    } else if (currentRisk == STATE_DANGER || currentRisk == STATE_CRITICAL) {
      if (filteredGas < (THRESH_DANGER - HYSTERESIS)) {
        evaluatedRisk = STATE_WARNING;
      }
    }

    // Rate-of-rise escalation
    if (rapidRiseDetected && evaluatedRisk < STATE_DANGER) {
      evaluatedRisk = STATE_DANGER;
      Serial.println(F("[ALERT] Rapid Gas Rise Detected! Escalating to DANGER."));
    }

    currentRisk = evaluatedRisk;

    // 4. Actuator and Peripheral Execution
    executeSafetyActions(currentRisk, rapidRiseDetected);

    // 5. Serial Telemetry Logging
    Serial.print(F("Raw: ")); Serial.print(rawAdc);
    Serial.print(F(" | Filtered: ")); Serial.print(filteredGas, 1);
    Serial.print(F(" | RoR: ")); Serial.print(ratePerSecond, 1);
    Serial.print(F("/s | Risk: "));
    switch (currentRisk) {
      case STATE_SAFE:     Serial.print(F("SAFE")); break;
      case STATE_WARNING:  Serial.print(F("WARNING")); break;
      case STATE_DANGER:   Serial.print(F("DANGER")); break;
      case STATE_CRITICAL: Serial.print(F("CRITICAL")); break;
    }
    Serial.print(F(" | Valve: "));
    Serial.println(safetyLockoutActive ? F("CLOSED (LOCKOUT)") : F("OPEN"));

    previousGas = filteredGas;
    lastSampleTime = now;
  }
}

// ------------------------------------------------------------------------------
// Safety Action Actuation
// ------------------------------------------------------------------------------
void executeSafetyActions(RiskLevel risk, bool rapidRise) {
  if (risk == STATE_CRITICAL || risk == STATE_DANGER || rapidRise) {
    // Emergency Shut-off
    valveServo.write(VALVE_CLOSED_ANGLE);
    safetyLockoutActive = true;

    digitalWrite(PIN_LED_SAFE, LOW);
    digitalWrite(PIN_LED_DANGER, HIGH);

    if (risk == STATE_CRITICAL) {
      // Continuous Alarm
      digitalWrite(PIN_BUZZER, HIGH);
    } else {
      // Pulsed Alarm
      digitalWrite(PIN_BUZZER, (millis() % 500 < 250) ? HIGH : LOW);
    }
  } else if (risk == STATE_WARNING) {
    digitalWrite(PIN_LED_SAFE, LOW);
    digitalWrite(PIN_LED_DANGER, HIGH);
    digitalWrite(PIN_BUZZER, LOW);
  } else {
    // SAFE condition
    digitalWrite(PIN_LED_SAFE, HIGH);
    digitalWrite(PIN_LED_DANGER, LOW);
    digitalWrite(PIN_BUZZER, LOW);

    // If safe and not latched by prior emergency, valve is open
    if (!safetyLockoutActive) {
      valveServo.write(VALVE_OPEN_ANGLE);
    }
  }
}

