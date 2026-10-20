#pragma once
#include "Controller.h"
#include "ThermalField.h"

class Sensors {
 public:
  uint8_t shape = Config::WATER_SHAPE;
  float profileX = Config::PROFILE_X_M;
  void begin() { depth = velocity = 0; measuredTemperature = 22; }
  Sample read(uint32_t now, float previousCommand, float dt) {
    Sample s;
    if (Config::SIMULATED_SENSORS) {
      // Toy plant for exercising state transitions, not a hydrodynamic model.
      velocity += (previousCommand * 1.2f - velocity * 1.5f - 0.01f) * dt;
      depth += velocity * dt;
      if (depth <= 0) { depth = 0; velocity = 0; }
      s.acquiredMs = now;
      s.depthRawM = s.depthM = depth;
      s.verticalMps = velocity;
      s.pressureMbar = 1013.25f + depth * 98.0665f;
      // Stable warm-over-cold layer; the controller sees only the lagged probe.
      const float trueTemperature = waterTemperature(profileX, depth, shape, Config::WATER_CENTER_M, Config::WATER_WIDTH_M, Config::WATER_DROP_C, Config::WATER_SURFACE_C);
      measuredTemperature += (trueTemperature - measuredTemperature) *
                             (1.0f - expf(-dt / Config::PROBE_TAU_S));
      s.temperatureRawC = s.temperatureC = measuredTemperature;
      s.voltageV = 12.0f;
      s.currentA = fabsf(previousCommand) * 4.0f;
      s.leak = false;
      s.valid = true;
    }
    // Real hardware adapter deliberately returns invalid until implemented.
    // Add asynchronous acquisition, surface pressure zero, calibration and filtering
    // here. acquiredMs must describe the oldest required channel, NOT the loop time.
    return s;
  }
 private:
  float measuredTemperature = 22;
  float depth = 0;
  float velocity = 0;
};
