# Optional Physical Hardware Integration

> [!WARNING]
> **Safety Warning & Disclaimer:**
> This hardware implementation is strictly an educational micro-controller prototype for bench-top demonstration.
> It **must NEVER be connected to a live LPG gas cylinder or pressurized gas pipeline**.
> Real-world explosive gas installations require intrinsically safe, explosion-proof (ATEX / IECEx certified) valves, flameproof enclosures, and certified industrial gas detection instruments.

---

## 1. Hardware Architecture Overview

This optional sketch demonstrates how the simulated software logic (moving average filtering, rate-of-rise threshold calculation, multi-level alert escalations, and servo-actuated shut-off) maps directly onto physical micro-controller hardware (ESP8266 NodeMCU or ESP32).

```
                      +-------------------+
                      |   NodeMCU ESP8266 |
                      |    (ESP-12E Module)|
                      +---------+---------+
                                |
       +------------------------+------------------------+
       |                        |                        |
+------v------+          +------v------+          +------v------+
| MQ-5 Sensor |          | SG90 Servo  |          | I2C OLED    |
| (Analog A0) |          | (PWM D4)    |          | (SSD1306)   |
+-------------+          +-------------+          +-------------+
       |                        |
+------v------+          +------v------+
| Warning LED |          | Danger LED  |
| (Digital D6)|          | + Buzzer    |
+-------------+          | (D7 & D5)   |
                         +-------------+
```

---

## 2. Bill of Materials (BOM)

| Component | Description | Pin Connection |
| :--- | :--- | :--- |
| **Microcontroller** | NodeMCU ESP8266 or ESP32 Dev Kit | Micro-USB power / 5V |
| **Gas Sensor** | MQ-5 or MQ-6 LPG/Propane Gas Sensor | Analog Output -> `A0` (VCC to 5V, GND to GND) |
| **Actuator** | TowerPro SG90 9g Micro Servo Motor | Signal -> `D4` (GPIO2), 5V, GND |
| **Acoustic Alert** | 5V Active Piezo Buzzer | Positive -> `D5` (GPIO14), Negative to GND |
| **Visual Indicators** | 5mm Green LED (Safe/Power) | Anode -> `D6` (GPIO12) via 330Ω resistor |
| | 5mm Red LED (Warning/Danger) | Anode -> `D7` (GPIO13) via 330Ω resistor |
| **Display (Optional)**| 0.96" I2C OLED (SSD1306 128x64) | SDA -> `D2` (GPIO4), SCL -> `D1` (GPIO5) |

---

## 3. Operational Logic on Microcontroller

1. **Sensor Reading & ADC Sampling:**
   Samples raw analog ADC reading on `A0` every 500 ms.
2. **Exponential Moving Average (EMA):**
   Smooths analog electrical noise:
   $$EMA_{t} = \alpha \times Raw + (1 - \alpha) \times EMA_{t-1}$$
3. **Rate-of-Rise (RoR) Calculation:**
   Computes delta per second to detect rapid bursts before absolute concentration reaches dangerous levels.
4. **Servo Actuation:**
   - **SAFE (0-199 ADC):** Servo at 90° (Valve Open)
   - **WARNING (200-399 ADC):** Servo at 90° (Warning LED active)
   - **DANGER / CRITICAL (>= 400 ADC or Rapid RoR):** Servo drives to 0° (Valve Closed) and latches until reset.
5. **Optional MQTT Telemetry:**
   Optionally connects to local Wi-Fi to publish JSON telemetry packets to the backend server's Mosquitto broker.
