#pragma once
#include <math.h>
#include <stdint.h>
#include "ThermalEstimator.h"
#include "ProbeModel.h"

struct SamplingSettings {
  float tauNominal=2,tauMax=2.5f,epsilon=.1f,noise=.005f;
  bool confidenceGate=true;
};
class SamplingPolicy {
 public:
  enum Reason : uint8_t { Fixed=0,Fallback=1,LagLimited=2,FloorLimited=3,Quiet=4,BudgetReturn=5,RateLimited=6,Hysteresis=7 };
  float speed=.02f,modelLimit=.02f,predictedLag=0;
  uint8_t reason=Fallback;
  void reset(){speed=modelLimit=.02f;predictedLag=0;reason=Fallback;lastChange=0;increaseCount=0;lastDirection=0;}
  void update(const ThermalEstimator&e,const SamplingSettings&c,uint32_t ms,float dt,float achieved){
    const bool usable=c.confidenceGate?e.valid:e.geometryValid;
    float desired=.02f;reason=Fallback;modelLimit=.02f;
    if(usable&&isfinite(e.gradient)&&isfinite(c.tauMax)&&c.tauMax>0&&isfinite(c.epsilon)&&c.epsilon>0){
      modelLimit=c.epsilon/(c.tauMax*fmaxf(.2f,fabsf(e.gradient)));
      desired=fmaxf(.02f,fminf(.05f,modelLimit));
      reason=modelLimit<.02f?FloorLimited:desired<.049f?LagLimited:Quiet;
    }
    predictedLag=usable?c.tauMax*fabsf(achieved)*fabsf(e.gradient):0;
    if(desired>speed+.002f){
      if(increaseCount<255)increaseCount++;
      if(increaseCount<4||(lastDirection!=1&&uint32_t(ms-lastChange)<1000)){desired=speed;reason=Hysteresis;}
    }else increaseCount=0;
    const float step=.01f*fmaxf(0,fminf(.2f,dt));
    const float next=fmaxf(speed-step,fminf(speed+step,desired));
    if(fabsf(next-desired)>.00001f)reason=RateLimited;
    const int8_t direction=next>speed+.000001f?1:next<speed-.000001f?-1:0;
    if(direction&&direction!=lastDirection){lastChange=ms;lastDirection=direction;}
    speed=fmaxf(.02f,fminf(.05f,next));
  }
 private:
  uint32_t lastChange=0;
  uint8_t increaseCount=0;
  int8_t lastDirection=0;
};

