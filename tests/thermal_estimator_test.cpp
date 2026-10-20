#include <cassert>
#include <cmath>
#include <iostream>
#include "ThermalEstimator.h"
#include "SamplingPolicy.h"

static void linear(float tau,bool reverse=false){
 ThermalEstimator e;e.tau=tau;
 float z=.1f,y=22;uint32_t ms=0;
 for(int i=0;i<1400;i++){
  const float dt=(i%5==0)?.08f:.05f;
  ms+=uint32_t(lroundf(dt*1000));
  z+=(reverse&&i>700?-.02f:.02f)*dt;
  const float truth=22-4*(z-.1f);y+=(truth-y)*(1-expf(-dt/tau));
  e.observe(ms,z,y);
  if(i>400&&(!reverse||std::abs(i-700)>90)){if(!e.valid)std::cerr<<"tau="<<tau<<" i="<<i<<" status="<<int(e.status)<<" span="<<e.span<<" cond="<<e.condition<<" sigma="<<e.gradientSigma<<" residual="<<e.residual<<" grad="<<e.gradient<<"\n";assert(e.valid);assert(fabsf(e.gradient+4)<.03f);assert(fabsf(e.temperature-truth)<.01f);assert(fabsf(e.supportTemperature-(22-4*(e.supportDepth-.1f)))<.01f);}
 }
}
int main(){
 linear(.3f);linear(2);linear(4,true);
 ThermalEstimator fixed;
 for(uint32_t t=0;t<20000;t+=50)fixed.observe(t,.4f,22+.005f*sinf(t*.01f));
 assert(!fixed.valid&&!fixed.geometryValid);
 ThermalEstimator flat;float z=0;
 for(uint32_t t=0;t<20000;t+=50){z+=.001f;flat.observe(t,z,22+.002f*sinf(t*.01f));}
 assert(flat.valid&&fabsf(flat.gradient)<.1f);
 flat.observe(19950,z,22);assert(!flat.valid&&flat.status==ThermalEstimator::Stale);
 flat.observe(21000,z,22);assert(!flat.valid&&!flat.geometryValid);
 flat.observe(21050,z,NAN);assert(flat.status==ThermalEstimator::Input);
 ThermalEstimator wrap;
 for(uint32_t i=0;i<300;i++)wrap.observe(uint32_t(4294960000UL+i*50),i*.001f,22);
 assert(wrap.valid);
 SamplingSettings settings;SamplingPolicy policy;
 ThermalEstimator fit;fit.valid=fit.geometryValid=true;fit.gradient=4;
 for(uint32_t t=0;t<10000;t+=50)policy.update(fit,settings,t,.05f,.03f);
 assert(policy.speed==.02f&&policy.modelLimit<.02f&&policy.reason==SamplingPolicy::FloorLimited);
 fit.valid=false;fit.gradient=NAN;policy.update(fit,settings,10000,.05f,.03f);
 assert(isfinite(policy.speed)&&policy.speed>=.02f&&policy.speed<=.05f);
 fit.valid=fit.geometryValid=true;fit.gradient=0;
 float previous=policy.speed;
 for(uint32_t t=10050;t<18000;t+=50){policy.update(fit,settings,t,.05f,.03f);assert(fabsf(policy.speed-previous)<=.000501f);previous=policy.speed;}
 assert(policy.speed>.049f);
 // The review's impossibility result must hold for every permitted tau/speed.
 for(float tau=.1f;tau<=8;tau+=.1f){
  const float speed=fminf(.04f,.08f/tau);const auto p=inspectionPlan(.1f,tau,speed);
  assert(!p.fullFeasible&&p.available+.03f<p.required&&p.neededSeconds>8);
 }
 std::cout<<"PASS: forward model ramp/reversal/jitter, noisy flat field, stationary rejection, stale/invalid/wrap, rate/confidence gates and impossible retrace\n";
}
