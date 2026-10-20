#pragma once
#include <math.h>
// The bound is deliberately evaluated before choosing movement. A short partial
// inspection is different from claiming to cover the complete sensor-lag margin.
struct InspectionPlan {
  float required,available,neededSeconds;
  bool fullFeasible;
};
inline InspectionPlan inspectionPlan(float velocity,float tau,float retraceSpeed,float allowance=8){
  InspectionPlan p;
  p.required=fabsf(velocity)*tau+.30f;
  p.neededSeconds=p.required/fmaxf(.001f,retraceSpeed)+4.4f+tau;
  p.fullFeasible=p.neededSeconds<=allowance;
  p.available=fmaxf(0,allowance-4.4f)*retraceSpeed;
  return p;
}
