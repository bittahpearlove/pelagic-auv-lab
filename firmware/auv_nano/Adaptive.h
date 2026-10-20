#pragma once
#include <math.h>
#include <stdint.h>
#include "Config.h"

enum class ProfileMode : uint8_t { Adaptive, Fast, Slow };

// Endpoint gradient over nonoverlapping depth windows. No division near zero,
// no observations from duplicate acquisition timestamps, no cross-leg history.
class AdaptiveSampler {
 public:
  float gradientCpm = 0;
  bool transition = false;
  bool gradientValid = false;
  void reset() {
    initialized = false;
    gradientCpm = 0;
    gradientValid = transition = false;
    highCount = lowCount = 0;
  }
  void observe(float depth, float temperature, uint32_t stamp, int8_t direction) {
    if (!isfinite(depth) || !isfinite(temperature)) return;
    if (!initialized) {
      initialized = true;
      anchorDepth = depth; anchorTemp = temperature; lastStamp = stamp;
      return;
    }
    if (stamp == lastStamp) return;
    lastStamp = stamp;
    const float progress = (depth - anchorDepth) * direction;
    // Unexpected reversal: discard window rather than mixing ascent/descent.
    if (progress < -Config::GRADIENT_WINDOW_M) {
      reset(); observe(depth, temperature, stamp, direction); return;
    }
    if (progress < Config::GRADIENT_WINDOW_M) return;
    gradientCpm = fabsf((temperature - anchorTemp) / (depth - anchorDepth));
    gradientValid = true;
    anchorDepth = depth; anchorTemp = temperature;
    if (gradientCpm >= Config::GRADIENT_ENTER_CPM) {
      lowCount = 0;
      if (highCount < Config::ENTER_WINDOWS) ++highCount;
      if (highCount >= Config::ENTER_WINDOWS) transition = true;
    } else if (gradientCpm <= Config::GRADIENT_EXIT_CPM) {
      highCount = 0;
      if (lowCount < Config::EXIT_WINDOWS) ++lowCount;
      if (lowCount >= Config::EXIT_WINDOWS) transition = false;
    } else {
      highCount = lowCount = 0; // Persistence requires consecutive windows.
    }
  }
  float speed(ProfileMode mode) const {
    const float lagLimit = Config::ALLOWED_LAG_M / Config::PROBE_TAU_S;
    const float slow = fminf(Config::SLOW_SPEED_MPS, lagLimit);
    return mode == ProfileMode::Slow || (mode == ProfileMode::Adaptive && transition)
      ? fminf(slow, Config::TARGET_SPEED_MPS) : Config::TARGET_SPEED_MPS;
  }
 private:
  bool initialized = false;
  uint8_t highCount = 0, lowCount = 0;
  float anchorDepth = 0, anchorTemp = 0;
  uint32_t lastStamp = 0;
};
static_assert(Config::PROBE_TAU_S > 0 && Config::ALLOWED_LAG_M > 0 &&
              Config::SLOW_SPEED_MPS > 0 && Config::GRADIENT_WINDOW_M > 0,
              "Adaptive parameters must be positive");
