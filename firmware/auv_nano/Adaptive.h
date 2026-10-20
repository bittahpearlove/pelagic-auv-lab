#pragma once
#include <math.h>
#include <stdint.h>
#include "Config.h"

enum class ProfileMode : uint8_t { Adaptive, Fast, Slow, Medium, Response, ResponseUngated };

// Endpoint gradient over nonoverlapping depth windows. No division near zero,
// no observations from duplicate acquisition timestamps, no cross-leg history.
class AdaptiveLegacy {
 public:
  float gradientCpm = 0;
  bool transition = false;
  bool gradientValid = false;
  // A conservative depth interval, learned from measurements, survives the
  // turn at depth. Acquisition history never crosses a reversal.
  bool regionValid = false;
  float regionLow = 0, regionHigh = 0;
  void reset(bool keepRegion = false) {
    initialized = false;
    gradientCpm = 0;
    gradientValid = transition = false;
    highCount = lowCount = 0;
    if (!keepRegion) { regionValid = false; regionLow = regionHigh = 0; }
  }
  void observe(float depth, float temperature, uint32_t stamp, int8_t direction) {
    if (!isfinite(depth) || !isfinite(temperature)) return;
    if (!initialized) {
      initialized = true;
      anchorDepth = depth; anchorTemp = temperature; lastStamp = anchorStamp = stamp;
      return;
    }
    if (stamp == lastStamp) return;
    lastStamp = stamp;
    const float progress = (depth - anchorDepth) * direction;
    // Unexpected reversal: discard window rather than mixing ascent/descent.
    if (progress < -Config::GRADIENT_WINDOW_M) {
      reset(true); observe(depth, temperature, stamp, direction); return;
    }
    if (progress < Config::GRADIENT_WINDOW_M) return;
    gradientCpm = fabsf((temperature - anchorTemp) / (depth - anchorDepth));
    gradientValid = true;
    if (gradientCpm >= Config::GRADIENT_ENTER_CPM) {
      const float elapsed = uint32_t(stamp - anchorStamp) * .001f;
      const float velocity = elapsed > 0 ? fminf(Config::TARGET_SPEED_MPS, progress / elapsed) : Config::TARGET_SPEED_MPS;
      const float margin = velocity * Config::PROBE_TAU_S + Config::GRADIENT_WINDOW_M;
      const float lo = fmaxf(0, fminf(depth, anchorDepth) - margin);
      const float hi = fminf(Config::TARGET_DEPTH_M, fmaxf(depth, anchorDepth) + margin);
      if (!highCount) { pendingLow = lo; pendingHigh = hi; }
      else { pendingLow = fminf(pendingLow, lo); pendingHigh = fmaxf(pendingHigh, hi); }
      lowCount = 0;
      if (highCount < Config::ENTER_WINDOWS) ++highCount;
      if (highCount >= Config::ENTER_WINDOWS) {
        transition = true;
        regionLow = regionValid ? fminf(regionLow, pendingLow) : pendingLow;
        regionHigh = regionValid ? fmaxf(regionHigh, pendingHigh) : pendingHigh;
        regionValid = true;
      }
    } else if (gradientCpm <= Config::GRADIENT_EXIT_CPM) {
      highCount = 0;
      if (lowCount < Config::EXIT_WINDOWS) ++lowCount;
      if (lowCount >= Config::EXIT_WINDOWS) transition = false;
    } else {
      highCount = lowCount = 0; // Persistence requires consecutive windows.
    }
    anchorDepth = depth; anchorTemp = temperature; anchorStamp = stamp;
  }
  float speed(ProfileMode mode, float depth = NAN) const {
    if (mode == ProfileMode::Medium) return .035f;
    const float lagLimit = Config::ALLOWED_LAG_M / Config::PROBE_TAU_S;
    const float slow = fminf(Config::SLOW_SPEED_MPS, lagLimit);
    const bool revisit = regionValid && isfinite(depth) && depth >= regionLow && depth <= regionHigh;
    return mode == ProfileMode::Slow || (mode == ProfileMode::Adaptive && (transition || revisit))
      ? fminf(slow, Config::TARGET_SPEED_MPS) : Config::TARGET_SPEED_MPS;
  }
 private:
  bool initialized = false;
  uint8_t highCount = 0, lowCount = 0;
  float anchorDepth = 0, anchorTemp = 0;
  float pendingLow = 0, pendingHigh = 0;
  uint32_t lastStamp = 0, anchorStamp = 0;
};
static_assert(Config::PROBE_TAU_S > 0 && Config::ALLOWED_LAG_M > 0 &&
              Config::SLOW_SPEED_MPS > 0 && Config::GRADIENT_WINDOW_M > 0,
              "Adaptive parameters must be positive");

using AdaptiveSampler = AdaptiveLegacy; // Stable name retained for older tests and integrations.
