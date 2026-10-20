#pragma once
#include <math.h>
#include <stdint.h>
// Shared teaching field: x in metres, z positive downward, temperature in Celsius.
// Shapes: 0 level layer, 1 tilted layer, 2 lateral front, 3 layer+patch, 4 tilted+patch.
inline float waterTemperature(float x, float z, uint8_t shape, float center,
                              float width, float drop, float surface = 22.0f) {
  if (shape == 2) return surface - drop / 2 * (1 + tanhf((x - 4) / (5 * width)));
  const float slope = (shape == 1 || shape == 4) ? 0.16f : 0;
  float value = surface - drop / 2 * (1 + tanhf((z - center - slope * (x - 4)) / width));
  if (shape == 3 || shape == 4) {
    const float dx = (x - 5.3f) / 0.75f, dz = (z - center - 0.35f) / 0.3f;
    value += 2 * expf(-0.5f * (dx * dx + dz * dz));
  }
  return value;
}
