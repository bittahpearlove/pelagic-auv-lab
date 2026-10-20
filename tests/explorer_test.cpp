#include <cassert>
#include <cmath>
#include <iostream>
#include <set>
#include "../firmware/auv_nano/Explorer.h"
struct Run {float travel;int known,visits;};
static int cell(float x,float z){return int(z*8)*64+int(x*8);}
Run simulate(bool layer,float tau=2){
 Explorer c;c.begin();c.tau=tau;
 float x=4,z=.2f,vx=0,vz=0,t=22,lastTX=-1,lastTZ=-1,checkpoint=0;
 uint16_t previousKnown=0;uint8_t previousPhase=255;uint32_t phaseSince=0,localSince=0;bool wasLocal=false;
 bool transit=false,returned=false,resumed=false,ascended=false;std::set<int> observed;
 for(uint32_t ms=0;ms<=600000;ms+=100){
  observed.insert(cell(x,z));c.update({x,z,vx,vz,t,ms});
  assert(c.knownCells>=previousKnown);previousKnown=c.knownCells;
  if(!c.active){assert(c.reason==1&&c.surge==0&&c.heave==0&&z<=.14f);break;}
  assert(isfinite(c.surge)&&isfinite(c.heave)&&fabsf(c.surge)<=1&&fabsf(c.heave)<=1);
  if(c.phase!=previousPhase){
   if(c.phase==Explorer::Backtrack)checkpoint=z;
   if(c.phase==Explorer::Return){returned=true;assert(fabsf(c.targetX-4)<.001f&&fabsf(c.targetZ-checkpoint)<.001f);}
   if(previousPhase==Explorer::Return&&c.phase==Explorer::Descend){resumed=true;assert(fabsf(x-4)<.036f&&fabsf(z-checkpoint)<.031f);}
   phaseSince=ms;previousPhase=c.phase;
  }
  if(c.local){if(!wasLocal)localSince=ms;assert(ms-localSince<8000);}
  wasLocal=c.local;
  if(c.phase==Explorer::Transit){
   transit=true;assert(ms-phaseSince<10000);
   if(c.targetX!=lastTX||c.targetZ!=lastTZ)assert(!observed.count(cell(c.targetX,c.targetZ)));
  }
  ascended|=c.phase==Explorer::Ascend;
  if(fabsf(c.surge)<.999f&&fabsf(c.heave)<.999f){
   const float rx=(.8f*c.surge+2*vx)/3.4f,rz=(.6f*c.heave-.018f+2*vz)/3.8f;
   const float limit=(c.phase==Explorer::Descend||c.phase==Explorer::Transit||c.phase==Explorer::Return||c.phase==Explorer::Ascend)?.10f:c.phase==Explorer::Backtrack?fminf(.04f,.08f/tau):fminf(.08f,.10f/tau);
   assert(hypotf(rx,rz)<=limit+.00001f);
  }
  lastTX=c.targetX;lastTZ=c.targetZ;
  assert(c.targetX>=.4f&&c.targetX<=7.6f&&c.targetZ>=.1f&&c.targetZ<=2.7f);
  for(int i=0;i<2;i++){
   vx+=(.8f*c.surge-1.4f*vx)*.05f;vz+=(.6f*c.heave-1.8f*vz-.018f)*.05f;
   x+=vx*.05f;z+=vz*.05f;assert(x>=.2f&&x<=7.8f&&z>=.08f&&z<=2.85f);
   const float truth=layer?20.5f-1.5f*tanhf((z-1.3f)/.1f):22;t+=(truth-t)*(1-expf(-.05f/tau));
  }
 }
 assert(!c.active&&c.reason==1&&ascended);
 if(layer)assert(c.visits>0&&transit&&returned&&resumed);
 else assert(c.visits==0&&!transit);
 return {c.distance,c.knownCells,c.visits};
}
int main(){
 const auto flat=simulate(false),layer=simulate(true),slow=simulate(true,8);
 assert(flat.visits==0&&layer.visits>0&&slow.visits>0);
 // Frozen waypoint progress cannot renew the 10 s search allowance.
 Explorer frozen;frozen.begin();frozen.update({4,.2f,0,0,22,0});
 frozen.update({4,.4f,0,.1f,21,1000});frozen.update({4,.6f,0,.1f,20,2000});
 assert(frozen.local);frozen.update({4,.6f,0,0,20,10000});assert(frozen.phase==Explorer::Transit);
 for(uint32_t ms=10100;ms<20000;ms+=100){frozen.update({4,.6f,0,0,20,ms});assert(frozen.phase==Explorer::Transit);}
 Explorer missedReturn=frozen;
 missedReturn.update({4.3f,.6f,0,0,20,20000});assert(missedReturn.phase==Explorer::Return);
 missedReturn.update({4.3f,.6f,0,0,20,35000});assert(missedReturn.phase==Explorer::Ascend);
 missedReturn.update({4.3f,.6f,0,0,20,95000});assert(!missedReturn.active&&missedReturn.reason==6);
 frozen.update({4,.6f,0,0,20,20000});assert(frozen.phase==Explorer::Descend); // Already at checkpoint.
 // A failed return attempts ascent; a stalled ascent ends with explicit failure.
 frozen.update({4,2.7f,0,0,20,20100});assert(frozen.phase==Explorer::Ascend);
 frozen.update({4,2.7f,0,0,20,80100});assert(!frozen.active&&frozen.reason==6&&frozen.heave==0);
 Explorer invalid;invalid.begin();invalid.update({NAN,1,0,0,22,0});assert(!invalid.active&&invalid.reason==3);
 invalid.begin();invalid.update({4,.2f,0,0,22,0});invalid.update({4,.2f,0,0,22,0});assert(!invalid.active&&invalid.reason==3);
 Explorer clock;clock.begin();clock.update({4,.2f,0,0,22,4294967200UL});clock.update({4,.2f,0,0,22,4});assert(clock.active);
 clock.stop(4);assert(!clock.active&&clock.surge==0&&clock.heave==0);
 clock.begin();assert(clock.knownCells==0);
 std::cout<<"PASS: 8 s local and 10 s total search limits, checkpoint return, resumed descent, surface completion, stalled recovery, memory, stop, rollover; travel="<<layer.travel<<" m visits="<<layer.visits<<"\n";
}
