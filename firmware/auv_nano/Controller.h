#pragma once
#include <math.h>
#include <stdint.h>
#include "Config.h"
#include "Build.h"
#include "Adaptive.h"
#include "SamplingPolicy.h"

// Positive depth and vertical velocity point down. All timestamps are millis().
struct Sample {
  uint32_t acquiredMs = 0;
  float temperatureRawC = 0;
  float temperatureC = 0;
  float pressureMbar = 0;
  float depthRawM = 0;
  float depthM = 0;
  float verticalMps = 0;
  float rollDeg = 0;
  float pitchDeg = 0;
  float voltageV = 0;
  float currentA = 0;
  bool valid = false; // True only when every required channel is valid and calibrated.
  bool leak = true;
};

enum class State : uint8_t { Disarmed, Ready, Descend, Hold, Ascend, Complete, Fault };
enum Fault : uint16_t {
  NONE = 0, INVALID_SENSOR = 1, STALE_SENSOR = 2, LEAK = 4,
  BATTERY = 8, OVERCURRENT = 16, TILT = 32, DEPTH = 64,
  TIMEOUT = 128, ARM_REMOVED = 256, OPERATOR_STOP = 512
};

inline float bounded(float value, float low, float high) {
  return value < low ? low : (value > high ? high : value);
}

class Controller {
 public:
  State state = State::Disarmed;
  uint16_t faults = NONE;
  float verticalCommand = 0;
  float targetDepthM = 0;

  ProfileMode mode = ProfileMode::Adaptive;
  AdaptiveSampler sampler;
#if AUV_HAS_RESEARCH
  ThermalEstimator estimator;
  SamplingPolicy policy;
  SamplingSettings settings;
  uint32_t allowanceMs=Config::MISSION_TIMEOUT_MS;
  bool reachedBottom=false,budgetReturn=false;
#endif
  float speedLimitMps = 0;

  bool selectMode(ProfileMode requested) {
    if (state != State::Disarmed || static_cast<uint8_t>(requested)>5) return false;
#if !AUV_HAS_RESEARCH
    if(static_cast<uint8_t>(requested)>3)return false;
#endif
    mode = requested;
    return true;
  }
#if AUV_HAS_RESEARCH
  bool configure(float tau,float tauMax,float epsilon,float noise,uint32_t allowance,bool gate=true){
    if(state!=State::Disarmed||!isfinite(tau)||!isfinite(tauMax)||!isfinite(epsilon)||!isfinite(noise)||
       tau<.1f||tau>8||tauMax<tau||tauMax>16||epsilon<=0||epsilon>5||noise<0||noise>.5f||allowance<5000||allowance>600000)return false;
    settings.tauNominal=tau;settings.tauMax=tauMax;settings.epsilon=epsilon;settings.noise=noise;settings.confidenceGate=gate;
    allowanceMs=allowance;return true;
  }
#endif

  bool responseAware()const{return mode==ProfileMode::Response||mode==ProfileMode::ResponseUngated;}
  float reportedGradient()const{
#if AUV_HAS_RESEARCH
    if(responseAware())return fabsf(estimator.gradient);
#endif
    return sampler.gradientCpm;
  }
  bool reportedGradientValid()const{
#if AUV_HAS_RESEARCH
    if(responseAware())return estimator.valid;
#endif
    return sampler.gradientValid;
  }
  bool reportedTransition()const{
#if AUV_HAS_RESEARCH
    if(responseAware())return (mode==ProfileMode::ResponseUngated?estimator.geometryValid:estimator.valid)&&fabsf(estimator.gradient)>=Config::GRADIENT_ENTER_CPM;
#endif
    return sampler.transition;
  }

  bool active() const {
    return state == State::Ready || state == State::Descend ||
           state == State::Hold || state == State::Ascend;
  }

  uint16_t check(const Sample& s, uint32_t now) const {
    uint16_t f = NONE;
    if (!s.valid || !isfinite(s.temperatureRawC) || !isfinite(s.temperatureC) ||
        !isfinite(s.pressureMbar) || !isfinite(s.depthRawM) || !isfinite(s.depthM) ||
        !isfinite(s.verticalMps) || !isfinite(s.rollDeg) || !isfinite(s.pitchDeg) ||
        !isfinite(s.voltageV) || !isfinite(s.currentA)) f |= INVALID_SENSOR;
    if(s.temperatureC< -5||s.temperatureC>45||fabsf(s.verticalMps)>2)f|=INVALID_SENSOR;
    if (uint32_t(now - s.acquiredMs) > Config::SENSOR_TIMEOUT_MS) f |= STALE_SENSOR;
    if (s.leak) f |= LEAK;
    if (s.voltageV < Config::MIN_BATTERY_V) f |= BATTERY;
    if (fabsf(s.currentA) > Config::MAX_CURRENT_A) f |= OVERCURRENT;
    if (fabsf(s.rollDeg) > Config::MAX_TILT_DEG ||
        fabsf(s.pitchDeg) > Config::MAX_TILT_DEG) f |= TILT;
    if (s.depthM > Config::MAX_DEPTH_M || s.depthM < -0.2f) f |= DEPTH;
    return f;
  }

  bool arm(const Sample& s, uint32_t now, bool permit) {
    if (state != State::Disarmed || !permit) return false;
    const uint16_t f = check(s, now);
    if (f || fabsf(s.depthM) > Config::SURFACE_DEPTH_M) return false;
    faults = NONE;
    verticalCommand = 0;
#if AUV_HAS_RESEARCH
    estimator.reset();estimator.tau=settings.tauNominal;estimator.noise=settings.noise;policy.reset();
    reachedBottom=budgetReturn=false;
#endif
    armedMs = now;
    state = State::Ready;
    return true;
  }

  bool start(uint32_t now) {
    if (state != State::Ready || uint32_t(now - armedMs) < Config::ESC_SETTLE_MS)
      return false;
    sampler.reset();

    speedLimitMps = sampler.speed(mode);
    missionMs = now;
    targetDepthM = 0;
    state = State::Descend;
    return true;
  }

  void stop(uint16_t reason) {
    speedLimitMps = 0;
    faults |= reason;
    state = State::Fault;
    verticalCommand = 0;
#if AUV_HAS_RESEARCH
    estimator.valid=estimator.geometryValid=false;
    estimator.status=(reason&STALE_SENSOR)?ThermalEstimator::Stale:ThermalEstimator::Input;
#endif
  }

  void disarm() {
    sampler.reset();
#if AUV_HAS_RESEARCH
    estimator.reset();policy.reset();reachedBottom=budgetReturn=false;
#endif
    speedLimitMps = 0;
    state = State::Disarmed;
    faults = NONE;
    verticalCommand = 0;
    targetDepthM = 0;
  }

  void update(const Sample& s, uint32_t now, bool permit, float dt) {
    verticalCommand = 0;
    if (!active()) return;
    if(!isfinite(dt)||dt<0||dt>.5f){stop(INVALID_SENSOR);return;}
    uint16_t f = check(s, now);
    if (!permit) f |= ARM_REMOVED;
    if (state != State::Ready && uint32_t(now - missionMs) >= missionAllowance())
      f |= TIMEOUT;
    if (f) { stop(f); return; }
#if AUV_HAS_RESEARCH
    estimator.observe(s.acquiredMs,s.depthM,s.temperatureC);
    if(state==State::Ready)return;
    // Model-based reserve is common to every strategy. It is not a guarantee
    // for an uncharacterized physical vehicle. Hard timeout still has priority.
    const float remaining=(allowanceMs-uint32_t(now-missionMs))*.001f;
    const float returnReserve=fmaxf(0,s.depthM)/.015f+10;
    if((state==State::Descend||state==State::Hold)&&remaining<=returnReserve){
      budgetReturn=true;state=State::Ascend;targetDepthM=fmaxf(0,s.depthM);sampler.reset(true);
    }
#else
    if(state==State::Ready)return;
#endif
    if (state == State::Descend || state == State::Ascend) {
      sampler.observe(s.depthM, s.temperatureC, s.acquiredMs,
                      state == State::Descend ? 1 : -1);
      speedLimitMps = sampler.speed(mode, s.depthM);
#if AUV_HAS_RESEARCH
      if(mode==ProfileMode::Response||mode==ProfileMode::ResponseUngated){
        settings.confidenceGate=mode!=ProfileMode::ResponseUngated;
        policy.update(estimator,settings,now,dt,s.verticalMps);speedLimitMps=policy.speed;
      }
      if(budgetReturn){policy.reason=SamplingPolicy::BudgetReturn;speedLimitMps=Config::TARGET_SPEED_MPS;}
#endif
    }
    if (state == State::Descend) {
      targetDepthM = bounded(targetDepthM + speedLimitMps * dt,
                             0, Config::TARGET_DEPTH_M);
      if (targetDepthM >= Config::TARGET_DEPTH_M &&
          fabsf(s.depthM - Config::TARGET_DEPTH_M) < 0.05f && fabsf(s.verticalMps) < 0.03f) {
        speedLimitMps = 0;
#if AUV_HAS_RESEARCH
        reachedBottom=true;
#endif
        state = State::Hold;
        holdMs = now;
      }
    } else if (state == State::Hold) {
      if (uint32_t(now - holdMs) >= Config::HOLD_MS) {
        sampler.reset(true); // Revisit the measured transition band on ascent.
        state = State::Ascend;
      }
    } else if (state == State::Ascend) {
      targetDepthM = bounded(targetDepthM - speedLimitMps * dt,
                             0, Config::TARGET_DEPTH_M);
      if (s.depthM <= Config::SURFACE_DEPTH_M && targetDepthM <= Config::SURFACE_DEPTH_M) {
        speedLimitMps = 0;
        state = State::Complete;
        return;
      }
    }
    verticalCommand = bounded(Config::DEPTH_KP * (targetDepthM - s.depthM) -
                               Config::VELOCITY_KD * s.verticalMps,
                               -Config::MAX_THRUST, Config::MAX_THRUST);
  }
 private:
  uint32_t missionAllowance()const{
#if AUV_HAS_RESEARCH
    return allowanceMs;
#else
    return Config::MISSION_TIMEOUT_MS;
#endif
  }
  uint32_t armedMs = 0, missionMs = 0, holdMs = 0;
};
