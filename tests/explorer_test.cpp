#include <cassert>
#include <cmath>
#include <iostream>
#include <set>
#include "../firmware/auv_nano/Explorer.h"
struct Run {float travel;int known,local,transits;};
static int cell(float x,float z){return int(z*8)*64+int(x*8);}
Run simulate(bool layer,float tau=2){
 Explorer c;c.begin();c.tau=tau;
 float x=4,z=.2f,vx=0,vz=0,t=22,lastTX=-1,lastTZ=-1;
 uint16_t previousKnown=0;uint8_t previousPhase=255;uint32_t phaseSince=0,localSince=0;bool wasLocal=false;
 int localRows=0,transits=0;std::set<int> observed;
 for(uint32_t ms=0;ms<=600000;ms+=100){
  observed.insert(cell(x,z));c.update({x,z,vx,vz,t,ms});
  assert(c.active&&c.reason==0&&c.knownCells>=previousKnown);previousKnown=c.knownCells;
  assert(isfinite(c.surge)&&isfinite(c.heave)&&fabsf(c.surge)<=1&&fabsf(c.heave)<=1);
  if(c.phase!=previousPhase){phaseSince=ms;previousPhase=c.phase;}
  if(c.local||c.phase==Explorer::Monitor)assert(ms-phaseSince<=8000);
  if(c.local){if(!wasLocal)localSince=ms;assert(ms-localSince<=8000);localRows++;}
  wasLocal=c.local;
  if(c.phase==Explorer::Transit&&(c.targetX!=lastTX||c.targetZ!=lastTZ)){
   assert(!observed.count(cell(c.targetX,c.targetZ)));transits++;
  }
  lastTX=c.targetX;lastTZ=c.targetZ;
  assert(c.targetX>=.4f&&c.targetX<=7.6f&&c.targetZ>=.2f&&c.targetZ<=2.7f);
  for(int i=0;i<2;i++){
   vx+=(.8f*c.surge-1.4f*vx)*.05f;vz+=(.6f*c.heave-1.8f*vz-.018f)*.05f;
   x+=vx*.05f;z+=vz*.05f;assert(x>=.2f&&x<=7.8f&&z>=.08f&&z<=2.85f);
   const float truth=layer?20.5f-1.5f*tanhf((z-1.3f)/.1f):22;t+=(truth-t)*(1-expf(-.05f/tau));
  }
 }
 assert(transits>10&&c.knownCells>40);
 c.stop(4);assert(!c.active&&c.phase==Explorer::Finished&&c.surge==0&&c.heave==0);
 return {c.distance,c.knownCells,localRows,transits};
}
int main(){
 const auto flat=simulate(false),layer=simulate(true),slow=simulate(true,8);
 assert(flat.local==0&&layer.local>0&&slow.local>0);
 Explorer invalid;invalid.begin();invalid.update({NAN,1,0,0,22,0});assert(!invalid.active&&invalid.reason==3);
 invalid.begin();invalid.update({4,.2f,0,0,22,0});invalid.update({4,.2f,0,0,22,0});assert(!invalid.active&&invalid.reason==3);
 Explorer clock;clock.begin();clock.update({4,.2f,0,0,22,4294967200UL});clock.update({4,.2f,0,0,22,4});assert(clock.active);
 clock.begin();assert(clock.knownCells==0);
 std::cout<<"PASS: 8 s local/hold limits, novel transit targets, retained memory, finite motion, operator stop, clock rollover; travel="<<layer.travel<<" m cells="<<layer.known<<" transits="<<layer.transits<<"\n";
}
