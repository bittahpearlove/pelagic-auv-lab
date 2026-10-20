#include <cassert>
#include <cmath>
#include <iostream>
#include "Controller.h"
#include "Sensors.h"

Sample healthy(uint32_t now = 0) {
  Sample s;
  s.acquiredMs = now; s.valid = true; s.leak = false;
  s.voltageV = 12; s.pressureMbar = 1013; s.temperatureC = 22;
  return s;
}
void begin(Controller& c, uint32_t now = 0) {
  assert(c.arm(healthy(now), now, true));
  assert(!c.start(now + Config::ESC_SETTLE_MS - 1));
  assert(c.start(now + Config::ESC_SETTLE_MS));
}
int main() {
  AdaptiveSampler a;
  a.reset();
  a.observe(0, 22, 1, 1);
  a.observe(0.06f, 21.5f, 1, 1); // Duplicate acquisition must not count.
  assert(!a.gradientValid);
  a.observe(0, 18, 2, 1); // Zero movement must not count.
  assert(!a.gradientValid);
  a.observe(0.06f, 21.5f, 3, 1);
  assert(!a.transition); // One high window is insufficient.
  a.observe(0.12f, 21, 4, 1);
  assert(a.transition && a.speed(ProfileMode::Adaptive) < Config::TARGET_SPEED_MPS);
  assert(a.speed(ProfileMode::Fast) == Config::TARGET_SPEED_MPS);
  a.observe(0.18f, 21, 5, 1); a.observe(0.24f, 21, 6, 1);
  assert(a.transition);
  a.observe(0.30f, 21, 7, 1); assert(!a.transition);
  assert(a.regionValid);
  const float learnedLow = a.regionLow, learnedHigh = a.regionHigh;
  a.reset(true); // The ascent gets new acquisition history, but retains the band.
  assert(!a.gradientValid && !a.transition && a.regionValid);
  assert(a.speed(ProfileMode::Adaptive, (learnedLow+learnedHigh)/2) <= Config::SLOW_SPEED_MPS);
  assert(a.speed(ProfileMode::Fast, (learnedLow+learnedHigh)/2) == Config::TARGET_SPEED_MPS);
  a.reset(); assert(!a.gradientValid && !a.transition);
  assert(!a.regionValid); // A new mission cannot inherit an old water column.
  a.observe(1, 19, 10, -1); a.observe(0.94f, 19.5f, 11, -1);
  a.observe(0.88f, 20, 12, -1); assert(a.transition);
  // Flat/noisy stationary readings cannot manufacture a transition.
  a.reset();
  for (uint32_t i = 0; i < 100; ++i) a.observe(0.2f, 22 + (i % 2 ? 0.01f : -0.01f), i, 1);
  assert(!a.gradientValid && !a.transition);
  uint32_t durations[3] = {};
  for (uint8_t index = 0; index < 3; ++index) {
    Controller run;
    assert(run.selectMode(static_cast<ProfileMode>(index)));
    begin(run);
    assert(!run.selectMode(ProfileMode::Fast));
    Sensors plant; plant.begin();
    for (uint32_t now = 5050; now < Config::MISSION_TIMEOUT_MS + 5000; now += 50) {
      auto measurement = plant.read(now, run.verticalCommand, 0.05f);
      run.update(measurement, now, true, 0.05f);
      assert(run.state != State::Fault);
      if (index == 1 && run.state == State::Descend) assert(run.speedLimitMps == Config::TARGET_SPEED_MPS);
      if (index == 2 && run.state == State::Descend) assert(run.speedLimitMps <= Config::SLOW_SPEED_MPS);
      if (run.state == State::Complete) { durations[index] = now - 5000; break; }
    }
    assert(durations[index]);
  }
  assert(durations[1] < durations[0] && durations[0] < durations[2]);
  std::cout << "Simulation seconds: adaptive=" << durations[0]/1000.0f
            << " fast=" << durations[1]/1000.0f << " slow=" << durations[2]/1000.0f << "\n";
  Controller c;
  assert(!c.start(0));
  assert(!c.arm(healthy(), 0, false));
  auto s = healthy(); s.valid = false;
  assert(!c.arm(s, 0, true));
  s = healthy(); s.depthM = 0.5f;
  assert(!c.arm(s, 0, true));
  const uint16_t expected[] = {INVALID_SENSOR, STALE_SENSOR, LEAK, BATTERY,
                              OVERCURRENT, TILT, DEPTH, ARM_REMOVED};
  for (unsigned i = 0; i < 8; ++i) {
    Controller f; begin(f);
    s = healthy(5050);
    switch (i) {
      case 0: s.temperatureC = NAN; break;
      case 1: s.acquiredMs = 0; break;
      case 2: s.leak = true; break;
      case 3: s.voltageV = 9; break;
      case 4: s.currentA = 11; break;
      case 5: s.pitchDeg = 31; break;
      case 6: s.depthM = 2; break;
    }
    f.update(s, 5050, i != 7, 0.05f);
    assert(f.state == State::Fault && (f.faults & expected[i]));
    assert(f.verticalCommand == 0);
    f.update(healthy(5100), 5100, true, 0.05f);
    assert(f.state == State::Fault);
    assert(!f.arm(healthy(5100), 5100, true));
    f.disarm(); assert(f.arm(healthy(5100), 5100, true));
  }
  Controller timed; begin(timed);
  const uint32_t expired = Config::ESC_SETTLE_MS + Config::MISSION_TIMEOUT_MS;
  timed.update(healthy(expired), expired, true, 0.05f);
  assert(timed.faults & TIMEOUT);
  Controller wrapped;
  const uint32_t nearWrap = UINT32_MAX - 2000;
  begin(wrapped, nearWrap);
  uint32_t wrappedNow = nearWrap + Config::ESC_SETTLE_MS + 50;
  wrapped.update(healthy(wrappedNow), wrappedNow, true, 0.05f);
  assert(wrapped.state == State::Descend && !wrapped.faults);
  Sample stale = healthy(UINT32_MAX - 100);
  assert(!(wrapped.check(stale, 100) & STALE_SENSOR));
  assert(wrapped.check(stale, 600) & STALE_SENSOR);

  Sensors sim;
  Controller mission; begin(mission);
  bool held = false, ascended = false, slowed = false;
  for (uint32_t now = 5050; now < Config::MISSION_TIMEOUT_MS + 5000; now += 50) {
    Sample sample = sim.read(now, mission.verticalCommand, 0.05f);
    mission.update(sample, now, true, 0.05f);
    assert(std::fabs(mission.verticalCommand) <= Config::MAX_THRUST);
    assert(mission.state != State::Fault);
    slowed |= mission.sampler.transition;
    held |= mission.state == State::Hold;
    ascended |= mission.state == State::Ascend;
    if (mission.state == State::Complete) break;
  }
  assert(slowed);
  assert(held && ascended && mission.state == State::Complete);
  assert(mission.verticalCommand == 0);
  mission.stop(OPERATOR_STOP);
  assert(mission.state == State::Fault && mission.faults == OPERATOR_STOP);
  std::cout << "PASS: mission, output limits, preflight, faults, latching, timeout, millis rollover\n";
}
