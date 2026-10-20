#pragma once
#include <stdint.h>

namespace Config {
constexpr uint8_t WATER_SHAPE = 0; // 0 layer, 1 tilted, 2 lateral front, 3 patch, 4 combined
constexpr float PROFILE_X_M = 4.0f; // Fixed simulated vertical transect; not navigation
static_assert(WATER_SHAPE <= 4, "Unknown simulated water shape");
static_assert(PROFILE_X_M >= 0.5f && PROFILE_X_M <= 7.5f, "Simulated x must be inside the laboratory");
constexpr float WATER_CENTER_M = 0.5f;
constexpr float WATER_WIDTH_M = 0.07f;
constexpr float WATER_DROP_C = 3.0f;
constexpr float WATER_SURFACE_C = 22.0f;
// Classic Nano / ATmega328P. Keep these defaults for the first bench run.
constexpr bool SIMULATED_SENSORS = true;
constexpr bool ENABLE_MOTOR_OUTPUTS = false;
static_assert(!(SIMULATED_SENSORS && ENABLE_MOTOR_OUTPUTS),
              "Simulated sensors must never drive real motors");
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t CONTROL_MS = 50;
constexpr uint32_t TELEMETRY_MS = 500;
constexpr uint32_t SENSOR_TIMEOUT_MS = 500;
constexpr uint32_t ESC_SETTLE_MS = 5000;
constexpr uint32_t MISSION_TIMEOUT_MS = 180000;
constexpr uint32_t HOLD_MS = 5000;
constexpr float TARGET_DEPTH_M = 1.0f;
constexpr float MAX_DEPTH_M = 1.5f;
constexpr float SURFACE_DEPTH_M = 0.08f;
constexpr float TARGET_SPEED_MPS = 0.05f;
// Provisional simulation settings; replace from installed-probe characterisation.
constexpr float PROBE_TAU_S = 2.0f;
constexpr float ALLOWED_LAG_M = 0.04f;
constexpr float SLOW_SPEED_MPS = 0.02f;
constexpr float GRADIENT_WINDOW_M = 0.05f;
constexpr float GRADIENT_ENTER_CPM = 2.0f;
constexpr float GRADIENT_EXIT_CPM = 0.8f;
constexpr uint8_t ENTER_WINDOWS = 2;
constexpr uint8_t EXIT_WINDOWS = 3;
constexpr float DEPTH_KP = 0.8f;  // Starting values for simulation; tune in water.
constexpr float VELOCITY_KD = 0.5f;
constexpr float MAX_THRUST = 0.25f;
constexpr float MIN_BATTERY_V = 10.5f; // Placeholder for a 3S pack; confirm chemistry.
constexpr float MAX_CURRENT_A = 10.0f; // Placeholder; replace from power budget.
constexpr float MAX_TILT_DEG = 30.0f;
constexpr uint8_t LEFT_ESC_PIN = 3;
constexpr uint8_t RIGHT_ESC_PIN = 5;
constexpr uint8_t VERTICAL_ESC_PIN = 6;
constexpr uint8_t ARM_PIN = 7;       // External maintained switch: closed to GND = arm permit.
constexpr uint8_t LEAK_PIN = 2;      // Normally closed dry loop to GND; open = wet/broken wire.
constexpr uint16_t ESC_NEUTRAL_US = 1500;
constexpr uint16_t ESC_SPAN_US = 400; // Generic bidirectional PWM assumption, verify ESC manual.
constexpr int8_t VERTICAL_SIGN = 1;  // Positive logical thrust means DOWN.
}
