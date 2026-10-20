#pragma once
#include <math.h>
#include <stdint.h>

// Forward-model least squares, not differentiation/deconvolution of noisy y.
// y-y0 = psi0*(beta0-y0) + psiz*gradient for a held linear field.
// Geometry, residual and initial-state gates are diagnostics, not calibrated CIs.
class ThermalEstimator {
 public:
  enum Invalid : uint8_t { Warming=1,Geometry=2,Condition=3,Residual=4,Stale=5,Input=6,Good=0 };
  static const uint8_t Capacity=12;
  float temperature=0,gradient=0,residual=0,gradientSigma=0,span=0,condition=0,supportDepth=0,supportTemperature=0;
  bool valid=false,geometryValid=false;
  uint8_t status=Warming,count=0;
  float tau=2,noise=.005f;
  void reset(){
    initialized=false;count=head=0;valid=geometryValid=false;status=Warming;
    temperature=gradient=residual=gradientSigma=span=condition=0;
    p0=pz=0;lastDelta=0;
  }
  void observe(uint32_t ms,float z,float y){
    if(!isfinite(z)||!isfinite(y)||z<-.2f||z>3||y< -5||y>45||!(tau>0)||!isfinite(tau)){
      reset();status=Input;return;
    }
    if(!initialized){initialized=true;startMs=lastMs=storedMs=ms;origin=z;y0=y;temperature=y;return;}
    const uint32_t delta=ms-lastMs;
    if(!delta){valid=false;status=Stale;return;}
    if(delta>500){reset();status=Stale;return;}
    lastMs=ms;
    if(delta!=lastDelta){a=expf(-float(delta)*.001f/tau);lastDelta=delta;}
    p0=a*p0+(1-a);pz=a*pz+(1-a)*(z-origin);
    if(uint32_t(ms-storedMs)<250){if(geometryValid)temperature=y0+intercept+gradient*(z-origin);return;}
    storedMs=ms;
    q0[head]=p0;qz[head]=pz;qy[head]=y-y0;qd[head]=z;
    head=(head+1)%Capacity;if(count<Capacity)count++;
    valid=geometryValid=false;status=Geometry;if(count<8)return;
    float aa=0,ab=0,bb=0,ay=0,by=0,lo=z,hi=z;
    for(uint8_t i=0;i<count;i++){
      aa+=q0[i]*q0[i];ab+=q0[i]*qz[i];bb+=qz[i]*qz[i];
      ay+=q0[i]*qy[i];by+=qz[i]*qy[i];lo=fminf(lo,qd[i]);hi=fmaxf(hi,qd[i]);
    }
    span=hi-lo;if(span<.04f)return;
    // Checked Schur complement solves the centered 2x2 system without inverse.
    const float pivot=aa>0?bb-ab*ab/aa:0;
    condition=(aa>0&&bb>0)?aa*bb/fmaxf(1e-12f,aa*pivot):1e9f;
    status=Condition;if(!(aa>1e-5f)||!(pivot>.00002f)||condition>100000)return;
    gradient=(by-ab*ay/aa)/pivot;intercept=(ay-ab*gradient)/aa;
    temperature=y0+intercept+gradient*(z-origin);
    if(!isfinite(gradient)||!isfinite(temperature)||fabsf(gradient)>200||temperature< -5||temperature>45)return;
    geometryValid=true;supportDepth=origin+ab/aa;supportTemperature=y0+intercept+gradient*(ab/aa);
    float sse=0;
    for(uint8_t i=0;i<count;i++){const float e=qy[i]-q0[i]*intercept-qz[i]*gradient;sse+=e*e;}
    residual=sqrtf(sse/count);
    gradientSigma=sqrtf(fmaxf(noise*noise,sse/(count-2))/pivot);
    status=Warming;if(uint32_t(ms-startMs)*.001f<3*tau)return;
    status=Residual;if(residual>fmaxf(.04f,3*noise)||gradientSigma>fmaxf(1.0f,.8f*fabsf(gradient)))return;
    valid=true;status=Good;
  }
 private:
  bool initialized=false;
  uint8_t head=0;
  uint32_t lastMs=0,startMs=0,storedMs=0,lastDelta=0;
  float p0=0,pz=0,origin=0,y0=0,intercept=0,a=0;
  float q0[Capacity]={},qz[Capacity]={},qy[Capacity]={},qd[Capacity]={};
};
