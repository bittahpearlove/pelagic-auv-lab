// Native wrapper around the exact header used by the Nano firmware.
#include "../firmware/auv_nano/Controller.h"
#include "../firmware/auv_nano/ReportedConfig.h"
#include "../firmware/auv_nano/ThermalField.h"
static Controller control;
extern "C" {
const char* lab_version(){return AUV_VERSION;}
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
int lab_profile_config(float tau,float tauMax,float epsilon,float noise){return control.configure(tau,tauMax,epsilon,noise,Config::MISSION_TIMEOUT_MS);}
void lab_stop() { control.stop(OPERATOR_STOP); }
int lab_arm(unsigned int now) {
  Sample s; s.valid = true; s.leak = false; s.voltageV = 12; s.acquiredMs = now;
  return control.arm(s, now, true);
}
void tickController(Controller& controller, unsigned int now, float dt, const float* input, float* out) {
  Sample s;
  s.acquiredMs = static_cast<uint32_t>(input[0]);
  s.temperatureRawC = s.temperatureC = input[1];
  s.depthRawM = s.depthM = input[2]; s.verticalMps = input[3];
  s.pressureMbar = 1013.25f + s.depthM * 98.0665f;
  s.voltageV = input[4]; s.currentA = input[5]; s.rollDeg = input[6];
  s.valid = input[7] != 0; s.leak = input[8] != 0;
  controller.update(s, now, true, dt);
  if (controller.state == State::Ready) controller.start(now);
  out[0] = static_cast<int>(controller.state); out[1] = controller.faults;
  out[2] = controller.verticalCommand; out[3] = controller.targetDepthM;
  out[4] = controller.speedLimitMps; out[5] = controller.reportedGradient();
  out[6] = controller.reportedGradientValid(); out[7] = controller.reportedTransition();
  out[8] = static_cast<int>(controller.mode);
}
void lab_tick(unsigned int now, float dt, const float* input, float* out) {
  tickController(control, now, dt, input, out);
}
// Independent instance: a benchmark never resets the live controller.
static Controller trial;
void lab_trial_reset(int mode) {
  trial=Controller(); trial.selectMode(static_cast<ProfileMode>(mode));
  Sample s; s.valid=true; s.leak=false; s.voltageV=12;
  trial.arm(s,0,true);
}
int lab_trial_config(int mode,float tau,float tauMax,float epsilon,float noise,unsigned int allowance) {
  trial=Controller();
  if(!trial.configure(tau,tauMax,epsilon,noise,allowance)||!trial.selectMode(static_cast<ProfileMode>(mode)))return 0;
  Sample s;s.valid=true;s.leak=false;s.voltageV=12;
  return trial.arm(s,0,true);
}
void diagnostics(const Controller&c,float*out){
  out[0]=c.estimator.temperature;out[1]=c.estimator.gradient;out[2]=c.estimator.residual;
  out[3]=c.estimator.valid;out[4]=c.policy.reason;out[5]=c.estimator.gradientSigma;
  out[6]=c.estimator.condition;out[7]=c.estimator.span;out[8]=c.settings.tauNominal;
  out[9]=c.settings.tauMax;out[10]=c.reachedBottom;out[11]=c.budgetReturn;
  out[12]=c.estimator.geometryValid;out[13]=c.estimator.status;
  out[14]=c.policy.modelLimit;out[15]=c.policy.predictedLag;
  out[16]=c.estimator.supportDepth;out[17]=c.estimator.supportTemperature;
}
void lab_diagnostics(float*out){diagnostics(control,out);}
void lab_trial_stop(){trial.stop(TIMEOUT);}
void lab_trial_tick(unsigned int now,float dt,const float* input,float* out) {
  tickController(trial,now,dt,input,out);
  out[9]=trial.sampler.regionValid; out[10]=trial.sampler.regionLow;
  out[11]=trial.sampler.regionHigh;
  diagnostics(trial,out+12);
}

}
#include "../firmware/auv_nano/Explorer.h"
static Explorer explorer;
extern "C" {
void lab_explore_begin(){explorer.begin();}
void lab_explore_tick(unsigned int ms,const float* in,float* out){
  ExplorationObservation o={in[0],in[1],in[2],in[3],in[4],ms};explorer.update(o);
  out[0]=explorer.active;out[1]=explorer.local?explorer.phase:0;out[2]=explorer.reason;out[3]=explorer.surge;out[4]=explorer.heave;
  out[5]=explorer.targetX;out[6]=explorer.targetZ;out[7]=explorer.gx;out[8]=explorer.gz;out[9]=explorer.gradientValid;out[10]=explorer.visits;out[11]=explorer.phase;out[12]=explorer.distance;out[13]=explorer.localExit;out[14]=explorer.knownCells;out[15]=0;
}
}
extern "C" void lab_explore_tau(float tau){explorer.tau=tau;}


