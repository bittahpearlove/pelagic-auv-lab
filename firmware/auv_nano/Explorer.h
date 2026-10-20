#pragma once
#include <math.h>
#include <stdint.h>
// Measured inputs only. Neither water truth nor analytic gradients enter here.
struct ExplorationObservation { float x,z,vx,vz,temperature; uint32_t ms; };
class Explorer {
 public:
  bool active=false,local=false,gradientValid=false;
  enum Phase : uint8_t { Descend=0,Backtrack=1,Probe=2,Follow=3,Finished=4,Monitor=5,Transit=6,Exhausted=7,Return=8,Ascend=9 };
  uint8_t reason=0,visits=0,phase=Descend,localStep=0,localExit=0;
  float surge=0,heave=0,targetX=4,targetZ=2.7f,gx=0,gz=0;
  uint16_t knownCells=0,rechecks=0;
  float trigger=.08f,tau=2,distance=0;
  void begin(){*this=Explorer();active=true;}
  void stop(uint8_t why){active=false;local=false;surge=heave=0;reason=why;phase=Finished;}
  void update(const ExplorationObservation&o){
    surge=heave=0;if(!active)return;
    if(!isfinite(o.x)||!isfinite(o.z)||!isfinite(o.vx)||!isfinite(o.vz)||!isfinite(o.temperature)||o.x<.2f||o.x>7.8f||o.z<.08f||o.z>2.85f||fabsf(o.vx)>2||fabsf(o.vz)>2||o.temperature< -5||o.temperature>45){stop(3);return;}
    if(initialized&&(uint32_t(o.ms-lastMs)==0||uint32_t(o.ms-lastMs)>0x7fffffffUL)){stop(3);return;}lastMs=o.ms;
    if(initialized)distance+=hypotf(o.x-lastX,o.z-lastZ);
    else{initialized=true;anchorX=o.x;anchorZ=o.z;anchorT=o.temperature;descentX=o.x;}
    lastX=o.x;lastZ=o.z;markObserved(o.x,o.z);
    if(phase==Descend){
      targetX=descentX;targetZ=2.7f;
      if(reached(o))startAscent(o);
      else if(o.z>=nextInvestigationZ&&changed(o)){resumeZ=o.z;startLocal(o,true);}
    }
    if(phase==Transit){
      // One deadline covers ALL waypoint hops. No nested investigation may
      // restart it; observations still contribute to the local measured fit.
      if(separated(o.x,o.z,fitLastX,fitLastZ,400))addFit(o);
      if(uint32_t(o.ms-transitStart)>=10000)startReturn(o);
      else if(reached(o))chooseFrontier(o);
    }
    if(phase==Monitor||phase==Exhausted)startReturn(o);
    if(local){
      if(separated(o.x,o.z,fitLastX,fitLastZ,400))addFit(o);
      // Every local burst (including retrace) has its own 8 s deadline, shared by retrace and probing.
      if(uint32_t(o.ms-phaseStart)>=8000){if(localExit!=5)localExit=2;chooseFrontier(o);}
      else if(phase==Backtrack){
        if(reached(o)){phase=Probe;centreZ=o.z;clearFit(o);if(!seedTarget())chooseFrontier(o);}
      }else if(reached(o)){
        localStep++;
        if(localStep<2){if(!seedTarget())chooseFrontier(o);}
        else {if(localExit!=5)localExit=1;chooseFrontier(o);}
      }
    }
    if(phase==Return){
      if(reached(o)){
        phase=Descend;targetX=descentX;targetZ=2.7f;
        // Clear reversal/lag history and pass the investigated interval before
        // rearming. Strict depth progress prevents the same boundary loop.
        nextInvestigationZ=resumeZ+.25f;resetDetection(o);
      }else if(uint32_t(o.ms-phaseStart)>=15000)startAscent(o);
    }
    if(phase==Ascend){
      if(o.z<=.14f&&fabsf(o.vz)<.03f){stop(1);return;}
      if(uint32_t(o.ms-phaseStart)>=60000){stop(6);return;}
    }
    const float speed=(phase==Descend||phase==Transit||phase==Return||phase==Ascend)?.10f:phase==Backtrack?fminf(.04f,.08f/fmaxf(.1f,tau)):fminf(.08f,.10f/fmaxf(.1f,tau));
    float vz=1.8f*(targetZ-o.z),vx=1.8f*(targetX-o.x);
    // Limit the vector norm: independent axis clipping allowed sqrt(2)*speed.
    const float magnitude=hypotf(vx,vz);
    if(magnitude>speed){vx*=speed/magnitude;vz*=speed/magnitude;}
    surge=clip((1.4f*vx+2*(vx-o.vx))/.8f,-1,1);heave=clip((1.8f*vz+.018f+2*(vz-o.vz))/.6f,-1,1);
  }
 private:
  bool initialized=false;
  uint8_t evidence=0,count=0,head=0;
  uint32_t lastMs=0,phaseStart=0,transitStart=0;
  float resumeZ=.2f,nextInvestigationZ=.2f;
  float previousDX=0,previousDZ=0;
  float anchorX=0,anchorZ=0,anchorT=0,centreX=0,centreZ=0,descentX=4,triggerZ=0,lastX=0,lastZ=0;
  float fitLastX=0,fitLastZ=0,fitT=0;
  uint8_t observed[192]={};
  float qx[16]={},qz[16]={},qt[16]={};
  static float clip(float v,float lo,float hi){return fmaxf(lo,fminf(hi,v));}
  bool changed(const ExplorationObservation&o){
    if(!separated(o.x,o.z,anchorX,anchorZ,1500))return false;
    const float dx=o.x-anchorX,dz=o.z-anchorZ,length=hypotf(dx,dz);
    // Consecutive, direction-consistent spatial windows. A point or a hold
    // cannot establish a gradient. Threshold is in C/m, with a delta floor.
    if(dx*previousDX+dz*previousDZ<0)evidence=0;
    const float delta=fabsf(o.temperature-anchorT);
    evidence=delta>=trigger&&delta/length>=2.0f?uint8_t(evidence+1):0;
    anchorX=o.x;anchorZ=o.z;anchorT=o.temperature;previousDX=dx;previousDZ=dz;
    return evidence>=2;
  }
  static bool separated(float x,float z,float a,float b,int32_t radius){
    const int32_t dx=int32_t(lroundf(x*10000))-int32_t(lroundf(a*10000)),dz=int32_t(lroundf(z*10000))-int32_t(lroundf(b*10000));
    return dx>=radius||dx<=-radius||dz>=radius||dz<=-radius||dx*dx+dz*dz>=radius*radius;
  }
  bool reached(const ExplorationObservation&o)const{
    const int32_t dx=int32_t(lroundf(targetX*10000))-int32_t(lroundf(o.x*10000)),dz=int32_t(lroundf(targetZ*10000))-int32_t(lroundf(o.z*10000));
    const int32_t horizontal=(local||phase==Transit||phase==Return)?350:800,vertical=(local||phase==Transit||phase==Return)?300:600;
    return dx>=-horizontal&&dx<=horizontal&&dz>=-vertical&&dz<=vertical;
  }
  bool seedTarget(){
    // Two short adjoining legs establish x/z geometry without a return diamond.
    const float sign=centreX+.125f<=localX(10)?1:-1;
    targetX=localX(centreX+.125f*sign);
    targetZ=localZ(centreZ+(localStep?.125f:0));
    if(localStep&&(fabsf(targetZ-centreZ)<.08f||seen(targetX,targetZ)))targetZ=localZ(centreZ-.125f);
    if(seen(targetX,targetZ))targetX=localX(centreX-.125f*sign);
    return !seen(targetX,targetZ);
  }
  float localX(float x)const{return clip(x,fmaxf(.4f,centreX-.45f),fminf(7.6f,centreX+.45f));}
  float localZ(float z)const{return clip(z,fmaxf(.2f,triggerZ-.45f),fminf(2.7f,triggerZ+.10f));}
  static uint16_t cell(float x,float z){const uint8_t ix=uint8_t(clip(x*8,0,63)),iz=uint8_t(clip(z*8,0,23));return uint16_t(iz)*64+ix;}
  bool seen(float x,float z)const{const uint16_t i=cell(x,z);return observed[i/8]&(1<<(i%8));}
  void markObserved(float x,float z){
    const uint16_t i=cell(x,z);const uint8_t bit=1<<(i%8);
    if(!(observed[i/8]&bit)){observed[i/8]|=bit;knownCells++;}
  }
  void clearFit(const ExplorationObservation&o){count=head=0;gx=gz=0;gradientValid=false;fitT=o.temperature;addFit(o);}
  void addFit(const ExplorationObservation&o){
    qx[head]=o.x-centreX;qz[head]=o.z-centreZ;qt[head]=o.temperature-fitT;head=(head+1)%16;if(count<16)count++;
    fitLastX=o.x;fitLastZ=o.z;gradientValid=false;if(count<5)return;
    float sx=0,sz=0,st=0,sxx=0,szz=0,sxz=0,sxt=0,szt=0;
    for(uint8_t i=0;i<count;i++){const float x=qx[i],z=qz[i],t=qt[i];sx+=x;sz+=z;st+=t;sxx+=x*x;szz+=z*z;sxz+=x*z;sxt+=x*t;szt+=z*t;}
    const float xx=sxx-sx*sx/count,zz=szz-sz*sz/count,xz=sxz-sx*sz/count,xt=sxt-sx*st/count,zt=szt-sz*st/count,det=xx*zz-xz*xz;
    gradientValid=xx>.005f&&zz>.005f&&det>.02f*xx*zz;if(gradientValid){gx=(xt*zz-zt*xz)/det;gz=(zt*xx-xt*xz)/det;}
  }
  void startLocal(const ExplorationObservation&o,bool retrace){
    local=true;if(visits<255)visits++;
    phase=retrace?Backtrack:Probe;phaseStart=o.ms;localStep=0;localExit=0;
    triggerZ=o.z;centreX=o.x;centreZ=o.z;clearFit(o);
    if(retrace){
      targetX=o.x;
      const float speed=fminf(.04f,.08f/fmaxf(.1f,tau));
      const float required=hypotf(o.vx,o.vz)*tau+.30f; // lag + two detection windows
      const float feasible=3.6f*speed; // reserve 4.4 s of the 8 s for local geometry
      const float retraceDistance=fminf(required,feasible);
      targetZ=clip(o.z-retraceDistance,.2f,2.7f);
      if(o.z-targetZ+.03f<required)localExit=5; // unresolved lag margin, not a validated boundary
    }else if(!seedTarget())chooseFrontier(o);
  }
  void resetDetection(const ExplorationObservation&o){
    evidence=0;previousDX=previousDZ=0;anchorX=o.x;anchorZ=o.z;anchorT=o.temperature;
  }
  void startReturn(const ExplorationObservation&o){
    local=false;phase=Return;phaseStart=o.ms;targetX=descentX;targetZ=resumeZ;
  }
  void startAscent(const ExplorationObservation&o){
    local=false;phase=Ascend;phaseStart=o.ms;targetX=o.x;targetZ=.10f;
  }
  void chooseFrontier(const ExplorationObservation&o){
    const bool continuingTransit=phase==Transit;
    if(!continuingTransit)transitStart=o.ms;
    // Integer millimetres keep distance/turn scores identical on AVR and native.
    // Penalize known-water transit and sharp reversals, not just endpoint length.
    const int32_t ox=lroundf(o.x*1000),oz=lroundf(o.z*1000);
    const int32_t headingX=lroundf(o.vx*1000),headingZ=lroundf(o.vz*1000);
    bool found=false;int32_t best=2147483647L;int16_t bx=0,bz=0;
    for(uint8_t iz=2;iz<=21;iz++)for(uint8_t ix=3;ix<=60;ix++){
      const uint16_t i=uint16_t(iz)*64+ix;
      if(observed[i/8]&(1<<(i%8)))continue;
      const int16_t x=ix*125+62,z=iz*125+62;
      if(x<400||x>7600||z<200||z>2700)continue;
      if(fabsf(x/1000.0f-centreX)>.45f||z/1000.0f<triggerZ-.45f||z/1000.0f>triggerZ+.10f)continue;
      const int32_t dx=x-ox,dz=z-oz,d2=dx*dx+dz*dz;
      if(d2<14400||d2>=best)continue;
      int32_t cost=d2;
      for(uint8_t step=1;step<8;step++){
        const int32_t px=ox+dx*step/8,pz=oz+dz*step/8;
        const uint16_t ci=uint16_t(pz/125)*64+uint16_t(px/125);
        if(observed[ci/8]&(1<<(ci%8)))cost+=6000;
      }
      if(dx*headingX+dz*headingZ<0)cost+=12000;
      if(cost<best){found=true;best=cost;bx=x;bz=z;}
    }
    local=false;phaseStart=o.ms;
    if(found){phase=Transit;targetX=bx/1000.0f;targetZ=bz/1000.0f;}
    else{
      startReturn(o); // No local frontier: resume the profile, never idle forever.
    }
    if(!continuingTransit)resetDetection(o);
  }
};
