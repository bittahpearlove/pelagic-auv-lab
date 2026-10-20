#pragma once
#include <math.h>
#include <stdint.h>
// Measured inputs only. Neither water truth nor analytic gradients enter here.
struct ExplorationObservation { float x,z,vx,vz,temperature; uint32_t ms; };
class Explorer {
 public:
  bool active=false,adaptive=true,local=false,gradientValid=false;
  uint8_t reason=0,visits=0,waypoint=0,localStep=0,localExit=0;
  float surge=0,heave=0,targetX=.4f,targetZ=.2f,gx=0,gz=0;
  float trigger=.08f,tau=2,distance=0,pathBudget=32;
  uint32_t budgetMs=300000;
  void begin(bool adapt=true){*this=Explorer();adaptive=adapt;active=true;}
  void stop(uint8_t why){active=false;local=false;surge=heave=0;reason=why;}
  void update(const ExplorationObservation&o){
    surge=heave=0;if(!active)return;
    if(!isfinite(o.x)||!isfinite(o.z)||!isfinite(o.vx)||!isfinite(o.vz)||!isfinite(o.temperature)||o.x<.2f||o.x>7.8f||o.z<.08f||o.z>2.85f||fabsf(o.vx)>2||fabsf(o.vz)>2||o.temperature< -5||o.temperature>45){stop(3);return;}
    if(initialized&&o.ms<=lastMs){stop(3);return;}lastMs=o.ms;
    if(initialized)distance+=hypotf(o.x-lastX,o.z-lastZ);
    else{initialized=true;anchorX=o.x;anchorZ=o.z;anchorT=o.temperature;lastVisitX=lastVisitZ=-100;}
    lastX=o.x;lastZ=o.z;markObserved(o.x,o.z);
    if(o.ms>=budgetMs){stop(2);return;}if(distance>=pathBudget){stop(6);return;}
    if(local){
      if(separated(o.x,o.z,fitLastX,fitLastZ,400))addFit(o);
      if(o.ms-localStart>=100000||distance-localDistance>=detourAllowance)endLocal(o,2);
    }else if(separated(o.x,o.z,anchorX,anchorZ,1500)){
      evidence=fabsf(o.temperature-anchorT)>=trigger?uint8_t(evidence+1):0;
      anchorX=o.x;anchorZ=o.z;anchorT=o.temperature;
      if(adaptive&&evidence>=2&&visits<3&&separated(o.x,o.z,lastVisitX,lastVisitZ,8001)){
        detourAllowance=fminf(5.0f,fmaxf(0,pathBudget-distance-remainingRoute(o)-.5f));
        if(detourAllowance<1.2f)evidence=0;
        else {local=true;visits++;localStep=0;localExit=0;localStart=o.ms;localDistance=distance;
        centreX=lastVisitX=o.x;centreZ=lastVisitZ=o.z;stable=weak=0;followX=(waypoint/2)%2?-1:1;followZ=0;clearFit(o);evidence=0;seedTarget();}
      }
    }
    if(local&&reached(o)){
      if(localStep>=4){
        stable=fabsf(o.temperature-(predictedT+predictGX*(o.x-predictX)+predictGZ*(o.z-predictZ)))<=.05f?uint8_t(stable+1):0;
        weak=gradientValid&&hypotf(gx,gz)<.35f?uint8_t(weak+1):0;
        if(stable>=3||weak>=2)endLocal(o,1); // Locally predictable / weak measured change.
      }
      if(local){localStep++;if(localStep<4)seedTarget();else if(!followTarget(o))endLocal(o,localExit==1?1:3);}
    }
    if(!local){coverageTarget();if(reached(o)){waypoint++;if(waypoint>=(adaptive?6:12)){stop(1);return;}coverageTarget();}}
    const float speed=local?fminf(.08f,.10f/fmaxf(.1f,tau)):.4f;
    const float vz=clip(1.8f*(targetZ-o.z),-speed,speed),vx=clip(1.8f*(targetX-o.x),-speed,speed);
    surge=clip((1.4f*vx+2*(vx-o.vx))/.8f,-1,1);heave=clip((1.8f*vz+.018f+2*(vz-o.vz))/.6f,-1,1);
  }
 private:
  bool initialized=false;uint8_t evidence=0,stable=0,weak=0,count=0,head=0;uint32_t localStart=0,lastMs=0;
  float anchorX=0,anchorZ=0,anchorT=0,centreX=0,centreZ=0,lastVisitX=0,lastVisitZ=0,lastX=0,lastZ=0,localDistance=0,detourAllowance=0;
  float fitLastX=0,fitLastZ=0,fitT=0,followX=1,followZ=0,predictedT=0,levelT=0,predictX=0,predictZ=0,predictGX=0,predictGZ=0;
  uint8_t observed[192]={};
  float qx[16]={},qz[16]={},qt[16]={};
  static float clip(float v,float lo,float hi){return fmaxf(lo,fminf(hi,v));}
  static bool separated(float x,float z,float a,float b,int32_t radius){
    const int32_t dx=int32_t(lroundf(x*10000))-int32_t(lroundf(a*10000)),dz=int32_t(lroundf(z*10000))-int32_t(lroundf(b*10000));
    return dx>=radius||dx<=-radius||dz>=radius||dz<=-radius||dx*dx+dz*dz>=radius*radius;
  }
  bool reached(const ExplorationObservation&o)const{
    const int32_t dx=int32_t(lroundf(targetX*10000))-int32_t(lroundf(o.x*10000)),dz=int32_t(lroundf(targetZ*10000))-int32_t(lroundf(o.z*10000));
    const int32_t horizontal=local?400:800,vertical=local?300:600;
    return dx>=-horizontal&&dx<=horizontal&&dz>=-vertical&&dz<=vertical;
  }
  float remainingRoute(const ExplorationObservation&o)const{
    float x=o.x,z=o.z,total=0;
    for(uint8_t i=waypoint;i<6;i++){const uint8_t row=i/2;const float nz=.3f+1.15f*row,nx=((row%2==0)==(i%2==0))?.4f:7.6f;total+=hypotf(nx-x,nz-z);x=nx;z=nz;}
    return total;
  }
  void coverageTarget(){const uint8_t row=waypoint/2;targetZ=adaptive?.3f+1.15f*row:.2f+.5f*row;targetX=((row%2==0)==(waypoint%2==0))?.4f:7.6f;}
  void seedTarget(){
    // A compact diamond establishes two-axis geometry; it is not repeated.
    static const float dx[]={.2f,0,-.2f,0},dz[]={0,.15f,0,-.15f};
    targetX=clip(centreX+dx[localStep],.4f,7.6f);targetZ=clip(centreZ+dz[localStep],.2f,2.7f);
  }
  static uint16_t cell(float x,float z){const uint8_t ix=uint8_t(clip(x*8,0,63)),iz=uint8_t(clip(z*8,0,23));return uint16_t(iz)*64+ix;}
  bool seen(float x,float z)const{const uint16_t i=cell(x,z);return observed[i/8]&(1<<(i%8));}
  void markObserved(float x,float z){const uint16_t i=cell(x,z);observed[i/8]|=1<<(i%8);}
  bool followTarget(const ExplorationObservation&o){
    if(!gradientValid)return false;
    const float n=hypotf(gx,gz);if(n<.1f)return false;
    float tx=-gz/n,tz=gx/n;if(tx*followX+tz*followZ<0){tx=-tx;tz=-tz;}
    const float correction=clip((levelT-o.temperature)/n,-.10f,.10f);
    bool found=false;float best=-100,bestX=0,bestZ=0,bestTx=0,bestTz=0;
    // Prefer unmeasured 0.125 m cells, then continuation with less correction.
    // No reward for merely collecting another correlated reading in the same cell.
    for(uint8_t i=0;i<4;i++){
      const float sign=i<2?1:-1;
      // Alternate along-feature travel with a normal contrast transect. This
      // samples a ribbon around the feature, rather than one isotherm only.
      const bool across=localStep%3==1;
      const float along=across?(i%2?.10f:-.10f):.25f*sign;
      const float normal=across?.25f*sign:correction+(i%2?.10f:-.10f);
      const float x=clip(o.x+along*tx+normal*gx/n,.4f,7.6f),z=clip(o.z+along*tz+normal*gz/n,.2f,2.7f);
      if(seen(x,z)||!separated(x,z,o.x,o.z,1200))continue;
      const float score=(sign>0?.2f:0)-(across?0:fabsf(normal));
      if(!found||score>best){found=true;best=score;bestX=x;bestZ=z;bestTx=sign*tx;bestTz=sign*tz;}
    }
    if(!found){localExit=1;return false;}
    targetX=bestX;targetZ=bestZ;followX=bestTx;followZ=bestTz;
    predictedT=o.temperature;predictX=o.x;predictZ=o.z;predictGX=gx;predictGZ=gz;
    return true;
  }
  void clearFit(const ExplorationObservation&o){count=head=0;gx=gz=0;gradientValid=false;fitT=levelT=o.temperature;addFit(o);}
  void addFit(const ExplorationObservation&o){
    qx[head]=o.x-centreX;qz[head]=o.z-centreZ;qt[head]=o.temperature-fitT;head=(head+1)%16;if(count<16)count++;
    fitLastX=o.x;fitLastZ=o.z;gradientValid=false;if(count<5)return;
    float sx=0,sz=0,st=0,sxx=0,szz=0,sxz=0,sxt=0,szt=0;
    for(uint8_t i=0;i<count;i++){const float x=qx[i],z=qz[i],t=qt[i];sx+=x;sz+=z;st+=t;sxx+=x*x;szz+=z*z;sxz+=x*z;sxt+=x*t;szt+=z*t;}
    const float xx=sxx-sx*sx/count,zz=szz-sz*sz/count,xz=sxz-sx*sz/count,xt=sxt-sx*st/count,zt=szt-sz*st/count,det=xx*zz-xz*xz;
    gradientValid=xx>.005f&&zz>.005f&&det>.02f*xx*zz;if(gradientValid){gx=(xt*zz-zt*xz)/det;gz=(zt*xx-xt*xz)/det;}
  }
  void endLocal(const ExplorationObservation&o,uint8_t why){local=false;localExit=why;evidence=0;anchorX=o.x;anchorZ=o.z;anchorT=o.temperature;}
};
