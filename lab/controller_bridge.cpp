// Native wrapper around the exact header used by the Nano firmware.
#include "../firmware/auv_nano/Controller.h"
#include "../firmware/auv_nano/ReportedConfig.h"
#include "../firmware/auv_nano/ThermalField.h"
static Controller control;
extern "C" {
float lab_water(float x, float z, int shape, float center, float width, float drop) {
  return waterTemperature(x, z, static_cast<uint8_t>(shape), center, width, drop);
}
int lab_config(float* out) {
  int i = 0;
#define REPORT_VALUE(key, constant) out[i++] = Config::constant;
  AUV_REPORTED_CONFIG(REPORT_VALUE)
#undef REPORT_VALUE
  return i;
}
void lab_reset(int mode) { control.disarm(); control.selectMode(static_cast<ProfileMode>(mode)); }
void lab_disarm() { control.disarm(); }
void lab_stop() { control.stop(OPERATOR_STOP); }
int lab_arm(unsigned int now) {
  Sample s; s.valid = true; s.leak = false; s.voltageV = 12; s.acquiredMs = now;
  return control.arm(s, now, true);
}
void lab_tick(unsigned int now, float dt, const float* input, float* out) {
  Sample s;
  s.acquiredMs = static_cast<uint32_t>(input[0]);
  s.temperatureRawC = s.temperatureC = input[1];
  s.depthRawM = s.depthM = input[2]; s.verticalMps = input[3];
  s.pressureMbar = 1013.25f + s.depthM * 98.0665f;
  s.voltageV = input[4]; s.currentA = input[5]; s.rollDeg = input[6];
  s.valid = input[7] != 0; s.leak = input[8] != 0;
  control.update(s, now, true, dt);
  if (control.state == State::Ready) control.start(now);
  out[0] = static_cast<int>(control.state); out[1] = control.faults;
  out[2] = control.verticalCommand; out[3] = control.targetDepthM;
  out[4] = control.speedLimitMps; out[5] = control.sampler.gradientCpm;
  out[6] = control.sampler.gradientValid; out[7] = control.sampler.transition;
  out[8] = static_cast<int>(control.mode);
}
}
#include "../firmware/auv_nano/Explorer.h"
static Explorer explorer;
extern "C" {
void lab_explore_begin(){explorer.begin();}
void lab_explore_tick(unsigned int ms,const float* in,float* out){
  ExplorationObservation o={in[0],in[1],in[2],in[3],in[4],ms};explorer.update(o);
  out[0]=explorer.active;out[1]=explorer.local?explorer.phase:0;out[2]=explorer.reason;out[3]=explorer.surge;out[4]=explorer.heave;
  out[5]=explorer.targetX;out[6]=explorer.targetZ;out[7]=explorer.gx;out[8]=explorer.gz;out[9]=explorer.gradientValid;out[10]=explorer.visits;out[11]=explorer.phase;out[12]=explorer.distance;out[13]=explorer.localExit;out[14]=explorer.knownCells;out[15]=explorer.rechecks;
}
}
extern "C" void lab_explore_tau(float tau){explorer.tau=tau;}


